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
