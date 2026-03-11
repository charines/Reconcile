import csv
import io
import unicodedata
from datetime import datetime
from typing import Dict, List, Tuple


EXPECTED_HEADERS = ["data", "valor", "historico"]
HEADER_ALIASES = {
    "data": {
        "data",
        "data lancamento",
        "data lançamento",
        "data de lancamento",
        "data de lançamento",
        "dt",
        "date",
    },
    "valor": {
        "valor",
        "valor r$",
        "valor (r$)",
        "valor (rs)",
        "amount",
    },
    "credito": {
        "credito",
        "crédito",
        "credito (r$)",
        "crédito (r$)",
        "créditos",
        "creditos",
    },
    "debito": {
        "debito",
        "débito",
        "debito (r$)",
        "débito (r$)",
        "débitos",
        "debitos",
    },
    "historico": {
        "historico",
        "histórico",
        "descricao",
        "descrição",
        "descricao do lancamento",
        "descricao do lançamento",
        "descricao historico",
        "descricao histórico",
        "historico descricao",
        "hist",
        "detalhe",
        "details",
        "lancamento",
        "lançamento",
    },
}


def detect_delimiter(sample: str) -> str:
    comma = sample.count(",")
    semicolon = sample.count(";")
    if semicolon > comma:
        return ";"
    return ","


def normalize_header(name: str) -> str:
    raw = name.strip().lower().replace("\ufeff", "")
    normalized = unicodedata.normalize("NFD", raw)
    without_accents = "".join(
        ch for ch in normalized if unicodedata.category(ch) != "Mn"
    )
    return " ".join(without_accents.split())


NORMALIZED_ALIASES = {
    canonical: {normalize_header(alias) for alias in aliases}
    for canonical, aliases in HEADER_ALIASES.items()
}


def parse_date(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def parse_value(value: str) -> str:
    raw = value.strip().replace(" ", "")
    if not raw:
        return ""

    if "," in raw and "." in raw:
        last_comma = raw.rfind(",")
        last_dot = raw.rfind(".")
        if last_comma > last_dot:
            raw = raw.replace(".", "")
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(".", "")
        raw = raw.replace(",", ".")

    return raw


def _resolve_header(field: str) -> str | None:
    normalized = normalize_header(field)
    for canonical, aliases in NORMALIZED_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def _find_header_start(lines: List[str]) -> Tuple[int, str]:
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        delimiter = detect_delimiter(line)
        if line.count(delimiter) == 0:
            continue
        fields = [normalize_header(part) for part in line.split(delimiter)]
        hits = set()
        for field in fields:
            resolved = _resolve_header(field)
            if resolved:
                hits.add(resolved)

        has_data = "data" in hits
        has_historico = "historico" in hits
        has_valor = "valor" in hits or ("credito" in hits and "debito" in hits)
        if has_data and has_historico and has_valor:
            return idx, delimiter
    # fallback: use first line delimiter if no header was found
    first_line = lines[0] if lines else ""
    return 0, detect_delimiter(first_line)


def read_csv(content: bytes) -> Tuple[List[Dict[str, str]], List[str]]:
    # Tenta diferentes encodings
    text = ""
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("utf-8", errors="replace")

    lines = text.splitlines()
    header_idx, delimiter = _find_header_start(lines)
    csv_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV sem cabecalho")

    header_map = {}
    for field in reader.fieldnames:
        resolved = _resolve_header(field)
        if resolved and resolved not in header_map:
            header_map[resolved] = field

    has_data = "data" in header_map
    has_historico = "historico" in header_map
    has_valor = "valor" in header_map or ("credito" in header_map and "debito" in header_map)

    if not has_data or not has_historico or not has_valor:
        missing = []
        if not has_data: missing.append("data")
        if not has_historico: missing.append("historico")
        if not has_valor: missing.append("valor / (credito e debito)")
        raise ValueError(f"CSV sem colunas obrigatorias: {', '.join(missing)}")

    rows = []
    for row in reader:
        data_raw = row.get(header_map.get("data", ""), "")
        historico_raw = row.get(header_map.get("historico", ""), "")
        
        # Processamento do valor
        if "valor" in header_map:
            valor_raw = row.get(header_map["valor"], "")
        else:
            credito = row.get(header_map.get("credito", ""), "")
            debito = row.get(header_map.get("debito", ""), "")
            if credito and credito.strip():
                valor_raw = credito
            elif debito and debito.strip():
                valor_raw = debito
            else:
                valor_raw = "0"

        data_iso = parse_date(str(data_raw))
        # Pula linhas que não tem uma data válida (ex: "Total")
        if data_iso == data_raw and not (len(data_iso) == 10 and data_iso[4] == '-' and data_iso[7] == '-'):
            continue
            
        if not str(historico_raw).strip():
            continue

        rows.append(
            {
                "data": data_iso,
                "valor": parse_value(str(valor_raw)),
                "historico": str(historico_raw).strip(),
            }
        )

    return rows, list(reader.fieldnames or [])
