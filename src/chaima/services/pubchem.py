# src/chaima/services/pubchem.py
"""Async client for PubChem PUG REST.

Exposes a single public ``lookup`` coroutine that resolves a name or CAS
to a normalized ``PubChemLookupResult``. Errors are mapped to two domain
exceptions — ``PubChemNotFound`` for 404 CID lookups and
``PubChemUpstreamError`` for everything else (non-2xx, timeouts, network).
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from chaima.schemas.pubchem import PubChemGHSHit, PubChemLookupResult

logger = logging.getLogger(__name__)

_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PER_REQUEST_TIMEOUT = 8.0
_TOTAL_TIMEOUT = 15.0
_SYNONYM_CAP = 20
_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
_HAZARD_CODE_RE = re.compile(r"^(H\d{3}|EUH\d{3})\b")


class PubChemNotFound(Exception):
    """Raised when the initial CID lookup returns 404."""


class PubChemUpstreamError(Exception):
    """Raised for non-404 PubChem failures (5xx, timeouts, network)."""


async def lookup(query: str) -> PubChemLookupResult:
    """Resolve a name or CAS to a normalized PubChem result.

    Parameters
    ----------
    query : str
        Chemical name, synonym, or CAS number.

    Returns
    -------
    PubChemLookupResult
        Normalized result payload.

    Raises
    ------
    PubChemNotFound
        If PubChem does not recognize the query.
    PubChemUpstreamError
        For any other upstream failure (5xx, timeout, network).
    """
    q = query.strip()
    timeout = httpx.Timeout(_TOTAL_TIMEOUT, connect=_PER_REQUEST_TIMEOUT)

    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=timeout) as client:
        cid = await _resolve_cid(client, q)
        props = await _fetch_properties(client, cid)
        synonyms = await _fetch_synonyms(client, cid)
        ghs_raw = await _fetch_ghs(client, cid)

    cas = _pick_cas(synonyms)
    return PubChemLookupResult(
        cid=str(cid),
        name=props.get("IUPACName") or q,
        cas=cas,
        molar_mass=_to_float(props.get("MolecularWeight")),
        smiles=props.get("CanonicalSMILES"),
        synonyms=synonyms[:_SYNONYM_CAP],
        ghs_codes=parse_ghs_classification(ghs_raw),
    )


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
    data = resp.json()
    cids = (data.get("IdentifierList") or {}).get("CID") or []
    if not cids:
        raise PubChemNotFound(query)
    return int(cids[0])


async def _fetch_properties(
    client: httpx.AsyncClient, cid: int
) -> dict[str, Any]:
    path = (
        f"/compound/cid/{cid}/property/"
        f"MolecularWeight,CanonicalSMILES,IUPACName/JSON"
    )
    try:
        resp = await client.get(path)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise PubChemUpstreamError(str(exc)) from exc
    if resp.status_code >= 400:
        raise PubChemUpstreamError(f"properties {resp.status_code}")
    data = resp.json()
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
    data = resp.json()
    info_list = (data.get("InformationList") or {}).get("Information") or []
    if not info_list:
        return []
    return list(info_list[0].get("Synonym") or [])


async def _fetch_ghs(client: httpx.AsyncClient, cid: int) -> dict[str, Any]:
    path = f"/compound/cid/{cid}/classification/JSON"
    try:
        resp = await client.get(
            path, params={"classification_type": "ghs"}
        )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise PubChemUpstreamError(str(exc)) from exc
    # 404 here just means "no GHS data" — not fatal.
    if resp.status_code == 404:
        return {}
    if resp.status_code >= 400:
        raise PubChemUpstreamError(f"ghs {resp.status_code}")
    return resp.json()


def _pick_cas(synonyms: list[str]) -> str | None:
    for syn in synonyms:
        if _CAS_RE.match(syn.strip()):
            return syn.strip()
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_ghs_classification(data: dict[str, Any]) -> list[PubChemGHSHit]:
    """Extract H-code hits from a PubChem GHS classification response.

    PubChem serializes GHS data as a flat ``Hierarchy.Node[]`` list where
    each node has an ``Information`` dict. Signal word and pictogram
    apply to the whole compound; hazard-statement nodes carry the code
    and description in one ``Description`` string shaped like
    ``"H225: Highly flammable liquid and vapour [Danger ...]"``.

    Parameters
    ----------
    data : dict
        The parsed JSON body from ``/classification/JSON``.

    Returns
    -------
    list[PubChemGHSHit]
        One hit per hazard statement. Empty list if the shape is
        missing, malformed, or has no hazard statements.
    """
    hierarchies = (data.get("Hierarchies") or {}).get("Hierarchy") or []
    if not hierarchies:
        return []

    signal_word: str | None = None
    pictogram: str | None = None
    hits: list[PubChemGHSHit] = []

    # A compound usually has one hierarchy; walk all to be safe.
    for hierarchy in hierarchies:
        nodes = hierarchy.get("Node") or []
        for node in nodes:
            info = node.get("Information") or {}
            name = info.get("Name")
            desc = info.get("Description") or ""
            if name == "Signal":
                signal_word = desc.strip() or signal_word
            elif name == "Pictogram" and pictogram is None:
                # Prefer the first pictogram code encountered.
                match = re.search(r"GHS\d{2}", desc)
                if match:
                    pictogram = match.group(0)
            elif name == "GHS Hazard Statements":
                hits.append(_parse_hazard_statement(desc))

    # Back-fill per-statement signal word / pictogram from the compound
    # defaults when the hazard statement didn't carry its own.
    for h in hits:
        if h.signal_word is None:
            h.signal_word = signal_word
        if h.pictogram is None:
            h.pictogram = pictogram

    # Drop any entries where we couldn't parse a code.
    return [h for h in hits if h.code]


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
