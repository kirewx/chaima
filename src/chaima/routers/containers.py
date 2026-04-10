# src/chaima/routers/containers.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import CurrentUserDep, GroupMemberDep, SessionDep
from chaima.schemas.container import ContainerCreate, ContainerRead, ContainerUpdate
from chaima.schemas.pagination import PaginatedResponse
from chaima.services import containers as container_service

router = APIRouter(tags=["containers"])

# Nested: containers for a specific chemical
nested = APIRouter(
    prefix="/api/v1/groups/{group_id}/chemicals/{chemical_id}/containers",
    tags=["containers"],
)

# Flat: all containers in a group
flat = APIRouter(
    prefix="/api/v1/groups/{group_id}/containers",
    tags=["containers"],
)


@nested.get("", response_model=PaginatedResponse[ContainerRead])
async def list_containers_for_chemical(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    search: str | None = Query(None),
    location_id: UUID | None = Query(None),
    supplier_id: UUID | None = Query(None),
    is_archived: bool = Query(False),
    sort: str = Query("identifier"),
    order: str = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ContainerRead]:
    """List containers for a specific chemical.

    Parameters
    ----------
    group_id : UUID
        The group to scope the request to.
    chemical_id : UUID
        The chemical whose containers to list.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.
    search : str or None, optional
        Case-insensitive partial match on container identifier.
    location_id : UUID or None, optional
        Filter by storage location.
    supplier_id : UUID or None, optional
        Filter by supplier.
    is_archived : bool, optional
        Show archived containers if True. Defaults to False.
    sort : str, optional
        Sort field. Defaults to ``"identifier"``.
    order : str, optional
        Sort direction. Defaults to ``"asc"``.
    offset : int, optional
        Pagination offset. Defaults to 0.
    limit : int, optional
        Page size. Defaults to 20.

    Returns
    -------
    PaginatedResponse[ContainerRead]
        Paginated list of containers.
    """
    items, total = await container_service.list_containers(
        session,
        group_id,
        chemical_id=chemical_id,
        location_id=location_id,
        supplier_id=supplier_id,
        search=search,
        is_archived=is_archived,
        sort=sort,
        order=order,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        items=[ContainerRead.model_validate(i, from_attributes=True) for i in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@nested.post("", response_model=ContainerRead, status_code=status.HTTP_201_CREATED)
async def create_container(
    group_id: UUID,
    chemical_id: UUID,
    body: ContainerCreate,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
) -> ContainerRead:
    """Create a container for a chemical.

    Parameters
    ----------
    group_id : UUID
        The group the chemical belongs to.
    chemical_id : UUID
        The chemical to attach the container to.
    body : ContainerCreate
        Container creation data.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.
    user : CurrentUserDep
        Authenticated user (set as creator).

    Returns
    -------
    ContainerRead
        The newly created container.

    Raises
    ------
    HTTPException
        404 if the chemical is not found or belongs to a different group.
    """
    from chaima.services import chemicals as chemical_svc

    chem = await chemical_svc.get_chemical(session, chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found")

    container = await container_service.create_container(
        session,
        chemical_id=chemical_id,
        location_id=body.location_id,
        supplier_id=body.supplier_id,
        identifier=body.identifier,
        amount=body.amount,
        unit=body.unit,
        created_by=user.id,
        purchased_at=body.purchased_at,
    )
    await session.commit()
    return ContainerRead.model_validate(container, from_attributes=True)


@flat.get("", response_model=PaginatedResponse[ContainerRead])
async def list_containers(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    search: str | None = Query(None),
    chemical_id: UUID | None = Query(None),
    location_id: UUID | None = Query(None),
    supplier_id: UUID | None = Query(None),
    is_archived: bool = Query(False),
    sort: str = Query("identifier"),
    order: str = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ContainerRead]:
    """List all containers in a group.

    Parameters
    ----------
    group_id : UUID
        The group to list containers for.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.
    search : str or None, optional
        Case-insensitive partial match on container identifier.
    chemical_id : UUID or None, optional
        Filter by chemical.
    location_id : UUID or None, optional
        Filter by storage location.
    supplier_id : UUID or None, optional
        Filter by supplier.
    is_archived : bool, optional
        Show archived containers if True. Defaults to False.
    sort : str, optional
        Sort field. Defaults to ``"identifier"``.
    order : str, optional
        Sort direction. Defaults to ``"asc"``.
    offset : int, optional
        Pagination offset. Defaults to 0.
    limit : int, optional
        Page size. Defaults to 20.

    Returns
    -------
    PaginatedResponse[ContainerRead]
        Paginated list of containers.
    """
    items, total = await container_service.list_containers(
        session,
        group_id,
        chemical_id=chemical_id,
        location_id=location_id,
        supplier_id=supplier_id,
        search=search,
        is_archived=is_archived,
        sort=sort,
        order=order,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        items=[ContainerRead.model_validate(i, from_attributes=True) for i in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@flat.get("/{container_id}", response_model=ContainerRead)
async def get_container(
    group_id: UUID,
    container_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> ContainerRead:
    """Get a container by ID.

    Parameters
    ----------
    group_id : UUID
        The group to scope the lookup to.
    container_id : UUID
        The container ID to retrieve.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Returns
    -------
    ContainerRead
        The requested container.

    Raises
    ------
    HTTPException
        404 if the container is not found or belongs to a different group.
    """
    container = await container_service.get_container(session, container_id)
    if container is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    from chaima.services import chemicals as chemical_svc

    chem = await chemical_svc.get_chemical(session, container.chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    return ContainerRead.model_validate(container, from_attributes=True)


@flat.patch("/{container_id}", response_model=ContainerRead)
async def update_container(
    group_id: UUID,
    container_id: UUID,
    body: ContainerUpdate,
    session: SessionDep,
    member: GroupMemberDep,
) -> ContainerRead:
    """Update a container (including unarchive via is_archived: false).

    Parameters
    ----------
    group_id : UUID
        The group to scope the update to.
    container_id : UUID
        The container ID to update.
    body : ContainerUpdate
        Fields to update. Set ``is_archived: false`` to unarchive.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Returns
    -------
    ContainerRead
        The updated container.

    Raises
    ------
    HTTPException
        404 if the container is not found or belongs to a different group.
    """
    container = await container_service.get_container(session, container_id)
    if container is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    from chaima.services import chemicals as chemical_svc

    chem = await chemical_svc.get_chemical(session, container.chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    updated = await container_service.update_container(
        session, container, **body.model_dump(exclude_unset=True)
    )
    await session.commit()
    await session.refresh(updated)
    return ContainerRead.model_validate(updated, from_attributes=True)


@flat.delete("/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_container(
    group_id: UUID,
    container_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
    """Archive (soft-delete) a container.

    Parameters
    ----------
    group_id : UUID
        The group to scope the delete to.
    container_id : UUID
        The container ID to archive.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Raises
    ------
    HTTPException
        404 if the container is not found or belongs to a different group.
    """
    container = await container_service.get_container(session, container_id)
    if container is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    from chaima.services import chemicals as chemical_svc

    chem = await chemical_svc.get_chemical(session, container.chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    await container_service.archive_container(session, container)
    await session.commit()


router.include_router(nested)
router.include_router(flat)
