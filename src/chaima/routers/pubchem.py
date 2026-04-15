# src/chaima/routers/pubchem.py
"""PubChem lookup endpoint.

Wraps ``chaima.services.pubchem.lookup`` behind a simple authenticated
GET. The response is public external data, so auth is only required to
keep the endpoint from being used as an open proxy to PubChem.
"""
from fastapi import APIRouter, HTTPException, Query

from chaima.dependencies import CurrentUserDep
from chaima.schemas.pubchem import PubChemLookupResult
from chaima.services import pubchem as pubchem_service
from chaima.services.pubchem import PubChemNotFound, PubChemUpstreamError

router = APIRouter(prefix="/api/v1/pubchem", tags=["pubchem"])


@router.get("/lookup", response_model=PubChemLookupResult)
async def lookup_pubchem(
    user: CurrentUserDep,
    q: str = Query(..., min_length=1, max_length=200),
) -> PubChemLookupResult:
    """Resolve a chemical name or CAS number via PubChem PUG REST."""
    try:
        return await pubchem_service.lookup(q)
    except PubChemNotFound as exc:
        raise HTTPException(status_code=404, detail="No PubChem match") from exc
    except PubChemUpstreamError as exc:
        raise HTTPException(
            status_code=502, detail="PubChem unavailable"
        ) from exc
