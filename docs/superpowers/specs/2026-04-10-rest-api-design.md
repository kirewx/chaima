# ChAIMa REST API Design

**Date:** 2026-04-10
**Status:** Approved
**Approach:** Router + Service layer with Annotated DI

## Overview

REST API for ChAIMa, a multi-tenant chemical inventory management system. Consumed by a React SPA. Built on FastAPI + SQLModel + fastapi-users with cookie-based authentication.

### Key decisions

- **Cookie auth** (httpOnly) — simplest for same-origin SPA, no token management in JS
- **Group in URL path** — `/api/v1/groups/{gid}/...` for all group-scoped resources. Fully stateless, no server-side session state.
- **Max 3 levels of nesting** — e.g. `/api/v1/groups/{gid}/chemicals/{cid}/containers`
- **Offset/limit pagination** — wrapped response with metadata
- **API version prefix** — `/api/v1/...`
- **Sub-resource endpoints** for M:N relationships (synonyms, GHS codes, hazard tags) with bulk PUT replace
- **Soft delete** for containers via `DELETE` (sets `is_archived=True`), restore via `PATCH`

## Project Structure

```
src/chaima/
├── app.py                    # FastAPI app factory
├── dependencies.py           # Shared DI: session, auth, group access
├── schemas/
│   ├── pagination.py         # PaginatedResponse[T] generic wrapper
│   ├── chemical.py
│   ├── container.py
│   ├── ghs.py
│   ├── hazard.py
│   ├── storage.py
│   ├── supplier.py
│   ├── group.py
│   └── user.py
├── routers/
│   ├── chemicals.py
│   ├── containers.py
│   ├── ghs.py
│   ├── hazard_tags.py
│   ├── storage_locations.py
│   ├── suppliers.py
│   └── groups.py
├── services/
│   ├── chemicals.py
│   ├── containers.py
│   ├── ghs.py
│   ├── hazard_tags.py
│   ├── storage_locations.py
│   └── suppliers.py
├── models/                   # (existing)
├── config.py                 # (existing)
└── db.py                     # (existing)
```

## Dependency Injection

Shared annotated types in `dependencies.py`:

```python
from typing import Annotated

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
GroupMemberDep = Annotated[tuple[Group, UserGroupLink], Depends(get_group_member)]
GroupAdminDep = Annotated[tuple[Group, UserGroupLink], Depends(get_group_admin)]
```

### DI functions

- `get_session` — yields an `AsyncSession`
- `get_current_user` — returns authenticated user via fastapi-users, 401 if not logged in
- `get_group_member` — takes `group_id` from path, verifies user belongs to group. Returns `(Group, UserGroupLink)`. 404 if group not found, 403 if not a member.
- `get_group_admin` — chains on `get_group_member`, verifies `is_admin=True`. 403 if not admin.

## Pagination

Generic wrapper for all list endpoints:

```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int
```

All list endpoints accept `offset` (default 0, min 0) and `limit` (default 20, min 1, max 100).

## Endpoint Map

### Auth (fastapi-users managed)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Cookie login |
| POST | `/api/v1/auth/logout` | Cookie logout |
| POST | `/api/v1/auth/register` | Register new user |
| GET | `/api/v1/users/me` | Current user profile |
| PATCH | `/api/v1/users/me` | Update own profile |

### Groups

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/groups` | List groups the current user belongs to |
| POST | `/api/v1/groups` | Create a new group |
| GET | `/api/v1/groups/{gid}` | Get group details |
| PATCH | `/api/v1/groups/{gid}` | Update group (admin) |
| POST | `/api/v1/groups/{gid}/members` | Add member (admin) |
| DELETE | `/api/v1/groups/{gid}/members/{uid}` | Remove member (admin) |
| PATCH | `/api/v1/groups/{gid}/members/{uid}` | Update member role (admin) |

### Chemicals

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/groups/{gid}/chemicals` | List chemicals (paginated, filterable) |
| POST | `/api/v1/groups/{gid}/chemicals` | Create chemical |
| GET | `/api/v1/groups/{gid}/chemicals/{cid}` | Get chemical detail (includes synonyms, GHS, hazard tags) |
| PATCH | `/api/v1/groups/{gid}/chemicals/{cid}` | Update chemical scalar fields |
| DELETE | `/api/v1/groups/{gid}/chemicals/{cid}` | Delete chemical |

### Chemical sub-resources (bulk replace)

| Method | Path | Description |
|--------|------|-------------|
| PUT | `/api/v1/groups/{gid}/chemicals/{cid}/synonyms` | Replace all synonyms |
| PUT | `/api/v1/groups/{gid}/chemicals/{cid}/ghs-codes` | Replace GHS code assignments |
| PUT | `/api/v1/groups/{gid}/chemicals/{cid}/hazard-tags` | Replace hazard tag assignments (same-group validated) |

### Containers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/groups/{gid}/chemicals/{cid}/containers` | List containers for a chemical |
| GET | `/api/v1/groups/{gid}/containers` | List all containers in group (filterable) |
| POST | `/api/v1/groups/{gid}/chemicals/{cid}/containers` | Create container |
| GET | `/api/v1/groups/{gid}/containers/{cid}` | Get container detail |
| PATCH | `/api/v1/groups/{gid}/containers/{cid}` | Update container (incl. unarchive via `is_archived: false`) |
| DELETE | `/api/v1/groups/{gid}/containers/{cid}` | Archive container (soft delete, sets `is_archived=True`) |

### Suppliers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/groups/{gid}/suppliers` | List suppliers |
| POST | `/api/v1/groups/{gid}/suppliers` | Create supplier |
| GET | `/api/v1/groups/{gid}/suppliers/{sid}` | Get supplier |
| PATCH | `/api/v1/groups/{gid}/suppliers/{sid}` | Update supplier |
| DELETE | `/api/v1/groups/{gid}/suppliers/{sid}` | Delete supplier |

### Storage Locations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/groups/{gid}/storage-locations` | Get full tree (nested JSON) |
| POST | `/api/v1/groups/{gid}/storage-locations` | Create location |
| GET | `/api/v1/groups/{gid}/storage-locations/{lid}` | Get location detail |
| PATCH | `/api/v1/groups/{gid}/storage-locations/{lid}` | Update location (rename, reparent) |
| DELETE | `/api/v1/groups/{gid}/storage-locations/{lid}` | Delete location (only if no containers) |

### Hazard Tags

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/groups/{gid}/hazard-tags` | List hazard tags |
| POST | `/api/v1/groups/{gid}/hazard-tags` | Create hazard tag |
| PATCH | `/api/v1/groups/{gid}/hazard-tags/{tid}` | Update hazard tag |
| DELETE | `/api/v1/groups/{gid}/hazard-tags/{tid}` | Delete hazard tag |
| GET | `/api/v1/groups/{gid}/hazard-tags/incompatibilities` | List incompatibility rules |
| POST | `/api/v1/groups/{gid}/hazard-tags/incompatibilities` | Create incompatibility rule (same-group validated) |
| DELETE | `/api/v1/groups/{gid}/hazard-tags/incompatibilities/{iid}` | Delete incompatibility rule |

### GHS Codes (global)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/ghs-codes` | List all GHS codes |
| GET | `/api/v1/ghs-codes/{id}` | Get GHS code detail |
| POST | `/api/v1/ghs-codes` | Create GHS code (superuser) |
| PATCH | `/api/v1/ghs-codes/{id}` | Update GHS code (superuser) |

## Query Parameters & Filtering

### Chemicals — `GET /api/v1/groups/{gid}/chemicals`

| Param | Type | Description |
|-------|------|-------------|
| `search` | string | Substring match on name, CAS, synonyms |
| `hazard_tag_id` | UUID | Filter by hazard tag |
| `ghs_code_id` | UUID | Filter by GHS code |
| `has_containers` | bool | `true` = only chemicals with active containers, `false` = only without |
| `sort` | string | `name`, `created_at`, `updated_at`, `cas` |
| `order` | string | `asc` (default) or `desc` |
| `offset` | int | Default 0 |
| `limit` | int | Default 20, max 100 |

### Containers — `GET /api/v1/groups/{gid}/containers`

| Param | Type | Description |
|-------|------|-------------|
| `search` | string | Substring match on identifier |
| `chemical_id` | UUID | Filter by chemical |
| `location_id` | UUID | Filter by storage location |
| `supplier_id` | UUID | Filter by supplier |
| `is_archived` | bool | Default `false`. `true` = archived only. |
| `sort` | string | `identifier`, `created_at`, `updated_at`, `amount`, `purchased_at` |
| `order` | string | `asc` (default) or `desc` |
| `offset` | int | Default 0 |
| `limit` | int | Default 20, max 100 |

### Containers nested — `GET /api/v1/groups/{gid}/chemicals/{cid}/containers`

Same params as above minus `chemical_id` (implicit from path).

### Other list endpoints

Suppliers, hazard tags, GHS codes, and incompatibilities get `search`, `sort`, `order`, `offset`, `limit` but no specialized filters.

## Request/Response Schemas

### Pattern: Read vs Detail

- **List endpoints** return the base `Read` schema (no nested relations) — keeps payloads small.
- **Detail endpoints** return the `Detail` schema with embedded sub-resources.

### Chemical

```python
class ChemicalCreate(BaseModel):
    name: str
    cas: str | None = None
    smiles: str | None = None
    cid: str | None = None
    structure: str | None = None
    molar_mass: float | None = None
    density: float | None = None
    melting_point: float | None = None
    boiling_point: float | None = None
    comment: str | None = None

class ChemicalUpdate(BaseModel):
    name: str | None = None
    cas: str | None = None
    smiles: str | None = None
    cid: str | None = None
    structure: str | None = None
    molar_mass: float | None = None
    density: float | None = None
    melting_point: float | None = None
    boiling_point: float | None = None
    comment: str | None = None

class ChemicalRead(BaseModel):
    id: UUID
    name: str
    cas: str | None
    smiles: str | None
    cid: str | None
    structure: str | None
    molar_mass: float | None
    density: float | None
    melting_point: float | None
    boiling_point: float | None
    image_path: str | None
    comment: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime

class ChemicalDetail(ChemicalRead):
    synonyms: list[SynonymRead]
    ghs_codes: list[GHSCodeRead]
    hazard_tags: list[HazardTagRead]
```

### Sub-resource bulk replace

```python
class SynonymWrite(BaseModel):
    name: str
    category: str | None = None

class SynonymBulkUpdate(BaseModel):
    synonyms: list[SynonymWrite]

class GHSCodeBulkUpdate(BaseModel):
    ghs_ids: list[UUID]

class HazardTagBulkUpdate(BaseModel):
    hazard_tag_ids: list[UUID]
```

### Container

```python
class ContainerCreate(BaseModel):
    location_id: UUID
    supplier_id: UUID | None = None
    identifier: str
    amount: float
    unit: str
    purchased_at: date | None = None

class ContainerRead(BaseModel):
    id: UUID
    chemical_id: UUID
    location_id: UUID
    supplier_id: UUID | None
    identifier: str
    amount: float
    unit: str
    image_path: str | None
    purchased_at: date | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    is_archived: bool
```

### Storage location tree

```python
class StorageLocationNode(BaseModel):
    id: UUID
    name: str
    description: str | None
    children: list["StorageLocationNode"]
```

`GET /api/v1/groups/{gid}/storage-locations` returns `list[StorageLocationNode]` (root nodes with nested children).

### Error response

```python
class ErrorResponse(BaseModel):
    detail: str
```

Consistent across all 4xx/5xx responses.

## HTTP Status Codes

| Operation | Success | Common errors |
|-----------|---------|---------------|
| GET list | 200 | 401, 403 |
| GET detail | 200 | 401, 403, 404 |
| POST create | 201 | 401, 403, 400, 409 |
| PATCH update | 200 | 401, 403, 404, 400, 409 |
| PUT bulk replace | 200 | 401, 403, 404, 400 |
| DELETE | 204 | 401, 403, 404 |

### 409 Conflict cases

- Chemical: duplicate name within group
- Hazard tag: duplicate name within group
- Container: duplicate identifier within group
- GHS code: duplicate code
- Incompatibility: duplicate tag pair
- Group member: user already in group

## Authorization Model

| Action | Requirement |
|--------|-------------|
| Read any group-scoped resource | Group member |
| Create/update/delete chemicals, containers, synonyms | Group member |
| Create/update/delete suppliers, hazard tags, incompatibilities | Group member |
| Manage storage locations | Group member |
| Add/remove group members, update roles | Group admin |
| Update/delete group | Group admin |
| Create/manage GHS codes | Superuser |
| Read GHS codes | Any authenticated user |

All authorization enforced via the DI chain (`GroupMemberDep`, `GroupAdminDep`). No manual checks in route handlers.

### Service-layer validations (400/422)

- **Hazard tag incompatibility**: both tags must belong to the same group
- **Chemical hazard tag link**: chemical and tag must belong to the same group
- **Container identifier uniqueness**: checked via parent chemical's group
- **Storage location delete**: rejected if location has containers

## Out of Scope

- WebSocket / real-time updates
- File upload endpoints (image_path management)
- Usage/withdrawal tracking
- Audit logs
- Rate limiting
- OpenAPI customization beyond FastAPI defaults
