# tests/test_services/test_suppliers.py
from chaima.services import suppliers as supplier_service


async def test_create_supplier(session, group):
    supplier = await supplier_service.create_supplier(session, group_id=group.id, name="Sigma")
    await session.commit()
    assert supplier.name == "Sigma"
    assert supplier.group_id == group.id


async def test_create_supplier_dedupes_case_insensitive(session, group):
    first = await supplier_service.create_supplier(
        session, group_id=group.id, name="Sigma Aldrich"
    )
    await session.commit()
    again = await supplier_service.create_supplier(
        session, group_id=group.id, name="sIgma alDrich"
    )
    await session.commit()
    assert again.id == first.id
    assert again.name == "Sigma Aldrich"  # original casing preserved

    items, total = await supplier_service.list_suppliers(session, group_id=group.id)
    assert total == 1


async def test_create_supplier_trims_whitespace(session, group):
    supplier = await supplier_service.create_supplier(
        session, group_id=group.id, name="  Merck  "
    )
    await session.commit()
    assert supplier.name == "Merck"


async def test_list_suppliers(session, group):
    await supplier_service.create_supplier(session, group_id=group.id, name="Sigma")
    await supplier_service.create_supplier(session, group_id=group.id, name="Merck")
    await session.commit()
    items, total = await supplier_service.list_suppliers(session, group_id=group.id)
    assert total == 2


async def test_list_suppliers_search(session, group):
    await supplier_service.create_supplier(session, group_id=group.id, name="Sigma")
    await supplier_service.create_supplier(session, group_id=group.id, name="Merck")
    await session.commit()
    items, total = await supplier_service.list_suppliers(session, group_id=group.id, search="Sig")
    assert total == 1
    assert items[0].name == "Sigma"


async def test_update_supplier(session, group):
    supplier = await supplier_service.create_supplier(session, group_id=group.id, name="Sigma")
    await session.commit()
    updated = await supplier_service.update_supplier(session, supplier, name="Sigma-Aldrich")
    await session.commit()
    assert updated.name == "Sigma-Aldrich"


async def test_delete_supplier(session, group):
    supplier = await supplier_service.create_supplier(session, group_id=group.id, name="Sigma")
    await session.commit()
    await supplier_service.delete_supplier(session, supplier)
    await session.commit()
    result = await supplier_service.get_supplier(session, supplier.id)
    assert result is None
