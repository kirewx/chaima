import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from chaima.models.group import Group, UserGroupLink


async def test_create_group(session):
    group = Group(name="Lab Beta")
    session.add(group)
    await session.commit()

    result = await session.get(Group, group.id)
    assert result is not None
    assert result.name == "Lab Beta"
    assert result.id is not None
    assert result.created_at is not None


async def test_group_name_unique(session):
    session.add(Group(name="Lab Beta"))
    await session.commit()

    session.add(Group(name="Lab Beta"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_create_user_group_link(session, group):
    user_id = uuid.uuid4()
    link = UserGroupLink(user_id=user_id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.commit()

    result = (await session.exec(
        select(UserGroupLink).where(UserGroupLink.user_id == user_id)
    )).one()
    assert result.group_id == group.id
    assert result.is_admin is True
    assert result.joined_at is not None
