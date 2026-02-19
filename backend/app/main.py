import csv
import io
import os
import re
import uuid
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .config import get_settings
from .csv_utils import read_csv
from .supabase_client import get_supabase_client


app = FastAPI(title="Reconcile API", version="0.1.0")

RULE_TYPES = {"financeira", "gerencial"}
RuleType = Literal["financeira", "gerencial"]

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
    rule_type: RuleType


class QualificationOut(QualificationIn):
    id: str
    created_at: Optional[str] = None


class ImportCreateResponse(BaseModel):
    import_id: str
    row_count: int
    output_file_path: str
    rule_type: RuleType


class ImportPreviewResponse(BaseModel):
    import_data: Dict[str, Any]
    total_rows: int
    page: int
    page_size: int
    rows: List[Dict[str, Any]]


class ImportOut(BaseModel):
    id: str
    company: Optional[str] = None
    bank: Optional[str] = None
    agency: Optional[str] = None
    account: Optional[str] = None
    input_file_path: Optional[str] = None
    output_file_path: Optional[str] = None
    row_count: Optional[int] = None
    created_at: Optional[str] = None
    rule_type: Optional[RuleType] = None


class ImportListResponse(BaseModel):
    items: List[ImportOut]
    page: int
    page_size: int
    total: int
    sort_by: str
    sort_dir: str


class RequalifyRequest(BaseModel):
    rule_type: RuleType
    import_ids: List[str]


class RequalifyResult(BaseModel):
    id: str
    company: Optional[str] = None
    account: Optional[str] = None
    row_count: int
    rule_type: RuleType


class RequalifiedItemsResponse(BaseModel):
    total_rows: int
    page: int
    page_size: int
    rows: List[Dict[str, Any]]


class RuleCount(BaseModel):
    id: Optional[str] = None
    keyword: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[RuleType] = None
    count: int


class UnqualifiedHistory(BaseModel):
    historico: str
    count: int


class DashboardResponse(BaseModel):
    total_records: int
    total_companies: int
    total_accounts: int
    total_imports: int
    total_rules: int
    unqualified_records: int
    items_per_rule: List[RuleCount]
    unqualified_histories: List[UnqualifiedHistory]


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


def _validate_rule_type(rule_type: str) -> None:
    if rule_type not in RULE_TYPES:
        raise HTTPException(status_code=400, detail="Tipo de regra invalido")


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_")
    return cleaned or "arquivo.csv"


def _load_qualifications(supabase, rule_type: str) -> List[Dict[str, Any]]:
    response = (
        supabase.table("qualifications")
        .select("*")
        .eq("rule_type", rule_type)
        .order("priority", desc=False)
        .execute()
    )
    error = _get_error(response)
    if error:
        raise HTTPException(status_code=500, detail=error)
    qualifications = response.data or []
    for q in qualifications:
        q["_keyword_norm"] = _normalize_text(q.get("keyword") or "")
    return qualifications


def _normalize_text(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = (
        raw.replace("“", "\"")
        .replace("”", "\"")
        .replace("‘", "'")
        .replace("’", "'")
    )
    normalized = unicodedata.normalize("NFD", raw)
    without_accents = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    cleaned = re.sub(r"[^0-9a-z]+", " ", without_accents)
    return " ".join(cleaned.split())


def _apply_qualifications(
    rows: List[Dict[str, Any]],
    qualifications: List[Dict[str, Any]],
    company: str,
    bank: str,
    agency: str,
    account: str,
) -> List[Dict[str, Any]]:
    output_rows = []
    for row in rows:
        historico = row.get("historico", "")
        historico_norm = _normalize_text(historico)
        match = None
        for q in qualifications:
            key = q.get("_keyword_norm", "")
            if key and key in historico_norm:
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
    return output_rows


def _build_output_csv(output_rows: List[Dict[str, Any]]) -> bytes:
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
    return output_buffer.getvalue().encode("utf-8")


def _remove_storage_file(supabase, bucket: str, path: Optional[str]) -> None:
    if not path:
        return
    storage = supabase.storage.from_(bucket)
    try:
        if hasattr(storage, "remove"):
            storage.remove([path])
        elif hasattr(storage, "delete"):
            storage.delete(path)
    except Exception:
        return


def _load_all_output_rows(supabase, settings) -> List[Dict[str, Any]]:
    imports_response = (
        supabase.table("imports")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    error = _get_error(imports_response)
    if error:
        raise HTTPException(status_code=500, detail=error)

    rows: List[Dict[str, Any]] = []
    for item in imports_response.data or []:
        output_path = item.get("output_file_path")
        if not output_path:
            continue
        output_rows = _load_output_csv(
            supabase, settings.supabase_outputs_bucket, output_path
        )
        rows.extend(output_rows)
    return rows


def _sort_requalified_rows(
    rows: List[Dict[str, Any]], sort_by: str, sort_dir: str
) -> List[Dict[str, Any]]:
    allowed = {
        "empresa",
        "banco",
        "agencia",
        "conta",
        "data",
        "valor",
        "historico",
        "codigo_qualificacao",
        "descricao_qualificacao",
    }
    if sort_by not in allowed:
        return rows

    reverse = sort_dir == "desc"

    def key_fn(item: Dict[str, Any]):
        value = item.get(sort_by)
        if value is None:
            return ""
        if sort_by == "valor":
            try:
                return float(str(value).replace(",", "."))
            except ValueError:
                return 0.0
        if sort_by == "data":
            try:
                return datetime.fromisoformat(str(value))
            except ValueError:
                return str(value)
        return str(value).lower()

    return sorted(rows, key=key_fn, reverse=reverse)


def _count_unique(values: List[str]) -> int:
    cleaned = {str(value).strip() for value in values if str(value).strip()}
    return len(cleaned)


def _build_rule_counts(
    qualifications: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    historicos_norm = [
        _normalize_text(row.get("historico") or "") for row in rows
    ]

    results: List[Dict[str, Any]] = []
    for q in qualifications:
        code = str(q.get("code") or "").strip()
        desc = str(q.get("description") or "").strip()
        keyword_norm = _normalize_text(q.get("keyword") or "")
        count = 0
        if keyword_norm:
            count = sum(
                1 for historico in historicos_norm if keyword_norm in historico
            )
        results.append(
            {
                "id": q.get("id"),
                "keyword": q.get("keyword"),
                "code": code or None,
                "description": desc or None,
                "rule_type": q.get("rule_type"),
                "count": count,
            }
        )

    results.sort(
        key=lambda item: (
            -item.get("count", 0),
            str(item.get("code") or ""),
            str(item.get("description") or ""),
        )
    )
    return results


def _build_unqualified_histories(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for row in rows:
        code = str(row.get("codigo_qualificacao") or "").strip()
        desc = str(row.get("descricao_qualificacao") or "").strip()
        if code or desc:
            continue
        historico = str(row.get("historico") or "").strip()
        if not historico:
            continue
        counts[historico] = counts.get(historico, 0) + 1

    results = [
        {"historico": historico, "count": count}
        for historico, count in counts.items()
    ]
    results.sort(key=lambda item: (-item["count"], item["historico"]))
    return results


def _filter_requalified_rows(
    rows: List[Dict[str, Any]], search: Optional[str]
) -> List[Dict[str, Any]]:
    if not search:
        return rows
    term = search.strip().lower()
    if not term:
        return rows
    filtered = []
    for row in rows:
        historico = str(row.get("historico") or "").lower()
        if term in historico:
            filtered.append(row)
    return filtered


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
def list_qualifications(rule_type: Optional[str] = Query(None)):
    supabase = _get_client()
    query = supabase.table("qualifications").select("*")
    if rule_type:
        _validate_rule_type(rule_type)
        query = query.eq("rule_type", rule_type)
    response = query.order("priority", desc=False).execute()
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


@app.put("/qualifications/{qualification_id}", response_model=QualificationOut)
def update_qualification(qualification_id: str, payload: QualificationIn):
    supabase = _get_client()
    response = (
        supabase.table("qualifications")
        .update(payload.model_dump())
        .eq("id", qualification_id)
        .execute()
    )
    error = _get_error(response)
    if error:
        raise HTTPException(status_code=500, detail=error)
    if not response.data:
        raise HTTPException(status_code=404, detail="Qualificacao nao encontrada")
    return response.data[0]


@app.delete("/qualifications/{qualification_id}")
def delete_qualification(qualification_id: str):
    supabase = _get_client()
    response = (
        supabase.table("qualifications")
        .delete()
        .eq("id", qualification_id)
        .execute()
    )
    error = _get_error(response)
    if error:
        raise HTTPException(status_code=500, detail=error)
    if not response.data:
        raise HTTPException(status_code=404, detail="Qualificacao nao encontrada")
    return {"status": "ok"}


@app.post("/imports", response_model=ImportCreateResponse)
async def create_import(
    file: UploadFile = File(...),
    company: str = Form(...),
    bank: str = Form(...),
    agency: str = Form(...),
    account: str = Form(...),
    rule_type: str = Form("financeira"),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    try:
        rows, _ = read_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _validate_rule_type(rule_type)
    supabase = _get_client()
    settings = get_settings()

    qualifications = _load_qualifications(supabase, rule_type)
    output_rows = _apply_qualifications(
        rows=rows,
        qualifications=qualifications,
        company=company,
        bank=bank,
        agency=agency,
        account=account,
    )

    output_bytes = _build_output_csv(output_rows)

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
        "rule_type": rule_type,
    }

    insert_response = supabase.table("imports").insert(import_record).execute()
    error = _get_error(insert_response)
    if error:
        raise HTTPException(status_code=500, detail=error)

    return ImportCreateResponse(
        import_id=import_id,
        row_count=len(output_rows),
        output_file_path=output_path,
        rule_type=rule_type,
    )


@app.get("/imports", response_model=ImportListResponse)
def list_imports(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
):
    allowed_sort = {"created_at", "company", "account", "row_count", "rule_type"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"

    start = (page - 1) * page_size
    end = start + page_size - 1

    supabase = _get_client()
    response = (
        supabase.table("imports")
        .select("*", count="exact")
        .order(sort_by, desc=sort_dir == "desc")
        .range(start, end)
        .execute()
    )
    error = _get_error(response)
    if error:
        raise HTTPException(status_code=500, detail=error)

    total = response.count if hasattr(response, "count") else None
    if total is None:
        total = len(response.data or [])

    return ImportListResponse(
        items=response.data or [],
        page=page,
        page_size=page_size,
        total=total,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@app.post("/imports/requalify", response_model=List[RequalifyResult])
def requalify_imports(payload: RequalifyRequest):
    if not payload.import_ids:
        raise HTTPException(status_code=400, detail="Selecione importacoes")

    supabase = _get_client()
    settings = get_settings()
    qualifications = _load_qualifications(supabase, payload.rule_type)
    results: List[RequalifyResult] = []

    for import_id in payload.import_ids:
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
            raise HTTPException(
                status_code=404, detail=f"Importacao nao encontrada: {import_id}"
            )

        import_data = import_response.data[0]
        input_path = import_data.get("input_file_path")
        if not input_path:
            raise HTTPException(
                status_code=404, detail=f"Arquivo de entrada ausente: {import_id}"
            )

        try:
            input_bytes = supabase.storage.from_(
                settings.supabase_inputs_bucket
            ).download(input_path)
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Falha ao baixar input: {import_id}"
            ) from exc

        if not isinstance(input_bytes, bytes):
            raise HTTPException(
                status_code=500, detail=f"Falha ao ler input: {import_id}"
            )

        try:
            rows, _ = read_csv(input_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        output_rows = _apply_qualifications(
            rows=rows,
            qualifications=qualifications,
            company=str(import_data.get("company") or ""),
            bank=str(import_data.get("bank") or ""),
            agency=str(import_data.get("agency") or ""),
            account=str(import_data.get("account") or ""),
        )
        output_bytes = _build_output_csv(output_rows)

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        output_path = f"{import_id}/{timestamp}_output.csv"

        output_upload = supabase.storage.from_(
            settings.supabase_outputs_bucket
        ).upload(
            output_path,
            output_bytes,
            {"content-type": "text/csv"},
        )
        error = _get_error(output_upload)
        if error:
            raise HTTPException(status_code=500, detail=f"Upload output falhou: {error}")

        previous_output = import_data.get("output_file_path")
        if previous_output and previous_output != output_path:
            _remove_storage_file(supabase, settings.supabase_outputs_bucket, previous_output)

        update_response = (
            supabase.table("imports")
            .update(
                {
                    "output_file_path": output_path,
                    "row_count": len(output_rows),
                    "rule_type": payload.rule_type,
                }
            )
            .eq("id", import_id)
            .execute()
        )
        error = _get_error(update_response)
        if error:
            raise HTTPException(status_code=500, detail=error)

        results.append(
            RequalifyResult(
                id=import_id,
                company=import_data.get("company"),
                account=import_data.get("account"),
                row_count=len(output_rows),
                rule_type=payload.rule_type,
            )
        )

    return results


@app.delete("/imports/{import_id}")
def delete_import(import_id: str):
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
    _remove_storage_file(supabase, settings.supabase_inputs_bucket, import_data.get("input_file_path"))
    _remove_storage_file(supabase, settings.supabase_outputs_bucket, import_data.get("output_file_path"))

    delete_response = (
        supabase.table("imports")
        .delete()
        .eq("id", import_id)
        .execute()
    )
    error = _get_error(delete_response)
    if error:
        raise HTTPException(status_code=500, detail=error)
    if not delete_response.data:
        raise HTTPException(status_code=404, detail="Importacao nao encontrada")
    return {"status": "ok"}


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


@app.get("/requalified-items", response_model=RequalifiedItemsResponse)
def list_requalified_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    sort_by: str = Query("data"),
    sort_dir: str = Query("desc"),
    search: Optional[str] = Query(None),
):
    supabase = _get_client()
    settings = get_settings()
    all_rows = _load_all_output_rows(supabase, settings)
    all_rows = _filter_requalified_rows(all_rows, search)
    all_rows = _sort_requalified_rows(all_rows, sort_by, sort_dir)
    total_rows = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    rows = all_rows[start:end]

    return RequalifiedItemsResponse(
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        rows=rows,
    )


@app.get("/dashboard", response_model=DashboardResponse)
def get_dashboard():
    supabase = _get_client()
    settings = get_settings()

    all_rows = _load_all_output_rows(supabase, settings)
    total_records = len(all_rows)

    companies = [str(row.get("empresa") or "") for row in all_rows]
    total_companies = _count_unique(companies)

    account_keys = []
    for row in all_rows:
        agencia = str(row.get("agencia") or "").strip()
        conta = str(row.get("conta") or "").strip()
        if not agencia and not conta:
            continue
        account_keys.append(f"{agencia}::{conta}")
    total_accounts = _count_unique(account_keys)

    imports_response = (
        supabase.table("imports").select("id", count="exact").execute()
    )
    error = _get_error(imports_response)
    if error:
        raise HTTPException(status_code=500, detail=error)
    total_imports = (
        imports_response.count
        if hasattr(imports_response, "count") and imports_response.count is not None
        else len(imports_response.data or [])
    )

    qualifications_response = (
        supabase.table("qualifications").select("*").execute()
    )
    error = _get_error(qualifications_response)
    if error:
        raise HTTPException(status_code=500, detail=error)
    qualifications = qualifications_response.data or []
    total_rules = len(qualifications)

    items_per_rule = _build_rule_counts(qualifications, all_rows)
    unqualified_histories = _build_unqualified_histories(all_rows)
    unqualified_records = sum(item["count"] for item in unqualified_histories)

    return DashboardResponse(
        total_records=total_records,
        total_companies=total_companies,
        total_accounts=total_accounts,
        total_imports=total_imports,
        total_rules=total_rules,
        unqualified_records=unqualified_records,
        items_per_rule=items_per_rule,
        unqualified_histories=unqualified_histories,
    )


@app.get("/requalified-items/download")
def download_requalified_items(
    sort_by: str = Query("data"),
    sort_dir: str = Query("desc"),
    search: Optional[str] = Query(None),
):
    supabase = _get_client()
    settings = get_settings()
    all_rows = _load_all_output_rows(supabase, settings)
    all_rows = _filter_requalified_rows(all_rows, search)
    all_rows = _sort_requalified_rows(all_rows, sort_by, sort_dir)
    output_bytes = _build_output_csv(all_rows)

    headers = {
        "Content-Disposition": "attachment; filename=requalified_items.csv"
    }
    return Response(content=output_bytes, media_type="text/csv", headers=headers)
