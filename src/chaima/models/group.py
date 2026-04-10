import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel


class Group(SQLModel, table=True):
    __tablename__ = "group"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    chemicals: list["Chemical"] = Relationship(back_populates="group")
    suppliers: list["Supplier"] = Relationship(back_populates="group")


class UserGroupLink(SQLModel, table=True):
    __tablename__ = "user_group_link"
    __table_args__ = (UniqueConstraint("user_id", "group_id"),)

    user_id: uuid_pkg.UUID = Field(primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", primary_key=True)
    is_admin: bool = Field(default=False)
    joined_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    group: "Group" = Relationship()
