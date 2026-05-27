"""Superuser-only analytics endpoints.

Endpoints all return JSON; auth via the existing ``SuperuserDep``. Range
filtering accepts ``24h | 7d | 30d | 90d`` (unknown values fall back to 7d).
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from fastapi import APIRouter, Query

from chaima.dependencies import SessionDep, SuperuserDep
from chaima.services import analytics as analytics_service

router = APIRouter(prefix="/api/v1/admin/analytics", tags=["admin-analytics"])

Range = Literal["24h", "7d", "30d", "90d"]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@router.get("/summary")
async def get_summary(
    session: SessionDep,
    user: SuperuserDep,
    range: Range = Query("7d"),
) -> dict[str, Any]:
    return await analytics_service.summary(session, range_=range, now=_now())


@router.get("/users")
async def get_user_stats(
    session: SessionDep,
    user: SuperuserDep,
    range: Range = Query("7d"),
) -> list[dict[str, Any]]:
    return await analytics_service.user_stats(session, range_=range, now=_now())


@router.get("/top-searches")
async def get_top_searches(
    session: SessionDep,
    user: SuperuserDep,
    range: Range = Query("7d"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    return await analytics_service.top_searches(
        session, range_=range, limit=limit, now=_now(),
    )


@router.get("/slow-endpoints")
async def get_slow_endpoints(
    session: SessionDep,
    user: SuperuserDep,
    range: Range = Query("7d"),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict[str, Any]]:
    return await analytics_service.slow_endpoints(
        session, range_=range, limit=limit, now=_now(),
    )


@router.post("/_compact")
async def compact_analytics(
    session: SessionDep,
    user: SuperuserDep,
) -> dict[str, Any]:
    """Roll old events into the daily summary and prune retention."""
    result = await analytics_service.compact(session, now=_now())
    return result
