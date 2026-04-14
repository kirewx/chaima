# tests/test_api/test_storage_locations.py
from chaima.models.storage import StorageKind, StorageLocation, StorageLocationGroup
from chaima.schemas.storage import StorageLocationNode, StorageLocationRead


async def test_create_location(client, session, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/storage-locations",
        json={"name": "Room A"},
    )
    assert resp.status_code == 201
    result = StorageLocationRead.model_validate(resp.json())
    assert result.name == "Room A"


async def test_get_tree(client, session, group, membership):
    room = StorageLocation(name="Room A", kind=StorageKind.ROOM)
    session.add(room)
    await session.flush()
    session.add(StorageLocationGroup(location_id=room.id, group_id=group.id))

    shelf = StorageLocation(name="Shelf 1", kind=StorageKind.SHELF, parent_id=room.id)
    session.add(shelf)
    await session.flush()
    session.add(StorageLocationGroup(location_id=shelf.id, group_id=group.id))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/storage-locations")
    assert resp.status_code == 200
    tree = [StorageLocationNode.model_validate(n) for n in resp.json()]
    assert len(tree) == 1
    assert tree[0].name == "Room A"
    assert len(tree[0].children) == 1
    assert tree[0].children[0].name == "Shelf 1"


async def test_delete_location(client, session, group, membership):
    loc = StorageLocation(name="Room A", kind=StorageKind.ROOM)
    session.add(loc)
    await session.flush()
    session.add(StorageLocationGroup(location_id=loc.id, group_id=group.id))
    await session.commit()

    resp = await client.delete(f"/api/v1/groups/{group.id}/storage-locations/{loc.id}")
    assert resp.status_code == 204
