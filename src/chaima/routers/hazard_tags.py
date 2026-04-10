# src/chaima/routers/hazard_tags.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import GroupMemberDep, SessionDep
from chaima.schemas.hazard import (
    HazardTagCreate,
    HazardTagRead,
    HazardTagUpdate,
    IncompatibilityCreate,
    IncompatibilityRead,
)
from chaima.schemas.pagination import PaginatedResponse
from chaima.services import hazard_tags as hazard_service

router = APIRouter(
    prefix="/api/v1/groups/{group_id}/hazard-tags", tags=["hazard-tags"]
)


@router.get("", response_model=PaginatedResponse[HazardTagRead])
async def list_hazard_tags(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    search: str | None = Query(None),
    sort: str = Query("name"),
    order: str = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[HazardTagRead]:
    """List hazard tags in a group.

    Parameters
    ----------
    group_id : UUID
        The group to list tags for.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.
    search : str or None, optional
        Filter by partial name match.
    sort : str, optional
        Field to sort by.
    order : str, optional
        Sort direction.
    offset : int, optional
        Pagination offset.
    limit : int, optional
        Pagination limit.

    Returns
    -------
    PaginatedResponse[HazardTagRead]
        Paginated list of hazard tags.
    """
    items, total = await hazard_service.list_hazard_tags(
        session, group_id, search=search, sort=sort, order=order, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[HazardTagRead.model_validate(i, from_attributes=True) for i in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=HazardTagRead, status_code=status.HTTP_201_CREATED)
async def create_hazard_tag(
    group_id: UUID,
    body: HazardTagCreate,
    session: SessionDep,
    member: GroupMemberDep,
) -> HazardTagRead:
    """Create a hazard tag.

    Parameters
    ----------
    group_id : UUID
        The group to create the tag in.
    body : HazardTagCreate
        Tag creation payload.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.

    Returns
    -------
    HazardTagRead
        The created hazard tag.
    """
    try:
        tag = await hazard_service.create_hazard_tag(
            session, group_id=group_id, name=body.name, description=body.description
        )
    except hazard_service.DuplicateTagError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hazard tag '{body.name}' already exists in this group",
        )
    await session.commit()
    return HazardTagRead.model_validate(tag, from_attributes=True)


@router.patch("/{tag_id}", response_model=HazardTagRead)
async def update_hazard_tag(
    group_id: UUID,
    tag_id: UUID,
    body: HazardTagUpdate,
    session: SessionDep,
    member: GroupMemberDep,
) -> HazardTagRead:
    """Update a hazard tag.

    Parameters
    ----------
    group_id : UUID
        The group the tag belongs to.
    tag_id : UUID
        The ID of the tag to update.
    body : HazardTagUpdate
        Update payload.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.

    Returns
    -------
    HazardTagRead
        The updated hazard tag.
    """
    tag = await hazard_service.get_hazard_tag(session, tag_id)
    if tag is None or tag.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard tag not found")
    updated = await hazard_service.update_hazard_tag(
        session, tag, name=body.name, description=body.description
    )
    await session.commit()
    return HazardTagRead.model_validate(updated, from_attributes=True)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hazard_tag(
    group_id: UUID,
    tag_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
    """Delete a hazard tag.

    Parameters
    ----------
    group_id : UUID
        The group the tag belongs to.
    tag_id : UUID
        The ID of the tag to delete.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.
    """
    tag = await hazard_service.get_hazard_tag(session, tag_id)
    if tag is None or tag.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hazard tag not found")
    await hazard_service.delete_hazard_tag(session, tag)
    await session.commit()


@router.get("/incompatibilities", response_model=list[IncompatibilityRead])
async def list_incompatibilities(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> list[IncompatibilityRead]:
    """List incompatibility rules for this group.

    Parameters
    ----------
    group_id : UUID
        The group to list incompatibilities for.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.

    Returns
    -------
    list[IncompatibilityRead]
        All incompatibility rules for the group.
    """
    items = await hazard_service.list_incompatibilities(session, group_id)
    return [IncompatibilityRead.model_validate(i, from_attributes=True) for i in items]


@router.post(
    "/incompatibilities",
    response_model=IncompatibilityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_incompatibility(
    group_id: UUID,
    body: IncompatibilityCreate,
    session: SessionDep,
    member: GroupMemberDep,
) -> IncompatibilityRead:
    """Create an incompatibility rule. Both tags must belong to this group.

    Parameters
    ----------
    group_id : UUID
        The group context.
    body : IncompatibilityCreate
        Incompatibility creation payload.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.

    Returns
    -------
    IncompatibilityRead
        The created incompatibility rule.
    """
    try:
        incompat = await hazard_service.create_incompatibility(
            session,
            group_id=group_id,
            tag_a_id=body.tag_a_id,
            tag_b_id=body.tag_b_id,
            reason=body.reason,
        )
    except hazard_service.CrossGroupError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both tags must belong to this group",
        )
    except hazard_service.DuplicateIncompatibilityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Incompatibility already exists",
        )
    await session.commit()
    return IncompatibilityRead.model_validate(incompat, from_attributes=True)


@router.delete(
    "/incompatibilities/{incompatibility_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_incompatibility(
    group_id: UUID,
    incompatibility_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
    """Delete an incompatibility rule.

    Parameters
    ----------
    group_id : UUID
        The group context.
    incompatibility_id : UUID
        The ID of the incompatibility to delete.
    session : SessionDep
        Injected database session.
    member : GroupMemberDep
        Injected group membership check.
    """
    incompat = await hazard_service.get_incompatibility(session, incompatibility_id)
    if incompat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Incompatibility not found"
        )
    await hazard_service.delete_incompatibility(session, incompat)
    await session.commit()
