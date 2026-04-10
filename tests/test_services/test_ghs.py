# tests/test_services/test_ghs.py
import pytest

from chaima.services import ghs as ghs_service


async def test_create_ghs_code(session):
    code = await ghs_service.create_ghs_code(
        session, code="H300", description="Fatal if swallowed"
    )
    await session.commit()
    assert code.code == "H300"
    assert code.description == "Fatal if swallowed"
    assert code.id is not None


async def test_create_ghs_code_duplicate(session):
    await ghs_service.create_ghs_code(session, code="H300", description="Fatal if swallowed")
    await session.commit()
    with pytest.raises(ghs_service.DuplicateCodeError):
        await ghs_service.create_ghs_code(session, code="H300", description="Duplicate")


async def test_list_ghs_codes(session):
    await ghs_service.create_ghs_code(session, code="H300", description="Fatal if swallowed")
    await ghs_service.create_ghs_code(session, code="H310", description="Fatal in contact with skin")
    await session.commit()
    items, total = await ghs_service.list_ghs_codes(session)
    assert total == 2
    assert len(items) == 2


async def test_list_ghs_codes_search(session):
    await ghs_service.create_ghs_code(session, code="H300", description="Fatal if swallowed")
    await ghs_service.create_ghs_code(session, code="H310", description="Fatal in contact with skin")
    await session.commit()
    items, total = await ghs_service.list_ghs_codes(session, search="H300")
    assert total == 1
    assert items[0].code == "H300"


async def test_update_ghs_code(session):
    code = await ghs_service.create_ghs_code(session, code="H300", description="Fatal if swallowed")
    await session.commit()
    updated = await ghs_service.update_ghs_code(session, code, description="Updated description")
    await session.commit()
    assert updated.description == "Updated description"
