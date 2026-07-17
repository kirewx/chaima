import time

import pytest

from chaima.services import chemicals as chemical_service
from chaima.services import gestis as gestis_service


@pytest.fixture(autouse=True)
def _reset_gestis_index():
    gestis_service._index = None
    gestis_service._expiry = 0.0
    yield
    gestis_service._index = None
    gestis_service._expiry = 0.0


def _warm_index(mapping: dict[str, str]) -> None:
    gestis_service._index = mapping
    gestis_service._expiry = time.time() + 3600


async def test_create_with_cas_warm_index_sets_zvg(session, group, user):
    _warm_index({"64-17-5": "010420"})
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id,
        name="Ethanol", cas="64-17-5",
    )
    assert chem.zvg == "010420"


async def test_create_with_cas_cold_index_still_succeeds(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id,
        name="Ethanol", cas="64-17-5",
    )
    assert chem.zvg is None


async def test_create_without_cas_leaves_zvg_null(session, group, user):
    _warm_index({"64-17-5": "010420"})
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Mystery",
    )
    assert chem.zvg is None


async def test_update_changing_cas_reresolves(session, group, user):
    _warm_index({"67-64-1": "011230"})
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id,
        name="Stoff", cas="64-17-5",
    )
    chem.zvg = "010420"  # simulate previously stored value
    session.add(chem)
    await session.flush()

    updated = await chemical_service.update_chemical(session, chem, cas="67-64-1")
    assert updated.zvg == "011230"


async def test_update_changing_cas_to_unknown_clears_zvg(session, group, user):
    _warm_index({})
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id,
        name="Stoff", cas="64-17-5",
    )
    chem.zvg = "010420"
    session.add(chem)
    await session.flush()

    updated = await chemical_service.update_chemical(session, chem, cas="67-64-1")
    assert updated.zvg is None


async def test_update_removing_cas_clears_zvg(session, group, user):
    _warm_index({"64-17-5": "010420"})
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id,
        name="Stoff", cas="64-17-5",
    )
    updated = await chemical_service.update_chemical(session, chem, cas=None)
    assert updated.cas is None
    assert updated.zvg is None


async def test_update_adding_cas_resolves(session, group, user):
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id, name="Stoff",
    )
    _warm_index({"64-17-5": "010420"})
    updated = await chemical_service.update_chemical(session, chem, cas="64-17-5")
    assert updated.zvg == "010420"


async def test_update_unrelated_field_keeps_zvg(session, group, user):
    _warm_index({"64-17-5": "010420"})
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id,
        name="Stoff", cas="64-17-5",
    )
    assert chem.zvg == "010420"
    gestis_service._index = {}  # even a now-empty index must not clear it
    updated = await chemical_service.update_chemical(
        session, chem, comment="updated"
    )
    assert updated.zvg == "010420"


async def test_update_same_cas_keeps_zvg(session, group, user):
    _warm_index({"64-17-5": "010420"})
    chem = await chemical_service.create_chemical(
        session, group_id=group.id, created_by=user.id,
        name="Stoff", cas="64-17-5",
    )
    gestis_service._index = {}
    updated = await chemical_service.update_chemical(session, chem, cas="64-17-5")
    assert updated.zvg == "010420"
