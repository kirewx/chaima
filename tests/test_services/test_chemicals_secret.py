import pytest
from sqlmodel import select

from chaima.models.chemical import Chemical
from chaima.services.chemicals import apply_secret_filter


async def test_non_creator_does_not_see_secret(session, group, user, other_user):
    secret = Chemical(
        name="Secret X",
        group_id=group.id,
        created_by=user.id,
        is_secret=True,
    )
    public = Chemical(
        name="Public Y",
        group_id=group.id,
        created_by=user.id,
        is_secret=False,
    )
    session.add_all([secret, public])
    await session.commit()

    stmt = select(Chemical).where(Chemical.group_id == group.id)
    stmt = apply_secret_filter(stmt, viewer=other_user)
    result = await session.exec(stmt)
    names = sorted(r.name for r in result.all())
    assert names == ["Public Y"]


async def test_creator_sees_own_secret(session, group, user):
    secret = Chemical(
        name="Secret X",
        group_id=group.id,
        created_by=user.id,
        is_secret=True,
    )
    session.add(secret)
    await session.commit()

    stmt = select(Chemical).where(Chemical.group_id == group.id)
    stmt = apply_secret_filter(stmt, viewer=user)
    result = await session.exec(stmt)
    assert [r.name for r in result.all()] == ["Secret X"]


async def test_superuser_sees_all_secrets(session, group, user, superuser):
    secret = Chemical(
        name="Secret X",
        group_id=group.id,
        created_by=user.id,
        is_secret=True,
    )
    session.add(secret)
    await session.commit()

    stmt = select(Chemical).where(Chemical.group_id == group.id)
    stmt = apply_secret_filter(stmt, viewer=superuser)
    result = await session.exec(stmt)
    assert [r.name for r in result.all()] == ["Secret X"]
