import asyncio
from typing import AsyncGenerator, Literal
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical, ChemicalSynonym
from chaima.models.ghs import ChemicalGHS, GHSCode
from chaima.services.chemicals import (
    _resolve_ghs_codes_by_code,
    replace_ghs_codes,
    replace_synonyms,
)
from chaima.services.pubchem import (
    PubChemNotFound,
    lookup as pubchem_lookup,
    lookup_ghs as pubchem_lookup_ghs,
    lookup_synonyms as pubchem_lookup_synonyms,
)
from chaima.services.events import _persist_event
from chaima.models.analytics import EventType


def _merge_synonyms(existing: list[str], incoming: list[str]) -> list[str]:
    """Case-insensitive union preserving existing order; mirrors frontend logic."""
    seen = {s.lower() for s in existing}
    merged = list(existing)
    for s in incoming:
        if s.lower() not in seen:
            seen.add(s.lower())
            merged.append(s)
    return merged

EnrichStatus = Literal["enriched", "skipped", "not_found", "error"]
RefetchGHSStatus = Literal["updated", "unchanged", "skipped", "error"]


async def enrich_one(session: AsyncSession, chemical: Chemical) -> EnrichStatus:
    if chemical.cid:
        return "skipped"

    query = chemical.cas or chemical.name
    if not query:
        return "skipped"

    success = False
    cas_resolved = False
    try:
        result = await pubchem_lookup(query)
        success = True
    except PubChemNotFound:
        await _persist_event(
            user_id=None, group_id=chemical.group_id,
            type=EventType.PUBCHEM_FETCH,
            payload={"success": False, "cas_resolved": False},
        )
        return "not_found"
    except Exception:
        await _persist_event(
            user_id=None, group_id=chemical.group_id,
            type=EventType.PUBCHEM_FETCH,
            payload={"success": False, "cas_resolved": False},
        )
        return "error"

    if result.cid and not chemical.cid:
        chemical.cid = str(result.cid)
    if result.cas and not chemical.cas:
        chemical.cas = result.cas
        cas_resolved = True
    elif result.cas:
        cas_resolved = True
    if result.smiles and not chemical.smiles:
        chemical.smiles = result.smiles
    if result.molar_mass is not None and chemical.molar_mass is None:
        chemical.molar_mass = result.molar_mass
    session.add(chemical)
    await session.flush()

    await _persist_event(
        user_id=None, group_id=chemical.group_id,
        type=EventType.PUBCHEM_FETCH,
        payload={"success": success, "cas_resolved": cas_resolved},
    )
    return "enriched"


async def enrich_group_chemicals(
    session: AsyncSession,
    group_id: UUID,
    chemical_ids: list[UUID] | None,
) -> AsyncGenerator[dict, None]:
    stmt = select(Chemical).where(Chemical.group_id == group_id)
    if chemical_ids is not None:
        stmt = stmt.where(Chemical.id.in_(chemical_ids))
    else:
        stmt = stmt.where(Chemical.cid.is_(None))
    result = await session.exec(stmt)
    chemicals = list(result.all())

    counts: dict[str, int] = {"enriched": 0, "skipped": 0, "not_found": 0, "error": 0}
    for chem in chemicals:
        status = await enrich_one(session, chem)
        counts[status] += 1
        yield {"id": str(chem.id), "name": chem.name, "status": status}
        await session.commit()
        await asyncio.sleep(0.25)

    yield {"summary": counts}


async def refetch_ghs_one(
    session: AsyncSession, chemical: Chemical
) -> RefetchGHSStatus:
    """Pull GHS hazards and synonyms from PubChem and merge into the chemical.

    Both sets are merged with what the chemical already has (case-insensitive
    for synonyms, code equality for GHS); manual additions are preserved.
    Never raises — upstream errors map to ``"error"``.
    """
    if not chemical.cid:
        return "skipped"

    try:
        hits, new_synonyms = await asyncio.gather(
            pubchem_lookup_ghs(chemical.cid),
            pubchem_lookup_synonyms(chemical.cid),
        )
    except Exception:
        return "error"

    changed = False

    # ---- GHS merge -------------------------------------------------------
    new_codes = [hit.code for hit in hits if hit.code]
    if new_codes:
        existing_link_ids = (
            await session.exec(
                select(ChemicalGHS.ghs_id).where(
                    ChemicalGHS.chemical_id == chemical.id
                )
            )
        ).all()
        existing_codes_result = await session.exec(
            select(GHSCode.code).where(GHSCode.id.in_(set(existing_link_ids)))  # type: ignore[union-attr]
        )
        existing_codes = set(existing_codes_result.all())
        merged_codes = existing_codes | set(new_codes)
        if merged_codes != existing_codes:
            merged_ids = await _resolve_ghs_codes_by_code(session, list(merged_codes))
            await replace_ghs_codes(session, chemical.id, merged_ids)
            changed = True

    # ---- Synonym merge ---------------------------------------------------
    if new_synonyms:
        existing_syns_result = await session.exec(
            select(ChemicalSynonym).where(ChemicalSynonym.chemical_id == chemical.id)
        )
        existing = list(existing_syns_result.all())
        existing_names = [s.name for s in existing]
        merged_names = _merge_synonyms(existing_names, new_synonyms)
        if merged_names != existing_names:
            await replace_synonyms(
                session,
                chemical.id,
                [{"name": n, "category": None} for n in merged_names],
            )
            changed = True

    return "updated" if changed else "unchanged"


async def refetch_group_ghs(
    session: AsyncSession,
    group_id: UUID,
    chemical_ids: list[UUID] | None,
) -> AsyncGenerator[dict, None]:
    """Yield SSE-style events while refetching GHS for chemicals in a group.

    Defaults to every chemical in the group that has a ``cid``. Per-chemical
    timing is dominated by PubChem's GHS endpoint (~10–15s).
    """
    stmt = select(Chemical).where(Chemical.group_id == group_id)
    if chemical_ids is not None:
        stmt = stmt.where(Chemical.id.in_(chemical_ids))
    else:
        stmt = stmt.where(Chemical.cid.is_not(None))
    result = await session.exec(stmt)
    chemicals = list(result.all())

    counts: dict[str, int] = {"updated": 0, "unchanged": 0, "skipped": 0, "error": 0}
    for chem in chemicals:
        status = await refetch_ghs_one(session, chem)
        counts[status] += 1
        yield {"id": str(chem.id), "name": chem.name, "status": status}
        await session.commit()
        await asyncio.sleep(0.25)

    yield {"summary": counts}
