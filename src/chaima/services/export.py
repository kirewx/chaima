# src/chaima/services/export.py
import csv
from io import BytesIO, StringIO
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.ghs import ChemicalGHS
from chaima.models.hazard import ChemicalHazardTag
from chaima.models.container import Container
from chaima.services.chemicals import list_chemicals as list_chemicals_service


EXPORT_COLUMNS = [
    "name", "cas", "smiles", "location", "identifier", "quantity", "unit",
    "purity", "ordered_by", "supplier", "purchased_at", "comment",
    "ghs_codes", "hazard_tags", "is_archived",
]

EXPORT_ROW_CAP = 10_000


class ExportTooLargeError(Exception):
    """Raised when the filtered export would exceed EXPORT_ROW_CAP."""


async def _load_chemicals_with_containers(
    session: AsyncSession, group_id: UUID, filters: dict[str, Any], viewer_id: UUID
) -> list[Chemical]:
    # Delegate filtering to the canonical list endpoint with limit high enough
    # to hit the row cap before anything else. Then eager-load relationships.
    from chaima.models.user import User
    viewer = await session.get(User, viewer_id)
    items, _ = await list_chemicals_service(
        session,
        group_id,
        viewer=viewer,
        search=filters.get("search"),
        hazard_tag_id=filters.get("hazard_tag_id"),
        ghs_code_id=filters.get("ghs_code_id"),
        has_containers=filters.get("has_containers"),
        my_secrets=filters.get("my_secrets", False),
        location_id=filters.get("location_id"),
        include_archived=filters.get("include_archived", False),
        sort="name",
        order="asc",
        offset=0,
        limit=EXPORT_ROW_CAP + 1,
    )
    ids = [c.id for c in items]
    if not ids:
        return []
    stmt = (
        select(Chemical)
        .where(Chemical.id.in_(ids))
        .options(
            selectinload(Chemical.containers).selectinload(Container.location),
            selectinload(Chemical.containers).selectinload(Container.supplier),
            selectinload(Chemical.ghs_links).selectinload(ChemicalGHS.ghs_code),
            selectinload(Chemical.hazard_tag_links).selectinload(ChemicalHazardTag.hazard_tag),
        )
        .order_by(Chemical.name)
    )
    result = await session.exec(stmt)
    return list(result.all())


def _row_for_container(chem: Chemical, container: Container | None) -> list[str]:
    ghs = ";".join(sorted(link.ghs_code.code for link in chem.ghs_links))
    tags = ";".join(sorted(link.hazard_tag.name for link in chem.hazard_tag_links))
    if container is None:
        return [
            chem.name, chem.cas or "", chem.smiles or "",
            "", "", "", "", "", "", "", "", chem.comment or "",
            ghs, tags, str(chem.is_archived),
        ]
    return [
        chem.name, chem.cas or "", chem.smiles or "",
        container.location.name if container.location else "",
        container.identifier,
        str(container.amount),
        container.unit,
        container.purity or "",
        container.ordered_by_name or "",
        container.supplier.name if container.supplier else "",
        container.purchased_at.isoformat() if container.purchased_at else "",
        chem.comment or "",
        ghs, tags, str(container.is_archived),
    ]


def _build_rows(chemicals: list[Chemical]) -> list[list[str]]:
    rows: list[list[str]] = []
    for chem in chemicals:
        if not chem.containers:
            rows.append(_row_for_container(chem, None))
        else:
            for container in chem.containers:
                rows.append(_row_for_container(chem, container))
    return rows


async def export_chemicals(
    session: AsyncSession,
    group_id: UUID,
    *,
    viewer_id: UUID,
    filters: dict[str, Any],
    fmt: Literal["csv", "xlsx"],
) -> bytes:
    chemicals = await _load_chemicals_with_containers(session, group_id, filters, viewer_id)
    rows = _build_rows(chemicals)
    if len(rows) > EXPORT_ROW_CAP:
        raise ExportTooLargeError(
            f"Export would produce {len(rows)} rows (cap: {EXPORT_ROW_CAP}). Narrow the filter."
        )

    if fmt == "csv":
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(EXPORT_COLUMNS)
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    if fmt == "xlsx":
        return _to_xlsx(rows)

    raise ValueError(f"Unsupported format: {fmt}")


def _to_xlsx(rows: list[list[str]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Chemicals"
    ws.append(EXPORT_COLUMNS)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
