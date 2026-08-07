"""Tests for the admin password-reset permission rule."""
import pytest

from chaima.models.group import Group, UserGroupLink
from chaima.services.password_reset import ResetNotPermittedError, assert_may_reset


async def _link(session, user, group, *, is_admin: bool) -> None:
    session.add(UserGroupLink(user_id=user.id, group_id=group.id, is_admin=is_admin))
    await session.flush()


@pytest.mark.asyncio
async def test_superuser_actor_is_always_permitted(session, superuser, other_user, group):
    """A superuser bypasses the subset rule entirely."""
    await _link(session, other_user, group, is_admin=False)

    await assert_may_reset(session, actor=superuser, target=other_user)


@pytest.mark.asyncio
async def test_superuser_target_is_refused(session, user, superuser, group):
    """A group admin must never be able to take over a superuser account."""
    await _link(session, user, group, is_admin=True)
    await _link(session, superuser, group, is_admin=True)

    with pytest.raises(ResetNotPermittedError):
        await assert_may_reset(session, actor=user, target=superuser)


@pytest.mark.asyncio
async def test_permitted_when_target_groups_are_subset(session, user, other_user, group):
    await _link(session, user, group, is_admin=True)
    await _link(session, other_user, group, is_admin=False)

    await assert_may_reset(session, actor=user, target=other_user)


@pytest.mark.asyncio
async def test_refused_when_target_is_in_an_unadministered_group(
    session, user, other_user, group
):
    """The escalation path this rule exists to close."""
    foreign = Group(name="Lab Beta")
    session.add(foreign)
    await session.flush()

    await _link(session, user, group, is_admin=True)
    await _link(session, other_user, group, is_admin=False)
    await _link(session, other_user, foreign, is_admin=False)

    with pytest.raises(ResetNotPermittedError):
        await assert_may_reset(session, actor=user, target=other_user)


@pytest.mark.asyncio
async def test_refused_when_actor_is_only_a_plain_member(session, user, other_user, group):
    """Membership is not enough — the actor must hold is_admin."""
    await _link(session, user, group, is_admin=False)
    await _link(session, other_user, group, is_admin=False)

    with pytest.raises(ResetNotPermittedError):
        await assert_may_reset(session, actor=user, target=other_user)


@pytest.mark.asyncio
async def test_permitted_when_target_has_no_memberships(session, user, other_user, group):
    """The empty set is a subset of anything.

    A user removed from every group is a real case, and refusing to reset
    them would leave the account unrecoverable.
    """
    await _link(session, user, group, is_admin=True)

    await assert_may_reset(session, actor=user, target=other_user)
