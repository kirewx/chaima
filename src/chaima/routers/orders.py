"""Router for chemical Order endpoints."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import (
    CurrentUserDep,
    GroupAdminDep,
    GroupMemberDep,
    SessionDep,
)
from chaima.models.chemical import Chemical
from chaima.models.project import Project
from chaima.models.supplier import Supplier
from chaima.schemas.container import ContainerRead
from chaima.schemas.order import (
    ContainerReceiveRow as ContainerReceiveRowSchema,
    OrderCancel,
    OrderCreate,
    OrderRead,
    OrderReceive,
    OrderUpdate,
)
from chaima.schemas.pagination import PaginatedResponse
from chaima.services import orders as order_service

router = APIRouter(prefix="/api/v1/groups/{group_id}/orders", tags=["orders"])


async def _hydrate(session, order) -> OrderRead:
    """Populate chemical_name / supplier_name / project_name on the read schema."""
    chemical = await session.get(Chemical, order.chemical_id)
    supplier = await session.get(Supplier, order.supplier_id)
    project = await session.get(Project, order.project_id)
    base = OrderRead.model_validate(order)
    return base.model_copy(
        update={
            "chemical_name": chemical.name if chemical else None,
            "supplier_name": supplier.name if supplier else None,
            "project_name": project.name if project else None,
        }
    )


@router.get("", response_model=PaginatedResponse[OrderRead])
async def list_orders(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    status_: Literal["ordered", "received", "cancelled"] | None = Query(None, alias="status"),
    supplier_id: UUID | None = Query(None),
    project_id: UUID | None = Query(None),
    chemical_id: UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> PaginatedResponse[OrderRead]:
    rows = await order_service.list_orders(
        session,
        group_id=group_id,
        status=status_,
        supplier_id=supplier_id,
        project_id=project_id,
        chemical_id=chemical_id,
    )
    page = rows[offset : offset + limit]
    items = [await _hydrate(session, o) for o in page]
    return PaginatedResponse(items=items, total=len(rows), offset=offset, limit=limit)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    group_id: UUID,
    body: OrderCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
    member: GroupMemberDep,
) -> OrderRead:
    try:
        order = await order_service.create_order(
            session,
            group_id=group_id,
            chemical_id=body.chemical_id,
            supplier_id=body.supplier_id,
            project_id=body.project_id,
            amount_per_package=body.amount_per_package,
            unit=body.unit,
            package_count=body.package_count,
            price_per_package=body.price_per_package,
            currency=body.currency,
            purity=body.purity,
            vendor_catalog_number=body.vendor_catalog_number,
            vendor_product_url=str(body.vendor_product_url) if body.vendor_product_url else None,
            vendor_order_number=body.vendor_order_number,
            expected_arrival=body.expected_arrival,
            comment=body.comment,
            ordered_by_user_id=current_user.id,
            wishlist_item_id=body.wishlist_item_id,
        )
    except order_service.CrossGroupReferenceError as exc:
        raise HTTPException(status_code=404, detail=f"{exc} not found in this group")
    await session.commit()
    return await _hydrate(session, order)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    group_id: UUID, order_id: UUID, session: SessionDep, member: GroupMemberDep,
) -> OrderRead:
    order = await order_service.get_order(session, order_id)
    if order is None or order.group_id != group_id:
        raise HTTPException(status_code=404, detail="Order not found")
    return await _hydrate(session, order)


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order(
    group_id: UUID, order_id: UUID, body: OrderUpdate,
    session: SessionDep, current_user: CurrentUserDep, member: GroupMemberDep,
) -> OrderRead:
    order = await order_service.get_order(session, order_id)
    if order is None or order.group_id != group_id:
        raise HTTPException(status_code=404, detail="Order not found")
    _, link = member
    if order.ordered_by_user_id != current_user.id and not link.is_admin:
        raise HTTPException(status_code=403, detail="Only the creator or an admin can edit")
    try:
        await order_service.edit_order(
            session, order, **body.model_dump(exclude_none=True),
        )
    except order_service.OrderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except order_service.CrossGroupReferenceError as exc:
        raise HTTPException(status_code=404, detail=f"{exc} not found in this group")
    await session.commit()
    return await _hydrate(session, order)


@router.post("/{order_id}/receive", response_model=list[ContainerRead])
async def receive_order(
    group_id: UUID, order_id: UUID, body: OrderReceive,
    session: SessionDep, current_user: CurrentUserDep, member: GroupMemberDep,
) -> list[ContainerRead]:
    order = await order_service.get_order(session, order_id)
    if order is None or order.group_id != group_id:
        raise HTTPException(status_code=404, detail="Order not found")
    rows = [
        order_service.ContainerReceiveRow(
            identifier=r.identifier,
            storage_location_id=r.storage_location_id,
            purity_override=r.purity_override,
        )
        for r in body.containers
    ]
    try:
        spawned = await order_service.receive_order(
            session, order, rows=rows, received_by_user_id=current_user.id,
        )
    except order_service.OrderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except order_service.ContainerCountMismatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except order_service.StorageLocationInvalidError as exc:
        raise HTTPException(
            status_code=422,
            detail={"row_index": exc.index, "message": str(exc)},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await session.commit()
    return [ContainerRead.model_validate(c) for c in spawned]


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    group_id: UUID, order_id: UUID, body: OrderCancel,
    session: SessionDep, admin: GroupAdminDep,
) -> OrderRead:
    order = await order_service.get_order(session, order_id)
    if order is None or order.group_id != group_id:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        await order_service.cancel_order(session, order, reason=body.cancellation_reason)
    except order_service.OrderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    return await _hydrate(session, order)
