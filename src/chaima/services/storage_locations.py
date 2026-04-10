# src/chaima/services/storage_locations.py
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.container import Container
from chaima.models.storage import StorageLocation, StorageLocationGroup
from chaima.schemas.storage import StorageLocationNode


class LocationHasContainersError(Exception):
    """Raised when trying to delete a location that has containers."""


async def create_location(
    session: AsyncSession,
    *,
    group_id: UUID,
    name: str,
    description: str | None = None,
    parent_id: UUID | None = None,
) -> StorageLocation:
    """Create a storage location and link it to the group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to link the location to.
    name : str
        Name of the location.
    description : str or None, optional
        Optional description.
    parent_id : UUID or None, optional
        Optional parent location ID.

    Returns
    -------
    StorageLocation
        The newly created storage location.
    """
    loc = StorageLocation(name=name, description=description, parent_id=parent_id)
    session.add(loc)
    await session.flush()

    link = StorageLocationGroup(location_id=loc.id, group_id=group_id)
    session.add(link)
    await session.flush()
    return loc


async def get_location(session: AsyncSession, location_id: UUID) -> StorageLocation | None:
    """Get a storage location by ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    location_id : UUID
        The ID of the location to retrieve.

    Returns
    -------
    StorageLocation or None
        The storage location, or None if not found.
    """
    return await session.get(StorageLocation, location_id)


async def get_tree(session: AsyncSession, group_id: UUID) -> list[StorageLocationNode]:
    """Get the full storage location tree for a group as nested nodes.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group ID to fetch locations for.

    Returns
    -------
    list[StorageLocationNode]
        A list of root nodes, each with nested children.
    """
    result = await session.exec(
        select(StorageLocation)
        .join(StorageLocationGroup, StorageLocationGroup.location_id == StorageLocation.id)
        .where(StorageLocationGroup.group_id == group_id)
    )
    all_locations = list(result.all())

    by_id: dict[UUID, StorageLocationNode] = {}
    for loc in all_locations:
        by_id[loc.id] = StorageLocationNode(
            id=loc.id, name=loc.name, description=loc.description
        )

    roots: list[StorageLocationNode] = []
    for loc in all_locations:
        node = by_id[loc.id]
        if loc.parent_id is not None and loc.parent_id in by_id:
            by_id[loc.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots


async def update_location(
    session: AsyncSession,
    location: StorageLocation,
    *,
    name: str | None = None,
    description: str | None = None,
    parent_id: UUID | None = None,
) -> StorageLocation:
    """Update a storage location.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    location : StorageLocation
        The location instance to update.
    name : str or None, optional
        New name, if provided.
    description : str or None, optional
        New description, if provided.
    parent_id : UUID or None, optional
        New parent location ID, if provided.

    Returns
    -------
    StorageLocation
        The updated storage location.
    """
    if name is not None:
        location.name = name
    if description is not None:
        location.description = description
    if parent_id is not None:
        location.parent_id = parent_id
    session.add(location)
    await session.flush()
    return location


async def delete_location(session: AsyncSession, location: StorageLocation) -> None:
    """Delete a storage location. Fails if it has containers.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    location : StorageLocation
        The location to delete.

    Raises
    ------
    LocationHasContainersError
        If the location has associated containers.
    """
    result = await session.exec(
        select(Container).where(Container.location_id == location.id).limit(1)
    )
    if result.first() is not None:
        raise LocationHasContainersError(
            f"Storage location {location.id} has containers and cannot be deleted"
        )
    await session.delete(location)
    await session.flush()


async def location_belongs_to_group(
    session: AsyncSession, location_id: UUID, group_id: UUID
) -> bool:
    """Check if a storage location belongs to a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    location_id : UUID
        The location ID to check.
    group_id : UUID
        The group ID to check against.

    Returns
    -------
    bool
        True if the location belongs to the group, False otherwise.
    """
    result = await session.exec(
        select(StorageLocationGroup).where(
            StorageLocationGroup.location_id == location_id,
            StorageLocationGroup.group_id == group_id,
        )
    )
    return result.first() is not None
