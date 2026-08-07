"""Permission rule for admin-issued password reset links.

Issuing a reset link is equivalent to handing over the account, so the
rule here is deliberately stricter than plain group-admin rights.
"""

import uuid as uuid_pkg

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import UserGroupLink
from chaima.models.user import User


class ResetNotPermittedError(Exception):
    """Raised when the actor may not reset the target user's password."""


async def _group_ids(
    session: AsyncSession, user_id: uuid_pkg.UUID, *, admin_only: bool
) -> set[uuid_pkg.UUID]:
    """Collect the group IDs a user belongs to, optionally only as admin."""
    statement = select(UserGroupLink.group_id).where(UserGroupLink.user_id == user_id)
    if admin_only:
        statement = statement.where(UserGroupLink.is_admin == True)  # noqa: E712
    result = await session.exec(statement)
    return set(result.all())


async def assert_may_reset(
    session: AsyncSession,
    *,
    actor: User,
    target: User,
) -> None:
    """Check whether ``actor`` may issue a reset link for ``target``.

    A user may belong to several groups. If an administrator of one group
    could reset any member, they would gain that member's access to every
    other group as well — so the target's memberships must be fully covered
    by the groups the actor administers.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    actor : User
        The user requesting the reset link.
    target : User
        The user whose password would be reset.

    Raises
    ------
    ResetNotPermittedError
        If the actor may not reset this target.
    """
    if actor.is_superuser:
        return

    if target.is_superuser:
        # This message tells a group admin the target is a superuser, which
        # MemberRead never exposes — a deliberate trade, not an oversight.
        # ChAiMa's admins are trusted lab colleagues, so the leak has little
        # protective value here, and the explanatory wording is worth more.
        raise ResetNotPermittedError(
            "Only a superuser can reset another superuser's password"
        )

    target_groups = await _group_ids(session, target.id, admin_only=False)
    actor_admin_groups = await _group_ids(session, actor.id, admin_only=True)

    if not target_groups <= actor_admin_groups:
        raise ResetNotPermittedError(
            "This user belongs to a group you do not administer, "
            "so you cannot reset their password"
        )
