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
        "valor (r$)",
        "valor (rs)",
        "valor r$",
        "amount",
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
        if hits.issuperset(EXPECTED_HEADERS):
            return idx, delimiter
    # fallback: use first line delimiter if no header was found
    first_line = lines[0] if lines else ""
    return 0, detect_delimiter(first_line)


def read_csv(content: bytes) -> Tuple[List[Dict[str, str]], List[str]]:
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

    missing = [h for h in EXPECTED_HEADERS if h not in header_map]
    if missing:
        raise ValueError(f"CSV sem colunas obrigatorias: {', '.join(missing)}")

    rows = []
    for row in reader:
        data_raw = row.get(header_map["data"], "")
        valor_raw = row.get(header_map["valor"], "")
        historico_raw = row.get(header_map["historico"], "")

        rows.append(
            {
                "data": parse_date(str(data_raw)),
                "valor": parse_value(str(valor_raw)),
                "historico": str(historico_raw).strip(),
            }
        )

    return rows, reader.fieldnames
