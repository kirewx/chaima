from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from chaima.dependencies import CurrentUserDep, GroupAdminDep, SessionDep
from chaima.services import import_ as import_service

router = APIRouter(prefix="/api/v1/groups/{group_id}/import", tags=["import"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class PreviousImport(BaseModel):
    imported_at: datetime
    imported_by_name: str
    row_count: int


class PreviewResponse(BaseModel):
    columns: list[str]
    rows: list[list[str]]
    row_count: int
    sheets: list[str] | None
    detected_mapping: dict[str, str]
    previous_import: PreviousImport | None = None


class LocationMappingBody(BaseModel):
    source_text: str
    location_id: UUID | None = None
    new_location: dict | None = None


class ChemicalGroupBody(BaseModel):
    canonical_name: str
    canonical_cas: str | None = None
    row_indices: list[int]


class CommitBody(BaseModel):
    file_name: str = ""
    column_mapping: dict[str, str]
    quantity_unit_combined_column: str | None = None
    columns: list[str]
    rows: list[list[str]]
    location_mapping: list[LocationMappingBody]
    chemical_groups: list[ChemicalGroupBody]


class WarningItem(BaseModel):
    chemical: str
    row: int
    details: str


class CommitResponse(BaseModel):
    created_chemicals: int
    created_containers: int
    created_locations: int
    skipped_rows: list[dict] = []
    warnings: list[WarningItem] = []


@router.post("/preview", response_model=PreviewResponse)
async def preview(
    group_id: UUID,
    session: SessionDep,
    admin: GroupAdminDep,
    file: UploadFile = File(...),
    sheet_name: str | None = None,
) -> PreviewResponse:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(data)} bytes, max {MAX_UPLOAD_BYTES}).",
        )
    lower = (file.filename or "").lower()
    if lower.endswith(".xlsx"):
        fmt = "xlsx"
    elif lower.endswith(".csv"):
        fmt = "csv"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx and .csv are supported.",
        )
    try:
        grid = import_service.parse_upload(data, fmt, sheet_name=sheet_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    prev = await import_service.find_previous_import(
        session, group_id=group_id, file_name=file.filename or "",
    )

    return PreviewResponse(
        columns=grid.columns,
        rows=grid.rows,
        row_count=grid.row_count,
        sheets=grid.sheets,
        detected_mapping=import_service.detect_header_mapping(grid.columns),
        previous_import=PreviousImport(
            imported_at=prev.created_at,
            imported_by_name=prev.user.email,
            row_count=prev.row_count,
        ) if prev else None,
    )


@router.post("/commit", response_model=CommitResponse)
async def commit(
    group_id: UUID,
    body: CommitBody,
    session: SessionDep,
    admin: GroupAdminDep,
    user: CurrentUserDep,
) -> CommitResponse:
    payload = import_service.CommitPayload(
        column_mapping=body.column_mapping,
        quantity_unit_combined_column=body.quantity_unit_combined_column,
        columns=body.columns,
        rows=body.rows,
        location_mapping=[
            import_service.LocationMapping(
                source_text=lm.source_text,
                location_id=lm.location_id,
                new_location=lm.new_location,
            )
            for lm in body.location_mapping
        ],
        chemical_groups=[
            import_service.ChemicalGroupPayload(
                canonical_name=cg.canonical_name,
                canonical_cas=cg.canonical_cas,
                row_indices=cg.row_indices,
            )
            for cg in body.chemical_groups
        ],
    )
    try:
        summary = await import_service.commit_import(
            session, group_id=group_id, viewer_id=user.id, payload=payload,
        )
        if body.file_name:
            await import_service.log_import(
                session,
                group_id=group_id,
                file_name=body.file_name,
                imported_by=user.id,
                row_count=len(body.rows),
            )
        await session.commit()
    except import_service.ImportValidationError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Validation failed", "errors": exc.errors},
        )
    except import_service.MappingValidationError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    return CommitResponse(
        created_chemicals=summary.created_chemicals,
        created_containers=summary.created_containers,
        created_locations=summary.created_locations,
        skipped_rows=summary.skipped_rows,
        warnings=summary.warnings,
    )
