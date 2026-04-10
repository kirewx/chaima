"""Service layer for invite link operations."""

import datetime
from uuid import UUID

from fastapi_users.password import PasswordHelper
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import UserGroupLink
from chaima.models.invite import Invite
from chaima.models.user import User


class InviteExpiredError(Exception):
    """Raised when an invite has expired."""


class InviteUsedError(Exception):
    """Raised when an invite has already been used."""


password_helper = PasswordHelper()


async def create_invite(
    session: AsyncSession,
    *,
    group_id: UUID,
    created_by: UUID,
) -> Invite:
    """Create a new single-use invite for a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to invite to.
    created_by : UUID
        The admin creating the invite.

    Returns
    -------
    Invite
        The newly created invite.
    """
    invite = Invite(group_id=group_id, created_by=created_by)
    session.add(invite)
    await session.flush()
    return invite


async def get_invite_by_token(
    session: AsyncSession,
    token: str,
) -> Invite | None:
    """Look up an invite by its token.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    token : str
        The invite token string.

    Returns
    -------
    Invite or None
        The invite if found, otherwise None.
    """
    result = await session.exec(select(Invite).where(Invite.token == token))
    return result.first()


def _validate_invite(invite: Invite) -> None:
    """Check that an invite is still usable.

    Raises
    ------
    InviteUsedError
        If the invite has already been accepted.
    InviteExpiredError
        If the invite has expired.
    """
    if invite.used_by is not None:
        raise InviteUsedError("This invite has already been used")
    if invite.expires_at < datetime.datetime.now(datetime.UTC):
        raise InviteExpiredError("This invite has expired")


async def accept_invite_new_user(
    session: AsyncSession,
    *,
    invite: Invite,
    email: str,
    password: str,
) -> User:
    """Accept an invite by creating a new user account.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    invite : Invite
        The invite to accept.
    email : str
        Email for the new account.
    password : str
        Password for the new account.

    Returns
    -------
    User
        The newly created user.

    Raises
    ------
    InviteExpiredError
        If the invite has expired.
    InviteUsedError
        If the invite has already been used.
    """
    _validate_invite(invite)

    hashed = password_helper.hash(password)
    user = User(
        email=email,
        hashed_password=hashed,
        is_active=True,
        is_superuser=False,
        is_verified=True,
        main_group_id=invite.group_id,
    )
    session.add(user)
    await session.flush()

    link = UserGroupLink(user_id=user.id, group_id=invite.group_id)
    session.add(link)

    invite.used_by = user.id
    invite.used_at = datetime.datetime.now(datetime.UTC)
    session.add(invite)
    await session.flush()

    return user


async def accept_invite_existing_user(
    session: AsyncSession,
    *,
    invite: Invite,
    user: User,
) -> None:
    """Accept an invite for an existing user (adds them to the group).

    Parameters
    ----------
    session : AsyncSession
        The database session.
    invite : Invite
        The invite to accept.
    user : User
        The existing authenticated user.

    Raises
    ------
    InviteExpiredError
        If the invite has expired.
    InviteUsedError
        If the invite has already been used.
    """
    _validate_invite(invite)

    link = UserGroupLink(user_id=user.id, group_id=invite.group_id)
    session.add(link)

    invite.used_by = user.id
    invite.used_at = datetime.datetime.now(datetime.UTC)
    session.add(invite)
    await session.flush()


async def list_invites(
    session: AsyncSession,
    group_id: UUID,
) -> list[Invite]:
    """List all invites for a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to list invites for.

    Returns
    -------
    list[Invite]
        All invites for the group.
    """
    result = await session.exec(
        select(Invite).where(Invite.group_id == group_id)
    )
    return list(result.all())


async def revoke_invite(
    session: AsyncSession,
    invite: Invite,
) -> None:
    """Delete an unused invite.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    invite : Invite
        The invite to revoke.
    """
    await session.delete(invite)
    await session.flush()
