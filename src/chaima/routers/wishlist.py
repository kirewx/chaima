"""Router for wishlist endpoints."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import CurrentUserDep, GroupMemberDep, SessionDep
from chaima.models.chemical import Chemical
from chaima.models.wishlist import WishlistStatus
from chaima.schemas.pagination import PaginatedResponse
from chaima.schemas.wishlist import (
    WishlistCreate,
    WishlistPromoteResult,
    WishlistRead,
    WishlistUpdate,
)
from chaima.services import wishlist as wishlist_service

router = APIRouter(prefix="/api/v1/groups/{group_id}/wishlist", tags=["wishlist"])


async def _hydrate(session, item) -> WishlistRead:
    name: str | None = None
    if item.chemical_id is not None:
        chem = await session.get(Chemical, item.chemical_id)
        name = chem.name if chem else None
    base = WishlistRead.model_validate(item)
    return base.model_copy(update={"chemical_name": name})


@router.get("", response_model=PaginatedResponse[WishlistRead])
async def list_wishlist(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    status_: WishlistStatus = Query(WishlistStatus.OPEN, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> PaginatedResponse[WishlistRead]:
    items = await wishlist_service.list_wishlist(session, group_id=group_id, status=status_)
    page = items[offset : offset + limit]
    hydrated = [await _hydrate(session, x) for x in page]
    return PaginatedResponse(items=hydrated, total=len(items), offset=offset, limit=limit)


@router.post("", response_model=WishlistRead, status_code=status.HTTP_201_CREATED)
async def create_wishlist(
    group_id: UUID,
    body: WishlistCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
    member: GroupMemberDep,
) -> WishlistRead:
    item = await wishlist_service.create_wishlist(
        session,
        group_id=group_id,
        chemical_id=body.chemical_id,
        freeform_name=body.freeform_name,
        freeform_cas=body.freeform_cas,
        comment=body.comment,
        requested_by_user_id=current_user.id,
    )
    await session.commit()
    return await _hydrate(session, item)


@router.post("/{wishlist_id}/dismiss", response_model=WishlistRead)
async def dismiss_wishlist(
    group_id: UUID, wishlist_id: UUID,
    session: SessionDep, current_user: CurrentUserDep, member: GroupMemberDep,
) -> WishlistRead:
    item = await wishlist_service.get_wishlist(session, wishlist_id)
    if item is None or item.group_id != group_id:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    await wishlist_service.dismiss_wishlist(session, item, dismissed_by_user_id=current_user.id)
    await session.commit()
    return await _hydrate(session, item)


@router.post("/{wishlist_id}/promote", response_model=WishlistPromoteResult)
async def promote_wishlist(
    group_id: UUID, wishlist_id: UUID,
    session: SessionDep, member: GroupMemberDep,
) -> WishlistPromoteResult:
    item = await wishlist_service.get_wishlist(session, wishlist_id)
    if item is None or item.group_id != group_id:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    try:
        chemical_id = await wishlist_service.promote_wishlist(session, item)
    except wishlist_service.WishlistChemicalNotResolvable as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "chemical_not_resolvable", "message": str(exc)},
        )
    await session.commit()
    return WishlistPromoteResult(wishlist_item_id=item.id, chemical_id=chemical_id)
