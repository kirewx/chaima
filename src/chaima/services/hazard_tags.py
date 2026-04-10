# src/chaima/services/hazard_tags.py
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.hazard import HazardTag, HazardTagIncompatibility


class DuplicateTagError(Exception):
    """Raised when a hazard tag name already exists in the group."""


class CrossGroupError(Exception):
    """Raised when creating an incompatibility between tags from different groups."""


class DuplicateIncompatibilityError(Exception):
    """Raised when an incompatibility pair already exists."""


async def create_hazard_tag(
    session: AsyncSession,
    *,
    group_id: UUID,
    name: str,
    description: str | None = None,
) -> HazardTag:
    """Create a hazard tag within a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to create the tag in.
    name : str
        Name of the hazard tag.
    description : str or None, optional
        Optional description.

    Returns
    -------
    HazardTag
        The newly created hazard tag.

    Raises
    ------
    DuplicateTagError
        If a tag with the same name already exists in the group.
    """
    existing = await session.exec(
        select(HazardTag).where(HazardTag.group_id == group_id, HazardTag.name == name)
    )
    if existing.first() is not None:
        raise DuplicateTagError(f"Hazard tag '{name}' already exists in this group")

    tag = HazardTag(name=name, description=description, group_id=group_id)
    session.add(tag)
    await session.flush()
    return tag


async def list_hazard_tags(
    session: AsyncSession,
    group_id: UUID,
    *,
    search: str | None = None,
    sort: str = "name",
    order: str = "asc",
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[HazardTag], int]:
    """List hazard tags for a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to list tags for.
    search : str or None, optional
        Filter by partial name match.
    sort : str, optional
        Field to sort by. Defaults to ``"name"``.
    order : str, optional
        Sort direction, ``"asc"`` or ``"desc"``. Defaults to ``"asc"``.
    offset : int, optional
        Number of records to skip. Defaults to 0.
    limit : int, optional
        Maximum number of records to return. Defaults to 20.

    Returns
    -------
    tuple[list[HazardTag], int]
        A tuple of (items, total count).
    """
    query = select(HazardTag).where(HazardTag.group_id == group_id)

    if search:
        query = query.where(HazardTag.name.ilike(f"%{search}%"))  # type: ignore[union-attr]

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.exec(count_query)).one()

    sort_col = getattr(HazardTag, sort, HazardTag.name)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    query = query.offset(offset).limit(limit)

    result = await session.exec(query)
    return list(result.all()), total


async def get_hazard_tag(session: AsyncSession, tag_id: UUID) -> HazardTag | None:
    """Get a hazard tag by ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    tag_id : UUID
        The ID of the hazard tag to retrieve.

    Returns
    -------
    HazardTag or None
        The hazard tag, or None if not found.
    """
    return await session.get(HazardTag, tag_id)


async def update_hazard_tag(
    session: AsyncSession,
    tag: HazardTag,
    *,
    name: str | None = None,
    description: str | None = None,
) -> HazardTag:
    """Update a hazard tag.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    tag : HazardTag
        The hazard tag instance to update.
    name : str or None, optional
        New name, if provided.
    description : str or None, optional
        New description, if provided.

    Returns
    -------
    HazardTag
        The updated hazard tag.
    """
    if name is not None:
        tag.name = name
    if description is not None:
        tag.description = description
    session.add(tag)
    await session.flush()
    return tag


async def delete_hazard_tag(session: AsyncSession, tag: HazardTag) -> None:
    """Delete a hazard tag.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    tag : HazardTag
        The hazard tag to delete.
    """
    await session.delete(tag)
    await session.flush()


async def create_incompatibility(
    session: AsyncSession,
    *,
    group_id: UUID,
    tag_a_id: UUID,
    tag_b_id: UUID,
    reason: str | None = None,
) -> HazardTagIncompatibility:
    """Create an incompatibility rule between two hazard tags.

    Enforces same-group check and canonical ordering (tag_a_id < tag_b_id).

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group context for validation.
    tag_a_id : UUID
        ID of the first hazard tag.
    tag_b_id : UUID
        ID of the second hazard tag.
    reason : str or None, optional
        Optional reason for the incompatibility.

    Returns
    -------
    HazardTagIncompatibility
        The newly created incompatibility rule.

    Raises
    ------
    ValueError
        If one or both hazard tags are not found.
    CrossGroupError
        If the tags belong to different groups or not to the specified group.
    DuplicateIncompatibilityError
        If the incompatibility pair already exists.
    """
    tag_a = await session.get(HazardTag, tag_a_id)
    tag_b = await session.get(HazardTag, tag_b_id)

    if tag_a is None or tag_b is None:
        raise ValueError("One or both hazard tags not found")

    if tag_a.group_id != tag_b.group_id:
        raise CrossGroupError("Both hazard tags must belong to the same group")

    if tag_a.group_id != group_id or tag_b.group_id != group_id:
        raise CrossGroupError("Hazard tags must belong to the specified group")

    # Canonical ordering
    lo, hi = sorted([tag_a_id, tag_b_id])

    existing = await session.exec(
        select(HazardTagIncompatibility).where(
            HazardTagIncompatibility.tag_a_id == lo,
            HazardTagIncompatibility.tag_b_id == hi,
        )
    )
    if existing.first() is not None:
        raise DuplicateIncompatibilityError("Incompatibility already exists")

    incompat = HazardTagIncompatibility(tag_a_id=lo, tag_b_id=hi, reason=reason)
    session.add(incompat)
    await session.flush()
    return incompat


async def list_incompatibilities(
    session: AsyncSession, group_id: UUID
) -> list[HazardTagIncompatibility]:
    """List all incompatibility rules for tags in a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to list incompatibilities for.

    Returns
    -------
    list[HazardTagIncompatibility]
        All incompatibility rules for the group.
    """
    result = await session.exec(
        select(HazardTagIncompatibility)
        .join(HazardTag, HazardTag.id == HazardTagIncompatibility.tag_a_id)
        .where(HazardTag.group_id == group_id)
    )
    return list(result.all())


async def delete_incompatibility(
    session: AsyncSession, incompat: HazardTagIncompatibility
) -> None:
    """Delete an incompatibility rule.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    incompat : HazardTagIncompatibility
        The incompatibility to delete.
    """
    await session.delete(incompat)
    await session.flush()


async def get_incompatibility(
    session: AsyncSession, incompat_id: UUID
) -> HazardTagIncompatibility | None:
    """Get an incompatibility by ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    incompat_id : UUID
        The ID of the incompatibility to retrieve.

    Returns
    -------
    HazardTagIncompatibility or None
        The incompatibility, or None if not found.
    """
    return await session.get(HazardTagIncompatibility, incompat_id)
