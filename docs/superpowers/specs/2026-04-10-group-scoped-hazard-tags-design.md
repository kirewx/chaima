# Group-Scoped Hazard Tags

## Problem

`HazardTag` and `HazardTagIncompatibility` are currently global — all groups share the same tag catalog. Different groups (labs) may have different hazard classification requirements, so hazard tags must be group-scoped.

`GHSCode` remains global (internationally standardized codes).

## Decision: Approach C — DB constraint + service-layer validation

- DB enforces structural integrity (composite uniqueness on tag name + group)
- Service-layer validation (deferred) will enforce cross-entity logic (same-group checks)

## Model Changes

### HazardTag

- Add `group_id: UUID` — required FK to `group.id`, indexed
- Replace global `unique=True` on `name` with composite `UniqueConstraint("name", "group_id")`
- Add `group: Group` relationship with `back_populates="hazard_tags"`

### Group

- Add `hazard_tags: list[HazardTag]` relationship with `back_populates="group"`

### HazardTagIncompatibility

No structural changes. Implicitly scoped through the two `HazardTag` FKs it references (both tags belong to a group).

### ChemicalHazardTag

No structural changes. Junction table stays the same.

### Initial Migration

Updated in-place — project is not yet released, so no new Alembic version file needed.

## Validation (Deferred)

The following checks are deferred until routes/services are implemented:

1. **HazardTagIncompatibility same-group check** — both tags must belong to the same group
2. **ChemicalHazardTag same-group check** — chemical and tag must belong to the same group

## Test Changes

- Update all existing hazard tests to pass `group_id` when creating `HazardTag`
- Add new test: same tag name in different groups succeeds (verifying per-group uniqueness)
