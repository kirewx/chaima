import datetime
import uuid as uuid_pkg
from typing import Optional

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel


class StorageLocation(SQLModel, table=True):
    __tablename__ = "storage_location"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    parent_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="storage_location.id", index=True
    )
    name: str
    description: str | None = Field(default=None)
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    children: list["StorageLocation"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"remote_side": "StorageLocation.id"},
    )
    parent: Optional["StorageLocation"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "StorageLocation.parent_id"},
    )
    containers: list["Container"] = Relationship(back_populates="location")


class StorageLocationGroup(SQLModel, table=True):
    __tablename__ = "storage_location_group"
    __table_args__ = (UniqueConstraint("location_id", "group_id"),)

    location_id: uuid_pkg.UUID = Field(foreign_key="storage_location.id", primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", primary_key=True)
