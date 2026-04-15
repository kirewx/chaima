# tests/test_api/test_storage_locations.py
from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.storage import StorageKind, StorageLocation, StorageLocationGroup
from chaima.schemas.storage import StorageLocationNode, StorageLocationRead


async def test_create_location(client, session, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/storage-locations",
        json={"name": "Building A", "kind": "building"},
    )
    assert resp.status_code == 201
    result = StorageLocationRead.model_validate(resp.json())
    assert result.name == "Building A"
    assert result.kind == StorageKind.BUILDING


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


async def test_create_building_room_cabinet_shelf(client, group, membership):
    r = await client.post(
        f"/api/v1/groups/{group.id}/storage-locations",
        json={"name": "Main", "kind": "building"},
    )
    assert r.status_code in (200, 201)
    building_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/groups/{group.id}/storage-locations",
        json={"name": "Lab 201", "kind": "room", "parent_id": building_id},
    )
    assert r.status_code in (200, 201)
    room_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/groups/{group.id}/storage-locations",
        json={"name": "A1", "kind": "cabinet", "parent_id": room_id},
    )
    assert r.status_code in (200, 201)

    # cabinet under building — rejected
    r = await client.post(
        f"/api/v1/groups/{group.id}/storage-locations",
        json={"name": "X", "kind": "cabinet", "parent_id": building_id},
    )
    assert r.status_code == 400
    assert "hierarchy" in r.json()["detail"].lower()


async def test_get_tree_exposes_kind_and_container_count(
    client, session, group, membership, user
):
    """Tree response surfaces kind, parent_id, and direct container_count."""
    room = StorageLocation(name="Room A", kind=StorageKind.ROOM)
    session.add(room)
    await session.flush()
    session.add(StorageLocationGroup(location_id=room.id, group_id=group.id))

    shelf = StorageLocation(name="Shelf 1", kind=StorageKind.SHELF, parent_id=room.id)
    session.add(shelf)
    await session.flush()
    session.add(StorageLocationGroup(location_id=shelf.id, group_id=group.id))

    chem = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    session.add(chem)
    await session.flush()

    session.add(
        Container(
            chemical_id=chem.id,
            location_id=shelf.id,
            identifier="ETH-001",
            amount=500.0,
            unit="mL",
            created_by=user.id,
        )
    )
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/storage-locations")
    assert resp.status_code == 200
    tree = [StorageLocationNode.model_validate(n) for n in resp.json()]
    assert len(tree) == 1
    room_node = tree[0]
    assert room_node.kind == StorageKind.ROOM
    assert room_node.parent_id is None
    assert room_node.container_count == 0
    assert len(room_node.children) == 1
    shelf_node = room_node.children[0]
    assert shelf_node.kind == StorageKind.SHELF
    assert shelf_node.parent_id == room_node.id
    assert shelf_node.container_count == 1
