import csv
import io
from datetime import datetime
from typing import Dict, List, Tuple


EXPECTED_HEADERS = ["data", "valor", "historico"]


def detect_delimiter(sample: str) -> str:
    comma = sample.count(",")
    semicolon = sample.count(";")
    if semicolon > comma:
        return ";"
    return ","


def normalize_header(name: str) -> str:
    return name.strip().lower()


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


def read_csv(content: bytes) -> Tuple[List[Dict[str, str]], List[str]]:
    text = content.decode("utf-8", errors="replace")
    sample_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = detect_delimiter(sample_line)

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV sem cabecalho")

    header_map = {normalize_header(h): h for h in reader.fieldnames}
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
