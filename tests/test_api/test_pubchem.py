# tests/test_api/test_pubchem.py
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from chaima.app import app
from chaima.db import get_async_session
from chaima.schemas.pubchem import PubChemGHSHit, PubChemLookupResult
from chaima.services.pubchem import PubChemNotFound, PubChemUpstreamError


_FAKE_RESULT = PubChemLookupResult(
    cid="180",
    name="propan-2-one",
    cas="67-64-1",
    molar_mass=58.08,
    smiles="CC(=O)C",
    synonyms=["Acetone", "67-64-1", "Dimethyl ketone"],
    ghs_codes=[
        PubChemGHSHit(
            code="H225",
            description="Highly flammable liquid and vapour",
            signal_word="Danger",
            pictogram="GHS02",
        )
    ],
)


@pytest_asyncio.fixture
async def anon_client(engine, session):
    """AsyncClient with no auth override — requests arrive unauthenticated."""
    async def _override_session():
        yield session

    app.dependency_overrides[get_async_session] = _override_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def test_lookup_endpoint_requires_auth(anon_client):
    resp = await anon_client.get("/api/v1/pubchem/lookup", params={"q": "acetone"})
    assert resp.status_code == 401


async def test_lookup_endpoint_success(client):
    with patch(
        "chaima.routers.pubchem.pubchem_service.lookup",
        new=AsyncMock(return_value=_FAKE_RESULT),
    ):
        resp = await client.get(
            "/api/v1/pubchem/lookup", params={"q": "acetone"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cid"] == "180"
    assert body["cas"] == "67-64-1"
    assert body["ghs_codes"][0]["code"] == "H225"


async def test_lookup_endpoint_not_found(client):
    with patch(
        "chaima.routers.pubchem.pubchem_service.lookup",
        new=AsyncMock(side_effect=PubChemNotFound("nope")),
    ):
        resp = await client.get(
            "/api/v1/pubchem/lookup", params={"q": "nope"}
        )
    assert resp.status_code == 404


async def test_lookup_endpoint_upstream_error(client):
    with patch(
        "chaima.routers.pubchem.pubchem_service.lookup",
        new=AsyncMock(side_effect=PubChemUpstreamError("boom")),
    ):
        resp = await client.get(
            "/api/v1/pubchem/lookup", params={"q": "acetone"}
        )
    assert resp.status_code == 502
