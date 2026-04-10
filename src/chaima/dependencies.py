from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.auth import current_active_user, current_superuser
from chaima.db import get_async_session
from chaima.models.group import Group, UserGroupLink
from chaima.models.user import User


async def get_group_member(
    group_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> tuple[Group, UserGroupLink]:
    """Verify user belongs to group.

    Returns
    -------
    tuple[Group, UserGroupLink]
        The group and the user's membership link.

    Raises
    ------
    HTTPException
        404 if group not found, 403 if user is not a member.
    """
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    if user.is_superuser:
        link = UserGroupLink(
            user_id=user.id, group_id=group.id, is_admin=True
        )
        return group, link

    result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == user.id,
            UserGroupLink.group_id == group_id,
        )
    )
    link = result.first()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group",
        )
    return group, link


async def get_group_admin(
    member: tuple[Group, UserGroupLink] = Depends(get_group_member),
) -> tuple[Group, UserGroupLink]:
    """Verify user is admin of the group.

    Returns
    -------
    tuple[Group, UserGroupLink]
        The group and the user's membership link.

    Raises
    ------
    HTTPException
        403 if user is not an admin.
    """
    _group, link = member
    if not link.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return member


SessionDep = Annotated[AsyncSession, Depends(get_async_session)]
CurrentUserDep = Annotated[User, Depends(current_active_user)]
SuperuserDep = Annotated[User, Depends(current_superuser)]
GroupMemberDep = Annotated[tuple[Group, UserGroupLink], Depends(get_group_member)]
GroupAdminDep = Annotated[tuple[Group, UserGroupLink], Depends(get_group_admin)]
