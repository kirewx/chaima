import datetime
from decimal import Decimal

import pytest

from chaima.models.group import Group
from chaima.models.storage import StorageLocationGroup
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


@pytest.mark.asyncio
async def test_list_orders_filters_by_status(session, group, chemical, supplier, user):
    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o1 = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
        ordered_by_user_id=user.id,
    )
    o2 = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=50, unit="g", package_count=2,
        ordered_by_user_id=user.id,
    )
    o2.status = svc.OrderStatus.CANCELLED
    session.add(o2)
    await session.flush()

    open_only = await svc.list_orders(session, group_id=group.id, status="ordered")
    assert {o.id for o in open_only} == {o1.id}

    cancelled = await svc.list_orders(session, group_id=group.id, status="cancelled")
    assert {o.id for o in cancelled} == {o2.id}

    all_ = await svc.list_orders(session, group_id=group.id)
    assert {o.id for o in all_} == {o1.id, o2.id}


@pytest.mark.asyncio
async def test_edit_order_blocked_after_received(session, group, chemical, supplier, user):
    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
        ordered_by_user_id=user.id,
    )
    o.status = svc.OrderStatus.RECEIVED
    session.add(o)
    await session.flush()

    with pytest.raises(svc.OrderStateError):
        await svc.edit_order(session, o, package_count=5)


@pytest.mark.asyncio
async def test_cancel_order(session, group, chemical, supplier, user):
    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
        ordered_by_user_id=user.id,
    )

    cancelled = await svc.cancel_order(session, o, reason="vendor out of stock")
    assert cancelled.status == svc.OrderStatus.CANCELLED
    assert cancelled.cancelled_at is not None
    assert cancelled.cancellation_reason == "vendor out of stock"

    with pytest.raises(svc.OrderStateError):
        await svc.cancel_order(session, cancelled)


@pytest.mark.asyncio
async def test_receive_spawns_n_containers(
    session, group, chemical, supplier, user, storage_location
):
    from chaima.models.container import Container
    from sqlmodel import select

    # Make storage_location visible to this group
    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))

    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=3,
        purity="99%", ordered_by_user_id=user.id,
    )
    await session.flush()

    rows = [
        svc.ContainerReceiveRow(identifier=f"lot-{i}", storage_location_id=storage_location.id)
        for i in range(3)
    ]
    containers = await svc.receive_order(session, o, rows=rows, received_by_user_id=user.id)
    assert len(containers) == 3
    assert all(c.amount == 100 and c.unit == "mL" and c.purity == "99%" for c in containers)
    assert all(c.order_id == o.id for c in containers)

    # Order is now received and locked from edits
    assert o.status == svc.OrderStatus.RECEIVED
    with pytest.raises(svc.OrderStateError):
        await svc.edit_order(session, o, package_count=5)


@pytest.mark.asyncio
async def test_receive_rejects_count_mismatch(
    session, group, chemical, supplier, user, storage_location
):
    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))
    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=3,
        ordered_by_user_id=user.id,
    )
    rows = [svc.ContainerReceiveRow(identifier="lot-0", storage_location_id=storage_location.id)]
    with pytest.raises(svc.ContainerCountMismatchError):
        await svc.receive_order(session, o, rows=rows, received_by_user_id=user.id)


@pytest.mark.asyncio
async def test_receive_rejects_invalid_storage_location(
    session, group, chemical, supplier, user
):
    """A storage_location_id outside the group must reject by index."""
    import uuid

    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
        ordered_by_user_id=user.id,
    )
    bogus = uuid.uuid4()
    rows = [svc.ContainerReceiveRow(identifier="lot-0", storage_location_id=bogus)]
    with pytest.raises(svc.StorageLocationInvalidError) as ei:
        await svc.receive_order(session, o, rows=rows, received_by_user_id=user.id)
    assert ei.value.index == 0


@pytest.mark.asyncio
async def test_lead_time_stats_null_under_three_orders(session, group, chemical, supplier, user):
    stats = await svc.lead_time_stats(session, group_id=group.id, supplier_id=supplier.id)
    assert stats is None


@pytest.mark.asyncio
async def test_lead_time_stats_returns_quantiles(
    session, group, chemical, supplier, user, storage_location
):
    """3+ received orders → returns median/p25/p75."""
    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))
    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")

    deltas = [5, 10, 14, 20]
    for d in deltas:
        o = await svc.create_order(
            session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
            project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
            ordered_by_user_id=user.id,
        )
        o.status = svc.OrderStatus.RECEIVED
        o.received_at = o.ordered_at + datetime.timedelta(days=d)
        session.add(o)
    await session.flush()

    stats = await svc.lead_time_stats(session, group_id=group.id, supplier_id=supplier.id)
    assert stats is not None
    assert stats.order_count == 4
    assert stats.median_days == 12  # median of [5,10,14,20] = 12
    assert 5 <= stats.p25_days <= 12
    assert 12 <= stats.p75_days <= 20
