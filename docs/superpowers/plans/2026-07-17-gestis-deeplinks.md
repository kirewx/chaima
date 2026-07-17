# GESTIS Deeplinks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every chemical with a CAS number gets a persistent deeplink to its official GESTIS substance datasheet, resolved once via an in-memory CAS→ZVG index and stored in a new `zvg` column.

**Architecture:** A new `services/gestis.py` downloads the full GESTIS substance list (~8,740 entries) once, indexes it by CAS in module memory (24 h TTL, serve-stale-on-error), and exposes an async `get_zvg` plus a never-blocking `get_zvg_if_warm` for write paths. A chemical-scoped `POST .../gestis-resolve` endpoint persists the ZVG on first info-box open; create/update/enrich hooks and a superuser SSE backfill fill it proactively. The frontend builds the deeplink client-side from the stored value.

**Tech Stack:** FastAPI + SQLModel + Alembic (backend), httpx (GESTIS API), React + MUI + TanStack Query (frontend), pytest + Playwright (tests).

**Spec:** `docs/superpowers/specs/2026-07-16-gestis-deeplinks-design.md`

**Branch note:** Current checkout may be on `feat/docker-deploy`. Before Task 1, create a feature branch off `main`: `git checkout main && git pull && git checkout -b feat/gestis-deeplinks`. Also `git add` the spec file above in the first commit.

**Commit policy (user preference, overrides the default):** The user reviews uncommitted changes himself before anything is committed. At each "Commit" step, STOP and ask for review instead of committing autonomously, unless the user has explicitly said to commit without review in this session.

**Test commands:** Backend: `uv run pytest <path> -v` (asyncio_mode is `auto` — plain `async def` tests, no decorator). Frontend type-check/build: `npm --prefix frontend run build`.

---

## Task 1: GESTIS settings in config

**Files:**
- Modify: `src/chaima/config.py` (add two fields to `Settings`, after `require_secure_config`)
- Test: `tests/test_config.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
def test_gestis_settings_defaults():
    from chaima.config import Settings

    s = Settings()
    assert s.gestis_api_base == "https://gestis-api.dguv.de/api"
    # Shipped default is GESTIS's public web-client key (served in cleartext
    # by their own SPA) — non-empty, overridable via env.
    assert s.gestis_api_key


def test_gestis_settings_env_override(monkeypatch):
    from chaima.config import Settings

    monkeypatch.setenv("CHAIMA_GESTIS_API_BASE", "https://example.invalid/api")
    monkeypatch.setenv("CHAIMA_GESTIS_API_KEY", "test-key")
    s = Settings()
    assert s.gestis_api_base == "https://example.invalid/api"
    assert s.gestis_api_key == "test-key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'gestis_api_base'` (or assertion error).

- [ ] **Step 3: Implement**

In `src/chaima/config.py`, inside `class Settings`, after the `require_secure_config` field and before `model_config`:

```python
    # GESTIS (DGUV hazardous-substance database) API. The shipped key is the
    # public web-client key from GESTIS's own SPA (env-config.js) — it is
    # served in cleartext to every browser, so it is public by design, not a
    # secret. Override via CHAIMA_GESTIS_API_KEY like any other setting.
    gestis_api_base: str = "https://gestis-api.dguv.de/api"
    gestis_api_key: str = "dddiiasjhduuvnnasdkkwUUSHhjaPPKMasd"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (all, including pre-existing tests).

- [ ] **Step 5: Commit (after user review)**

```bash
git add docs/superpowers/specs/2026-07-16-gestis-deeplinks-design.md tests/test_config.py src/chaima/config.py
git commit -m "feat(gestis): add GESTIS API settings"
```

---

## Task 2: `zvg` column on Chemical (model + migration + read schemas)

**Files:**
- Modify: `src/chaima/models/chemical.py` (one field, after `cid`)
- Modify: `src/chaima/schemas/chemical.py` (`ChemicalRead` only — NOT Create/Update)
- Create: `alembic/versions/d2f4a6b8c0e2_add_chemical_zvg.py`
- Test: `tests/test_models/test_chemical_zvg.py` (new)

`zvg` is server-authoritative: readable by clients, never settable through `ChemicalCreate`/`ChemicalUpdate` (mirrors how `cid` enrichment works, but stricter — `cid` is client-settable, `zvg` is not).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_models/test_chemical_zvg.py`:

```python
import uuid

from chaima.models.chemical import Chemical
from chaima.schemas.chemical import ChemicalCreate, ChemicalRead, ChemicalUpdate


def test_chemical_model_has_nullable_zvg():
    chem = Chemical(name="Ethanol", group_id=uuid.uuid4(), created_by=uuid.uuid4())
    assert chem.zvg is None


def test_zvg_is_read_only_in_api_schemas():
    # Server-authoritative: exposed on reads, never accepted on writes.
    assert "zvg" in ChemicalRead.model_fields
    assert "zvg" not in ChemicalCreate.model_fields
    assert "zvg" not in ChemicalUpdate.model_fields
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_chemical_zvg.py -v`
Expected: FAIL — `Chemical` has no attribute `zvg` / `zvg` not in `ChemicalRead.model_fields`.

- [ ] **Step 3: Implement model + schema**

In `src/chaima/models/chemical.py`, in `class Chemical`, directly after the `cid` field:

```python
    zvg: str | None = Field(default=None)
```

In `src/chaima/schemas/chemical.py`, in `class ChemicalRead`, directly after the `cid: str | None` line:

```python
    zvg: str | None = None
```

(`ChemicalDetail` inherits it. Do NOT touch `ChemicalCreate`/`ChemicalUpdate`.)

- [ ] **Step 4: Write the migration**

Create `alembic/versions/d2f4a6b8c0e2_add_chemical_zvg.py` (current head is `a1b2c3d4e5f6`):

```python
"""add chemical zvg

Revision ID: d2f4a6b8c0e2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd2f4a6b8c0e2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'chemical',
        sa.Column('zvg', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chemical', 'zvg')
```

- [ ] **Step 5: Verify migration against a scratch DB**

Run (Bash): `cd /c/Users/erikw/Documents/Projekte/ChAiMa && CHAIMA_DATABASE_URL="sqlite+aiosqlite:///./scratch_zvg.db" uv run alembic upgrade head && rm -f scratch_zvg.db`
Expected: output ends with `Running upgrade a1b2c3d4e5f6 -> d2f4a6b8c0e2, add chemical zvg`, exit 0.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_models/test_chemical_zvg.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit (after user review)**

```bash
git add src/chaima/models/chemical.py src/chaima/schemas/chemical.py alembic/versions/d2f4a6b8c0e2_add_chemical_zvg.py tests/test_models/test_chemical_zvg.py
git commit -m "feat(gestis): add nullable zvg column to chemical"
```

---

## Task 3: GESTIS index service

**Files:**
- Create: `src/chaima/services/gestis.py`
- Test: `tests/test_services/test_gestis.py` (new)

The GESTIS API has **no server-side CAS search** — `GET /search/<anything>` ignores the query and always returns the full pure-substance list (~8,740 JSON objects with `zvg_nr`, `cas_nr`, `name`). Verified live 2026-07-06/09 in `notebooks/test_pubchem_gestis.ipynb`. We download once, index `{cas_nr: zvg_nr.zfill(6)}` in module memory, TTL 24 h, and serve a stale index when a refresh fails.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_services/test_gestis.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_gestis.py -v`
Expected: FAIL with `ModuleNotFoundError`/`ImportError` for `chaima.services.gestis`.

- [ ] **Step 3: Implement the service**

Create `src/chaima/services/gestis.py`:

```python
# src/chaima/services/gestis.py
"""Async CAS→ZVG index service for GESTIS (DGUV hazardous-substance database).

A GESTIS deeplink needs GESTIS's internal substance id (ZVG), not the CAS.
The GESTIS API has no server-side CAS search — its ``search`` endpoint
ignores the query and always returns the full pure-substance list
(~8,740 entries), which the official SPA filters locally. We do the same:
download the list once, index it by ``cas_nr`` in module memory with a
24 h TTL, and keep serving a stale index when a refresh fails.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

import httpx

from chaima.config import settings

logger = logging.getLogger(__name__)

_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
_TIMEOUT = 30.0
_CACHE_TTL = 86400  # 24 hours — the GESTIS substance list barely changes

_WEB_BASE_URL = "https://gestis-database.dguv.de/data?name="

# Module-level cache, same pattern as services/pubchem.py.
_index: dict[str, str] | None = None
_expiry: float = 0.0
_load_lock = asyncio.Lock()


def gestis_url(zvg: str) -> str:
    """Public EN deeplink for a ZVG number (linking explicitly permitted)."""
    return f"{_WEB_BASE_URL}{zvg}"


def _cas_check_digit_ok(cas: str) -> bool:
    """Validate the CAS check digit (the last digit of the number)."""
    digits = cas.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * i for i, d in enumerate(reversed(body), start=1))
    return total % 10 == check


def _normalize_cas(cas: str) -> str | None:
    """Strip and validate a CAS; None when pattern or check digit is wrong."""
    cas = cas.strip()
    if not _CAS_RE.match(cas):
        return None
    if not _cas_check_digit_ok(cas):
        return None
    return cas


async def _fetch_index() -> dict[str, str]:
    """Download the full GESTIS substance list and index it by CAS.

    ZVG numbers are zero-padded to 6 chars — exactly as deeplinks need
    them. Raises on any upstream failure; callers decide how to degrade.
    """
    headers = {
        "Authorization": f"Bearer {settings.gestis_api_key}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT)) as client:
        resp = await client.get(
            f"{settings.gestis_api_base}/search/x", headers=headers
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"GESTIS index fetch returned {resp.status_code}")
    return {
        entry["cas_nr"]: str(entry["zvg_nr"]).zfill(6)
        for entry in resp.json()
        if entry.get("cas_nr") and entry.get("zvg_nr")
    }


async def _ensure_index() -> dict[str, str] | None:
    """Return the CAS→ZVG index, loading or refreshing it when needed.

    A failed refresh keeps serving the previous (stale) index; a failed
    first load returns None. A single in-flight load is guarded by a lock
    so concurrent first lookups don't download the list twice.
    """
    global _index, _expiry
    if _index is not None and time.time() < _expiry:
        return _index
    async with _load_lock:
        if _index is not None and time.time() < _expiry:
            return _index
        try:
            fresh = await _fetch_index()
        except Exception as exc:
            logger.warning("GESTIS index load failed: %s", exc)
            return _index  # stale-but-present index keeps serving
        _index = fresh
        _expiry = time.time() + _CACHE_TTL
        return _index


async def get_zvg(cas: str) -> str | None:
    """Resolve a CAS to a zero-padded ZVG, loading the index if needed.

    An invalid CAS (pattern or check digit) returns None without any
    upstream call; upstream failures degrade to None.
    """
    normalized = _normalize_cas(cas)
    if normalized is None:
        return None
    index = await _ensure_index()
    if index is None:
        return None
    return index.get(normalized)


def get_zvg_if_warm(cas: str) -> str | None:
    """Resolve a CAS against an already-loaded index; never awaits the network.

    Write paths (chemical create/update, PubChem enrich) use this so they
    never wait on a GESTIS list download and never fail when GESTIS is
    down. Cold index → None; an expired-but-present index still serves.
    """
    if _index is None:
        return None
    normalized = _normalize_cas(cas)
    if normalized is None:
        return None
    return _index.get(normalized)


async def load_index() -> bool:
    """Ensure the index is loaded; True when one (fresh or stale) is available."""
    return await _ensure_index() is not None


async def preload_index() -> None:
    """Background pre-load fired from the app lifespan. Never raises."""
    try:
        await _ensure_index()
    except Exception as exc:
        logger.warning("GESTIS index preload failed: %s", exc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_gestis.py -v`
Expected: PASS (16 tests).

- [ ] **Step 5: Commit (after user review)**

```bash
git add src/chaima/services/gestis.py tests/test_services/test_gestis.py
git commit -m "feat(gestis): CAS-to-ZVG index service with TTL cache"
```

---

## Task 4: Resolve endpoint (`POST .../{chemical_id}/gestis-resolve`)

**Files:**
- Create: `src/chaima/schemas/gestis.py`
- Modify: `src/chaima/routers/chemicals.py` (imports + one endpoint, placed directly before the `class EnrichBody` definition near line 842)
- Test: `tests/test_api/test_gestis_resolve.py` (new)

Chemical-scoped and mutating, so it runs through the existing group-membership chain. Idempotent: a stored `zvg` short-circuits without an upstream call. Never 5xxs on GESTIS failure (decision (h)).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api/test_gestis_resolve.py` (fixtures `client`, `session`, `group`, `user`, `membership`, `other_user` come from `tests/test_api/conftest.py`):

```python
from unittest.mock import AsyncMock, patch

from chaima.models.chemical import Chemical
from chaima.models.group import Group


async def test_resolve_hit_persists_zvg(client, session, group, user, membership):
    chem = Chemical(
        name="Ethanol", cas="64-17-5", group_id=group.id, created_by=user.id
    )
    session.add(chem)
    await session.commit()

    with patch(
        "chaima.services.gestis.get_zvg", AsyncMock(return_value="010420")
    ):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
        )
    assert resp.status_code == 200
    assert resp.json() == {
        "zvg": "010420",
        "url": "https://gestis-database.dguv.de/data?name=010420",
    }
    await session.refresh(chem)
    assert chem.zvg == "010420"


async def test_resolve_with_stored_zvg_skips_upstream(
    client, session, group, user, membership
):
    chem = Chemical(
        name="Ethanol", cas="64-17-5", zvg="010420",
        group_id=group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    mock_get_zvg = AsyncMock()
    with patch("chaima.services.gestis.get_zvg", mock_get_zvg):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
        )
    assert resp.status_code == 200
    assert resp.json()["zvg"] == "010420"
    mock_get_zvg.assert_not_called()


async def test_resolve_without_cas_returns_nulls(
    client, session, group, user, membership
):
    chem = Chemical(name="Mystery", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    mock_get_zvg = AsyncMock()
    with patch("chaima.services.gestis.get_zvg", mock_get_zvg):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
        )
    assert resp.status_code == 200
    assert resp.json() == {"zvg": None, "url": None}
    mock_get_zvg.assert_not_called()


async def test_resolve_miss_returns_nulls_persists_nothing(
    client, session, group, user, membership
):
    chem = Chemical(
        name="Cocaine", cas="50-36-2", group_id=group.id, created_by=user.id
    )
    session.add(chem)
    await session.commit()

    with patch("chaima.services.gestis.get_zvg", AsyncMock(return_value=None)):
        resp = await client.post(
            f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
        )
    assert resp.status_code == 200
    assert resp.json() == {"zvg": None, "url": None}
    await session.refresh(chem)
    assert chem.zvg is None


async def test_resolve_foreign_group_forbidden(
    client, session, group, user, membership
):
    other_group = Group(name="Lab Beta")
    session.add(other_group)
    await session.flush()
    chem = Chemical(
        name="Ethanol", cas="64-17-5",
        group_id=other_group.id, created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    resp = await client.post(
        f"/api/v1/groups/{other_group.id}/chemicals/{chem.id}/gestis-resolve"
    )
    assert resp.status_code == 403  # GroupMemberDep: not a member


async def test_resolve_secret_chemical_of_other_user_404(
    client, session, group, user, membership, other_user
):
    chem = Chemical(
        name="Secret stuff", cas="64-17-5", is_secret=True,
        group_id=group.id, created_by=other_user.id,
    )
    session.add(chem)
    await session.commit()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{chem.id}/gestis-resolve"
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_gestis_resolve.py -v`
Expected: FAIL — all with 404/405 (route does not exist yet), or ImportError.

- [ ] **Step 3: Implement schema + endpoint**

Create `src/chaima/schemas/gestis.py`:

```python
# src/chaima/schemas/gestis.py
from pydantic import BaseModel


class GestisResolveResult(BaseModel):
    """Result of resolving a chemical's CAS against the GESTIS index.

    Parameters
    ----------
    zvg : str or None
        GESTIS substance id, zero-padded to 6 chars (e.g. ``"010420"``),
        or None on miss / missing CAS / GESTIS unavailable.
    url : str or None
        Public EN deeplink built from ``zvg``, or None.
    """

    zvg: str | None
    url: str | None
```

In `src/chaima/routers/chemicals.py`, add to the imports (after the `from chaima.schemas.pagination import ...` line):

```python
from chaima.schemas.gestis import GestisResolveResult
from chaima.services import gestis as gestis_service
```

Add the endpoint directly before `class EnrichBody(BaseModel):`:

```python
@router.post("/{chemical_id}/gestis-resolve", response_model=GestisResolveResult)
async def resolve_gestis(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
) -> GestisResolveResult:
    """Resolve the chemical's CAS to a GESTIS ZVG and persist it.

    Idempotent: a stored ``zvg`` is returned without an upstream call.
    GESTIS being unreachable or the CAS not being listed both yield 200
    with nulls — upstream problems never surface as 5xx (only auth or
    ownership errors produce 4xx).
    """
    chem = await chemical_service.get_chemical(session, chemical_id)
    if (
        chem is None
        or chem.group_id != group_id
        or not chemical_service.can_view_chemical(chem, user)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found"
        )
    if chem.zvg:
        return GestisResolveResult(
            zvg=chem.zvg, url=gestis_service.gestis_url(chem.zvg)
        )
    if not chem.cas:
        return GestisResolveResult(zvg=None, url=None)
    zvg = await gestis_service.get_zvg(chem.cas)
    if zvg is None:
        return GestisResolveResult(zvg=None, url=None)
    chem.zvg = zvg
    session.add(chem)
    await session.commit()
    return GestisResolveResult(zvg=zvg, url=gestis_service.gestis_url(zvg))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_gestis_resolve.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit (after user review)**

```bash
git add src/chaima/schemas/gestis.py src/chaima/routers/chemicals.py tests/test_api/test_gestis_resolve.py
git commit -m "feat(gestis): chemical-scoped resolve-and-store endpoint"
```

---

## Task 5: Warm auto-resolve on create/update

**Files:**
- Modify: `src/chaima/services/chemicals.py` (`create_chemical`, `update_chemical`)
- Test: `tests/test_services/test_chemicals_gestis.py` (new)

Uses `get_zvg_if_warm` only (decision (i)): writes never wait on a GESTIS download and never fail when GESTIS is down. A CAS change invalidates the stored `zvg` (decision (j)) — including clearing it when the CAS is removed.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_services/test_chemicals_gestis.py` (fixtures `session`, `group`, `user` from `tests/test_services/conftest.py`):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_chemicals_gestis.py -v`
Expected: FAIL — `zvg` stays None on warm-index create / stays stale on update (assertions fail).

- [ ] **Step 3: Implement the hooks**

In `src/chaima/services/chemicals.py`:

Add to the imports (after `from chaima.models.user import User`):

```python
from chaima.services import gestis as gestis_service
```

In `create_chemical`, replace the `chem = Chemical(` construction's first lines — insert one line before it and one field into it. Directly before `chem = Chemical(`:

```python
    # Warm-index-only GESTIS resolution: never waits on a network download
    # (cold index → zvg stays null; the info-box resolve catches up later).
    zvg = gestis_service.get_zvg_if_warm(cas) if cas else None
```

and inside the `Chemical(...)` constructor call, after the `cas=cas,` line add:

```python
        zvg=zvg,
```

In `update_chemical`, inside the existing `if "cas" in kwargs:` block, directly after the line `kwargs["cas"] = new_cas`, add:

```python
        # A CAS change invalidates the stored zvg; re-resolve against the
        # warm index only (a stale deeplink must never point at the wrong
        # substance, and updates must never wait on GESTIS).
        if new_cas != chemical.cas:
            kwargs["zvg"] = (
                gestis_service.get_zvg_if_warm(new_cas) if new_cas else None
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_chemicals_gestis.py tests/test_services/test_chemicals.py tests/test_api/test_chemicals.py -v`
Expected: PASS (new tests plus all pre-existing chemical tests — no regressions).

- [ ] **Step 5: Commit (after user review)**

```bash
git add src/chaima/services/chemicals.py tests/test_services/test_chemicals_gestis.py
git commit -m "feat(gestis): warm-index auto-resolve on chemical create/update"
```

---

## Task 6: Warm auto-resolve in PubChem enrich

**Files:**
- Modify: `src/chaima/services/enrich.py` (`enrich_one`)
- Test: `tests/test_services/test_enrich_gestis.py` (new)

When the PubChem lookup yields or confirms a CAS, attempt warm GESTIS resolution before the flush. Covers the interactive fetch flow and the bulk PubChem backfill.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_services/test_enrich_gestis.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_enrich_gestis.py -v`
Expected: `test_enrich_one_sets_zvg_when_index_warm` FAILS (`chem.zvg is None`); the other two may already pass — that's fine.

- [ ] **Step 3: Implement the hook**

In `src/chaima/services/enrich.py`:

Add to the imports (after the `from chaima.services.pubchem import (...)` block):

```python
from chaima.services import gestis as gestis_service
```

In `enrich_one`, directly before the `session.add(chemical)` / `await session.flush()` pair, add:

```python
    if chemical.cas and not chemical.zvg:
        # Warm-index-only GESTIS resolution (never blocks on a download).
        zvg = gestis_service.get_zvg_if_warm(chemical.cas)
        if zvg:
            chemical.zvg = zvg
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services/test_enrich_gestis.py tests/test_services/test_enrich.py -v`
Expected: PASS (new tests plus all pre-existing enrich tests).

- [ ] **Step 5: Commit (after user review)**

```bash
git add src/chaima/services/enrich.py tests/test_services/test_enrich_gestis.py
git commit -m "feat(gestis): resolve zvg during PubChem enrichment"
```

---

## Task 7: Bulk backfill (generator + SSE endpoint)

**Files:**
- Modify: `src/chaima/services/enrich.py` (new generator at end of file)
- Modify: `src/chaima/routers/chemicals.py` (new endpoint after `refetch_ghs`)
- Test: `tests/test_api/test_gestis_backfill.py` (new)

Mirrors `enrich-pubchem`/`refetch-ghs`: superuser-only, body `{chemical_ids: [...] | null}`, SSE stream with one event per chemical plus a final summary, one commit per chemical so progress survives interruption. The index is loaded **once** before the loop (this is the one call that may download the list); per-chemical resolution is then a local dict lookup, so the loop needs no throttle delay (decision (k)) — unlike the PubChem generators.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api/test_gestis_backfill.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api/test_gestis_backfill.py -v`
Expected: FAIL — 404/405 (route missing).

- [ ] **Step 3: Implement generator + endpoint**

In `src/chaima/services/enrich.py`:

Add next to the existing status type aliases (after `RefetchGHSStatus = ...`):

```python
GestisBackfillStatus = Literal["resolved", "skipped", "not_found", "error"]
```

Append at the end of the file:

```python
async def backfill_group_gestis(
    session: AsyncSession,
    group_id: UUID,
    chemical_ids: list[UUID] | None,
) -> AsyncGenerator[dict, None]:
    """Yield SSE-style events while resolving GESTIS ZVGs for a group.

    Default selection (``chemical_ids`` None): every chemical with a CAS
    and no ``zvg`` yet. The index is loaded once up front (the only call
    that may download the substance list); per-chemical resolution is a
    local dict lookup, so — unlike the PubChem backfills — the loop needs
    no throttle delay. One commit per chemical so progress survives
    interruption.
    """
    stmt = select(Chemical).where(Chemical.group_id == group_id)
    if chemical_ids is not None:
        stmt = stmt.where(Chemical.id.in_(chemical_ids))
    else:
        stmt = stmt.where(
            Chemical.cas.is_not(None),  # type: ignore[union-attr]
            Chemical.zvg.is_(None),  # type: ignore[union-attr]
        )
    result = await session.exec(stmt)
    chemicals = list(result.all())

    index_available = await gestis_service.load_index()

    counts: dict[str, int] = {
        "resolved": 0, "skipped": 0, "not_found": 0, "error": 0
    }
    for chem in chemicals:
        if chem.zvg or not chem.cas:
            chem_status = "skipped"
        elif not index_available:
            chem_status = "error"
        else:
            zvg = gestis_service.get_zvg_if_warm(chem.cas)
            if zvg is None:
                chem_status = "not_found"
            else:
                chem.zvg = zvg
                session.add(chem)
                chem_status = "resolved"
        counts[chem_status] += 1
        yield {"id": str(chem.id), "name": chem.name, "status": chem_status}
        await session.commit()

    yield {"summary": counts}
```

In `src/chaima/routers/chemicals.py`, append after the `refetch_ghs` endpoint:

```python
@router.post("/backfill-gestis")
async def backfill_gestis(
    group_id: UUID,
    body: EnrichBody,
    session: SessionDep,
    user: SuperuserDep,
) -> StreamingResponse:
    """Stream a bulk CAS→ZVG resolution for chemicals in the group.

    Superuser-only. Defaults to every chemical with a CAS and no stored
    ``zvg``. Resolution is a local index lookup after a single list
    download, so the stream runs without throttling.
    """
    async def generate():
        async for event in enrich_service.backfill_group_gestis(
            session, group_id, body.chemical_ids,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api/test_gestis_backfill.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit (after user review)**

```bash
git add src/chaima/services/enrich.py src/chaima/routers/chemicals.py tests/test_api/test_gestis_backfill.py
git commit -m "feat(gestis): superuser SSE backfill for missing zvg values"
```

---

## Task 8: Index pre-load in the app lifespan

**Files:**
- Modify: `src/chaima/app.py` (lifespan)

Non-blocking (decision (e)): startup never waits on GESTIS; `preload_index` already swallows every error (tested in Task 3). Test clients (`ASGITransport`) don't run the lifespan, so the test suite is unaffected.

- [ ] **Step 1: Implement**

In `src/chaima/app.py`, add to the imports (after `from chaima.services.seed import run_seeds`):

```python
from chaima.services.gestis import preload_index
```

Replace the `lifespan` function body:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_secure_config()
    await asyncio.to_thread(_run_migrations)
    async with async_session_maker() as session:
        await seed_admin(session)
        await run_seeds(session)
    # Background pre-load of the GESTIS CAS→ZVG index (~8,740 entries, one
    # request). Never blocks startup; failures degrade to on-demand loads.
    preload_task = asyncio.create_task(preload_index())
    yield
    preload_task.cancel()
```

- [ ] **Step 2: Verify nothing broke**

Run: `uv run pytest tests/ -x -q`
Expected: full suite PASS (446+ tests, plus the new ones).

- [ ] **Step 3: Smoke-test startup (optional but recommended)**

Run: `uv run chaima run` briefly and confirm the log shows no GESTIS-related error at startup (a warning is acceptable if offline), then stop it. **Windows caveat:** stop with Ctrl+C in the same terminal; killing the terminal window leaves a zombie listener on port 8000 (see project memory).

- [ ] **Step 4: Commit (after user review)**

```bash
git add src/chaima/app.py
git commit -m "feat(gestis): pre-load CAS index in app lifespan"
```

---

## Task 9: Frontend types + `useGestisResolve` hook

**Files:**
- Modify: `frontend/src/types/index.ts` (`ChemicalRead` interface, after `cid`)
- Create: `frontend/src/api/hooks/useGestis.ts`

On a hit the hook writes the new `zvg` straight into the React Query caches (detail + infinite list pages) instead of invalidating — the link appears without a refetch, which also keeps the e2e tests network-independent.

- [ ] **Step 1: Add the type field**

In `frontend/src/types/index.ts`, in `interface ChemicalRead`, directly after the `cid: string | null;` line:

```typescript
  zvg: string | null;
```

(`ChemicalDetail` extends `ChemicalRead`; `ChemicalCreate`/`ChemicalUpdate` stay untouched — `zvg` is server-authoritative.)

- [ ] **Step 2: Create the hook**

Create `frontend/src/api/hooks/useGestis.ts`:

```typescript
import { useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import client from "../client";
import type { ChemicalDetail, ChemicalRead, PaginatedResponse } from "../../types";

export interface GestisResolveResult {
  zvg: string | null;
  url: string | null;
}

// EN deeplink base — linking is explicitly permitted by GESTIS.
export function gestisUrl(zvg: string): string {
  return `https://gestis-database.dguv.de/data?name=${zvg}`;
}

export function useGestisResolve(groupId: string, chemicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      client
        .post(`/groups/${groupId}/chemicals/${chemicalId}/gestis-resolve`)
        .then((r) => r.data as GestisResolveResult),
    onSuccess: (result) => {
      if (!result.zvg) return; // miss / GESTIS down: nothing to update
      const zvg = result.zvg;
      // Detail query: plain ChemicalDetail object.
      queryClient.setQueryData<ChemicalDetail>(
        ["chemicals", groupId, chemicalId],
        (old) => (old ? { ...old, zvg } : old),
      );
      // List queries: infinite data with paginated pages. The prefix also
      // matches detail keys, so guard on the "pages" shape.
      queryClient.setQueriesData<InfiniteData<PaginatedResponse<ChemicalRead>>>(
        { queryKey: ["chemicals", groupId] },
        (old) => {
          if (!old || !("pages" in old)) return old;
          return {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((c) =>
                c.id === chemicalId ? { ...c, zvg } : c,
              ),
            })),
          };
        },
      );
    },
  });
}
```

- [ ] **Step 3: Verify it compiles**

Run: `npm --prefix frontend run build`
Expected: `tsc -b` and `vite build` succeed with no errors.

- [ ] **Step 4: Commit (after user review)**

```bash
git add frontend/src/types/index.ts frontend/src/api/hooks/useGestis.ts
git commit -m "feat(gestis): frontend types and resolve mutation hook"
```

---

## Task 10: GESTIS link row + auto-resolve in ChemicalInfoBox

**Files:**
- Modify: `frontend/src/components/ChemicalInfoBox.tsx`

Behavior (spec "User flow"): `zvg` set → render link immediately; `zvg` null but `cas` set → fire the resolve mutation once per opened chemical; miss/error/no CAS → render nothing, silently (background enrichment, not a user action — no toast).

- [ ] **Step 1: Implement**

In `frontend/src/components/ChemicalInfoBox.tsx`:

Change the first import line from `import { useRef, useState } from "react";` to:

```typescript
import { useEffect, useRef, useState } from "react";
```

Add after the other hook imports (e.g. after the `useUploadSDS` import line):

```typescript
import { gestisUrl, useGestisResolve } from "../api/hooks/useGestis";
```

Inside the component, after the line `const isAdmin = useIsGroupAdmin(groupId);`, add:

```typescript
  const resolveGestis = useGestisResolve(groupId, chemical.id);
  const resolveGestisMutate = resolveGestis.mutate;
  // Auto-resolve once per opened chemical: only when a CAS exists but no
  // zvg is stored yet. A miss changes nothing, so the effect won't re-fire
  // until the box is reopened — misses are retried on the next open.
  useEffect(() => {
    if (chemical.zvg || !chemical.cas) return;
    resolveGestisMutate();
  }, [chemical.id, chemical.zvg, chemical.cas, resolveGestisMutate]);
```

In the JSX "Links" section, directly after the PubChem block (the `{chemical.cid ? (...) : (...)}` expression ends with `)}` before the `{chemical.sds_path ? (` line), insert:

```tsx
        {chemical.zvg && (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", mb: 0.5 }}>
            <LinkIcon sx={{ fontSize: 12, color: "primary.main" }} />
            <MuiLink
              href={gestisUrl(chemical.zvg)}
              target="_blank"
              rel="noopener"
              sx={{ fontSize: 11 }}
            >
              GESTIS {chemical.zvg}
            </MuiLink>
          </Stack>
        )}
```

(No placeholder row when there is no `zvg` — decision (c).)

- [ ] **Step 2: Verify it compiles and lints**

Run: `npm --prefix frontend run build && npm --prefix frontend run lint`
Expected: both succeed with no new errors.

- [ ] **Step 3: Commit (after user review)**

```bash
git add frontend/src/components/ChemicalInfoBox.tsx
git commit -m "feat(gestis): deeplink row with auto-resolve in chemical info box"
```

---

## Task 11: Admin backfill control in Settings → Chemicals

**Files:**
- Modify: `frontend/src/components/settings/ChemicalsAdminSection.tsx`

Clones the existing `RefetchGHSControl` SSE fetch-and-dialog pattern, superuser-only.

- [ ] **Step 1: Implement**

In `frontend/src/components/settings/ChemicalsAdminSection.tsx`:

Add a type next to the existing event types (after `type RefetchGHSEvent = ...`):

```typescript
type GestisBackfillEvent =
  | { id: string; name: string; status: "resolved" | "skipped" | "not_found" | "error" }
  | { summary: { resolved: number; skipped: number; not_found: number; error: number } };
```

In the `ChemicalsAdminSection` JSX, directly after the line `{isSuperuser && <RefetchGHSControl groupId={groupId} />}`, add:

```tsx
        {isSuperuser && <GestisBackfillControl groupId={groupId} />}
```

Append this component after the `RefetchGHSControl` function (before `AssignHazardsDebug`):

```tsx
function GestisBackfillControl({ groupId }: { groupId: string }) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<GestisBackfillEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const start = async () => {
    setRunning(true);
    setEvents([]);
    setErr(null);
    try {
      const resp = await fetch(`/api/v1/groups/${groupId}/chemicals/backfill-gestis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chemical_ids: null }),
        credentials: "include",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n");
        buf = parts.pop()!;
        for (const line of parts) {
          if (!line.startsWith("data: ")) continue;
          const ev = JSON.parse(line.slice(6)) as GestisBackfillEvent;
          setEvents((prev) => [...prev, ev]);
        }
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const summary = events.find((e) => "summary" in e) as
    | { summary: { resolved: number; skipped: number; not_found: number; error: number } }
    | undefined;
  const perChemCount = events.filter((e) => "id" in e).length;

  return (
    <>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Button
          variant="outlined"
          size="small"
          startIcon={<ScienceIcon />}
          onClick={() => setOpen(true)}
        >
          Resolve GESTIS links
        </Button>
        <Typography variant="body2" color="text.secondary">
          Superuser-only. Stores the GESTIS substance id for every chemical
          with a CAS number that has none yet.
        </Typography>
      </Stack>

      <Dialog open={open} onClose={() => !running && setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Resolve GESTIS links</DialogTitle>
        <DialogContent>
          {!running && !summary && (
            <Typography>
              This resolves the GESTIS substance id (ZVG) for every chemical in
              this group that has a CAS number but no GESTIS link yet. The full
              substance list is downloaded once; after that each chemical is a
              local lookup, so this is fast.
            </Typography>
          )}
          {running && (
            <Stack spacing={2}>
              <LinearProgress />
              <Typography variant="body2">{perChemCount} processed…</Typography>
            </Stack>
          )}
          {summary && (
            <Alert severity="success">
              Resolved {summary.summary.resolved}, skipped {summary.summary.skipped},
              not found {summary.summary.not_found}, errors {summary.summary.error}.
            </Alert>
          )}
          {err && <Alert severity="error">{err}</Alert>}
        </DialogContent>
        <DialogActions>
          {!running && !summary && (
            <>
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="contained" onClick={start}>Start</Button>
            </>
          )}
          {(running || summary) && (
            <Button onClick={() => { setOpen(false); setEvents([]); }} disabled={running}>Close</Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
}
```

- [ ] **Step 2: Verify it compiles and lints**

Run: `npm --prefix frontend run build && npm --prefix frontend run lint`
Expected: both succeed.

- [ ] **Step 3: Commit (after user review)**

```bash
git add frontend/src/components/settings/ChemicalsAdminSection.tsx
git commit -m "feat(gestis): admin backfill control in settings"
```

---

## Task 12: Frontend e2e tests

**Files:**
- Create: `frontend/e2e/gestis-link.spec.ts`

Same harness as the existing specs (real backend, admin login, GESTIS network intercepted — no live GESTIS calls). CAS numbers are fabricated per-run with a valid check digit so reruns never hit the group-level duplicate-CAS guard and never accidentally exist in the real GESTIS index (relevant because the server's create-hook resolves against the real index when it's warm).

- [ ] **Step 1: Write the spec**

Create `frontend/e2e/gestis-link.spec.ts`:

```typescript
import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@chaima.dev");
  await page.getByLabel("Password").fill("changeme");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL("/", { timeout: 15_000 });
}

// Fabricate a unique, check-digit-valid CAS per run: unique so reruns don't
// trip the duplicate-CAS guard, fabricated so it's never in the real GESTIS
// index (the backend create-hook resolves against the real index when warm).
function makeCas(): string {
  const first = String(Date.now()).slice(-7);
  const second = "13";
  const digits = (first + second).split("").reverse();
  let total = 0;
  digits.forEach((d, i) => {
    total += Number(d) * (i + 1);
  });
  return `${Number(first)}-${second}-${total % 10}`;
}

async function createChemical(page: Page, name: string, cas?: string) {
  await page.getByRole("button", { name: /new chemical/i }).click();
  await expect(page.getByLabel("Name")).toBeVisible();
  await page.getByLabel("Name").fill(name);
  if (cas) {
    await page.getByLabel(/cas number/i).fill(cas);
  }
  await page.getByRole("button", { name: /^create$/i }).click();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
}

test.describe("GESTIS deeplink", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("auto-resolve hit shows GESTIS link with correct href", async ({ page }) => {
    const name = `GESTIS Hit ${Date.now()}`;
    await page.route("**/gestis-resolve", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          zvg: "010420",
          url: "https://gestis-database.dguv.de/data?name=010420",
        }),
      });
    });

    await createChemical(page, name, makeCas());
    await page.getByText(name, { exact: true }).click();

    const link = page.getByRole("link", { name: /gestis 010420/i });
    await expect(link).toBeVisible({ timeout: 10_000 });
    await expect(link).toHaveAttribute(
      "href",
      "https://gestis-database.dguv.de/data?name=010420",
    );
  });

  test("resolve miss renders no GESTIS row", async ({ page }) => {
    const name = `GESTIS Miss ${Date.now()}`;
    let resolveCalls = 0;
    await page.route("**/gestis-resolve", async (route) => {
      resolveCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ zvg: null, url: null }),
      });
    });

    await createChemical(page, name, makeCas());
    await page.getByText(name, { exact: true }).click();

    // Info box is open (actions button visible), resolve was attempted,
    // but no GESTIS link is rendered.
    await expect(
      page.getByRole("button", { name: /chemical actions/i }),
    ).toBeVisible();
    await expect.poll(() => resolveCalls, { timeout: 10_000 }).toBeGreaterThan(0);
    await expect(page.getByRole("link", { name: /gestis/i })).not.toBeVisible();
  });

  test("stored zvg renders immediately without a resolve call", async ({ page }) => {
    const name = `GESTIS Stored ${Date.now()}`;
    let resolveCalls = 0;
    await page.route("**/gestis-resolve", async (route) => {
      resolveCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ zvg: null, url: null }),
      });
    });
    // Inject a stored zvg into the list response for our chemical.
    await page.route("**/api/v1/groups/*/chemicals?*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      for (const item of json.items ?? []) {
        if (item.name === name) item.zvg = "010420";
      }
      await route.fulfill({ response, json });
    });

    // No CAS: with zvg set the effect must not fire regardless.
    await createChemical(page, name);
    await page.getByText(name, { exact: true }).click();

    const link = page.getByRole("link", { name: /gestis 010420/i });
    await expect(link).toBeVisible({ timeout: 10_000 });
    expect(resolveCalls).toBe(0);
  });
});
```

- [ ] **Step 2: Run the e2e tests**

Prerequisite: the same running dev stack the existing specs use (check `frontend/playwright.config.ts` for a `webServer` block; if none, start backend + frontend the way you'd run any other spec in this repo before this step).

Run: from `frontend/`: `npx playwright test e2e/gestis-link.spec.ts`
Expected: 3 passed.

- [ ] **Step 3: Run the whole existing e2e suite to check for regressions**

Run: from `frontend/`: `npx playwright test`
Expected: all specs pass (same pass rate as before this feature).

- [ ] **Step 4: Commit (after user review)**

```bash
git add frontend/e2e/gestis-link.spec.ts
git commit -m "test(gestis): e2e coverage for deeplink resolve flows"
```

---

## Task 13: Docs + final verification

**Files:**
- Modify: `README.md` (config reference table)

- [ ] **Step 1: Document the new settings**

In `README.md`, find the configuration reference (the table listing `CHAIMA_`-prefixed variables, added in commit `72bf6df`/`d9c602d`) and add two rows, matching the existing table format exactly:

- `CHAIMA_GESTIS_API_BASE` — default `https://gestis-api.dguv.de/api` — Base URL of the GESTIS (DGUV) substance-database API.
- `CHAIMA_GESTIS_API_KEY` — default: GESTIS's public web-client key — Bearer token for the GESTIS API. The shipped default is the public key GESTIS's own web frontend serves in cleartext; override only if DGUV rotates it.

- [ ] **Step 2: Full backend suite**

Run: `uv run pytest tests/ -q`
Expected: all tests pass, 0 failures.

- [ ] **Step 3: Frontend build (required for bundled mode)**

Run: `npm --prefix frontend run build`
Expected: success. (The backend serves `src/chaima/static/` — without this build, manual testing in bundled mode shows the old UI; see project memory.)

- [ ] **Step 4: Manual smoke test (bundled mode)**

Run `uv run chaima run`, open the app, and check:
1. A chemical with a common CAS (e.g. ethanol 64-17-5) shows a `GESTIS 010420` link in the info-box Links section after opening it; clicking opens the GESTIS datasheet in a new tab.
2. Settings → Chemicals shows the "Resolve GESTIS links" control (as superuser) and a run completes with a summary line.
3. A chemical without a CAS shows no GESTIS row.

- [ ] **Step 5: Commit (after user review)**

```bash
git add README.md
git commit -m "docs(config): document GESTIS API settings"
```

---

## Self-review results (already applied)

- **Spec coverage:** All in-scope items map to tasks — column+migration (T2), service (T3), resolve endpoint (T4), lifespan pre-load (T8), config (T1), info-box link + auto-resolve (T9/T10), admin backfill (T7/T11), write-path hooks (T5/T6), all listed test categories (T2–T7 backend, T12 e2e). Out-of-scope items (DE variant, article content, not-found persistence) are not implemented anywhere.
- **Decision compliance:** (a) chemical-scoped POST ✓, (b) EN-only URL ✓, (c) no placeholder row ✓, (d) key in settings with public default ✓, (e) background pre-load + 24 h TTL + lazy refresh ✓, (f) no miss persistence ✓, (g) `zfill(6)` at index build ✓, (h) resolve never 5xxs ✓, (i) `get_zvg_if_warm` on all three write paths ✓, (j) CAS change invalidates ✓ (plus CAS removal clears), (k) backfill unthrottled — implemented as one up-front `load_index()` + warm lookups, equivalent to "get_zvg may trigger the one download" but lets the generator distinguish `error` from `not_found`.
- **Type consistency:** `get_zvg`/`get_zvg_if_warm`/`gestis_url`/`load_index`/`preload_index` names used identically across service, router, enrich, and tests; `GestisResolveResult {zvg, url}` matches frontend `GestisResolveResult`; SSE statuses `resolved/skipped/not_found/error` identical in generator, tests, and `GestisBackfillEvent`.
- **Deviation from spec (intentional):** Frontend cache update uses `setQueryData`/`setQueriesData` instead of invalidation — the spec offers both ("update the chemical in the React Query cache (or invalidate)"); direct cache writes avoid a refetch and make the e2e tests deterministic without backend persistence.
