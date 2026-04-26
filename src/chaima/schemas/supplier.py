import datetime
from uuid import UUID

from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str


class SupplierUpdate(BaseModel):
    name: str | None = None


class LeadTimeStats(BaseModel):
    order_count: int
    median_days: int
    p25_days: int
    p75_days: int


class SupplierRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    group_id: UUID
    created_at: datetime.datetime
    container_count: int = 0
    lead_time: LeadTimeStats | None = None


class SupplierContainerRow(BaseModel):
    """Flat row describing a container attached to a supplier."""

    model_config = {"from_attributes": True}

    id: UUID
    identifier: str
    amount: float
    unit: str
    is_archived: bool
    chemical_id: UUID
    chemical_name: str
