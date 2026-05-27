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
