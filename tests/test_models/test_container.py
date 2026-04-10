from sqlmodel import select

from chaima.models.chemical import Chemical  # noqa: F401 - ensures table is registered before create_all
from chaima.models.container import Container
from chaima.models.group import Group  # noqa: F401 - ensures table is registered before create_all
from chaima.models.storage import StorageLocation  # noqa: F401 - ensures table is registered before create_all
from chaima.models.supplier import Supplier  # noqa: F401 - ensures table is registered before create_all
from chaima.models.user import User  # noqa: F401 - ensures table is registered before create_all


async def test_create_container(session, chemical, storage_location, supplier, user):
    container = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        supplier_id=supplier.id,
        identifier="ETH-001",
        amount=500.0,
        unit="mL",
        created_by=user.id,
    )
    session.add(container)
    await session.commit()

    result = await session.get(Container, container.id)
    assert result.identifier == "ETH-001"
    assert result.amount == 500.0
    assert result.unit == "mL"
    assert result.is_archived is False


async def test_container_optional_supplier(session, chemical, storage_location, user):
    container = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        identifier="ETH-002",
        amount=1.0,
        unit="kg",
        created_by=user.id,
    )
    session.add(container)
    await session.commit()

    result = await session.get(Container, container.id)
    assert result.supplier_id is None


async def test_container_archive(session, chemical, storage_location, user):
    container = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        identifier="ETH-003",
        amount=100.0,
        unit="g",
        created_by=user.id,
        is_archived=True,
    )
    session.add(container)
    await session.commit()

    result = await session.get(Container, container.id)
    assert result.is_archived is True


async def test_filter_excludes_archived(session, chemical, storage_location, user):
    c1 = Container(chemical_id=chemical.id, location_id=storage_location.id,
                   identifier="A", amount=1.0, unit="mL", created_by=user.id)
    c2 = Container(chemical_id=chemical.id, location_id=storage_location.id,
                   identifier="B", amount=2.0, unit="mL", created_by=user.id,
                   is_archived=True)
    session.add_all([c1, c2])
    await session.commit()

    result = (await session.exec(
        select(Container).where(Container.is_archived == False)  # noqa: E712
    )).all()
    assert len(result) == 1
    assert result[0].identifier == "A"
