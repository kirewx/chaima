import pytest

from chaima.models.container import Container
from chaima.models.order import Order, OrderStatus
from chaima.models.project import Project


@pytest.mark.asyncio
async def test_order_can_be_inserted(session, group, chemical, supplier, user):
    project = Project(group_id=group.id, name="Catalysis")
    session.add(project)
    await session.flush()

    order = Order(
        group_id=group.id,
        chemical_id=chemical.id,
        supplier_id=supplier.id,
        project_id=project.id,
        amount_per_package=100.0,
        unit="mL",
        package_count=3,
        ordered_by_user_id=user.id,
    )
    session.add(order)
    await session.flush()

    assert order.id is not None
    assert order.status == OrderStatus.ORDERED
    assert order.currency == "EUR"
    assert order.ordered_at is not None


@pytest.mark.asyncio
async def test_container_links_to_order(session, group, chemical, supplier, user, storage_location):
    project = Project(group_id=group.id, name="X")
    session.add(project)
    await session.flush()

    order = Order(
        group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=project.id, amount_per_package=100.0, unit="mL",
        package_count=1, ordered_by_user_id=user.id,
    )
    session.add(order)
    await session.flush()

    c = Container(
        chemical_id=chemical.id, location_id=storage_location.id,
        identifier="lot-1", amount=100.0, unit="mL",
        order_id=order.id, created_by=user.id,
    )
    session.add(c)
    await session.flush()
    assert c.order_id == order.id
