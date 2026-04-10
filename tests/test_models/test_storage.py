from sqlmodel import select

from chaima.models.group import Group
from chaima.models.storage import StorageLocation, StorageLocationGroup


async def test_create_root_location(session):
    loc = StorageLocation(name="Room B")
    session.add(loc)
    await session.commit()

    result = await session.get(StorageLocation, loc.id)
    assert result.name == "Room B"
    assert result.parent_id is None


async def test_create_nested_location(session, storage_location):
    shelf = StorageLocation(name="Shelf 1", parent_id=storage_location.id)
    session.add(shelf)
    await session.flush()

    bottom = StorageLocation(name="Bottom", parent_id=shelf.id)
    session.add(bottom)
    await session.commit()

    result = await session.get(StorageLocation, bottom.id)
    assert result.parent_id == shelf.id


async def test_assign_location_to_group(session, group, storage_location):
    link = StorageLocationGroup(location_id=storage_location.id, group_id=group.id)
    session.add(link)
    await session.commit()

    result = (await session.exec(
        select(StorageLocationGroup).where(StorageLocationGroup.group_id == group.id)
    )).all()
    assert len(result) == 1
    assert result[0].location_id == storage_location.id


async def test_location_shared_across_groups(session, storage_location):
    g1 = Group(name="Lab X")
    g2 = Group(name="Lab Y")
    session.add_all([g1, g2])
    await session.flush()

    session.add_all([
        StorageLocationGroup(location_id=storage_location.id, group_id=g1.id),
        StorageLocationGroup(location_id=storage_location.id, group_id=g2.id),
    ])
    await session.commit()

    result = (await session.exec(
        select(StorageLocationGroup).where(
            StorageLocationGroup.location_id == storage_location.id
        )
    )).all()
    assert len(result) == 2
