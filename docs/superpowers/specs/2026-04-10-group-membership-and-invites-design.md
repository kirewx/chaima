# Group Membership, Invites & Multi-Group Search

## Overview

Redesign the group system so that every user has a mandatory **main group**, registration happens exclusively via **single-use invite links**, and search supports **multi-group filtering** via parallel frontend queries. A superuser account is seeded on first startup via pydantic-settings.

## Data Model Changes

### User model

- Add `main_group_id: UUID` — non-nullable foreign key to `Group`. Every user must belong to at least one group.
- Add `is_superuser: bool` — default `False`.
- A user cannot exist without a `main_group_id`.

### Invite model (new)

| Field        | Type             | Notes                                        |
|--------------|------------------|----------------------------------------------|
| `id`         | UUID             | Primary key                                  |
| `group_id`   | UUID             | FK to Group                                  |
| `token`      | str              | Unique, indexed, short random string         |
| `created_by` | UUID             | FK to User (admin who created the invite)    |
| `expires_at` | datetime         | created_at + configurable TTL                |
| `used_by`    | UUID | None      | FK to User, set on acceptance                |
| `used_at`    | datetime | None  | Set on acceptance                            |

Single-use: once `used_by` is set, the invite is consumed and cannot be reused.

### UserGroupLink

No changes. Continues to serve as the many-to-many junction between User and Group with `is_admin` flag.

### AdminSettings (pydantic-settings)

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class AdminSettings(BaseSettings):
    admin_email: str = "admin@chaima.dev"
    admin_password: SecretStr = SecretStr("changeme")
    admin_group_name: str = "Admin"
    invite_ttl_hours: int = 48

    model_config = SettingsConfigDict(env_prefix="CHAIMA_")
```

**Startup seed logic**: If no superuser exists in the DB, create the group from `admin_group_name`, create the user with `is_superuser=True` and `main_group_id` set to that group, and create a `UserGroupLink` with `is_admin=True`.

## API Endpoints

### Invite management (authenticated)

| Method | Endpoint                              | Auth                  | Description                          |
|--------|---------------------------------------|-----------------------|--------------------------------------|
| POST   | `/api/v1/groups/{group_id}/invites`   | Group Admin or Superuser | Create invite, returns token + URL + expires_at |
| GET    | `/api/v1/groups/{group_id}/invites`   | Group Admin or Superuser | List pending/used invites for group  |
| DELETE | `/api/v1/invites/{invite_id}`         | Creator or Superuser  | Revoke an unused invite              |

### Public invite endpoints (no auth required)

| Method | Endpoint                    | Auth                | Description                                     |
|--------|-----------------------------|---------------------|-------------------------------------------------|
| GET    | `/api/v1/invites/{token}`   | None                | Returns `{group_name, expires_at, is_valid}` for landing page |
| PATCH  | `/api/v1/invites/{token}`   | None or CurrentUser | Accept the invite (see accept flows below)      |

### Accept flows

**New user (not logged in):**

1. `PATCH /api/v1/invites/{token}` with `{email, password}` in body
2. Backend creates User with `main_group_id` = invite's group
3. Creates `UserGroupLink`
4. Marks invite as used (`used_by`, `used_at`)
5. Returns auth token (immediate login)

**Existing user (logged in):**

1. `PATCH /api/v1/invites/{token}` with auth header, no body
2. Backend creates `UserGroupLink`
3. Marks invite as used
4. Does NOT change `main_group_id`

### User self-service

| Method | Endpoint          | Auth        | Description                                          |
|--------|-------------------|-------------|------------------------------------------------------|
| PATCH  | `/api/v1/users/me` | CurrentUser | Update `main_group_id` (must be a group user belongs to) |

### Superuser-only endpoints

| Method | Endpoint                                        | Auth      | Description                          |
|--------|-------------------------------------------------|-----------|--------------------------------------|
| POST   | `/api/v1/groups`                                | Superuser | Create a new group                   |
| PATCH  | `/api/v1/groups/{group_id}/members/{user_id}`   | Superuser | Promote to admin or superuser        |

### Removed endpoints

- `POST /api/v1/auth/register` — removed entirely. Registration only via invite acceptance.

### Unchanged endpoints

- `GET /api/v1/groups` — returns groups current user belongs to
- All group-scoped resource endpoints (`/groups/{group_id}/chemicals`, `/groups/{group_id}/containers`, etc.) — unchanged

## Frontend Flow

### Invite landing page (`/invite/:token`)

- **Public route** (no auth required)
- On load: `GET /api/v1/invites/{token}` to fetch group name + validity
- Displays: "You've been invited to **[Group Name]**"
- If invite expired or used: show error message, no action buttons
- Two buttons: **Accept** / **Decline**
- Decline: navigates away (no API call)
- Accept behavior:
  - **If logged in**: `PATCH /api/v1/invites/{token}` with auth header, redirect to `/`
  - **If not logged in**: show choice — "Log in" or "Create account"
    - **Log in**: redirect to `/login?redirect=/invite/:token` — after login, auto-accept
    - **Create account**: show inline email + password form, submit via `PATCH /api/v1/invites/{token}`, auto-login, redirect to `/`

### FilterDrawer changes (SearchPage)

- Add a **"Groups" section** at the top of the FilterDrawer (above existing "Has stock" toggle)
- Shows a chip for each group the user belongs to
- Main group chip is **on by default**, other group chips are off
- User toggles groups on/off to widen/narrow search
- FilterBadges shows active group filters as colored chips

### Settings page changes

- **Remove** the "Active Group" dropdown
- **Add** "Main Group" section: display current main group with a dropdown to change it (only groups user belongs to)
- Keep suppliers and hazard tags sections (scoped to main group)

### Superuser admin panel (Settings page, conditional)

Visible only when `user.is_superuser`:

- **Create Group** button + form
- **Groups list** — click into a group to:
  - Generate invite link (shows URL, TTL, copy button)
  - View members with roles (admin / member / superuser)
  - Promote/demote members (admin toggle, superuser toggle)
  - View pending invites with revoke option

### Navigation changes

- Remove standalone registration page/route
- Add `/invite/:token` as a public route in `App.tsx`

## Multi-Group Search (Frontend)

### Approach

No new backend endpoints. The frontend fires **parallel queries** per selected group and merges results client-side.

### Chemicals

- `useChemicals` hook accepts an array of group IDs (from FilterDrawer selection)
- Fires one `GET /groups/{group_id}/chemicals?search=...&filters...` per group in parallel
- Merges results, sorts client-side
- Attaches `group_name` from the already-loaded group list (no backend schema change needed)
- Chemical cards show a small group label when multiple groups are active

### Containers

- Same pattern: parallel queries per selected group for container search
- Merge + sort client-side
- Group label on container results when multi-group is active

### Default behavior

- On page load, only the user's main group is selected
- User opens FilterDrawer to toggle additional groups on/off
- Toggling a group on/off triggers an immediate re-query (same as existing filter behavior)
