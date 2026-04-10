# src/chaima/routers/suppliers.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import GroupMemberDep, SessionDep
from chaima.schemas.pagination import PaginatedResponse
from chaima.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from chaima.services import suppliers as supplier_service

router = APIRouter(prefix="/api/v1/groups/{group_id}/suppliers", tags=["suppliers"])


@router.get("", response_model=PaginatedResponse[SupplierRead])
async def list_suppliers(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    search: str | None = Query(None),
    sort: str = Query("name"),
    order: str = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[SupplierRead]:
    """List suppliers in a group.

    Parameters
    ----------
    group_id : UUID
        The ID of the group.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and membership link (injected, requires group membership).
    search : str or None, optional
        Filter by partial match on supplier name.
    sort : str, optional
        Field to sort by. Defaults to ``"name"``.
    order : str, optional
        Sort direction, ``"asc"`` or ``"desc"``. Defaults to ``"asc"``.
    offset : int, optional
        Number of records to skip. Defaults to 0.
    limit : int, optional
        Maximum records to return (1–100). Defaults to 20.

    Returns
    -------
    PaginatedResponse[SupplierRead]
        Paginated list of suppliers.
    """
    items, total = await supplier_service.list_suppliers(
        session, group_id, search=search, sort=sort, order=order, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[SupplierRead.model_validate(i, from_attributes=True) for i in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    group_id: UUID,
    body: SupplierCreate,
    session: SessionDep,
    member: GroupMemberDep,
) -> SupplierRead:
    """Create a supplier.

    Parameters
    ----------
    group_id : UUID
        The ID of the group.
    body : SupplierCreate
        The supplier data.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and membership link (injected, requires group membership).

    Returns
    -------
    SupplierRead
        The newly created supplier.
    """
    supplier = await supplier_service.create_supplier(session, group_id=group_id, name=body.name)
    await session.commit()
    return SupplierRead.model_validate(supplier, from_attributes=True)


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(
    group_id: UUID,
    supplier_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> SupplierRead:
    """Get a supplier by ID.

    Parameters
    ----------
    group_id : UUID
        The ID of the group.
    supplier_id : UUID
        The ID of the supplier to retrieve.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and membership link (injected, requires group membership).

    Returns
    -------
    SupplierRead
        The requested supplier.

    Raises
    ------
    HTTPException
        404 if the supplier does not exist or belongs to a different group.
    """
    supplier = await supplier_service.get_supplier(session, supplier_id)
    if supplier is None or supplier.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return SupplierRead.model_validate(supplier, from_attributes=True)


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    group_id: UUID,
    supplier_id: UUID,
    body: SupplierUpdate,
    session: SessionDep,
    member: GroupMemberDep,
) -> SupplierRead:
    """Update a supplier.

    Parameters
    ----------
    group_id : UUID
        The ID of the group.
    supplier_id : UUID
        The ID of the supplier to update.
    body : SupplierUpdate
        Fields to update.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and membership link (injected, requires group membership).

    Returns
    -------
    SupplierRead
        The updated supplier.

    Raises
    ------
    HTTPException
        404 if the supplier does not exist or belongs to a different group.
    """
    supplier = await supplier_service.get_supplier(session, supplier_id)
    if supplier is None or supplier.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    updated = await supplier_service.update_supplier(session, supplier, name=body.name)
    await session.commit()
    return SupplierRead.model_validate(updated, from_attributes=True)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    group_id: UUID,
    supplier_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
    """Delete a supplier.

    Parameters
    ----------
    group_id : UUID
        The ID of the group.
    supplier_id : UUID
        The ID of the supplier to delete.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and membership link (injected, requires group membership).

    Raises
    ------
    HTTPException
        404 if the supplier does not exist or belongs to a different group.
    """
    supplier = await supplier_service.get_supplier(session, supplier_id)
    if supplier is None or supplier.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    await supplier_service.delete_supplier(session, supplier)
    await session.commit()
