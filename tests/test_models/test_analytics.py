import datetime
import uuid as uuid_pkg

import pytest
from sqlmodel import select

from chaima.models.analytics import Event, EventDaily, EventType, SlowRequest


@pytest.mark.asyncio
async def test_event_round_trip(session, user, group):
    e = Event(
        user_id=user.id,
        group_id=group.id,
        type=EventType.SEARCH_EXECUTED,
        payload={"query": "acetone", "result_count": 3},
    )
    session.add(e)
    await session.flush()
    fetched = (await session.exec(select(Event).where(Event.id == e.id))).first()
    assert fetched is not None
    assert fetched.type == "search_executed"
    assert fetched.payload == {"query": "acetone", "result_count": 3}
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_event_user_id_and_group_id_can_be_null(session):
    """login_failure uses NULL user_id; non-group events use NULL group_id."""
    e = Event(
        user_id=None, group_id=None,
        type=EventType.LOGIN_FAILURE,
        payload={"email_attempted": "x@example.com"},
    )
    session.add(e)
    await session.flush()
    assert e.id is not None


@pytest.mark.asyncio
async def test_event_daily_round_trip(session, user):
    today = datetime.date(2026, 5, 1)
    d = EventDaily(day=today, user_id=user.id, type="login_success", count=14)
    session.add(d)
    await session.flush()
    fetched = (await session.exec(
        select(EventDaily).where(EventDaily.day == today, EventDaily.user_id == user.id)
    )).first()
    assert fetched is not None
    assert fetched.count == 14


@pytest.mark.asyncio
async def test_slow_request_round_trip(session, user):
    r = SlowRequest(
        user_id=user.id,
        method="POST",
        path="/api/v1/groups/{group_id}/chemicals/extract-from-photo",
        status=200,
        duration_ms=1850,
    )
    session.add(r)
    await session.flush()
    fetched = (await session.exec(
        select(SlowRequest).where(SlowRequest.id == r.id)
    )).first()
    assert fetched is not None
    assert fetched.duration_ms == 1850


def test_event_type_enum_has_all_expected_values():
    expected = {
        "login_success", "login_failure", "search_executed",
        "chemical_created", "container_created", "order_created",
        "wishlist_added", "photo_extract", "pubchem_fetch",
    }
    assert {v.value for v in EventType} == expected
