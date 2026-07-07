"""API tests for the compatibility endpoints."""
from __future__ import annotations

import pytest

from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.ghs import ChemicalGHS, GHSCode
from chaima.models.storage import StorageKind, StorageLocation, StorageLocationGroup

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


# --------------------------------------------------------------------------
# Secret chemicals must still surface as (anonymized) safety conflicts
# --------------------------------------------------------------------------


async def _setup_secret_vs_flammable(session, group, owner, other):
    """A hidden secret oxidizer and a visible flammable stored together.

    Returns (location, secret_chemical, visible_chemical). The secret belongs
    to ``owner``; the flammable was created by ``other`` and is not secret.
    """
    loc = StorageLocation(name="Cabinet 7", kind=StorageKind.SHELF)
    session.add(loc)
    await session.flush()
    session.add(StorageLocationGroup(location_id=loc.id, group_id=group.id))

    ghs02 = GHSCode(code="GHS02", description="Flammable")
    ghs03 = GHSCode(code="GHS03", description="Oxidizing")
    secret = Chemical(
        group_id=group.id, name="Secret Oxidizer", created_by=owner.id,
        is_secret=True,
    )
    visible = Chemical(group_id=group.id, name="Ethanol", created_by=other.id)
    session.add_all([ghs02, ghs03, secret, visible])
    await session.flush()

    session.add_all([
        ChemicalGHS(chemical_id=secret.id, ghs_id=ghs03.id),
        ChemicalGHS(chemical_id=visible.id, ghs_id=ghs02.id),
        Container(
            chemical_id=secret.id, location_id=loc.id, identifier="S-1",
            amount=1.0, unit="L", created_by=owner.id,
        ),
        Container(
            chemical_id=visible.id, location_id=loc.id, identifier="E-1",
            amount=1.0, unit="L", created_by=other.id,
        ),
    ])
    await session.flush()
    return loc, secret, visible


async def test_location_conflicts_surface_hidden_secret_anonymized(
    other_client, session, user, other_user, other_membership, group
):
    """A secret the viewer may not see must still warn — without its name."""
    loc, secret, _ = await _setup_secret_vs_flammable(session, group, user, other_user)

    r = await other_client.get(
        f"/api/v1/groups/{group.id}/locations/{loc.id}/conflicts"
    )
    assert r.status_code == 200, r.text
    conflicts = r.json()
    assert len(conflicts) == 1, conflicts
    names = {conflicts[0]["chem_a_name"], conflicts[0]["chem_b_name"]}
    assert "Ethanol" in names
    assert "Hidden chemical" in names
    # The secret's identity must not leak anywhere in the payload.
    assert "Secret Oxidizer" not in r.text
    assert str(secret.id) not in r.text


async def test_location_conflicts_show_secret_name_to_owner(
    client, session, user, other_user, membership, group
):
    """The secret's owner keeps seeing the real name in conflicts."""
    loc, _, _ = await _setup_secret_vs_flammable(session, group, user, other_user)

    r = await client.get(
        f"/api/v1/groups/{group.id}/locations/{loc.id}/conflicts"
    )
    assert r.status_code == 200, r.text
    conflicts = r.json()
    assert len(conflicts) == 1, conflicts
    names = {conflicts[0]["chem_a_name"], conflicts[0]["chem_b_name"]}
    assert names == {"Ethanol", "Secret Oxidizer"}


async def test_compatibility_check_surfaces_hidden_secret_anonymized(
    other_client, session, user, other_user, other_membership, group
):
    """Placement check against a location holding a hidden secret must warn."""
    loc, secret, visible = await _setup_secret_vs_flammable(
        session, group, user, other_user
    )

    r = await other_client.get(
        f"/api/v1/groups/{group.id}/compatibility/check",
        params={"chemical_id": str(visible.id), "location_id": str(loc.id)},
    )
    assert r.status_code == 200, r.text
    conflicts = r.json()
    assert len(conflicts) == 1, conflicts
    names = {conflicts[0]["chem_a_name"], conflicts[0]["chem_b_name"]}
    assert "Ethanol" in names
    assert "Hidden chemical" in names
    assert "Secret Oxidizer" not in r.text
    assert str(secret.id) not in r.text
