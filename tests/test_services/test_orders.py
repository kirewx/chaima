import datetime
from decimal import Decimal

import pytest

from chaima.models.group import Group
from chaima.models.supplier import Supplier
from chaima.services import orders as svc
from chaima.services import projects as proj_svc


@pytest.mark.asyncio
async def test_create_order(session, group, chemical, supplier, user):
    project = await proj_svc.create_project(session, group_id=group.id, name="Cat")

    order = await svc.create_order(
        session,
        group_id=group.id,
        chemical_id=chemical.id,
        supplier_id=supplier.id,
        project_id=project.id,
        amount_per_package=100.0,
        unit="mL",
        package_count=3,
        price_per_package=Decimal("25.00"),
        currency="EUR",
        ordered_by_user_id=user.id,
    )
    assert order.id is not None
    assert order.status.value == "ordered"
    assert order.package_count == 3


@pytest.mark.asyncio
async def test_create_order_rejects_cross_group_supplier(session, group, chemical, user):
    """A supplier from a different group must not be accepted."""
    other = Group(name="OtherLab")
    session.add(other)
    await session.flush()
    foreign_supplier = Supplier(name="Foreign", group_id=other.id)
    session.add(foreign_supplier)
    await session.flush()

    project = await proj_svc.create_project(session, group_id=group.id, name="Cat")

    with pytest.raises(svc.CrossGroupReferenceError):
        await svc.create_order(
            session,
            group_id=group.id,
            chemical_id=chemical.id,
            supplier_id=foreign_supplier.id,
            project_id=project.id,
            amount_per_package=100.0,
            unit="mL",
            package_count=1,
            ordered_by_user_id=user.id,
        )
