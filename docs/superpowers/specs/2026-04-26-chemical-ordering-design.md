# Chemical Ordering & Wishlist

## Problem

ChAiMa today tracks chemicals and their on-shelf containers, but has no concept of *pending* inventory. When a lab member orders a chemical from a vendor:

- There is no record of the order in the app until the package arrives and someone adds the resulting `Container` rows manually.
- Other lab members cannot see "we have already ordered toluene; it should arrive next week" — they may order the same thing or run out unexpectedly.
- Vendor metadata (price, package size, vendor catalog number, expected arrival) is lost. Lead-time intelligence ("abcr usually takes 12 days") cannot be built up.
- A separate Slack workflow is currently used for ordering, but it is not integrated with the app's chemical catalog.

This spec adds an Orders feature: a single-step ordering workflow (anyone records an order, anyone marks it received), a lightweight Wishlist for "I need this someday" requests, and the supporting data model, API, and UI to wire them into the existing app.

## Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Vendor data source | **No scraping.** PubChem provides the per-compound vendor list (names + URLs to product pages) for discovery; price, package size, and lead time come from manual entry on the order form. Lead time is then computed automatically from the user's own order history. |
| 2 | Workflow | **Single-step.** An order is created in `ordered` status and flips to `received` (or `cancelled`) in one action. No separate request/approval steps. A separate Wishlist concept captures "I need this" without committing to vendor/price. |
| 3 | Order ↔ Container | **Separate `Order` entity.** One order spawns N `Container` rows on receipt (each bottle individually trackable). Containers gain an `order_id` FK. |
| 4 | New chemical handling | **Chemical created at order time.** The order form's chemical search falls through to PubChem when no existing match is found; picking a PubChem result creates a skeleton `Chemical` immediately, then the order is created against it. The chemical appears in the catalog as "0 containers, 1 on order". |
| 5 | Vendor model | **Keep existing `Supplier` schema unchanged.** No `search_url_template` (URLs rot, PubChem already has per-compound links). The order's own `vendor_product_url` field carries the durable per-order link. Pre-seed 10 supplier names per group at install. |
| 6 | Project tracking | **Required.** New `Project` entity (group-scoped), free-solo combobox like Supplier, "General" pre-seeded per group. |
| 7 | Status states | `ordered`, `received`, `cancelled`. **No `partially_received`** — partial arrivals are handled by editing `package_count` down + creating a follow-up order. |
| 8 | Permissions | Any group member: create order, receive, dismiss/promote wishlist, create supplier/project (free-solo). Admin only: cancel order, archive supplier/project, edit any non-own order. |

## Section 1 — Data model

Three new tables, one extended.

### `Project` (new)

| field | type | notes |
|---|---|---|
| `id` | int PK | |
| `group_id` | FK → `groups.id` | scoping |
| `name` | str | `UNIQUE(group_id, name)` |
| `is_archived` | bool | soft-delete; matches the existing Chemical pattern |
| `created_at` | datetime | |

Pre-seeded `Project(name="General")` per group on creation and via data migration for existing groups.

### `Supplier` (unchanged)

Schema stays as-is (`id`, `group_id`, `name`, `created_at`). Migration only inserts pre-seeded rows for existing groups.

Pre-seed list (10 rows per existing group, `INSERT ... ON CONFLICT DO NOTHING` keyed on `(group_id, name)`):

`Sigma-Aldrich`, `Merck`, `Carl Roth`, `abcr`, `BLDPharm`, `TCI`, `Alfa Aesar`, `Fisher Scientific`, `Thermo Fisher`, `VWR`.

### `Order` (new)

| field | type | notes |
|---|---|---|
| `id` | int PK | |
| `group_id` | FK → `groups.id` | |
| `chemical_id` | FK → `chemicals.id` | required |
| `supplier_id` | FK → `suppliers.id` | required |
| `project_id` | FK → `projects.id` | required |
| `amount_per_package` | float | > 0 |
| `unit` | str | same vocabulary as `Container.unit` |
| `package_count` | int | ≥ 1 |
| `price_per_package` | Numeric(10,2) | nullable |
| `currency` | str(3) | ISO 4217, default `EUR` |
| `purity` | str | nullable; propagates to all containers on receipt |
| `vendor_catalog_number` | str | nullable |
| `vendor_product_url` | str | nullable |
| `vendor_order_number` | str | nullable (PO reference) |
| `expected_arrival` | date | nullable |
| `comment` | text | nullable |
| `status` | enum | `ordered` / `received` / `cancelled` |
| `ordered_by_user_id` | FK → `user.id` | |
| `ordered_at` | datetime | auto |
| `received_by_user_id` | FK → `user.id` | nullable |
| `received_at` | datetime | nullable |
| `cancelled_at` | datetime | nullable |
| `cancellation_reason` | text | nullable |

### `Container` (extended)

Adds one column: `order_id INT NULL REFERENCES orders(id)`. Nullable because Containers existed before this feature.

### `WishlistItem` (new)

| field | type | notes |
|---|---|---|
| `id` | int PK | |
| `group_id` | FK → `groups.id` | |
| `chemical_id` | FK → `chemicals.id` | nullable — request can reference an existing chemical |
| `freeform_name` | str | nullable; used when `chemical_id` is null |
| `freeform_cas` | str | nullable; used when `chemical_id` is null |
| `requested_by_user_id` | FK → `user.id` | |
| `requested_at` | datetime | auto |
| `comment` | text | nullable |
| `status` | enum | `open` / `converted` / `dismissed` |
| `converted_to_order_id` | FK → `orders.id` | nullable |
| `dismissed_at` | datetime | nullable |
| `dismissed_by_user_id` | FK → `user.id` | nullable |

Either `chemical_id` is set OR (`freeform_name` is set, optionally with `freeform_cas`). Constraint enforced at schema layer.

When a wishlist item is promoted to an order, the row stays (`status=converted`, `converted_to_order_id` set) — keeps an audit trail of who asked for what.

## Section 2 — API

New routers: `orders.py`, `wishlist.py`, `projects.py`. Extended: `pubchem.py`, `suppliers.py`.

### `/api/orders`

| method | path | who | purpose |
|---|---|---|---|
| GET | `/orders` | member | list group's orders; query filters: `status`, `supplier_id`, `project_id`, `chemical_id` |
| POST | `/orders` | member | create order; optional `wishlist_item_id` to atomically mark a wishlist row converted |
| GET | `/orders/{id}` | member | read |
| PATCH | `/orders/{id}` | creator or admin | edit; **rejected with 409 if `status != ordered`** |
| POST | `/orders/{id}/receive` | member | mark received; spawns N containers (payload below) |
| POST | `/orders/{id}/cancel` | admin | sets `status=cancelled`, records `cancellation_reason` |

**Receive payload:**

```json
{
  "containers": [
    { "identifier": "lot-A12345", "storage_location_id": 7, "purity_override": null }
  ]
}
```

Strict: `containers.length` MUST equal `order.package_count`. `purity_override` defaults to `order.purity` when null. Returns the spawned `Container` rows.

### `/api/wishlist`

| method | path | who | purpose |
|---|---|---|---|
| GET | `/wishlist` | member | list `status=open` items in group |
| POST | `/wishlist` | member | create with `chemical_id` OR `freeform_name`(+`freeform_cas`) |
| PATCH | `/wishlist/{id}` | creator or admin | edit |
| POST | `/wishlist/{id}/dismiss` | member | mark `dismissed`, record actor |
| POST | `/wishlist/{id}/promote` | member | resolve chemical (PubChem lookup if freeform); returns the wishlist item with a populated `chemical_id` so the frontend can open the order form pre-filled. The wishlist row is **only** flipped to `converted` when the subsequent `POST /orders` succeeds (atomic via `wishlist_item_id` param). |

### `/api/projects` (new)

| method | path | who |
|---|---|---|
| GET | `/projects` | member |
| POST | `/projects` | member (free-solo) |
| PATCH | `/projects/{id}` | admin |
| POST | `/projects/{id}/archive` | admin |

### `/api/suppliers` (extended)

Existing endpoints unchanged. `GET /suppliers` response embeds lead-time stats per supplier:

```json
{
  "id": 3, "name": "abcr",
  "lead_time": { "order_count": 12, "median_days": 13, "p25_days": 11, "p75_days": 16 }
}
```

`lead_time` is `null` when `order_count < 3`. Computed inside the route handler from `received_at - ordered_at` deltas of received orders in the requesting group.

### `/api/pubchem` (extended)

| method | path | purpose |
|---|---|---|
| GET | `/pubchem/vendors/{cid}` | fetch PubChem's "Chemical Vendors" section; returns `[{name, url, country?}]` |

Backed by a new `lookup_vendors(cid)` in `src/chaima/services/pubchem.py`. Hits PUG-View `/data/compound/{cid}/JSON?heading=Chemical+Vendors`, parses the section tree (similar to `parse_ghs_classification`), reuses the existing 24h cache.

### Error responses (consistent across endpoints)

| HTTP | when |
|---|---|
| `400` | malformed request (validation, container count mismatch) |
| `403` | role check failed |
| `404` | resource not found OR cross-group access |
| `409` | state conflict (editing received order, receiving cancelled order, double-receive) |
| `422` | downstream validation (e.g. one of N container payloads invalid) |
| `502` | PubChem upstream failure (only on lookup endpoints; never blocks order creation) |

## Section 3 — Service layer

| file | responsibilities |
|---|---|
| `src/chaima/services/orders.py` (new) | `create_order`, `edit_order`, `cancel_order`, `receive_order` (transactional), `list_orders`, `lead_time_stats` |
| `src/chaima/services/wishlist.py` (new) | `create`, `dismiss`, `promote` (resolves chemical via PubChem if freeform) |
| `src/chaima/services/projects.py` (new) | CRUD + archive |
| `src/chaima/services/pubchem.py` (extended) | `lookup_vendors(cid)` parser |

### Receipt transaction (`receive_order`)

Single DB transaction. Any error → rollback, no partial state.

1. `SELECT ... FOR UPDATE` on the `Order` row.
2. Reject `409` if `status != ordered`.
3. Reject `400` if `len(containers) != order.package_count`.
4. For each `containers[i]`:
   - validate `storage_location_id` exists and belongs to the requesting group;
   - create a `Container` row with `chemical_id=order.chemical_id`, `amount=order.amount_per_package`, `unit=order.unit`, `supplier_id=order.supplier_id`, `purity=containers[i].purity_override or order.purity`, `identifier=containers[i].identifier`, `order_id=order.id`, `purchased_at=now()`.
5. Update order: `status=received`, `received_at=now()`, `received_by_user_id=current_user.id`.
6. Commit.

### Lead-time stats algorithm

```python
def lead_time_stats(session, group_id: int, supplier_id: int) -> LeadTimeStats | None:
    deltas_days = [
        (o.received_at - o.ordered_at).days
        for o in session.query(Order)
            .filter(
                Order.group_id == group_id,
                Order.supplier_id == supplier_id,
                Order.status == "received",
            )
            .all()
    ]
    if len(deltas_days) < 3:
        return None
    return LeadTimeStats(
        order_count=len(deltas_days),
        median_days=int(median(deltas_days)),
        p25_days=int(quantile(deltas_days, 0.25)),
        p75_days=int(quantile(deltas_days, 0.75)),
    )
```

Computed inside `GET /suppliers` route handler. No separate cache — trivial cost at expected scale.

### Concurrency

- `PATCH /orders/{id}` allowed only when `status == ordered`. After receipt or cancel, edits are rejected with `409`.
- `FOR UPDATE` lock during receipt serializes concurrent edit/receive naturally.
- Wishlist conversion: the wishlist row is flipped to `converted` *inside the order-create transaction* when the create payload includes `wishlist_item_id`. Atomic.

### Validation rules (Pydantic schemas)

| field | rule |
|---|---|
| `package_count` | int ≥ 1 |
| `amount_per_package` | float > 0 |
| `price_per_package` | Decimal ≥ 0, nullable |
| `currency` | regex `^[A-Z]{3}$`, default `EUR` |
| `expected_arrival` | date; warn-but-allow if in past |
| `vendor_product_url` | `HttpUrl`, nullable |
| `supplier_id` / `project_id` / `chemical_id` | must belong to same `group_id` (cross-group → 404) |
| `containers[*].identifier` | non-empty string, unique within receipt payload |

### Edge cases

| case | resolution |
|---|---|
| Chemical archived after order placed | Order still references it; UI shows archived badge; receipt still works. |
| Supplier/Project archived | FK preserved on past orders; pickers hide archived rows for new orders. |
| Storage location deleted between order and receipt | Per-row 422 with the offending index; user picks another and resubmits. |
| Order placed against potential duplicate chemical | On chemical search, exact CID match → reuse. CAS-only match (no CID) → prompt "A chemical with CAS X exists — order against existing or create separate?" Mirrors the existing import flow's dedup. |
| Reordering an archived chemical | Allowed with a warning on the order form. Does not auto-unarchive. |
| PubChem vendor lookup fails | Vendor panel renders "PubChem temporarily unavailable [Retry]". Order creation is unblocked — the panel is purely informational. |
| Wishlist freeform item, PubChem returns no result | Promote endpoint returns `404 chemical_not_resolvable`; frontend opens the full `ChemicalForm` flow instead of the order form, then re-tries promote. |

### Permissions enforcement

Reuses existing FastAPI deps:

- `GroupMemberDep` for create/list/receive/dismiss/wishlist-add/promote/project-create/supplier-create.
- `GroupAdminDep` for cancel/archive/edit-any.
- New small dep `creator_or_admin(resource_type)` for own-resource edits — looks up the resource by ID, checks `resource.created_by_user_id == user.id` OR user is admin in `resource.group`.

## Section 4 — Frontend

### Navigation

New top-level route `/orders` in `App.tsx`, slotted into `Layout` between Storage and Settings. Nav item shows a count badge of open orders.

### `OrdersPage` (`/orders`)

Single page with MUI Tabs:

| tab | filter | empty state |
|---|---|---|
| Open | `status=ordered` (default landing) | "No open orders. + New Order" |
| Received | `status=received` | "Nothing received yet" |
| Cancelled | `status=cancelled` | hidden if zero |
| Wishlist | `WishlistItem.status=open` | "Wishlist empty. + Add to Wishlist" |

Top-right action area: `+ New Order` (Open/Received/Cancelled tabs) or `+ Add to Wishlist` (Wishlist tab).

### Order list rendering

Card rows matching the StoragePage aesthetic. Each card: chemical name + CAS, supplier name, project, `3 × 100 mL @ €25`, expected arrival (red "overdue" badge if past), ordered by, ordered date. Click anywhere → opens detail drawer.

### Order form (drawer, mirrors `ContainerForm.tsx`)

Sections:

1. **Chemical** — search bound to existing chemicals; if no match, "Search PubChem for {query}" → opens existing `ChemicalForm` flow inline as a stacked drawer (creates skeleton chemical, returns to order form pre-filled).
2. **Vendor** — Supplier picker (free-solo). When a chemical with `cid` is selected, a collapsible panel "PubChem says these vendors stock it" renders the `[{name, url}]` list as plain external links (no matching against configured Suppliers).
3. **Lead-time hint** — once a Supplier is picked, a small info row: "abcr usually takes 11–16 days for your group (12 past orders)". Hidden if `lead_time` is null.
4. **Quantity & price** — `amount_per_package` `unit` `× package_count`; `price_per_package` `currency`; auto-calculated total shown read-only.
5. **Project** — Project picker (free-solo).
6. **Optional details** (collapsed) — vendor catalog #, product URL, vendor order #, purity, expected arrival, comment.

Submit → `POST /orders`, drawer closes, list refreshes.

When pre-filled from a Wishlist item: chemical is locked, wishlist comment copied into order comment.

### Order detail drawer

Same drawer as the form, read-only by default. Edit toggle visible to creator/admin while `status=ordered`. Action buttons:

- **Mark Received** (member, `status=ordered`) → opens Receive dialog.
- **Cancel Order** (admin only, `status=ordered`) → modal asking for `cancellation_reason`.
- **Reorder** (any status) → opens `+ New Order` drawer pre-filled from this order.

### Receive dialog (modal)

Shows N rows where N = `package_count`. Each row:

- `identifier` (lot/bottle number) — required.
- `storage_location_id` — required, existing hierarchical location picker.
- `purity_override` — optional (defaults to `order.purity`).

Submit → `POST /orders/{id}/receive`. Success toast: "3 containers received and added to inventory" with link to chemical detail.

### Wishlist sub-tab

Simpler list. Each row: chemical name (or freeform `name (CAS)`), requested_by, requested_at, comment. Per-row actions: **Promote to Order** (opens order form pre-filled) and **Dismiss**.

`+ Add to Wishlist` form: chemical picker (existing OR freeform `name`+`cas`) + comment.

### Chemical detail page additions

- **"Order more"** button next to the existing "Add container" button → opens order form pre-filled with this chemical.
- **"On order"** indicator near the container count: "On order: 3 packages, expected Apr 30" (linking to the open order). Hidden if no open orders for this chemical.

### Settings additions

New **"Projects"** section in `SettingsNav` under "Group Admin", matching `GroupsAdminSection.tsx` pattern. Member can add; admin can edit/archive.

### File map (frontend)

```
frontend/src/pages/OrdersPage.tsx                          -- new
frontend/src/components/orders/OrderList.tsx               -- new
frontend/src/components/orders/OrderForm.tsx               -- new (drawer)
frontend/src/components/orders/OrderDetailDrawer.tsx       -- new
frontend/src/components/orders/ReceiveOrderDialog.tsx      -- new
frontend/src/components/orders/PubChemVendorPanel.tsx      -- new
frontend/src/components/orders/WishlistList.tsx            -- new
frontend/src/components/orders/WishlistForm.tsx            -- new
frontend/src/components/settings/ProjectsAdminSection.tsx  -- new
frontend/src/api/hooks/useOrders.ts                        -- new
frontend/src/api/hooks/useWishlist.ts                      -- new
frontend/src/api/hooks/useProjects.ts                      -- new
frontend/src/api/hooks/usePubChemVendors.ts                -- new
frontend/src/api/hooks/useSuppliers.ts                     -- modify (lead_time stats in response)
frontend/src/components/Layout.tsx                         -- modify (add Orders nav)
frontend/src/components/ChemicalDetail*.tsx                -- modify (Order more, On order)
frontend/src/App.tsx                                       -- modify (add /orders route)
frontend/src/types/index.ts                                -- modify (Order, WishlistItem, Project types)
```

## Section 5 — Migration, testing, rollout

### Alembic migration

Single file: `alembic/versions/XXXX_add_orders_feature.py`.

Schema:

1. `CREATE TABLE projects` (id, group_id FK, name, is_archived, created_at; `UNIQUE(group_id, name)`).
2. `CREATE TABLE orders` (full schema from §1).
3. `CREATE TABLE wishlist_items` (full schema from §1).
4. `ALTER TABLE containers ADD COLUMN order_id INT NULL REFERENCES orders(id)`.

Data migration in same file (back-fills existing groups):

- For each existing `group_id`: insert one `Project(name="General")`.
- For each existing group: insert the 10 pre-seeded supplier names — `INSERT ... ON CONFLICT DO NOTHING` keyed on `(group_id, name)` so we never duplicate a supplier the group already created manually.

Group-creation code path (forward seeding): extend `src/chaima/services/groups.py` (or wherever new groups are created today, e.g. `services/seed.py` for the initial group) to insert the same `Project(name="General")` row + the 10 supplier rows whenever a new group is created. Use the same names as the data migration so the two paths stay in sync.

`downgrade()` drops the new tables and the `containers.order_id` column.

### Backend tests

Mirroring existing `tests/test_services/` (unit) + `tests/test_api/` (FastAPI integration) split.

**`tests/test_services/test_orders.py`** (new):

- `test_create_order_valid`
- `test_receive_spawns_n_containers`
- `test_receive_is_atomic_on_failure` — inject a bad `storage_location_id` in row 2 of 3, assert nothing committed
- `test_cannot_edit_after_received` → 409
- `test_cannot_receive_cancelled` → 409
- `test_cannot_double_receive` → 409
- `test_cross_group_supplier_rejected` → 404
- `test_lead_time_stats_null_under_three_orders`
- `test_lead_time_stats_quantiles`

**`tests/test_services/test_wishlist.py`** (new):

- `test_create_with_chemical_id`
- `test_create_freeform`
- `test_promote_resolves_via_pubchem` (mock `lookup` to return a known CID)
- `test_promote_freeform_no_pubchem_match` → 404
- `test_promote_already_in_catalog_reuses_chemical`
- `test_dismiss_sets_status_and_actor`
- `test_order_create_with_wishlist_id_marks_converted_atomically`

**`tests/test_services/test_projects.py`** (new) — basic CRUD + archive.

**`tests/test_api/test_orders.py`** (new) — end-to-end happy path + permission matrix:

- member creates → member receives → containers visible at `GET /containers`;
- non-admin cannot cancel (403);
- admin cancel succeeds, `status=cancelled`, `cancellation_reason` recorded;
- non-creator non-admin cannot edit other user's order (403).

**`tests/test_api/test_wishlist.py`** (new) — CRUD + promote → order create flow.

**`tests/test_api/test_pubchem.py`** (extend existing) — `lookup_vendors` endpoint with a recorded PUG-View JSON fixture committed under `tests/fixtures/pubchem/vendors_*.json`.

### Frontend tests

Manual smoke checklist (no Jest/Vitest setup in repo today, matching the rest of the codebase):

1. Place order from chemical detail "Order more".
2. Place order via Orders tab → existing chemical.
3. Place order via Orders tab → PubChem-fallthrough new chemical.
4. Receive a 3-package order; verify 3 containers spawn at the chosen locations.
5. Cancel as admin; verify button hidden for non-admins.
6. Add wishlist freeform; promote to order; verify wishlist row marked converted.
7. Place 3+ orders from one supplier with realistic ordered/received dates; verify lead-time hint appears.

### Rollout

- Single PR; feature is self-contained behind `/orders`.
- Migration runs via existing `alembic upgrade head` on deploy.
- No feature flag, no new env vars — additive change.
- The existing 24h PubChem cache absorbs `/vendors/{cid}` calls.

## Out of scope (v2+)

| | |
|---|---|
| Vendor scraping, per-vendor adapters, headless browser | Decided in §Decisions row 1 — manual entry + deep links via PubChem |
| Email/Slack notifications (overdue, arrived) | Wishlist data shape is Slack-friendly; future webhook-pusher is straightforward |
| Multi-line orders (multiple chemicals on one shipment) | Each chemical is its own Order |
| Partial receipts as a first-class state | Edit `package_count` + follow-up order is the workaround |
| Budget reports / cost-center aggregations | `Project` is captured; aggregation UI is a separate feature |
| Order export (CSV/PDF) | Trivial to add later — schema supports it |
| Mobile-optimized UI | Desktop-first, matching existing pages |

## Known open items (deferred)

- **Mixed currencies in totals.** v1 displays per-row currency; no totals shown anywhere.
- **Cancellation reason visibility.** v1 shows it to anyone who can see the order. If labs want admin-only later, it's a small filter.
- **"General" project escape hatch.** Labs that don't want project tracking rename "General" or ignore it. No "no project" toggle in v1.
