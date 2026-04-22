# src/chaima/services/suppliers.py
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.supplier import Supplier


class SupplierInUseError(Exception):
    """Raised when attempting to delete a supplier referenced by containers."""

    def __init__(self, container_count: int) -> None:
        self.container_count = container_count
        super().__init__(f"Supplier has {container_count} container(s) and cannot be deleted")


async def create_supplier(
    session: AsyncSession, *, group_id: UUID, name: str
) -> Supplier:
    """Create a supplier within a group, or return existing match.

    Supplier names are deduplicated case-insensitively within a group: if a
    supplier with the same name (regardless of case) already exists, it is
    returned unchanged instead of inserting a duplicate.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The ID of the group this supplier belongs to.
    name : str
        The name of the supplier.

    Returns
    -------
    Supplier
        The existing or newly created supplier.
    """
    trimmed = name.strip()
    existing = (
        await session.exec(
            select(Supplier).where(
                Supplier.group_id == group_id,
                func.lower(Supplier.name) == trimmed.lower(),
            )
        )
    ).first()
    if existing is not None:
        return existing

    supplier = Supplier(name=trimmed, group_id=group_id)
    session.add(supplier)
    await session.flush()
    return supplier


async def count_supplier_containers(
    session: AsyncSession, supplier_ids: list[UUID]
) -> dict[UUID, int]:
    """Return container counts keyed by supplier id for the given suppliers."""
    if not supplier_ids:
        return {}
    result = await session.exec(
        select(Container.supplier_id, func.count(Container.id))
        .where(Container.supplier_id.in_(supplier_ids))  # type: ignore[union-attr]
        .group_by(Container.supplier_id)
    )
    return {sid: cnt for sid, cnt in result.all() if sid is not None}


async def list_supplier_containers(
    session: AsyncSession, supplier_id: UUID
) -> list[tuple[Container, str]]:
    """List containers attached to a supplier with their chemical name."""
    result = await session.exec(
        select(Container, Chemical.name)
        .join(Chemical, Chemical.id == Container.chemical_id)
        .where(Container.supplier_id == supplier_id)
        .order_by(Chemical.name, Container.identifier)
    )
    return list(result.all())


async def list_suppliers(
    session: AsyncSession,
    group_id: UUID,
    *,
    search: str | None = None,
    sort: str = "name",
    order: str = "asc",
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Supplier], int]:
    """List suppliers for a group with pagination.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The ID of the group whose suppliers to list.
    search : str or None, optional
        Filter by partial match on supplier name.
    sort : str, optional
        Field to sort by. Defaults to ``"name"``.
    order : str, optional
        Sort direction, ``"asc"`` or ``"desc"``. Defaults to ``"asc"``.
    offset : int, optional
        Number of records to skip. Defaults to 0.
    limit : int, optional
        Maximum number of records to return. Defaults to 20.

    Returns
    -------
    tuple[list[Supplier], int]
        A tuple of (items, total count).
    """
    query = select(Supplier).where(Supplier.group_id == group_id)

    if search:
        query = query.where(Supplier.name.ilike(f"%{search}%"))  # type: ignore[union-attr]

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.exec(count_query)).one()

    sort_col = getattr(Supplier, sort, Supplier.name)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    query = query.offset(offset).limit(limit)

    result = await session.exec(query)
    return list(result.all()), total


async def get_supplier(session: AsyncSession, supplier_id: UUID) -> Supplier | None:
    """Get a supplier by ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    supplier_id : UUID
        The ID of the supplier to retrieve.

    Returns
    -------
    Supplier or None
        The supplier, or None if not found.
    """
    return await session.get(Supplier, supplier_id)


async def update_supplier(
    session: AsyncSession, supplier: Supplier, *, name: str | None = None
) -> Supplier:
    """Update a supplier.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    supplier : Supplier
        The supplier instance to update.
    name : str or None, optional
        New name for the supplier, if provided.

    Returns
    -------
    Supplier
        The updated supplier.
    """
    if name is not None:
        supplier.name = name
    session.add(supplier)
    await session.flush()
    return supplier


async def delete_supplier(session: AsyncSession, supplier: Supplier) -> None:
    """Delete a supplier. Fails if any container still references it.

    Raises
    ------
    SupplierInUseError
        If one or more containers reference this supplier.
    """
    counts = await count_supplier_containers(session, [supplier.id])
    count = counts.get(supplier.id, 0)
    if count > 0:
        raise SupplierInUseError(count)
    await session.delete(supplier)
    await session.flush()
