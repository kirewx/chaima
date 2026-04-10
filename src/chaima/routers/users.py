"""Router for custom user endpoints (beyond fastapi-users defaults)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select

from chaima.dependencies import CurrentUserDep, SessionDep
from chaima.models.group import UserGroupLink
from chaima.schemas.user import UserRead


class MainGroupUpdate(BaseModel):
    """Schema for updating a user's main group.

    Attributes
    ----------
    group_id : UUID
        The ID of the group to set as the user's main group.
    """

    group_id: UUID


router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.patch("/me/main-group", response_model=UserRead)
async def update_main_group(
    body: MainGroupUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> UserRead:
    """Update the current user's main group.

    Parameters
    ----------
    body : MainGroupUpdate
        The group ID to set as main group.
    session : AsyncSession
        The database session (injected).
    current_user : User
        The authenticated user (injected).

    Returns
    -------
    UserRead
        The updated user.

    Raises
    ------
    HTTPException
        403 if the user is not a member of the target group.
    """
    result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == current_user.id,
            UserGroupLink.group_id == body.group_id,
        )
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group",
        )
    current_user.main_group_id = body.group_id
    session.add(current_user)
    await session.flush()
    return UserRead.model_validate(current_user)
