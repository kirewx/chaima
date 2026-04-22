import asyncio
from typing import AsyncGenerator, Literal
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.services.pubchem import PubChemNotFound, lookup as pubchem_lookup

EnrichStatus = Literal["enriched", "skipped", "not_found", "error"]


async def enrich_one(session: AsyncSession, chemical: Chemical) -> EnrichStatus:
    if chemical.cid:
        return "skipped"

    query = chemical.cas or chemical.name
    if not query:
        return "skipped"
    try:
        result = await pubchem_lookup(query)
    except PubChemNotFound:
        return "not_found"
    except Exception:
        return "error"

    if result.cid and not chemical.cid:
        chemical.cid = str(result.cid)
    if result.cas and not chemical.cas:
        chemical.cas = result.cas
    if result.smiles and not chemical.smiles:
        chemical.smiles = result.smiles
    if result.molar_mass is not None and chemical.molar_mass is None:
        chemical.molar_mass = result.molar_mass
    session.add(chemical)
    await session.flush()
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
