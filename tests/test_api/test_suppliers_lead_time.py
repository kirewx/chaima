import datetime
import pytest


@pytest.mark.asyncio
async def test_supplier_lead_time_null_under_three_orders(client, group, supplier, membership):
    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    items = resp.json()["items"]
    target = next(s for s in items if s["id"] == str(supplier.id))
    assert target["lead_time"] is None


@pytest.mark.asyncio
async def test_supplier_lead_time_populated_with_history(
    client, session, group, supplier, chemical, user, membership
):
    """Pre-populate 4 received orders with realistic deltas, then expect populated stats."""
    from chaima.models.order import Order, OrderStatus
    from chaima.models.project import Project

    project = Project(group_id=group.id, name="Cat")
    session.add(project)
    await session.flush()

    base_ordered = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    deltas = [5, 10, 14, 20]
    for d in deltas:
        o = Order(
            group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
            project_id=project.id, amount_per_package=1, unit="g", package_count=1,
            ordered_by_user_id=user.id, status=OrderStatus.RECEIVED,
        )
        session.add(o)
        await session.flush()
        o.ordered_at = base_ordered
        o.received_at = base_ordered + datetime.timedelta(days=d)
        session.add(o)
    await session.flush()

    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    target = next(s for s in resp.json()["items"] if s["id"] == str(supplier.id))
    assert target["lead_time"] is not None
    assert target["lead_time"]["order_count"] == 4
    assert target["lead_time"]["median_days"] == 12
