import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class Supplier(SQLModel, table=True):
    __tablename__ = "supplier"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    name: str
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
