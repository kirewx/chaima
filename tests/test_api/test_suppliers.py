# tests/test_api/test_suppliers.py
from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.storage import StorageLocation
from chaima.models.supplier import Supplier
from chaima.schemas.pagination import PaginatedResponse
from chaima.schemas.supplier import SupplierContainerRow, SupplierRead


async def test_create_supplier(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/suppliers",
        json={"name": "Sigma"},
    )
    assert resp.status_code == 201
    result = SupplierRead.model_validate(resp.json())
    assert result.name == "Sigma"
    assert result.container_count == 0


async def test_list_suppliers(client, session, group, membership):
    session.add(Supplier(name="Sigma", group_id=group.id))
    session.add(Supplier(name="Merck", group_id=group.id))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    assert resp.status_code == 200
    page = PaginatedResponse[SupplierRead].model_validate(resp.json())
    assert page.total == 2


async def test_list_suppliers_includes_container_count(
    client, session, group, user, membership
):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    chem = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, supplier_id=s.id,
        created_by=user.id, identifier="E-001", amount=1.0, unit="L",
    ))
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, supplier_id=s.id,
        created_by=user.id, identifier="E-002", amount=1.0, unit="L",
    ))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    assert resp.status_code == 200
    page = PaginatedResponse[SupplierRead].model_validate(resp.json())
    assert page.items[0].container_count == 2


async def test_get_supplier(client, session, group, membership):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers/{s.id}")
    assert resp.status_code == 200
    result = SupplierRead.model_validate(resp.json())
    assert result.name == "Sigma"


async def test_list_supplier_containers(
    client, session, group, user, membership
):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    chem = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, supplier_id=s.id,
        created_by=user.id, identifier="E-001", amount=1.0, unit="L",
    ))
    await session.commit()

    resp = await client.get(
        f"/api/v1/groups/{group.id}/suppliers/{s.id}/containers"
    )
    assert resp.status_code == 200
    rows = [SupplierContainerRow.model_validate(r) for r in resp.json()]
    assert len(rows) == 1
    assert rows[0].chemical_name == "Ethanol"
    assert rows[0].identifier == "E-001"


async def test_delete_supplier_as_admin(client, session, group, admin_membership):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    await session.commit()

    resp = await client.delete(f"/api/v1/groups/{group.id}/suppliers/{s.id}")
    assert resp.status_code == 204


async def test_delete_supplier_requires_admin(client, session, group, membership):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    await session.commit()

    resp = await client.delete(f"/api/v1/groups/{group.id}/suppliers/{s.id}")
    assert resp.status_code == 403


async def test_delete_supplier_with_containers_returns_409(
    client, session, group, user, admin_membership
):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    chem = Chemical(name="Ethanol", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, supplier_id=s.id,
        created_by=user.id, identifier="E-001", amount=1.0, unit="L",
    ))
    await session.commit()

    resp = await client.delete(f"/api/v1/groups/{group.id}/suppliers/{s.id}")
    assert resp.status_code == 409
    assert resp.json()["detail"]["container_count"] == 1


async def test_update_supplier_requires_admin(client, session, group, membership):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    await session.commit()

    resp = await client.patch(
        f"/api/v1/groups/{group.id}/suppliers/{s.id}",
        json={"name": "Sigma-Aldrich"},
    )
    assert resp.status_code == 403


async def test_not_member(client, group):
    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    assert resp.status_code == 403
