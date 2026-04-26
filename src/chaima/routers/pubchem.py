# src/chaima/routers/pubchem.py
"""PubChem lookup endpoint.

Wraps ``chaima.services.pubchem.lookup`` behind a simple authenticated
GET. The response is public external data, so auth is only required to
keep the endpoint from being used as an open proxy to PubChem.
"""
from fastapi import APIRouter, HTTPException, Query

from chaima.dependencies import CurrentUserDep
from chaima.schemas.pubchem import PubChemGHSHit, PubChemLookupResult, PubChemVendorList
from chaima.services import pubchem as pubchem_service
from chaima.services.pubchem import PubChemNotFound, PubChemUpstreamError

router = APIRouter(prefix="/api/v1/pubchem", tags=["pubchem"])


@router.get("/lookup", response_model=PubChemLookupResult)
async def lookup_pubchem(
    user: CurrentUserDep,
    q: str = Query(..., min_length=1, max_length=200),
) -> PubChemLookupResult:
    """Resolve a chemical name or CAS number via PubChem PUG REST.

    Returns name, CAS, molar mass, SMILES, and synonyms quickly.
    GHS codes are excluded — use ``/ghs`` to fetch them separately.
    """
    try:
        return await pubchem_service.lookup(q)
    except PubChemNotFound as exc:
        raise HTTPException(status_code=404, detail="No PubChem match") from exc
    except PubChemUpstreamError as exc:
        raise HTTPException(
            status_code=502, detail="PubChem unavailable"
        ) from exc


@router.get("/ghs", response_model=list[PubChemGHSHit])
async def lookup_ghs(
    user: CurrentUserDep,
    cid: str = Query(..., min_length=1, max_length=20),
) -> list[PubChemGHSHit]:
    """Fetch GHS hazard codes for a PubChem CID.

    This endpoint is intentionally separate because the PubChem
    classification API can take 10-15 seconds to respond.
    """
    return await pubchem_service.lookup_ghs(cid)


@router.get("/vendors/{cid}", response_model=PubChemVendorList)
async def get_pubchem_vendors(cid: str) -> PubChemVendorList:
    """PubChem 'Chemical Vendors' for a CID. Returns empty list on upstream failure."""
    vendors = await pubchem_service.lookup_vendors(cid)
    return PubChemVendorList(cid=cid, vendors=vendors)
