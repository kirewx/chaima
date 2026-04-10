# src/chaima/services/suppliers.py
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.supplier import Supplier


async def create_supplier(
    session: AsyncSession, *, group_id: UUID, name: str
) -> Supplier:
    """Create a supplier within a group.

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
        The newly created supplier.
    """
    supplier = Supplier(name=name, group_id=group_id)
    session.add(supplier)
    await session.flush()
    return supplier


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
    """Delete a supplier.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    supplier : Supplier
        The supplier instance to delete.
    """
    await session.delete(supplier)
    await session.flush()
