import pytest

from chaima.services import projects as svc


@pytest.mark.asyncio
async def test_create_project(session, group):
    p = await svc.create_project(session, group_id=group.id, name="Catalysis")
    assert p.name == "Catalysis"
    assert p.is_archived is False


@pytest.mark.asyncio
async def test_create_project_dedupes_case_insensitively(session, group):
    p1 = await svc.create_project(session, group_id=group.id, name="Catalysis")
    p2 = await svc.create_project(session, group_id=group.id, name="catalysis")
    assert p1.id == p2.id


@pytest.mark.asyncio
async def test_archive_and_list_excludes_archived(session, group):
    p = await svc.create_project(session, group_id=group.id, name="X")
    await svc.archive_project(session, p)

    active = await svc.list_projects(session, group_id=group.id, include_archived=False)
    assert active == []
    all_ = await svc.list_projects(session, group_id=group.id, include_archived=True)
    assert len(all_) == 1
