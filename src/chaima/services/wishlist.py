"""Service layer for WishlistItem entities."""
from __future__ import annotations

import datetime
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.wishlist import WishlistItem, WishlistStatus


class WishlistFreeformInvalid(ValueError):
    """Raised when neither chemical_id nor freeform_name is provided."""


class WishlistChemicalNotResolvable(Exception):
    """Raised when promoting a freeform item but PubChem can't find it."""


async def create_wishlist(
    session: AsyncSession,
    *,
    group_id: UUID,
    requested_by_user_id: UUID,
    chemical_id: UUID | None = None,
    freeform_name: str | None = None,
    freeform_cas: str | None = None,
    comment: str | None = None,
) -> WishlistItem:
    if chemical_id is None and not (freeform_name and freeform_name.strip()):
        raise WishlistFreeformInvalid(
            "Either chemical_id or freeform_name is required"
        )
    item = WishlistItem(
        group_id=group_id,
        chemical_id=chemical_id,
        freeform_name=freeform_name.strip() if freeform_name else None,
        freeform_cas=freeform_cas.strip() if freeform_cas else None,
        requested_by_user_id=requested_by_user_id,
        comment=comment,
    )
    session.add(item)
    await session.flush()
    return item


async def list_wishlist(
    session: AsyncSession, *, group_id: UUID, status: WishlistStatus = WishlistStatus.OPEN
) -> list[WishlistItem]:
    stmt = (
        select(WishlistItem)
        .where(WishlistItem.group_id == group_id, WishlistItem.status == status)
        .order_by(WishlistItem.requested_at.desc())
    )
    return list((await session.exec(stmt)).all())


async def get_wishlist(session: AsyncSession, wishlist_id: UUID) -> WishlistItem | None:
    return await session.get(WishlistItem, wishlist_id)


async def dismiss_wishlist(
    session: AsyncSession, item: WishlistItem, *, dismissed_by_user_id: UUID
) -> WishlistItem:
    item.status = WishlistStatus.DISMISSED
    item.dismissed_at = datetime.datetime.now(datetime.timezone.utc)
    item.dismissed_by_user_id = dismissed_by_user_id
    session.add(item)
    await session.flush()
    return item
