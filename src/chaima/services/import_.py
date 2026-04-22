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


@dataclass
class ParsedRow:
    index: int
    name: str | None
    cas: str | None
    location_text: str | None
    quantity: float | None
    unit: str | None
    purity: str | None
    purchased_at: str | None
    ordered_by: str | None
    identifier: str | None
    created_by_name: str | None
    comment: str | None
    errors: list[str]


class MappingValidationError(ValueError):
    pass


_REQUIRED_TARGETS = {"name"}


def apply_column_mapping(
    grid: Grid,
    mapping: dict[str, str],
    qu_combined_column: str | None,
) -> list[ParsedRow]:
    targets_in_use = set(mapping.values())
    missing = _REQUIRED_TARGETS - targets_in_use
    if missing:
        raise MappingValidationError(f"Missing required columns: {sorted(missing)}")
    has_qty = "quantity" in targets_in_use
    has_qu = qu_combined_column is not None
    if not (has_qty or has_qu):
        raise MappingValidationError(
            "Need either a 'quantity' column or a 'quantity_unit_combined' column"
        )

    col_index = {col: i for i, col in enumerate(grid.columns)}
    parsed: list[ParsedRow] = []
    for i, row in enumerate(grid.rows):
        errors: list[str] = []
        values: dict[str, str | None] = {t: None for t in [
            "name", "cas", "location_text", "quantity", "unit", "purity",
            "purchased_at", "ordered_by", "identifier", "created_by_name", "comment",
        ]}
        qty: float | None = None
        unit: str | None = None
        for source_col, target in mapping.items():
            if target == "ignore":
                continue
            cell = row[col_index[source_col]] if col_index[source_col] < len(row) else ""
            cell = cell.strip() if cell else ""
            if target == "quantity_unit_combined":
                q, u = split_quantity_unit(cell)
                if cell and q is None:
                    errors.append(f"Unparseable quantity+unit cell: {cell!r}")
                qty = q if q is not None else qty
                unit = u if u is not None else unit
            elif target == "quantity":
                if cell:
                    try:
                        qty = float(cell.replace(",", "."))
                    except ValueError:
                        errors.append(f"Unparseable quantity: {cell!r}")
            elif target == "unit":
                unit = cell or None
            else:
                values[target] = cell or None

        if not values.get("name"):
            errors.append("Missing chemical name")

        parsed.append(ParsedRow(
            index=i,
            name=values["name"],
            cas=values["cas"],
            location_text=values["location_text"],
            quantity=qty,
            unit=unit,
            purity=values["purity"],
            purchased_at=values["purchased_at"],
            ordered_by=values["ordered_by"],
            identifier=values["identifier"],
            created_by_name=values["created_by_name"],
            comment=values["comment"],
            errors=errors,
        ))
    return parsed


@dataclass
class ChemicalGroup:
    canonical_name: str
    canonical_cas: str | None
    row_indices: list[int]


def _normalize_name(s: str | None) -> str:
    return (s or "").strip().lower()


def group_chemicals_by_identity(rows: list[ParsedRow]) -> list[ChemicalGroup]:
    buckets: dict[str, list[ParsedRow]] = {}
    for r in rows:
        if r.cas:
            key = f"cas:{r.cas}"
        else:
            key = f"name:{_normalize_name(r.name)}"
        buckets.setdefault(key, []).append(r)

    groups: list[ChemicalGroup] = []
    for key, rs in buckets.items():
        canonical = next((r.name for r in rs if r.name), rs[0].name or "")
        canonical_cas = next((r.cas for r in rs if r.cas), None)
        groups.append(ChemicalGroup(
            canonical_name=canonical,
            canonical_cas=canonical_cas,
            row_indices=[r.index for r in rs],
        ))
    return groups
