import re

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
