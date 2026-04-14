# src/chaima/routers/storage_locations.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from chaima.dependencies import GroupMemberDep, SessionDep
from chaima.schemas.storage import (
    StorageLocationCreate,
    StorageLocationNode,
    StorageLocationRead,
    StorageLocationUpdate,
)
from chaima.services import storage_locations as storage_service
from chaima.services.storage_locations import InvalidHierarchy

router = APIRouter(
    prefix="/api/v1/groups/{group_id}/storage-locations", tags=["storage-locations"]
)


@router.get("", response_model=list[StorageLocationNode])
async def get_tree(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> list[StorageLocationNode]:
    """Get the full storage location tree for a group.

    Parameters
    ----------
    group_id : UUID
        The group to retrieve locations for.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.

    Returns
    -------
    list[StorageLocationNode]
        Nested tree of storage locations.
    """
    return await storage_service.get_tree(session, group_id)


@router.post("", response_model=StorageLocationRead, status_code=status.HTTP_201_CREATED)
async def create_location(
    group_id: UUID,
    body: StorageLocationCreate,
    session: SessionDep,
    member: GroupMemberDep,
) -> StorageLocationRead:
    """Create a storage location in a group.

    Parameters
    ----------
    group_id : UUID
        The group to create the location in.
    body : StorageLocationCreate
        Location creation payload.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.

    Returns
    -------
    StorageLocationRead
        The created storage location.
    """
    if body.parent_id is not None:
        if not await storage_service.location_belongs_to_group(session, body.parent_id, group_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent location does not belong to this group",
            )
    try:
        loc = await storage_service.create_location(
            session,
            group_id=group_id,
            name=body.name,
            kind=body.kind,
            description=body.description,
            parent_id=body.parent_id,
        )
    except InvalidHierarchy as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid hierarchy: {e}",
        )
    await session.commit()
    return StorageLocationRead.model_validate(loc, from_attributes=True)


@router.get("/{location_id}", response_model=StorageLocationRead)
async def get_location(
    group_id: UUID,
    location_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> StorageLocationRead:
    """Get a storage location by ID.

    Parameters
    ----------
    group_id : UUID
        The group the location belongs to.
    location_id : UUID
        The ID of the location to retrieve.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.

    Returns
    -------
    StorageLocationRead
        The storage location.
    """
    if not await storage_service.location_belongs_to_group(session, location_id, group_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage location not found"
        )
    loc = await storage_service.get_location(session, location_id)
    if loc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage location not found"
        )
    return StorageLocationRead.model_validate(loc, from_attributes=True)


@router.patch("/{location_id}", response_model=StorageLocationRead)
async def update_location(
    group_id: UUID,
    location_id: UUID,
    body: StorageLocationUpdate,
    session: SessionDep,
    member: GroupMemberDep,
) -> StorageLocationRead:
    """Update a storage location.

    Parameters
    ----------
    group_id : UUID
        The group the location belongs to.
    location_id : UUID
        The ID of the location to update.
    body : StorageLocationUpdate
        Update payload.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.

    Returns
    -------
    StorageLocationRead
        The updated storage location.
    """
    if not await storage_service.location_belongs_to_group(session, location_id, group_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage location not found"
        )
    loc = await storage_service.get_location(session, location_id)
    if loc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage location not found"
        )
    updated = await storage_service.update_location(
        session, loc, name=body.name, description=body.description, parent_id=body.parent_id
    )
    await session.commit()
    return StorageLocationRead.model_validate(updated, from_attributes=True)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    group_id: UUID,
    location_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
    """Delete a storage location. Fails if it has containers.

    Parameters
    ----------
    group_id : UUID
        The group the location belongs to.
    location_id : UUID
        The ID of the location to delete.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.
    """
    if not await storage_service.location_belongs_to_group(session, location_id, group_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage location not found"
        )
    loc = await storage_service.get_location(session, location_id)
    if loc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage location not found"
        )
    try:
        await storage_service.delete_location(session, loc)
    except storage_service.LocationHasContainersError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete location with containers",
        )
    await session.commit()
