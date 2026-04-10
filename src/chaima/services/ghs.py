# src/chaima/services/ghs.py
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.ghs import GHSCode


class DuplicateCodeError(Exception):
    """Raised when a GHS code already exists."""


async def create_ghs_code(
    session: AsyncSession,
    *,
    code: str,
    description: str,
    pictogram: str | None = None,
    signal_word: str | None = None,
) -> GHSCode:
    """Create a new GHS code.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    code : str
        The GHS hazard code (e.g. ``"H300"``).
    description : str
        Human-readable description of the hazard.
    pictogram : str or None, optional
        Optional pictogram identifier.
    signal_word : str or None, optional
        Optional signal word (e.g. ``"Danger"``).

    Returns
    -------
    GHSCode
        The newly created GHS code.

    Raises
    ------
    DuplicateCodeError
        If a GHS code with the same code already exists.
    """
    existing = await session.exec(select(GHSCode).where(GHSCode.code == code))
    if existing.first() is not None:
        raise DuplicateCodeError(f"GHS code {code} already exists")

    ghs = GHSCode(
        code=code, description=description, pictogram=pictogram, signal_word=signal_word
    )
    session.add(ghs)
    await session.flush()
    return ghs


async def list_ghs_codes(
    session: AsyncSession,
    *,
    search: str | None = None,
    sort: str = "code",
    order: str = "asc",
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[GHSCode], int]:
    """List GHS codes with optional search, sorting, and pagination.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    search : str or None, optional
        Filter by partial match on code or description.
    sort : str, optional
        Field to sort by. Defaults to ``"code"``.
    order : str, optional
        Sort direction, ``"asc"`` or ``"desc"``. Defaults to ``"asc"``.
    offset : int, optional
        Number of records to skip. Defaults to 0.
    limit : int, optional
        Maximum number of records to return. Defaults to 20.

    Returns
    -------
    tuple[list[GHSCode], int]
        A tuple of (items, total count).
    """
    query = select(GHSCode)

    if search:
        query = query.where(
            GHSCode.code.ilike(f"%{search}%")  # type: ignore[union-attr]
            | GHSCode.description.ilike(f"%{search}%")  # type: ignore[union-attr]
        )

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.exec(count_query)).one()

    # Sort
    sort_col = getattr(GHSCode, sort, GHSCode.code)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    # Paginate
    query = query.offset(offset).limit(limit)
    result = await session.exec(query)
    return list(result.all()), total


async def get_ghs_code(session: AsyncSession, ghs_id: UUID) -> GHSCode | None:
    """Get a GHS code by ID.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    ghs_id : UUID
        The ID of the GHS code to retrieve.

    Returns
    -------
    GHSCode or None
        The GHS code, or None if not found.
    """
    return await session.get(GHSCode, ghs_id)


async def update_ghs_code(
    session: AsyncSession,
    ghs: GHSCode,
    *,
    description: str | None = None,
    pictogram: str | None = None,
    signal_word: str | None = None,
) -> GHSCode:
    """Update a GHS code.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    ghs : GHSCode
        The GHS code instance to update.
    description : str or None, optional
        New description, if provided.
    pictogram : str or None, optional
        New pictogram identifier, if provided.
    signal_word : str or None, optional
        New signal word, if provided.

    Returns
    -------
    GHSCode
        The updated GHS code.
    """
    if description is not None:
        ghs.description = description
    if pictogram is not None:
        ghs.pictogram = pictogram
    if signal_word is not None:
        ghs.signal_word = signal_word
    session.add(ghs)
    await session.flush()
    return ghs
