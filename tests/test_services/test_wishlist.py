import pytest

from chaima.models.wishlist import WishlistStatus
from chaima.services import wishlist as svc


@pytest.mark.asyncio
async def test_create_with_chemical_id(session, group, chemical, user):
    item = await svc.create_wishlist(
        session, group_id=group.id, chemical_id=chemical.id,
        requested_by_user_id=user.id, comment="please order soon",
    )
    assert item.chemical_id == chemical.id
    assert item.status.value == "open"


@pytest.mark.asyncio
async def test_create_freeform(session, group, user):
    item = await svc.create_wishlist(
        session, group_id=group.id,
        freeform_name="Some new reagent", freeform_cas="123-45-6",
        requested_by_user_id=user.id,
    )
    assert item.chemical_id is None
    assert item.freeform_name == "Some new reagent"


@pytest.mark.asyncio
async def test_create_freeform_requires_name(session, group, user):
    with pytest.raises(ValueError):
        await svc.create_wishlist(
            session, group_id=group.id, requested_by_user_id=user.id,
        )


@pytest.mark.asyncio
async def test_dismiss_records_actor_and_timestamp(session, group, chemical, user):
    item = await svc.create_wishlist(
        session, group_id=group.id, chemical_id=chemical.id,
        requested_by_user_id=user.id,
    )
    await svc.dismiss_wishlist(session, item, dismissed_by_user_id=user.id)
    assert item.status == WishlistStatus.DISMISSED
    assert item.dismissed_at is not None
    assert item.dismissed_by_user_id == user.id
