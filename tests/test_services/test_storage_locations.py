# tests/test_services/test_storage_locations.py
import pytest

from chaima.models.storage import StorageKind, StorageLocation, StorageLocationGroup
from chaima.services import storage_locations as storage_service


async def test_create_location(session, group):
    loc = await storage_service.create_location(
        session, group_id=group.id, name="Building A", kind=StorageKind.BUILDING
    )
    await session.commit()
    assert loc.name == "Building A"
    assert loc.parent_id is None


async def test_create_child_location(session, group):
    parent = await storage_service.create_location(
        session, group_id=group.id, name="Building A", kind=StorageKind.BUILDING
    )
    await session.flush()
    child = await storage_service.create_location(
        session, group_id=group.id, name="Room 1", kind=StorageKind.ROOM, parent_id=parent.id
    )
    await session.commit()
    assert child.parent_id == parent.id


async def test_get_tree(session, group):
    building = await storage_service.create_location(
        session, group_id=group.id, name="Building A", kind=StorageKind.BUILDING
    )
    await session.flush()
    room = await storage_service.create_location(
        session, group_id=group.id, name="Room 1", kind=StorageKind.ROOM, parent_id=building.id
    )
    await session.commit()

    tree = await storage_service.get_tree(session, group.id)
    assert len(tree) == 1
    assert tree[0].name == "Building A"
    assert len(tree[0].children) == 1
    assert tree[0].children[0].name == "Room 1"


async def test_update_location(session, group):
    loc = await storage_service.create_location(
        session, group_id=group.id, name="Building A", kind=StorageKind.BUILDING
    )
    await session.commit()
    updated = await storage_service.update_location(session, loc, name="Building B")
    await session.commit()
    assert updated.name == "Building B"


async def test_delete_location(session, group):
    loc = await storage_service.create_location(
        session, group_id=group.id, name="Building A", kind=StorageKind.BUILDING
    )
    await session.commit()
    await storage_service.delete_location(session, loc)
    await session.commit()
    result = await storage_service.get_location(session, loc.id)
    assert result is None


async def test_delete_location_with_containers_fails(session, group, user, chemical):
    from chaima.models.container import Container

    loc = await storage_service.create_location(
        session, group_id=group.id, name="Building A", kind=StorageKind.BUILDING
    )
    await session.flush()
    session.add(Container(
        chemical_id=chemical.id,
        location_id=loc.id,
        identifier="ETH-001",
        amount=500.0,
        unit="mL",
        created_by=user.id,
    ))
    await session.commit()

    with pytest.raises(storage_service.LocationHasContainersError):
        await storage_service.delete_location(session, loc)
