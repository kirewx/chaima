import pytest

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
