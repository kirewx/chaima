# tests/test_services/test_containers.py
import pytest

from chaima.models.storage import StorageKind, StorageLocation, StorageLocationGroup
from chaima.models.supplier import Supplier
from chaima.services import containers as container_service


@pytest.fixture
def _storage_and_supplier(session, group):
    """Helper to create storage location and supplier for tests."""

    async def _create():
        loc = StorageLocation(name="Room A", kind=StorageKind.ROOM)
        session.add(loc)
        await session.flush()
        session.add(StorageLocationGroup(location_id=loc.id, group_id=group.id))

        sup = Supplier(name="Sigma", group_id=group.id)
        session.add(sup)
        await session.flush()
        return loc, sup

    return _create


async def test_create_container(session, group, user, chemical, _storage_and_supplier):
    """Test that a container can be created with expected defaults."""
    loc, sup = await _storage_and_supplier()
    container = await container_service.create_container(
        session,
        chemical_id=chemical.id,
        location_id=loc.id,
        supplier_id=sup.id,
        identifier="ETH-001",
        amount=500.0,
        unit="mL",
        created_by=user.id,
    )
    await session.commit()
    assert container.identifier == "ETH-001"
    assert container.amount == 500.0
    assert container.is_archived is False


async def test_list_containers_group(session, group, user, chemical, _storage_and_supplier):
    """Test that list_containers returns containers belonging to the group."""
    loc, _ = await _storage_and_supplier()
    await container_service.create_container(
        session,
        chemical_id=chemical.id,
        location_id=loc.id,
        identifier="ETH-001",
        amount=500.0,
        unit="mL",
        created_by=user.id,
    )
    await session.commit()
    items, total = await container_service.list_containers(session, group_id=group.id)
    assert total == 1


async def test_list_containers_excludes_archived(session, group, user, chemical, _storage_and_supplier):
    """Test that archived containers are excluded from the default listing."""
    loc, _ = await _storage_and_supplier()
    c = await container_service.create_container(
        session,
        chemical_id=chemical.id,
        location_id=loc.id,
        identifier="ETH-001",
        amount=500.0,
        unit="mL",
        created_by=user.id,
    )
    await session.flush()
    await container_service.archive_container(session, c)
    await session.commit()

    items, total = await container_service.list_containers(session, group_id=group.id)
    assert total == 0

    items, total = await container_service.list_containers(
        session, group_id=group.id, is_archived=True
    )
    assert total == 1


async def test_archive_container(session, group, user, chemical, _storage_and_supplier):
    """Test that archiving a container sets is_archived to True."""
    loc, _ = await _storage_and_supplier()
    c = await container_service.create_container(
        session,
        chemical_id=chemical.id,
        location_id=loc.id,
        identifier="ETH-001",
        amount=500.0,
        unit="mL",
        created_by=user.id,
    )
    await session.commit()
    await container_service.archive_container(session, c)
    await session.commit()
    assert c.is_archived is True


async def test_list_containers_by_chemical(session, group, user, chemical, _storage_and_supplier):
    """Test filtering containers by chemical_id."""
    loc, _ = await _storage_and_supplier()
    await container_service.create_container(
        session,
        chemical_id=chemical.id,
        location_id=loc.id,
        identifier="ETH-001",
        amount=500.0,
        unit="mL",
        created_by=user.id,
    )
    await session.commit()
    items, total = await container_service.list_containers(
        session, group_id=group.id, chemical_id=chemical.id
    )
    assert total == 1
