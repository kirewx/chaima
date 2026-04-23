from pathlib import Path

FIXTURE = Path(__file__).parent.parent / "fixtures" / "import_sample.xlsx"


async def test_preview_xlsx(client, group, admin_membership):
    with FIXTURE.open("rb") as f:
        resp = await client.post(
            f"/api/v1/groups/{group.id}/import/preview",
            files={"file": ("import_sample.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["columns"][:3] == ["Name", "CAS-Nr.", "Standort"]
    assert body["row_count"] == 4
    assert body["detected_mapping"]["Name"] == "name"
    assert body["detected_mapping"]["CAS-Nr."] == "cas"


async def test_preview_requires_admin(client, group, membership):
    with FIXTURE.open("rb") as f:
        resp = await client.post(
            f"/api/v1/groups/{group.id}/import/preview",
            files={"file": ("s.xlsx", f, "application/octet-stream")},
        )
    assert resp.status_code == 403


async def test_commit_happy_path(client, session, group, user, admin_membership):
    body = {
        "column_mapping": {"Name": "name", "Loc": "location_text", "Q": "quantity", "U": "unit"},
        "quantity_unit_combined_column": None,
        "columns": ["Name", "Loc", "Q", "U"],
        "rows": [["Ethanol", "Shelf A", "1", "L"]],
        "location_mapping": [
            {"source_text": "Shelf A", "location_id": None,
             "new_location": {"name": "Shelf A", "parent_id": None}},
        ],
        "chemical_groups": [
            {"canonical_name": "Ethanol", "canonical_cas": None, "row_indices": [0]},
        ],
    }
    resp = await client.post(
        f"/api/v1/groups/{group.id}/import/commit", json=body,
    )
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    assert summary["created_chemicals"] == 1
    assert summary["created_containers"] == 1
    assert summary["created_locations"] == 1


async def test_commit_blank_rows_skipped(client, group, admin_membership):
    body = {
        "column_mapping": {"Name": "name", "Q": "quantity", "U": "unit"},
        "quantity_unit_combined_column": None,
        "columns": ["Name", "Q", "U"],
        "rows": [["Ethanol", "1", "L"], ["", "1", "L"]],
        "location_mapping": [],
        "chemical_groups": [
            {"canonical_name": "Ethanol", "canonical_cas": None, "row_indices": [0]},
            {"canonical_name": "", "canonical_cas": None, "row_indices": [1]},
        ],
    }
    resp = await client.post(
        f"/api/v1/groups/{group.id}/import/commit", json=body,
    )
    assert resp.status_code == 200
    assert resp.json()["created_chemicals"] == 1
