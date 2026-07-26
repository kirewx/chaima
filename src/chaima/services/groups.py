"""Service layer for group management operations."""

from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.group import Group, UserGroupLink
from chaima.models.user import User

PRESEED_SUPPLIERS = (
    "Sigma-Aldrich", "Merck", "Carl Roth", "abcr", "BLDPharm",
    "TCI", "Alfa Aesar", "Fisher Scientific", "Thermo Fisher", "VWR",
)


class MemberExistsError(Exception):
    """Raised when adding a user who is already a member."""


class MemberNotFoundError(Exception):
    """Raised when the target membership does not exist."""


class LastAdminError(Exception):
    """Raised when demoting or removing the last admin of a group."""


async def _count_admins(session: AsyncSession, group_id: UUID) -> int:
    """Count the admins of a group."""
    result = await session.exec(
        select(func.count())
        .select_from(UserGroupLink)
        .where(
            UserGroupLink.group_id == group_id,
            UserGroupLink.is_admin == True,  # noqa: E712
        )
    )
    return result.one()


async def create_group(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    creator_id: UUID,
) -> Group:
    """Create a group and add the creator as admin.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    name : str
        The name of the new group.
    description : str or None, optional
        Optional description for the group.
    creator_id : UUID
        The ID of the user creating the group; they will be added as admin.

    Returns
    -------
    Group
        The newly created group.
    """
    group = Group(name=name, description=description)
    session.add(group)
    await session.flush()
    link = UserGroupLink(user_id=creator_id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.flush()

    # Pre-seed standard data so the group is usable for ordering immediately.
    from chaima.models.project import Project
    from chaima.models.supplier import Supplier

    session.add(Project(group_id=group.id, name="General"))
    for supplier_name in PRESEED_SUPPLIERS:
        session.add(Supplier(group_id=group.id, name=supplier_name))
    await session.flush()
    return group


async def list_groups_for_user(
    session: AsyncSession,
    user_id: UUID,
) -> list[Group]:
    """List all groups a user belongs to.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    user_id : UUID
        The ID of the user whose groups to list.

    Returns
    -------
    list[Group]
        All groups the user is a member of.
    """
    result = await session.exec(
        select(Group)
        .join(UserGroupLink, UserGroupLink.group_id == Group.id)
        .where(UserGroupLink.user_id == user_id)
    )
    return list(result.all())


async def list_all_groups(session: AsyncSession) -> list[Group]:
    """List every group in the system, ordered by name.

    Parameters
    ----------
    session : AsyncSession
        The database session.

    Returns
    -------
    list[Group]
        All groups, sorted alphabetically by name.
    """
    result = await session.exec(select(Group).order_by(Group.name))
    return list(result.all())


async def get_group(
    session: AsyncSession,
    group_id: UUID,
) -> Group | None:
    """Retrieve a group by its ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The ID of the group to retrieve.

    Returns
    -------
    Group or None
        The group, or None if not found.
    """
    return await session.get(Group, group_id)


async def update_group(
    session: AsyncSession,
    group: Group,
    *,
    name: str | None = None,
    description: str | None = None,
    show_sds_research_links: bool | None = None,
) -> Group:
    """Update a group's name, description, and/or SDS research links flag.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group : Group
        The group instance to update.
    name : str or None, optional
        New name for the group, if provided.
    description : str or None, optional
        New description for the group, if provided.
    show_sds_research_links : bool or None, optional
        New value for the SDS research links flag, if provided.

    Returns
    -------
    Group
        The updated group.
    """
    if name is not None:
        group.name = name
    if description is not None:
        group.description = description
    if show_sds_research_links is not None:
        group.show_sds_research_links = show_sds_research_links
    session.add(group)
    await session.flush()
    return group


async def add_member(
    session: AsyncSession,
    group_id: UUID,
    user_id: UUID,
    *,
    is_admin: bool = False,
) -> UserGroupLink:
    """Add a user as a member of a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The ID of the group.
    user_id : UUID
        The ID of the user to add.
    is_admin : bool, optional
        Whether the new member should be an admin. Defaults to False.

    Returns
    -------
    UserGroupLink
        The newly created membership link.

    Raises
    ------
    MemberExistsError
        If the user is already a member of the group.
    """
    result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == user_id,
            UserGroupLink.group_id == group_id,
        )
    )
    if result.first() is not None:
        raise MemberExistsError(
            f"User {user_id} is already a member of group {group_id}"
        )
    link = UserGroupLink(user_id=user_id, group_id=group_id, is_admin=is_admin)
    session.add(link)
    await session.flush()
    return link


async def remove_member(
    session: AsyncSession,
    group_id: UUID,
    user_id: UUID,
) -> None:
    """Remove a user from a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The ID of the group.
    user_id : UUID
        The ID of the user to remove.

    Raises
    ------
    MemberNotFoundError
        If the user is not a member of the group.
    LastAdminError
        If the user is the last admin of the group.
    """
    result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == user_id,
            UserGroupLink.group_id == group_id,
        )
    )
    link = result.first()
    if link is None:
        raise MemberNotFoundError(
            f"User {user_id} is not a member of group {group_id}"
        )
    if link.is_admin and await _count_admins(session, group_id) <= 1:
        raise LastAdminError(
            f"User {user_id} is the last admin of group {group_id}"
        )
    await session.delete(link)
    await session.flush()


async def update_member_role(
    session: AsyncSession,
    group_id: UUID,
    user_id: UUID,
    *,
    is_admin: bool,
) -> UserGroupLink:
    """Update the admin role of a group member.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The ID of the group.
    user_id : UUID
        The ID of the user whose role to update.
    is_admin : bool
        Whether the user should be an admin.

    Returns
    -------
    UserGroupLink
        The updated membership link.

    Raises
    ------
    MemberNotFoundError
        If the user is not a member of the group.
    LastAdminError
        If demoting the user would leave the group without an admin.
    """
    result = await session.exec(
        select(UserGroupLink).where(
            UserGroupLink.user_id == user_id,
            UserGroupLink.group_id == group_id,
        )
    )
    link = result.first()
    if link is None:
        raise MemberNotFoundError(
            f"User {user_id} is not a member of group {group_id}"
        )
    if link.is_admin and not is_admin and await _count_admins(session, group_id) <= 1:
        raise LastAdminError(
            f"User {user_id} is the last admin of group {group_id}"
        )
    link.is_admin = is_admin
    session.add(link)
    await session.flush()
    return link


async def list_members(
    session: AsyncSession,
    group_id: UUID,
) -> list[tuple[UserGroupLink, User]]:
    """List all members of a group with their user information.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The ID of the group.

    Returns
    -------
    list[tuple[UserGroupLink, User]]
        A list of (membership link, user) pairs for all members.

    Notes
    -----
    Uses individual ``session.get`` lookups per link to avoid UUID encoding
    mismatches between SQLModel and SQLAlchemy ORM in SQLite.
    """
    result = await session.exec(
        select(UserGroupLink).where(UserGroupLink.group_id == group_id)
    )
    links = list(result.all())
    pairs: list[tuple[UserGroupLink, User]] = []
    for link in links:
        user = await session.get(User, link.user_id)
        if user is not None:
            pairs.append((link, user))
    return pairs
