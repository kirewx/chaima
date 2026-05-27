"""Analytics tables: raw events, daily aggregates, slow-request log."""
from __future__ import annotations

import datetime
import enum
import uuid as uuid_pkg

from sqlalchemy import JSON, Column, DateTime, Index, func
from sqlmodel import Field, SQLModel


class EventType(str, enum.Enum):
    """Whitelist of valid event.type values.

    Stored as plain ``str`` in the DB (no SQL Enum) so we can add new types
    later without a migration. Use these constants when writing events.
    """
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    SEARCH_EXECUTED = "search_executed"
    CHEMICAL_CREATED = "chemical_created"
    CONTAINER_CREATED = "container_created"
    ORDER_CREATED = "order_created"
    WISHLIST_ADDED = "wishlist_added"
    PHOTO_EXTRACT = "photo_extract"
    PUBCHEM_FETCH = "pubchem_fetch"


class Event(SQLModel, table=True):
    __tablename__ = "event"
    __table_args__ = (
        Index("ix_event_user_created", "user_id", "created_at"),
        Index("ix_event_type_created", "type", "created_at"),
    )

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    user_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="user.id", index=True, nullable=True,
    )
    group_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="group.id", index=True, nullable=True,
    )
    type: str = Field(index=True)
    payload: dict | None = Field(
        default=None, sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
            index=True,
        ),
    )


class EventDaily(SQLModel, table=True):
    """Per-day aggregate row written by the nightly compaction job."""
    __tablename__ = "event_daily"

    day: datetime.date = Field(primary_key=True)
    user_id: uuid_pkg.UUID = Field(primary_key=True, foreign_key="user.id")
    type: str = Field(primary_key=True)
    group_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="group.id")
    count: int = Field(default=0, nullable=False)


class SlowRequest(SQLModel, table=True):
    __tablename__ = "slow_request"
    __table_args__ = (
        Index("ix_slow_path_created", "path", "created_at"),
    )

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    user_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="user.id", nullable=True,
    )
    method: str
    path: str = Field(index=True)
    status: int
    duration_ms: int
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
            index=True,
        ),
    )
