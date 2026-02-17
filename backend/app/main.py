import csv
import io
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .config import get_settings
from .csv_utils import read_csv
from .supabase_client import get_supabase_client


app = FastAPI(title="Reconcile API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "*")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QualificationIn(BaseModel):
    keyword: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1)


class QualificationOut(QualificationIn):
    id: str
    created_at: Optional[str] = None


class ImportCreateResponse(BaseModel):
    import_id: str
    row_count: int
    output_file_path: str


class ImportPreviewResponse(BaseModel):
    import_data: Dict[str, Any]
    total_rows: int
    page: int
    page_size: int
    rows: List[Dict[str, Any]]


def _get_client():
    try:
        return get_supabase_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _get_error(response: Any) -> Optional[str]:
    if hasattr(response, "error") and response.error:
        return str(response.error)
    if isinstance(response, dict) and response.get("error"):
        return str(response["error"])
    return None


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_")
    return cleaned or "arquivo.csv"


def _load_output_csv(supabase, bucket: str, path: str) -> List[Dict[str, Any]]:
    data = supabase.storage.from_(bucket).download(path)
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="replace")
    else:
        text = str(data)
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/qualifications", response_model=List[QualificationOut])
def list_qualifications():
    supabase = _get_client()
    response = (
        supabase.table("qualifications")
        .select("*")
        .order("priority", desc=False)
        .execute()
    )
    error = _get_error(response)
    if error:
        raise HTTPException(status_code=500, detail=error)
    return response.data or []


@app.post("/qualifications", response_model=QualificationOut)
def create_qualification(payload: QualificationIn):
    supabase = _get_client()
    response = (
        supabase.table("qualifications")
        .insert(payload.model_dump())
        .execute()
    )
    error = _get_error(response)
    if error:
        raise HTTPException(status_code=500, detail=error)

    if not response.data:
        raise HTTPException(status_code=500, detail="Falha ao criar qualificacao")
    return response.data[0]


@app.post("/imports", response_model=ImportCreateResponse)
async def create_import(
    file: UploadFile = File(...),
    company: str = Form(...),
    bank: str = Form(...),
    agency: str = Form(...),
    account: str = Form(...),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    try:
        rows, _ = read_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    supabase = _get_client()
    settings = get_settings()

    qualifications_response = (
        supabase.table("qualifications")
        .select("*")
        .order("priority", desc=False)
        .execute()
    )
    error = _get_error(qualifications_response)
    if error:
        raise HTTPException(status_code=500, detail=error)

    qualifications = qualifications_response.data or []
    for q in qualifications:
        q["_keyword_lower"] = (q.get("keyword") or "").lower()

    output_rows = []
    for row in rows:
        historico = row.get("historico", "")
        historico_lower = historico.lower()
        match = None
        for q in qualifications:
            key = q.get("_keyword_lower", "")
            if key and key in historico_lower:
                match = q
                break

        output_rows.append(
            {
                "empresa": company,
                "banco": bank,
                "agencia": agency,
                "conta": account,
                "data": row.get("data", ""),
                "valor": row.get("valor", ""),
                "historico": historico,
                "codigo_qualificacao": match.get("code") if match else "",
                "descricao_qualificacao": match.get("description") if match else "",
            }
        )

    output_buffer = io.StringIO()
    writer = csv.DictWriter(
        output_buffer,
        fieldnames=[
            "empresa",
            "banco",
            "agencia",
            "conta",
            "data",
            "valor",
            "historico",
            "codigo_qualificacao",
            "descricao_qualificacao",
        ],
    )
    writer.writeheader()
    writer.writerows(output_rows)
    output_bytes = output_buffer.getvalue().encode("utf-8")

    import_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    input_name = _safe_filename(file.filename or "input.csv")
    input_path = f"{import_id}/{timestamp}_{input_name}"
    output_path = f"{import_id}/{timestamp}_output.csv"

    input_upload = supabase.storage.from_(settings.supabase_inputs_bucket).upload(
        input_path,
        content,
        {"content-type": file.content_type or "text/csv"},
    )
    error = _get_error(input_upload)
    if error:
        raise HTTPException(status_code=500, detail=f"Upload input falhou: {error}")

    output_upload = supabase.storage.from_(settings.supabase_outputs_bucket).upload(
        output_path,
        output_bytes,
        {"content-type": "text/csv"},
    )
    error = _get_error(output_upload)
    if error:
        raise HTTPException(status_code=500, detail=f"Upload output falhou: {error}")

    import_record = {
        "id": import_id,
        "company": company,
        "bank": bank,
        "agency": agency,
        "account": account,
        "input_file_path": input_path,
        "output_file_path": output_path,
        "row_count": len(output_rows),
    }

    insert_response = supabase.table("imports").insert(import_record).execute()
    error = _get_error(insert_response)
    if error:
        raise HTTPException(status_code=500, detail=error)

    return ImportCreateResponse(
        import_id=import_id,
        row_count=len(output_rows),
        output_file_path=output_path,
    )


@app.get("/imports/{import_id}", response_model=ImportPreviewResponse)
def get_import(
    import_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    supabase = _get_client()
    settings = get_settings()

    import_response = (
        supabase.table("imports")
        .select("*")
        .eq("id", import_id)
        .limit(1)
        .execute()
    )
    error = _get_error(import_response)
    if error:
        raise HTTPException(status_code=500, detail=error)

    if not import_response.data:
        raise HTTPException(status_code=404, detail="Importacao nao encontrada")

    import_data = import_response.data[0]
    output_path = import_data.get("output_file_path")
    if not output_path:
        raise HTTPException(status_code=404, detail="Arquivo de saida nao encontrado")

    all_rows = _load_output_csv(supabase, settings.supabase_outputs_bucket, output_path)
    total_rows = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    rows = all_rows[start:end]

    return ImportPreviewResponse(
        import_data=import_data,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        rows=rows,
    )


@app.get("/imports/{import_id}/download")
def download_import(import_id: str):
    supabase = _get_client()
    settings = get_settings()

    import_response = (
        supabase.table("imports")
        .select("*")
        .eq("id", import_id)
        .limit(1)
        .execute()
    )
    error = _get_error(import_response)
    if error:
        raise HTTPException(status_code=500, detail=error)

    if not import_response.data:
        raise HTTPException(status_code=404, detail="Importacao nao encontrada")

    output_path = import_response.data[0].get("output_file_path")
    if not output_path:
        raise HTTPException(status_code=404, detail="Arquivo de saida nao encontrado")

    data = supabase.storage.from_(settings.supabase_outputs_bucket).download(output_path)
    if not isinstance(data, bytes):
        raise HTTPException(status_code=500, detail="Falha ao baixar arquivo")

    filename = os.path.basename(output_path)
    headers = {
        "Content-Disposition": f"attachment; filename={filename}"
    }
    return Response(content=data, media_type="text/csv", headers=headers)
