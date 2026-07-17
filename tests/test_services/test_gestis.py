# tests/test_services/test_gestis.py
import asyncio
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from chaima.services import gestis as gestis_service

# Shape matches the live GESTIS /search response (verified in
# notebooks/test_pubchem_gestis.ipynb): zvg_nr comes back unpadded.
SEARCH_FIXTURE = [
    {"zvg_nr": "10420", "cas_nr": "64-17-5", "name": "Ethanol"},
    {"zvg_nr": "11230", "cas_nr": "67-64-1", "name": "Acetone"},
    {"zvg_nr": "1330", "cas_nr": "7647-14-5", "name": "Sodium chloride"},
    {"zvg_nr": "570000", "cas_nr": None, "name": "Entry without CAS"},
    {"zvg_nr": "570001", "name": "Entry missing cas_nr key"},
]


def _mock_response(data, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=data,
        request=httpx.Request("GET", "https://gestis-api.dguv.de/"),
    )


def _build_client_mock(responses) -> AsyncMock:
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(side_effect=responses)
    return client


@pytest.fixture(autouse=True)
def _reset_gestis_index():
    """Clear the module-level index cache between tests."""
    gestis_service._index = None
    gestis_service._expiry = 0.0
    yield
    gestis_service._index = None
    gestis_service._expiry = 0.0


async def test_get_zvg_hit_zero_padded():
    client = _build_client_mock([_mock_response(SEARCH_FIXTURE)])
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        zvg = await gestis_service.get_zvg("64-17-5")
    assert zvg == "010420"


async def test_get_zvg_strips_whitespace():
    client = _build_client_mock([_mock_response(SEARCH_FIXTURE)])
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        zvg = await gestis_service.get_zvg("  64-17-5 ")
    assert zvg == "010420"


async def test_get_zvg_miss_returns_none():
    client = _build_client_mock([_mock_response(SEARCH_FIXTURE)])
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        # 50-78-2 (aspirin) has a valid check digit but is not in the fixture.
        zvg = await gestis_service.get_zvg("50-78-2")
    assert zvg is None


async def test_entries_without_cas_are_skipped():
    client = _build_client_mock([_mock_response(SEARCH_FIXTURE)])
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        await gestis_service.get_zvg("64-17-5")
    assert None not in gestis_service._index
    assert len(gestis_service._index) == 3


async def test_invalid_cas_pattern_no_http_call():
    with patch("chaima.services.gestis.httpx.AsyncClient") as client_cls:
        assert await gestis_service.get_zvg("not-a-cas") is None
        assert await gestis_service.get_zvg("") is None
    client_cls.assert_not_called()


async def test_bad_check_digit_no_http_call():
    with patch("chaima.services.gestis.httpx.AsyncClient") as client_cls:
        # 64-17-6: pattern ok, check digit wrong (correct is 5).
        assert await gestis_service.get_zvg("64-17-6") is None
    client_cls.assert_not_called()


async def test_upstream_500_returns_none_and_warns(caplog):
    client = _build_client_mock([_mock_response({}, status=500)])
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        with caplog.at_level("WARNING"):
            zvg = await gestis_service.get_zvg("64-17-5")
    assert zvg is None
    assert any("GESTIS" in r.message for r in caplog.records)


async def test_timeout_returns_none():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout", request=None))
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        zvg = await gestis_service.get_zvg("64-17-5")
    assert zvg is None


async def test_ttl_expiry_triggers_refetch():
    client = _build_client_mock(
        [_mock_response(SEARCH_FIXTURE), _mock_response(SEARCH_FIXTURE)]
    )
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        await gestis_service.get_zvg("64-17-5")
        gestis_service._expiry = 0.0  # force expiry
        await gestis_service.get_zvg("64-17-5")
    assert client.get.await_count == 2


async def test_failed_refresh_serves_stale_index():
    client = _build_client_mock(
        [_mock_response(SEARCH_FIXTURE), _mock_response({}, status=500)]
    )
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        assert await gestis_service.get_zvg("64-17-5") == "010420"
        gestis_service._expiry = 0.0  # force expiry; refresh will 500
        assert await gestis_service.get_zvg("64-17-5") == "010420"


async def test_concurrent_first_lookups_fetch_once():
    client = _build_client_mock([_mock_response(SEARCH_FIXTURE)])
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        results = await asyncio.gather(
            gestis_service.get_zvg("64-17-5"),
            gestis_service.get_zvg("67-64-1"),
        )
    assert results == ["010420", "011230"]
    assert client.get.await_count == 1


async def test_get_zvg_if_warm_cold_index_returns_none():
    with patch("chaima.services.gestis.httpx.AsyncClient") as client_cls:
        assert gestis_service.get_zvg_if_warm("64-17-5") is None
    client_cls.assert_not_called()


async def test_get_zvg_if_warm_after_load():
    gestis_service._index = {"64-17-5": "010420"}
    gestis_service._expiry = time.time() + 3600
    assert gestis_service.get_zvg_if_warm("64-17-5") == "010420"
    assert gestis_service.get_zvg_if_warm("67-64-1") is None
    assert gestis_service.get_zvg_if_warm("garbage") is None


async def test_load_index_reports_availability():
    client = _build_client_mock([_mock_response(SEARCH_FIXTURE)])
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        assert await gestis_service.load_index() is True

    gestis_service._index = None
    gestis_service._expiry = 0.0
    failing = _build_client_mock([_mock_response({}, status=500)])
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=failing):
        assert await gestis_service.load_index() is False


async def test_preload_index_never_raises():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(side_effect=httpx.TransportError("boom"))
    with patch("chaima.services.gestis.httpx.AsyncClient", return_value=client):
        await gestis_service.preload_index()  # must not raise
    assert gestis_service._index is None


def test_gestis_url():
    assert (
        gestis_service.gestis_url("010420")
        == "https://gestis-database.dguv.de/data?name=010420"
    )
