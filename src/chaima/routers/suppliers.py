# src/chaima/routers/suppliers.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import GroupAdminDep, GroupMemberDep, SessionDep
from chaima.schemas.pagination import PaginatedResponse
from chaima.schemas.supplier import (
    SupplierContainerRow,
    SupplierCreate,
    SupplierRead,
    SupplierUpdate,
)
from chaima.services import suppliers as supplier_service
from chaima.services.orders import lead_time_stats

router = APIRouter(prefix="/api/v1/groups/{group_id}/suppliers", tags=["suppliers"])


def _supplier_read_with_count(
    supplier, container_count: int, lead_time=None
) -> SupplierRead:
    data = SupplierRead.model_validate(supplier, from_attributes=True)
    return data.model_copy(
        update={"container_count": container_count, "lead_time": lead_time}
    )


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
    counts = await supplier_service.count_supplier_containers(
        session, [s.id for s in items]
    )
    lead_times = {}
    for s in items:
        lead_times[s.id] = await lead_time_stats(
            session, group_id=group_id, supplier_id=s.id
        )
    return PaginatedResponse(
        items=[
            _supplier_read_with_count(s, counts.get(s.id, 0), lead_times.get(s.id))
            for s in items
        ],
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
    # Any group member can create suppliers inline while adding a container.
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
    counts = await supplier_service.count_supplier_containers(session, [supplier.id])
    lt = await lead_time_stats(session, group_id=group_id, supplier_id=supplier.id)
    return _supplier_read_with_count(supplier, counts.get(supplier.id, 0), lt)


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
    counts = await supplier_service.count_supplier_containers(session, [supplier.id])
    lt = await lead_time_stats(session, group_id=group_id, supplier_id=supplier.id)
    return _supplier_read_with_count(supplier, counts.get(supplier.id, 0), lt)


@router.get(
    "/{supplier_id}/containers",
    response_model=list[SupplierContainerRow],
)
async def list_supplier_containers(
    group_id: UUID,
    supplier_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> list[SupplierContainerRow]:
    """List containers attached to a supplier (with chemical name)."""
    supplier = await supplier_service.get_supplier(session, supplier_id)
    if supplier is None or supplier.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    rows = await supplier_service.list_supplier_containers(session, supplier_id)
    return [
        SupplierContainerRow(
            id=container.id,
            identifier=container.identifier,
            amount=container.amount,
            unit=container.unit,
            is_archived=container.is_archived,
            chemical_id=container.chemical_id,
            chemical_name=chemical_name,
        )
        for container, chemical_name in rows
    ]


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    group_id: UUID,
    supplier_id: UUID,
    body: SupplierUpdate,
    session: SessionDep,
    admin: GroupAdminDep,
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
    counts = await supplier_service.count_supplier_containers(session, [updated.id])
    lt = await lead_time_stats(session, group_id=group_id, supplier_id=updated.id)
    return _supplier_read_with_count(updated, counts.get(updated.id, 0), lt)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    group_id: UUID,
    supplier_id: UUID,
    session: SessionDep,
    admin: GroupAdminDep,
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
    try:
        await supplier_service.delete_supplier(session, supplier)
    except supplier_service.SupplierInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Supplier is still assigned to containers; reassign them first.",
                "container_count": exc.container_count,
            },
        )
    await session.commit()
