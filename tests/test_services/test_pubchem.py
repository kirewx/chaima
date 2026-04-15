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


async def test_lookup_by_name_happy_path():
    responses = [
        _mock_response(_load("pubchem_acetone_cid.json")),
        _mock_response(_load("pubchem_acetone_properties.json")),
        _mock_response(_load("pubchem_acetone_synonyms.json")),
        _mock_response(_load("pubchem_acetone_ghs.json")),
    ]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        result = await pubchem_service.lookup("acetone")

    assert result.cid == "180"
    assert result.name == "propan-2-one"
    assert result.cas == "67-64-1"
    assert result.molar_mass == pytest.approx(58.08)
    assert result.smiles == "CC(=O)C"
    assert "Acetone" in result.synonyms
    assert len(result.synonyms) <= 20
    codes = [g.code for g in result.ghs_codes]
    assert "H225" in codes
    assert "H319" in codes
    assert "H336" in codes
    h225 = next(g for g in result.ghs_codes if g.code == "H225")
    assert h225.description.startswith("Highly flammable")
    assert h225.signal_word == "Danger"
    assert h225.pictogram == "GHS02"


async def test_lookup_by_cas_happy_path():
    # CAS is passed to the same name namespace — PUG REST resolves it.
    responses = [
        _mock_response(_load("pubchem_acetone_cid.json")),
        _mock_response(_load("pubchem_acetone_properties.json")),
        _mock_response(_load("pubchem_acetone_synonyms.json")),
        _mock_response(_load("pubchem_acetone_ghs.json")),
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
        _mock_response(_load("pubchem_acetone_ghs.json")),
    ]
    client = _build_client_mock(responses)

    with patch("chaima.services.pubchem.httpx.AsyncClient", return_value=client):
        result = await pubchem_service.lookup("acetone")

    assert len(result.synonyms) == 20
