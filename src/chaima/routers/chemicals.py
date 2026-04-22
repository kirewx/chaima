# src/chaima/routers/chemicals.py
import hashlib
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError

from chaima.dependencies import CurrentUserDep, GroupMemberDep, SessionDep
from chaima.schemas.chemical import (
    ChemicalCreate,
    ChemicalDetail,
    ChemicalRead,
    ChemicalUpdate,
    GHSCodeBulkUpdate,
    GHSCodeReadNested,
    HazardTagBulkUpdate,
    HazardTagReadNested,
    SynonymBulkUpdate,
    SynonymRead,
)
from chaima.schemas.pagination import PaginatedResponse
from chaima.models.chemical import Chemical
from chaima.services import chemicals as chemical_service
from chaima.services import files as files_service
from chaima.services.structure import InvalidSmilesError, render_structure_svg

router = APIRouter(prefix="/api/v1/groups/{group_id}/chemicals", tags=["chemicals"])


@router.get("/check-exists")
async def check_chemical_exists(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    name: str | None = Query(None),
    cas: str | None = Query(None),
) -> dict:
    """Check if a chemical with the given name or CAS already exists.

    Returns the existing chemical's id and archived status, or null.
    """
    chem = await chemical_service.find_existing(session, group_id, name=name, cas=cas)
    if chem is None:
        return {"exists": False}
    return {
        "exists": True,
        "chemical_id": str(chem.id),
        "chemical_name": chem.name,
        "is_archived": chem.is_archived,
    }


@router.get("", response_model=PaginatedResponse[ChemicalRead])
async def list_chemicals(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
    search: str | None = Query(None),
    hazard_tag_id: UUID | None = Query(None),
    ghs_code_id: UUID | None = Query(None),
    has_containers: bool | None = Query(None),
    my_secrets: bool = Query(False),
    location_id: UUID | None = Query(None),
    include_archived: bool = Query(False),
    sort: str = Query("name"),
    order: str = Query("asc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ChemicalRead]:
    """List chemicals in a group.

    Parameters
    ----------
    group_id : UUID
        Group to list chemicals for.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.
    search : str or None, optional
        Filter by name or CAS (case-insensitive partial match).
    hazard_tag_id : UUID or None, optional
        Filter to chemicals with this hazard tag.
    ghs_code_id : UUID or None, optional
        Filter to chemicals with this GHS code.
    has_containers : bool or None, optional
        Filter by active container presence.
    sort : str, optional
        Sort field. Defaults to ``"name"``.
    order : str, optional
        Sort direction. Defaults to ``"asc"``.
    offset : int, optional
        Pagination offset. Defaults to 0.
    limit : int, optional
        Page size. Defaults to 20.

    Returns
    -------
    PaginatedResponse[ChemicalRead]
        Paginated list of chemicals.
    """
    items, total = await chemical_service.list_chemicals(
        session,
        group_id,
        viewer=user,
        search=search,
        hazard_tag_id=hazard_tag_id,
        ghs_code_id=ghs_code_id,
        has_containers=has_containers,
        my_secrets=my_secrets,
        location_id=location_id,
        include_archived=include_archived,
        sort=sort,
        order=order,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        items=[ChemicalRead.model_validate(i, from_attributes=True) for i in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=ChemicalRead, status_code=status.HTTP_201_CREATED)
async def create_chemical(
    group_id: UUID,
    body: ChemicalCreate,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
) -> ChemicalRead:
    """Create a chemical in a group.

    Parameters
    ----------
    group_id : UUID
        Group to create the chemical in.
    body : ChemicalCreate
        Chemical creation data.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.
    user : CurrentUserDep
        Authenticated user (set as creator).

    Returns
    -------
    ChemicalRead
        The newly created chemical.
    """
    try:
        chem = await chemical_service.create_chemical(
            session,
            group_id=group_id,
            created_by=user.id,
            name=body.name,
            cas=body.cas,
            smiles=body.smiles,
            cid=body.cid,
            structure=body.structure,
            molar_mass=body.molar_mass,
            density=body.density,
            melting_point=body.melting_point,
            boiling_point=body.boiling_point,
            comment=body.comment,
            is_secret=body.is_secret,
            sds_path=body.sds_path,
            synonyms=body.synonyms,
            ghs_codes=body.ghs_codes,
        )
    except chemical_service.DuplicateNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "A chemical with this name already exists in the group",
                "existing_chemical_id": str(exc.chemical_id),
                "is_archived": exc.is_archived,
            },
        )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A chemical with this name already exists in the group",
        )
    await session.refresh(chem)
    return ChemicalRead.model_validate(chem, from_attributes=True)


@router.get("/{chemical_id}", response_model=ChemicalDetail)
async def get_chemical(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> ChemicalDetail:
    """Get chemical detail including synonyms, GHS codes, and hazard tags.

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Returns
    -------
    ChemicalDetail
        Full chemical detail with all sub-resources.

    Raises
    ------
    HTTPException
        404 if the chemical is not found or belongs to a different group.
    """
    chem = await chemical_service.get_chemical_detail(session, chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found")
    return ChemicalDetail(
        **ChemicalRead.model_validate(chem, from_attributes=True).model_dump(),
        synonyms=[SynonymRead.model_validate(s, from_attributes=True) for s in chem.synonyms],
        ghs_codes=[
            GHSCodeReadNested.model_validate(link.ghs_code, from_attributes=True)
            for link in chem.ghs_links
        ],
        hazard_tags=[
            HazardTagReadNested.model_validate(link.hazard_tag, from_attributes=True)
            for link in chem.hazard_tag_links
        ],
    )


@router.get("/{chemical_id}/structure.svg", include_in_schema=False)
async def get_chemical_structure_svg(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> Response:
    """Render the chemical's structure as an SVG from its SMILES via RDKit.

    The SVG uses ``currentColor`` for strokes and has a transparent
    background, so it adapts to light and dark mode via CSS without
    any theme-specific render.

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Returns
    -------
    Response
        An ``image/svg+xml`` response with long cache headers.

    Raises
    ------
    HTTPException
        404 if the chemical does not exist, belongs to a different
        group, or has no SMILES. 422 if RDKit cannot parse the SMILES.
    """
    chem = await session.get(Chemical, chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found"
        )
    if not chem.smiles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chemical has no SMILES"
        )
    try:
        svg = render_structure_svg(chem.smiles)
    except InvalidSmilesError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    updated_at = getattr(chem, "updated_at", None) or getattr(chem, "created_at", None)
    etag_seed = f"{chem.id}:{updated_at.isoformat() if updated_at else ''}"
    etag = hashlib.sha256(etag_seed.encode("utf-8")).hexdigest()[:16]
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=3600",
            "ETag": f'W/"{etag}"',
        },
    )


@router.patch("/{chemical_id}", response_model=ChemicalRead)
async def update_chemical(
    group_id: UUID,
    chemical_id: UUID,
    body: ChemicalUpdate,
    session: SessionDep,
    member: GroupMemberDep,
) -> ChemicalRead:
    """Update chemical scalar fields.

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    body : ChemicalUpdate
        Fields to update (all optional).
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Returns
    -------
    ChemicalRead
        The updated chemical.

    Raises
    ------
    HTTPException
        404 if the chemical is not found or belongs to a different group.
    """
    chem = await chemical_service.get_chemical(session, chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found")
    updated = await chemical_service.update_chemical(
        session, chem, **body.model_dump(exclude_unset=True)
    )
    await session.commit()
    return ChemicalRead.model_validate(updated, from_attributes=True)


@router.delete("/{chemical_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chemical(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
    """Delete a chemical.

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Raises
    ------
    HTTPException
        404 if the chemical is not found or belongs to a different group.
    """
    chem = await chemical_service.get_chemical(session, chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found")
    await chemical_service.delete_chemical(session, chem)
    await session.commit()


@router.put("/{chemical_id}/synonyms", response_model=list[SynonymRead])
async def replace_synonyms(
    group_id: UUID,
    chemical_id: UUID,
    body: SynonymBulkUpdate,
    session: SessionDep,
    member: GroupMemberDep,
) -> list[SynonymRead]:
    """Bulk-replace all synonyms for a chemical.

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    body : SynonymBulkUpdate
        New synonym list.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Returns
    -------
    list[SynonymRead]
        The new synonym list.

    Raises
    ------
    HTTPException
        404 if the chemical is not found or belongs to a different group.
    """
    chem = await chemical_service.get_chemical(session, chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found")
    synonyms = await chemical_service.replace_synonyms(
        session, chemical_id, [s.model_dump() for s in body.synonyms]
    )
    await session.commit()
    return [SynonymRead.model_validate(s, from_attributes=True) for s in synonyms]


@router.put("/{chemical_id}/ghs-codes", response_model=list[GHSCodeReadNested])
async def replace_ghs_codes(
    group_id: UUID,
    chemical_id: UUID,
    body: GHSCodeBulkUpdate,
    session: SessionDep,
    member: GroupMemberDep,
) -> list[GHSCodeReadNested]:
    """Bulk-replace GHS code assignments for a chemical.

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    body : GHSCodeBulkUpdate
        New list of GHS code IDs.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Returns
    -------
    list[GHSCodeReadNested]
        The updated GHS codes.

    Raises
    ------
    HTTPException
        400 if any GHS code ID is invalid.
        404 if the chemical is not found.
    """
    chem = await chemical_service.get_chemical(session, chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found")
    try:
        codes = await chemical_service.replace_ghs_codes(session, chemical_id, body.ghs_ids)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await session.commit()
    return [GHSCodeReadNested.model_validate(c, from_attributes=True) for c in codes]


@router.post("/{chemical_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
    """Archive a chemical (hide from default listing).

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Raises
    ------
    HTTPException
        404 if the chemical is not found.
    """
    try:
        await chemical_service.archive_chemical(session, chemical_id)
    except chemical_service.ChemicalNotFound:
        raise HTTPException(status_code=404, detail="Chemical not found")


@router.post("/{chemical_id}/unarchive", status_code=status.HTTP_204_NO_CONTENT)
async def unarchive(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
    """Restore an archived chemical back to the default listing.

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Raises
    ------
    HTTPException
        404 if the chemical is not found.
    """
    try:
        await chemical_service.unarchive_chemical(session, chemical_id)
    except chemical_service.ChemicalNotFound:
        raise HTTPException(status_code=404, detail="Chemical not found")


@router.put("/{chemical_id}/hazard-tags", response_model=list[HazardTagReadNested])
async def replace_hazard_tags(
    group_id: UUID,
    chemical_id: UUID,
    body: HazardTagBulkUpdate,
    session: SessionDep,
    member: GroupMemberDep,
) -> list[HazardTagReadNested]:
    """Bulk-replace hazard tag assignments for a chemical.

    All tags must belong to the same group as the chemical.

    Parameters
    ----------
    group_id : UUID
        Group the chemical belongs to.
    chemical_id : UUID
        Chemical ID.
    body : HazardTagBulkUpdate
        New list of hazard tag IDs.
    session : SessionDep
        Database session.
    member : GroupMemberDep
        Verified group membership.

    Returns
    -------
    list[HazardTagReadNested]
        The updated hazard tags.

    Raises
    ------
    HTTPException
        400 if tags are from a different group or IDs are invalid.
        404 if the chemical is not found.
    """
    chem = await chemical_service.get_chemical(session, chemical_id)
    if chem is None or chem.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chemical not found")
    try:
        tags = await chemical_service.replace_hazard_tags(
            session, chemical_id, group_id=group_id, tag_ids=body.hazard_tag_ids
        )
    except chemical_service.CrossGroupError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All hazard tags must belong to this group",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await session.commit()
    return [HazardTagReadNested.model_validate(t, from_attributes=True) for t in tags]


@router.post("/{chemical_id}/sds", response_model=ChemicalRead)
async def upload_sds(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    file: UploadFile = File(...),
) -> ChemicalRead:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="SDS must be a PDF")
    data = await file.read()
    path = files_service.save_upload(group_id, file.filename or "sds.pdf", data)
    chem = await session.get(Chemical, chemical_id)
    if chem is None:
        raise HTTPException(status_code=404, detail="Chemical not found")
    chem.sds_path = path
    session.add(chem)
    await session.commit()
    await session.refresh(chem)
    return ChemicalRead.model_validate(chem)
