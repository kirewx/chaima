# Group-Scoped Hazard Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `HazardTag` group-scoped so different groups can define their own hazard tags independently.

**Architecture:** Add `group_id` FK to `HazardTag`, replace global name uniqueness with per-group uniqueness via composite constraint. Update initial Alembic migration in-place (not released). Update tests to supply `group_id` and verify per-group uniqueness.

**Tech Stack:** SQLModel, pytest, pytest-asyncio, Alembic

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/chaima/models/hazard.py` | Modify | Add `group_id` FK and relationship to `HazardTag`, update unique constraint |
| `src/chaima/models/group.py` | Modify | Add `hazard_tags` back-populates relationship |
| `alembic/versions/bb0857b3e226_initial_schema.py` | Modify | Update `hazard_tag` table to include `group_id` column, FK, index, and composite unique constraint |
| `tests/test_models/test_hazard.py` | Modify | Update all tests to pass `group_id`, add per-group uniqueness test |

---

### Task 1: Update HazardTag model with group_id

**Files:**
- Modify: `src/chaima/models/hazard.py:1-15`
- Modify: `src/chaima/models/group.py:19-20`

- [ ] **Step 1: Add group_id FK and relationship to HazardTag**

In `src/chaima/models/hazard.py`, update the `HazardTag` class:

```python
class HazardTag(SQLModel, table=True):
    __tablename__ = "hazard_tag"
    __table_args__ = (UniqueConstraint("name", "group_id"),)

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    name: str = Field(index=True)
    description: str | None = Field(default=None)

    group: "Group" = Relationship(back_populates="hazard_tags")
    chemical_links: list["ChemicalHazardTag"] = Relationship(back_populates="hazard_tag")
```

Key changes from the current model:
- Added `group_id` field with FK to `group.id` and index
- Removed `unique=True` from `name` (now handled by composite `UniqueConstraint`)
- Added `__table_args__` with `UniqueConstraint("name", "group_id")`
- Added `group` relationship

- [ ] **Step 2: Add hazard_tags back-populates on Group**

In `src/chaima/models/group.py`, add the relationship after the existing `suppliers` line (line 20):

```python
    chemicals: list["Chemical"] = Relationship(back_populates="group")
    suppliers: list["Supplier"] = Relationship(back_populates="group")
    hazard_tags: list["HazardTag"] = Relationship(back_populates="group")
```

- [ ] **Step 3: Run existing tests to see them fail**

Run: `uv run pytest tests/test_models/test_hazard.py -v`

Expected: All tests FAIL because `HazardTag` now requires `group_id`.

- [ ] **Step 4: Commit model changes**

```bash
git add src/chaima/models/hazard.py src/chaima/models/group.py
git commit -m "feat: add group_id to HazardTag for per-group scoping"
```

---

### Task 2: Update initial Alembic migration

**Files:**
- Modify: `alembic/versions/bb0857b3e226_initial_schema.py:43-49` (upgrade)
- Modify: `alembic/versions/bb0857b3e226_initial_schema.py:208-209` (downgrade)

- [ ] **Step 1: Update the hazard_tag table in upgrade()**

Replace the current `hazard_tag` table creation (lines 43-49) with:

```python
    op.create_table('hazard_tag',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('group_id', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['group.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'group_id')
    )
    op.create_index(op.f('ix_hazard_tag_group_id'), 'hazard_tag', ['group_id'], unique=False)
    op.create_index(op.f('ix_hazard_tag_name'), 'hazard_tag', ['name'], unique=False)
```

Key changes:
- Added `group_id` column (non-nullable)
- Added `ForeignKeyConstraint` to `group.id`
- Added `UniqueConstraint('name', 'group_id')` (composite, replaces global unique)
- Added `ix_hazard_tag_group_id` index
- Changed `ix_hazard_tag_name` index from `unique=True` to `unique=False`

- [ ] **Step 2: Update downgrade() to drop the new index**

In the `downgrade()` function, add the new index drop. Find the existing line:

```python
    op.drop_index(op.f('ix_hazard_tag_name'), table_name='hazard_tag')
```

Add the `group_id` index drop right after it:

```python
    op.drop_index(op.f('ix_hazard_tag_name'), table_name='hazard_tag')
    op.drop_index(op.f('ix_hazard_tag_group_id'), table_name='hazard_tag')
```

- [ ] **Step 3: Commit migration changes**

```bash
git add alembic/versions/bb0857b3e226_initial_schema.py
git commit -m "feat: update initial migration for group-scoped hazard_tag"
```

---

### Task 3: Update hazard tests

**Files:**
- Modify: `tests/test_models/test_hazard.py`

- [ ] **Step 1: Update test_create_hazard_tag to pass group_id**

```python
async def test_create_hazard_tag(session, group):
    tag = HazardTag(name="flammable", description="Catches fire easily", group_id=group.id)
    session.add(tag)
    await session.commit()

    result = await session.get(HazardTag, tag.id)
    assert result.name == "flammable"
    assert result.group_id == group.id
```

- [ ] **Step 2: Update test_hazard_tag_name_unique for per-group uniqueness**

Same name + same group should still conflict:

```python
async def test_hazard_tag_name_unique_within_group(session, group):
    session.add(HazardTag(name="flammable", group_id=group.id))
    await session.commit()
    session.add(HazardTag(name="flammable", group_id=group.id))
    with pytest.raises(IntegrityError):
        await session.commit()
```

- [ ] **Step 3: Add test for same name in different groups**

```python
async def test_hazard_tag_name_allowed_across_groups(session):
    group_a = Group(name="Lab Alpha")
    group_b = Group(name="Lab Beta")
    session.add_all([group_a, group_b])
    await session.flush()

    session.add(HazardTag(name="flammable", group_id=group_a.id))
    session.add(HazardTag(name="flammable", group_id=group_b.id))
    await session.commit()

    result = (await session.exec(
        select(HazardTag).where(HazardTag.name == "flammable")
    )).all()
    assert len(result) == 2
```

- [ ] **Step 4: Update test_link_chemical_to_hazard_tag**

```python
async def test_link_chemical_to_hazard_tag(session, chemical, group):
    tag = HazardTag(name="flammable", group_id=group.id)
    session.add(tag)
    await session.flush()

    session.add(ChemicalHazardTag(chemical_id=chemical.id, hazard_tag_id=tag.id))
    await session.commit()

    result = (await session.exec(
        select(ChemicalHazardTag).where(ChemicalHazardTag.chemical_id == chemical.id)
    )).all()
    assert len(result) == 1
    assert result[0].hazard_tag_id == tag.id
```

- [ ] **Step 5: Update test_incompatibility_pair**

```python
async def test_incompatibility_pair(session, group):
    acid = HazardTag(name="acid", group_id=group.id)
    base = HazardTag(name="base", group_id=group.id)
    session.add_all([acid, base])
    await session.flush()

    incompat = HazardTagIncompatibility(
        tag_a_id=acid.id,
        tag_b_id=base.id,
        reason="Exothermic neutralization reaction",
    )
    session.add(incompat)
    await session.commit()

    result = await session.get(HazardTagIncompatibility, incompat.id)
    assert result.reason == "Exothermic neutralization reaction"
```

- [ ] **Step 6: Update test_incompatibility_pair_unique**

```python
async def test_incompatibility_pair_unique(session, group):
    acid = HazardTag(name="acid", group_id=group.id)
    base = HazardTag(name="base", group_id=group.id)
    session.add_all([acid, base])
    await session.flush()

    session.add(HazardTagIncompatibility(tag_a_id=acid.id, tag_b_id=base.id))
    await session.commit()
    session.add(HazardTagIncompatibility(tag_a_id=acid.id, tag_b_id=base.id))
    with pytest.raises(IntegrityError):
        await session.commit()
```

- [ ] **Step 7: Run all tests**

Run: `uv run pytest tests/test_models/test_hazard.py -v`

Expected: All 6 tests PASS.

- [ ] **Step 8: Run full test suite**

Run: `uv run pytest -v`

Expected: All tests PASS (no regressions).

- [ ] **Step 9: Commit test changes**

```bash
git add tests/test_models/test_hazard.py
git commit -m "test: update hazard tests for group-scoped tags"
```
