# src/chaima/services/pubchem.py
"""Async client for PubChem PUG REST.

Exposes a single public ``lookup`` coroutine that resolves a name or CAS
to a normalized ``PubChemLookupResult``. Errors are mapped to two domain
exceptions — ``PubChemNotFound`` for 404 CID lookups and
``PubChemUpstreamError`` for everything else (non-2xx, timeouts, network).
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from typing import Any
from urllib.parse import quote

import httpx

from chaima.schemas.pubchem import PubChemGHSHit, PubChemLookupResult

logger = logging.getLogger(__name__)

_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PUG_VIEW_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
_PER_REQUEST_TIMEOUT = 8.0
_TOTAL_TIMEOUT = 15.0
_GHS_TIMEOUT = 30.0
_SYNONYM_CAP = 20
_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
_HAZARD_CODE_RE = re.compile(r"^(H\d{3}|EUH\d{3})\b")
_PICTOGRAM_RE = re.compile(r"GHS\d{2}")

# Simple TTL cache: {key: (result, expiry_timestamp)}
_CACHE_TTL = 86400  # 24 hours — PubChem data barely changes
_cache: dict[str, tuple[object, float]] = {}


def _cache_get(key: str) -> object | None:
    import time as _time
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expiry = entry
    if _time.time() > expiry:
        del _cache[key]
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    import time as _time
    _cache[key] = (value, _time.time() + _CACHE_TTL)


class PubChemNotFound(Exception):
    """Raised when the initial CID lookup returns 404."""


class PubChemUpstreamError(Exception):
    """Raised for non-404 PubChem failures (5xx, timeouts, network)."""


async def lookup(query: str) -> PubChemLookupResult:
    """Resolve a name or CAS to a normalized PubChem result (fast, no GHS).

    GHS classification is intentionally excluded — it takes 10-15 seconds
    on PubChem's side.  Use ``lookup_ghs`` separately.

    Raises
    ------
    PubChemNotFound
        If PubChem does not recognize the query.
    PubChemUpstreamError
        For any other upstream failure (5xx, timeout, network).
    """
    q = query.strip().lower()
    cached = _cache_get(f"lookup:{q}")
    if cached is not None:
        return cached  # type: ignore[return-value]

    timeout = httpx.Timeout(_TOTAL_TIMEOUT, connect=_PER_REQUEST_TIMEOUT)

    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=timeout) as client:
        cid = await _resolve_cid(client, q)
        props, synonyms = await asyncio.gather(
            _fetch_properties(client, cid),
            _fetch_synonyms(client, cid),
        )

    cas = _pick_cas(synonyms)
    common_name = _pick_common_name(synonyms)
    iupac = props.get("IUPACName")
    name = common_name or iupac or query.strip()
    result = PubChemLookupResult(
        cid=str(cid),
        name=name,
        cas=cas,
        molar_mass=_to_float(props.get("MolecularWeight")),
        smiles=props.get("SMILES"),
        synonyms=synonyms[:_SYNONYM_CAP],
        ghs_codes=[],
    )
    _cache_set(f"lookup:{q}", result)
    return result


async def lookup_ghs(cid: str) -> list[PubChemGHSHit]:
    """Fetch GHS hazard codes for a CID (the slow part).

    Returns cached results when available. Returns an empty list on
    failure so callers don't need to handle errors.
    """
    cache_key = f"ghs:{cid}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    timeout = httpx.Timeout(_GHS_TIMEOUT, connect=_PER_REQUEST_TIMEOUT)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            ghs_raw = await _fetch_ghs(client, int(cid))
    except (PubChemUpstreamError, Exception) as exc:
        logger.warning("GHS fetch failed for CID %s: %s", cid, exc)
        return []

    result = parse_ghs_classification(ghs_raw)
    _cache_set(cache_key, result)
    return result


def _safe_json(resp: httpx.Response) -> Any:
    """Decode a PubChem JSON response that may contain non-UTF-8 bytes.

    PubChem occasionally returns synonyms or descriptions containing legacy
    latin-1 bytes (e.g. ``0xae`` for ``®``) inside an ``application/json``
    body. Fall back to lenient decoding so a single bad byte doesn't 500
    the whole lookup.
    """
    import json as _json
    try:
        return resp.json()
    except (UnicodeDecodeError, _json.JSONDecodeError):
        text = resp.content.decode("utf-8", errors="replace")
        return _json.loads(text)


async def _resolve_cid(client: httpx.AsyncClient, query: str) -> int:
    path = f"/compound/name/{quote(query, safe='')}/cids/JSON"
    try:
        resp = await client.get(path)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise PubChemUpstreamError(str(exc)) from exc
    if resp.status_code == 404:
        raise PubChemNotFound(query)
    if resp.status_code >= 400:
        raise PubChemUpstreamError(f"CID lookup {resp.status_code}")
    data = _safe_json(resp)
    cids = (data.get("IdentifierList") or {}).get("CID") or []
    if not cids:
        raise PubChemNotFound(query)
    return int(cids[0])


async def _fetch_properties(
    client: httpx.AsyncClient, cid: int
) -> dict[str, Any]:
    path = (
        f"/compound/cid/{cid}/property/"
        f"MolecularWeight,SMILES,IUPACName/JSON"
    )
    try:
        resp = await client.get(path)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise PubChemUpstreamError(str(exc)) from exc
    if resp.status_code >= 400:
        raise PubChemUpstreamError(f"properties {resp.status_code}")
    data = _safe_json(resp)
    props_list = (data.get("PropertyTable") or {}).get("Properties") or []
    return props_list[0] if props_list else {}


async def _fetch_synonyms(client: httpx.AsyncClient, cid: int) -> list[str]:
    path = f"/compound/cid/{cid}/synonyms/JSON"
    try:
        resp = await client.get(path)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise PubChemUpstreamError(str(exc)) from exc
    if resp.status_code >= 400:
        raise PubChemUpstreamError(f"synonyms {resp.status_code}")
    data = _safe_json(resp)
    info_list = (data.get("InformationList") or {}).get("Information") or []
    if not info_list:
        return []
    return list(info_list[0].get("Synonym") or [])


async def _fetch_ghs(client: httpx.AsyncClient, cid: int) -> dict[str, Any]:
    # PubChem's PUG-REST classification endpoint returns the entire Compound
    # TOC tree (tens of MB) and ignores classification_type filters, so we
    # use PUG-View and ask only for the GHS Classification heading.
    url = f"{_PUG_VIEW_URL}/data/compound/{cid}/JSON"
    try:
        resp = await client.get(url, params={"heading": "GHS Classification"})
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise PubChemUpstreamError(str(exc)) from exc
    # 404 here just means "no GHS data" — not fatal.
    if resp.status_code == 404:
        return {}
    if resp.status_code >= 400:
        raise PubChemUpstreamError(f"ghs {resp.status_code}")
    return _safe_json(resp)


def _pick_cas(synonyms: list[str]) -> str | None:
    for syn in synonyms:
        if _CAS_RE.match(syn.strip()):
            return syn.strip()
    return None


def _pick_common_name(synonyms: list[str]) -> str | None:
    """Return the first synonym that looks like a common name.

    Skips CAS numbers and strings that are obviously IUPAC-style
    (contain commas or start with a digit). The first remaining
    synonym from PubChem is almost always the common/trivial name.
    Result is title-cased so "acetone" becomes "Acetone".
    """
    for syn in synonyms:
        s = syn.strip()
        if not s:
            continue
        if _CAS_RE.match(s):
            continue
        # Skip entries that start with a digit (usually numbered systematic names)
        if s[0].isdigit():
            continue
        # Capitalize first letter, leave the rest as-is so e.g.
        # "tert-Butanol" or "NaCl" aren't mangled.
        return s[0].upper() + s[1:]
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_ghs_classification(data: dict[str, Any]) -> list[PubChemGHSHit]:
    """Extract H-code hits from a PubChem PUG-View GHS Classification body.

    PUG-View nests the data as ``Record.Section[].Section[].Section[]`` and
    aggregates many sources (ECHA, registrant filings, EPA, etc.) into a
    single ``GHS Classification`` section. Each source occupies several
    ``Information`` items sharing the same ``ReferenceNumber`` — typically
    one each for ``Signal``, ``Pictogram(s)``, and ``GHS Hazard Statements``.

    To suppress minority-source over-flagging, codes are kept only when
    they appear in a strict majority of source buckets. When fewer than
    three buckets are present the sample is too small to vote, so every
    observed code is kept.

    Parameters
    ----------
    data : dict
        The parsed JSON body from
        ``/rest/pug_view/data/compound/{cid}/JSON?heading=GHS+Classification``.

    Returns
    -------
    list[PubChemGHSHit]
        One hit per surviving H-code. Empty list if the body lacks a GHS
        Classification section or carries no hazard statements.
    """
    sections = list(_iter_ghs_sections(data))
    if not sections:
        return []

    code_counts: dict[str, int] = defaultdict(int)
    first_hit: dict[str, PubChemGHSHit] = {}
    bucket_count = 0

    for section in sections:
        buckets: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for info in section.get("Information") or []:
            buckets[info.get("ReferenceNumber")].append(info)

        for items in buckets.values():
            bucket_count += 1
            signal_word: str | None = None
            pictogram: str | None = None
            statements: list[PubChemGHSHit] = []
            for info in items:
                name = info.get("Name")
                value = info.get("Value") or {}
                if name == "Signal":
                    for s in _value_strings(value):
                        if s.strip():
                            signal_word = signal_word or s.strip()
                elif name == "Pictogram(s)":
                    for code in _pictogram_codes(value):
                        pictogram = pictogram or code
                elif name == "GHS Hazard Statements":
                    for s in _value_strings(value):
                        hit = _parse_hazard_statement(s)
                        if hit.code:
                            statements.append(hit)

            seen_in_bucket: set[str] = set()
            for hit in statements:
                if hit.code in seen_in_bucket:
                    continue
                seen_in_bucket.add(hit.code)
                code_counts[hit.code] += 1
                if hit.code not in first_hit:
                    if hit.signal_word is None:
                        hit.signal_word = signal_word
                    if hit.pictogram is None:
                        hit.pictogram = pictogram
                    first_hit[hit.code] = hit

    if bucket_count == 0:
        return []
    threshold = 1 if bucket_count < 3 else bucket_count // 2 + 1
    kept = [
        first_hit[code]
        for code, count in code_counts.items()
        if count >= threshold
    ]
    # Sort by support descending, then code ascending for deterministic order.
    kept.sort(key=lambda h: (-code_counts[h.code], h.code))
    return kept


def _iter_ghs_sections(node: Any):
    """Yield every ``Section`` dict whose ``TOCHeading`` is GHS Classification.

    PUG-View documents have a top-level ``Record.Section[]`` containing
    ``Safety and Hazards`` → ``Hazards Identification`` → ``GHS
    Classification``. We walk the tree generically so the parser also
    works on minimal fixtures or future shape tweaks.
    """
    if not isinstance(node, dict):
        return
    if node.get("TOCHeading") == "GHS Classification":
        yield node
    for child in node.get("Section") or []:
        yield from _iter_ghs_sections(child)
    record = node.get("Record")
    if isinstance(record, dict):
        yield from _iter_ghs_sections(record)


def _value_strings(value: dict[str, Any]) -> list[str]:
    """Return every ``String`` from a PUG-View ``Value.StringWithMarkup``."""
    out: list[str] = []
    for entry in value.get("StringWithMarkup") or []:
        s = (entry or {}).get("String")
        if isinstance(s, str):
            out.append(s)
    return out


def _pictogram_codes(value: dict[str, Any]) -> list[str]:
    """Return GHSxx pictogram codes parsed from Markup URLs / Extras.

    PUG-View renders pictograms as inline icons, with the GHS code embedded
    in the icon URL (``.../images/ghs/GHS02.svg``) and sometimes mirrored
    in the ``Extra`` label.
    """
    codes: list[str] = []
    for entry in value.get("StringWithMarkup") or []:
        for markup in (entry or {}).get("Markup") or []:
            for field in (markup.get("URL"), markup.get("Extra")):
                if not isinstance(field, str):
                    continue
                m = _PICTOGRAM_RE.search(field)
                if m and m.group(0) not in codes:
                    codes.append(m.group(0))
    return codes


async def fetch_structure_image(cid: str) -> bytes | None:
    """Download the 2D structure PNG for a CID from PubChem.

    Returns the raw PNG bytes, or ``None`` on any failure (timeout, 404,
    network error). Image fetch is best-effort — a missing image must
    never block chemical creation.
    """
    timeout = httpx.Timeout(_TOTAL_TIMEOUT, connect=_PER_REQUEST_TIMEOUT)
    url = f"{_BASE_URL}/compound/cid/{cid}/PNG"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.warning("PubChem image fetch failed for CID %s: %s", cid, exc)
        return None
    if resp.status_code != 200:
        logger.warning(
            "PubChem image fetch returned %s for CID %s",
            resp.status_code,
            cid,
        )
        return None
    return resp.content


def _parse_hazard_statement(text: str) -> PubChemGHSHit:
    """Parse one ``H-code: description [Signal ...]`` line."""
    code = ""
    description = text
    local_signal: str | None = None

    match = _HAZARD_CODE_RE.match(text)
    if match:
        code = match.group(1)
        remainder = text[match.end():].lstrip(": ").strip()
        # Split off a trailing "[Danger ...]" annotation if present.
        if "[" in remainder and remainder.endswith("]"):
            description, _, annotation = remainder.rpartition(" [")
            annotation = annotation.rstrip("]")
            if annotation.startswith("Danger"):
                local_signal = "Danger"
            elif annotation.startswith("Warning"):
                local_signal = "Warning"
        else:
            description = remainder

    return PubChemGHSHit(
        code=code,
        description=description,
        signal_word=local_signal,
        pictogram=None,
    )


def parse_chemical_vendors(data: dict[str, Any]) -> list["PubChemVendor"]:
    """Extract vendor entries from a PubChem PUG-View Chemical Vendors body.

    Returns a deduplicated list of vendors keyed on URL. Empty list if the
    body lacks the section (or PubChem returned 404).
    """
    from chaima.schemas.pubchem import PubChemVendor

    sections = list(_iter_sections(data, "Chemical Vendors"))
    seen_urls: set[str] = set()
    vendors: list[PubChemVendor] = []

    for section in sections:
        for info in section.get("Information") or []:
            value = info.get("Value") or {}
            for entry in value.get("StringWithMarkup") or []:
                name = (entry.get("String") or "").strip()
                url: str | None = None
                for markup in entry.get("Markup") or []:
                    candidate = markup.get("URL")
                    if isinstance(candidate, str) and candidate.startswith("http"):
                        url = candidate
                        break
                if not name or not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                vendors.append(PubChemVendor(name=name, url=url))
    return vendors


def _iter_sections(node: Any, heading: str):
    """Yield every Section dict whose TOCHeading matches the given string."""
    if not isinstance(node, dict):
        return
    if node.get("TOCHeading") == heading:
        yield node
    for child in node.get("Section") or []:
        yield from _iter_sections(child, heading)
    record = node.get("Record")
    if isinstance(record, dict):
        yield from _iter_sections(record, heading)


async def lookup_vendors(cid: str) -> list["PubChemVendor"]:
    """Fetch PubChem 'Chemical Vendors' for a CID. Cached 24h.

    Returns an empty list on any upstream failure — never raises.
    """
    from chaima.schemas.pubchem import PubChemVendor  # noqa: F401

    cache_key = f"vendors:{cid}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    url = f"{_PUG_VIEW_URL}/data/compound/{cid}/JSON"
    timeout = httpx.Timeout(_TOTAL_TIMEOUT, connect=_PER_REQUEST_TIMEOUT)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params={"heading": "Chemical Vendors"})
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.warning("PubChem vendors fetch failed for CID %s: %s", cid, exc)
        return []
    if resp.status_code == 404:
        result: list = []
    elif resp.status_code >= 400:
        logger.warning("PubChem vendors returned %s for CID %s", resp.status_code, cid)
        return []
    else:
        result = parse_chemical_vendors(_safe_json(resp))
    _cache_set(cache_key, result)
    return result
