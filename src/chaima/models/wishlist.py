import datetime
import uuid as uuid_pkg
from enum import Enum

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class WishlistStatus(str, Enum):
    OPEN = "open"
    CONVERTED = "converted"
    DISMISSED = "dismissed"


class WishlistItem(SQLModel, table=True):
    __tablename__ = "wishlist_item"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)

    chemical_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="chemical.id", index=True)
    freeform_name: str | None = Field(default=None)
    freeform_cas: str | None = Field(default=None)

    requested_by_user_id: uuid_pkg.UUID = Field(foreign_key="user.id")
    requested_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    comment: str | None = Field(default=None)

    status: WishlistStatus = Field(default=WishlistStatus.OPEN, index=True)
    converted_to_order_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="chemical_order.id"
    )
    dismissed_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    dismissed_by_user_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="user.id")
