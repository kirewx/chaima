# src/chaima/routers/ghs.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import CurrentUserDep, SessionDep, SuperuserDep
from chaima.schemas.ghs import GHSCodeCreate, GHSCodeRead, GHSCodeUpdate
from chaima.schemas.pagination import PaginatedResponse
from chaima.services import ghs as ghs_service

router = APIRouter(prefix="/api/v1/ghs-codes", tags=["ghs-codes"])


@router.get("", response_model=PaginatedResponse[GHSCodeRead])
async def list_ghs_codes(
    session: SessionDep,
    user: CurrentUserDep,
    search: str | None = Query(None),
    sort: str = Query("code"),
    order: str = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[GHSCodeRead]:
    """List all GHS codes. Any authenticated user.

    Parameters
    ----------
    session : AsyncSession
        The database session (injected).
    user : User
        The authenticated user (injected).
    search : str or None, optional
        Filter by partial match on code or description.
    sort : str, optional
        Field to sort by. Defaults to ``"code"``.
    order : str, optional
        Sort direction, ``"asc"`` or ``"desc"``. Defaults to ``"asc"``.
    offset : int, optional
        Number of records to skip. Defaults to 0.
    limit : int, optional
        Maximum records to return (1–100). Defaults to 20.

    Returns
    -------
    PaginatedResponse[GHSCodeRead]
        Paginated list of GHS codes.
    """
    items, total = await ghs_service.list_ghs_codes(
        session, search=search, sort=sort, order=order, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[GHSCodeRead.model_validate(i, from_attributes=True) for i in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{ghs_id}", response_model=GHSCodeRead)
async def get_ghs_code(
    ghs_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
) -> GHSCodeRead:
    """Get a GHS code by ID. Any authenticated user.

    Parameters
    ----------
    ghs_id : UUID
        The ID of the GHS code to retrieve.
    session : AsyncSession
        The database session (injected).
    user : User
        The authenticated user (injected).

    Returns
    -------
    GHSCodeRead
        The requested GHS code.

    Raises
    ------
    HTTPException
        404 if the GHS code does not exist.
    """
    ghs = await ghs_service.get_ghs_code(session, ghs_id)
    if ghs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GHS code not found")
    return GHSCodeRead.model_validate(ghs, from_attributes=True)


@router.post("", response_model=GHSCodeRead, status_code=status.HTTP_201_CREATED)
async def create_ghs_code(
    body: GHSCodeCreate,
    session: SessionDep,
    user: SuperuserDep,
) -> GHSCodeRead:
    """Create a GHS code. Superuser only.

    Parameters
    ----------
    body : GHSCodeCreate
        The GHS code data.
    session : AsyncSession
        The database session (injected).
    user : User
        The authenticated superuser (injected).

    Returns
    -------
    GHSCodeRead
        The newly created GHS code.

    Raises
    ------
    HTTPException
        409 if a GHS code with the same code already exists.
    """
    try:
        ghs = await ghs_service.create_ghs_code(
            session,
            code=body.code,
            description=body.description,
            pictogram=body.pictogram,
            signal_word=body.signal_word,
        )
    except ghs_service.DuplicateCodeError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"GHS code {body.code} already exists",
        )
    await session.commit()
    return GHSCodeRead.model_validate(ghs, from_attributes=True)


@router.patch("/{ghs_id}", response_model=GHSCodeRead)
async def update_ghs_code(
    ghs_id: UUID,
    body: GHSCodeUpdate,
    session: SessionDep,
    user: SuperuserDep,
) -> GHSCodeRead:
    """Update a GHS code. Superuser only.

    Parameters
    ----------
    ghs_id : UUID
        The ID of the GHS code to update.
    body : GHSCodeUpdate
        Fields to update.
    session : AsyncSession
        The database session (injected).
    user : User
        The authenticated superuser (injected).

    Returns
    -------
    GHSCodeRead
        The updated GHS code.

    Raises
    ------
    HTTPException
        404 if the GHS code does not exist.
    """
    ghs = await ghs_service.get_ghs_code(session, ghs_id)
    if ghs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GHS code not found")
    updated = await ghs_service.update_ghs_code(
        session, ghs, description=body.description, pictogram=body.pictogram, signal_word=body.signal_word
    )
    await session.commit()
    return GHSCodeRead.model_validate(updated, from_attributes=True)
