"""Compatibility endpoints: location conflicts + placement check."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from chaima.dependencies import CurrentUserDep, GroupMemberDep, SessionDep
from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.ghs import ChemicalGHS
from chaima.models.hazard import ChemicalHazardTag
from chaima.schemas.compatibility import ConflictRead
from chaima.services.chemicals import apply_secret_filter
from chaima.services.hazard_compatibility import (
    location_conflicts as svc_location_conflicts,
    pair_conflicts_async,
)
from chaima.services.orders import _validate_location_in_group

router = APIRouter(prefix="/api/v1/groups/{group_id}", tags=["compatibility"])


def _to_read(c) -> ConflictRead:
    return ConflictRead(
        chem_a_name=c.chem_a_name,
        chem_b_name=c.chem_b_name,
        kind=c.kind,
        code_or_tag=c.code_or_tag,
        reason=c.reason,
    )


@router.get(
    "/locations/{location_id}/conflicts",
    response_model=list[ConflictRead],
)
async def get_location_conflicts(
    group_id: UUID,
    location_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
):
    """Return pairwise conflicts among chemicals stored under this location subtree."""
    conflicts = await svc_location_conflicts(
        session, group_id, location_id, viewer=user
    )
    return [_to_read(c) for c in conflicts]


@router.get(
    "/compatibility/check",
    response_model=list[ConflictRead],
)
async def check_compatibility(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    user: CurrentUserDep,
    chemical_id: UUID = Query(...),
    location_id: UUID = Query(...),
):
    """Predict conflicts if `chemical_id` were placed under `location_id`."""
    # Location must be linked to the caller's group.
    if not await _validate_location_in_group(session, group_id, location_id):
        raise HTTPException(status_code=404, detail="Location not found")

    # Candidate chemical: scoped to the caller's group, secret-filtered, and
    # eager-loaded so the rules engine never triggers a lazy load (MissingGreenlet).
    cand_stmt = (
        select(Chemical)
        .where(Chemical.id == chemical_id, Chemical.group_id == group_id)
        .options(
            selectinload(Chemical.ghs_links).selectinload(ChemicalGHS.ghs_code),
            selectinload(Chemical.hazard_tag_links).selectinload(
                ChemicalHazardTag.hazard_tag
            ),
        )
    )
    cand_stmt = apply_secret_filter(cand_stmt, user)
    candidate = (await session.execute(cand_stmt)).scalars().first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Chemical not found")

    cand_codes = [link.ghs_code for link in candidate.ghs_links]
    cand_tags = [link.hazard_tag for link in candidate.hazard_tag_links]

    stored_stmt = (
        select(Chemical)
        .join(Container, Container.chemical_id == Chemical.id)
        .where(
            Container.location_id == location_id,
            Container.is_archived == False,  # noqa: E712
            Chemical.group_id == group_id,
        )
        .options(
            selectinload(Chemical.ghs_links).selectinload(ChemicalGHS.ghs_code),
            selectinload(Chemical.hazard_tag_links).selectinload(
                ChemicalHazardTag.hazard_tag
            ),
        )
    )
    stored_stmt = apply_secret_filter(stored_stmt, user)
    rows = (await session.execute(stored_stmt)).scalars().unique().all()

    out: list[ConflictRead] = []
    for other in rows:
        if other.id == chemical_id:
            continue
        other_codes = [link.ghs_code for link in other.ghs_links]
        other_tags = [link.hazard_tag for link in other.hazard_tag_links]
        conflicts = await pair_conflicts_async(
            session=session,
            group_id=group_id,
            a_codes=cand_codes, a_tags=cand_tags, a_name=candidate.name,
            b_codes=other_codes, b_tags=other_tags, b_name=other.name,
        )
        out.extend(_to_read(c) for c in conflicts)
    return out
