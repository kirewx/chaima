# tests/test_services/test_pubchem.py
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from chaima.services import pubchem as pubchem_service
from chaima.services.pubchem import (
    PubChemNotFound,
    PubChemUpstreamError,
    parse_ghs_classification,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _mock_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=data,
        request=httpx.Request("GET", "https://pubchem.ncbi.nlm.nih.gov/"),
    )


def _build_client_mock(responses: list[httpx.Response]) -> AsyncMock:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(side_effect=responses)
    return client


@pytest.fixture(autouse=True)
def _clear_pubchem_cache():
    """Clear the in-memory PubChem cache between tests."""
    pubchem_service._cache.clear()
    yield
    pubchem_service._cache.clear()


async def test_lookup_by_name_happy_path():
    responses = [
        _mock_response(_load("pubchem_acetone_cid.json")),
        _mock_response(_load("pubchem_acetone_properties.json")),
        _mock_response(_load("pubchem_acetone_synonyms.json")),
    ]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        result = await pubchem_service.lookup("acetone")

    assert result.cid == "180"
    assert result.name == "Acetone"
    assert result.cas == "67-64-1"
    assert result.molar_mass == pytest.approx(58.08)
    assert result.smiles == "CC(=O)C"
    assert "acetone" in result.synonyms
    assert len(result.synonyms) <= 20
    # GHS codes are fetched separately now
    assert result.ghs_codes == []


async def test_lookup_by_cas_happy_path():
    responses = [
        _mock_response(_load("pubchem_acetone_cid.json")),
        _mock_response(_load("pubchem_acetone_properties.json")),
        _mock_response(_load("pubchem_acetone_synonyms.json")),
    ]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        result = await pubchem_service.lookup("67-64-1")

    assert result.cid == "180"
    assert result.cas == "67-64-1"


async def test_lookup_not_found():
    responses = [_mock_response({}, status=404)]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        with pytest.raises(PubChemNotFound):
            await pubchem_service.lookup("nonexistent-compound-xyz")


async def test_lookup_upstream_error_500():
    responses = [_mock_response({}, status=500)]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        with pytest.raises(PubChemUpstreamError):
            await pubchem_service.lookup("acetone")


async def test_lookup_upstream_error_timeout():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(
        side_effect=httpx.TimeoutException("timeout", request=None)
    )

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        with pytest.raises(PubChemUpstreamError):
            await pubchem_service.lookup("acetone")


async def test_lookup_ghs_happy_path():
    responses = [_mock_response(_load("pubchem_acetone_ghs.json"))]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        codes = await pubchem_service.lookup_ghs("180")

    code_strs = [c.code for c in codes]
    assert "H225" in code_strs
    assert "H319" in code_strs
    assert "H336" in code_strs
    h225 = next(c for c in codes if c.code == "H225")
    assert h225.description.startswith("Highly flammable")
    assert h225.signal_word == "Danger"
    assert h225.pictogram == "GHS02"


async def test_lookup_ghs_failure_returns_empty():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(
        side_effect=httpx.TimeoutException("timeout", request=None)
    )

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        codes = await pubchem_service.lookup_ghs("180")

    assert codes == []


async def test_lookup_caches_result():
    responses = [
        _mock_response(_load("pubchem_acetone_cid.json")),
        _mock_response(_load("pubchem_acetone_properties.json")),
        _mock_response(_load("pubchem_acetone_synonyms.json")),
    ]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        r1 = await pubchem_service.lookup("acetone")
        # Second call should return cached — no more mock responses needed
        r2 = await pubchem_service.lookup("acetone")

    assert r1.cid == r2.cid
    assert client.get.call_count == 3  # only the first lookup hit the API


def test_parse_ghs_classification_extracts_codes():
    data = json.loads((FIXTURES / "pubchem_acetone_ghs.json").read_text())
    hits = parse_ghs_classification(data)
    codes = [h.code for h in hits]
    assert codes == ["H225", "H319", "H336"]
    assert all(h.signal_word in {"Danger", "Warning"} for h in hits)
    h225 = next(h for h in hits if h.code == "H225")
    assert "flammable" in h225.description.lower()


def test_parse_ghs_classification_empty():
    assert parse_ghs_classification({}) == []
    assert parse_ghs_classification({"Hierarchies": {}}) == []


async def test_fetch_structure_image_success():
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    response = httpx.Response(
        status_code=200,
        content=fake_png,
        request=httpx.Request("GET", "https://pubchem.ncbi.nlm.nih.gov/"),
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(return_value=response)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        data = await pubchem_service.fetch_structure_image("180")

    assert data == fake_png


async def test_fetch_structure_image_404_returns_none():
    response = httpx.Response(
        status_code=404,
        request=httpx.Request("GET", "https://pubchem.ncbi.nlm.nih.gov/"),
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(return_value=response)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        data = await pubchem_service.fetch_structure_image("999999")

    assert data is None


async def test_fetch_structure_image_timeout_returns_none():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(
        side_effect=httpx.TimeoutException("timeout", request=None)
    )

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        data = await pubchem_service.fetch_structure_image("180")

    assert data is None


async def test_lookup_synonym_cap():
    long_synonyms = {
        "InformationList": {
            "Information": [
                {
                    "CID": 180,
                    "Synonym": ["67-64-1"] + [f"syn-{i}" for i in range(500)],
                }
            ]
        }
    }
    responses = [
        _mock_response(_load("pubchem_acetone_cid.json")),
        _mock_response(_load("pubchem_acetone_properties.json")),
        _mock_response(long_synonyms),
    ]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        result = await pubchem_service.lookup("acetone")

    assert len(result.synonyms) == 20
