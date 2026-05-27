"""End-to-end checks that user-facing endpoints emit the right events."""
import pytest
from sqlmodel import select

from chaima.models.analytics import Event


@pytest.mark.asyncio
async def test_chemicals_list_with_search_emits_search_executed(
    client, group, membership, session, patch_events_session_maker
):
    r = await client.get(
        f"/api/v1/groups/{group.id}/chemicals",
        params={"search": "acetone"},
    )
    assert r.status_code == 200
    rows = (await session.exec(select(Event).where(Event.type == "search_executed"))).all()
    assert len(rows) == 1
    assert rows[0].payload["query"] == "acetone"
    assert rows[0].payload["result_count"] == r.json()["total"]
    assert rows[0].group_id == group.id


@pytest.mark.asyncio
async def test_chemicals_list_short_search_does_not_emit(
    client, group, membership, session, patch_events_session_maker
):
    """Queries under 3 chars are noise (incremental typing) — no event."""
    r = await client.get(
        f"/api/v1/groups/{group.id}/chemicals",
        params={"search": "ac"},
    )
    assert r.status_code == 200
    rows = (await session.exec(select(Event).where(Event.type == "search_executed"))).all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_chemicals_list_without_search_does_not_emit(
    client, group, membership, session, patch_events_session_maker
):
    r = await client.get(f"/api/v1/groups/{group.id}/chemicals")
    assert r.status_code == 200
    rows = (await session.exec(select(Event).where(Event.type == "search_executed"))).all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_create_chemical_emits_chemical_created(
    client, group, membership, session, patch_events_session_maker
):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals",
        json={"name": "Acetone-X"},
    )
    assert r.status_code == 201, r.text
    chem_id = r.json()["id"]
    rows = (await session.exec(select(Event).where(Event.type == "chemical_created"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"chemical_id": chem_id}
    assert rows[0].group_id == group.id


@pytest.mark.asyncio
async def test_create_container_emits_container_created(
    client, group, membership, chemical, storage_location, session, patch_events_session_maker
):
    r = await client.post(
        f"/api/v1/groups/{group.id}/chemicals/{chemical.id}/containers",
        json={"identifier": "C-001", "amount": 100, "unit": "mL", "location_id": str(storage_location.id)},
    )
    assert r.status_code == 201, r.text
    cont_id = r.json()["id"]
    rows = (await session.exec(select(Event).where(Event.type == "container_created"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"container_id": cont_id}


@pytest.mark.asyncio
async def test_create_wishlist_emits_wishlist_added(
    client, group, membership, chemical, session, patch_events_session_maker
):
    r = await client.post(
        f"/api/v1/groups/{group.id}/wishlist",
        json={"chemical_id": str(chemical.id)},
    )
    assert r.status_code == 201, r.text
    rows = (await session.exec(select(Event).where(Event.type == "wishlist_added"))).all()
    assert len(rows) == 1
    assert rows[0].user_id is not None


@pytest.mark.asyncio
async def test_create_order_emits_order_created(
    client, group, membership, chemical, supplier, session, patch_events_session_maker
):
    # Orders require a project — create one via direct DB write to avoid
    # needing the projects-admin endpoint here.
    from chaima.models.project import Project
    project = Project(group_id=group.id, name="GeneralA")
    session.add(project)
    await session.flush()

    r = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id),
            "supplier_id": str(supplier.id),
            "project_id": str(project.id),
            "amount_per_package": 100,
            "unit": "g",
            "package_count": 1,
        },
    )
    assert r.status_code == 201, r.text
    order_id = r.json()["id"]
    rows = (await session.exec(select(Event).where(Event.type == "order_created"))).all()
    assert len(rows) == 1
    assert rows[0].payload == {"order_id": order_id}
