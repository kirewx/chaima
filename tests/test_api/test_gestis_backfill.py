import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from chaima.models.chemical import Chemical
from chaima.services import gestis as gestis_service


@pytest.fixture(autouse=True)
def _reset_gestis_index():
    gestis_service._index = None
    gestis_service._expiry = 0.0
    yield
    gestis_service._index = None
    gestis_service._expiry = 0.0


def _events(resp) -> list[dict]:
    return [
        json.loads(line[len("data: "):])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]


async def test_backfill_requires_superuser(client, group, admin_membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/backfill-gestis",
        json={"chemical_ids": None},
    )
    assert resp.status_code == 403


async def test_backfill_streams_events_and_summary(
    superuser_client, session, group, superuser
):
    gestis_service._index = {"64-17-5": "010420"}
    gestis_service._expiry = time.time() + 3600

    resolvable = Chemical(
        name="Ethanol", cas="64-17-5", group_id=group.id, created_by=superuser.id
    )
    unknown_cas = Chemical(
        name="Cocaine", cas="50-36-2", group_id=group.id, created_by=superuser.id
    )
    no_cas = Chemical(name="Mystery", group_id=group.id, created_by=superuser.id)
    session.add_all([resolvable, unknown_cas, no_cas])
    await session.commit()

    resp = await superuser_client.post(
        f"/api/v1/groups/{group.id}/chemicals/backfill-gestis",
        json={"chemical_ids": [
            str(resolvable.id), str(unknown_cas.id), str(no_cas.id),
        ]},
    )
    assert resp.status_code == 200
    events = _events(resp)
    by_name = {e["name"]: e["status"] for e in events if "status" in e}
    assert by_name == {
        "Ethanol": "resolved",
        "Cocaine": "not_found",
        "Mystery": "skipped",
    }
    summary = next(e for e in events if "summary" in e)["summary"]
    assert summary == {"resolved": 1, "skipped": 1, "not_found": 1, "error": 0}

    await session.refresh(resolvable)
    assert resolvable.zvg == "010420"


async def test_backfill_default_selection_skips_resolved_and_casless(
    superuser_client, session, group, superuser
):
    gestis_service._index = {"64-17-5": "010420", "67-64-1": "011230"}
    gestis_service._expiry = time.time() + 3600

    candidate = Chemical(
        name="Ethanol", cas="64-17-5", group_id=group.id, created_by=superuser.id
    )
    already_done = Chemical(
        name="Acetone", cas="67-64-1", zvg="011230",
        group_id=group.id, created_by=superuser.id,
    )
    no_cas = Chemical(name="Mystery", group_id=group.id, created_by=superuser.id)
    session.add_all([candidate, already_done, no_cas])
    await session.commit()

    resp = await superuser_client.post(
        f"/api/v1/groups/{group.id}/chemicals/backfill-gestis",
        json={"chemical_ids": None},
    )
    events = _events(resp)
    names = [e["name"] for e in events if "status" in e]
    assert names == ["Ethanol"]  # only cas IS NOT NULL AND zvg IS NULL
    summary = next(e for e in events if "summary" in e)["summary"]
    assert summary["resolved"] == 1


async def test_backfill_index_unavailable_yields_error_status(
    superuser_client, session, group, superuser
):
    chem = Chemical(
        name="Ethanol", cas="64-17-5", group_id=group.id, created_by=superuser.id
    )
    session.add(chem)
    await session.commit()

    with patch(
        "chaima.services.gestis.load_index", AsyncMock(return_value=False)
    ):
        resp = await superuser_client.post(
            f"/api/v1/groups/{group.id}/chemicals/backfill-gestis",
            json={"chemical_ids": None},
        )
    assert resp.status_code == 200
    events = _events(resp)
    statuses = [e["status"] for e in events if "status" in e]
    assert statuses == ["error"]
    await session.refresh(chem)
    assert chem.zvg is None
