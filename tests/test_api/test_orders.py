import pytest


async def _make_project(client, group_id, name="P"):
    return (await client.post(f"/api/v1/groups/{group_id}/projects", json={"name": name})).json()


@pytest.mark.asyncio
async def test_create_order_returns_201(client, group, chemical, supplier, membership):
    project = await _make_project(client, group.id)
    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id),
            "supplier_id": str(supplier.id),
            "project_id": project["id"],
            "amount_per_package": 100.0,
            "unit": "mL",
            "package_count": 3,
            "currency": "EUR",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ordered"
    assert body["package_count"] == 3
    assert body["chemical_name"] == chemical.name
    assert body["supplier_name"] == supplier.name


@pytest.mark.asyncio
async def test_receive_order_spawns_containers(
    client, session, group, chemical, supplier, membership, storage_location
):
    from chaima.models.storage import StorageLocationGroup
    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))
    await session.flush()

    project = await _make_project(client, group.id)
    create_resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id), "supplier_id": str(supplier.id),
            "project_id": project["id"], "amount_per_package": 50.0, "unit": "g",
            "package_count": 2,
        },
    )
    order_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order_id}/receive",
        json={
            "containers": [
                {"identifier": "lot-1", "storage_location_id": str(storage_location.id)},
                {"identifier": "lot-2", "storage_location_id": str(storage_location.id)},
            ]
        },
    )
    assert resp.status_code == 200
    spawned = resp.json()
    assert len(spawned) == 2

    # Order is now received (verify via GET)
    g = await client.get(f"/api/v1/groups/{group.id}/orders/{order_id}")
    assert g.json()["status"] == "received"


@pytest.mark.asyncio
async def test_receive_count_mismatch_returns_400(
    client, session, group, chemical, supplier, membership, storage_location
):
    from chaima.models.storage import StorageLocationGroup
    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))
    await session.flush()

    project = await _make_project(client, group.id)
    create_resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id), "supplier_id": str(supplier.id),
            "project_id": project["id"], "amount_per_package": 50.0, "unit": "g",
            "package_count": 3,
        },
    )
    order_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order_id}/receive",
        json={"containers": [
            {"identifier": "lot-1", "storage_location_id": str(storage_location.id)},
        ]},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cancel_by_creator(client, group, chemical, supplier, membership):
    project = await _make_project(client, group.id)
    create_resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id), "supplier_id": str(supplier.id),
            "project_id": project["id"], "amount_per_package": 1.0, "unit": "g",
            "package_count": 1,
        },
    )
    order_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order_id}/cancel",
        json={"cancellation_reason": "no longer needed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_forbidden_for_other_non_admin_member(
    client, session, group, chemical, supplier, membership
):
    """A non-admin member who didn't create the order cannot cancel it."""
    from uuid import UUID, uuid4
    from chaima.models.order import Order

    project = await _make_project(client, group.id)
    other_user_id = uuid4()
    order = Order(
        group_id=group.id,
        chemical_id=chemical.id,
        supplier_id=supplier.id,
        project_id=UUID(project["id"]),
        amount_per_package=1.0,
        unit="g",
        package_count=1,
        ordered_by_user_id=other_user_id,
    )
    session.add(order)
    await session.commit()

    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order.id}/cancel",
        json={"cancellation_reason": "not mine"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cancel_as_admin(client, group, chemical, supplier, admin_membership):
    project = await _make_project(client, group.id)
    create_resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id), "supplier_id": str(supplier.id),
            "project_id": project["id"], "amount_per_package": 1.0, "unit": "g",
            "package_count": 1,
        },
    )
    order_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order_id}/cancel",
        json={"cancellation_reason": "no longer needed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
