import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

from chaima.models.wishlist import WishlistStatus


class WishlistCreate(BaseModel):
    chemical_id: UUID | None = None
    freeform_name: str | None = None
    freeform_cas: str | None = None
    comment: str | None = None

    @model_validator(mode="after")
    def _require_chemical_or_freeform(self) -> "WishlistCreate":
        if self.chemical_id is None and not self.freeform_name:
            raise ValueError("Either chemical_id or freeform_name is required")
        return self


class WishlistUpdate(BaseModel):
    chemical_id: UUID | None = None
    freeform_name: str | None = None
    freeform_cas: str | None = None
    comment: str | None = None


class WishlistRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    group_id: UUID
    chemical_id: UUID | None
    chemical_name: str | None = None  # joined when chemical_id is set
    freeform_name: str | None
    freeform_cas: str | None
    requested_by_user_id: UUID
    requested_at: datetime.datetime
    comment: str | None
    status: WishlistStatus
    converted_to_order_id: UUID | None
    dismissed_at: datetime.datetime | None
    dismissed_by_user_id: UUID | None


class WishlistPromoteResult(BaseModel):
    """Returned by POST /wishlist/{id}/promote. Frontend uses chemical_id to pre-fill the order form."""

    wishlist_item_id: UUID
    chemical_id: UUID
