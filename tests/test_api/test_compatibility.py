"""API tests for the compatibility endpoints."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_location_conflicts_empty(client, group, membership):
    """An empty cabinet has no conflicts."""
    resp = await client.post(
        f"/api/v1/groups/{group.id}/storage-locations",
        json={"name": "Building 1", "kind": "building"},
    )
    assert resp.status_code in (200, 201)
    loc_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/groups/{group.id}/locations/{loc_id}/conflicts",
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_compatibility_check_returns_list(client, group, membership):
    """Placement check returns a (possibly empty) list for any valid pair."""
    chem_resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "Test Chemical"},
    )
    assert chem_resp.status_code in (200, 201)
    chemical_id = chem_resp.json()["id"]

    loc_resp = await client.post(
        f"/api/v1/groups/{group.id}/storage-locations",
        json={"name": "Building A", "kind": "building"},
    )
    assert loc_resp.status_code in (200, 201)
    location_id = loc_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/groups/{group.id}/compatibility/check",
        params={"chemical_id": chemical_id, "location_id": location_id},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
