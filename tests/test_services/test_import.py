from pathlib import Path

import pytest

from chaima.services import import_ as import_service

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.parametrize("input_str,expected", [
    ("250 mL", (250.0, "mL")),
    ("1,5 L", (1.5, "L")),
    ("1.5 L", (1.5, "L")),
    ("5", (5.0, None)),
    ("0.1 µmol", (0.1, "µmol")),
    ("100g", (100.0, "g")),
    ("", (None, None)),
    ("some text", (None, None)),
    ("abc 5 def", (None, None)),
])
def test_split_quantity_unit(input_str, expected):
    assert import_service.split_quantity_unit(input_str) == expected


def test_detect_header_mapping_english():
    cols = ["Name", "CAS", "Location", "Quantity", "Unit", "Purity"]
    m = import_service.detect_header_mapping(cols)
    assert m == {
        "Name": "name",
        "CAS": "cas",
        "Location": "location_text",
        "Quantity": "quantity",
        "Unit": "unit",
        "Purity": "purity",
    }


def test_detect_header_mapping_german():
    cols = ["Name", "CAS-Nr.", "Standort", "Menge", "Einheit", "Lieferant", "Bestellt von"]
    m = import_service.detect_header_mapping(cols)
    assert m["Name"] == "name"
    assert m["CAS-Nr."] == "cas"
    assert m["Standort"] == "location_text"
    assert m["Menge"] == "quantity"
    assert m["Einheit"] == "unit"
    assert m["Bestellt von"] == "ordered_by"


def test_detect_header_mapping_unknown_column():
    cols = ["Flibbertigibbet"]
    assert import_service.detect_header_mapping(cols) == {"Flibbertigibbet": "ignore"}


def test_detect_header_mapping_combined_qu():
    cols = ["Name", "Menge (mit Einheit)"]
    m = import_service.detect_header_mapping(cols)
    assert m["Menge (mit Einheit)"] == "quantity_unit_combined"


def test_parse_xlsx():
    with (FIXTURE_DIR / "import_sample.xlsx").open("rb") as f:
        grid = import_service.parse_upload(f.read(), "xlsx")
    assert grid.columns[:3] == ["Name", "CAS-Nr.", "Standort"]
    assert grid.row_count == 4
    assert grid.rows[0][0] == "Ethanol"
    assert grid.sheets == ["Inventory"]


def test_parse_csv():
    with (FIXTURE_DIR / "import_sample.csv").open("rb") as f:
        grid = import_service.parse_upload(f.read(), "csv")
    assert grid.columns == ["Name", "CAS", "Location", "Quantity", "Unit"]
    assert grid.row_count == 2
    assert grid.rows[0][0] == "Ethanol"
    assert grid.sheets is None


def test_parse_xlsx_pick_sheet():
    with (FIXTURE_DIR / "import_sample.xlsx").open("rb") as f:
        grid = import_service.parse_upload(f.read(), "xlsx", sheet_name="Inventory")
    assert grid.row_count == 4


def test_parse_xlsx_missing_sheet_raises():
    with (FIXTURE_DIR / "import_sample.xlsx").open("rb") as f:
        with pytest.raises(ValueError, match="Sheet 'NoSuchSheet' not found"):
            import_service.parse_upload(f.read(), "xlsx", sheet_name="NoSuchSheet")
