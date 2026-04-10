import datetime
import secrets
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from chaima.config import admin_settings


def _default_expiry() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        hours=admin_settings.invite_ttl_hours
    )


class Invite(SQLModel, table=True):
    __tablename__ = "invite"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        unique=True,
        index=True,
    )
    created_by: uuid_pkg.UUID = Field(foreign_key="user.id")
    expires_at: datetime.datetime = Field(
        default_factory=_default_expiry,
    )
    used_by: uuid_pkg.UUID | None = Field(default=None, foreign_key="user.id")
    used_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
