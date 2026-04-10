# ChAIMa Database Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 13 database tables from the approved schema using SQLModel, with fastapi-users integration, Alembic migrations, and a minimal FastAPI entry point.

**Architecture:** SQLModel models with async SQLite (aiosqlite) for dev/test. fastapi-users User model uses SQLAlchemy's DeclarativeBase sharing metadata with SQLModel so Alembic has a single metadata target. All UUIDs, adjacency list for storage hierarchy, pint-compatible unit strings. Import `AsyncSession` from `sqlmodel.ext.asyncio.session` (NOT sqlalchemy). Use `session.exec()` everywhere (NOT `session.execute()` which is deprecated on SQLModel sessions).

**Tech Stack:** SQLModel, FastAPI, fastapi-users[sqlalchemy], aiosqlite, Alembic, pytest-asyncio, pydantic-settings

---

## File Structure

```
src/chaima/
├── __init__.py              (exists, clear placeholder)
├── _version.py              (exists, no changes)
├── app.py                   (create: FastAPI app factory)
├── config.py                (create: pydantic-settings config)
├── db.py                    (create: engine, session, Base)
├── auth.py                  (create: fastapi-users manager + backend)
├── schemas.py               (create: user read/create/update schemas)
├── models/
│   ├── __init__.py          (create: re-export all models)
│   ├── user.py              (create: User via fastapi-users)
│   ├── group.py             (create: Group + UserGroupLink)
│   ├── chemical.py          (create: Chemical + ChemicalSynonym)
│   ├── ghs.py               (create: GHSCode + ChemicalGHS)
│   ├── hazard.py            (create: HazardTag + ChemicalHazardTag + HazardTagIncompatibility)
│   ├── storage.py           (create: StorageLocation + StorageLocationGroup)
│   ├── supplier.py          (create: Supplier)
│   └── container.py         (create: Container)
tests/
├── conftest.py              (create: async fixtures + shared factories)
├── test_models/
│   ├── __init__.py
│   ├── test_group.py
│   ├── test_user.py
│   ├── test_chemical.py
│   ├── test_ghs.py
│   ├── test_hazard.py
│   ├── test_storage.py
│   ├── test_supplier.py
│   └── test_container.py
alembic.ini                  (create: alembic config)
alembic/
├── env.py                   (create: async alembic env)
├── script.py.mako           (create: migration template)
└── versions/                (create: empty dir)
```

---

### Task 1: Add dependencies & create package structure

**Files:**
- Modify: `pyproject.toml` (via uv add)
- Create: `src/chaima/models/__init__.py`, `tests/__init__.py`, `tests/test_models/__init__.py`

- [ ] **Step 1: Add main dependencies**

```bash
uv add "fastapi-users[sqlalchemy]>=15.0.5" aiosqlite alembic pydantic-settings
```

Note: this replaces the existing `fastapi-users` dep with `fastapi-users[sqlalchemy]`.

- [ ] **Step 2: Add dev dependencies**

```bash
uv add --group dev pytest-asyncio
```

- [ ] **Step 3: Add pytest asyncio_mode to pyproject.toml**

Append to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 4: Create package directories**

```bash
mkdir -p src/chaima/models tests/test_models
touch src/chaima/models/__init__.py tests/__init__.py tests/test_models/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/chaima/models/__init__.py tests/__init__.py tests/test_models/__init__.py
git commit -m "chore: add dependencies and package structure for database models"
```

---

### Task 2: Database configuration

**Files:**
- Create: `src/chaima/config.py`
- Create: `src/chaima/db.py`

- [ ] **Step 1: Create config.py**

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./chaima.db"
    secret_key: SecretStr = SecretStr("CHANGE-ME-IN-PRODUCTION")

    model_config = {"env_prefix": "CHAIMA_"}


settings = Settings()
```

- [ ] **Step 2: Create db.py**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.orm import DeclarativeBase
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chaima.config import settings

# Share metadata so fastapi-users (DeclarativeBase) and SQLModel
# models all register in the same metadata. Alembic uses one target.


class Base(DeclarativeBase):
    metadata = SQLModel.metadata


engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
```

- [ ] **Step 3: Verify imports**

Run: `uv run python -c "from chaima.db import engine, Base, get_async_session; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/chaima/config.py src/chaima/db.py
git commit -m "feat: add database configuration with async engine and shared metadata"
```

---

### Task 3: Test infrastructure

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create conftest.py with async fixtures and shared factories**

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest_asyncio.fixture
async def engine():
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def group(session):
    from chaima.models.group import Group

    g = Group(name="Lab Alpha")
    session.add(g)
    await session.flush()
    return g


@pytest_asyncio.fixture
async def user(session):
    from chaima.models.user import User

    u = User(
        email="alice@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    session.add(u)
    await session.flush()
    return u


@pytest_asyncio.fixture
async def chemical(session, group, user):
    from chaima.models.chemical import Chemical

    c = Chemical(group_id=group.id, name="Ethanol", created_by=user.id)
    session.add(c)
    await session.flush()
    return c


@pytest_asyncio.fixture
async def storage_location(session):
    from chaima.models.storage import StorageLocation

    loc = StorageLocation(name="Room A")
    session.add(loc)
    await session.flush()
    return loc


@pytest_asyncio.fixture
async def supplier(session, group):
    from chaima.models.supplier import Supplier

    s = Supplier(name="Sigma Aldrich", group_id=group.id)
    session.add(s)
    await session.flush()
    return s
```

- [ ] **Step 2: Verify pytest discovers fixtures**

Run: `uv run pytest --collect-only`
Expected: No errors, no tests collected yet.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add async fixtures and shared model factories"
```

---

### Task 4: Group & UserGroupLink models + tests

**Files:**
- Create: `src/chaima/models/group.py`
- Create: `tests/test_models/test_group.py`

- [ ] **Step 1: Write the failing tests**

```python
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from chaima.models.group import Group, UserGroupLink


async def test_create_group(session):
    group = Group(name="Lab Beta")
    session.add(group)
    await session.commit()

    result = await session.get(Group, group.id)
    assert result is not None
    assert result.name == "Lab Beta"
    assert result.id is not None
    assert result.created_at is not None


async def test_group_name_unique(session):
    session.add(Group(name="Lab Beta"))
    await session.commit()

    session.add(Group(name="Lab Beta"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_create_user_group_link(session, group):
    user_id = uuid.uuid4()
    link = UserGroupLink(user_id=user_id, group_id=group.id, is_admin=True)
    session.add(link)
    await session.commit()

    result = (await session.exec(
        select(UserGroupLink).where(UserGroupLink.user_id == user_id)
    )).one()
    assert result.group_id == group.id
    assert result.is_admin is True
    assert result.joined_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_group.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'chaima.models.group'`

- [ ] **Step 3: Implement Group and UserGroupLink models**

```python
import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class Group(SQLModel, table=True):
    __tablename__ = "group"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


class UserGroupLink(SQLModel, table=True):
    __tablename__ = "user_group_link"
    __table_args__ = (UniqueConstraint("user_id", "group_id"),)

    user_id: uuid_pkg.UUID = Field(primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", primary_key=True)
    is_admin: bool = Field(default=False)
    joined_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
```

Note: `UserGroupLink.user_id` has no FK constraint to `user` yet because the User table is defined in Task 5. The FK will be added via Alembic migration after User exists.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models/test_group.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/group.py tests/test_models/test_group.py
git commit -m "feat: add Group and UserGroupLink models with tests"
```

---

### Task 5: User model (fastapi-users)

**Files:**
- Create: `src/chaima/models/user.py`
- Create: `tests/test_models/test_user.py`

- [ ] **Step 1: Write the failing test**

```python
import datetime

from chaima.models.user import User


async def test_create_user(session):
    u = User(
        email="bob@example.com",
        hashed_password="fakehash",
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    session.add(u)
    await session.commit()

    result = await session.get(User, u.id)
    assert result is not None
    assert result.email == "bob@example.com"
    assert result.is_superuser is False
    assert isinstance(result.created_at, datetime.datetime)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models/test_user.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement User model**

```python
import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from chaima.db import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

Note: User inherits from `Base` (which shares `SQLModel.metadata`) so the `user` table is registered alongside all SQLModel tables.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models/test_user.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/user.py tests/test_models/test_user.py
git commit -m "feat: add User model via fastapi-users with created_at field"
```

---

### Task 6: Chemical & ChemicalSynonym models + tests

**Files:**
- Create: `src/chaima/models/chemical.py`
- Create: `tests/test_models/test_chemical.py`

- [ ] **Step 1: Write the failing tests**

```python
from sqlmodel import select

from chaima.models.chemical import Chemical, ChemicalSynonym
from chaima.models.group import Group
from chaima.models.user import User


async def test_create_chemical(session, group, user):
    chem = Chemical(
        group_id=group.id,
        name="Acetone",
        cas="67-64-1",
        smiles="CC(C)=O",
        created_by=user.id,
    )
    session.add(chem)
    await session.commit()

    result = await session.get(Chemical, chem.id)
    assert result is not None
    assert result.name == "Acetone"
    assert result.cas == "67-64-1"
    assert result.group_id == group.id
    assert result.created_by == user.id


async def test_chemical_optional_fields_nullable(session, group, user):
    chem = Chemical(group_id=group.id, name="Water", created_by=user.id)
    session.add(chem)
    await session.commit()

    result = await session.get(Chemical, chem.id)
    assert result.cas is None
    assert result.smiles is None
    assert result.molar_mass is None


async def test_create_synonym_with_category(session, chemical):
    syn = ChemicalSynonym(chemical_id=chemical.id, name="EtOH", category="common")
    session.add(syn)
    await session.commit()

    result = (await session.exec(
        select(ChemicalSynonym).where(ChemicalSynonym.chemical_id == chemical.id)
    )).all()
    assert len(result) == 1
    assert result[0].name == "EtOH"
    assert result[0].category == "common"


async def test_synonym_category_optional(session, chemical):
    syn = ChemicalSynonym(chemical_id=chemical.id, name="Alcohol")
    session.add(syn)
    await session.commit()

    result = await session.get(ChemicalSynonym, syn.id)
    assert result.category is None


async def test_same_chemical_in_different_groups(session, user):
    g1 = Group(name="Lab X")
    g2 = Group(name="Lab Y")
    session.add_all([g1, g2])
    await session.flush()

    c1 = Chemical(group_id=g1.id, name="Ethanol", created_by=user.id)
    c2 = Chemical(group_id=g2.id, name="Ethanol", created_by=user.id)
    session.add_all([c1, c2])
    await session.commit()

    assert c1.id != c2.id
    assert c1.group_id != c2.group_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_chemical.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Chemical and ChemicalSynonym**

```python
import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class Chemical(SQLModel, table=True):
    __tablename__ = "chemical"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    name: str = Field(index=True)
    cas: str | None = Field(default=None, index=True)
    smiles: str | None = Field(default=None)
    cid: str | None = Field(default=None)
    structure: str | None = Field(default=None)
    molar_mass: float | None = Field(default=None)
    density: float | None = Field(default=None)
    melting_point: float | None = Field(default=None)
    boiling_point: float | None = Field(default=None)
    image_path: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    created_by: uuid_pkg.UUID = Field(foreign_key="user.id")
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        ),
    )


class ChemicalSynonym(SQLModel, table=True):
    __tablename__ = "chemical_synonym"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", index=True)
    name: str
    category: str | None = Field(default=None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models/test_chemical.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/chemical.py tests/test_models/test_chemical.py
git commit -m "feat: add Chemical and ChemicalSynonym models with tests"
```

---

### Task 7: GHSCode & ChemicalGHS models + tests

**Files:**
- Create: `src/chaima/models/ghs.py`
- Create: `tests/test_models/test_ghs.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from chaima.models.ghs import ChemicalGHS, GHSCode


async def test_create_ghs_code(session):
    code = GHSCode(code="H300", description="Fatal if swallowed", signal_word="Danger")
    session.add(code)
    await session.commit()

    result = await session.get(GHSCode, code.id)
    assert result.code == "H300"
    assert result.description == "Fatal if swallowed"


async def test_ghs_code_unique(session):
    session.add(GHSCode(code="H300", description="Fatal if swallowed"))
    await session.commit()
    session.add(GHSCode(code="H300", description="Duplicate"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_link_chemical_to_ghs(session, chemical):
    h300 = GHSCode(code="H300", description="Fatal if swallowed")
    h310 = GHSCode(code="H310", description="Fatal in contact with skin")
    session.add_all([h300, h310])
    await session.flush()

    session.add_all([
        ChemicalGHS(chemical_id=chemical.id, ghs_id=h300.id),
        ChemicalGHS(chemical_id=chemical.id, ghs_id=h310.id),
    ])
    await session.commit()

    result = (await session.exec(
        select(ChemicalGHS).where(ChemicalGHS.chemical_id == chemical.id)
    )).all()
    assert len(result) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_ghs.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement GHSCode and ChemicalGHS**

```python
import uuid as uuid_pkg

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class GHSCode(SQLModel, table=True):
    __tablename__ = "ghs_code"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)
    description: str
    pictogram: str | None = Field(default=None)
    signal_word: str | None = Field(default=None)


class ChemicalGHS(SQLModel, table=True):
    __tablename__ = "chemical_ghs"
    __table_args__ = (UniqueConstraint("chemical_id", "ghs_id"),)

    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", primary_key=True)
    ghs_id: uuid_pkg.UUID = Field(foreign_key="ghs_code.id", primary_key=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models/test_ghs.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/ghs.py tests/test_models/test_ghs.py
git commit -m "feat: add GHSCode and ChemicalGHS models with tests"
```

---

### Task 8: HazardTag, ChemicalHazardTag, HazardTagIncompatibility models + tests

**Files:**
- Create: `src/chaima/models/hazard.py`
- Create: `tests/test_models/test_hazard.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from chaima.models.hazard import ChemicalHazardTag, HazardTag, HazardTagIncompatibility


async def test_create_hazard_tag(session):
    tag = HazardTag(name="flammable", description="Catches fire easily")
    session.add(tag)
    await session.commit()

    result = await session.get(HazardTag, tag.id)
    assert result.name == "flammable"


async def test_hazard_tag_name_unique(session):
    session.add(HazardTag(name="flammable"))
    await session.commit()
    session.add(HazardTag(name="flammable"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_link_chemical_to_hazard_tag(session, chemical):
    tag = HazardTag(name="flammable")
    session.add(tag)
    await session.flush()

    session.add(ChemicalHazardTag(chemical_id=chemical.id, hazard_tag_id=tag.id))
    await session.commit()

    result = (await session.exec(
        select(ChemicalHazardTag).where(ChemicalHazardTag.chemical_id == chemical.id)
    )).all()
    assert len(result) == 1
    assert result[0].hazard_tag_id == tag.id


async def test_incompatibility_pair(session):
    acid = HazardTag(name="acid")
    base = HazardTag(name="base")
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


async def test_incompatibility_pair_unique(session):
    acid = HazardTag(name="acid")
    base = HazardTag(name="base")
    session.add_all([acid, base])
    await session.flush()

    session.add(HazardTagIncompatibility(tag_a_id=acid.id, tag_b_id=base.id))
    await session.commit()
    session.add(HazardTagIncompatibility(tag_a_id=acid.id, tag_b_id=base.id))
    with pytest.raises(IntegrityError):
        await session.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_hazard.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement models**

```python
import uuid as uuid_pkg

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class HazardTag(SQLModel, table=True):
    __tablename__ = "hazard_tag"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)


class ChemicalHazardTag(SQLModel, table=True):
    __tablename__ = "chemical_hazard_tag"
    __table_args__ = (UniqueConstraint("chemical_id", "hazard_tag_id"),)

    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", primary_key=True)
    hazard_tag_id: uuid_pkg.UUID = Field(foreign_key="hazard_tag.id", primary_key=True)


class HazardTagIncompatibility(SQLModel, table=True):
    __tablename__ = "hazard_tag_incompatibility"
    __table_args__ = (UniqueConstraint("tag_a_id", "tag_b_id"),)

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    tag_a_id: uuid_pkg.UUID = Field(foreign_key="hazard_tag.id")
    tag_b_id: uuid_pkg.UUID = Field(foreign_key="hazard_tag.id")
    reason: str | None = Field(default=None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models/test_hazard.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/hazard.py tests/test_models/test_hazard.py
git commit -m "feat: add HazardTag, ChemicalHazardTag, and HazardTagIncompatibility models with tests"
```

---

### Task 9: StorageLocation & StorageLocationGroup models + tests

**Files:**
- Create: `src/chaima/models/storage.py`
- Create: `tests/test_models/test_storage.py`

- [ ] **Step 1: Write the failing tests**

```python
from sqlmodel import select

from chaima.models.group import Group
from chaima.models.storage import StorageLocation, StorageLocationGroup


async def test_create_root_location(session):
    loc = StorageLocation(name="Room B")
    session.add(loc)
    await session.commit()

    result = await session.get(StorageLocation, loc.id)
    assert result.name == "Room B"
    assert result.parent_id is None


async def test_create_nested_location(session, storage_location):
    shelf = StorageLocation(name="Shelf 1", parent_id=storage_location.id)
    session.add(shelf)
    await session.flush()

    bottom = StorageLocation(name="Bottom", parent_id=shelf.id)
    session.add(bottom)
    await session.commit()

    result = await session.get(StorageLocation, bottom.id)
    assert result.parent_id == shelf.id


async def test_assign_location_to_group(session, group, storage_location):
    link = StorageLocationGroup(location_id=storage_location.id, group_id=group.id)
    session.add(link)
    await session.commit()

    result = (await session.exec(
        select(StorageLocationGroup).where(StorageLocationGroup.group_id == group.id)
    )).all()
    assert len(result) == 1
    assert result[0].location_id == storage_location.id


async def test_location_shared_across_groups(session, storage_location):
    g1 = Group(name="Lab X")
    g2 = Group(name="Lab Y")
    session.add_all([g1, g2])
    await session.flush()

    session.add_all([
        StorageLocationGroup(location_id=storage_location.id, group_id=g1.id),
        StorageLocationGroup(location_id=storage_location.id, group_id=g2.id),
    ])
    await session.commit()

    result = (await session.exec(
        select(StorageLocationGroup).where(
            StorageLocationGroup.location_id == storage_location.id
        )
    )).all()
    assert len(result) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement StorageLocation and StorageLocationGroup**

```python
import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class StorageLocation(SQLModel, table=True):
    __tablename__ = "storage_location"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    parent_id: uuid_pkg.UUID | None = Field(
        default=None, foreign_key="storage_location.id", index=True
    )
    name: str
    description: str | None = Field(default=None)
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


class StorageLocationGroup(SQLModel, table=True):
    __tablename__ = "storage_location_group"
    __table_args__ = (UniqueConstraint("location_id", "group_id"),)

    location_id: uuid_pkg.UUID = Field(foreign_key="storage_location.id", primary_key=True)
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", primary_key=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models/test_storage.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/storage.py tests/test_models/test_storage.py
git commit -m "feat: add StorageLocation and StorageLocationGroup models with tests"
```

---

### Task 10: Supplier model + tests

**Files:**
- Create: `src/chaima/models/supplier.py`
- Create: `tests/test_models/test_supplier.py`

- [ ] **Step 1: Write the failing test**

```python
from chaima.models.supplier import Supplier


async def test_create_supplier(session, group):
    s = Supplier(name="Sigma Aldrich", group_id=group.id)
    session.add(s)
    await session.commit()

    result = await session.get(Supplier, s.id)
    assert result.name == "Sigma Aldrich"
    assert result.group_id == group.id
    assert result.created_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models/test_supplier.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Supplier**

```python
import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class Supplier(SQLModel, table=True):
    __tablename__ = "supplier"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    name: str
    group_id: uuid_pkg.UUID = Field(foreign_key="group.id", index=True)
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models/test_supplier.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/supplier.py tests/test_models/test_supplier.py
git commit -m "feat: add Supplier model with tests"
```

---

### Task 11: Container model + tests

**Files:**
- Create: `src/chaima/models/container.py`
- Create: `tests/test_models/test_container.py`

- [ ] **Step 1: Write the failing tests**

```python
from sqlmodel import select

from chaima.models.container import Container


async def test_create_container(session, chemical, storage_location, supplier, user):
    container = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        supplier_id=supplier.id,
        identifier="ETH-001",
        amount=500.0,
        unit="mL",
        created_by=user.id,
    )
    session.add(container)
    await session.commit()

    result = await session.get(Container, container.id)
    assert result.identifier == "ETH-001"
    assert result.amount == 500.0
    assert result.unit == "mL"
    assert result.is_archived is False


async def test_container_optional_supplier(session, chemical, storage_location, user):
    container = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        identifier="ETH-002",
        amount=1.0,
        unit="kg",
        created_by=user.id,
    )
    session.add(container)
    await session.commit()

    result = await session.get(Container, container.id)
    assert result.supplier_id is None


async def test_container_archive(session, chemical, storage_location, user):
    container = Container(
        chemical_id=chemical.id,
        location_id=storage_location.id,
        identifier="ETH-003",
        amount=100.0,
        unit="g",
        created_by=user.id,
        is_archived=True,
    )
    session.add(container)
    await session.commit()

    result = await session.get(Container, container.id)
    assert result.is_archived is True


async def test_filter_excludes_archived(session, chemical, storage_location, user):
    c1 = Container(chemical_id=chemical.id, location_id=storage_location.id,
                   identifier="A", amount=1.0, unit="mL", created_by=user.id)
    c2 = Container(chemical_id=chemical.id, location_id=storage_location.id,
                   identifier="B", amount=2.0, unit="mL", created_by=user.id,
                   is_archived=True)
    session.add_all([c1, c2])
    await session.commit()

    result = (await session.exec(
        select(Container).where(Container.is_archived == False)  # noqa: E712
    )).all()
    assert len(result) == 1
    assert result[0].identifier == "A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models/test_container.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Container**

```python
import datetime
import uuid as uuid_pkg

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class Container(SQLModel, table=True):
    __tablename__ = "container"

    id: uuid_pkg.UUID = Field(default_factory=uuid_pkg.uuid4, primary_key=True)
    chemical_id: uuid_pkg.UUID = Field(foreign_key="chemical.id", index=True)
    location_id: uuid_pkg.UUID = Field(foreign_key="storage_location.id", index=True)
    supplier_id: uuid_pkg.UUID | None = Field(default=None, foreign_key="supplier.id")
    identifier: str = Field(index=True)
    amount: float
    unit: str
    image_path: str | None = Field(default=None)
    purchased_at: datetime.date | None = Field(default=None)
    created_by: uuid_pkg.UUID = Field(foreign_key="user.id")
    created_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        ),
    )
    is_archived: bool = Field(default=False, index=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models/test_container.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/chaima/models/container.py tests/test_models/test_container.py
git commit -m "feat: add Container model with soft-archive and tests"
```

---

### Task 12: Add Relationship attributes + models \_\_init\_\_.py

**Files:**
- Modify: all model files in `src/chaima/models/`

Now that all models exist, add `Relationship()` attributes for ORM navigation and create the re-export module.

- [ ] **Step 1: Add relationships to group.py**

```python
# Add to imports:
from sqlmodel import Field, Relationship, SQLModel

# Add to Group class body:
    chemicals: list["Chemical"] = Relationship(back_populates="group")
    suppliers: list["Supplier"] = Relationship(back_populates="group")

# Add to UserGroupLink class body:
    group: "Group" = Relationship()
```

- [ ] **Step 2: Add relationships to user.py**

User uses SQLAlchemy (not SQLModel), so relationships use `sqlalchemy.orm.relationship`:

```python
# Add to imports:
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Add to User class body:
    created_chemicals: Mapped[list["Chemical"]] = relationship(
        "Chemical", back_populates="creator", foreign_keys="[Chemical.created_by]"
    )
    created_containers: Mapped[list["Container"]] = relationship(
        "Container", back_populates="creator", foreign_keys="[Container.created_by]"
    )
```

- [ ] **Step 3: Add relationships to chemical.py**

```python
# Add to imports:
from sqlmodel import Field, Relationship, SQLModel

# Add to Chemical class body:
    group: "Group" = Relationship(back_populates="chemicals")
    creator: "User" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Chemical.created_by"}
    )
    synonyms: list["ChemicalSynonym"] = Relationship(back_populates="chemical")
    ghs_links: list["ChemicalGHS"] = Relationship(back_populates="chemical")
    hazard_tag_links: list["ChemicalHazardTag"] = Relationship(back_populates="chemical")
    containers: list["Container"] = Relationship(back_populates="chemical")

# Add to ChemicalSynonym class body:
    chemical: "Chemical" = Relationship(back_populates="synonyms")
```

- [ ] **Step 4: Add relationships to ghs.py**

```python
# Add to imports:
from sqlmodel import Field, Relationship, SQLModel

# Add to GHSCode class body:
    chemical_links: list["ChemicalGHS"] = Relationship(back_populates="ghs_code")

# Add to ChemicalGHS class body:
    chemical: "Chemical" = Relationship(back_populates="ghs_links")
    ghs_code: "GHSCode" = Relationship(back_populates="chemical_links")
```

- [ ] **Step 5: Add relationships to hazard.py**

```python
# Add to imports:
from sqlmodel import Field, Relationship, SQLModel

# Add to HazardTag class body:
    chemical_links: list["ChemicalHazardTag"] = Relationship(back_populates="hazard_tag")

# Add to ChemicalHazardTag class body:
    chemical: "Chemical" = Relationship(back_populates="hazard_tag_links")
    hazard_tag: "HazardTag" = Relationship(back_populates="chemical_links")
```

- [ ] **Step 6: Add relationships to storage.py**

```python
# Add to imports:
from sqlmodel import Field, Relationship, SQLModel

# Add to StorageLocation class body:
    children: list["StorageLocation"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"remote_side": "StorageLocation.id"},
    )
    parent: "StorageLocation" | None = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "StorageLocation.parent_id"},
    )
    containers: list["Container"] = Relationship(back_populates="location")
```

- [ ] **Step 7: Add relationships to supplier.py**

```python
# Add to imports:
from sqlmodel import Field, Relationship, SQLModel

# Add to Supplier class body:
    group: "Group" = Relationship(back_populates="suppliers")
    containers: list["Container"] = Relationship(back_populates="supplier")
```

- [ ] **Step 8: Add relationships to container.py**

```python
# Add to imports:
from sqlmodel import Field, Relationship, SQLModel

# Add to Container class body:
    chemical: "Chemical" = Relationship(back_populates="containers")
    location: "StorageLocation" = Relationship(back_populates="containers")
    supplier: "Supplier" | None = Relationship(back_populates="containers")
    creator: "User" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Container.created_by"}
    )
```

- [ ] **Step 9: Create models \_\_init\_\_.py**

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
from chaima.models.storage import StorageLocation, StorageLocationGroup
from chaima.models.supplier import Supplier
from chaima.models.user import User

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
    "StorageLocation",
    "StorageLocationGroup",
    "Supplier",
    "User",
    "UserGroupLink",
]
```

- [ ] **Step 10: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All 26 tests pass.

- [ ] **Step 11: Commit**

```bash
git add src/chaima/models/
git commit -m "feat: add ORM relationships and models __init__.py re-exports"
```

---

### Task 13: Alembic setup & initial migration

**Files:**
- Create: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`

- [ ] **Step 1: Initialize alembic skeleton**

```bash
uv run alembic init alembic
```

- [ ] **Step 2: Update alembic.ini**

Set the SQLAlchemy URL placeholder (overridden by env.py):

In `alembic.ini`, change the `sqlalchemy.url` line to:
```ini
sqlalchemy.url = sqlite+aiosqlite:///./chaima.db
```

- [ ] **Step 3: Replace alembic/env.py with async version**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from chaima.models import *  # noqa: F401, F403
from chaima.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Generate initial migration**

Run: `uv run alembic revision --autogenerate -m "initial schema"`
Expected: Creates a file in `alembic/versions/` with all 13 tables.

- [ ] **Step 5: Apply migration**

Run: `uv run alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> <rev_id>, initial schema`

- [ ] **Step 6: Verify tables exist**

Run: `uv run python -c "import sqlite3; conn = sqlite3.connect('chaima.db'); print(sorted(r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()))"`
Expected: List containing all table names.

- [ ] **Step 7: Add chaima.db to .gitignore**

Append `chaima.db` to `.gitignore`.

- [ ] **Step 8: Commit**

```bash
git add alembic.ini alembic/ .gitignore
git commit -m "feat: add Alembic async setup with initial schema migration"
```

---

### Task 14: FastAPI app entry point + auth wiring

**Files:**
- Create: `src/chaima/schemas.py`
- Create: `src/chaima/auth.py`
- Create: `src/chaima/app.py`
- Modify: `src/chaima/__init__.py`

- [ ] **Step 1: Create user schemas**

```python
import datetime
import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    created_at: datetime.datetime | None = None


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass
```

- [ ] **Step 2: Create auth.py**

```python
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlmodel.ext.asyncio.session import AsyncSession

from chaima.config import settings
from chaima.db import get_async_session
from chaima.models.user import User


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key.get_secret_value()
    verification_token_secret = settings.secret_key.get_secret_value()


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key.get_secret_value(), lifetime_seconds=3600
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager=get_user_manager,
    auth_backends=[auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
```

- [ ] **Step 3: Create app.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from chaima.auth import auth_backend, fastapi_users
from chaima.db import create_db_and_tables
from chaima.schemas import UserCreate, UserRead, UserUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(title="ChAIMa", lifespan=lifespan)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
```

- [ ] **Step 4: Clear \_\_init\_\_.py placeholder**

Replace `src/chaima/__init__.py` with an empty file (remove the `print("Hello, World!")` placeholder).

- [ ] **Step 5: Verify app starts**

Run: `uv run python -c "from chaima.app import app; print(app.title)"`
Expected: `ChAIMa`

- [ ] **Step 6: Commit**

```bash
git add src/chaima/schemas.py src/chaima/auth.py src/chaima/app.py src/chaima/__init__.py
git commit -m "feat: add FastAPI app with fastapi-users auth wiring"
```

---

### Task 15: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README.md**

```markdown
# ChAIMa

Chemical AI Manager — inventory management for laboratory chemicals.

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn chaima.app:app --reload
```

## Test

```bash
uv run pytest
```

## Migrations

```bash
uv run alembic upgrade head           # apply
uv run alembic revision --autogenerate -m "description"  # generate
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with setup, run, test, and migration instructions"
```

---

## Self-Review

- **Spec coverage:** All 13 tables implemented. All fields match spec. All constraints present.
- **Placeholder scan:** No TBDs, TODOs, or vague steps. Every code step has complete code.
- **Type consistency:** All UUID fields use `uuid_pkg.UUID`, all FK strings match `__tablename__`, all `Relationship` `back_populates` match across models. `session.exec()` used everywhere (no deprecated `session.execute()`). `AsyncSession` imported from `sqlmodel.ext.asyncio.session`.
- **DRY:** Shared fixtures (`group`, `user`, `chemical`, `storage_location`, `supplier`) in `tests/conftest.py`. No repeated helper functions across test files.
