# src/chaima/schemas/supplier.py
import datetime
from uuid import UUID

from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str


class SupplierUpdate(BaseModel):
    name: str | None = None


class SupplierRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    group_id: UUID
    created_at: datetime.datetime
