# tests/test_api/test_suppliers.py
from chaima.models.supplier import Supplier
from chaima.schemas.pagination import PaginatedResponse
from chaima.schemas.supplier import SupplierRead


async def test_create_supplier(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/suppliers",
        json={"name": "Sigma"},
    )
    assert resp.status_code == 201
    result = SupplierRead.model_validate(resp.json())
    assert result.name == "Sigma"


async def test_list_suppliers(client, session, group, membership):
    session.add(Supplier(name="Sigma", group_id=group.id))
    session.add(Supplier(name="Merck", group_id=group.id))
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    assert resp.status_code == 200
    page = PaginatedResponse[SupplierRead].model_validate(resp.json())
    assert page.total == 2


async def test_get_supplier(client, session, group, membership):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    await session.commit()

    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers/{s.id}")
    assert resp.status_code == 200
    result = SupplierRead.model_validate(resp.json())
    assert result.name == "Sigma"


async def test_delete_supplier(client, session, group, membership):
    s = Supplier(name="Sigma", group_id=group.id)
    session.add(s)
    await session.commit()

    resp = await client.delete(f"/api/v1/groups/{group.id}/suppliers/{s.id}")
    assert resp.status_code == 204


async def test_not_member(client, group):
    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    assert resp.status_code == 403
