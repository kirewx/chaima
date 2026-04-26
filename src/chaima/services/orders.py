"""Service layer for chemical Orders.

Service functions flush; the calling router commits. Receipt is the only
operation that requires an explicit transaction (handled inline below).
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from statistics import median, quantiles
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.order import Order, OrderStatus
from chaima.models.project import Project
from chaima.models.storage import StorageLocation, StorageLocationGroup
from chaima.models.supplier import Supplier
from chaima.models.wishlist import WishlistItem, WishlistStatus


class CrossGroupReferenceError(Exception):
    """A referenced resource (chemical/supplier/project) belongs to a different group."""


class OrderStateError(Exception):
    """Operation is not allowed for the order's current status."""


class ContainerCountMismatchError(Exception):
    """Number of received containers does not match order.package_count."""


class StorageLocationInvalidError(Exception):
    """A storage_location_id in the receive payload is not in the requesting group."""

    def __init__(self, index: int, location_id: UUID) -> None:
        self.index = index
        self.location_id = location_id
        super().__init__(f"Container row {index}: storage_location_id {location_id} invalid")


async def _verify_same_group(
    session: AsyncSession, group_id: UUID, chemical_id: UUID, supplier_id: UUID, project_id: UUID
) -> None:
    chemical = await session.get(Chemical, chemical_id)
    if chemical is None or chemical.group_id != group_id:
        raise CrossGroupReferenceError("chemical")
    supplier = await session.get(Supplier, supplier_id)
    if supplier is None or supplier.group_id != group_id:
        raise CrossGroupReferenceError("supplier")
    project = await session.get(Project, project_id)
    if project is None or project.group_id != group_id:
        raise CrossGroupReferenceError("project")


async def create_order(
    session: AsyncSession,
    *,
    group_id: UUID,
    chemical_id: UUID,
    supplier_id: UUID,
    project_id: UUID,
    amount_per_package: float,
    unit: str,
    package_count: int,
    ordered_by_user_id: UUID,
    price_per_package: Decimal | None = None,
    currency: str = "EUR",
    purity: str | None = None,
    vendor_catalog_number: str | None = None,
    vendor_product_url: str | None = None,
    vendor_order_number: str | None = None,
    expected_arrival: datetime.date | None = None,
    comment: str | None = None,
    wishlist_item_id: UUID | None = None,
) -> Order:
    await _verify_same_group(session, group_id, chemical_id, supplier_id, project_id)

    order = Order(
        group_id=group_id,
        chemical_id=chemical_id,
        supplier_id=supplier_id,
        project_id=project_id,
        amount_per_package=amount_per_package,
        unit=unit,
        package_count=package_count,
        price_per_package=price_per_package,
        currency=currency,
        purity=purity,
        vendor_catalog_number=vendor_catalog_number,
        vendor_product_url=vendor_product_url,
        vendor_order_number=vendor_order_number,
        expected_arrival=expected_arrival,
        comment=comment,
        ordered_by_user_id=ordered_by_user_id,
    )
    session.add(order)
    await session.flush()

    if wishlist_item_id is not None:
        wl = await session.get(WishlistItem, wishlist_item_id)
        if wl is not None and wl.group_id == group_id and wl.status == WishlistStatus.OPEN:
            wl.status = WishlistStatus.CONVERTED
            wl.converted_to_order_id = order.id
            session.add(wl)
            await session.flush()

    return order


async def list_orders(
    session: AsyncSession,
    *,
    group_id: UUID,
    status: str | None = None,
    supplier_id: UUID | None = None,
    project_id: UUID | None = None,
    chemical_id: UUID | None = None,
) -> list[Order]:
    stmt = select(Order).where(Order.group_id == group_id)
    if status is not None:
        stmt = stmt.where(Order.status == OrderStatus(status))
    if supplier_id is not None:
        stmt = stmt.where(Order.supplier_id == supplier_id)
    if project_id is not None:
        stmt = stmt.where(Order.project_id == project_id)
    if chemical_id is not None:
        stmt = stmt.where(Order.chemical_id == chemical_id)
    stmt = stmt.order_by(Order.ordered_at.desc())
    return list((await session.exec(stmt)).all())


async def get_order(session: AsyncSession, order_id: UUID) -> Order | None:
    return await session.get(Order, order_id)


async def edit_order(
    session: AsyncSession,
    order: Order,
    *,
    supplier_id: UUID | None = None,
    project_id: UUID | None = None,
    amount_per_package: float | None = None,
    unit: str | None = None,
    package_count: int | None = None,
    price_per_package: Decimal | None = None,
    currency: str | None = None,
    purity: str | None = None,
    vendor_catalog_number: str | None = None,
    vendor_product_url: str | None = None,
    vendor_order_number: str | None = None,
    expected_arrival: datetime.date | None = None,
    comment: str | None = None,
) -> Order:
    if order.status != OrderStatus.ORDERED:
        raise OrderStateError(f"Order is {order.status.value}; edits are not allowed")

    if supplier_id is not None:
        sup = await session.get(Supplier, supplier_id)
        if sup is None or sup.group_id != order.group_id:
            raise CrossGroupReferenceError("supplier")
        order.supplier_id = supplier_id
    if project_id is not None:
        proj = await session.get(Project, project_id)
        if proj is None or proj.group_id != order.group_id:
            raise CrossGroupReferenceError("project")
        order.project_id = project_id

    for attr, value in {
        "amount_per_package": amount_per_package,
        "unit": unit,
        "package_count": package_count,
        "price_per_package": price_per_package,
        "currency": currency,
        "purity": purity,
        "vendor_catalog_number": vendor_catalog_number,
        "vendor_product_url": vendor_product_url,
        "vendor_order_number": vendor_order_number,
        "expected_arrival": expected_arrival,
        "comment": comment,
    }.items():
        if value is not None:
            setattr(order, attr, value)

    session.add(order)
    await session.flush()
    return order


async def cancel_order(
    session: AsyncSession, order: Order, *, reason: str | None = None
) -> Order:
    if order.status != OrderStatus.ORDERED:
        raise OrderStateError(f"Order is {order.status.value}; cannot cancel")
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.datetime.now(datetime.timezone.utc)
    order.cancellation_reason = reason
    session.add(order)
    await session.flush()
    return order
