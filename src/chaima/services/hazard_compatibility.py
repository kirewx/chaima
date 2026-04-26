"""Hazard compatibility rules engine.

Pure functions over GHS codes + hazard tags. No DB writes; only reads
HazardTagIncompatibility for the user-defined tag rules.

Limitations (v1):
- Acid/base discrimination for GHS05 corrosives is name-based and best-effort.
- Conservative: when in doubt, return a conflict so the user is warned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Conflict:
    chem_a_name: str
    chem_b_name: str
    kind: str  # "ghs" | "tag"
    code_or_tag: str
    reason: str


# --- GHS rules --------------------------------------------------------------

# Pairs that are categorically incompatible regardless of name.
_HARD_PAIRS: list[tuple[str, str, str]] = [
    ("GHS02", "GHS03", "Flammable + oxidizer: fire/explosion risk"),
    ("GHS01", "GHS02", "Explosive + flammable: detonation risk"),
    ("GHS01", "GHS03", "Explosive + oxidizer: detonation risk"),
]

_ACID_NAME = re.compile(r"\b(acid|hcl|h2so4|hno3|hf|hbr)\b", re.IGNORECASE)
_BASE_NAME = re.compile(
    r"\b(hydroxide|amine|naoh|koh|ammonia|lithium hydroxide)\b", re.IGNORECASE
)


def _has_code(codes: Iterable[object], code: str) -> bool:
    return any(getattr(c, "code", None) == code for c in codes)


def _is_acid(name: str) -> bool:
    return bool(_ACID_NAME.search(name or ""))


def _is_base(name: str) -> bool:
    return bool(_BASE_NAME.search(name or ""))


def _ghs_pair_conflicts(
    a_codes: Iterable[object], b_codes: Iterable[object],
    a_name: str, b_name: str,
) -> list[Conflict]:
    out: list[Conflict] = []

    # Hardcoded pictogram pairs
    for left, right, reason in _HARD_PAIRS:
        if (_has_code(a_codes, left) and _has_code(b_codes, right)) or (
            _has_code(a_codes, right) and _has_code(b_codes, left)
        ):
            out.append(
                Conflict(
                    chem_a_name=a_name,
                    chem_b_name=b_name,
                    kind="ghs",
                    code_or_tag=f"{left}+{right}",
                    reason=reason,
                )
            )

    # Acid + base — both carry GHS05.
    if _has_code(a_codes, "GHS05") and _has_code(b_codes, "GHS05"):
        a_acid = _is_acid(a_name)
        a_base = _is_base(a_name)
        b_acid = _is_acid(b_name)
        b_base = _is_base(b_name)
        # Conservative: warn unless both are clearly the same kind.
        if (a_acid and b_base) or (a_base and b_acid) or (
            not (a_acid or a_base) or not (b_acid or b_base)
        ):
            out.append(
                Conflict(
                    chem_a_name=a_name,
                    chem_b_name=b_name,
                    kind="ghs",
                    code_or_tag="GHS05+GHS05",
                    reason="Two corrosives in same storage: violent neutralization risk if acid+base",
                )
            )

    return out


# --- Tag rules --------------------------------------------------------------


async def _tag_pair_conflicts(
    session: AsyncSession,
    group_id: UUID,
    a_tag_ids: list[UUID],
    b_tag_ids: list[UUID],
    a_name: str,
    b_name: str,
) -> list[Conflict]:
    if not a_tag_ids or not b_tag_ids:
        return []

    # Late import to avoid circulars at module import time.
    from chaima.models.hazard import HazardTag, HazardTagIncompatibility

    stmt = select(HazardTagIncompatibility).where(
        or_(
            HazardTagIncompatibility.tag_a_id.in_(a_tag_ids),
            HazardTagIncompatibility.tag_b_id.in_(a_tag_ids),
        )
    )
    rows = (await session.execute(stmt)).scalars().all()

    out: list[Conflict] = []
    a_set = set(a_tag_ids)
    b_set = set(b_tag_ids)
    for row in rows:
        if (row.tag_a_id in a_set and row.tag_b_id in b_set) or (
            row.tag_b_id in a_set and row.tag_a_id in b_set
        ):
            # Resolve names for display.
            tag_ids = [row.tag_a_id, row.tag_b_id]
            tags = (
                await session.execute(
                    select(HazardTag).where(HazardTag.id.in_(tag_ids))
                )
            ).scalars().all()
            label = " + ".join(t.name for t in tags)
            out.append(
                Conflict(
                    chem_a_name=a_name,
                    chem_b_name=b_name,
                    kind="tag",
                    code_or_tag=label,
                    reason=row.reason or "Group-defined tag incompatibility",
                )
            )
    return out


# --- Public API -------------------------------------------------------------


def pair_conflicts(
    *,
    session: AsyncSession | None,
    group_id: UUID | None,
    a_codes: Iterable[object],
    a_tags: Iterable[object],
    a_name: str,
    b_codes: Iterable[object],
    b_tags: Iterable[object],
    b_name: str,
) -> list[Conflict]:
    """Conflicts between chemicals A and B. Tag conflicts require a session.

    Sync wrapper around the GHS rules. For tag rules, callers should use
    `pair_conflicts_async`. The unit-test code paths only exercise GHS rules
    and therefore pass session=None.
    """
    return _ghs_pair_conflicts(a_codes, b_codes, a_name, b_name)


async def pair_conflicts_async(
    *,
    session: AsyncSession,
    group_id: UUID,
    a_codes: Iterable[object],
    a_tags: Iterable[object],
    a_name: str,
    b_codes: Iterable[object],
    b_tags: Iterable[object],
    b_name: str,
) -> list[Conflict]:
    """Async variant that also includes tag-based conflicts."""
    out = _ghs_pair_conflicts(a_codes, b_codes, a_name, b_name)
    a_tag_ids = [getattr(t, "id", t) for t in a_tags]
    b_tag_ids = [getattr(t, "id", t) for t in b_tags]
    out.extend(
        await _tag_pair_conflicts(
            session, group_id, a_tag_ids, b_tag_ids, a_name, b_name
        )
    )
    return out


async def location_conflicts(
    session: AsyncSession,
    group_id: UUID,
    location_id: UUID,
) -> list[Conflict]:
    """Pairwise conflicts among all chemicals stored under this location subtree."""
    from chaima.models.chemical import Chemical
    from chaima.models.container import Container
    from chaima.models.storage import StorageLocation

    # Walk subtree of locations under location_id (use a recursive CTE if the
    # storage_location table is treelike; otherwise direct children only — verify
    # against the existing models during implementation).
    sub_ids: list[UUID] = [location_id]
    children = (
        await session.execute(
            select(StorageLocation.id).where(StorageLocation.parent_id == location_id)
        )
    ).scalars().all()
    sub_ids.extend(children)

    rows = (
        await session.execute(
            select(Container, Chemical)
            .join(Chemical, Container.chemical_id == Chemical.id)
            .where(Container.location_id.in_(sub_ids))
        )
    ).all()

    chemicals = []
    seen_chem_ids: set[UUID] = set()
    for container, chem in rows:
        if chem.id in seen_chem_ids:
            continue
        seen_chem_ids.add(chem.id)
        # Eager-load relationships needed for rules.
        await session.refresh(chem, attribute_names=["ghs_links", "hazard_tag_links"])
        chem_codes = [link.ghs_code for link in chem.ghs_links]
        chem_tags = [link.hazard_tag for link in chem.hazard_tag_links]
        chemicals.append((chem, chem_codes, chem_tags))

    out: list[Conflict] = []
    for i in range(len(chemicals)):
        for j in range(i + 1, len(chemicals)):
            ca, codes_a, tags_a = chemicals[i]
            cb, codes_b, tags_b = chemicals[j]
            out.extend(
                await pair_conflicts_async(
                    session=session,
                    group_id=group_id,
                    a_codes=codes_a, a_tags=tags_a, a_name=ca.name,
                    b_codes=codes_b, b_tags=tags_b, b_name=cb.name,
                )
            )
    return out
