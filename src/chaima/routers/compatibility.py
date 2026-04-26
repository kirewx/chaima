"""Compatibility endpoints: location conflicts + placement check."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from chaima.dependencies import GroupMemberDep, SessionDep
from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.schemas.compatibility import ConflictRead
from chaima.services.hazard_compatibility import (
    location_conflicts as svc_location_conflicts,
    pair_conflicts_async,
)

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
):
    """Return pairwise conflicts among chemicals stored under this location subtree."""
    conflicts = await svc_location_conflicts(session, group_id, location_id)
    return [_to_read(c) for c in conflicts]


@router.get(
    "/compatibility/check",
    response_model=list[ConflictRead],
)
async def check_compatibility(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    chemical_id: UUID = Query(...),
    location_id: UUID = Query(...),
):
    """Predict conflicts if `chemical_id` were placed under `location_id`."""
    candidate = await session.get(Chemical, chemical_id)
    if candidate is None:
        return []
    await session.refresh(candidate, attribute_names=["ghs_links", "hazard_tag_links"])
    cand_codes = [link.ghs_code for link in candidate.ghs_links]
    cand_tags = [link.hazard_tag for link in candidate.hazard_tag_links]

    rows = (
        await session.execute(
            select(Chemical)
            .join(Container, Container.chemical_id == Chemical.id)
            .where(Container.location_id == location_id)
        )
    ).scalars().unique().all()

    out: list[ConflictRead] = []
    for other in rows:
        if other.id == chemical_id:
            continue
        await session.refresh(other, attribute_names=["ghs_links", "hazard_tag_links"])
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
