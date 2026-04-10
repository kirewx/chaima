import datetime

from chaima.models.user import User


async def test_create_user(session):
    u = User(
        email="bob@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    session.add(u)
    await session.commit()

    result = await session.get(User, u.id)
    assert result is not None
    assert result.email == "bob@example.com"
    assert result.is_superuser is False
    assert isinstance(result.created_at, datetime.datetime)
