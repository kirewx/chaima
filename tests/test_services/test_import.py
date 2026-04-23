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


def test_apply_column_mapping_basic():
    grid = import_service.Grid(
        columns=["Name", "CAS", "Qty", "Unit", "Notes"],
        rows=[["Ethanol", "64-17-5", "1", "L", "ignore this"]],
        row_count=1,
        sheets=None,
    )
    mapping = {
        "Name": "name",
        "CAS": "cas",
        "Qty": "quantity",
        "Unit": "unit",
        "Notes": "ignore",
    }
    parsed = import_service.apply_column_mapping(grid, mapping, qu_combined_column=None)
    assert len(parsed) == 1
    row = parsed[0]
    assert row.index == 0
    assert row.name == "Ethanol"
    assert row.cas == "64-17-5"
    assert row.quantity == 1.0
    assert row.unit == "L"
    assert row.errors == []


def test_apply_column_mapping_combined_qu():
    grid = import_service.Grid(
        columns=["Name", "Menge"],
        rows=[["Acetone", "250 mL"], ["Bad", "junk"]],
        row_count=2,
        sheets=None,
    )
    mapping = {"Name": "name", "Menge": "quantity_unit_combined"}
    parsed = import_service.apply_column_mapping(grid, mapping, qu_combined_column="Menge")
    assert parsed[0].quantity == 250.0
    assert parsed[0].unit == "mL"
    assert parsed[0].errors == []
    assert parsed[1].quantity is None
    assert parsed[1].errors == []


def test_apply_column_mapping_missing_required_name():
    grid = import_service.Grid(
        columns=["CAS"],
        rows=[["64-17-5"]],
        row_count=1,
        sheets=None,
    )
    mapping = {"CAS": "cas"}
    with pytest.raises(import_service.MappingValidationError, match="name"):
        import_service.apply_column_mapping(grid, mapping, qu_combined_column=None)


def test_group_chemicals_by_cas():
    rows = [
        _parsed(0, name="Ethanol 99%", cas="64-17-5"),
        _parsed(1, name="ethanol", cas="64-17-5"),
        _parsed(2, name="Acetone", cas="67-64-1"),
    ]
    groups = import_service.group_chemicals_by_identity(rows)
    assert len(groups) == 2
    ethanol_group = next(g for g in groups if g.canonical_cas == "64-17-5")
    assert sorted(ethanol_group.row_indices) == [0, 1]


def test_group_chemicals_by_name_when_no_cas():
    rows = [
        _parsed(0, name="Water", cas=None),
        _parsed(1, name="  water ", cas=None),
        _parsed(2, name="WATER", cas=None),
    ]
    groups = import_service.group_chemicals_by_identity(rows)
    assert len(groups) == 1
    assert groups[0].row_indices == [0, 1, 2]


def _parsed(index, **kw):
    return import_service.ParsedRow(
        index=index,
        name=kw.get("name"),
        cas=kw.get("cas"),
        location_text=kw.get("location_text"),
        supplier_text=kw.get("supplier_text"),
        quantity=kw.get("quantity"),
        unit=kw.get("unit"),
        purity=kw.get("purity"),
        purchased_at=kw.get("purchased_at"),
        ordered_by=kw.get("ordered_by"),
        identifier=kw.get("identifier"),
        created_by_name=kw.get("created_by_name"),
        comment=kw.get("comment"),
        errors=[],
        warnings=[],
    )


async def test_commit_import_happy_path(session, group, user):
    payload = import_service.CommitPayload(
        column_mapping={
            "Name": "name", "CAS": "cas", "Location": "location_text",
            "Qty": "quantity", "Unit": "unit", "Id": "identifier",
        },
        quantity_unit_combined_column=None,
        rows=[
            ["Ethanol", "64-17-5", "Shelf A", "1", "L", "E-001"],
            ["Ethanol", "64-17-5", "Shelf A", "0.5", "L", "E-002"],
            ["Acetone", "67-64-1", "Shelf B", "250", "mL", "A-001"],
        ],
        columns=["Name", "CAS", "Location", "Qty", "Unit", "Id"],
        location_mapping=[
            import_service.LocationMapping(source_text="Shelf A", location_id=None,
                                           new_location={"name": "Shelf A", "parent_id": None}),
            import_service.LocationMapping(source_text="Shelf B", location_id=None,
                                           new_location={"name": "Shelf B", "parent_id": None}),
        ],
        chemical_groups=[
            import_service.ChemicalGroupPayload(
                canonical_name="Ethanol", canonical_cas="64-17-5", row_indices=[0, 1]
            ),
            import_service.ChemicalGroupPayload(
                canonical_name="Acetone", canonical_cas="67-64-1", row_indices=[2]
            ),
        ],
    )

    summary = await import_service.commit_import(
        session, group_id=group.id, viewer_id=user.id, payload=payload,
    )
    await session.commit()

    assert summary.created_chemicals == 2
    assert summary.created_containers == 3
    assert summary.created_locations == 2
    assert summary.skipped_rows == []

    from sqlmodel import select
    from chaima.models.chemical import Chemical
    chems = (await session.exec(select(Chemical).where(Chemical.group_id == group.id))).all()
    assert {c.name for c in chems} == {"Ethanol", "Acetone"}


async def test_commit_import_skips_blank_rows(session, group, user):
    payload = import_service.CommitPayload(
        column_mapping={"Name": "name", "Qty": "quantity", "Unit": "unit"},
        quantity_unit_combined_column=None,
        rows=[
            ["Ethanol", "1", "L"],
            ["", "1", "L"],
        ],
        columns=["Name", "Qty", "Unit"],
        location_mapping=[],
        chemical_groups=[
            import_service.ChemicalGroupPayload(canonical_name="Ethanol", canonical_cas=None, row_indices=[0]),
            import_service.ChemicalGroupPayload(canonical_name="", canonical_cas=None, row_indices=[1]),
        ],
    )
    summary = await import_service.commit_import(
        session, group_id=group.id, viewer_id=user.id, payload=payload,
    )
    await session.commit()
    assert summary.created_chemicals == 1
    assert summary.created_containers == 1


async def test_commit_import_uses_existing_location(session, group, user):
    from chaima.models.storage import StorageKind, StorageLocation
    existing = StorageLocation(name="Existing Shelf", kind=StorageKind.SHELF)
    session.add(existing)
    await session.flush()

    payload = import_service.CommitPayload(
        column_mapping={"Name": "name", "Loc": "location_text", "Q": "quantity", "U": "unit"},
        quantity_unit_combined_column=None,
        rows=[["Ethanol", "Existing", "1", "L"]],
        columns=["Name", "Loc", "Q", "U"],
        location_mapping=[
            import_service.LocationMapping(source_text="Existing", location_id=existing.id, new_location=None),
        ],
        chemical_groups=[
            import_service.ChemicalGroupPayload(canonical_name="Ethanol", canonical_cas=None, row_indices=[0]),
        ],
    )
    summary = await import_service.commit_import(
        session, group_id=group.id, viewer_id=user.id, payload=payload,
    )
    await session.commit()
    assert summary.created_locations == 0
    assert summary.created_containers == 1
