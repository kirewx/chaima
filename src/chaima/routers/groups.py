"""Router for group management endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from chaima.dependencies import (
    CurrentUserDep,
    GroupAdminDep,
    GroupMemberDep,
    SessionDep,
)
from chaima.models.user import User
from chaima.schemas.group import (
    GroupCreate,
    GroupRead,
    GroupUpdate,
    MemberAdd,
    MemberRead,
    MemberUpdate,
)
from chaima.services import groups as group_service
from chaima.services.groups import MemberExistsError, MemberNotFoundError

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


@router.get("", response_model=list[GroupRead])
async def list_groups(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[GroupRead]:
    """List all groups the current user belongs to.

    Parameters
    ----------
    session : AsyncSession
        The database session (injected).
    current_user : User
        The authenticated user (injected).

    Returns
    -------
    list[GroupRead]
        All groups the user is a member of.
    """
    groups = await group_service.list_groups_for_user(session, current_user.id)
    return [GroupRead.model_validate(g) for g in groups]


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    body: GroupCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> GroupRead:
    """Create a new group with the current user as admin.

    Parameters
    ----------
    body : GroupCreate
        The group data.
    session : AsyncSession
        The database session (injected).
    current_user : User
        The authenticated user (injected).

    Returns
    -------
    GroupRead
        The newly created group.
    """
    group = await group_service.create_group(
        session,
        name=body.name,
        description=body.description,
        creator_id=current_user.id,
    )
    return GroupRead.model_validate(group)


@router.get("/{group_id}", response_model=GroupRead)
async def get_group(
    member: GroupMemberDep,
) -> GroupRead:
    """Retrieve a group by ID.

    Parameters
    ----------
    member : tuple[Group, UserGroupLink]
        The group and membership link (injected, requires group membership).

    Returns
    -------
    GroupRead
        The requested group.
    """
    group, _link = member
    return GroupRead.model_validate(group)


@router.patch("/{group_id}", response_model=GroupRead)
async def update_group(
    body: GroupUpdate,
    session: SessionDep,
    member: GroupAdminDep,
) -> GroupRead:
    """Update a group's name or description.

    Parameters
    ----------
    body : GroupUpdate
        Fields to update.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and membership link (injected, requires admin role).

    Returns
    -------
    GroupRead
        The updated group.
    """
    group, _link = member
    updated = await group_service.update_group(
        session,
        group,
        name=body.name,
        description=body.description,
    )
    return GroupRead.model_validate(updated)


@router.post(
    "/{group_id}/members",
    response_model=MemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    body: MemberAdd,
    session: SessionDep,
    member: GroupAdminDep,
) -> MemberRead:
    """Add a user to the group.

    Parameters
    ----------
    body : MemberAdd
        The user to add and their role.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and admin membership link (injected, requires admin role).

    Returns
    -------
    MemberRead
        The new membership details including user email.

    Raises
    ------
    HTTPException
        409 if the user is already a member.
        404 if the target user does not exist.
    """
    group, _link = member
    target_user = await session.get(User, body.user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    try:
        link = await group_service.add_member(
            session,
            group.id,
            body.user_id,
            is_admin=body.is_admin,
        )
    except MemberExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this group",
        )
    return MemberRead(
        user_id=link.user_id,
        group_id=link.group_id,
        is_admin=link.is_admin,
        joined_at=link.joined_at,
        email=target_user.email,
    )


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    user_id: UUID,
    session: SessionDep,
    member: GroupAdminDep,
) -> None:
    """Remove a user from the group.

    Parameters
    ----------
    user_id : UUID
        The ID of the user to remove.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and admin membership link (injected, requires admin role).

    Raises
    ------
    HTTPException
        404 if the user is not a member of the group.
    """
    group, _link = member
    try:
        await group_service.remove_member(session, group.id, user_id)
    except MemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this group",
        )


@router.patch("/{group_id}/members/{user_id}", response_model=MemberRead)
async def update_member_role(
    user_id: UUID,
    body: MemberUpdate,
    session: SessionDep,
    member: GroupAdminDep,
) -> MemberRead:
    """Update a group member's admin role.

    Parameters
    ----------
    user_id : UUID
        The ID of the member to update.
    body : MemberUpdate
        The new role data.
    session : AsyncSession
        The database session (injected).
    member : tuple[Group, UserGroupLink]
        The group and admin membership link (injected, requires admin role).

    Returns
    -------
    MemberRead
        The updated membership details.

    Raises
    ------
    HTTPException
        404 if the user is not a member or does not exist.
    """
    group, _link = member
    target_user = await session.get(User, user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    try:
        link = await group_service.update_member_role(
            session,
            group.id,
            user_id,
            is_admin=body.is_admin,
        )
    except MemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this group",
        )
    return MemberRead(
        user_id=link.user_id,
        group_id=link.group_id,
        is_admin=link.is_admin,
        joined_at=link.joined_at,
        email=target_user.email,
    )
