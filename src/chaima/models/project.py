import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel


class Project(SQLModel, table=True):
    __tablename__ = "project"
    __table_args__ = (UniqueConstraint("name", "group_id"),)

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    name: str = Field(index=True)
    is_archived: bool = Field(default=False, index=True)
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
