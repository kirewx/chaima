# src/chaima/services/containers.py
import datetime
import uuid as uuid_pkg
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.container import Container


class DuplicateIdentifier(ValueError):
    """Raised when a container identifier already exists in the same group."""


async def check_identifier_unique_in_group(
    session: AsyncSession,
    group_id: uuid_pkg.UUID,
    identifier: str,
    exclude_container_id: uuid_pkg.UUID | None = None,
) -> None:
    """Raise DuplicateIdentifier if another (non-archived) container in
    ``group_id`` already uses ``identifier``. Containers inherit their group
    through their chemical."""
    stmt = (
        select(Container.id)
        .join(Chemical, Chemical.id == Container.chemical_id)
        .where(Chemical.group_id == group_id)
        .where(Container.identifier == identifier)
        .where(Container.is_archived.is_(False))
    )
    if exclude_container_id is not None:
        stmt = stmt.where(Container.id != exclude_container_id)
    result = await session.exec(stmt)
    if result.first() is not None:
        raise DuplicateIdentifier(
            f"Container identifier '{identifier}' already in use in this group"
        )


async def create_container(
    session: AsyncSession,
    *,
    chemical_id: UUID,
    location_id: UUID,
    identifier: str,
    amount: float,
    unit: str,
    created_by: UUID,
    supplier_id: UUID | None = None,
    purchased_at: datetime.date | None = None,
) -> Container:
    """Create a new container for a chemical.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical_id : UUID
        The chemical this container holds.
    location_id : UUID
        The storage location for this container.
    identifier : str
        A human-readable identifier (e.g. bottle number or lot ID).
    amount : float
        Quantity of chemical in this container.
    unit : str
        Unit of measurement (e.g. mL, g).
    created_by : UUID
        ID of the user creating the container.
    supplier_id : UUID or None, optional
        The supplier this container came from.
    purchased_at : datetime.date or None, optional
        Purchase date.

    Returns
    -------
    Container
        The newly created container.
    """
    container = Container(
        chemical_id=chemical_id,
        location_id=location_id,
        supplier_id=supplier_id,
        identifier=identifier,
        amount=amount,
        unit=unit,
        created_by=created_by,
        purchased_at=purchased_at,
    )
    session.add(container)
    await session.flush()
    return container


async def list_containers(
    session: AsyncSession,
    group_id: UUID,
    *,
    chemical_id: UUID | None = None,
    location_id: UUID | None = None,
    supplier_id: UUID | None = None,
    search: str | None = None,
    is_archived: bool = False,
    sort: str = "identifier",
    order: str = "asc",
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Container], int]:
    """List containers for a group with optional filtering and pagination.

    Containers are scoped to a group via their parent Chemical.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to list containers for.
    chemical_id : UUID or None, optional
        Filter to containers for a specific chemical.
    location_id : UUID or None, optional
        Filter by storage location.
    supplier_id : UUID or None, optional
        Filter by supplier.
    search : str or None, optional
        Case-insensitive partial match on container identifier.
    is_archived : bool, optional
        If False (default), return only active containers.
        If True, return only archived containers.
    sort : str, optional
        Field to sort by. Defaults to ``"identifier"``.
    order : str, optional
        Sort direction, ``"asc"`` or ``"desc"``. Defaults to ``"asc"``.
    offset : int, optional
        Number of records to skip. Defaults to 0.
    limit : int, optional
        Maximum number of records to return. Defaults to 20.

    Returns
    -------
    tuple[list[Container], int]
        A tuple of (items, total count).
    """
    query = (
        select(Container)
        .join(Chemical, Chemical.id == Container.chemical_id)
        .where(Chemical.group_id == group_id)
        .where(Container.is_archived == is_archived)
    )

    if chemical_id:
        query = query.where(Container.chemical_id == chemical_id)
    if location_id:
        query = query.where(Container.location_id == location_id)
    if supplier_id:
        query = query.where(Container.supplier_id == supplier_id)
    if search:
        query = query.where(Container.identifier.ilike(f"%{search}%"))  # type: ignore[union-attr]

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.exec(count_query)).one()

    sort_col = getattr(Container, sort, Container.identifier)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    query = query.offset(offset).limit(limit)

    result = await session.exec(query)
    return list(result.all()), total


async def get_container(session: AsyncSession, container_id: UUID) -> Container | None:
    """Get a container by ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    container_id : UUID
        The ID of the container to retrieve.

    Returns
    -------
    Container or None
        The container, or None if not found.
    """
    return await session.get(Container, container_id)


async def update_container(
    session: AsyncSession,
    container: Container,
    **kwargs: object,
) -> Container:
    """Update container fields.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    container : Container
        The container instance to update.
    **kwargs : object
        Field name/value pairs to update. None values are skipped.

    Returns
    -------
    Container
        The updated container.
    """
    for key, value in kwargs.items():
        if value is not None:
            setattr(container, key, value)
    session.add(container)
    await session.flush()
    return container


async def archive_container(session: AsyncSession, container: Container) -> Container:
    """Soft-delete a container by setting is_archived to True.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    container : Container
        The container to archive.

    Returns
    -------
    Container
        The archived container.
    """
    container.is_archived = True
    session.add(container)
    await session.flush()
    return container
