import csv as csv_module
import re
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Literal

_QU_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([a-zA-ZµμÅ%°]+)?\s*$")


def split_quantity_unit(s: str) -> tuple[float | None, str | None]:
    if not s:
        return (None, None)
    m = _QU_RE.match(s)
    if m is None:
        return (None, None)
    qty_str = m.group(1).replace(",", ".")
    try:
        qty = float(qty_str)
    except ValueError:
        return (None, None)
    unit = m.group(2)
    return (qty, unit)


_HEADER_PATTERNS: list[tuple[str, str]] = [
    ("cas", "cas"),
    ("mit einheit", "quantity_unit_combined"),
    ("with unit", "quantity_unit_combined"),
    ("menge", "quantity"),
    ("quantity", "quantity"),
    ("amount", "quantity"),
    ("einheit", "unit"),
    ("unit", "unit"),
    ("standort", "location_text"),
    ("location", "location_text"),
    ("lagerort", "location_text"),
    ("reinheit", "purity"),
    ("purity", "purity"),
    ("bestellt von", "ordered_by"),
    ("ordered by", "ordered_by"),
    ("besteller", "ordered_by"),
    ("erstellt von", "created_by_name"),
    ("created by", "created_by_name"),
    ("label", "identifier"),
    ("behälter", "identifier"),
    ("identifier", "identifier"),
    ("bemerkung", "comment"),
    ("kommentar", "comment"),
    ("comment", "comment"),
    ("notes", "comment"),
    ("kaufdatum", "purchased_at"),
    ("gekauft", "purchased_at"),
    ("purchased", "purchased_at"),
    ("bought", "purchased_at"),
    ("name", "name"),
]


def detect_header_mapping(columns: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for col in columns:
        lower = col.strip().lower()
        chosen: str | None = None
        for pattern, target in _HEADER_PATTERNS:
            if pattern in lower:
                chosen = target
                break
        result[col] = chosen or "ignore"
    return result


@dataclass
class Grid:
    columns: list[str]
    rows: list[list[str]]
    row_count: int
    sheets: list[str] | None


def parse_upload(
    data: bytes, fmt: Literal["xlsx", "csv"], sheet_name: str | None = None
) -> Grid:
    if fmt == "xlsx":
        return _parse_xlsx(data, sheet_name)
    if fmt == "csv":
        return _parse_csv(data)
    raise ValueError(f"Unsupported format: {fmt}")


def _parse_xlsx(data: bytes, sheet_name: str | None) -> Grid:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    sheet_names = wb.sheetnames
    if sheet_name is None:
        ws = wb.active
    else:
        if sheet_name not in sheet_names:
            raise ValueError(f"Sheet '{sheet_name}' not found. Available: {sheet_names}")
        ws = wb[sheet_name]

    all_rows = [
        [("" if cell is None else str(cell)) for cell in row]
        for row in ws.iter_rows(values_only=True)
    ]
    if not all_rows:
        return Grid(columns=[], rows=[], row_count=0, sheets=sheet_names)

    columns = [str(c).strip() for c in all_rows[0]]
    rows = all_rows[1:]
    while rows and all(cell == "" for cell in rows[-1]):
        rows.pop()
    return Grid(columns=columns, rows=rows, row_count=len(rows), sheets=sheet_names)


def _parse_csv(data: bytes) -> Grid:
    text = data.decode("utf-8-sig")
    reader = csv_module.reader(StringIO(text))
    all_rows = list(reader)
    if not all_rows:
        return Grid(columns=[], rows=[], row_count=0, sheets=None)
    columns = [c.strip() for c in all_rows[0]]
    rows = all_rows[1:]
    while rows and all(cell == "" for cell in rows[-1]):
        rows.pop()
    return Grid(columns=columns, rows=rows, row_count=len(rows), sheets=None)
