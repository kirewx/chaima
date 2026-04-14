# src/chaima/services/chemicals.py
import datetime
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical, ChemicalSynonym, StructureSource
from chaima.models.ghs import ChemicalGHS, GHSCode
from chaima.models.hazard import ChemicalHazardTag, HazardTag
from chaima.models.user import User


class CrossGroupError(Exception):
    """Raised when linking a chemical to a hazard tag from a different group."""


class DuplicateNameError(Exception):
    """Raised when a chemical name already exists within the same group."""


class ChemicalNotFound(LookupError):
    """Raised when a chemical id does not exist."""


def apply_secret_filter(stmt, viewer: User):
    """Exclude secret chemicals the viewer is not allowed to see.

    A user sees a secret chemical only if they created it. Superusers see
    all secrets. Non-secret chemicals are always visible.
    """
    if viewer.is_superuser:
        return stmt
    return stmt.where(
        or_(Chemical.is_secret.is_(False), Chemical.created_by == viewer.id)
    )


async def create_chemical(
    session: AsyncSession,
    *,
    group_id: UUID,
    created_by: UUID,
    name: str,
    cas: str | None = None,
    smiles: str | None = None,
    cid: str | None = None,
    structure: str | None = None,
    molar_mass: float | None = None,
    density: float | None = None,
    melting_point: float | None = None,
    boiling_point: float | None = None,
    comment: str | None = None,
    is_secret: bool = False,
    structure_source: StructureSource = StructureSource.NONE,
    sds_path: str | None = None,
) -> Chemical:
    """Create a new chemical within a group.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        ID of the group this chemical belongs to.
    created_by : UUID
        ID of the user creating the chemical.
    name : str
        Chemical name.
    cas : str or None, optional
        CAS registry number.
    smiles : str or None, optional
        SMILES notation.
    cid : str or None, optional
        PubChem compound ID.
    structure : str or None, optional
        Structure data.
    molar_mass : float or None, optional
        Molar mass in g/mol.
    density : float or None, optional
        Density in g/mL.
    melting_point : float or None, optional
        Melting point in °C.
    boiling_point : float or None, optional
        Boiling point in °C.
    comment : str or None, optional
        Free-text comment.

    Returns
    -------
    Chemical
        The newly created chemical.
    """
    existing = (
        await session.exec(
            select(Chemical).where(
                Chemical.group_id == group_id, Chemical.name == name
            )
        )
    ).first()
    if existing is not None:
        raise DuplicateNameError(
            f"Chemical '{name}' already exists in this group"
        )

    chem = Chemical(
        group_id=group_id,
        created_by=created_by,
        name=name,
        cas=cas,
        smiles=smiles,
        cid=cid,
        structure=structure,
        molar_mass=molar_mass,
        density=density,
        melting_point=melting_point,
        boiling_point=boiling_point,
        comment=comment,
        is_secret=is_secret,
        structure_source=structure_source,
        sds_path=sds_path,
    )
    session.add(chem)
    await session.flush()
    return chem


async def list_chemicals(
    session: AsyncSession,
    group_id: UUID,
    *,
    viewer: User,
    search: str | None = None,
    hazard_tag_id: UUID | None = None,
    ghs_code_id: UUID | None = None,
    has_containers: bool | None = None,
    include_archived: bool = False,
    sort: str = "name",
    order: str = "asc",
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Chemical], int]:
    """List chemicals in a group with optional filtering and pagination.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    group_id : UUID
        The group to list chemicals for.
    search : str or None, optional
        Filter by partial name or CAS match (case-insensitive).
    hazard_tag_id : UUID or None, optional
        Filter to chemicals with this hazard tag assigned.
    ghs_code_id : UUID or None, optional
        Filter to chemicals with this GHS code assigned.
    has_containers : bool or None, optional
        Filter to chemicals with (True) or without (False) active containers.
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
    tuple[list[Chemical], int]
        A tuple of (items, total count).
    """
    query = select(Chemical).where(Chemical.group_id == group_id)

    if search:
        query = query.where(
            Chemical.name.ilike(f"%{search}%")  # type: ignore[union-attr]
            | Chemical.cas.ilike(f"%{search}%")  # type: ignore[union-attr]
        )

    if hazard_tag_id:
        query = query.join(ChemicalHazardTag).where(
            ChemicalHazardTag.hazard_tag_id == hazard_tag_id
        )

    if ghs_code_id:
        query = query.join(ChemicalGHS).where(ChemicalGHS.ghs_id == ghs_code_id)

    if has_containers is not None:
        from chaima.models.container import Container

        container_exists = (
            select(Container.id)
            .where(Container.chemical_id == Chemical.id, Container.is_archived == False)  # noqa: E712
            .correlate(Chemical)
            .exists()
        )
        if has_containers:
            query = query.where(container_exists)
        else:
            query = query.where(~container_exists)

    if not include_archived:
        query = query.where(Chemical.is_archived.is_(False))
    query = apply_secret_filter(query, viewer)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.exec(count_query)).one()

    sort_col = getattr(Chemical, sort, Chemical.name)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    query = query.offset(offset).limit(limit)

    result = await session.exec(query)
    return list(result.all()), total


async def get_chemical(session: AsyncSession, chemical_id: UUID) -> Chemical | None:
    """Get a chemical by ID (no relationships loaded).

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical_id : UUID
        The ID of the chemical to retrieve.

    Returns
    -------
    Chemical or None
        The chemical, or None if not found.
    """
    return await session.get(Chemical, chemical_id)


async def get_chemical_detail(session: AsyncSession, chemical_id: UUID) -> Chemical | None:
    """Get a chemical with all relationships eagerly loaded.

    Loads synonyms, GHS codes (via ghs_links), and hazard tags
    (via hazard_tag_links) using selectinload.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical_id : UUID
        The ID of the chemical to retrieve.

    Returns
    -------
    Chemical or None
        The chemical with eager-loaded relations, or None if not found.
    """
    result = await session.exec(
        select(Chemical)
        .where(Chemical.id == chemical_id)
        .options(
            selectinload(Chemical.synonyms),  # type: ignore[arg-type]
            selectinload(Chemical.ghs_links).selectinload(ChemicalGHS.ghs_code),  # type: ignore[arg-type]
            selectinload(Chemical.hazard_tag_links).selectinload(ChemicalHazardTag.hazard_tag),  # type: ignore[arg-type]
        )
    )
    return result.first()


async def update_chemical(
    session: AsyncSession,
    chemical: Chemical,
    **kwargs: object,
) -> Chemical:
    """Update chemical scalar fields.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical : Chemical
        The chemical instance to update.
    **kwargs : object
        Field name/value pairs to update. None values are skipped.

    Returns
    -------
    Chemical
        The updated chemical.
    """
    for key, value in kwargs.items():
        if value is not None:
            setattr(chemical, key, value)
    session.add(chemical)
    await session.flush()
    return chemical


async def delete_chemical(session: AsyncSession, chemical: Chemical) -> None:
    """Delete a chemical.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical : Chemical
        The chemical to delete.
    """
    await session.delete(chemical)
    await session.flush()


async def replace_synonyms(
    session: AsyncSession,
    chemical_id: UUID,
    synonyms: list[dict[str, str | None]],
) -> list[ChemicalSynonym]:
    """Replace all synonyms for a chemical.

    Deletes all existing synonyms and creates new ones from the provided list.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical_id : UUID
        The ID of the chemical whose synonyms to replace.
    synonyms : list[dict[str, str or None]]
        List of synonym dicts with ``name`` and optional ``category`` keys.

    Returns
    -------
    list[ChemicalSynonym]
        The newly created synonyms.
    """
    # Delete existing
    result = await session.exec(
        select(ChemicalSynonym).where(ChemicalSynonym.chemical_id == chemical_id)
    )
    for s in result.all():
        await session.delete(s)
    await session.flush()

    # Create new
    new_synonyms = []
    for data in synonyms:
        syn = ChemicalSynonym(
            chemical_id=chemical_id, name=data["name"], category=data.get("category")
        )
        session.add(syn)
        new_synonyms.append(syn)
    await session.flush()
    return new_synonyms


async def replace_ghs_codes(
    session: AsyncSession,
    chemical_id: UUID,
    ghs_ids: list[UUID],
) -> list[GHSCode]:
    """Replace all GHS code assignments for a chemical.

    Deletes existing ChemicalGHS links and creates new ones.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical_id : UUID
        The ID of the chemical.
    ghs_ids : list[UUID]
        New list of GHS code IDs.

    Returns
    -------
    list[GHSCode]
        The GHSCode objects for the new assignments.

    Raises
    ------
    ValueError
        If any GHS code ID is not found.
    """
    # Delete existing links
    result = await session.exec(
        select(ChemicalGHS).where(ChemicalGHS.chemical_id == chemical_id)
    )
    for link in result.all():
        await session.delete(link)
    await session.flush()

    # Create new links
    codes = []
    for ghs_id in ghs_ids:
        ghs = await session.get(GHSCode, ghs_id)
        if ghs is None:
            raise ValueError(f"GHS code {ghs_id} not found")
        session.add(ChemicalGHS(chemical_id=chemical_id, ghs_id=ghs_id))
        codes.append(ghs)
    await session.flush()
    return codes


async def replace_hazard_tags(
    session: AsyncSession,
    chemical_id: UUID,
    *,
    group_id: UUID,
    tag_ids: list[UUID],
) -> list[HazardTag]:
    """Replace all hazard tag assignments for a chemical.

    Validates that all tags belong to the same group as the chemical.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical_id : UUID
        The ID of the chemical.
    group_id : UUID
        The group that the chemical belongs to; all tags must also belong here.
    tag_ids : list[UUID]
        New list of hazard tag IDs.

    Returns
    -------
    list[HazardTag]
        The HazardTag objects for the new assignments.

    Raises
    ------
    ValueError
        If any hazard tag ID is not found.
    CrossGroupError
        If any hazard tag does not belong to ``group_id``.
    """
    # Validate all tags belong to the group
    tags = []
    for tag_id in tag_ids:
        tag = await session.get(HazardTag, tag_id)
        if tag is None:
            raise ValueError(f"Hazard tag {tag_id} not found")
        if tag.group_id != group_id:
            raise CrossGroupError(
                f"Hazard tag {tag_id} does not belong to group {group_id}"
            )
        tags.append(tag)

    # Delete existing links
    result = await session.exec(
        select(ChemicalHazardTag).where(ChemicalHazardTag.chemical_id == chemical_id)
    )
    for link in result.all():
        await session.delete(link)
    await session.flush()

    # Create new links
    for tag_id in tag_ids:
        session.add(ChemicalHazardTag(chemical_id=chemical_id, hazard_tag_id=tag_id))
    await session.flush()
    return tags


async def archive_chemical(
    session: AsyncSession, chemical_id: UUID
) -> None:
    """Set a chemical's is_archived flag to True.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical_id : UUID
        The ID of the chemical to archive.

    Raises
    ------
    ChemicalNotFound
        If no chemical with the given ID exists.
    """
    chem = await session.get(Chemical, chemical_id)
    if chem is None:
        raise ChemicalNotFound(str(chemical_id))
    chem.is_archived = True
    chem.archived_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(chem)
    await session.commit()


async def unarchive_chemical(
    session: AsyncSession, chemical_id: UUID
) -> None:
    """Clear a chemical's is_archived flag.

    Parameters
    ----------
    session : AsyncSession
        The database session.
    chemical_id : UUID
        The ID of the chemical to unarchive.

    Raises
    ------
    ChemicalNotFound
        If no chemical with the given ID exists.
    """
    chem = await session.get(Chemical, chemical_id)
    if chem is None:
        raise ChemicalNotFound(str(chemical_id))
    chem.is_archived = False
    chem.archived_at = None
    session.add(chem)
    await session.commit()
