from typing import Literal

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
