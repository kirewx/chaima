import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class Container(SQLModel, table=True):
    __tablename__ = "container"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", index=True)
    location_id: uuid_pkg.UUID = Field(foreign_key="storage_location.id", index=True)
    supplier_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="supplier.id")
    identifier: str = Field(index=True)
    amount: float
    unit: str
    image_path: str | None = Field(default=None)
    purchased_at: datetime.date | None = Field(default=None)
    created_by: uuid_pkg.UUID = Field(foreign_key="user.id")
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        ),
    )
    is_archived: bool = Field(default=False, index=True)
