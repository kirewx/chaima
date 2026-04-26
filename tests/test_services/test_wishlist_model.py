import pytest

from chaima.models.order import Order  # noqa: F401  -- registers chemical_order for FK
from chaima.models.project import Project  # noqa: F401  -- chemical_order FKs to project
from chaima.models.wishlist import WishlistItem, WishlistStatus


@pytest.mark.asyncio
async def test_wishlist_with_chemical_id(session, group, chemical, user):
    item = WishlistItem(
        group_id=group.id,
        chemical_id=chemical.id,
        requested_by_user_id=user.id,
    )
    session.add(item)
    await session.flush()

    assert item.id is not None
    assert item.status == WishlistStatus.OPEN
    assert item.requested_at is not None


@pytest.mark.asyncio
async def test_wishlist_freeform(session, group, user):
    item = WishlistItem(
        group_id=group.id,
        freeform_name="Some new reagent",
        freeform_cas="123-45-6",
        requested_by_user_id=user.id,
        comment="for the catalysis project",
    )
    session.add(item)
    await session.flush()
    assert item.chemical_id is None
    assert item.freeform_name == "Some new reagent"
    assert item.status == WishlistStatus.OPEN
