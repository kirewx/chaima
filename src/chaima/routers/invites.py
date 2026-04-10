"""Router for invite link endpoints."""

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from chaima.auth import optional_current_user
from chaima.dependencies import GroupAdminDep, SessionDep, SuperuserDep
from chaima.models.group import Group
from chaima.models.invite import Invite
from chaima.models.user import User
from chaima.schemas.invite import InviteAccept, InviteInfo, InviteRead
from chaima.services import invites as invite_service
from chaima.services.invites import InviteExpiredError, InviteUsedError

router = APIRouter(tags=["invites"])


@router.post(
    "/api/v1/groups/{group_id}/invites",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    session: SessionDep,
    member: GroupAdminDep,
) -> InviteRead:
    """Create a single-use invite link for this group.

    Parameters
    ----------
    session : SessionDep
        The database session.
    member : GroupAdminDep
        The group and the admin's membership link.

    Returns
    -------
    InviteRead
        The newly created invite.
    """
    group, link = member
    invite = await invite_service.create_invite(
        session, group_id=group.id, created_by=link.user_id
    )
    return InviteRead.model_validate(invite)


@router.get(
    "/api/v1/groups/{group_id}/invites",
    response_model=list[InviteRead],
)
async def list_invites(
    session: SessionDep,
    member: GroupAdminDep,
) -> list[InviteRead]:
    """List all invites for this group.

    Parameters
    ----------
    session : SessionDep
        The database session.
    member : GroupAdminDep
        The group and the admin's membership link.

    Returns
    -------
    list[InviteRead]
        All invites for the group.
    """
    group, _link = member
    invites = await invite_service.list_invites(session, group_id=group.id)
    return [InviteRead.model_validate(i) for i in invites]


@router.get("/api/v1/invites/{token}", response_model=InviteInfo)
async def get_invite_info(
    token: str,
    session: SessionDep,
) -> InviteInfo:
    """Get public info about an invite for the landing page.

    Parameters
    ----------
    token : str
        The invite token.
    session : SessionDep
        The database session.

    Returns
    -------
    InviteInfo
        Public invite information.

    Raises
    ------
    HTTPException
        404 if the invite is not found.
    """
    invite = await invite_service.get_invite_by_token(session, token)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    group = await session.get(Group, invite.group_id)
    is_valid = (
        invite.used_by is None
        and invite.expires_at > datetime.datetime.now(datetime.UTC)
    )
    return InviteInfo(
        group_name=group.name,
        expires_at=invite.expires_at,
        is_valid=is_valid,
    )


@router.patch("/api/v1/invites/{token}")
async def accept_invite(
    token: str,
    session: SessionDep,
    body: InviteAccept | None = None,
    user: User | None = Depends(optional_current_user),
) -> dict:
    """Accept an invite — register new user or join existing user to group.

    Parameters
    ----------
    token : str
        The invite token.
    session : SessionDep
        The database session.
    body : InviteAccept or None
        Credentials for new user registration (optional).
    user : User or None
        The currently authenticated user, if any.

    Returns
    -------
    dict
        A detail message and optionally the new user ID.

    Raises
    ------
    HTTPException
        404 if invite not found, 400 if expired or already used,
        422 if neither credentials nor session user is provided.
    """
    invite = await invite_service.get_invite_by_token(session, token)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )

    try:
        if user is not None:
            await invite_service.accept_invite_existing_user(
                session, invite=invite, user=user
            )
            return {"detail": "Joined group successfully"}
        elif body is not None:
            new_user = await invite_service.accept_invite_new_user(
                session, invite=invite, email=body.email, password=body.password
            )
            return {"detail": "Account created and joined group", "user_id": str(new_user.id)}
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Must provide credentials or be logged in",
            )
    except InviteExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invite has expired"
        )
    except InviteUsedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invite has already been used"
        )


@router.delete(
    "/api/v1/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_invite(
    invite_id: UUID,
    session: SessionDep,
    user: SuperuserDep,
) -> None:
    """Revoke an unused invite.

    Parameters
    ----------
    invite_id : UUID
        The invite ID to revoke.
    session : SessionDep
        The database session.
    user : SuperuserDep
        The authenticated superuser.

    Raises
    ------
    HTTPException
        404 if the invite is not found.
    """
    invite = await session.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    await invite_service.revoke_invite(session, invite)
