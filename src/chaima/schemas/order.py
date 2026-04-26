import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from chaima.models.order import OrderStatus


class OrderCreate(BaseModel):
    chemical_id: UUID
    supplier_id: UUID
    project_id: UUID
    amount_per_package: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    package_count: int = Field(ge=1)
    price_per_package: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    purity: str | None = None
    vendor_catalog_number: str | None = None
    vendor_product_url: HttpUrl | None = None
    vendor_order_number: str | None = None
    expected_arrival: datetime.date | None = None
    comment: str | None = None
    wishlist_item_id: UUID | None = None  # Atomically marks wishlist as converted on create.


class OrderUpdate(BaseModel):
    """Edit allowed only while status=ordered. Server returns 409 otherwise."""

    supplier_id: UUID | None = None
    project_id: UUID | None = None
    amount_per_package: float | None = Field(default=None, gt=0)
    unit: str | None = None
    package_count: int | None = Field(default=None, ge=1)
    price_per_package: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    purity: str | None = None
    vendor_catalog_number: str | None = None
    vendor_product_url: HttpUrl | None = None
    vendor_order_number: str | None = None
    expected_arrival: datetime.date | None = None
    comment: str | None = None


class OrderCancel(BaseModel):
    cancellation_reason: str | None = None


class ContainerReceiveRow(BaseModel):
    identifier: str = Field(min_length=1)
    storage_location_id: UUID
    purity_override: str | None = None


class OrderReceive(BaseModel):
    containers: list[ContainerReceiveRow] = Field(min_length=1)


class OrderRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    group_id: UUID
    chemical_id: UUID
    chemical_name: str | None = None  # populated server-side from join
    supplier_id: UUID
    supplier_name: str | None = None
    project_id: UUID
    project_name: str | None = None

    amount_per_package: float
    unit: str
    package_count: int
    price_per_package: Decimal | None
    currency: str

    purity: str | None
    vendor_catalog_number: str | None
    vendor_product_url: str | None
    vendor_order_number: str | None
    expected_arrival: datetime.date | None
    comment: str | None

    status: OrderStatus

    ordered_by_user_id: UUID
    ordered_by_user_email: str | None = None
    ordered_at: datetime.datetime
    received_by_user_id: UUID | None
    received_by_user_email: str | None = None
    received_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None
    cancellation_reason: str | None
