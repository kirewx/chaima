import pytest
from sqlalchemy.exc import IntegrityError

from chaima.models.project import Project


@pytest.mark.asyncio
async def test_project_can_be_inserted(session, group):
    p = Project(group_id=group.id, name="Catalysis")
    session.add(p)
    await session.flush()

    assert p.id is not None
    assert p.is_archived is False
    assert p.created_at is not None


@pytest.mark.asyncio
async def test_project_unique_within_group(session, group):
    session.add(Project(group_id=group.id, name="General"))
    await session.flush()
    session.add(Project(group_id=group.id, name="General"))
    with pytest.raises(IntegrityError):
        await session.flush()
