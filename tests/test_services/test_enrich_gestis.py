import time
from unittest.mock import AsyncMock, patch

import pytest

from chaima.models.chemical import Chemical
from chaima.schemas.pubchem import PubChemLookupResult
from chaima.services import enrich as enrich_service
from chaima.services import gestis as gestis_service


@pytest.fixture(autouse=True)
def _reset_gestis_index():
    gestis_service._index = None
    gestis_service._expiry = 0.0
    yield
    gestis_service._index = None
    gestis_service._expiry = 0.0


def _lookup_result() -> PubChemLookupResult:
    return PubChemLookupResult(
        cid="702", name="Ethanol", cas="64-17-5", molar_mass=46.07,
        smiles="CCO", synonyms=[], ghs_codes=[],
    )


async def test_enrich_one_sets_zvg_when_index_warm(session, group, user):
    gestis_service._index = {"64-17-5": "010420"}
    gestis_service._expiry = time.time() + 3600

    chem = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    with patch(
        "chaima.services.enrich.pubchem_lookup",
        AsyncMock(return_value=_lookup_result()),
    ):
        status = await enrich_service.enrich_one(session, chem)
    assert status == "enriched"
    assert chem.cas == "64-17-5"
    assert chem.zvg == "010420"


async def test_enrich_one_cold_index_leaves_zvg_null(session, group, user):
    chem = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    with patch(
        "chaima.services.enrich.pubchem_lookup",
        AsyncMock(return_value=_lookup_result()),
    ):
        status = await enrich_service.enrich_one(session, chem)
    assert status == "enriched"
    assert chem.zvg is None


async def test_enrich_one_keeps_existing_zvg(session, group, user):
    gestis_service._index = {"64-17-5": "999999"}
    gestis_service._expiry = time.time() + 3600

    chem = Chemical(
        name="Ethanol", cas="64-17-5", zvg="010420",
        group_id=group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    with patch(
        "chaima.services.enrich.pubchem_lookup",
        AsyncMock(return_value=_lookup_result()),
    ):
        await enrich_service.enrich_one(session, chem)
    assert chem.zvg == "010420"
