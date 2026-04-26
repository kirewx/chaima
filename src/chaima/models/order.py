import datetime
import uuid as uuid_pkg
from decimal import Decimal
from enum import Enum

from sqlalchemy import Column, DateTime, Numeric, func
from sqlmodel import Field, Relationship, SQLModel


class OrderStatus(str, Enum):
    ORDERED = "ordered"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class Order(SQLModel, table=True):
    __tablename__ = "chemical_order"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", index=True)
    supplier_id: uuid_pkg.UUID = Field(foreign_key="supplier.id", index=True)
    project_id: uuid_pkg.UUID = Field(foreign_key="project.id", index=True)

    amount_per_package: float
    unit: str
    package_count: int
    price_per_package: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True)
    )
    currency: str = Field(default="EUR", max_length=3)

    purity: str | None = Field(default=None)
    vendor_catalog_number: str | None = Field(default=None)
    vendor_product_url: str | None = Field(default=None)
    vendor_order_number: str | None = Field(default=None)
    expected_arrival: datetime.date | None = Field(default=None)
    comment: str | None = Field(default=None)

    status: OrderStatus = Field(default=OrderStatus.ORDERED, index=True)

    ordered_by_user_id: uuid_pkg.UUID = Field(foreign_key="user.id")
    ordered_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    received_by_user_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="user.id")
    received_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    cancelled_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    cancellation_reason: str | None = Field(default=None)

    chemical: "Chemical" = Relationship()
    supplier: "Supplier" = Relationship()
    project: "Project" = Relationship()
