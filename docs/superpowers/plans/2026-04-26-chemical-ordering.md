# Chemical Ordering & Wishlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single-step Orders feature with PubChem-driven vendor discovery, manual price/size entry, lead-time intelligence from order history, and a lightweight Wishlist — all wired into ChAiMa's existing chemical catalog.

**Architecture:** Three new SQLModel tables (`project`, `chemical_order`, `wishlist_item`) plus a `Container.order_id` FK. Backend services follow ChAiMa's async pattern (`AsyncSession`, service flushes / router commits). API under `/api/v1/groups/{group_id}/{orders|wishlist|projects}`. PubChem vendor list fetched via PUG-View. Frontend adds an `/orders` route with MUI tabs (Open/Received/Cancelled/Wishlist), a drawer-based order form mirroring `ContainerForm.tsx`, and a PubChem vendor panel. No vendor scraping. Lead-time stats computed on `GET /suppliers` from `received_at - ordered_at` deltas.

**Tech Stack:** FastAPI + SQLModel + fastapi-users + pydantic v2 + Alembic + httpx (backend); React + TypeScript + Vite + MUI v9 + TanStack Query + axios + react-router (frontend); pytest-asyncio + sqlite-aiosqlite (tests).

---

## Codebase conventions (read first)

These deviate from generic Python defaults — failing to follow them will cause real bugs:

| convention | what it means here |
|---|---|
| **UUID primary keys** | Use `id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)`. Never `int`. |
| **Singular table names** | `__tablename__ = "project"` not `"projects"`. FK strings reference singular: `foreign_key="group.id"`. |
| **Async sessions** | All service functions are `async def`, take `session: AsyncSession`, end with `await session.flush()`. The router commits via `await session.commit()` after the service returns. |
| **Service flushes, router commits** | Don't call `session.commit()` inside services — tests rely on this separation. |
| **Group-scoped routes** | New resources live under `/api/v1/groups/{group_id}/<resource>`. `group_id` is taken from path. `GroupMemberDep` / `GroupAdminDep` validate against it. |
| **Server-default timestamps** | `created_at` uses `sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)`. Don't try `default_factory=datetime.now`. |
| **`order` is a SQL reserved word** | Use `__tablename__ = "chemical_order"` for the new Order model. The Python class can stay `Order`. |
| **AutoString in migrations** | Alembic uses `sqlmodel.sql.sqltypes.AutoString()` for strings, `sa.Uuid()` for UUID columns, `sa.DateTime(timezone=True)` for timestamps. Pattern visible in `alembic/versions/49c7178e33a9_initial_schema.py`. |
| **Models registered in `__init__.py`** | Alembic discovers models via `from chaima.models import *` in `alembic/env.py`. New models MUST be exported from `src/chaima/models/__init__.py` or migrations won't see them. |
| **Test fixtures** | Use the existing `client`, `superuser_client`, `other_client`, `membership`, `admin_membership`, `group`, `user`, `chemical`, `supplier`, `storage_location` fixtures from `tests/test_api/conftest.py` and `tests/test_services/conftest.py`. |
| **Frontend baseURL** | The axios client (`frontend/src/api/client.ts`) prepends `/api/v1`, so hook URLs start at `/groups/...`. |
| **Drawer pattern** | New form drawers register via `DrawerProvider` / `useDrawer` from `frontend/src/components/drawer/DrawerContext`. Mirror `ContainerForm.tsx`. |

**Spec reference:** All decisions trace back to `docs/superpowers/specs/2026-04-26-chemical-ordering-design.md`. Two minor type-name corrections: the spec says "int PK" — actual is UUID; the spec says `groups.id` — actual is `group.id` (singular). The spec stays as-written; this plan uses the codebase reality.

**Build commands:**
- Backend tests: `uv run pytest tests/test_services/<file>::<test> -v` or `uv run pytest tests/test_api/<file>::<test> -v`
- Backend lint/type-check: not enforced in pre-commit per recent commits — skip unless requested.
- Migration generate: `uv run alembic revision --autogenerate -m "add orders feature"`
- Migration apply: `uv run alembic upgrade head`
- Frontend type-check: `cd frontend && npm run build` (vite build does the type check)
- Frontend dev server: `cd frontend && npm run dev`

---

## Phase 1 — Models & migration

### Task 1: Add `Project` SQLModel

**Files:**
- Create: `src/chaima/models/project.py`
- Test: `tests/test_services/test_projects_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_projects_model.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_project_can_be_inserted(session, group):
    from chaima.models.project import Project

    p = Project(group_id=group.id, name="Catalysis")
    session.add(p)
    await session.flush()

    assert p.id is not None
    assert p.is_archived is False
    assert p.created_at is not None


@pytest.mark.asyncio
async def test_project_unique_within_group(session, group):
    from sqlalchemy.exc import IntegrityError
    from chaima.models.project import Project

    session.add(Project(group_id=group.id, name="General"))
    await session.flush()
    session.add(Project(group_id=group.id, name="General"))
    with pytest.raises(IntegrityError):
        await session.flush()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_services/test_projects_model.py -v`
Expected: `ModuleNotFoundError: No module named 'chaima.models.project'`.

- [ ] **Step 3: Implement the model**

Create `src/chaima/models/project.py`:

```python
import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel


class Project(SQLModel, table=True):
    __tablename__ = "project"
    __table_args__ = (UniqueConstraint("name", "group_id"),)

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    name: str = Field(index=True)
    is_archived: bool = Field(default=False, index=True)
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
```

(Relationships will be added in later tasks once `Order` exists.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_services/test_projects_model.py -v`
Expected: both tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/project.py tests/test_services/test_projects_model.py
git commit -m "feat(orders): add Project SQLModel"
```

---

### Task 2: Add `Order` SQLModel (`chemical_order` table)

**Files:**
- Create: `src/chaima/models/order.py`
- Test: `tests/test_services/test_order_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_order_model.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_order_can_be_inserted(session, group, chemical, supplier, user):
    from chaima.models.project import Project
    from chaima.models.order import Order, OrderStatus

    project = Project(group_id=group.id, name="Catalysis")
    session.add(project)
    await session.flush()

    order = Order(
        group_id=group.id,
        chemical_id=chemical.id,
        supplier_id=supplier.id,
        project_id=project.id,
        amount_per_package=100.0,
        unit="mL",
        package_count=3,
        ordered_by_user_id=user.id,
    )
    session.add(order)
    await session.flush()

    assert order.id is not None
    assert order.status == OrderStatus.ORDERED
    assert order.currency == "EUR"
    assert order.ordered_at is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_services/test_order_model.py -v`
Expected: `ModuleNotFoundError: No module named 'chaima.models.order'`.

- [ ] **Step 3: Implement the model**

Create `src/chaima/models/order.py`:

```python
import datetime
import uuid as uuid_pkg
from decimal import Decimal
from enum import Enum

from sqlalchemy import Column, DateTime, Numeric, func
from sqlmodel import Field, Relationship, SQLModel


class OrderStatus(str, Enum):
    ORDERED = "ordered"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class Order(SQLModel, table=True):
    __tablename__ = "chemical_order"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", index=True)
    supplier_id: uuid_pkg.UUID = Field(foreign_key="supplier.id", index=True)
    project_id: uuid_pkg.UUID = Field(foreign_key="project.id", index=True)

    amount_per_package: float
    unit: str
    package_count: int
    price_per_package: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True)
    )
    currency: str = Field(default="EUR", max_length=3)

    purity: str | None = Field(default=None)
    vendor_catalog_number: str | None = Field(default=None)
    vendor_product_url: str | None = Field(default=None)
    vendor_order_number: str | None = Field(default=None)
    expected_arrival: datetime.date | None = Field(default=None)
    comment: str | None = Field(default=None)

    status: OrderStatus = Field(default=OrderStatus.ORDERED, index=True)

    ordered_by_user_id: uuid_pkg.UUID = Field(foreign_key="user.id")
    ordered_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    received_by_user_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="user.id")
    received_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    cancelled_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    cancellation_reason: str | None = Field(default=None)

    chemical: "Chemical" = Relationship()
    supplier: "Supplier" = Relationship()
    project: "Project" = Relationship()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_services/test_order_model.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/order.py tests/test_services/test_order_model.py
git commit -m "feat(orders): add Order SQLModel"
```

---

### Task 3: Add `WishlistItem` SQLModel

**Files:**
- Create: `src/chaima/models/wishlist.py`
- Test: `tests/test_services/test_wishlist_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_wishlist_model.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_wishlist_with_chemical_id(session, group, chemical, user):
    from chaima.models.wishlist import WishlistItem, WishlistStatus

    item = WishlistItem(
        group_id=group.id,
        chemical_id=chemical.id,
        requested_by_user_id=user.id,
    )
    session.add(item)
    await session.flush()

    assert item.id is not None
    assert item.status == WishlistStatus.OPEN
    assert item.requested_at is not None


@pytest.mark.asyncio
async def test_wishlist_freeform(session, group, user):
    from chaima.models.wishlist import WishlistItem, WishlistStatus

    item = WishlistItem(
        group_id=group.id,
        freeform_name="Some new reagent",
        freeform_cas="123-45-6",
        requested_by_user_id=user.id,
        comment="for the catalysis project",
    )
    session.add(item)
    await session.flush()
    assert item.chemical_id is None
    assert item.freeform_name == "Some new reagent"
    assert item.status == WishlistStatus.OPEN
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_services/test_wishlist_model.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the model**

Create `src/chaima/models/wishlist.py`:

```python
import datetime
import uuid as uuid_pkg
from enum import Enum

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class WishlistStatus(str, Enum):
    OPEN = "open"
    CONVERTED = "converted"
    DISMISSED = "dismissed"


class WishlistItem(SQLModel, table=True):
    __tablename__ = "wishlist_item"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)

    chemical_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="chemical.id", index=True)
    freeform_name: str | None = Field(default=None)
    freeform_cas: str | None = Field(default=None)

    requested_by_user_id: uuid_pkg.UUID = Field(foreign_key="user.id")
    requested_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    comment: str | None = Field(default=None)

    status: WishlistStatus = Field(default=WishlistStatus.OPEN, index=True)
    converted_to_order_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="chemical_order.id"
    )
    dismissed_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    dismissed_by_user_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="user.id")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_services/test_wishlist_model.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/wishlist.py tests/test_services/test_wishlist_model.py
git commit -m "feat(orders): add WishlistItem SQLModel"
```

---

### Task 4: Add `order_id` FK to `Container`

**Files:**
- Modify: `src/chaima/models/container.py`
- Test: extend `tests/test_services/test_order_model.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_services/test_order_model.py`:

```python
@pytest.mark.asyncio
async def test_container_links_to_order(session, group, chemical, supplier, user, storage_location):
    from chaima.models.container import Container
    from chaima.models.order import Order
    from chaima.models.project import Project

    project = Project(group_id=group.id, name="X")
    session.add(project)
    await session.flush()

    order = Order(
        group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=project.id, amount_per_package=100.0, unit="mL",
        package_count=1, ordered_by_user_id=user.id,
    )
    session.add(order)
    await session.flush()

    c = Container(
        chemical_id=chemical.id, location_id=storage_location.id,
        identifier="lot-1", amount=100.0, unit="mL",
        order_id=order.id, created_by=user.id,
    )
    session.add(c)
    await session.flush()
    assert c.order_id == order.id
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_services/test_order_model.py::test_container_links_to_order -v`
Expected: `TypeError: 'order_id' is an invalid keyword argument`.

- [ ] **Step 3: Implement the model change**

In `src/chaima/models/container.py`, add this field after `supplier_id` (around line 16):

```python
    order_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="chemical_order.id", index=True
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_services/test_order_model.py -v`
Expected: all 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/container.py tests/test_services/test_order_model.py
git commit -m "feat(orders): link Container to Order via order_id FK"
```

---

### Task 5: Register new models in `models/__init__.py`

**Files:**
- Modify: `src/chaima/models/__init__.py`

- [ ] **Step 1: Edit the file**

Add imports and `__all__` entries. The full updated file:

```python
from chaima.models.chemical import Chemical, ChemicalSynonym
from chaima.models.container import Container
from chaima.models.ghs import ChemicalGHS, GHSCode
from chaima.models.group import Group, UserGroupLink
from chaima.models.hazard import (
    ChemicalHazardTag,
    HazardTag,
    HazardTagIncompatibility,
)
from chaima.models.import_log import ImportLog
from chaima.models.invite import Invite
from chaima.models.order import Order, OrderStatus
from chaima.models.project import Project
from chaima.models.storage import StorageLocation, StorageLocationGroup
from chaima.models.supplier import Supplier
from chaima.models.user import User
from chaima.models.wishlist import WishlistItem, WishlistStatus

__all__ = [
    "Chemical",
    "ChemicalGHS",
    "ChemicalHazardTag",
    "ChemicalSynonym",
    "Container",
    "GHSCode",
    "Group",
    "HazardTag",
    "HazardTagIncompatibility",
    "ImportLog",
    "Invite",
    "Order",
    "OrderStatus",
    "Project",
    "StorageLocation",
    "StorageLocationGroup",
    "Supplier",
    "User",
    "UserGroupLink",
    "WishlistItem",
    "WishlistStatus",
]
```

- [ ] **Step 2: Smoke-test the import**

Run: `uv run python -c "from chaima.models import Order, Project, WishlistItem; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/chaima/models/__init__.py
git commit -m "feat(orders): export Order, Project, WishlistItem from models package"
```

---

### Task 6: Generate Alembic migration with pre-seed data

**Files:**
- Create: `alembic/versions/<auto>_add_orders_feature.py`

- [ ] **Step 1: Generate the autogenerated migration**

Run: `uv run alembic revision --autogenerate -m "add orders feature"`
Expected: a new file under `alembic/versions/`. Note the filename.

- [ ] **Step 2: Verify the autogen body**

Open the generated file. The autogen should include:
- `op.create_table('project', ...)`
- `op.create_table('chemical_order', ...)`
- `op.create_table('wishlist_item', ...)`
- `op.add_column('container', sa.Column('order_id', sa.Uuid(), nullable=True))`
- `op.create_index(...)` for indexed FKs
- `op.create_foreign_key(...)` for `container.order_id → chemical_order.id`

If anything is missing (most often: a `sa.UniqueConstraint('name', 'group_id', name='uq_project_name_group')` on `project`), add it manually.

- [ ] **Step 3: Add the data migration**

At the end of the autogenerated `upgrade()` body (before the `# ### end Alembic commands ###` line — or after if there's no end marker), append the pre-seed loop:

```python
    # --- Data migration: pre-seed General project + 10 supplier names per existing group.
    # Idempotent: skips suppliers that already exist for that group (case-insensitive on name).
    bind = op.get_bind()
    PRESEED_SUPPLIERS = [
        "Sigma-Aldrich", "Merck", "Carl Roth", "abcr", "BLDPharm",
        "TCI", "Alfa Aesar", "Fisher Scientific", "Thermo Fisher", "VWR",
    ]
    groups = bind.execute(sa.text("SELECT id FROM \"group\"")).fetchall()
    for (group_id,) in groups:
        # General project
        existing = bind.execute(
            sa.text(
                "SELECT id FROM project WHERE group_id = :gid AND name = :name"
            ),
            {"gid": group_id, "name": "General"},
        ).first()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO project (id, group_id, name, is_archived) "
                    "VALUES (:id, :gid, :name, 0)"
                ),
                {"id": str(__import__('uuid').uuid4()), "gid": group_id, "name": "General"},
            )
        # Pre-seeded suppliers (skip if already present case-insensitively)
        for supplier_name in PRESEED_SUPPLIERS:
            already = bind.execute(
                sa.text(
                    "SELECT id FROM supplier "
                    "WHERE group_id = :gid AND LOWER(name) = LOWER(:name)"
                ),
                {"gid": group_id, "name": supplier_name},
            ).first()
            if already is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO supplier (id, group_id, name) "
                        "VALUES (:id, :gid, :name)"
                    ),
                    {
                        "id": str(__import__('uuid').uuid4()),
                        "gid": group_id,
                        "name": supplier_name,
                    },
                )
```

Note: SQLite uses `0`/`1` for booleans; Postgres accepts `false`/`true`. The string `"0"` works on both because `is_archived` has `Boolean()` column type and SQLAlchemy does the conversion via `sa.text` parameter binding when typed correctly. If SQLite chokes, change `0` to `False` and let the bind coerce.

- [ ] **Step 4: Apply the migration**

Run: `uv run alembic upgrade head`
Expected: migration runs without error. Check that `project`, `chemical_order`, `wishlist_item` tables exist:

```bash
uv run python -c "
import asyncio
from sqlmodel import select
from chaima.db import async_session_maker
from chaima.models.project import Project
async def go():
    async with async_session_maker() as s:
        rows = (await s.exec(select(Project))).all()
        print(f'projects: {len(rows)}')
asyncio.run(go())
"
```

Expected: prints a number ≥ 1 if any group existed before the migration.

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/*_add_orders_feature.py
git commit -m "feat(orders): alembic migration + pre-seed General project & 10 suppliers"
```

---

## Phase 2 — Pydantic schemas

### Task 7: Project schemas

**Files:**
- Create: `src/chaima/schemas/project.py`

- [ ] **Step 1: Write the file**

Create `src/chaima/schemas/project.py`:

```python
import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectUpdate(BaseModel):
    name: str | None = None
    is_archived: bool | None = None


class ProjectRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    group_id: UUID
    name: str
    is_archived: bool
    created_at: datetime.datetime
```

- [ ] **Step 2: Smoke-test**

Run: `uv run python -c "from chaima.schemas.project import ProjectCreate, ProjectRead; ProjectCreate(name='X')"`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git add src/chaima/schemas/project.py
git commit -m "feat(orders): Project pydantic schemas"
```

---

### Task 8: Order schemas

**Files:**
- Create: `src/chaima/schemas/order.py`

- [ ] **Step 1: Write the file**

Create `src/chaima/schemas/order.py`:

```python
import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from chaima.models.order import OrderStatus


class OrderCreate(BaseModel):
    chemical_id: UUID
    supplier_id: UUID
    project_id: UUID
    amount_per_package: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    package_count: int = Field(ge=1)
    price_per_package: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    purity: str | None = None
    vendor_catalog_number: str | None = None
    vendor_product_url: HttpUrl | None = None
    vendor_order_number: str | None = None
    expected_arrival: datetime.date | None = None
    comment: str | None = None
    wishlist_item_id: UUID | None = None  # Atomically marks wishlist as converted on create.


class OrderUpdate(BaseModel):
    """Edit allowed only while status=ordered. Server returns 409 otherwise."""

    supplier_id: UUID | None = None
    project_id: UUID | None = None
    amount_per_package: float | None = Field(default=None, gt=0)
    unit: str | None = None
    package_count: int | None = Field(default=None, ge=1)
    price_per_package: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    purity: str | None = None
    vendor_catalog_number: str | None = None
    vendor_product_url: HttpUrl | None = None
    vendor_order_number: str | None = None
    expected_arrival: datetime.date | None = None
    comment: str | None = None


class OrderCancel(BaseModel):
    cancellation_reason: str | None = None


class ContainerReceiveRow(BaseModel):
    identifier: str = Field(min_length=1)
    storage_location_id: UUID
    purity_override: str | None = None


class OrderReceive(BaseModel):
    containers: list[ContainerReceiveRow] = Field(min_length=1)


class OrderRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    group_id: UUID
    chemical_id: UUID
    chemical_name: str | None = None  # populated server-side from join
    supplier_id: UUID
    supplier_name: str | None = None
    project_id: UUID
    project_name: str | None = None

    amount_per_package: float
    unit: str
    package_count: int
    price_per_package: Decimal | None
    currency: str

    purity: str | None
    vendor_catalog_number: str | None
    vendor_product_url: str | None
    vendor_order_number: str | None
    expected_arrival: datetime.date | None
    comment: str | None

    status: OrderStatus

    ordered_by_user_id: UUID
    ordered_at: datetime.datetime
    received_by_user_id: UUID | None
    received_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None
    cancellation_reason: str | None
```

- [ ] **Step 2: Smoke-test**

Run: `uv run python -c "from chaima.schemas.order import OrderCreate, OrderReceive; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/chaima/schemas/order.py
git commit -m "feat(orders): Order pydantic schemas"
```

---

### Task 9: WishlistItem schemas

**Files:**
- Create: `src/chaima/schemas/wishlist.py`

- [ ] **Step 1: Write the file**

Create `src/chaima/schemas/wishlist.py`:

```python
import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

from chaima.models.wishlist import WishlistStatus


class WishlistCreate(BaseModel):
    chemical_id: UUID | None = None
    freeform_name: str | None = None
    freeform_cas: str | None = None
    comment: str | None = None

    @model_validator(mode="after")
    def _require_chemical_or_freeform(self) -> "WishlistCreate":
        if self.chemical_id is None and not self.freeform_name:
            raise ValueError("Either chemical_id or freeform_name is required")
        return self


class WishlistUpdate(BaseModel):
    chemical_id: UUID | None = None
    freeform_name: str | None = None
    freeform_cas: str | None = None
    comment: str | None = None


class WishlistRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    group_id: UUID
    chemical_id: UUID | None
    chemical_name: str | None = None  # joined when chemical_id is set
    freeform_name: str | None
    freeform_cas: str | None
    requested_by_user_id: UUID
    requested_at: datetime.datetime
    comment: str | None
    status: WishlistStatus
    converted_to_order_id: UUID | None
    dismissed_at: datetime.datetime | None
    dismissed_by_user_id: UUID | None


class WishlistPromoteResult(BaseModel):
    """Returned by POST /wishlist/{id}/promote. Frontend uses chemical_id to pre-fill the order form."""

    wishlist_item_id: UUID
    chemical_id: UUID
```

- [ ] **Step 2: Commit**

```bash
git add src/chaima/schemas/wishlist.py
git commit -m "feat(orders): Wishlist pydantic schemas"
```

---

### Task 10: Extend Supplier schema with `lead_time`

**Files:**
- Modify: `src/chaima/schemas/supplier.py`

- [ ] **Step 1: Edit the file**

In `src/chaima/schemas/supplier.py`, add a `LeadTimeStats` model and embed an optional field on `SupplierRead`:

```python
import datetime
from uuid import UUID

from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str


class SupplierUpdate(BaseModel):
    name: str | None = None


class LeadTimeStats(BaseModel):
    order_count: int
    median_days: int
    p25_days: int
    p75_days: int


class SupplierRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    group_id: UUID
    created_at: datetime.datetime
    container_count: int = 0
    lead_time: LeadTimeStats | None = None


class SupplierContainerRow(BaseModel):
    """Flat row describing a container attached to a supplier."""

    model_config = {"from_attributes": True}

    id: UUID
    identifier: str
    amount: float
    unit: str
    is_archived: bool
    chemical_id: UUID
    chemical_name: str
```

- [ ] **Step 2: Commit**

```bash
git add src/chaima/schemas/supplier.py
git commit -m "feat(orders): expose lead_time on SupplierRead"
```

---

### Task 11: Add PubChem vendor schemas

**Files:**
- Modify: `src/chaima/schemas/pubchem.py`

- [ ] **Step 1: Add the schemas**

Append to `src/chaima/schemas/pubchem.py`:

```python
class PubChemVendor(BaseModel):
    name: str
    url: str
    country: str | None = None


class PubChemVendorList(BaseModel):
    cid: str
    vendors: list[PubChemVendor]
```

- [ ] **Step 2: Commit**

```bash
git add src/chaima/schemas/pubchem.py
git commit -m "feat(orders): PubChem vendor schema types"
```

---

## Phase 3 — Services: projects, supplier seeding, PubChem vendors

### Task 12: `services/projects.py`

**Files:**
- Create: `src/chaima/services/projects.py`
- Test: `tests/test_services/test_projects.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_projects.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_project(session, group):
    from chaima.services import projects as svc

    p = await svc.create_project(session, group_id=group.id, name="Catalysis")
    assert p.name == "Catalysis"
    assert p.is_archived is False


@pytest.mark.asyncio
async def test_create_project_dedupes_case_insensitively(session, group):
    from chaima.services import projects as svc

    p1 = await svc.create_project(session, group_id=group.id, name="Catalysis")
    p2 = await svc.create_project(session, group_id=group.id, name="catalysis")
    assert p1.id == p2.id


@pytest.mark.asyncio
async def test_archive_and_list_excludes_archived(session, group):
    from chaima.services import projects as svc

    p = await svc.create_project(session, group_id=group.id, name="X")
    await svc.archive_project(session, p)

    active = await svc.list_projects(session, group_id=group.id, include_archived=False)
    assert active == []
    all_ = await svc.list_projects(session, group_id=group.id, include_archived=True)
    assert len(all_) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_projects.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the service**

Create `src/chaima/services/projects.py`:

```python
"""Service layer for Project entities (group-scoped)."""
from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.project import Project


async def create_project(
    session: AsyncSession, *, group_id: UUID, name: str
) -> Project:
    """Create a project, or return existing case-insensitive match."""
    trimmed = name.strip()
    existing = (
        await session.exec(
            select(Project).where(
                Project.group_id == group_id,
                func.lower(Project.name) == trimmed.lower(),
            )
        )
    ).first()
    if existing is not None:
        return existing
    project = Project(group_id=group_id, name=trimmed)
    session.add(project)
    await session.flush()
    return project


async def list_projects(
    session: AsyncSession, *, group_id: UUID, include_archived: bool = False
) -> list[Project]:
    stmt = select(Project).where(Project.group_id == group_id)
    if not include_archived:
        stmt = stmt.where(Project.is_archived == False)  # noqa: E712
    stmt = stmt.order_by(Project.name)
    return list((await session.exec(stmt)).all())


async def get_project(session: AsyncSession, project_id: UUID) -> Project | None:
    return await session.get(Project, project_id)


async def update_project(
    session: AsyncSession, project: Project, *, name: str | None = None
) -> Project:
    if name is not None:
        project.name = name.strip()
    session.add(project)
    await session.flush()
    return project


async def archive_project(session: AsyncSession, project: Project) -> Project:
    project.is_archived = True
    session.add(project)
    await session.flush()
    return project
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_projects.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/projects.py tests/test_services/test_projects.py
git commit -m "feat(orders): Project service (CRUD + archive)"
```

---

### Task 13: Extend `services/groups.create_group` to pre-seed General + 10 suppliers

**Files:**
- Modify: `src/chaima/services/groups.py`
- Test: extend `tests/test_services/test_groups.py` (or create one if it doesn't exist for `create_group`)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_services/test_groups.py` (create if missing):

```python
import pytest


@pytest.mark.asyncio
async def test_create_group_pre_seeds_general_project(session, user):
    from chaima.services import groups as svc
    from chaima.models.project import Project
    from sqlmodel import select

    g = await svc.create_group(session, name="New Lab", creator_id=user.id)
    rows = (await session.exec(select(Project).where(Project.group_id == g.id))).all()
    names = sorted(p.name for p in rows)
    assert names == ["General"]


@pytest.mark.asyncio
async def test_create_group_pre_seeds_ten_suppliers(session, user):
    from chaima.services import groups as svc
    from chaima.models.supplier import Supplier
    from sqlmodel import select

    g = await svc.create_group(session, name="New Lab", creator_id=user.id)
    rows = (await session.exec(select(Supplier).where(Supplier.group_id == g.id))).all()
    assert len(rows) == 10
    assert {s.name for s in rows} == {
        "Sigma-Aldrich", "Merck", "Carl Roth", "abcr", "BLDPharm",
        "TCI", "Alfa Aesar", "Fisher Scientific", "Thermo Fisher", "VWR",
    }
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_groups.py::test_create_group_pre_seeds_general_project -v`
Expected: `assert names == [] == ["General"]` fails.

- [ ] **Step 3: Implement**

In `src/chaima/services/groups.py`, add a constant near the top (after imports):

```python
PRESEED_SUPPLIERS = (
    "Sigma-Aldrich", "Merck", "Carl Roth", "abcr", "BLDPharm",
    "TCI", "Alfa Aesar", "Fisher Scientific", "Thermo Fisher", "VWR",
)
```

Then modify `create_group` to seed at the end (before `return group`):

```python
    # Pre-seed standard data so the group is usable for ordering immediately.
    from chaima.models.project import Project
    from chaima.models.supplier import Supplier

    session.add(Project(group_id=group.id, name="General"))
    for supplier_name in PRESEED_SUPPLIERS:
        session.add(Supplier(group_id=group.id, name=supplier_name))
    await session.flush()
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_groups.py -v`
Expected: pass (existing tests + new ones).

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/groups.py tests/test_services/test_groups.py
git commit -m "feat(orders): pre-seed General project + 10 suppliers on group creation"
```

---

### Task 14: PubChem `lookup_vendors`

**Files:**
- Modify: `src/chaima/services/pubchem.py`
- Test: extend `tests/test_services/test_pubchem.py` (or create) with a fixture-based test
- Create fixture: `tests/fixtures/pubchem/vendors_acetone.json` (sample PUG-View body)

- [ ] **Step 1: Capture a real PUG-View vendors fixture**

Run once to capture a real response (don't ship private data — just save the vendors list):

```bash
uv run python -c "
import asyncio, json, httpx
async def go():
    url = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/180/JSON?heading=Chemical+Vendors'
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url)
        r.raise_for_status()
        with open('tests/fixtures/pubchem/vendors_acetone.json', 'w', encoding='utf-8') as f:
            json.dump(r.json(), f, indent=2)
asyncio.run(go())
"
```

If the network call fails (offline / PubChem down), hand-craft a minimal stub matching the PUG-View shape:

```json
{
  "Record": {
    "Section": [{
      "TOCHeading": "Chemical Vendors",
      "Information": [
        {"Name": "Vendor", "Value": {"StringWithMarkup": [{"String": "Sigma-Aldrich", "Markup": [{"URL": "https://www.sigmaaldrich.com/...", "Type": "URL"}]}]}},
        {"Name": "Vendor", "Value": {"StringWithMarkup": [{"String": "abcr GmbH", "Markup": [{"URL": "https://www.abcr.com/...", "Type": "URL"}]}]}}
      ]
    }]
  }
}
```

- [ ] **Step 2: Write the failing parser test**

Create `tests/test_services/test_pubchem_vendors.py`:

```python
import json
from pathlib import Path

import pytest


def _load_fixture(name: str) -> dict:
    return json.loads(
        (Path(__file__).parent.parent / "fixtures" / "pubchem" / name).read_text()
    )


def test_parse_chemical_vendors_fixture():
    from chaima.services.pubchem import parse_chemical_vendors

    data = _load_fixture("vendors_acetone.json")
    vendors = parse_chemical_vendors(data)

    assert len(vendors) >= 1
    assert all(v.name and v.url for v in vendors)
    # No duplicate URLs
    urls = [v.url for v in vendors]
    assert len(urls) == len(set(urls))


def test_parse_chemical_vendors_empty_returns_empty_list():
    from chaima.services.pubchem import parse_chemical_vendors

    assert parse_chemical_vendors({}) == []
    assert parse_chemical_vendors({"Record": {"Section": []}}) == []
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_services/test_pubchem_vendors.py -v`
Expected: `ImportError: cannot import name 'parse_chemical_vendors'`.

- [ ] **Step 4: Implement parser + async fetch**

In `src/chaima/services/pubchem.py`, after `parse_ghs_classification` (around line 337), add:

```python
def parse_chemical_vendors(data: dict[str, Any]) -> list["PubChemVendor"]:
    """Extract vendor entries from a PubChem PUG-View Chemical Vendors body.

    Returns a deduplicated list of vendors keyed on URL. Empty list if the
    body lacks the section (or PubChem returned 404).
    """
    from chaima.schemas.pubchem import PubChemVendor

    sections = list(_iter_sections(data, "Chemical Vendors"))
    seen_urls: set[str] = set()
    vendors: list[PubChemVendor] = []

    for section in sections:
        for info in section.get("Information") or []:
            value = info.get("Value") or {}
            for entry in value.get("StringWithMarkup") or []:
                name = (entry.get("String") or "").strip()
                url: str | None = None
                for markup in entry.get("Markup") or []:
                    candidate = markup.get("URL")
                    if isinstance(candidate, str) and candidate.startswith("http"):
                        url = candidate
                        break
                if not name or not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                vendors.append(PubChemVendor(name=name, url=url))
    return vendors


def _iter_sections(node: Any, heading: str):
    """Yield every Section dict whose TOCHeading matches the given string."""
    if not isinstance(node, dict):
        return
    if node.get("TOCHeading") == heading:
        yield node
    for child in node.get("Section") or []:
        yield from _iter_sections(child, heading)
    record = node.get("Record")
    if isinstance(record, dict):
        yield from _iter_sections(record, heading)


async def lookup_vendors(cid: str) -> list["PubChemVendor"]:
    """Fetch PubChem 'Chemical Vendors' for a CID. Cached 24h.

    Returns an empty list on any upstream failure — never raises.
    """
    from chaima.schemas.pubchem import PubChemVendor  # noqa: F401

    cache_key = f"vendors:{cid}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    url = f"{_PUG_VIEW_URL}/data/compound/{cid}/JSON"
    timeout = httpx.Timeout(_TOTAL_TIMEOUT, connect=_PER_REQUEST_TIMEOUT)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params={"heading": "Chemical Vendors"})
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.warning("PubChem vendors fetch failed for CID %s: %s", cid, exc)
        return []
    if resp.status_code == 404:
        result: list = []
    elif resp.status_code >= 400:
        logger.warning("PubChem vendors returned %s for CID %s", resp.status_code, cid)
        return []
    else:
        result = parse_chemical_vendors(_safe_json(resp))
    _cache_set(cache_key, result)
    return result
```

- [ ] **Step 5: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_pubchem_vendors.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/services/pubchem.py tests/test_services/test_pubchem_vendors.py tests/fixtures/pubchem/vendors_acetone.json
git commit -m "feat(orders): PubChem lookup_vendors with parser + cache"
```

---

## Phase 4 — Services: Orders

### Task 15: `services/orders.create_order`

**Files:**
- Create: `src/chaima/services/orders.py`
- Test: `tests/test_services/test_orders.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_services/test_orders.py`:

```python
import datetime
from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_create_order(session, group, chemical, supplier, user):
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc

    project = await proj_svc.create_project(session, group_id=group.id, name="Cat")

    order = await svc.create_order(
        session,
        group_id=group.id,
        chemical_id=chemical.id,
        supplier_id=supplier.id,
        project_id=project.id,
        amount_per_package=100.0,
        unit="mL",
        package_count=3,
        price_per_package=Decimal("25.00"),
        currency="EUR",
        ordered_by_user_id=user.id,
    )
    assert order.id is not None
    assert order.status.value == "ordered"
    assert order.package_count == 3


@pytest.mark.asyncio
async def test_create_order_rejects_cross_group_supplier(session, group, chemical, user):
    """A supplier from a different group must not be accepted."""
    from chaima.models.group import Group
    from chaima.models.supplier import Supplier
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc

    other = Group(name="OtherLab")
    session.add(other)
    await session.flush()
    foreign_supplier = Supplier(name="Foreign", group_id=other.id)
    session.add(foreign_supplier)
    await session.flush()

    project = await proj_svc.create_project(session, group_id=group.id, name="Cat")

    with pytest.raises(svc.CrossGroupReferenceError):
        await svc.create_order(
            session,
            group_id=group.id,
            chemical_id=chemical.id,
            supplier_id=foreign_supplier.id,
            project_id=project.id,
            amount_per_package=100.0,
            unit="mL",
            package_count=1,
            ordered_by_user_id=user.id,
        )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_orders.py -v`
Expected: `ModuleNotFoundError: No module named 'chaima.services.orders'`.

- [ ] **Step 3: Implement**

Create `src/chaima/services/orders.py`:

```python
"""Service layer for chemical Orders.

Service functions flush; the calling router commits. Receipt is the only
operation that requires an explicit transaction (handled inline below).
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from statistics import median, quantiles
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.order import Order, OrderStatus
from chaima.models.project import Project
from chaima.models.storage import StorageLocation, StorageLocationGroup
from chaima.models.supplier import Supplier
from chaima.models.wishlist import WishlistItem, WishlistStatus


class CrossGroupReferenceError(Exception):
    """A referenced resource (chemical/supplier/project) belongs to a different group."""


class OrderStateError(Exception):
    """Operation is not allowed for the order's current status."""


class ContainerCountMismatchError(Exception):
    """Number of received containers does not match order.package_count."""


class StorageLocationInvalidError(Exception):
    """A storage_location_id in the receive payload is not in the requesting group."""

    def __init__(self, index: int, location_id: UUID) -> None:
        self.index = index
        self.location_id = location_id
        super().__init__(f"Container row {index}: storage_location_id {location_id} invalid")


async def _verify_same_group(
    session: AsyncSession, group_id: UUID, chemical_id: UUID, supplier_id: UUID, project_id: UUID
) -> None:
    chemical = await session.get(Chemical, chemical_id)
    if chemical is None or chemical.group_id != group_id:
        raise CrossGroupReferenceError("chemical")
    supplier = await session.get(Supplier, supplier_id)
    if supplier is None or supplier.group_id != group_id:
        raise CrossGroupReferenceError("supplier")
    project = await session.get(Project, project_id)
    if project is None or project.group_id != group_id:
        raise CrossGroupReferenceError("project")


async def create_order(
    session: AsyncSession,
    *,
    group_id: UUID,
    chemical_id: UUID,
    supplier_id: UUID,
    project_id: UUID,
    amount_per_package: float,
    unit: str,
    package_count: int,
    ordered_by_user_id: UUID,
    price_per_package: Decimal | None = None,
    currency: str = "EUR",
    purity: str | None = None,
    vendor_catalog_number: str | None = None,
    vendor_product_url: str | None = None,
    vendor_order_number: str | None = None,
    expected_arrival: datetime.date | None = None,
    comment: str | None = None,
    wishlist_item_id: UUID | None = None,
) -> Order:
    await _verify_same_group(session, group_id, chemical_id, supplier_id, project_id)

    order = Order(
        group_id=group_id,
        chemical_id=chemical_id,
        supplier_id=supplier_id,
        project_id=project_id,
        amount_per_package=amount_per_package,
        unit=unit,
        package_count=package_count,
        price_per_package=price_per_package,
        currency=currency,
        purity=purity,
        vendor_catalog_number=vendor_catalog_number,
        vendor_product_url=vendor_product_url,
        vendor_order_number=vendor_order_number,
        expected_arrival=expected_arrival,
        comment=comment,
        ordered_by_user_id=ordered_by_user_id,
    )
    session.add(order)
    await session.flush()

    if wishlist_item_id is not None:
        wl = await session.get(WishlistItem, wishlist_item_id)
        if wl is not None and wl.group_id == group_id and wl.status == WishlistStatus.OPEN:
            wl.status = WishlistStatus.CONVERTED
            wl.converted_to_order_id = order.id
            session.add(wl)
            await session.flush()

    return order
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_orders.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/orders.py tests/test_services/test_orders.py
git commit -m "feat(orders): create_order service with cross-group guard + wishlist atomic conversion"
```

---

### Task 16: `services/orders.list_orders` with filters

**Files:**
- Modify: `src/chaima/services/orders.py`
- Modify: `tests/test_services/test_orders.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/test_services/test_orders.py`:

```python
@pytest.mark.asyncio
async def test_list_orders_filters_by_status(session, group, chemical, supplier, user):
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc

    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o1 = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
        ordered_by_user_id=user.id,
    )
    o2 = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=50, unit="g", package_count=2,
        ordered_by_user_id=user.id,
    )
    o2.status = svc.OrderStatus.CANCELLED
    session.add(o2)
    await session.flush()

    open_only = await svc.list_orders(session, group_id=group.id, status="ordered")
    assert {o.id for o in open_only} == {o1.id}

    cancelled = await svc.list_orders(session, group_id=group.id, status="cancelled")
    assert {o.id for o in cancelled} == {o2.id}

    all_ = await svc.list_orders(session, group_id=group.id)
    assert {o.id for o in all_} == {o1.id, o2.id}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_services/test_orders.py::test_list_orders_filters_by_status -v`
Expected: `AttributeError: module 'chaima.services.orders' has no attribute 'list_orders'`.

- [ ] **Step 3: Implement**

Append to `src/chaima/services/orders.py`:

```python
async def list_orders(
    session: AsyncSession,
    *,
    group_id: UUID,
    status: str | None = None,
    supplier_id: UUID | None = None,
    project_id: UUID | None = None,
    chemical_id: UUID | None = None,
) -> list[Order]:
    stmt = select(Order).where(Order.group_id == group_id)
    if status is not None:
        stmt = stmt.where(Order.status == OrderStatus(status))
    if supplier_id is not None:
        stmt = stmt.where(Order.supplier_id == supplier_id)
    if project_id is not None:
        stmt = stmt.where(Order.project_id == project_id)
    if chemical_id is not None:
        stmt = stmt.where(Order.chemical_id == chemical_id)
    stmt = stmt.order_by(Order.ordered_at.desc())
    return list((await session.exec(stmt)).all())


async def get_order(session: AsyncSession, order_id: UUID) -> Order | None:
    return await session.get(Order, order_id)
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_orders.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/orders.py tests/test_services/test_orders.py
git commit -m "feat(orders): list_orders + get_order service"
```

---

### Task 17: `services/orders.edit_order` (state-guarded)

**Files:**
- Modify: `src/chaima/services/orders.py`
- Modify: `tests/test_services/test_orders.py`

- [ ] **Step 1: Append the failing test**

```python
@pytest.mark.asyncio
async def test_edit_order_blocked_after_received(session, group, chemical, supplier, user):
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc

    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
        ordered_by_user_id=user.id,
    )
    o.status = svc.OrderStatus.RECEIVED
    session.add(o)
    await session.flush()

    with pytest.raises(svc.OrderStateError):
        await svc.edit_order(session, o, package_count=5)
```

- [ ] **Step 2: Run to verify failure**

Expected: `AttributeError: ... no attribute 'edit_order'`.

- [ ] **Step 3: Implement**

Append to `src/chaima/services/orders.py`:

```python
async def edit_order(
    session: AsyncSession,
    order: Order,
    *,
    supplier_id: UUID | None = None,
    project_id: UUID | None = None,
    amount_per_package: float | None = None,
    unit: str | None = None,
    package_count: int | None = None,
    price_per_package: Decimal | None = None,
    currency: str | None = None,
    purity: str | None = None,
    vendor_catalog_number: str | None = None,
    vendor_product_url: str | None = None,
    vendor_order_number: str | None = None,
    expected_arrival: datetime.date | None = None,
    comment: str | None = None,
) -> Order:
    if order.status != OrderStatus.ORDERED:
        raise OrderStateError(f"Order is {order.status.value}; edits are not allowed")

    if supplier_id is not None:
        sup = await session.get(Supplier, supplier_id)
        if sup is None or sup.group_id != order.group_id:
            raise CrossGroupReferenceError("supplier")
        order.supplier_id = supplier_id
    if project_id is not None:
        proj = await session.get(Project, project_id)
        if proj is None or proj.group_id != order.group_id:
            raise CrossGroupReferenceError("project")
        order.project_id = project_id

    for attr, value in {
        "amount_per_package": amount_per_package,
        "unit": unit,
        "package_count": package_count,
        "price_per_package": price_per_package,
        "currency": currency,
        "purity": purity,
        "vendor_catalog_number": vendor_catalog_number,
        "vendor_product_url": vendor_product_url,
        "vendor_order_number": vendor_order_number,
        "expected_arrival": expected_arrival,
        "comment": comment,
    }.items():
        if value is not None:
            setattr(order, attr, value)

    session.add(order)
    await session.flush()
    return order
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_orders.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/orders.py tests/test_services/test_orders.py
git commit -m "feat(orders): edit_order with state guard + cross-group validation"
```

---

### Task 18: `services/orders.cancel_order`

**Files:**
- Modify: `src/chaima/services/orders.py`
- Modify: `tests/test_services/test_orders.py`

- [ ] **Step 1: Append the failing test**

```python
@pytest.mark.asyncio
async def test_cancel_order(session, group, chemical, supplier, user):
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc

    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
        ordered_by_user_id=user.id,
    )

    cancelled = await svc.cancel_order(session, o, reason="vendor out of stock")
    assert cancelled.status == svc.OrderStatus.CANCELLED
    assert cancelled.cancelled_at is not None
    assert cancelled.cancellation_reason == "vendor out of stock"

    with pytest.raises(svc.OrderStateError):
        await svc.cancel_order(session, cancelled)
```

- [ ] **Step 2: Run to verify failure**

Expected: `AttributeError: ... no attribute 'cancel_order'`.

- [ ] **Step 3: Implement**

Append:

```python
async def cancel_order(
    session: AsyncSession, order: Order, *, reason: str | None = None
) -> Order:
    if order.status != OrderStatus.ORDERED:
        raise OrderStateError(f"Order is {order.status.value}; cannot cancel")
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.datetime.now(datetime.timezone.utc)
    order.cancellation_reason = reason
    session.add(order)
    await session.flush()
    return order
```

- [ ] **Step 4: Run to confirm pass**

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/orders.py tests/test_services/test_orders.py
git commit -m "feat(orders): cancel_order service"
```

---

### Task 19: `services/orders.receive_order` (transactional, spawns N containers)

**Files:**
- Modify: `src/chaima/services/orders.py`
- Modify: `tests/test_services/test_orders.py`

- [ ] **Step 1: Append the failing tests**

```python
@pytest.mark.asyncio
async def test_receive_spawns_n_containers(
    session, group, chemical, supplier, user, storage_location
):
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc
    from chaima.models.container import Container
    from sqlmodel import select

    # Make storage_location visible to this group
    from chaima.models.storage import StorageLocationGroup
    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))

    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=3,
        purity="99%", ordered_by_user_id=user.id,
    )
    await session.flush()

    rows = [
        svc.ContainerReceiveRow(identifier=f"lot-{i}", storage_location_id=storage_location.id)
        for i in range(3)
    ]
    containers = await svc.receive_order(session, o, rows=rows, received_by_user_id=user.id)
    assert len(containers) == 3
    assert all(c.amount == 100 and c.unit == "mL" and c.purity == "99%" for c in containers)
    assert all(c.order_id == o.id for c in containers)

    # Order is now received and locked from edits
    assert o.status == svc.OrderStatus.RECEIVED
    with pytest.raises(svc.OrderStateError):
        await svc.edit_order(session, o, package_count=5)


@pytest.mark.asyncio
async def test_receive_rejects_count_mismatch(
    session, group, chemical, supplier, user, storage_location
):
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc
    from chaima.models.storage import StorageLocationGroup

    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))
    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=3,
        ordered_by_user_id=user.id,
    )
    rows = [svc.ContainerReceiveRow(identifier="lot-0", storage_location_id=storage_location.id)]
    with pytest.raises(svc.ContainerCountMismatchError):
        await svc.receive_order(session, o, rows=rows, received_by_user_id=user.id)


@pytest.mark.asyncio
async def test_receive_rejects_invalid_storage_location(
    session, group, chemical, supplier, user
):
    """A storage_location_id outside the group must reject by index."""
    import uuid
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc

    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")
    o = await svc.create_order(
        session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
        project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
        ordered_by_user_id=user.id,
    )
    bogus = uuid.uuid4()
    rows = [svc.ContainerReceiveRow(identifier="lot-0", storage_location_id=bogus)]
    with pytest.raises(svc.StorageLocationInvalidError) as ei:
        await svc.receive_order(session, o, rows=rows, received_by_user_id=user.id)
    assert ei.value.index == 0
```

- [ ] **Step 2: Run to verify failure**

Expected: `AttributeError: ... 'ContainerReceiveRow'` and `'receive_order'`.

- [ ] **Step 3: Implement**

Append to `src/chaima/services/orders.py`:

```python
from dataclasses import dataclass


@dataclass
class ContainerReceiveRow:
    identifier: str
    storage_location_id: UUID
    purity_override: str | None = None


async def _validate_location_in_group(
    session: AsyncSession, group_id: UUID, location_id: UUID
) -> bool:
    """True if the location is linked to the group via StorageLocationGroup."""
    result = await session.exec(
        select(StorageLocationGroup).where(
            StorageLocationGroup.location_id == location_id,
            StorageLocationGroup.group_id == group_id,
        )
    )
    return result.first() is not None


async def receive_order(
    session: AsyncSession,
    order: Order,
    *,
    rows: list[ContainerReceiveRow],
    received_by_user_id: UUID,
) -> list[Container]:
    """Mark an order received and spawn N containers in one transaction.

    The caller's session is the unit of work — anything raised here aborts
    the whole receipt. The router commits on success.
    """
    if order.status != OrderStatus.ORDERED:
        raise OrderStateError(f"Order is {order.status.value}; cannot receive")
    if len(rows) != order.package_count:
        raise ContainerCountMismatchError(
            f"expected {order.package_count} containers, got {len(rows)}"
        )

    # Validate every storage_location belongs to the group BEFORE creating any container.
    for i, row in enumerate(rows):
        ok = await _validate_location_in_group(session, order.group_id, row.storage_location_id)
        if not ok:
            raise StorageLocationInvalidError(i, row.storage_location_id)

    # Reject duplicate identifiers within the receipt payload.
    seen: set[str] = set()
    for i, row in enumerate(rows):
        if row.identifier in seen:
            raise ValueError(f"Container row {i}: duplicate identifier '{row.identifier}'")
        seen.add(row.identifier)

    # Spawn containers.
    spawned: list[Container] = []
    today = datetime.date.today()
    for row in rows:
        c = Container(
            chemical_id=order.chemical_id,
            location_id=row.storage_location_id,
            supplier_id=order.supplier_id,
            identifier=row.identifier,
            amount=order.amount_per_package,
            unit=order.unit,
            purity=row.purity_override or order.purity,
            order_id=order.id,
            purchased_at=today,
            created_by=received_by_user_id,
        )
        session.add(c)
        spawned.append(c)
    await session.flush()

    # Mark the order received.
    order.status = OrderStatus.RECEIVED
    order.received_by_user_id = received_by_user_id
    order.received_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(order)
    await session.flush()

    return spawned
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_orders.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/orders.py tests/test_services/test_orders.py
git commit -m "feat(orders): receive_order spawns N containers transactionally"
```

---

### Task 20: `services/orders.lead_time_stats`

**Files:**
- Modify: `src/chaima/services/orders.py`
- Modify: `tests/test_services/test_orders.py`

- [ ] **Step 1: Append the failing test**

```python
@pytest.mark.asyncio
async def test_lead_time_stats_null_under_three_orders(session, group, chemical, supplier, user):
    from chaima.services import orders as svc
    stats = await svc.lead_time_stats(session, group_id=group.id, supplier_id=supplier.id)
    assert stats is None


@pytest.mark.asyncio
async def test_lead_time_stats_returns_quantiles(
    session, group, chemical, supplier, user, storage_location
):
    """3+ received orders → returns median/p25/p75."""
    import datetime
    from chaima.services import projects as proj_svc
    from chaima.services import orders as svc
    from chaima.models.order import OrderStatus
    from chaima.models.storage import StorageLocationGroup

    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))
    p = await proj_svc.create_project(session, group_id=group.id, name="Cat")

    deltas = [5, 10, 14, 20]
    for d in deltas:
        o = await svc.create_order(
            session, group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
            project_id=p.id, amount_per_package=100, unit="mL", package_count=1,
            ordered_by_user_id=user.id,
        )
        o.status = OrderStatus.RECEIVED
        o.received_at = o.ordered_at + datetime.timedelta(days=d)
        session.add(o)
    await session.flush()

    stats = await svc.lead_time_stats(session, group_id=group.id, supplier_id=supplier.id)
    assert stats is not None
    assert stats.order_count == 4
    assert stats.median_days == 12  # median of [5,10,14,20] = 12
    assert 5 <= stats.p25_days <= 12
    assert 12 <= stats.p75_days <= 20
```

- [ ] **Step 2: Run to verify failure**

Expected: `AttributeError`.

- [ ] **Step 3: Implement**

Append to `src/chaima/services/orders.py`:

```python
from chaima.schemas.supplier import LeadTimeStats


async def lead_time_stats(
    session: AsyncSession, *, group_id: UUID, supplier_id: UUID
) -> LeadTimeStats | None:
    """Median + IQR of received orders' (received_at - ordered_at) days."""
    rows = (
        await session.exec(
            select(Order).where(
                Order.group_id == group_id,
                Order.supplier_id == supplier_id,
                Order.status == OrderStatus.RECEIVED,
            )
        )
    ).all()
    deltas = [
        (o.received_at - o.ordered_at).days
        for o in rows
        if o.received_at is not None and o.ordered_at is not None
    ]
    if len(deltas) < 3:
        return None
    sorted_deltas = sorted(deltas)
    if len(sorted_deltas) < 4:
        # quantiles needs n>=2; for n=3 use simple split.
        p25 = sorted_deltas[0]
        p75 = sorted_deltas[-1]
    else:
        qs = quantiles(sorted_deltas, n=4)  # returns 3 values: q1, q2, q3
        p25 = int(round(qs[0]))
        p75 = int(round(qs[2]))
    return LeadTimeStats(
        order_count=len(deltas),
        median_days=int(round(median(deltas))),
        p25_days=p25,
        p75_days=p75,
    )
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_orders.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/orders.py tests/test_services/test_orders.py
git commit -m "feat(orders): lead_time_stats (median + IQR from order history)"
```

---

## Phase 5 — Services: Wishlist

### Task 21: `services/wishlist.py` — create + dismiss

**Files:**
- Create: `src/chaima/services/wishlist.py`
- Test: `tests/test_services/test_wishlist.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_services/test_wishlist.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_with_chemical_id(session, group, chemical, user):
    from chaima.services import wishlist as svc

    item = await svc.create_wishlist(
        session, group_id=group.id, chemical_id=chemical.id,
        requested_by_user_id=user.id, comment="please order soon",
    )
    assert item.chemical_id == chemical.id
    assert item.status.value == "open"


@pytest.mark.asyncio
async def test_create_freeform(session, group, user):
    from chaima.services import wishlist as svc

    item = await svc.create_wishlist(
        session, group_id=group.id,
        freeform_name="Some new reagent", freeform_cas="123-45-6",
        requested_by_user_id=user.id,
    )
    assert item.chemical_id is None
    assert item.freeform_name == "Some new reagent"


@pytest.mark.asyncio
async def test_create_freeform_requires_name(session, group, user):
    from chaima.services import wishlist as svc

    with pytest.raises(ValueError):
        await svc.create_wishlist(
            session, group_id=group.id, requested_by_user_id=user.id,
        )


@pytest.mark.asyncio
async def test_dismiss_records_actor_and_timestamp(session, group, chemical, user):
    from chaima.services import wishlist as svc
    from chaima.models.wishlist import WishlistStatus

    item = await svc.create_wishlist(
        session, group_id=group.id, chemical_id=chemical.id,
        requested_by_user_id=user.id,
    )
    await svc.dismiss_wishlist(session, item, dismissed_by_user_id=user.id)
    assert item.status == WishlistStatus.DISMISSED
    assert item.dismissed_at is not None
    assert item.dismissed_by_user_id == user.id
```

- [ ] **Step 2: Run to verify failure**

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Create `src/chaima/services/wishlist.py`:

```python
"""Service layer for WishlistItem entities."""
from __future__ import annotations

import datetime
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.models.chemical import Chemical
from chaima.models.wishlist import WishlistItem, WishlistStatus


class WishlistFreeformInvalid(ValueError):
    """Raised when neither chemical_id nor freeform_name is provided."""


class WishlistChemicalNotResolvable(Exception):
    """Raised when promoting a freeform item but PubChem can't find it."""


async def create_wishlist(
    session: AsyncSession,
    *,
    group_id: UUID,
    requested_by_user_id: UUID,
    chemical_id: UUID | None = None,
    freeform_name: str | None = None,
    freeform_cas: str | None = None,
    comment: str | None = None,
) -> WishlistItem:
    if chemical_id is None and not (freeform_name and freeform_name.strip()):
        raise WishlistFreeformInvalid(
            "Either chemical_id or freeform_name is required"
        )
    item = WishlistItem(
        group_id=group_id,
        chemical_id=chemical_id,
        freeform_name=freeform_name.strip() if freeform_name else None,
        freeform_cas=freeform_cas.strip() if freeform_cas else None,
        requested_by_user_id=requested_by_user_id,
        comment=comment,
    )
    session.add(item)
    await session.flush()
    return item


async def list_wishlist(
    session: AsyncSession, *, group_id: UUID, status: WishlistStatus = WishlistStatus.OPEN
) -> list[WishlistItem]:
    stmt = (
        select(WishlistItem)
        .where(WishlistItem.group_id == group_id, WishlistItem.status == status)
        .order_by(WishlistItem.requested_at.desc())
    )
    return list((await session.exec(stmt)).all())


async def get_wishlist(session: AsyncSession, wishlist_id: UUID) -> WishlistItem | None:
    return await session.get(WishlistItem, wishlist_id)


async def dismiss_wishlist(
    session: AsyncSession, item: WishlistItem, *, dismissed_by_user_id: UUID
) -> WishlistItem:
    item.status = WishlistStatus.DISMISSED
    item.dismissed_at = datetime.datetime.now(datetime.timezone.utc)
    item.dismissed_by_user_id = dismissed_by_user_id
    session.add(item)
    await session.flush()
    return item
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_wishlist.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/wishlist.py tests/test_services/test_wishlist.py
git commit -m "feat(orders): wishlist create + list + dismiss services"
```

---

### Task 22: `services/wishlist.promote` (PubChem fallthrough + chemical creation)

**Files:**
- Modify: `src/chaima/services/wishlist.py`
- Modify: `tests/test_services/test_wishlist.py`

The promote flow:
1. If wishlist already has `chemical_id` → return it immediately.
2. Otherwise, look up PubChem with `freeform_cas` (preferred) or `freeform_name`. If no hit → raise `WishlistChemicalNotResolvable`.
3. If PubChem returns a CID that already exists as a Chemical in the group → reuse that.
4. Else → create a new skeleton Chemical via the existing chemical service / model.
5. Update wishlist's `chemical_id` to the resolved value (status stays `open` until `POST /orders` with `wishlist_item_id` flips it to `converted`).

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.asyncio
async def test_promote_already_has_chemical_id(session, group, chemical, user):
    from chaima.services import wishlist as svc
    item = await svc.create_wishlist(
        session, group_id=group.id, chemical_id=chemical.id,
        requested_by_user_id=user.id,
    )
    resolved_id = await svc.promote_wishlist(session, item)
    assert resolved_id == chemical.id


@pytest.mark.asyncio
async def test_promote_freeform_creates_chemical_via_pubchem(
    session, group, user, monkeypatch
):
    from chaima.services import wishlist as svc
    from chaima.schemas.pubchem import PubChemLookupResult

    async def fake_lookup(query: str) -> PubChemLookupResult:
        return PubChemLookupResult(
            cid="180", name="Acetone", cas="67-64-1",
            molar_mass=58.08, smiles="CC(=O)C",
            synonyms=["acetone", "propan-2-one"], ghs_codes=[],
        )
    monkeypatch.setattr("chaima.services.pubchem.lookup", fake_lookup)

    item = await svc.create_wishlist(
        session, group_id=group.id,
        freeform_name="acetone", requested_by_user_id=user.id,
    )
    resolved_id = await svc.promote_wishlist(session, item)
    assert resolved_id is not None
    # Verify a Chemical row was created
    from chaima.models.chemical import Chemical
    from sqlmodel import select
    chems = (await session.exec(select(Chemical).where(Chemical.cid == "180"))).all()
    assert len(chems) == 1
    assert chems[0].name == "Acetone"


@pytest.mark.asyncio
async def test_promote_freeform_reuses_existing_chemical_by_cid(
    session, group, user, monkeypatch
):
    from chaima.services import wishlist as svc
    from chaima.schemas.pubchem import PubChemLookupResult
    from chaima.models.chemical import Chemical

    existing = Chemical(
        group_id=group.id, name="Acetone", cas="67-64-1", cid="180", created_by=user.id,
    )
    session.add(existing)
    await session.flush()

    async def fake_lookup(query: str) -> PubChemLookupResult:
        return PubChemLookupResult(
            cid="180", name="Acetone", cas="67-64-1",
            molar_mass=58.08, smiles="CC(=O)C",
            synonyms=[], ghs_codes=[],
        )
    monkeypatch.setattr("chaima.services.pubchem.lookup", fake_lookup)

    item = await svc.create_wishlist(
        session, group_id=group.id, freeform_cas="67-64-1",
        requested_by_user_id=user.id,
    )
    resolved_id = await svc.promote_wishlist(session, item)
    assert resolved_id == existing.id


@pytest.mark.asyncio
async def test_promote_freeform_no_pubchem_match(session, group, user, monkeypatch):
    from chaima.services import wishlist as svc
    from chaima.services.pubchem import PubChemNotFound

    async def fake_lookup(query: str):
        raise PubChemNotFound(query)
    monkeypatch.setattr("chaima.services.pubchem.lookup", fake_lookup)

    item = await svc.create_wishlist(
        session, group_id=group.id,
        freeform_name="madeupchem", requested_by_user_id=user.id,
    )
    with pytest.raises(svc.WishlistChemicalNotResolvable):
        await svc.promote_wishlist(session, item)
```

- [ ] **Step 2: Run to verify failure**

Expected: `AttributeError: ... 'promote_wishlist'`.

- [ ] **Step 3: Implement**

Append to `src/chaima/services/wishlist.py`:

```python
async def promote_wishlist(session: AsyncSession, item: WishlistItem) -> UUID:
    """Resolve the wishlist item to a Chemical id (creating one if needed).

    Returns the chemical_id; the wishlist's status remains `open` until the
    caller's subsequent POST /orders with wishlist_item_id flips it to
    `converted` atomically.
    """
    if item.chemical_id is not None:
        return item.chemical_id

    from chaima.services import pubchem as pubchem_svc
    from chaima.services.pubchem import PubChemNotFound, PubChemUpstreamError

    query = (item.freeform_cas or item.freeform_name or "").strip()
    if not query:
        raise WishlistChemicalNotResolvable("wishlist item has no resolvable text")

    try:
        result = await pubchem_svc.lookup(query)
    except PubChemNotFound:
        raise WishlistChemicalNotResolvable(query)
    except PubChemUpstreamError:
        raise WishlistChemicalNotResolvable(f"upstream error for {query}")

    # Reuse existing Chemical with the same CID in this group.
    existing = (
        await session.exec(
            select(Chemical).where(
                Chemical.group_id == item.group_id, Chemical.cid == result.cid
            )
        )
    ).first()
    if existing is not None:
        item.chemical_id = existing.id
        session.add(item)
        await session.flush()
        return existing.id

    # Create a skeleton Chemical.
    chemical = Chemical(
        group_id=item.group_id,
        name=result.name,
        cas=result.cas,
        cid=result.cid,
        smiles=result.smiles,
        molar_mass=result.molar_mass,
        created_by=item.requested_by_user_id,
    )
    session.add(chemical)
    await session.flush()
    item.chemical_id = chemical.id
    session.add(item)
    await session.flush()
    return chemical.id
```

- [ ] **Step 4: Run to confirm pass**

Run: `uv run pytest tests/test_services/test_wishlist.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/services/wishlist.py tests/test_services/test_wishlist.py
git commit -m "feat(orders): wishlist promote_wishlist resolves chemical via PubChem"
```

---

## Phase 6 — Routers

### Task 23: `routers/projects.py`

**Files:**
- Create: `src/chaima/routers/projects.py`
- Test: `tests/test_api/test_projects.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api/test_projects.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_and_list_project(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/projects", json={"name": "Catalysis"}
    )
    assert resp.status_code == 201
    proj_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/groups/{group.id}/projects")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(p["id"] == proj_id and p["name"] == "Catalysis" for p in items)


@pytest.mark.asyncio
async def test_create_project_dedupes_case_insensitively(client, group, membership):
    r1 = await client.post(f"/api/v1/groups/{group.id}/projects", json={"name": "X"})
    r2 = await client.post(f"/api/v1/groups/{group.id}/projects", json={"name": "x"})
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_archive_project_admin_only(client, group, membership):
    """Members can create but not archive."""
    r = await client.post(f"/api/v1/groups/{group.id}/projects", json={"name": "Y"})
    pid = r.json()["id"]
    resp = await client.post(f"/api/v1/groups/{group.id}/projects/{pid}/archive")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_archive_project_as_admin(client, group, admin_membership):
    r = await client.post(f"/api/v1/groups/{group.id}/projects", json={"name": "Y"})
    pid = r.json()["id"]
    resp = await client.post(f"/api/v1/groups/{group.id}/projects/{pid}/archive")
    assert resp.status_code == 200
    assert resp.json()["is_archived"] is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_api/test_projects.py -v`
Expected: 404 (no router registered).

- [ ] **Step 3: Implement**

Create `src/chaima/routers/projects.py`:

```python
"""Router for Project management endpoints."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import GroupAdminDep, GroupMemberDep, SessionDep
from chaima.schemas.pagination import PaginatedResponse
from chaima.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from chaima.services import projects as project_service

router = APIRouter(
    prefix="/api/v1/groups/{group_id}/projects", tags=["projects"]
)


@router.get("", response_model=PaginatedResponse[ProjectRead])
async def list_projects(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    include_archived: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> PaginatedResponse[ProjectRead]:
    items = await project_service.list_projects(
        session, group_id=group_id, include_archived=include_archived
    )
    page = items[offset : offset + limit]
    return PaginatedResponse(
        items=[ProjectRead.model_validate(p) for p in page],
        total=len(items),
        offset=offset,
        limit=limit,
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    group_id: UUID,
    body: ProjectCreate,
    session: SessionDep,
    member: GroupMemberDep,
) -> ProjectRead:
    project = await project_service.create_project(
        session, group_id=group_id, name=body.name
    )
    await session.commit()
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    group_id: UUID,
    project_id: UUID,
    body: ProjectUpdate,
    session: SessionDep,
    admin: GroupAdminDep,
) -> ProjectRead:
    project = await project_service.get_project(session, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if body.name is not None:
        await project_service.update_project(session, project, name=body.name)
    if body.is_archived is True:
        await project_service.archive_project(session, project)
    if body.is_archived is False:
        project.is_archived = False
        session.add(project)
    await session.commit()
    return ProjectRead.model_validate(project)


@router.post("/{project_id}/archive", response_model=ProjectRead)
async def archive_project(
    group_id: UUID,
    project_id: UUID,
    session: SessionDep,
    admin: GroupAdminDep,
) -> ProjectRead:
    project = await project_service.get_project(session, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await project_service.archive_project(session, project)
    await session.commit()
    return ProjectRead.model_validate(project)
```

- [ ] **Step 4: Register router in `app.py`**

In `src/chaima/app.py`, add the import and `include_router` line. Add near other router imports:

```python
from chaima.routers.projects import router as projects_router
```

After the existing `app.include_router(suppliers_router)` line, add:

```python
app.include_router(projects_router)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_api/test_projects.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/routers/projects.py src/chaima/app.py tests/test_api/test_projects.py
git commit -m "feat(orders): /api/v1/groups/{gid}/projects router"
```

---

### Task 24: `routers/orders.py`

**Files:**
- Create: `src/chaima/routers/orders.py`
- Test: `tests/test_api/test_orders.py`

- [ ] **Step 1: Write failing API tests** (the high-value end-to-end ones)

Create `tests/test_api/test_orders.py`:

```python
import pytest


async def _make_project(client, group_id, name="P"):
    return (await client.post(f"/api/v1/groups/{group_id}/projects", json={"name": name})).json()


@pytest.mark.asyncio
async def test_create_order_returns_201(client, group, chemical, supplier, membership):
    project = await _make_project(client, group.id)
    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id),
            "supplier_id": str(supplier.id),
            "project_id": project["id"],
            "amount_per_package": 100.0,
            "unit": "mL",
            "package_count": 3,
            "currency": "EUR",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ordered"
    assert body["package_count"] == 3
    assert body["chemical_name"] == chemical.name
    assert body["supplier_name"] == supplier.name


@pytest.mark.asyncio
async def test_receive_order_spawns_containers(
    client, session, group, chemical, supplier, membership, storage_location
):
    from chaima.models.storage import StorageLocationGroup
    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))
    await session.flush()

    project = await _make_project(client, group.id)
    create_resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id), "supplier_id": str(supplier.id),
            "project_id": project["id"], "amount_per_package": 50.0, "unit": "g",
            "package_count": 2,
        },
    )
    order_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order_id}/receive",
        json={
            "containers": [
                {"identifier": "lot-1", "storage_location_id": str(storage_location.id)},
                {"identifier": "lot-2", "storage_location_id": str(storage_location.id)},
            ]
        },
    )
    assert resp.status_code == 200
    spawned = resp.json()
    assert len(spawned) == 2

    # Order is now received (verify via GET)
    g = await client.get(f"/api/v1/groups/{group.id}/orders/{order_id}")
    assert g.json()["status"] == "received"


@pytest.mark.asyncio
async def test_receive_count_mismatch_returns_400(
    client, session, group, chemical, supplier, membership, storage_location
):
    from chaima.models.storage import StorageLocationGroup
    session.add(StorageLocationGroup(location_id=storage_location.id, group_id=group.id))
    await session.flush()

    project = await _make_project(client, group.id)
    create_resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id), "supplier_id": str(supplier.id),
            "project_id": project["id"], "amount_per_package": 50.0, "unit": "g",
            "package_count": 3,
        },
    )
    order_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order_id}/receive",
        json={"containers": [
            {"identifier": "lot-1", "storage_location_id": str(storage_location.id)},
        ]},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cancel_admin_only(client, group, chemical, supplier, membership):
    project = await _make_project(client, group.id)
    create_resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id), "supplier_id": str(supplier.id),
            "project_id": project["id"], "amount_per_package": 1.0, "unit": "g",
            "package_count": 1,
        },
    )
    order_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order_id}/cancel",
        json={"cancellation_reason": "no longer needed"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cancel_as_admin(client, group, chemical, supplier, admin_membership):
    project = await _make_project(client, group.id)
    create_resp = await client.post(
        f"/api/v1/groups/{group.id}/orders",
        json={
            "chemical_id": str(chemical.id), "supplier_id": str(supplier.id),
            "project_id": project["id"], "amount_per_package": 1.0, "unit": "g",
            "package_count": 1,
        },
    )
    order_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/groups/{group.id}/orders/{order_id}/cancel",
        json={"cancellation_reason": "no longer needed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_api/test_orders.py -v`
Expected: 404s.

- [ ] **Step 3: Implement the router**

Create `src/chaima/routers/orders.py`:

```python
"""Router for chemical Order endpoints."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import (
    CurrentUserDep,
    GroupAdminDep,
    GroupMemberDep,
    SessionDep,
)
from chaima.models.chemical import Chemical
from chaima.models.project import Project
from chaima.models.supplier import Supplier
from chaima.schemas.container import ContainerRead
from chaima.schemas.order import (
    ContainerReceiveRow as ContainerReceiveRowSchema,
    OrderCancel,
    OrderCreate,
    OrderRead,
    OrderReceive,
    OrderUpdate,
)
from chaima.schemas.pagination import PaginatedResponse
from chaima.services import orders as order_service

router = APIRouter(prefix="/api/v1/groups/{group_id}/orders", tags=["orders"])


async def _hydrate(session, order) -> OrderRead:
    """Populate chemical_name / supplier_name / project_name on the read schema."""
    chemical = await session.get(Chemical, order.chemical_id)
    supplier = await session.get(Supplier, order.supplier_id)
    project = await session.get(Project, order.project_id)
    base = OrderRead.model_validate(order)
    return base.model_copy(
        update={
            "chemical_name": chemical.name if chemical else None,
            "supplier_name": supplier.name if supplier else None,
            "project_name": project.name if project else None,
        }
    )


@router.get("", response_model=PaginatedResponse[OrderRead])
async def list_orders(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    status_: Literal["ordered", "received", "cancelled"] | None = Query(None, alias="status"),
    supplier_id: UUID | None = Query(None),
    project_id: UUID | None = Query(None),
    chemical_id: UUID | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> PaginatedResponse[OrderRead]:
    rows = await order_service.list_orders(
        session,
        group_id=group_id,
        status=status_,
        supplier_id=supplier_id,
        project_id=project_id,
        chemical_id=chemical_id,
    )
    page = rows[offset : offset + limit]
    items = [await _hydrate(session, o) for o in page]
    return PaginatedResponse(items=items, total=len(rows), offset=offset, limit=limit)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    group_id: UUID,
    body: OrderCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
    member: GroupMemberDep,
) -> OrderRead:
    try:
        order = await order_service.create_order(
            session,
            group_id=group_id,
            chemical_id=body.chemical_id,
            supplier_id=body.supplier_id,
            project_id=body.project_id,
            amount_per_package=body.amount_per_package,
            unit=body.unit,
            package_count=body.package_count,
            price_per_package=body.price_per_package,
            currency=body.currency,
            purity=body.purity,
            vendor_catalog_number=body.vendor_catalog_number,
            vendor_product_url=str(body.vendor_product_url) if body.vendor_product_url else None,
            vendor_order_number=body.vendor_order_number,
            expected_arrival=body.expected_arrival,
            comment=body.comment,
            ordered_by_user_id=current_user.id,
            wishlist_item_id=body.wishlist_item_id,
        )
    except order_service.CrossGroupReferenceError as exc:
        raise HTTPException(status_code=404, detail=f"{exc} not found in this group")
    await session.commit()
    return await _hydrate(session, order)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    group_id: UUID, order_id: UUID, session: SessionDep, member: GroupMemberDep,
) -> OrderRead:
    order = await order_service.get_order(session, order_id)
    if order is None or order.group_id != group_id:
        raise HTTPException(status_code=404, detail="Order not found")
    return await _hydrate(session, order)


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order(
    group_id: UUID, order_id: UUID, body: OrderUpdate,
    session: SessionDep, current_user: CurrentUserDep, member: GroupMemberDep,
) -> OrderRead:
    order = await order_service.get_order(session, order_id)
    if order is None or order.group_id != group_id:
        raise HTTPException(status_code=404, detail="Order not found")
    _, link = member
    if order.ordered_by_user_id != current_user.id and not link.is_admin:
        raise HTTPException(status_code=403, detail="Only the creator or an admin can edit")
    try:
        await order_service.edit_order(
            session, order, **body.model_dump(exclude_none=True),
        )
    except order_service.OrderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except order_service.CrossGroupReferenceError as exc:
        raise HTTPException(status_code=404, detail=f"{exc} not found in this group")
    await session.commit()
    return await _hydrate(session, order)


@router.post("/{order_id}/receive", response_model=list[ContainerRead])
async def receive_order(
    group_id: UUID, order_id: UUID, body: OrderReceive,
    session: SessionDep, current_user: CurrentUserDep, member: GroupMemberDep,
) -> list[ContainerRead]:
    order = await order_service.get_order(session, order_id)
    if order is None or order.group_id != group_id:
        raise HTTPException(status_code=404, detail="Order not found")
    rows = [
        order_service.ContainerReceiveRow(
            identifier=r.identifier,
            storage_location_id=r.storage_location_id,
            purity_override=r.purity_override,
        )
        for r in body.containers
    ]
    try:
        spawned = await order_service.receive_order(
            session, order, rows=rows, received_by_user_id=current_user.id,
        )
    except order_service.OrderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except order_service.ContainerCountMismatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except order_service.StorageLocationInvalidError as exc:
        raise HTTPException(
            status_code=422,
            detail={"row_index": exc.index, "message": str(exc)},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await session.commit()
    return [ContainerRead.model_validate(c) for c in spawned]


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    group_id: UUID, order_id: UUID, body: OrderCancel,
    session: SessionDep, admin: GroupAdminDep,
) -> OrderRead:
    order = await order_service.get_order(session, order_id)
    if order is None or order.group_id != group_id:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        await order_service.cancel_order(session, order, reason=body.cancellation_reason)
    except order_service.OrderStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await session.commit()
    return await _hydrate(session, order)
```

- [ ] **Step 4: Register router in `app.py`**

```python
from chaima.routers.orders import router as orders_router
# ...
app.include_router(orders_router)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_api/test_orders.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/routers/orders.py src/chaima/app.py tests/test_api/test_orders.py
git commit -m "feat(orders): /api/v1/groups/{gid}/orders router (CRUD + receive + cancel)"
```

---

### Task 25: `routers/wishlist.py`

**Files:**
- Create: `src/chaima/routers/wishlist.py`
- Test: `tests/test_api/test_wishlist.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api/test_wishlist.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_wishlist_with_chemical_id(client, group, chemical, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/wishlist",
        json={"chemical_id": str(chemical.id), "comment": "please"},
    )
    assert resp.status_code == 201
    assert resp.json()["chemical_id"] == str(chemical.id)


@pytest.mark.asyncio
async def test_create_wishlist_freeform(client, group, membership):
    resp = await client.post(
        f"/api/v1/groups/{group.id}/wishlist",
        json={"freeform_name": "Mystery reagent", "freeform_cas": "1-2-3"},
    )
    assert resp.status_code == 201
    assert resp.json()["freeform_name"] == "Mystery reagent"


@pytest.mark.asyncio
async def test_list_wishlist_only_open(client, group, chemical, membership):
    r1 = await client.post(f"/api/v1/groups/{group.id}/wishlist", json={"chemical_id": str(chemical.id)})
    await client.post(f"/api/v1/groups/{group.id}/wishlist/{r1.json()['id']}/dismiss")

    r2 = await client.post(f"/api/v1/groups/{group.id}/wishlist", json={"chemical_id": str(chemical.id), "comment": "still open"})

    resp = await client.get(f"/api/v1/groups/{group.id}/wishlist")
    ids = [item["id"] for item in resp.json()["items"]]
    assert r2.json()["id"] in ids
    assert r1.json()["id"] not in ids


@pytest.mark.asyncio
async def test_promote_with_chemical_id_returns_chemical(
    client, group, chemical, membership
):
    r = await client.post(
        f"/api/v1/groups/{group.id}/wishlist", json={"chemical_id": str(chemical.id)},
    )
    wid = r.json()["id"]
    resp = await client.post(f"/api/v1/groups/{group.id}/wishlist/{wid}/promote")
    assert resp.status_code == 200
    assert resp.json()["chemical_id"] == str(chemical.id)
```

- [ ] **Step 2: Run to verify failure**

Expected: 404.

- [ ] **Step 3: Implement**

Create `src/chaima/routers/wishlist.py`:

```python
"""Router for wishlist endpoints."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from chaima.dependencies import CurrentUserDep, GroupMemberDep, SessionDep
from chaima.models.chemical import Chemical
from chaima.models.wishlist import WishlistStatus
from chaima.schemas.pagination import PaginatedResponse
from chaima.schemas.wishlist import (
    WishlistCreate,
    WishlistPromoteResult,
    WishlistRead,
    WishlistUpdate,
)
from chaima.services import wishlist as wishlist_service

router = APIRouter(prefix="/api/v1/groups/{group_id}/wishlist", tags=["wishlist"])


async def _hydrate(session, item) -> WishlistRead:
    name: str | None = None
    if item.chemical_id is not None:
        chem = await session.get(Chemical, item.chemical_id)
        name = chem.name if chem else None
    base = WishlistRead.model_validate(item)
    return base.model_copy(update={"chemical_name": name})


@router.get("", response_model=PaginatedResponse[WishlistRead])
async def list_wishlist(
    group_id: UUID,
    session: SessionDep,
    member: GroupMemberDep,
    status_: WishlistStatus = Query(WishlistStatus.OPEN, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> PaginatedResponse[WishlistRead]:
    items = await wishlist_service.list_wishlist(session, group_id=group_id, status=status_)
    page = items[offset : offset + limit]
    hydrated = [await _hydrate(session, x) for x in page]
    return PaginatedResponse(items=hydrated, total=len(items), offset=offset, limit=limit)


@router.post("", response_model=WishlistRead, status_code=status.HTTP_201_CREATED)
async def create_wishlist(
    group_id: UUID,
    body: WishlistCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
    member: GroupMemberDep,
) -> WishlistRead:
    item = await wishlist_service.create_wishlist(
        session,
        group_id=group_id,
        chemical_id=body.chemical_id,
        freeform_name=body.freeform_name,
        freeform_cas=body.freeform_cas,
        comment=body.comment,
        requested_by_user_id=current_user.id,
    )
    await session.commit()
    return await _hydrate(session, item)


@router.post("/{wishlist_id}/dismiss", response_model=WishlistRead)
async def dismiss_wishlist(
    group_id: UUID, wishlist_id: UUID,
    session: SessionDep, current_user: CurrentUserDep, member: GroupMemberDep,
) -> WishlistRead:
    item = await wishlist_service.get_wishlist(session, wishlist_id)
    if item is None or item.group_id != group_id:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    await wishlist_service.dismiss_wishlist(session, item, dismissed_by_user_id=current_user.id)
    await session.commit()
    return await _hydrate(session, item)


@router.post("/{wishlist_id}/promote", response_model=WishlistPromoteResult)
async def promote_wishlist(
    group_id: UUID, wishlist_id: UUID,
    session: SessionDep, member: GroupMemberDep,
) -> WishlistPromoteResult:
    item = await wishlist_service.get_wishlist(session, wishlist_id)
    if item is None or item.group_id != group_id:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    try:
        chemical_id = await wishlist_service.promote_wishlist(session, item)
    except wishlist_service.WishlistChemicalNotResolvable as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "chemical_not_resolvable", "message": str(exc)},
        )
    await session.commit()
    return WishlistPromoteResult(wishlist_item_id=item.id, chemical_id=chemical_id)
```

- [ ] **Step 4: Register router in `app.py`**

```python
from chaima.routers.wishlist import router as wishlist_router
# ...
app.include_router(wishlist_router)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_api/test_wishlist.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/chaima/routers/wishlist.py src/chaima/app.py tests/test_api/test_wishlist.py
git commit -m "feat(orders): /api/v1/groups/{gid}/wishlist router"
```

---

### Task 26: Add `/pubchem/vendors/{cid}` endpoint

**Files:**
- Modify: `src/chaima/routers/pubchem.py`
- Modify: existing PubChem test file (find with `Glob tests/test_api/test_pubchem*.py`)

- [ ] **Step 1: Write failing test**

Append to the existing `tests/test_api/test_pubchem*.py` (or create `tests/test_api/test_pubchem_vendors.py`):

```python
import pytest


@pytest.mark.asyncio
async def test_get_pubchem_vendors_returns_list(client, monkeypatch):
    from chaima.schemas.pubchem import PubChemVendor

    async def fake_lookup(cid: str):
        return [
            PubChemVendor(name="Sigma-Aldrich", url="https://sigmaaldrich.com/p/180"),
            PubChemVendor(name="abcr", url="https://abcr.com/p/180"),
        ]
    monkeypatch.setattr("chaima.services.pubchem.lookup_vendors", fake_lookup)

    resp = await client.get("/api/v1/pubchem/vendors/180")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cid"] == "180"
    assert len(body["vendors"]) == 2
```

- [ ] **Step 2: Run to verify failure**

Expected: 404.

- [ ] **Step 3: Add the endpoint**

In `src/chaima/routers/pubchem.py`, add the route (do not duplicate the existing imports — read the current file first):

```python
from chaima.schemas.pubchem import PubChemVendorList
from chaima.services.pubchem import lookup_vendors as _lookup_vendors


@router.get("/vendors/{cid}", response_model=PubChemVendorList)
async def get_pubchem_vendors(cid: str) -> PubChemVendorList:
    """PubChem 'Chemical Vendors' for a CID. Returns empty list on upstream failure."""
    vendors = await _lookup_vendors(cid)
    return PubChemVendorList(cid=cid, vendors=vendors)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api/test_pubchem_vendors.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/routers/pubchem.py tests/test_api/
git commit -m "feat(orders): GET /pubchem/vendors/{cid}"
```

---

### Task 27: Embed `lead_time` in `GET /suppliers`

**Files:**
- Modify: `src/chaima/routers/suppliers.py`
- Modify: `tests/test_api/test_suppliers.py` (or create one)

- [ ] **Step 1: Write failing test**

Create or extend `tests/test_api/test_suppliers_lead_time.py`:

```python
import datetime
import pytest


@pytest.mark.asyncio
async def test_supplier_lead_time_null_under_three_orders(client, group, supplier, membership):
    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    items = resp.json()["items"]
    target = next(s for s in items if s["id"] == str(supplier.id))
    assert target["lead_time"] is None


@pytest.mark.asyncio
async def test_supplier_lead_time_populated_with_history(
    client, session, group, supplier, chemical, user, membership
):
    """Pre-populate 4 received orders with realistic deltas, then expect populated stats."""
    from chaima.models.order import Order, OrderStatus
    from chaima.models.project import Project

    project = Project(group_id=group.id, name="Cat")
    session.add(project)
    await session.flush()

    base_ordered = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    deltas = [5, 10, 14, 20]
    for d in deltas:
        o = Order(
            group_id=group.id, chemical_id=chemical.id, supplier_id=supplier.id,
            project_id=project.id, amount_per_package=1, unit="g", package_count=1,
            ordered_by_user_id=user.id, status=OrderStatus.RECEIVED,
        )
        session.add(o)
        await session.flush()
        o.ordered_at = base_ordered
        o.received_at = base_ordered + datetime.timedelta(days=d)
        session.add(o)
    await session.flush()

    resp = await client.get(f"/api/v1/groups/{group.id}/suppliers")
    target = next(s for s in resp.json()["items"] if s["id"] == str(supplier.id))
    assert target["lead_time"] is not None
    assert target["lead_time"]["order_count"] == 4
    assert target["lead_time"]["median_days"] == 12
```

- [ ] **Step 2: Run to verify failure**

Expected: KeyError 'lead_time' or assert None != stats.

- [ ] **Step 3: Implement**

In `src/chaima/routers/suppliers.py`:

1. Import the lead-time service:
   ```python
   from chaima.services.orders import lead_time_stats
   ```

2. Modify `_supplier_read_with_count` (line 19) to accept optional lead_time and embed it. Replace the helper:

```python
def _supplier_read_with_count(
    supplier, container_count: int, lead_time=None
) -> SupplierRead:
    data = SupplierRead.model_validate(supplier, from_attributes=True)
    return data.model_copy(
        update={"container_count": container_count, "lead_time": lead_time}
    )
```

3. In `list_suppliers` (line 25), after fetching `counts`, also fetch lead-time stats per supplier and pass to the helper:

```python
    lead_times = {}
    for s in items:
        lead_times[s.id] = await lead_time_stats(
            session, group_id=group_id, supplier_id=s.id
        )
    return PaginatedResponse(
        items=[
            _supplier_read_with_count(s, counts.get(s.id, 0), lead_times.get(s.id))
            for s in items
        ],
        total=total, offset=offset, limit=limit,
    )
```

4. Apply the same `lead_time=...` pass-through to `create_supplier`, `get_supplier`, `update_supplier` in this file (they all use `_supplier_read_with_count`). For these single-supplier paths the lead time comes from `await lead_time_stats(session, group_id=group_id, supplier_id=supplier.id)`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_api/test_suppliers_lead_time.py -v`
Expected: 2 passed. Also re-run existing supplier tests: `uv run pytest tests/test_api/test_suppliers.py -v` to confirm no regressions.

- [ ] **Step 5: Commit**

```bash
git add src/chaima/routers/suppliers.py tests/test_api/test_suppliers_lead_time.py
git commit -m "feat(orders): embed lead_time stats in GET /suppliers"
```

---

### Task 28: Verify all routers wired

**Files:**
- Verify: `src/chaima/app.py`

- [ ] **Step 1: Inspect**

Open `src/chaima/app.py` and confirm these `include_router` calls exist:

- `app.include_router(projects_router)` (added in Task 23)
- `app.include_router(orders_router)` (added in Task 24)
- `app.include_router(wishlist_router)` (added in Task 25)

Run a smoke check:

```bash
uv run python -c "
from chaima.app import app
paths = sorted({r.path for r in app.routes if hasattr(r, 'path')})
for p in paths:
    if any(s in p for s in ['orders', 'wishlist', 'projects', 'pubchem']):
        print(p)
"
```

Expected: lists `/api/v1/groups/{group_id}/orders`, `/api/v1/groups/{group_id}/wishlist`, `/api/v1/groups/{group_id}/projects`, `/api/v1/pubchem/vendors/{cid}`.

- [ ] **Step 2: Commit if anything was added**

```bash
git status
git add src/chaima/app.py
git commit -m "chore(orders): finalize router wiring" || echo "nothing to commit"
```

---

## Phase 7 — Frontend types + hooks

### Task 29: Add Order/Project/Wishlist/Vendor types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Append types**

Append to `frontend/src/types/index.ts`:

```typescript
export type OrderStatus = "ordered" | "received" | "cancelled";

export interface ProjectRead {
  id: string;
  group_id: string;
  name: string;
  is_archived: boolean;
  created_at: string;
}

export interface ProjectCreate {
  name: string;
}

export interface ProjectUpdate {
  name?: string | null;
  is_archived?: boolean | null;
}

export interface OrderCreate {
  chemical_id: string;
  supplier_id: string;
  project_id: string;
  amount_per_package: number;
  unit: string;
  package_count: number;
  price_per_package?: number | string | null;
  currency?: string;
  purity?: string | null;
  vendor_catalog_number?: string | null;
  vendor_product_url?: string | null;
  vendor_order_number?: string | null;
  expected_arrival?: string | null;
  comment?: string | null;
  wishlist_item_id?: string | null;
}

export interface OrderUpdate {
  supplier_id?: string;
  project_id?: string;
  amount_per_package?: number;
  unit?: string;
  package_count?: number;
  price_per_package?: number | string | null;
  currency?: string;
  purity?: string | null;
  vendor_catalog_number?: string | null;
  vendor_product_url?: string | null;
  vendor_order_number?: string | null;
  expected_arrival?: string | null;
  comment?: string | null;
}

export interface OrderRead {
  id: string;
  group_id: string;
  chemical_id: string;
  chemical_name: string | null;
  supplier_id: string;
  supplier_name: string | null;
  project_id: string;
  project_name: string | null;
  amount_per_package: number;
  unit: string;
  package_count: number;
  price_per_package: string | null;  // Decimal serialized as string
  currency: string;
  purity: string | null;
  vendor_catalog_number: string | null;
  vendor_product_url: string | null;
  vendor_order_number: string | null;
  expected_arrival: string | null;
  comment: string | null;
  status: OrderStatus;
  ordered_by_user_id: string;
  ordered_at: string;
  received_by_user_id: string | null;
  received_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
}

export interface ContainerReceiveRow {
  identifier: string;
  storage_location_id: string;
  purity_override?: string | null;
}

export interface OrderReceive {
  containers: ContainerReceiveRow[];
}

export interface OrderCancel {
  cancellation_reason?: string | null;
}

export type WishlistStatus = "open" | "converted" | "dismissed";

export interface WishlistRead {
  id: string;
  group_id: string;
  chemical_id: string | null;
  chemical_name: string | null;
  freeform_name: string | null;
  freeform_cas: string | null;
  requested_by_user_id: string;
  requested_at: string;
  comment: string | null;
  status: WishlistStatus;
  converted_to_order_id: string | null;
  dismissed_at: string | null;
  dismissed_by_user_id: string | null;
}

export interface WishlistCreate {
  chemical_id?: string | null;
  freeform_name?: string | null;
  freeform_cas?: string | null;
  comment?: string | null;
}

export interface WishlistPromoteResult {
  wishlist_item_id: string;
  chemical_id: string;
}

export interface PubChemVendor {
  name: string;
  url: string;
  country: string | null;
}

export interface PubChemVendorList {
  cid: string;
  vendors: PubChemVendor[];
}

export interface LeadTimeStats {
  order_count: number;
  median_days: number;
  p25_days: number;
  p75_days: number;
}
```

Also extend the existing `SupplierRead` interface (~line 226) to add the optional `lead_time` field:

```typescript
export interface SupplierRead {
  id: string;
  name: string;
  group_id: string;
  created_at: string;
  container_count: number;
  lead_time: LeadTimeStats | null;
}
```

- [ ] **Step 2: Smoke-test the type-check**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(orders): frontend types for orders/wishlist/projects/vendors"
```

---

### Task 30: `useProjects` hook

**Files:**
- Create: `frontend/src/api/hooks/useProjects.ts`

- [ ] **Step 1: Write the hook**

Create the file mirroring `useSuppliers.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type {
  PaginatedResponse,
  ProjectRead,
  ProjectCreate,
  ProjectUpdate,
} from "../../types";

export function useProjects(groupId: string, includeArchived: boolean = false) {
  return useQuery<PaginatedResponse<ProjectRead>>({
    queryKey: ["projects", groupId, { includeArchived }],
    queryFn: () =>
      client
        .get(`/groups/${groupId}/projects`, {
          params: { include_archived: includeArchived, limit: 500 },
        })
        .then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useCreateProject(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectCreate) =>
      client
        .post(`/groups/${groupId}/projects`, data)
        .then((r) => r.data as ProjectRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", groupId] });
    },
  });
}

export function useUpdateProject(groupId: string, projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProjectUpdate) =>
      client
        .patch(`/groups/${groupId}/projects/${projectId}`, data)
        .then((r) => r.data as ProjectRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", groupId] });
    },
  });
}

export function useArchiveProject(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) =>
      client
        .post(`/groups/${groupId}/projects/${projectId}/archive`)
        .then((r) => r.data as ProjectRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects", groupId] });
    },
  });
}
```

- [ ] **Step 2: Build to type-check**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/hooks/useProjects.ts
git commit -m "feat(orders): useProjects TanStack hooks"
```

---

### Task 31: `useOrders` hook

**Files:**
- Create: `frontend/src/api/hooks/useOrders.ts`

- [ ] **Step 1: Write the hook**

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type {
  PaginatedResponse,
  OrderRead,
  OrderCreate,
  OrderUpdate,
  OrderReceive,
  OrderCancel,
  ContainerRead,
  OrderStatus,
} from "../../types";

export interface OrdersFilters {
  status?: OrderStatus;
  supplier_id?: string;
  project_id?: string;
  chemical_id?: string;
}

export function useOrders(groupId: string, filters: OrdersFilters = {}) {
  return useQuery<PaginatedResponse<OrderRead>>({
    queryKey: ["orders", groupId, filters],
    queryFn: () =>
      client
        .get(`/groups/${groupId}/orders`, { params: { ...filters, limit: 500 } })
        .then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useOrder(groupId: string, orderId: string | null | undefined) {
  return useQuery<OrderRead>({
    queryKey: ["orders", groupId, orderId],
    queryFn: () =>
      client.get(`/groups/${groupId}/orders/${orderId}`).then((r) => r.data),
    enabled: !!groupId && !!orderId,
  });
}

export function useCreateOrder(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderCreate) =>
      client
        .post(`/groups/${groupId}/orders`, data)
        .then((r) => r.data as OrderRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders", groupId] });
      qc.invalidateQueries({ queryKey: ["wishlist", groupId] });
    },
  });
}

export function useUpdateOrder(groupId: string, orderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderUpdate) =>
      client
        .patch(`/groups/${groupId}/orders/${orderId}`, data)
        .then((r) => r.data as OrderRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders", groupId] });
    },
  });
}

export function useReceiveOrder(groupId: string, orderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderReceive) =>
      client
        .post(`/groups/${groupId}/orders/${orderId}/receive`, data)
        .then((r) => r.data as ContainerRead[]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders", groupId] });
      qc.invalidateQueries({ queryKey: ["containers"] });
      qc.invalidateQueries({ queryKey: ["chemicals"] });
    },
  });
}

export function useCancelOrder(groupId: string, orderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderCancel) =>
      client
        .post(`/groups/${groupId}/orders/${orderId}/cancel`, data)
        .then((r) => r.data as OrderRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders", groupId] });
    },
  });
}
```

- [ ] **Step 2: Build to type-check**

Run: `cd frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/hooks/useOrders.ts
git commit -m "feat(orders): useOrders TanStack hooks"
```

---

### Task 32: `useWishlist` + `usePubChemVendors` hooks

**Files:**
- Create: `frontend/src/api/hooks/useWishlist.ts`
- Create: `frontend/src/api/hooks/usePubChemVendors.ts`

- [ ] **Step 1: Write the wishlist hook**

```typescript
// frontend/src/api/hooks/useWishlist.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type {
  PaginatedResponse,
  WishlistRead,
  WishlistCreate,
  WishlistPromoteResult,
} from "../../types";

export function useWishlist(groupId: string) {
  return useQuery<PaginatedResponse<WishlistRead>>({
    queryKey: ["wishlist", groupId],
    queryFn: () =>
      client.get(`/groups/${groupId}/wishlist`).then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useCreateWishlist(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WishlistCreate) =>
      client
        .post(`/groups/${groupId}/wishlist`, data)
        .then((r) => r.data as WishlistRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wishlist", groupId] });
    },
  });
}

export function useDismissWishlist(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (wishlistId: string) =>
      client
        .post(`/groups/${groupId}/wishlist/${wishlistId}/dismiss`)
        .then((r) => r.data as WishlistRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wishlist", groupId] });
    },
  });
}

export function usePromoteWishlist(groupId: string) {
  return useMutation({
    mutationFn: (wishlistId: string) =>
      client
        .post(`/groups/${groupId}/wishlist/${wishlistId}/promote`)
        .then((r) => r.data as WishlistPromoteResult),
  });
}
```

- [ ] **Step 2: Write the PubChem vendors hook**

```typescript
// frontend/src/api/hooks/usePubChemVendors.ts
import { useQuery } from "@tanstack/react-query";
import client from "../client";
import type { PubChemVendorList } from "../../types";

export function usePubChemVendors(cid: string | null | undefined) {
  return useQuery<PubChemVendorList>({
    queryKey: ["pubchem", "vendors", cid],
    queryFn: () =>
      client.get(`/pubchem/vendors/${cid}`).then((r) => r.data),
    enabled: !!cid,
    // PubChem returns are cached server-side for 24h; on the client a
    // staleTime of 1h is plenty.
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}
```

- [ ] **Step 3: Build to type-check**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/hooks/useWishlist.ts frontend/src/api/hooks/usePubChemVendors.ts
git commit -m "feat(orders): useWishlist + usePubChemVendors hooks"
```

---

### Task 33: Confirm `useSuppliers` reads `lead_time`

**Files:**
- Verify: `frontend/src/api/hooks/useSuppliers.ts`

The existing hook already exposes `SupplierRead` directly via `r.data.items`. Since we extended `SupplierRead` in Task 29, the `lead_time` field is now reachable on the existing hook with no code change. Confirm with a `grep` that no consumer drops the field.

- [ ] **Step 1: Run a quick search**

Use the Grep tool: pattern `SupplierRead` in `frontend/src/`. Confirm no consumer uses a narrowed type like `Pick<SupplierRead, ...>` that would drop `lead_time`. (None expected — code uses `SupplierRead` directly.)

- [ ] **Step 2: No commit needed unless something was changed.**

---

## Phase 8 — Frontend: Settings (Projects admin)

### Task 34: `ProjectsAdminSection` + Settings wiring

**Files:**
- Create: `frontend/src/components/settings/ProjectsAdminSection.tsx`
- Modify: `frontend/src/components/settings/SettingsNav.tsx` (add a new key)
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Create the section component**

```tsx
// frontend/src/components/settings/ProjectsAdminSection.tsx
import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import ArchiveIcon from "@mui/icons-material/Archive";
import UnarchiveIcon from "@mui/icons-material/Unarchive";
import {
  useProjects,
  useCreateProject,
  useUpdateProject,
  useArchiveProject,
} from "../../api/hooks/useProjects";
import { SectionHeader } from "./SectionHeader";
import type { ProjectRead } from "../../types";

interface Props {
  groupId: string;
}

type DialogState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; project: ProjectRead };

export function ProjectsAdminSection({ groupId }: Props) {
  const [showArchived, setShowArchived] = useState(false);
  const { data, isLoading } = useProjects(groupId, showArchived);
  const projects = data?.items ?? [];

  const create = useCreateProject(groupId);
  const archive = useArchiveProject(groupId);
  const [dialog, setDialog] = useState<DialogState>({ mode: "closed" });
  const [name, setName] = useState("");

  const submit = async () => {
    if (dialog.mode === "create") {
      await create.mutateAsync({ name });
    } else if (dialog.mode === "edit") {
      const update = useUpdateProject(groupId, dialog.project.id);
      await update.mutateAsync({ name });
    }
    setDialog({ mode: "closed" });
    setName("");
  };

  return (
    <Box>
      <SectionHeader
        title="Projects"
        subtitle="Group-scoped projects used to tag chemical orders for budget tracking."
        actions={
          <Stack direction="row" gap={1}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => setShowArchived((s) => !s)}
            >
              {showArchived ? "Hide archived" : "Show archived"}
            </Button>
            <Button
              size="small"
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => {
                setName("");
                setDialog({ mode: "create" });
              }}
            >
              New project
            </Button>
          </Stack>
        }
      />

      {isLoading && (
        <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
          <CircularProgress size={20} />
        </Box>
      )}

      {!isLoading && projects.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No projects yet. Click <b>New project</b> to add one.
        </Typography>
      )}

      {projects.length > 0 && (
        <Stack
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            overflow: "hidden",
            bgcolor: "background.paper",
          }}
        >
          {projects.map((p, i) => (
            <Stack
              key={p.id}
              direction="row"
              sx={{
                px: 2,
                py: 1.25,
                gap: 1,
                alignItems: "center",
                borderBottom: i < projects.length - 1 ? "1px solid" : "none",
                borderColor: "divider",
              }}
            >
              <Box sx={{ flex: 1 }}>
                <Typography variant="body2">{p.name}</Typography>
                {p.is_archived && (
                  <Chip size="small" label="Archived" sx={{ mt: 0.5 }} />
                )}
              </Box>
              <IconButton
                size="small"
                onClick={() => {
                  setName(p.name);
                  setDialog({ mode: "edit", project: p });
                }}
              >
                <EditIcon fontSize="small" />
              </IconButton>
              {!p.is_archived && (
                <IconButton
                  size="small"
                  onClick={() => archive.mutate(p.id)}
                >
                  <ArchiveIcon fontSize="small" />
                </IconButton>
              )}
            </Stack>
          ))}
        </Stack>
      )}

      <Dialog
        open={dialog.mode !== "closed"}
        onClose={() => setDialog({ mode: "closed" })}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>
          {dialog.mode === "create" ? "New project" : "Edit project"}
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            margin="dense"
            label="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          {create.error instanceof Error && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {create.error.message}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog({ mode: "closed" })}>Cancel</Button>
          <Button onClick={submit} variant="contained" disabled={!name.trim()}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
```

> Note: `useUpdateProject` is being called inside the `submit` async function above. Hooks must be at the top level of the component — refactor by lifting the hook into a separate dialog component, or create the project ID-bound hook lazily through a generic `client.patch` call. Quick fix: replace the `else if (dialog.mode === "edit")` branch with a direct `client.patch` call:
>
> ```typescript
> import client from "../../api/client";
> // ...
> } else if (dialog.mode === "edit") {
>   await client.patch(`/groups/${groupId}/projects/${dialog.project.id}`, { name });
> }
> ```
>
> This is the lighter-weight option and matches a few other places in the codebase that do inline patches.

- [ ] **Step 2: Apply the inline patch fix**

Replace the `submit` function in the file you just created with:

```typescript
import client from "../../api/client";
import { useQueryClient } from "@tanstack/react-query";
// ... in component:
const qc = useQueryClient();
const submit = async () => {
  if (dialog.mode === "create") {
    await create.mutateAsync({ name });
  } else if (dialog.mode === "edit") {
    await client.patch(`/groups/${groupId}/projects/${dialog.project.id}`, { name });
    qc.invalidateQueries({ queryKey: ["projects", groupId] });
  }
  setDialog({ mode: "closed" });
  setName("");
};
```

Remove the now-unused `useUpdateProject` import.

- [ ] **Step 3: Wire into SettingsNav**

Open `frontend/src/components/settings/SettingsNav.tsx` and add `"projects"` to the `SettingsSectionKey` union (search for existing keys like `"hazard-tags"` and follow the pattern).

- [ ] **Step 4: Wire into SettingsPage**

In `frontend/src/pages/SettingsPage.tsx`:

1. Add the import:
   ```typescript
   import { ProjectsAdminSection } from "../components/settings/ProjectsAdminSection";
   ```

2. In the `items` array, add a new entry between `suppliers` and `import`:
   ```typescript
   { key: "projects", label: "Projects", group: "GROUP ADMIN", visible: isMember },
   ```

3. In the rendered switch (around line 48), add:
   ```tsx
   {active === "projects" && isMember && user?.main_group_id && (
     <ProjectsAdminSection groupId={user.main_group_id} />
   )}
   ```

- [ ] **Step 5: Build to type-check**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/settings/ProjectsAdminSection.tsx \
        frontend/src/components/settings/SettingsNav.tsx \
        frontend/src/pages/SettingsPage.tsx
git commit -m "feat(orders): ProjectsAdminSection in Settings"
```

---

## Phase 9 — Frontend: Orders feature

> Pre-flight for this phase: the backend must be running and migrations applied. In one terminal: `uv run uvicorn chaima.app:app --reload`. In another: `cd frontend && npm run dev`. The Vite dev server proxies `/api` to the backend.

### Task 35: `OrdersPage` skeleton with tabs

**Files:**
- Create: `frontend/src/pages/OrdersPage.tsx`
- Modify: `frontend/src/App.tsx` (add route)
- Modify: `frontend/src/components/Layout.tsx` (add nav item)

- [ ] **Step 1: Create the page skeleton**

```tsx
// frontend/src/pages/OrdersPage.tsx
import { useState } from "react";
import { Box, Tab, Tabs } from "@mui/material";
import { useCurrentUser } from "../api/hooks/useAuth";
import { OrderList } from "../components/orders/OrderList";
import { WishlistList } from "../components/orders/WishlistList";
import type { OrderStatus } from "../types";

type TabKey = OrderStatus | "wishlist";

export default function OrdersPage() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";
  const [tab, setTab] = useState<TabKey>("ordered");

  if (!groupId) {
    return <Box sx={{ p: 2 }}>Join a group to see orders.</Box>;
  }

  return (
    <Box>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab value="ordered" label="Open" />
        <Tab value="received" label="Received" />
        <Tab value="cancelled" label="Cancelled" />
        <Tab value="wishlist" label="Wishlist" />
      </Tabs>

      {tab === "wishlist" ? (
        <WishlistList groupId={groupId} />
      ) : (
        <OrderList groupId={groupId} status={tab} />
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Create empty placeholder components**

Create `frontend/src/components/orders/OrderList.tsx`:

```tsx
import type { OrderStatus } from "../../types";

interface Props {
  groupId: string;
  status: OrderStatus;
}

export function OrderList({ groupId, status }: Props) {
  return <div>OrderList placeholder ({status})</div>;
}
```

Create `frontend/src/components/orders/WishlistList.tsx`:

```tsx
interface Props {
  groupId: string;
}

export function WishlistList({ groupId }: Props) {
  return <div>WishlistList placeholder</div>;
}
```

(These get fleshed out in later tasks.)

- [ ] **Step 3: Add route to App.tsx**

In `frontend/src/App.tsx`, add the import and route inside the protected `<Layout>` block:

```tsx
import OrdersPage from "./pages/OrdersPage";
// ...
<Route path="/orders" element={<OrdersPage />} />
```

- [ ] **Step 4: Add nav item in Layout.tsx**

In `frontend/src/components/Layout.tsx`, modify the `navItems` array (line 14):

```tsx
const navItems = [
  { to: "/", label: "Chemicals" },
  { to: "/storage", label: "Storage" },
  { to: "/orders", label: "Orders" },
  { to: "/settings", label: "Settings" },
];
```

- [ ] **Step 5: Build and smoke-check**

Run: `cd frontend && npm run build`. Expected: success.

Then run dev server, navigate to `/orders`, click each tab; you should see the placeholder text. Login as a group member.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/OrdersPage.tsx \
        frontend/src/components/orders/OrderList.tsx \
        frontend/src/components/orders/WishlistList.tsx \
        frontend/src/App.tsx \
        frontend/src/components/Layout.tsx
git commit -m "feat(orders): /orders route + tab skeleton + placeholder lists"
```

---

### Task 36: Flesh out `OrderList`

**Files:**
- Replace: `frontend/src/components/orders/OrderList.tsx`

- [ ] **Step 1: Replace placeholder with real list**

```tsx
import {
  Box,
  Button,
  Card,
  CardActionArea,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { useState } from "react";
import { useOrders } from "../../api/hooks/useOrders";
import { useDrawer } from "../drawer/DrawerContext";
import type { OrderRead, OrderStatus } from "../../types";

interface Props {
  groupId: string;
  status: OrderStatus;
}

function formatPrice(o: OrderRead): string {
  if (o.price_per_package == null) return "no price";
  return `${o.currency} ${o.price_per_package}`;
}

function isOverdue(o: OrderRead): boolean {
  if (!o.expected_arrival || o.status !== "ordered") return false;
  return new Date(o.expected_arrival) < new Date();
}

export function OrderList({ groupId, status }: Props) {
  const { data, isLoading } = useOrders(groupId, { status });
  const { open: openDrawer } = useDrawer();
  const orders = data?.items ?? [];

  const newOrder = () => openDrawer({ kind: "new-order", groupId });

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" sx={{ mb: 2 }}>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={newOrder}
        >
          New order
        </Button>
      </Stack>

      {orders.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No {status} orders.
        </Typography>
      )}

      <Stack gap={1}>
        {orders.map((o) => (
          <Card key={o.id} variant="outlined">
            <CardActionArea
              onClick={() => openDrawer({ kind: "order-detail", groupId, orderId: o.id })}
              sx={{ p: 2 }}
            >
              <Stack
                direction={{ xs: "column", sm: "row" }}
                gap={1}
                alignItems={{ sm: "center" }}
              >
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="subtitle2" noWrap>
                    {o.chemical_name ?? "(unknown)"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {o.supplier_name} • {o.project_name}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2">
                    {o.package_count} × {o.amount_per_package} {o.unit} @ {formatPrice(o)}
                  </Typography>
                </Box>
                <Box>
                  {o.expected_arrival && (
                    <Chip
                      size="small"
                      label={`exp ${o.expected_arrival}`}
                      color={isOverdue(o) ? "error" : "default"}
                    />
                  )}
                </Box>
              </Stack>
            </CardActionArea>
          </Card>
        ))}
      </Stack>
    </Box>
  );
}
```

> Note: this references `openDrawer({ kind: "new-order", ... })` and `openDrawer({ kind: "order-detail", ... })`. The drawer system in `frontend/src/components/drawer/DrawerContext.tsx` and `EditDrawer.tsx` needs to handle these new kinds. Read those files in **Task 37** and add cases there.

- [ ] **Step 2: Build (will fail until Task 37 wires the drawer)**

Run: `cd frontend && npm run build`
Expected: TypeScript may complain about the `kind` literal types. That's fine — fix in Task 37.

- [ ] **Step 3: Skip commit until Task 37 makes the build pass.**

---

### Task 37: Wire `OrderForm` drawer

**Files:**
- Read first: `frontend/src/components/drawer/DrawerContext.tsx`, `frontend/src/components/drawer/EditDrawer.tsx`
- Create: `frontend/src/components/orders/OrderForm.tsx`
- Modify: drawer context types + EditDrawer rendering

- [ ] **Step 1: Inspect the drawer system**

Read `DrawerContext.tsx` and `EditDrawer.tsx`. The pattern is: `useDrawer()` returns `{ open, close }`; `open` takes a discriminated union (`{ kind: "edit-container", ...}` etc.). `EditDrawer` switches on `kind` and renders the right form.

- [ ] **Step 2: Extend the union to support orders**

In `DrawerContext.tsx`, add to the discriminated union (the exact shape will mirror existing entries):

```typescript
| { kind: "new-order"; groupId: string; chemicalId?: string; wishlistItemId?: string }
| { kind: "order-detail"; groupId: string; orderId: string }
```

- [ ] **Step 3: Create the OrderForm component**

```tsx
// frontend/src/components/orders/OrderForm.tsx
import { useState, useEffect } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Collapse,
  CircularProgress,
  Stack,
  TextField,
  Typography,
  createFilterOptions,
} from "@mui/material";
import { useCreateOrder } from "../../api/hooks/useOrders";
import { useSuppliers, useCreateSupplier } from "../../api/hooks/useSuppliers";
import { useProjects, useCreateProject } from "../../api/hooks/useProjects";
import { useChemicalDetail } from "../../api/hooks/useChemicals";
import type { SupplierRead, ProjectRead } from "../../types";
import { PubChemVendorPanel } from "./PubChemVendorPanel";

type SupplierOption = SupplierRead | { inputValue: string; name: string; id?: undefined };
type ProjectOption = ProjectRead | { inputValue: string; name: string; id?: undefined };

const supplierFilter = createFilterOptions<SupplierOption>();
const projectFilter = createFilterOptions<ProjectOption>();

interface Props {
  groupId: string;
  chemicalId?: string;
  wishlistItemId?: string;
  onDone: () => void;
}

export function OrderForm({ groupId, chemicalId, wishlistItemId, onDone }: Props) {
  const create = useCreateOrder(groupId);
  const { data: suppliersPage } = useSuppliers(groupId);
  const suppliers = suppliersPage?.items ?? [];
  const createSupplier = useCreateSupplier(groupId);

  const { data: projectsPage } = useProjects(groupId);
  const projects = projectsPage?.items ?? [];
  const createProject = useCreateProject(groupId);

  const chemical = useChemicalDetail(groupId, chemicalId ?? "");

  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [amount, setAmount] = useState<number | "">("");
  const [unit, setUnit] = useState("");
  const [packageCount, setPackageCount] = useState<number | "">(1);
  const [pricePerPackage, setPricePerPackage] = useState<string>("");
  const [currency, setCurrency] = useState("EUR");
  const [purity, setPurity] = useState("");
  const [vendorCatalog, setVendorCatalog] = useState("");
  const [vendorUrl, setVendorUrl] = useState("");
  const [vendorOrderNumber, setVendorOrderNumber] = useState("");
  const [expectedArrival, setExpectedArrival] = useState("");
  const [comment, setComment] = useState("");
  const [showOptional, setShowOptional] = useState(false);

  // Default to the first project named "General" if available
  useEffect(() => {
    if (projectId === null && projects.length > 0) {
      const general = projects.find((p) => p.name === "General");
      setProjectId(general?.id ?? projects[0].id);
    }
  }, [projects, projectId]);

  const submit = async () => {
    if (!chemicalId || !supplierId || !projectId) return;
    await create.mutateAsync({
      chemical_id: chemicalId,
      supplier_id: supplierId,
      project_id: projectId,
      amount_per_package: Number(amount),
      unit,
      package_count: Number(packageCount),
      price_per_package: pricePerPackage ? pricePerPackage : null,
      currency,
      purity: purity || null,
      vendor_catalog_number: vendorCatalog || null,
      vendor_product_url: vendorUrl || null,
      vendor_order_number: vendorOrderNumber || null,
      expected_arrival: expectedArrival || null,
      comment: comment || null,
      wishlist_item_id: wishlistItemId ?? null,
    });
    onDone();
  };

  const supplierLeadTime = suppliers.find((s) => s.id === supplierId)?.lead_time;

  if (chemicalId && chemical.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  return (
    <Stack gap={2} sx={{ p: 2 }}>
      <Typography variant="h6">New order</Typography>
      <Box>
        <Typography variant="caption" color="text.secondary">Chemical</Typography>
        <Typography variant="body1">
          {chemical.data?.name ?? "(pick from chemicals page)"}
        </Typography>
      </Box>

      <Autocomplete
        options={suppliers as SupplierOption[]}
        getOptionLabel={(o) => ("name" in o ? o.name : "")}
        value={suppliers.find((s) => s.id === supplierId) ?? null}
        onChange={async (_, value) => {
          if (value && "inputValue" in value) {
            const created = await createSupplier.mutateAsync({ name: value.inputValue });
            setSupplierId(created.id);
          } else {
            setSupplierId(value?.id ?? null);
          }
        }}
        filterOptions={(options, params) => {
          const filtered = supplierFilter(options, params);
          if (params.inputValue && !filtered.some((o) => "name" in o && o.name === params.inputValue)) {
            filtered.push({ inputValue: params.inputValue, name: `Add "${params.inputValue}"` });
          }
          return filtered;
        }}
        renderInput={(params) => <TextField {...params} label="Supplier" />}
        freeSolo={false}
        selectOnFocus
        clearOnBlur
        handleHomeEndKeys
      />

      {chemical.data?.cid && (
        <PubChemVendorPanel
          cid={chemical.data.cid}
          onPick={(name) => {
            const match = suppliers.find(
              (s) => s.name.toLowerCase() === name.toLowerCase(),
            );
            if (match) setSupplierId(match.id);
          }}
        />
      )}

      {supplierLeadTime && (
        <Alert severity="info" variant="outlined" sx={{ py: 0 }}>
          {(suppliers.find((s) => s.id === supplierId)?.name ?? "supplier")} usually takes{" "}
          {supplierLeadTime.p25_days}–{supplierLeadTime.p75_days} days for your group{" "}
          ({supplierLeadTime.order_count} past orders).
        </Alert>
      )}

      <Stack direction="row" gap={1}>
        <TextField
          label="Amount per package"
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value === "" ? "" : Number(e.target.value))}
          sx={{ flex: 2 }}
        />
        <TextField
          label="Unit"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          sx={{ flex: 1 }}
          placeholder="mL"
        />
        <TextField
          label="× count"
          type="number"
          value={packageCount}
          onChange={(e) => setPackageCount(e.target.value === "" ? "" : Number(e.target.value))}
          sx={{ flex: 1 }}
        />
      </Stack>

      <Stack direction="row" gap={1}>
        <TextField
          label="Price per package"
          value={pricePerPackage}
          onChange={(e) => setPricePerPackage(e.target.value)}
          sx={{ flex: 2 }}
          inputMode="decimal"
        />
        <TextField
          label="Currency"
          value={currency}
          onChange={(e) => setCurrency(e.target.value.toUpperCase())}
          sx={{ flex: 1 }}
          inputProps={{ maxLength: 3 }}
        />
      </Stack>

      <Autocomplete
        options={projects as ProjectOption[]}
        getOptionLabel={(o) => ("name" in o ? o.name : "")}
        value={projects.find((p) => p.id === projectId) ?? null}
        onChange={async (_, value) => {
          if (value && "inputValue" in value) {
            const created = await createProject.mutateAsync({ name: value.inputValue });
            setProjectId(created.id);
          } else {
            setProjectId(value?.id ?? null);
          }
        }}
        filterOptions={(options, params) => {
          const filtered = projectFilter(options, params);
          if (params.inputValue && !filtered.some((o) => "name" in o && o.name === params.inputValue)) {
            filtered.push({ inputValue: params.inputValue, name: `Add "${params.inputValue}"` });
          }
          return filtered;
        }}
        renderInput={(params) => <TextField {...params} label="Project" />}
        selectOnFocus
        clearOnBlur
        handleHomeEndKeys
      />

      <Button onClick={() => setShowOptional((s) => !s)} size="small">
        {showOptional ? "Hide optional details" : "Show optional details"}
      </Button>
      <Collapse in={showOptional}>
        <Stack gap={1}>
          <TextField label="Vendor catalog #" value={vendorCatalog} onChange={(e) => setVendorCatalog(e.target.value)} />
          <TextField label="Vendor product URL" value={vendorUrl} onChange={(e) => setVendorUrl(e.target.value)} />
          <TextField label="Vendor order #" value={vendorOrderNumber} onChange={(e) => setVendorOrderNumber(e.target.value)} />
          <TextField label="Purity" value={purity} onChange={(e) => setPurity(e.target.value)} />
          <TextField
            label="Expected arrival"
            type="date"
            InputLabelProps={{ shrink: true }}
            value={expectedArrival}
            onChange={(e) => setExpectedArrival(e.target.value)}
          />
          <TextField label="Comment" multiline rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
        </Stack>
      </Collapse>

      {create.error instanceof Error && (
        <Alert severity="error">
          {(create.error as any).response?.data?.detail ?? create.error.message}
        </Alert>
      )}

      <Stack direction="row" justifyContent="flex-end" gap={1}>
        <Button onClick={onDone}>Cancel</Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={!chemicalId || !supplierId || !projectId || amount === "" || !unit}
        >
          Place order
        </Button>
      </Stack>
    </Stack>
  );
}
```

- [ ] **Step 4: Wire OrderForm into the EditDrawer**

In `frontend/src/components/drawer/EditDrawer.tsx`, add cases for the new `kind`s. Pattern (mirror existing cases):

```tsx
import { OrderForm } from "../orders/OrderForm";
import { OrderDetailDrawer } from "../orders/OrderDetailDrawer"; // created in Task 39
// ...
{state.kind === "new-order" && (
  <OrderForm
    groupId={state.groupId}
    chemicalId={state.chemicalId}
    wishlistItemId={state.wishlistItemId}
    onDone={close}
  />
)}
{state.kind === "order-detail" && (
  <OrderDetailDrawer
    groupId={state.groupId}
    orderId={state.orderId}
    onDone={close}
  />
)}
```

(The `OrderDetailDrawer` import will fail until Task 39 — leave it commented out for now, or stub the file with a placeholder export so the import resolves.)

- [ ] **Step 5: Stub OrderDetailDrawer + PubChemVendorPanel placeholders so the build passes**

Create stubs:

```tsx
// frontend/src/components/orders/PubChemVendorPanel.tsx
interface Props {
  cid: string;
  onPick: (vendorName: string) => void;
}
export function PubChemVendorPanel(_: Props) {
  return null;  // Replaced in Task 38
}

// frontend/src/components/orders/OrderDetailDrawer.tsx
interface Props {
  groupId: string;
  orderId: string;
  onDone: () => void;
}
export function OrderDetailDrawer(_: Props) {
  return <div>OrderDetailDrawer placeholder</div>;  // Replaced in Task 39
}
```

- [ ] **Step 6: Build**

Run: `cd frontend && npm run build`. Expected: success.

- [ ] **Step 7: Manually smoke-test**

In the browser, open `/orders`, click "New order". You should see the form. Pick a chemical via... wait — the OrderForm needs a `chemicalId` upfront. For now, the only entry is from the chemical detail page (Task 41). The "New order" button on the OrderList page will open the form with no chemical pre-selected → it shows "(pick from chemicals page)". That's acceptable for v1 — a later iteration adds an inline chemical search. Document this in the spec follow-ups if you wish; otherwise note it as a known v1 gap.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/orders/ \
        frontend/src/components/drawer/DrawerContext.tsx \
        frontend/src/components/drawer/EditDrawer.tsx
git commit -m "feat(orders): OrderForm drawer + OrderList card view"
```

---

### Task 38: Implement `PubChemVendorPanel`

**Files:**
- Replace: `frontend/src/components/orders/PubChemVendorPanel.tsx`

- [ ] **Step 1: Replace placeholder**

```tsx
import {
  Alert,
  Box,
  Button,
  Collapse,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { usePubChemVendors } from "../../api/hooks/usePubChemVendors";

interface Props {
  cid: string;
  onPick: (vendorName: string) => void;
}

export function PubChemVendorPanel({ cid, onPick }: Props) {
  const { data, isLoading, error } = usePubChemVendors(cid);
  const [expanded, setExpanded] = useState(false);

  return (
    <Box>
      <Button
        size="small"
        variant="text"
        onClick={() => setExpanded((e) => !e)}
      >
        {expanded ? "Hide" : "Show"} PubChem vendor list
      </Button>

      <Collapse in={expanded}>
        {isLoading && <Typography variant="caption">Loading…</Typography>}
        {error && (
          <Alert severity="warning" sx={{ mt: 1 }}>
            PubChem temporarily unavailable.
          </Alert>
        )}
        {data && data.vendors.length === 0 && (
          <Typography variant="caption" color="text.secondary">
            PubChem has no vendor list for this compound.
          </Typography>
        )}
        {data && data.vendors.length > 0 && (
          <Stack gap={0.5} sx={{ mt: 1 }}>
            {data.vendors.map((v) => (
              <Stack
                key={v.url}
                direction="row"
                gap={1}
                alignItems="center"
              >
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => onPick(v.name)}
                >
                  Use as supplier
                </Button>
                <Link href={v.url} target="_blank" rel="noopener" sx={{ flex: 1 }} noWrap>
                  {v.name}
                </Link>
              </Stack>
            ))}
          </Stack>
        )}
      </Collapse>
    </Box>
  );
}
```

- [ ] **Step 2: Build + manual check**

Run: `cd frontend && npm run build`. Then in the dev server, open the order form for a chemical that has a PubChem CID — click "Show PubChem vendor list" and confirm vendors load.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/orders/PubChemVendorPanel.tsx
git commit -m "feat(orders): PubChemVendorPanel inside OrderForm"
```

---

### Task 39: Implement `OrderDetailDrawer` + `ReceiveOrderDialog`

**Files:**
- Replace: `frontend/src/components/orders/OrderDetailDrawer.tsx`
- Create: `frontend/src/components/orders/ReceiveOrderDialog.tsx`

- [ ] **Step 1: Create `ReceiveOrderDialog`**

```tsx
// frontend/src/components/orders/ReceiveOrderDialog.tsx
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
} from "@mui/material";
import { useState } from "react";
import { useReceiveOrder } from "../../api/hooks/useOrders";
import LocationPicker from "../LocationPicker";
import type { OrderRead } from "../../types";

interface Props {
  open: boolean;
  order: OrderRead;
  onDone: () => void;
}

interface Row {
  identifier: string;
  storage_location_id: string | null;
  purity_override: string;
}

export function ReceiveOrderDialog({ open, order, onDone }: Props) {
  const receive = useReceiveOrder(order.group_id, order.id);
  const [rows, setRows] = useState<Row[]>(
    Array.from({ length: order.package_count }, () => ({
      identifier: "",
      storage_location_id: null,
      purity_override: "",
    })),
  );

  const updateRow = (i: number, patch: Partial<Row>) => {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  };

  const submit = async () => {
    await receive.mutateAsync({
      containers: rows.map((r) => ({
        identifier: r.identifier,
        storage_location_id: r.storage_location_id!,
        purity_override: r.purity_override || null,
      })),
    });
    onDone();
  };

  const allFilled = rows.every(
    (r) => r.identifier.trim() && r.storage_location_id,
  );

  return (
    <Dialog open={open} onClose={onDone} fullWidth maxWidth="sm">
      <DialogTitle>Receive order ({order.package_count} containers)</DialogTitle>
      <DialogContent>
        <Stack gap={2} sx={{ mt: 1 }}>
          {rows.map((row, i) => (
            <Stack key={i} gap={1} sx={{ borderBottom: "1px solid", borderColor: "divider", pb: 2 }}>
              <TextField
                label={`Container ${i + 1} identifier`}
                value={row.identifier}
                onChange={(e) => updateRow(i, { identifier: e.target.value })}
                size="small"
              />
              <LocationPicker
                groupId={order.group_id}
                value={row.storage_location_id}
                onChange={(loc) => updateRow(i, { storage_location_id: loc })}
              />
              <TextField
                label="Purity override (optional)"
                value={row.purity_override}
                onChange={(e) => updateRow(i, { purity_override: e.target.value })}
                size="small"
                placeholder={order.purity ?? ""}
              />
            </Stack>
          ))}
          {receive.error instanceof Error && (
            <Alert severity="error">
              {(receive.error as any).response?.data?.detail ?? receive.error.message}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onDone}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={!allFilled || receive.isPending}>
          Mark received
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

> Note: this assumes `LocationPicker` accepts `groupId`, `value`, `onChange`. Read the existing `frontend/src/components/LocationPicker.tsx` and adapt the props if they differ. If LocationPicker uses a different API, wrap it appropriately.

- [ ] **Step 2: Replace `OrderDetailDrawer`**

```tsx
// frontend/src/components/orders/OrderDetailDrawer.tsx
import {
  Alert,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useOrder, useCancelOrder } from "../../api/hooks/useOrders";
import { useDrawer } from "../drawer/DrawerContext";
import { RoleGate } from "../RoleGate";
import { ReceiveOrderDialog } from "./ReceiveOrderDialog";

interface Props {
  groupId: string;
  orderId: string;
  onDone: () => void;
}

export function OrderDetailDrawer({ groupId, orderId, onDone }: Props) {
  const { data: order, isLoading } = useOrder(groupId, orderId);
  const cancel = useCancelOrder(groupId, orderId);
  const { open: openDrawer } = useDrawer();
  const [showReceive, setShowReceive] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState("");

  if (isLoading || !order) {
    return (
      <Stack sx={{ p: 4, alignItems: "center" }}>
        <CircularProgress size={20} />
      </Stack>
    );
  }

  const reorder = () =>
    openDrawer({ kind: "new-order", groupId, chemicalId: order.chemical_id });

  return (
    <Stack gap={2} sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" gap={1}>
        <Typography variant="h6" sx={{ flex: 1 }}>
          {order.chemical_name}
        </Typography>
        <Chip
          size="small"
          color={
            order.status === "ordered"
              ? "warning"
              : order.status === "received"
              ? "success"
              : "default"
          }
          label={order.status}
        />
      </Stack>

      <Typography variant="body2" color="text.secondary">
        {order.package_count} × {order.amount_per_package} {order.unit} from{" "}
        {order.supplier_name} ({order.project_name})
      </Typography>

      {order.price_per_package && (
        <Typography variant="body2">
          {order.currency} {order.price_per_package} per package · total{" "}
          {order.currency}{" "}
          {(Number(order.price_per_package) * order.package_count).toFixed(2)}
        </Typography>
      )}

      {order.expected_arrival && (
        <Typography variant="caption">
          Expected: {order.expected_arrival}
        </Typography>
      )}

      {order.vendor_product_url && (
        <Typography variant="caption">
          <a href={order.vendor_product_url} target="_blank" rel="noopener">
            Vendor product page ↗
          </a>
        </Typography>
      )}

      {order.comment && (
        <Typography variant="body2" sx={{ fontStyle: "italic" }}>
          {order.comment}
        </Typography>
      )}

      {order.status === "cancelled" && order.cancellation_reason && (
        <Alert severity="info">Cancelled: {order.cancellation_reason}</Alert>
      )}

      <Stack direction="row" gap={1} sx={{ mt: 2 }}>
        {order.status === "ordered" && (
          <Button variant="contained" onClick={() => setShowReceive(true)}>
            Mark received
          </Button>
        )}
        {order.status === "ordered" && (
          <RoleGate allow={["admin"]}>
            <Button variant="outlined" color="error" onClick={() => setShowCancel(true)}>
              Cancel
            </Button>
          </RoleGate>
        )}
        <Button variant="outlined" onClick={reorder}>
          Reorder
        </Button>
        <Button onClick={onDone}>Close</Button>
      </Stack>

      {showReceive && (
        <ReceiveOrderDialog
          open
          order={order}
          onDone={() => {
            setShowReceive(false);
            onDone();
          }}
        />
      )}

      <Dialog open={showCancel} onClose={() => setShowCancel(false)}>
        <DialogTitle>Cancel order</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            multiline
            rows={2}
            margin="dense"
            label="Reason (optional)"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCancel(false)}>Back</Button>
          <Button
            color="error"
            onClick={async () => {
              await cancel.mutateAsync({ cancellation_reason: cancelReason || null });
              setShowCancel(false);
              onDone();
            }}
          >
            Confirm cancel
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
```

- [ ] **Step 3: Build + manual smoke**

Run: `cd frontend && npm run build`. Then in the browser, click an order card → drawer opens. Click "Mark received" → dialog opens with N rows. Fill them and submit. Confirm the order moves to the Received tab and N containers appear in the chemical's storage view.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/orders/OrderDetailDrawer.tsx \
        frontend/src/components/orders/ReceiveOrderDialog.tsx
git commit -m "feat(orders): OrderDetailDrawer with receive/cancel/reorder actions"
```

---

### Task 40: Flesh out `WishlistList` + `WishlistForm`

**Files:**
- Replace: `frontend/src/components/orders/WishlistList.tsx`
- Create: `frontend/src/components/orders/WishlistForm.tsx`

- [ ] **Step 1: Create WishlistForm (modal-style)**

```tsx
// frontend/src/components/orders/WishlistForm.tsx
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useCreateWishlist } from "../../api/hooks/useWishlist";

interface Props {
  open: boolean;
  groupId: string;
  onDone: () => void;
}

export function WishlistForm({ open, groupId, onDone }: Props) {
  const create = useCreateWishlist(groupId);
  const [freeformName, setFreeformName] = useState("");
  const [freeformCas, setFreeformCas] = useState("");
  const [comment, setComment] = useState("");

  const submit = async () => {
    await create.mutateAsync({
      freeform_name: freeformName,
      freeform_cas: freeformCas || null,
      comment: comment || null,
    });
    onDone();
    setFreeformName("");
    setFreeformCas("");
    setComment("");
  };

  return (
    <Dialog open={open} onClose={onDone} fullWidth maxWidth="xs">
      <DialogTitle>Add to wishlist</DialogTitle>
      <DialogContent>
        <Stack gap={1.5} sx={{ mt: 1 }}>
          <TextField
            autoFocus
            label="Chemical name"
            value={freeformName}
            onChange={(e) => setFreeformName(e.target.value)}
            size="small"
          />
          <TextField
            label="CAS (optional)"
            value={freeformCas}
            onChange={(e) => setFreeformCas(e.target.value)}
            size="small"
          />
          <TextField
            label="Comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            multiline
            rows={2}
            size="small"
          />
          <Typography variant="caption" color="text.secondary">
            Promote a wishlist item later to convert it into a real order.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onDone}>Cancel</Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={!freeformName.trim() || create.isPending}
        >
          Add
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

- [ ] **Step 2: Replace `WishlistList`**

```tsx
// frontend/src/components/orders/WishlistList.tsx
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  IconButton,
  Stack,
  Typography,
  Alert,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { useState } from "react";
import {
  useWishlist,
  useDismissWishlist,
  usePromoteWishlist,
} from "../../api/hooks/useWishlist";
import { useDrawer } from "../drawer/DrawerContext";
import { WishlistForm } from "./WishlistForm";

interface Props {
  groupId: string;
}

export function WishlistList({ groupId }: Props) {
  const { data, isLoading } = useWishlist(groupId);
  const dismiss = useDismissWishlist(groupId);
  const promote = usePromoteWishlist(groupId);
  const { open: openDrawer } = useDrawer();
  const [showForm, setShowForm] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);

  const items = data?.items ?? [];

  const handlePromote = async (wid: string) => {
    setPromoteError(null);
    try {
      const result = await promote.mutateAsync(wid);
      openDrawer({
        kind: "new-order",
        groupId,
        chemicalId: result.chemical_id,
        wishlistItemId: result.wishlist_item_id,
      });
    } catch (err) {
      const detail = (err as any).response?.data?.detail;
      setPromoteError(
        typeof detail === "object"
          ? detail.message
          : detail ?? "Could not resolve chemical via PubChem.",
      );
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" sx={{ mb: 2 }}>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={() => setShowForm(true)}
        >
          Add to wishlist
        </Button>
      </Stack>

      {promoteError && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setPromoteError(null)}>
          {promoteError}
        </Alert>
      )}

      {items.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          Wishlist empty.
        </Typography>
      )}

      <Stack gap={1}>
        {items.map((item) => (
          <Card key={item.id} variant="outlined">
            <CardContent>
              <Stack direction="row" alignItems="center" gap={1}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="subtitle2">
                    {item.chemical_name ??
                      `${item.freeform_name}${item.freeform_cas ? ` (${item.freeform_cas})` : ""}`}
                  </Typography>
                  {item.comment && (
                    <Typography variant="caption" color="text.secondary">
                      {item.comment}
                    </Typography>
                  )}
                </Box>
                <Button
                  size="small"
                  variant="outlined"
                  endIcon={<ArrowForwardIcon />}
                  onClick={() => handlePromote(item.id)}
                >
                  Promote
                </Button>
                <IconButton size="small" onClick={() => dismiss.mutate(item.id)}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>

      <WishlistForm
        open={showForm}
        groupId={groupId}
        onDone={() => setShowForm(false)}
      />
    </Box>
  );
}
```

- [ ] **Step 3: Build + smoke**

Run: `cd frontend && npm run build`. Add a wishlist freeform item; promote it; confirm the order form opens with the chemical pre-filled and wishlist row marked converted (re-check Wishlist tab — it should disappear).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/orders/WishlistList.tsx \
        frontend/src/components/orders/WishlistForm.tsx
git commit -m "feat(orders): wishlist list + add + promote + dismiss"
```

---

### Task 41: Add "Order more" + "On order" indicator on chemical detail

**Files:**
- Modify: the chemical detail surface (likely `frontend/src/components/ChemicalInfoBox.tsx` — locate the existing "Add container" button first)

- [ ] **Step 1: Locate the existing Add container button**

Use Grep with pattern `Add container` in `frontend/src/components/`. The result will pinpoint the file (most likely `ChemicalInfoBox.tsx` or similar). Open it and read enough surrounding context to mirror the styling and the variable that holds the chemical (e.g. `chemical`, `data`, etc.).

- [ ] **Step 2: Add an "Order more" button next to it**

Inside the same file, near the top of the component body:

```tsx
import { useDrawer } from "./drawer/DrawerContext";  // adjust if file lives elsewhere
import { useOrders } from "../api/hooks/useOrders";

// ...inside the component (rename `chemical` to whatever the existing variable is):
const { open: openDrawer } = useDrawer();
const openOrders = useOrders(groupId, { chemical_id: chemical.id, status: "ordered" });
const onOrderCount = (openOrders.data?.items ?? []).reduce(
  (sum, o) => sum + o.package_count, 0,
);
const nextArrival = (openOrders.data?.items ?? [])
  .map((o) => o.expected_arrival)
  .filter((d): d is string => Boolean(d))
  .sort()[0];
```

In the JSX next to the existing **Add container** button:

```tsx
<Button
  size="small"
  variant="outlined"
  onClick={() => openDrawer({ kind: "new-order", groupId, chemicalId: chemical.id })}
>
  Order more
</Button>
{onOrderCount > 0 && (
  <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
    On order: {onOrderCount} package{onOrderCount === 1 ? "" : "s"}
    {nextArrival ? `, expected ${nextArrival}` : ""}
  </Typography>
)}
```

If the chemical is archived (`chemical.is_archived`), additionally show a warning above the buttons (this is the spec's "warn-but-allow on archived chemical" behavior):

```tsx
{chemical.is_archived && (
  <Alert severity="warning" sx={{ mb: 1 }}>
    This chemical is archived. Ordering it does not auto-unarchive.
  </Alert>
)}
```

- [ ] **Step 3: Build + smoke-test**

Run: `cd frontend && npm run build`. Open a chemical that has open orders → "On order: 3 packages, expected 2026-04-30" should appear under the existing buttons.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ChemicalInfoBox.tsx  # or whichever file
git commit -m "feat(orders): 'Order more' button and 'On order' indicator on chemical detail"
```

---

## Phase 10 — Smoke test

### Task 42: End-to-end manual smoke checklist

No code change. Walk the full flow against a clean dev environment.

- [ ] **Step 1: Reset to a known state**

```bash
# (optional) blow away the local dev DB and re-seed
rm -f data/chaima.db   # adjust path if your local DB is elsewhere
uv run alembic upgrade head
uv run uvicorn chaima.app:app --reload &
cd frontend && npm run dev &
```

- [ ] **Step 2: Run the smoke list**

Tick each item only if it actually works:

- [ ] On a fresh group: navigate to `/settings → Projects` — see "General" pre-seeded.
- [ ] On a fresh group: navigate to `/settings → Suppliers` — see all 10 pre-seeded vendors.
- [ ] On a chemical's detail page, click **Order more** → form opens with chemical pre-filled.
- [ ] Pick `abcr` as supplier; pick `General` as project; enter `100` `mL` `× 3`, price `25` `EUR`. Submit. The order appears in `/orders` (Open tab).
- [ ] Click that order's card → drawer opens with full details.
- [ ] Click **Mark received** → dialog with 3 rows. Fill identifiers, pick a storage location for each, submit. Toast confirms 3 containers added.
- [ ] Order moves to Received tab. Three new containers appear under the chemical's storage view.
- [ ] Cancel an open order **as admin** — confirm modal appears, reason field works, order moves to Cancelled tab.
- [ ] Cancel an open order **as a non-admin** — verify the **Cancel** button is hidden.
- [ ] On `/orders → Wishlist`, add a freeform `acetone` (no chemical_id). Click **Promote** — order form opens; wishlist item is removed from the Wishlist tab.
- [ ] Place 3+ received orders for the same supplier with realistic ordered/received dates (use the DB shell to backdate `ordered_at` / `received_at` if needed). Open the order form, pick that supplier — verify the lead-time hint appears: "X usually takes A–B days for your group (N past orders)."
- [ ] On a chemical with a known PubChem CID (e.g. acetone, CID 180), open the order form and click "Show PubChem vendor list" → vendors load with external links. Click "Use as supplier" on a vendor whose name exactly matches a configured supplier → that supplier auto-fills.

If any item fails, file an issue, do not mark the task complete.

- [ ] **Step 3: Final commit**

If you made any small fixes during smoke testing, commit them with a `fix(orders): ...` message.

---

## Known v1 gaps (acceptable for shipping; flag in PR description)

The spec describes an **embedded chemical search inside the order form** that falls through to PubChem when no match exists, calling the existing `ChemicalForm` flow inline. This plan implements the simpler version: the order form requires `chemicalId` to be passed in. The two practical entry points covered for v1:

1. **From an existing chemical** — "Order more" button on the chemical detail page (Task 41) passes `chemicalId` directly.
2. **From the wishlist** — `promote_wishlist` (Task 22) resolves the chemical server-side (creating one via PubChem if freeform), so the order form opens with `chemicalId` pre-set.

The "+ New order" button on the Orders Open tab opens the form without a `chemicalId`, in which case the form shows a hint "(pick from chemicals page)" and the **Place order** button stays disabled. To start an order for a not-yet-cataloged chemical: add it via the existing Chemicals page first (which already has a PubChem search), then click "Order more". Add the embedded chemical search as a v1.1 follow-up if it becomes a friction point.

---

## Done

If every checkbox above is ticked, the feature is shippable. Open a single PR titled "feat(orders): chemical ordering & wishlist" and link the spec at `docs/superpowers/specs/2026-04-26-chemical-ordering-design.md`.

Suggested PR description structure:
- Summary (3 bullets)
- Screenshots (orders tab, order form with PubChem panel, receive dialog)
- Migration safety: data migration is idempotent (`INSERT … ON CONFLICT DO NOTHING` semantics) and only inserts; existing data is untouched
- Test plan: backend `pytest tests/test_services/test_orders.py tests/test_api/test_orders.py tests/test_services/test_wishlist.py tests/test_api/test_wishlist.py tests/test_api/test_projects.py tests/test_api/test_suppliers_lead_time.py tests/test_services/test_pubchem_vendors.py -v`; frontend manual smoke list above




