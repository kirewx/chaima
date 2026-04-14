# Frontend Redesign — Plan 1: Backend Schema & Endpoints

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend fields, endpoints, and permission rules that the new frontend depends on: secret chemicals, archive semantics, storage kind hierarchy, SDS upload, dark mode preference, container identifier uniqueness per group.

**Architecture:** Extend existing SQLModel tables with new columns. Regenerate the single initial Alembic migration (no production data — the repo already follows a "regenerate, don't stack" pattern, see commit 674fe25). Update schemas and service functions. Enforce the 4-level storage kind hierarchy and per-group container identifier uniqueness in the service layer, not in the database — SQLite's constraint support is limited and application-layer checks are easier to test.

**Tech Stack:** FastAPI · SQLModel · SQLAlchemy async · Alembic · fastapi-users · Pydantic v2 · pytest · uv. Parent spec: `docs/superpowers/specs/2026-04-14-frontend-redesign-design.md`.

**Dependency notes:** This plan has no deps. Plans 2–4 (frontend) consume the endpoints this plan adds. Each task in this plan ends with a green test run and a commit. After the last task, the backend works end-to-end with the existing frontend; the new frontend ships in later plans.

---

## File map

**Models (modify):**
- `src/chaima/models/chemical.py` — add `is_secret`, `is_archived`, `archived_at`, `structure_source`, `sds_path`
- `src/chaima/models/container.py` — add `purity`
- `src/chaima/models/storage.py` — add `kind` enum
- `src/chaima/models/user.py` — add `dark_mode`

**Schemas (modify):**
- `src/chaima/schemas/chemical.py` — propagate new fields to `ChemicalCreate`, `ChemicalRead`, `ChemicalUpdate`, `ChemicalDetail`
- `src/chaima/schemas/container.py` — add `purity` to create/read/update
- `src/chaima/schemas/storage.py` — add `kind` to create/read
- `src/chaima/schemas/user.py` — add `dark_mode` to update/read

**Services (modify):**
- `src/chaima/services/chemicals.py` — secret filter, archive, permission helpers
- `src/chaima/services/containers.py` — group-unique identifier check
- `src/chaima/services/storage.py` — kind hierarchy validation

**Routers (modify):**
- `src/chaima/routers/chemicals.py` — archive/unarchive endpoints, secret toggle, SDS upload, filter param `include_archived`
- `src/chaima/routers/storage_locations.py` — accept/return `kind`
- `src/chaima/routers/users.py` — allow `dark_mode` in update

**New files:**
- `src/chaima/services/files.py` — one tiny helper for saving uploaded files (SDS, structure images) under `uploads/<group_id>/<uuid>.<ext>`

**Migration:**
- `alembic/versions/c100a96867a6_initial_schema.py` — regenerate after all model changes are in place

**Tests (new/modified):**
- `tests/test_models/test_chemical.py` — new fields
- `tests/test_models/test_storage.py` — kind hierarchy validation
- `tests/test_services/test_chemicals_secret.py` — new
- `tests/test_services/test_chemicals_archive.py` — new
- `tests/test_services/test_containers_identifier.py` — new
- `tests/test_services/test_storage_kind.py` — new
- `tests/test_api/test_chemicals.py` — archive/secret endpoints
- `tests/test_api/test_storage_locations.py` — kind in request/response
- `tests/test_api/test_users.py` — dark_mode update
- `tests/test_api/test_sds_upload.py` — new

---

## Task 1: Add `is_archived` + `archived_at` to Chemical model

**Files:**
- Modify: `src/chaima/models/chemical.py`
- Test: `tests/test_models/test_chemical.py` (create if missing)

- [ ] **Step 1: Write the failing test**

Create or append to `tests/test_models/test_chemical.py`:

```python
import datetime
import uuid as uuid_pkg

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical


@pytest.mark.asyncio
async def test_chemical_defaults_to_not_archived(session: AsyncSession, seeded_group, seeded_user):
    c = Chemical(
        name="Acetone",
        group_id=seeded_group.id,
        created_by=seeded_user.id,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.is_archived is False
    assert c.archived_at is None


@pytest.mark.asyncio
async def test_chemical_can_be_archived(session: AsyncSession, seeded_group, seeded_user):
    c = Chemical(
        name="Methanol",
        group_id=seeded_group.id,
        created_by=seeded_user.id,
        is_archived=True,
        archived_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.is_archived is True
    assert c.archived_at is not None
```

If `seeded_group` / `seeded_user` fixtures don't exist, reuse whatever fixture `tests/conftest.py` already provides — check it first and adjust names.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models/test_chemical.py::test_chemical_defaults_to_not_archived -v`
Expected: FAIL with `AttributeError: 'Chemical' object has no attribute 'is_archived'`.

- [ ] **Step 3: Add the fields to the model**

Edit `src/chaima/models/chemical.py`, inside `class Chemical`, after the `updated_at` field:

```python
    is_archived: bool = Field(default=False, index=True)
    archived_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models/test_chemical.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/chemical.py tests/test_models/test_chemical.py
git commit -m "feat(models): add is_archived and archived_at to Chemical"
```

---

## Task 2: Add `is_secret` to Chemical model

**Files:**
- Modify: `src/chaima/models/chemical.py`
- Test: `tests/test_models/test_chemical.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models/test_chemical.py`:

```python
@pytest.mark.asyncio
async def test_chemical_defaults_to_not_secret(session: AsyncSession, seeded_group, seeded_user):
    c = Chemical(name="Ethanol", group_id=seeded_group.id, created_by=seeded_user.id)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.is_secret is False


@pytest.mark.asyncio
async def test_chemical_can_be_marked_secret(session: AsyncSession, seeded_group, seeded_user):
    c = Chemical(
        name="AZ Int 3a", group_id=seeded_group.id, created_by=seeded_user.id, is_secret=True
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.is_secret is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models/test_chemical.py::test_chemical_defaults_to_not_secret -v`
Expected: FAIL with AttributeError on `is_secret`.

- [ ] **Step 3: Add the field**

In `src/chaima/models/chemical.py`, after `is_archived`:

```python
    is_secret: bool = Field(default=False, index=True)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_models/test_chemical.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/chemical.py tests/test_models/test_chemical.py
git commit -m "feat(models): add is_secret flag to Chemical"
```

---

## Task 3: Add `structure_source` enum and `sds_path` to Chemical

**Files:**
- Modify: `src/chaima/models/chemical.py`
- Test: `tests/test_models/test_chemical.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
from chaima.models.chemical import Chemical, StructureSource


@pytest.mark.asyncio
async def test_chemical_structure_source_defaults_to_none(
    session: AsyncSession, seeded_group, seeded_user
):
    c = Chemical(name="Toluene", group_id=seeded_group.id, created_by=seeded_user.id)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.structure_source == StructureSource.NONE
    assert c.sds_path is None


@pytest.mark.asyncio
async def test_chemical_structure_source_set_to_pubchem(
    session: AsyncSession, seeded_group, seeded_user
):
    c = Chemical(
        name="Benzene",
        group_id=seeded_group.id,
        created_by=seeded_user.id,
        structure_source=StructureSource.PUBCHEM,
        sds_path="uploads/g1/benz-sds.pdf",
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.structure_source == StructureSource.PUBCHEM
    assert c.sds_path == "uploads/g1/benz-sds.pdf"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_models/test_chemical.py::test_chemical_structure_source_defaults_to_none -v`
Expected: FAIL on `StructureSource` import.

- [ ] **Step 3: Add enum + fields**

Top of `src/chaima/models/chemical.py`, below existing imports, add:

```python
from enum import Enum


class StructureSource(str, Enum):
    NONE = "none"
    PUBCHEM = "pubchem"
    UPLOADED = "uploaded"
```

Inside `class Chemical`, after `is_secret`:

```python
    structure_source: StructureSource = Field(default=StructureSource.NONE)
    sds_path: str | None = Field(default=None)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_models/test_chemical.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/chemical.py tests/test_models/test_chemical.py
git commit -m "feat(models): add structure_source enum and sds_path to Chemical"
```

---

## Task 4: Add `purity` to Container model

**Files:**
- Modify: `src/chaima/models/container.py`
- Test: `tests/test_models/test_container.py` (create if missing)

- [ ] **Step 1: Write the failing test**

```python
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.container import Container


@pytest.mark.asyncio
async def test_container_purity_optional(session, seeded_chemical, seeded_location, seeded_user):
    c = Container(
        chemical_id=seeded_chemical.id,
        location_id=seeded_location.id,
        identifier="AB01",
        amount=1.0,
        unit="L",
        created_by=seeded_user.id,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.purity is None


@pytest.mark.asyncio
async def test_container_purity_stores_string(
    session, seeded_chemical, seeded_location, seeded_user
):
    c = Container(
        chemical_id=seeded_chemical.id,
        location_id=seeded_location.id,
        identifier="AB02",
        amount=0.5,
        unit="L",
        purity="99.8%",
        created_by=seeded_user.id,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.purity == "99.8%"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_models/test_container.py -v`
Expected: FAIL on `purity` attribute.

- [ ] **Step 3: Add the field**

In `src/chaima/models/container.py`, after `unit: str`:

```python
    purity: str | None = Field(default=None)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_models/test_container.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/container.py tests/test_models/test_container.py
git commit -m "feat(models): add purity to Container"
```

---

## Task 5: Add `dark_mode` to User model

**Files:**
- Modify: `src/chaima/models/user.py`
- Test: `tests/test_models/test_user.py` (create if missing)

- [ ] **Step 1: Write the failing test**

```python
import pytest


@pytest.mark.asyncio
async def test_user_dark_mode_defaults_to_false(seeded_user):
    assert seeded_user.dark_mode is False


@pytest.mark.asyncio
async def test_user_dark_mode_can_be_enabled(session, seeded_user):
    seeded_user.dark_mode = True
    session.add(seeded_user)
    await session.commit()
    await session.refresh(seeded_user)
    assert seeded_user.dark_mode is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_models/test_user.py -v`
Expected: FAIL on `dark_mode`.

- [ ] **Step 3: Add the field**

In `src/chaima/models/user.py`, inside `class User`, after `main_group_id`:

```python
    dark_mode: Mapped[bool] = mapped_column(default=False, server_default="0", nullable=False)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_models/test_user.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/user.py tests/test_models/test_user.py
git commit -m "feat(models): add dark_mode preference to User"
```

---

## Task 6: Add `kind` enum to StorageLocation

**Files:**
- Modify: `src/chaima/models/storage.py`
- Test: `tests/test_models/test_storage.py` (create if missing)

- [ ] **Step 1: Write the failing test**

```python
import pytest

from chaima.models.storage import StorageKind, StorageLocation


@pytest.mark.asyncio
async def test_storage_location_requires_kind(session):
    loc = StorageLocation(name="Main Building", kind=StorageKind.BUILDING)
    session.add(loc)
    await session.commit()
    await session.refresh(loc)
    assert loc.kind == StorageKind.BUILDING


@pytest.mark.asyncio
async def test_storage_location_kind_values():
    assert {k.value for k in StorageKind} == {"building", "room", "cabinet", "shelf"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_models/test_storage.py -v`
Expected: FAIL on `StorageKind` import.

- [ ] **Step 3: Add the enum + field**

At the top of `src/chaima/models/storage.py`:

```python
from enum import Enum


class StorageKind(str, Enum):
    BUILDING = "building"
    ROOM = "room"
    CABINET = "cabinet"
    SHELF = "shelf"
```

Inside `class StorageLocation`, after `name`:

```python
    kind: StorageKind = Field(index=True)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_models/test_storage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/storage.py tests/test_models/test_storage.py
git commit -m "feat(models): add kind enum to StorageLocation"
```

---

## Task 7: Service helper — validate storage kind hierarchy

**Files:**
- Modify: `src/chaima/services/storage.py` (create the file if absent; otherwise append)
- Test: `tests/test_services/test_storage_kind.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_storage_kind.py`:

```python
import pytest

from chaima.models.storage import StorageKind
from chaima.services.storage import validate_kind_hierarchy, InvalidHierarchy


def test_building_has_no_parent():
    # building is top-level, parent kind is None
    validate_kind_hierarchy(child=StorageKind.BUILDING, parent=None)


def test_building_cannot_have_parent():
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.BUILDING, parent=StorageKind.ROOM)


def test_room_requires_building_parent():
    validate_kind_hierarchy(child=StorageKind.ROOM, parent=StorageKind.BUILDING)
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.ROOM, parent=None)
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.ROOM, parent=StorageKind.CABINET)


def test_cabinet_requires_room_parent():
    validate_kind_hierarchy(child=StorageKind.CABINET, parent=StorageKind.ROOM)
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.CABINET, parent=StorageKind.BUILDING)


def test_shelf_requires_cabinet_parent():
    validate_kind_hierarchy(child=StorageKind.SHELF, parent=StorageKind.CABINET)
    with pytest.raises(InvalidHierarchy):
        validate_kind_hierarchy(child=StorageKind.SHELF, parent=StorageKind.ROOM)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_services/test_storage_kind.py -v`
Expected: FAIL on import.

- [ ] **Step 3: Implement**

Add to `src/chaima/services/storage.py`:

```python
from chaima.models.storage import StorageKind


class InvalidHierarchy(ValueError):
    """Raised when a storage location's kind does not match its parent's kind."""


# allowed_parent[child] = the exact parent kind required (or None for building)
_ALLOWED_PARENT: dict[StorageKind, StorageKind | None] = {
    StorageKind.BUILDING: None,
    StorageKind.ROOM: StorageKind.BUILDING,
    StorageKind.CABINET: StorageKind.ROOM,
    StorageKind.SHELF: StorageKind.CABINET,
}


def validate_kind_hierarchy(child: StorageKind, parent: StorageKind | None) -> None:
    expected = _ALLOWED_PARENT[child]
    if expected != parent:
        raise InvalidHierarchy(
            f"{child.value} must have parent of kind "
            f"{expected.value if expected else 'None'}, got "
            f"{parent.value if parent else 'None'}"
        )
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_services/test_storage_kind.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/storage.py tests/test_services/test_storage_kind.py
git commit -m "feat(services): validate storage kind hierarchy"
```

---

## Task 8: Service helper — group-unique container identifier

**Files:**
- Modify: `src/chaima/services/containers.py`
- Test: `tests/test_services/test_containers_identifier.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from chaima.services.containers import (
    check_identifier_unique_in_group,
    DuplicateIdentifier,
)


@pytest.mark.asyncio
async def test_identifier_is_unique_within_group(
    session, seeded_chemical, seeded_location, seeded_user
):
    # Create one container with identifier AB01
    from chaima.models.container import Container
    c1 = Container(
        chemical_id=seeded_chemical.id,
        location_id=seeded_location.id,
        identifier="AB01",
        amount=1.0,
        unit="L",
        created_by=seeded_user.id,
    )
    session.add(c1)
    await session.commit()

    # The same identifier must raise in the same group
    with pytest.raises(DuplicateIdentifier):
        await check_identifier_unique_in_group(
            session, group_id=seeded_chemical.group_id, identifier="AB01"
        )

    # A different identifier must pass
    await check_identifier_unique_in_group(
        session, group_id=seeded_chemical.group_id, identifier="AB99"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_services/test_containers_identifier.py -v`
Expected: FAIL on import.

- [ ] **Step 3: Implement**

Add to `src/chaima/services/containers.py`:

```python
import uuid as uuid_pkg

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.container import Container


class DuplicateIdentifier(ValueError):
    """Raised when a container identifier already exists in the same group."""


async def check_identifier_unique_in_group(
    session: AsyncSession,
    group_id: uuid_pkg.UUID,
    identifier: str,
    exclude_container_id: uuid_pkg.UUID | None = None,
) -> None:
    """Raise DuplicateIdentifier if another container in ``group_id`` already
    uses ``identifier``. Containers inherit their group through their chemical."""
    stmt = (
        select(Container.id)
        .join(Chemical, Chemical.id == Container.chemical_id)
        .where(Chemical.group_id == group_id)
        .where(Container.identifier == identifier)
        .where(Container.is_archived.is_(False))
    )
    if exclude_container_id is not None:
        stmt = stmt.where(Container.id != exclude_container_id)
    result = await session.exec(stmt)
    if result.first() is not None:
        raise DuplicateIdentifier(
            f"Container identifier '{identifier}' already in use in this group"
        )
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_services/test_containers_identifier.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/containers.py tests/test_services/test_containers_identifier.py
git commit -m "feat(services): enforce group-unique container identifier"
```

---

## Task 9: Service helper — filter secret chemicals

**Files:**
- Modify: `src/chaima/services/chemicals.py`
- Test: `tests/test_services/test_chemicals_secret.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from sqlmodel import select

from chaima.models.chemical import Chemical
from chaima.services.chemicals import apply_secret_filter


@pytest.mark.asyncio
async def test_non_creator_does_not_see_secret(
    session, seeded_group, seeded_user, seeded_other_user
):
    secret = Chemical(
        name="Secret X",
        group_id=seeded_group.id,
        created_by=seeded_user.id,
        is_secret=True,
    )
    public = Chemical(
        name="Public Y",
        group_id=seeded_group.id,
        created_by=seeded_user.id,
        is_secret=False,
    )
    session.add_all([secret, public])
    await session.commit()

    stmt = select(Chemical).where(Chemical.group_id == seeded_group.id)
    stmt = apply_secret_filter(stmt, viewer=seeded_other_user)
    result = await session.exec(stmt)
    names = sorted(r.name for r in result.all())
    assert names == ["Public Y"]


@pytest.mark.asyncio
async def test_creator_sees_own_secret(session, seeded_group, seeded_user):
    secret = Chemical(
        name="Secret X",
        group_id=seeded_group.id,
        created_by=seeded_user.id,
        is_secret=True,
    )
    session.add(secret)
    await session.commit()

    stmt = select(Chemical).where(Chemical.group_id == seeded_group.id)
    stmt = apply_secret_filter(stmt, viewer=seeded_user)
    result = await session.exec(stmt)
    assert [r.name for r in result.all()] == ["Secret X"]


@pytest.mark.asyncio
async def test_superuser_sees_all_secrets(
    session, seeded_group, seeded_user, seeded_superuser
):
    secret = Chemical(
        name="Secret X",
        group_id=seeded_group.id,
        created_by=seeded_user.id,
        is_secret=True,
    )
    session.add(secret)
    await session.commit()

    stmt = select(Chemical).where(Chemical.group_id == seeded_group.id)
    stmt = apply_secret_filter(stmt, viewer=seeded_superuser)
    result = await session.exec(stmt)
    assert [r.name for r in result.all()] == ["Secret X"]
```

If `seeded_other_user` / `seeded_superuser` fixtures are missing, add them to `tests/conftest.py`. `seeded_other_user` is a plain second user in the same group. `seeded_superuser` is a user with `is_superuser=True`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_services/test_chemicals_secret.py -v`
Expected: FAIL on import.

- [ ] **Step 3: Implement**

Add to `src/chaima/services/chemicals.py`:

```python
from sqlalchemy import or_
from sqlmodel.sql.expression import Select

from chaima.models.chemical import Chemical
from chaima.models.user import User


def apply_secret_filter(stmt: Select, viewer: User) -> Select:
    """Exclude secret chemicals the viewer is not allowed to see.

    A user sees a secret chemical only if they created it. Superusers see
    all secrets. Non-secret chemicals are always visible.
    """
    if viewer.is_superuser:
        return stmt
    return stmt.where(
        or_(Chemical.is_secret.is_(False), Chemical.created_by == viewer.id)
    )
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_services/test_chemicals_secret.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/chemicals.py tests/test_services/test_chemicals_secret.py
git commit -m "feat(services): filter secret chemicals by viewer"
```

---

## Task 10: Wire secret filter into `list_chemicals` service

**Files:**
- Modify: `src/chaima/services/chemicals.py:list_chemicals` (existing function)
- Modify: `src/chaima/routers/chemicals.py` — pass `viewer=user` to the service
- Test: `tests/test_api/test_chemicals.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api/test_chemicals.py`:

```python
@pytest.mark.asyncio
async def test_list_excludes_secret_from_non_creator(
    client, seeded_group, user_token, other_user_token, seeded_user
):
    # User creates a secret chemical
    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals",
        json={"name": "SecretMol", "is_secret": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 201

    # Other user in the same group lists chemicals — SecretMol must not appear
    r = await client.get(
        f"/api/v1/groups/{seeded_group.id}/chemicals",
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    names = [c["name"] for c in r.json()["items"]]
    assert "SecretMol" not in names
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_api/test_chemicals.py::test_list_excludes_secret_from_non_creator -v`
Expected: FAIL — SecretMol visible to other user (or missing `is_secret` in create schema — Task 11 will add that, so test may also fail on 422).

If the failure is on schema (422), proceed: Task 11 fixes it. Re-run this test at the end of Task 11.

- [ ] **Step 3: Wire the filter**

In `src/chaima/services/chemicals.py:list_chemicals`, accept a `viewer: User` parameter and call `apply_secret_filter(stmt, viewer)` on the SELECT statement before pagination. Also accept `include_archived: bool = False` and add `stmt = stmt.where(Chemical.is_archived.is_(False))` unless include_archived is true.

Exact diff — find this function signature and edit it:

```python
async def list_chemicals(
    session: AsyncSession,
    group_id: uuid_pkg.UUID,
    *,
    viewer: User,  # NEW
    search: str | None = None,
    hazard_tag_id: uuid_pkg.UUID | None = None,
    ghs_code_id: uuid_pkg.UUID | None = None,
    has_containers: bool | None = None,
    include_archived: bool = False,  # NEW
    sort: str = "name",
    order: str = "asc",
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Chemical], int]:
    stmt = select(Chemical).where(Chemical.group_id == group_id)
    if not include_archived:
        stmt = stmt.where(Chemical.is_archived.is_(False))
    stmt = apply_secret_filter(stmt, viewer)
    # ... rest of existing filters unchanged
```

Then in `src/chaima/routers/chemicals.py:list_chemicals`, pass `viewer=member.user` (or whatever `GroupMemberDep` exposes — check the file; the existing router already resolves the user, it's just a naming question).

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_api/test_chemicals.py::test_list_excludes_secret_from_non_creator -v`

If it fails because `ChemicalCreate` rejects `is_secret`, continue to Task 11 and re-run. Otherwise: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/chemicals.py src/chaima/routers/chemicals.py tests/test_api/test_chemicals.py
git commit -m "feat(api): filter secret and archived chemicals in list endpoint"
```

---

## Task 11: Propagate new fields into Chemical schemas

**Files:**
- Modify: `src/chaima/schemas/chemical.py`
- Test: rerun the test from Task 10

- [ ] **Step 1: Add fields to schemas**

In `src/chaima/schemas/chemical.py`:

- `ChemicalCreate`: add `is_secret: bool = False`, `is_archived: bool = False` (archive is almost always left to the archive endpoint, but accept it for completeness), `structure_source: StructureSource = StructureSource.NONE`, `sds_path: str | None = None`.
- `ChemicalRead`: add `is_secret: bool`, `is_archived: bool`, `archived_at: datetime | None`, `structure_source: StructureSource`, `sds_path: str | None`.
- `ChemicalUpdate`: add the same fields as `Optional` (i.e. `bool | None = None`) so partial updates work. Key exception: `is_archived` is managed via the archive endpoint and is NOT accepted in the update schema — leave it out of `ChemicalUpdate`.
- `ChemicalDetail`: inherits from `ChemicalRead`, so no change unless it redeclares fields.

Import `StructureSource` from `chaima.models.chemical`.

- [ ] **Step 2: Run the Task 10 test**

Run: `uv run pytest tests/test_api/test_chemicals.py::test_list_excludes_secret_from_non_creator -v`
Expected: PASS.

Also run the full chemicals test file to check for regressions:

Run: `uv run pytest tests/test_api/test_chemicals.py -v`
Expected: all PASS. If an existing test breaks because it didn't set `is_secret`, the defaults should make it backwards-compatible; if not, adjust the existing fixture.

- [ ] **Step 3: Commit**

```bash
git add src/chaima/schemas/chemical.py
git commit -m "feat(schemas): expose is_secret, is_archived, structure_source, sds_path"
```

---

## Task 12: Archive / unarchive endpoints for Chemical

**Files:**
- Modify: `src/chaima/routers/chemicals.py`
- Modify: `src/chaima/services/chemicals.py`
- Test: `tests/test_api/test_chemicals.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_archive_chemical_hides_it_from_default_list(
    client, seeded_group, admin_token
):
    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals",
        json={"name": "OldStock"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = r.json()["id"]

    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals/{cid}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    r = await client.get(
        f"/api/v1/groups/{seeded_group.id}/chemicals",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    names = [c["name"] for c in r.json()["items"]]
    assert "OldStock" not in names

    # include_archived=true brings it back
    r = await client.get(
        f"/api/v1/groups/{seeded_group.id}/chemicals?include_archived=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    names = [c["name"] for c in r.json()["items"]]
    assert "OldStock" in names


@pytest.mark.asyncio
async def test_unarchive_chemical(client, seeded_group, admin_token):
    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals",
        json={"name": "Rediscovered"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = r.json()["id"]

    await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals/{cid}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals/{cid}/unarchive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    r = await client.get(
        f"/api/v1/groups/{seeded_group.id}/chemicals",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    names = [c["name"] for c in r.json()["items"]]
    assert "Rediscovered" in names
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_api/test_chemicals.py::test_archive_chemical_hides_it_from_default_list -v`
Expected: FAIL 404 on archive endpoint.

- [ ] **Step 3: Implement service + router**

In `src/chaima/services/chemicals.py`:

```python
import datetime

async def archive_chemical(
    session: AsyncSession, chemical_id: uuid_pkg.UUID
) -> None:
    chem = await session.get(Chemical, chemical_id)
    if chem is None:
        raise ChemicalNotFound(str(chemical_id))
    chem.is_archived = True
    chem.archived_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(chem)
    await session.commit()


async def unarchive_chemical(
    session: AsyncSession, chemical_id: uuid_pkg.UUID
) -> None:
    chem = await session.get(Chemical, chemical_id)
    if chem is None:
        raise ChemicalNotFound(str(chemical_id))
    chem.is_archived = False
    chem.archived_at = None
    session.add(chem)
    await session.commit()
```

If `ChemicalNotFound` does not exist yet, add:

```python
class ChemicalNotFound(LookupError):
    """Raised when a chemical id does not exist."""
```

In `src/chaima/routers/chemicals.py`, add:

```python
@router.post("/{chemical_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive(
    group_id: UUID,
    chemical_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
) -> None:
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
    try:
        await chemical_service.unarchive_chemical(session, chemical_id)
    except chemical_service.ChemicalNotFound:
        raise HTTPException(status_code=404, detail="Chemical not found")
```

Also accept an `include_archived: bool = Query(False)` parameter in `list_chemicals` and forward it to the service (already prepared in Task 10).

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api/test_chemicals.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/chemicals.py src/chaima/routers/chemicals.py tests/test_api/test_chemicals.py
git commit -m "feat(api): archive and unarchive chemical endpoints"
```

---

## Task 13: SDS upload endpoint

**Files:**
- Create: `src/chaima/services/files.py`
- Modify: `src/chaima/routers/chemicals.py`
- Test: `tests/test_api/test_sds_upload.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_api/test_sds_upload.py`:

```python
import io

import pytest


@pytest.mark.asyncio
async def test_sds_upload_stores_pdf_and_sets_path(client, seeded_group, admin_token):
    # Create chemical
    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals",
        json={"name": "SDSTest"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = r.json()["id"]

    pdf_bytes = b"%PDF-1.4\n%EOF\n"
    files = {"file": ("msds.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals/{cid}/sds",
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["sds_path"].endswith(".pdf")


@pytest.mark.asyncio
async def test_sds_upload_rejects_non_pdf(client, seeded_group, admin_token):
    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals",
        json={"name": "BadSDS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = r.json()["id"]

    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = await client.post(
        f"/api/v1/groups/{seeded_group.id}/chemicals/{cid}/sds",
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 415
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_api/test_sds_upload.py -v`
Expected: FAIL 404.

- [ ] **Step 3: Implement file helper**

Create `src/chaima/services/files.py`:

```python
from __future__ import annotations

import os
import uuid as uuid_pkg
from pathlib import Path

UPLOADS_ROOT = Path(os.environ.get("CHAIMA_UPLOADS_DIR", "uploads"))


def save_upload(group_id: uuid_pkg.UUID, original_name: str, data: bytes) -> str:
    """Save ``data`` under ``uploads/<group_id>/<uuid><ext>`` and return the
    relative path string."""
    ext = Path(original_name).suffix
    new_name = f"{uuid_pkg.uuid4().hex}{ext}"
    group_dir = UPLOADS_ROOT / str(group_id)
    group_dir.mkdir(parents=True, exist_ok=True)
    (group_dir / new_name).write_bytes(data)
    return str(Path(str(group_id)) / new_name)
```

- [ ] **Step 4: Implement endpoint**

In `src/chaima/routers/chemicals.py`:

```python
from fastapi import UploadFile, File

from chaima.services import files as files_service


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
```

- [ ] **Step 5: Run test**

Run: `uv run pytest tests/test_api/test_sds_upload.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/services/files.py src/chaima/routers/chemicals.py tests/test_api/test_sds_upload.py
git commit -m "feat(api): SDS PDF upload endpoint"
```

---

## Task 14: Expose `kind` in storage_locations router + enforce hierarchy

**Files:**
- Modify: `src/chaima/schemas/storage.py`
- Modify: `src/chaima/routers/storage_locations.py`
- Modify: `src/chaima/services/storage.py`
- Test: `tests/test_api/test_storage_locations.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api/test_storage_locations.py`:

```python
@pytest.mark.asyncio
async def test_create_building_room_cabinet_shelf(client, seeded_group, admin_token):
    # building
    r = await client.post(
        "/api/v1/storage-locations",
        json={"name": "Main", "kind": "building"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    building_id = r.json()["id"]

    # room with building parent
    r = await client.post(
        "/api/v1/storage-locations",
        json={"name": "Lab 201", "kind": "room", "parent_id": building_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    room_id = r.json()["id"]

    # cabinet under room — ok
    r = await client.post(
        "/api/v1/storage-locations",
        json={"name": "A1", "kind": "cabinet", "parent_id": room_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201

    # cabinet under building — rejected
    r = await client.post(
        "/api/v1/storage-locations",
        json={"name": "X", "kind": "cabinet", "parent_id": building_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 400
    assert "hierarchy" in r.json()["detail"].lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_api/test_storage_locations.py::test_create_building_room_cabinet_shelf -v`
Expected: FAIL — either schema rejects `kind` or hierarchy unchecked.

- [ ] **Step 3: Update schema**

In `src/chaima/schemas/storage.py`, add `kind: StorageKind` to the Create and Read schemas. Import `StorageKind` from `chaima.models.storage`.

- [ ] **Step 4: Add service function**

Append to `src/chaima/services/storage.py`:

```python
import uuid as uuid_pkg

from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.storage import StorageKind, StorageLocation


async def create_location(
    session: AsyncSession,
    *,
    name: str,
    kind: StorageKind,
    parent_id: uuid_pkg.UUID | None,
    description: str | None = None,
) -> StorageLocation:
    parent_kind: StorageKind | None = None
    if parent_id is not None:
        parent = await session.get(StorageLocation, parent_id)
        if parent is None:
            raise InvalidHierarchy(f"Parent {parent_id} does not exist")
        parent_kind = parent.kind
    validate_kind_hierarchy(child=kind, parent=parent_kind)

    loc = StorageLocation(
        name=name, kind=kind, parent_id=parent_id, description=description
    )
    session.add(loc)
    await session.commit()
    await session.refresh(loc)
    return loc
```

- [ ] **Step 5: Update router**

In `src/chaima/routers/storage_locations.py`, make the create endpoint delegate to `storage_service.create_location`, and translate `InvalidHierarchy` into HTTP 400:

```python
from chaima.services import storage as storage_service
from chaima.services.storage import InvalidHierarchy


@router.post("", response_model=StorageLocationRead, status_code=201)
async def create_storage_location(
    body: StorageLocationCreate,
    session: SessionDep,
    member: GroupMemberDep,
) -> StorageLocationRead:
    try:
        loc = await storage_service.create_location(
            session,
            name=body.name,
            kind=body.kind,
            parent_id=body.parent_id,
            description=body.description,
        )
    except InvalidHierarchy as e:
        raise HTTPException(status_code=400, detail=f"Invalid hierarchy: {e}")
    return StorageLocationRead.model_validate(loc)
```

- [ ] **Step 6: Run test**

Run: `uv run pytest tests/test_api/test_storage_locations.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/chaima/schemas/storage.py src/chaima/services/storage.py src/chaima/routers/storage_locations.py tests/test_api/test_storage_locations.py
git commit -m "feat(api): validate storage hierarchy and expose kind field"
```

---

## Task 15: `dark_mode` in User update endpoint

**Files:**
- Modify: `src/chaima/schemas/user.py`
- Modify: `src/chaima/routers/users.py`
- Test: `tests/test_api/test_users.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api/test_users.py`:

```python
@pytest.mark.asyncio
async def test_user_can_toggle_dark_mode(client, user_token):
    r = await client.patch(
        "/api/v1/users/me",
        json={"dark_mode": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.status_code == 200
    assert r.json()["dark_mode"] is True

    r = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert r.json()["dark_mode"] is True
```

If `/users/me` doesn't exist, adapt the URL to whatever the existing users router uses. Check `src/chaima/routers/users.py` first.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_api/test_users.py::test_user_can_toggle_dark_mode -v`
Expected: FAIL on schema rejecting `dark_mode`.

- [ ] **Step 3: Add to schema**

In `src/chaima/schemas/user.py`, add `dark_mode: bool | None = None` to the update schema and `dark_mode: bool` to the read schema. The existing users router should already accept partial updates; if not, wire it through.

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_api/test_users.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/schemas/user.py src/chaima/routers/users.py tests/test_api/test_users.py
git commit -m "feat(api): allow users to toggle dark_mode"
```

---

## Task 16: Regenerate Alembic initial migration

**Files:**
- Modify: `alembic/versions/c100a96867a6_initial_schema.py`

- [ ] **Step 1: Delete the existing migration**

```bash
rm alembic/versions/c100a96867a6_initial_schema.py
```

- [ ] **Step 2: Drop and recreate the dev DB**

```bash
rm -f chaima.db
```

- [ ] **Step 3: Autogenerate fresh migration**

```bash
uv run alembic revision --autogenerate -m "initial schema"
```

The new file lands in `alembic/versions/` with a new hash. Open it and verify it includes:

- `is_archived`, `archived_at`, `is_secret`, `structure_source`, `sds_path` on `chemical`
- `purity` on `container`
- `dark_mode` on `user`
- `kind` on `storage_location`

If anything is missing, your model edit was wrong — go back and fix.

- [ ] **Step 4: Apply migration**

```bash
uv run alembic upgrade head
```

Expected: no errors.

- [ ] **Step 5: Run the full test suite**

```bash
uv run pytest
```

Expected: ALL tests pass. If existing tests broke because they relied on the old migration name, update them.

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/ chaima.db
git commit -m "chore(db): regenerate initial migration with new fields"
```

Note: `chaima.db` is a dev artefact; the commit is optional but matches the project's existing habit of tracking it (see `chaima.db` already in the repo root). If the file is in `.gitignore`, skip adding it.

---

## Task 17: Smoke-run the API

**Files:** none (manual verification)

- [ ] **Step 1: Start the server**

```bash
uv run uvicorn chaima.app:app --reload
```

- [ ] **Step 2: Check OpenAPI**

Open `http://localhost:8000/docs` in a browser. Verify these new items show up:

- `POST /api/v1/groups/{group_id}/chemicals/{chemical_id}/archive`
- `POST /api/v1/groups/{group_id}/chemicals/{chemical_id}/unarchive`
- `POST /api/v1/groups/{group_id}/chemicals/{chemical_id}/sds`
- `is_secret`, `is_archived`, `structure_source`, `sds_path` fields on `ChemicalCreate` / `ChemicalRead`
- `kind` on `StorageLocationCreate` / `StorageLocationRead`
- `dark_mode` on `UserRead` / `UserUpdate`

- [ ] **Step 3: Stop server**

Done. No commit needed.

---

## Deferred to later plans

These spec items are intentionally NOT in Plan 1 — they belong to the frontend plans or a separate permissions mini-plan:

- **Fine-grained edit permissions** (admin can edit any non-secret; creator edits own; SU edits all). The current router enforces group membership only. When the frontend in Plan 2 starts triggering edits from the "…" menu, we'll add a role check helper (`can_edit_chemical(viewer, chemical)`) in the service layer. Until then, group membership is the enforced boundary, which is no worse than today.
- **`Container.received_date` rename.** The existing field is `purchased_at: date`. The frontend will map this to "Received" in the UI — no DB change needed.
- **Structure image upload endpoint.** The existing `Chemical.image_path` field is already wired for uploads; Plan 2 will reuse it with `structure_source=UPLOADED`. No new endpoint required.
- **Storage unit edit/archive endpoints.** Create is covered in Task 14; edit and archive follow the same pattern and will be added in Plan 3 when the Storage page needs them.

## Plan 1 complete

After Task 17, the backend exposes everything Plans 2–4 need. The existing frontend still works (all new fields have safe defaults, and archive is opt-in via the new endpoints).

Next plan: `2026-04-14-frontend-redesign-plan-2-chemicals-page.md` — theme, layout shell, and Chemicals page that consumes these endpoints. Will be generated after this one lands (or on demand, if you want all four upfront).
