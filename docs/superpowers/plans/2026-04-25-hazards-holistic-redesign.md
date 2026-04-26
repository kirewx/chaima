# Hazards Holistic Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface GHS pictograms with a signal-word chip and empty state on the chemical card, give admins a debug-only way to assign hazard tags + GHS codes to chemicals, add a UI for tag incompatibilities, and add storage-compatibility warnings on the location view and container placement form.

**Architecture:** Most backend endpoints already exist (`PUT /chemicals/{cid}/hazard-tags`, `PUT /chemicals/{cid}/ghs-codes`, `/hazard-tags/incompatibilities` CRUD). The only new backend is a pure-function compatibility rules engine plus two query endpoints. Frontend wires up these endpoints with new hooks and three UI surfaces (card, settings, storage).

**Tech Stack:** FastAPI, SQLModel, async SQLAlchemy, pytest-asyncio (backend); React 18, MUI v9, TanStack Query, axios (frontend). PowerShell-friendly one-liners are preferred for Windows users.

**Spec:** `docs/superpowers/specs/2026-04-25-hazards-holistic-redesign-design.md`

---

## File Structure

**New files:**

- `src/chaima/services/hazard_compatibility.py` — pure rules engine (Conflict dataclass, pair_conflicts, location_conflicts).
- `src/chaima/routers/compatibility.py` — two GET endpoints, mounted under `/api/v1/groups/{gid}`.
- `src/chaima/schemas/compatibility.py` — Pydantic `ConflictRead` schema.
- `tests/test_services/test_hazard_compatibility.py` — service unit tests.
- `tests/test_api/test_compatibility.py` — router integration tests.
- `frontend/src/api/hooks/useGHSCodes.ts` — global GHS-code list hook.
- `frontend/src/api/hooks/useHazardTagIncompatibilities.ts` — incompatibility CRUD hooks.
- `frontend/src/api/hooks/useCompatibility.ts` — `useLocationConflicts` + `useCompatibilityCheck`.

**Modified files:**

- `frontend/src/components/ChemicalInfoBox.tsx` — signal-word chip + empty state (Task 2).
- `frontend/src/components/settings/ChemicalsAdminSection.tsx` — hazard-assignment subsection (Task 3).
- `frontend/src/components/settings/HazardTagsSection.tsx` — per-row incompatibility button + dialog (Task 5).
- `frontend/src/components/drawer/ContainerForm.tsx` — inline conflict warning (Task 10).
- `frontend/src/pages/StoragePage.tsx` — location conflict banner (Task 11).
- `frontend/src/types/index.ts` — `ConflictRead`, `IncompatibilityRead`, `IncompatibilityCreate`.
- `src/chaima/app.py` — register compatibility router (Task 8).

---

## Phase A — Card display + admin assignment

Phase A produces a usable, shippable slice on its own: card shows signal word + empty state, admin can assign hazards via Settings.

### Task 1: `useGHSCodes` hook (frontend)

**Files:**
- Create: `frontend/src/api/hooks/useGHSCodes.ts`
- Modify: `frontend/src/types/index.ts` (only if `GHSCodeRead` not exported globally — verify first)

- [ ] **Step 1: Inspect existing pattern**

Run: `cat frontend/src/api/hooks/useHazardTags.ts`
Expected: Shows the `useQuery` pattern for paginated list endpoints.

- [ ] **Step 2: Create the hook**

Write `frontend/src/api/hooks/useGHSCodes.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import client from "../client";
import type { GHSCodeRead, PaginatedResponse } from "../../types";

async function fetchGHSCodes(): Promise<GHSCodeRead[]> {
  const resp = await client.get<PaginatedResponse<GHSCodeRead>>(
    "/ghs-codes",
    { params: { limit: 100, offset: 0 } },
  );
  return resp.data.items;
}

export function useGHSCodes() {
  return useQuery({
    queryKey: ["ghs-codes"],
    queryFn: fetchGHSCodes,
    staleTime: 60 * 60 * 1000,
  });
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No new errors.

- [ ] **Step 4: Commit suggestion (do not run during planning)**

```bash
git add frontend/src/api/hooks/useGHSCodes.ts
git commit -m "feat(frontend): add useGHSCodes hook for global GHS list"
```

---

### Task 2: Card signal-word chip + empty state

**Files:**
- Modify: `frontend/src/components/ChemicalInfoBox.tsx:205-217` (the existing Hazards block)

- [ ] **Step 1: Add helper to compute worst signal word**

At the top of the file (above the component), add:

```ts
function worstSignalWord(codes: GHSCodeRead[]): "Danger" | "Warning" | null {
  let hasWarning = false;
  for (const c of codes) {
    if (c.signal_word === "Danger") return "Danger";
    if (c.signal_word === "Warning") hasWarning = true;
  }
  return hasWarning ? "Warning" : null;
}
```

- [ ] **Step 2: Import `Chip` and `Button` from MUI**

In the existing MUI import at line 1, add `Chip` and `Button`:

```ts
import { Box, Stack, Typography, Link as MuiLink, Chip, Button } from "@mui/material";
```

- [ ] **Step 3: Detect admin (current user)**

Replace the existing `useChemicalStructureSvg` import block (line 13) with:

```ts
import { useChemicalStructureSvg } from "../api/hooks/useChemicalStructureSvg";
import { useCurrentUser } from "../api/hooks/useAuth";
```

Inside the component body, near the top (after `const { data: structureSvg ... }` at line 49-50), add:

```ts
const { data: currentUser } = useCurrentUser();
const isAdmin = !!currentUser?.is_system_admin || !!currentUser?.is_group_admin;
```

(If `is_group_admin` does not exist on the user shape, drop it and rely solely on `is_system_admin` — verify against `frontend/src/types/index.ts`. If neither is present, see Step 3a.)

- [ ] **Step 3a: Fallback if admin flags are missing**

If neither `is_system_admin` nor `is_group_admin` is exposed, gate the empty-state CTA on `currentUser != null` only. Note this in the commit message; a follow-up task will add proper admin gating.

- [ ] **Step 4: Replace lines 205-217 with the new block**

Old (line 205-217):

```tsx
{(ghsCodes.length > 0 || hazardTags.length > 0) && (
  <Box sx={{ mb: 1.5 }}>
    <Typography variant="h5" sx={{ mb: 0.75 }}>
      Hazards
    </Typography>
    {ghsCodes.length > 0 && (
      <Box sx={{ mb: hazardTags.length > 0 ? 1 : 0 }}>
        <GHSPictogramRow codes={ghsCodes} size={40} />
      </Box>
    )}
    {hazardTags.length > 0 && <HazardTagChips tags={hazardTags} />}
  </Box>
)}
```

New:

```tsx
<Box sx={{ mb: 1.5 }}>
  <Typography variant="h5" sx={{ mb: 0.75 }}>
    Hazards
  </Typography>
  {(() => {
    const signal = worstSignalWord(ghsCodes);
    if (ghsCodes.length === 0 && hazardTags.length === 0) {
      return (
        <Stack spacing={0.75}>
          <Typography variant="caption" color="text.disabled">
            No hazard data
          </Typography>
          {isAdmin && (
            <Button
              size="small"
              variant="text"
              href="/settings#chemicals-admin"
              sx={{ alignSelf: "flex-start", px: 0 }}
            >
              Manage in Settings
            </Button>
          )}
        </Stack>
      );
    }
    return (
      <Stack spacing={0.75}>
        {signal && (
          <Chip
            label={signal}
            size="small"
            color={signal === "Danger" ? "error" : "warning"}
            sx={{ alignSelf: "flex-start", fontWeight: 600 }}
          />
        )}
        {ghsCodes.length > 0 && (
          <GHSPictogramRow codes={ghsCodes} size={40} />
        )}
        {hazardTags.length > 0 && <HazardTagChips tags={hazardTags} />}
      </Stack>
    );
  })()}
</Box>
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 6: Manual verification**

Run: `cd frontend && npm run dev`
- Open a chemical that has GHS data (e.g., a PubChem-fetched one). Sidebar should show pictograms + a Danger or Warning chip.
- Open a chemical with no GHS and no tags. Sidebar should show "No hazard data" + (if admin) a "Manage in Settings" button linking to `/settings#chemicals-admin`.

- [ ] **Step 7: Commit suggestion**

```bash
git add frontend/src/components/ChemicalInfoBox.tsx
git commit -m "feat(card): signal-word chip and empty state on Hazards block"
```

---

### Task 3: ChemicalsAdminSection — assign hazards (debug) subsection

**Files:**
- Modify: `frontend/src/components/settings/ChemicalsAdminSection.tsx` (append a new subsection after the existing PubChem-enrich block)
- Modify: `frontend/src/types/index.ts` (verify `HazardTagBulkUpdate`, `GHSCodeBulkUpdate` types are exported; add if missing)

- [ ] **Step 1: Verify backend put-bulk schemas**

Run: `grep -n "HazardTagBulkUpdate\|GHSCodeBulkUpdate\|GHSBulkUpdate" src/chaima/schemas/*.py`
Expected: Locate the existing schemas. Confirm body shape (likely `{hazard_tag_ids: UUID[]}` and `{ghs_ids: UUID[]}` — match exactly in the frontend payload).

- [ ] **Step 2: Add types to `frontend/src/types/index.ts` if missing**

```ts
export interface HazardTagBulkUpdate {
  hazard_tag_ids: string[];
}

export interface GHSCodeBulkUpdate {
  ghs_ids: string[];
}
```

(Skip the export if they already exist — check first.)

- [ ] **Step 3: Implement the subsection component**

Append to `frontend/src/components/settings/ChemicalsAdminSection.tsx` (just before the final `}` of `ChemicalsAdminSection`, but inside the component's returned `<Box>` wrapper or as a sibling — verify shape from the existing render):

```tsx
function AssignHazardsDebug({ groupId }: { groupId: string }) {
  const [chemId, setChemId] = useState<string | null>(null);
  const [chemQuery, setChemQuery] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [ghsIds, setGhsIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const chemicals = useChemicals(groupId, { search: chemQuery, limit: 20 });
  const tags = useHazardTags(groupId);
  const ghs = useGHSCodes();
  const detail = useChemicalDetail(groupId, chemId ?? "");

  useEffect(() => {
    if (detail.data) {
      setTagIds(detail.data.hazard_tags?.map((t) => t.id) ?? []);
      setGhsIds(detail.data.ghs_codes?.map((g) => g.id) ?? []);
    } else {
      setTagIds([]);
      setGhsIds([]);
    }
  }, [detail.data?.id]);

  const onSave = async () => {
    if (!chemId) return;
    setBusy(true);
    setMsg(null);
    try {
      await Promise.all([
        client.put(`/groups/${groupId}/chemicals/${chemId}/hazard-tags`, {
          hazard_tag_ids: tagIds,
        }),
        client.put(`/groups/${groupId}/chemicals/${chemId}/ghs-codes`, {
          ghs_ids: ghsIds,
        }),
      ]);
      setMsg({ kind: "ok", text: "Saved." });
    } catch (e) {
      setMsg({ kind: "err", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box id="assign-hazards-debug" sx={{ mt: 4 }}>
      <SectionHeader
        title="Assign hazards (debug)"
        subtitle="Admin-only. Attaches GHS codes and hazard tags to a chemical without going through the regular drawer."
      />
      <Stack spacing={2}>
        <Autocomplete
          size="small"
          options={chemicals.data?.items ?? []}
          getOptionLabel={(c) => c.name}
          inputValue={chemQuery}
          onInputChange={(_, v) => setChemQuery(v)}
          onChange={(_, c) => setChemId(c?.id ?? null)}
          renderInput={(params) => (
            <TextField {...params} label="Chemical" placeholder="Type to search" />
          )}
        />

        {chemId && (
          <>
            <Autocomplete
              multiple
              size="small"
              options={tags.data?.items ?? []}
              getOptionLabel={(t) => t.name}
              value={(tags.data?.items ?? []).filter((t) => tagIds.includes(t.id))}
              onChange={(_, vs) => setTagIds(vs.map((t) => t.id))}
              renderInput={(params) => <TextField {...params} label="Hazard tags" />}
            />
            <Autocomplete
              multiple
              size="small"
              options={ghs.data ?? []}
              getOptionLabel={(g) => `${g.code} — ${g.description}`}
              value={(ghs.data ?? []).filter((g) => ghsIds.includes(g.id))}
              onChange={(_, vs) => setGhsIds(vs.map((g) => g.id))}
              renderInput={(params) => <TextField {...params} label="GHS codes" />}
            />
            {msg && (
              <Alert severity={msg.kind === "ok" ? "success" : "error"}>
                {msg.text}
              </Alert>
            )}
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                size="small"
                disabled={busy}
                onClick={onSave}
              >
                {busy ? "Saving…" : "Save"}
              </Button>
            </Stack>
          </>
        )}
      </Stack>
    </Box>
  );
}
```

- [ ] **Step 4: Add the necessary imports at the top of the file**

```tsx
import { useState, useEffect } from "react";
import { Autocomplete, TextField } from "@mui/material";
import { useChemicals, useChemicalDetail } from "../../api/hooks/useChemicals";
import { useHazardTags } from "../../api/hooks/useHazardTags";
import { useGHSCodes } from "../../api/hooks/useGHSCodes";
import client from "../../api/client";
```

(Merge with existing MUI imports rather than duplicating.)

- [ ] **Step 5: Render `<AssignHazardsDebug groupId={groupId} />` at the bottom of `ChemicalsAdminSection`**

Just before the closing `</Box>` of the section's root, add:

```tsx
<AssignHazardsDebug groupId={groupId} />
```

- [ ] **Step 6: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 7: Manual verification**

Run: `cd frontend && npm run dev`
- Sign in as admin → Settings → Chemicals admin section.
- Search for a chemical, pick it. Current GHS + tags load into the multi-selects.
- Add a tag, add a GHS code, click Save. "Saved." toast shows.
- Open the chemical's card → sidebar reflects the new hazards.

- [ ] **Step 8: Commit suggestion**

```bash
git add frontend/src/components/settings/ChemicalsAdminSection.tsx frontend/src/types/index.ts
git commit -m "feat(settings): admin debug panel to assign hazards to a chemical"
```

---

## Phase B — Tag incompatibilities

### Task 4: `useHazardTagIncompatibilities` hook

**Files:**
- Create: `frontend/src/api/hooks/useHazardTagIncompatibilities.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Verify backend response schema**

Run: `grep -n "IncompatibilityRead\|IncompatibilityCreate" src/chaima/schemas/*.py`
Expected: Locate `IncompatibilityRead` (id, tag_a_id, tag_b_id, reason) and `IncompatibilityCreate` (tag_a_id, tag_b_id, reason).

- [ ] **Step 2: Add types to `frontend/src/types/index.ts`**

```ts
export interface IncompatibilityRead {
  id: string;
  tag_a_id: string;
  tag_b_id: string;
  reason: string | null;
}

export interface IncompatibilityCreate {
  tag_a_id: string;
  tag_b_id: string;
  reason?: string | null;
}
```

- [ ] **Step 3: Create the hook file**

Write `frontend/src/api/hooks/useHazardTagIncompatibilities.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { IncompatibilityCreate, IncompatibilityRead } from "../../types";

const key = (groupId: string) => ["hazard-tag-incompatibilities", groupId];

export function useHazardTagIncompatibilities(groupId: string) {
  return useQuery({
    queryKey: key(groupId),
    queryFn: async () => {
      const r = await client.get<IncompatibilityRead[]>(
        `/groups/${groupId}/hazard-tags/incompatibilities`,
      );
      return r.data;
    },
    enabled: !!groupId,
  });
}

export function useCreateIncompatibility(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: IncompatibilityCreate) => {
      const r = await client.post<IncompatibilityRead>(
        `/groups/${groupId}/hazard-tags/incompatibilities`,
        body,
      );
      return r.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: key(groupId) }),
  });
}

export function useDeleteIncompatibility(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await client.delete(
        `/groups/${groupId}/hazard-tags/incompatibilities/${id}`,
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: key(groupId) }),
  });
}
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 5: Commit suggestion**

```bash
git add frontend/src/api/hooks/useHazardTagIncompatibilities.ts frontend/src/types/index.ts
git commit -m "feat(frontend): hooks for hazard-tag incompatibility CRUD"
```

---

### Task 5: HazardTagsSection — incompatibility dialog

**Files:**
- Modify: `frontend/src/components/settings/HazardTagsSection.tsx`

- [ ] **Step 1: Replace the TODO subtitle**

In the `SectionHeader` at line 47, change the `subtitle` from:

```tsx
subtitle="Group-scoped tags used on chemicals. TODO: manage incompatibilities in a follow-up plan."
```

to:

```tsx
subtitle="Group-scoped tags used on chemicals. Click the link icon on a tag to manage incompatibilities."
```

- [ ] **Step 2: Add a new icon import**

At the top with other icon imports:

```tsx
import LinkOffIcon from "@mui/icons-material/LinkOff";
```

- [ ] **Step 3: Extend `DialogState`**

Replace:

```tsx
type DialogState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; tag: HazardTagRead };
```

with:

```tsx
type DialogState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; tag: HazardTagRead }
  | { mode: "incompatibilities"; tag: HazardTagRead };
```

- [ ] **Step 4: Add a per-row "Manage incompatibilities" button**

In the row JSX (around line 104, between Edit and Delete), insert:

```tsx
<IconButton
  size="small"
  onClick={() => setDialog({ mode: "incompatibilities", tag: t })}
  aria-label={`Manage incompatibilities for ${t.name}`}
>
  <LinkOffIcon fontSize="small" />
</IconButton>
```

- [ ] **Step 5: Add the new dialog component at the bottom of the file**

```tsx
function IncompatibilityDialog({
  open,
  tag,
  groupId,
  allTags,
  onClose,
}: {
  open: boolean;
  tag: HazardTagRead | null;
  groupId: string;
  allTags: HazardTagRead[];
  onClose: () => void;
}) {
  const list = useHazardTagIncompatibilities(groupId);
  const create = useCreateIncompatibility(groupId);
  const remove = useDeleteIncompatibility(groupId);

  const [otherId, setOtherId] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  if (!tag) return null;

  const rows = (list.data ?? []).filter(
    (i) => i.tag_a_id === tag.id || i.tag_b_id === tag.id,
  );

  const otherTagOptions = allTags.filter(
    (t) =>
      t.id !== tag.id &&
      !rows.some(
        (r) =>
          (r.tag_a_id === tag.id && r.tag_b_id === t.id) ||
          (r.tag_b_id === tag.id && r.tag_a_id === t.id),
      ),
  );

  const tagName = (id: string) =>
    allTags.find((t) => t.id === id)?.name ?? id;

  const onAdd = async () => {
    if (!otherId) return;
    await create.mutateAsync({
      tag_a_id: tag.id,
      tag_b_id: otherId,
      reason: reason.trim() || null,
    });
    setOtherId(null);
    setReason("");
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Incompatibilities for "{tag.name}"</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {rows.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              No incompatibilities yet.
            </Typography>
          )}
          {rows.map((r) => {
            const otherName =
              r.tag_a_id === tag.id ? tagName(r.tag_b_id) : tagName(r.tag_a_id);
            return (
              <Stack
                key={r.id}
                direction="row"
                spacing={1}
                sx={{ alignItems: "center" }}
              >
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2">{otherName}</Typography>
                  {r.reason && (
                    <Typography variant="caption" color="text.secondary">
                      {r.reason}
                    </Typography>
                  )}
                </Box>
                <IconButton
                  size="small"
                  onClick={() => remove.mutate(r.id)}
                  aria-label="Remove incompatibility"
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Stack>
            );
          })}

          <Stack
            direction="row"
            spacing={1}
            sx={{ alignItems: "center", borderTop: "1px solid", borderColor: "divider", pt: 2 }}
          >
            <Autocomplete
              size="small"
              sx={{ flex: 1 }}
              options={otherTagOptions}
              getOptionLabel={(t) => t.name}
              value={otherTagOptions.find((t) => t.id === otherId) ?? null}
              onChange={(_, v) => setOtherId(v?.id ?? null)}
              renderInput={(params) => (
                <TextField {...params} label="Add incompatible tag" />
              )}
            />
            <TextField
              size="small"
              label="Reason (optional)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              sx={{ flex: 1 }}
            />
            <Button
              variant="outlined"
              size="small"
              disabled={!otherId || create.isPending}
              onClick={onAdd}
            >
              Add
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
```

- [ ] **Step 6: Wire the new dialog in `HazardTagsSection`**

At the bottom of `HazardTagsSection`, just below the existing `<HazardTagDialog ... />` mount, add:

```tsx
<IncompatibilityDialog
  open={dialog.mode === "incompatibilities"}
  tag={dialog.mode === "incompatibilities" ? dialog.tag : null}
  groupId={groupId}
  allTags={tags}
  onClose={() => setDialog({ mode: "closed" })}
/>
```

- [ ] **Step 7: Add the new imports at the top of the file**

```tsx
import { Autocomplete } from "@mui/material";
import {
  useHazardTagIncompatibilities,
  useCreateIncompatibility,
  useDeleteIncompatibility,
} from "../../api/hooks/useHazardTagIncompatibilities";
```

- [ ] **Step 8: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 9: Manual verification**

Run: `cd frontend && npm run dev`
- Settings → Hazard tags. Each tag row shows three icons: Edit, LinkOff, Delete.
- Click LinkOff on a tag → dialog opens. Empty list initially.
- Pick another tag from the autocomplete, type a reason, click Add. Row appears.
- Reload — row still there.
- Click Delete on the row → it disappears.

- [ ] **Step 10: Commit suggestion**

```bash
git add frontend/src/components/settings/HazardTagsSection.tsx
git commit -m "feat(settings): UI to manage hazard-tag incompatibilities"
```

---

## Phase C — Compatibility engine + storage warnings

### Task 6: Backend `hazard_compatibility.py` service (TDD)

**Files:**
- Create: `src/chaima/services/hazard_compatibility.py`
- Create: `tests/test_services/test_hazard_compatibility.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_services/test_hazard_compatibility.py`:

```python
"""Unit tests for the hazard-compatibility rules engine."""
from __future__ import annotations

from chaima.services.hazard_compatibility import (
    Conflict,
    pair_conflicts,
)


def _ghs(code: str, signal: str = "Warning") -> object:
    class C:
        pass
    c = C()
    c.code = code
    c.signal_word = signal
    c.pictogram = code
    return c


def test_flammable_plus_oxidizer_conflict():
    a_codes = [_ghs("GHS02", "Danger")]
    b_codes = [_ghs("GHS03", "Danger")]
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=a_codes, a_tags=[], a_name="Acetone",
        b_codes=b_codes, b_tags=[], b_name="Hydrogen peroxide",
    )
    assert any(c.kind == "ghs" and "GHS02" in c.code_or_tag for c in out)
    assert any("oxidizer" in (c.reason or "").lower() for c in out)


def test_acid_plus_base_corrosive_conflict():
    a_codes = [_ghs("GHS05", "Danger")]
    b_codes = [_ghs("GHS05", "Danger")]
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=a_codes, a_tags=[], a_name="Hydrochloric acid",
        b_codes=b_codes, b_tags=[], b_name="Sodium hydroxide",
    )
    assert any(c.kind == "ghs" and "corrosive" in (c.reason or "").lower() for c in out)


def test_unrelated_chemicals_no_conflict():
    a_codes = [_ghs("GHS07", "Warning")]
    b_codes = [_ghs("GHS09", "Warning")]
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=a_codes, a_tags=[], a_name="Sucrose",
        b_codes=b_codes, b_tags=[], b_name="Sodium chloride",
    )
    assert out == []


def test_explosive_plus_flammable_conflict():
    a_codes = [_ghs("GHS01", "Danger")]
    b_codes = [_ghs("GHS02", "Danger")]
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=a_codes, a_tags=[], a_name="TNT",
        b_codes=b_codes, b_tags=[], b_name="Acetone",
    )
    assert len(out) >= 1
    assert any(c.kind == "ghs" for c in out)


def test_returns_conflict_dataclass_shape():
    out = pair_conflicts(
        session=None,
        group_id=None,
        a_codes=[_ghs("GHS02", "Danger")],
        a_tags=[],
        a_name="A",
        b_codes=[_ghs("GHS03", "Danger")],
        b_tags=[],
        b_name="B",
    )
    assert isinstance(out[0], Conflict)
    assert out[0].chem_a_name == "A"
    assert out[0].chem_b_name == "B"
    assert out[0].kind in {"ghs", "tag"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_hazard_compatibility.py -v`
Expected: FAIL with `ModuleNotFoundError: chaima.services.hazard_compatibility`.

- [ ] **Step 3: Create the service file**

Write `src/chaima/services/hazard_compatibility.py`:

```python
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
    from chaima.models.storage_location import StorageLocation

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
            .where(Container.storage_location_id.in_(sub_ids))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_hazard_compatibility.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit suggestion**

```bash
git add src/chaima/services/hazard_compatibility.py tests/test_services/test_hazard_compatibility.py
git commit -m "feat(backend): hazard-compatibility rules engine (GHS + tag rules)"
```

---

### Task 7: Backend `compatibility.py` router (TDD)

**Files:**
- Create: `src/chaima/schemas/compatibility.py`
- Create: `src/chaima/routers/compatibility.py`
- Create: `tests/test_api/test_compatibility.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_api/test_compatibility.py`:

```python
"""API tests for the compatibility endpoints."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_location_conflicts_empty(client_with_group):
    client, group_id, _ = client_with_group
    # Pick any storage location in the group; create one if helpers don't.
    resp = await client.post(
        f"/api/v1/groups/{group_id}/storage-locations",
        json={"name": "Cabinet 1", "kind": "cabinet"},
    )
    assert resp.status_code in (200, 201)
    loc_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/groups/{group_id}/locations/{loc_id}/conflicts",
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_compatibility_check_returns_list(client_with_group):
    client, group_id, _ = client_with_group
    # Endpoint must return a list (potentially empty) for any valid pair.
    # Create a chemical and a location.
    chem_resp = await client.post(
        f"/api/v1/groups/{group_id}/chemicals",
        json={"name": "Test Chemical", "synonyms": [], "ghs_codes": []},
    )
    chemical_id = chem_resp.json()["id"]
    loc_resp = await client.post(
        f"/api/v1/groups/{group_id}/storage-locations",
        json={"name": "Cabinet A", "kind": "cabinet"},
    )
    location_id = loc_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/groups/{group_id}/compatibility/check",
        params={"chemical_id": chemical_id, "location_id": location_id},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

(`client_with_group` is the fixture used elsewhere — check `tests/test_api/conftest.py` for the exact name and tuple shape, and adjust.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api/test_compatibility.py -v`
Expected: 404 on the new endpoints (router not yet registered).

- [ ] **Step 3: Create the schema**

Write `src/chaima/schemas/compatibility.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class ConflictRead(BaseModel):
    chem_a_name: str
    chem_b_name: str
    kind: str
    code_or_tag: str
    reason: str
```

- [ ] **Step 4: Create the router**

Write `src/chaima/routers/compatibility.py`:

```python
"""Compatibility endpoints: location conflicts + placement check."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from chaima.db import get_session
from chaima.dependencies import require_group_member
from chaima.models.chemical import Chemical
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
    session: AsyncSession = Depends(get_session),
    _=Depends(require_group_member),
):
    conflicts = await svc_location_conflicts(session, group_id, location_id)
    return [_to_read(c) for c in conflicts]


@router.get(
    "/compatibility/check",
    response_model=list[ConflictRead],
)
async def check_compatibility(
    group_id: UUID,
    chemical_id: UUID = Query(...),
    location_id: UUID = Query(...),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_group_member),
):
    """Predict conflicts if `chemical_id` were placed under `location_id`."""
    from sqlalchemy import select
    from chaima.models.container import Container

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
            .where(Container.storage_location_id == location_id)
        )
    ).scalars().unique().all()

    out = []
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
```

(Verify `require_group_member` is the actual dependency name in `src/chaima/dependencies.py` — adjust if it differs.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_api/test_compatibility.py -v`
Expected: 2 passed (status 200 returning empty lists).

- [ ] **Step 6: Commit suggestion**

```bash
git add src/chaima/routers/compatibility.py src/chaima/schemas/compatibility.py tests/test_api/test_compatibility.py
git commit -m "feat(api): /locations/{lid}/conflicts and /compatibility/check endpoints"
```

---

### Task 8: Register the new router

**Files:**
- Modify: `src/chaima/app.py` (around lines 15-25 imports, line 76-96 mounts)

- [ ] **Step 1: Add the import**

Append to the router-imports block (around line 25):

```python
from chaima.routers.compatibility import router as compatibility_router
```

- [ ] **Step 2: Mount the router**

Append to the `include_router` block (around line 96):

```python
app.include_router(compatibility_router)
```

- [ ] **Step 3: Verify the app boots**

Run: `python -c "from chaima.app import app; print(len(app.routes))"`
Expected: prints a number that's two larger than before; no import errors.

- [ ] **Step 4: Commit suggestion**

```bash
git add src/chaima/app.py
git commit -m "chore(api): mount compatibility router"
```

---

### Task 9: `useCompatibility` hooks

**Files:**
- Create: `frontend/src/api/hooks/useCompatibility.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add the type to `frontend/src/types/index.ts`**

```ts
export interface ConflictRead {
  chem_a_name: string;
  chem_b_name: string;
  kind: "ghs" | "tag";
  code_or_tag: string;
  reason: string;
}
```

- [ ] **Step 2: Create the hook file**

Write `frontend/src/api/hooks/useCompatibility.ts`:

```ts
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import client from "../client";
import type { ConflictRead } from "../../types";

export function useLocationConflicts(groupId: string, locationId: string | null) {
  return useQuery({
    queryKey: ["location-conflicts", groupId, locationId],
    queryFn: async () => {
      const r = await client.get<ConflictRead[]>(
        `/groups/${groupId}/locations/${locationId}/conflicts`,
      );
      return r.data;
    },
    enabled: !!groupId && !!locationId,
  });
}

export function useCompatibilityCheck(
  groupId: string,
  chemicalId: string | null,
  locationId: string | null,
) {
  return useQuery({
    queryKey: ["compatibility-check", groupId, chemicalId, locationId],
    queryFn: async () => {
      const r = await client.get<ConflictRead[]>(
        `/groups/${groupId}/compatibility/check`,
        { params: { chemical_id: chemicalId, location_id: locationId } },
      );
      return r.data;
    },
    enabled: !!groupId && !!chemicalId && !!locationId,
    placeholderData: keepPreviousData,
  });
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Commit suggestion**

```bash
git add frontend/src/api/hooks/useCompatibility.ts frontend/src/types/index.ts
git commit -m "feat(frontend): hooks for location conflicts and placement check"
```

---

### Task 10: ContainerForm inline conflict warning

**Files:**
- Modify: `frontend/src/components/drawer/ContainerForm.tsx`

- [ ] **Step 1: Inspect the existing component**

Run: `grep -n "location_id\|storage_location_id\|locationId" frontend/src/components/drawer/ContainerForm.tsx`
Expected: Locate the state variable that holds the selected location and the chemical id prop.

- [ ] **Step 2: Add the import**

```tsx
import { useCompatibilityCheck } from "../../api/hooks/useCompatibility";
import { Alert } from "@mui/material";
```

(Merge `Alert` with existing MUI imports.)

- [ ] **Step 3: Wire the hook**

Inside the component body, after the location state is read, add:

```tsx
const conflicts = useCompatibilityCheck(
  groupId,
  chemicalId ?? null,
  locationId ?? null,
);
```

(Field names — `groupId`, `chemicalId`, `locationId` — must match the existing component. Adjust if the form names them differently.)

- [ ] **Step 4: Render the warning above the Save row**

Just above the existing Save/Cancel row, add:

```tsx
{conflicts.data && conflicts.data.length > 0 && (
  <Alert severity="warning" sx={{ mt: 1 }}>
    <strong>Storage conflict.</strong>
    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
      {conflicts.data.map((c, i) => (
        <li key={i}>
          {c.chem_a_name} and {c.chem_b_name}: {c.reason}
        </li>
      ))}
    </ul>
  </Alert>
)}
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 6: Manual verification**

- Pick a flammable chemical (e.g., acetone) with GHS02. Place its container in a cabinet that already holds a chemical with GHS03 (oxidizer).
- Open the container form for the new container. Pick the cabinet location. Within ~250 ms, the warning Alert appears above Save listing the conflict.
- Save remains enabled; clicking it creates the container regardless.

- [ ] **Step 7: Commit suggestion**

```bash
git add frontend/src/components/drawer/ContainerForm.tsx
git commit -m "feat(container): inline storage-conflict warning on placement"
```

---

### Task 11: StoragePage location conflict banner

**Files:**
- Modify: `frontend/src/pages/StoragePage.tsx`

- [ ] **Step 1: Locate the location detail render block**

Run: `grep -n "selected\|locationId\|location\\.id" frontend/src/pages/StoragePage.tsx`
Expected: Find the JSX section that renders a single selected location's details.

- [ ] **Step 2: Add the import**

```tsx
import { useLocationConflicts } from "../api/hooks/useCompatibility";
import { Alert } from "@mui/material";
```

(Merge `Alert` with existing MUI imports.)

- [ ] **Step 3: Wire the hook**

In the location detail render path:

```tsx
const conflicts = useLocationConflicts(groupId, selectedLocationId);
```

- [ ] **Step 4: Render the banner at the top of the location detail block**

```tsx
{conflicts.data && conflicts.data.length > 0 && (
  <Alert severity="warning" sx={{ mb: 2 }}>
    <strong>This location has {conflicts.data.length} storage conflict{conflicts.data.length === 1 ? "" : "s"}.</strong>
    <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
      {conflicts.data.map((c, i) => (
        <li key={i}>
          {c.chem_a_name} and {c.chem_b_name}: {c.reason}
        </li>
      ))}
    </ul>
  </Alert>
)}
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 6: Manual verification**

- Find a cabinet that contains incompatible chemicals (use Phase A's debug panel to set up the data: assign GHS02 to chemical X, GHS03 to chemical Y, place both in the same cabinet).
- Open the storage page → select the cabinet. Banner appears at the top listing the X+Y conflict.

- [ ] **Step 7: Commit suggestion**

```bash
git add frontend/src/pages/StoragePage.tsx
git commit -m "feat(storage): location conflict banner on detail view"
```

---

## Self-Review

**Spec coverage:**

- [x] Section 1 — card signal-word + empty state → Task 2
- [x] Section 2 — admin assignment debug → Tasks 1 + 3
- [x] Section 3 — incompatibilities UI → Tasks 4 + 5
- [x] Section 4 — backend rules engine + endpoints → Tasks 6 + 7 + 8
- [x] Section 5 — storage warning surfaces → Tasks 9 + 10 + 11

**Type/name consistency:**

- `Conflict` dataclass (backend) ↔ `ConflictRead` Pydantic ↔ `ConflictRead` TS interface — same field names: `chem_a_name`, `chem_b_name`, `kind`, `code_or_tag`, `reason`.
- `pair_conflicts` is the sync GHS-only entry (used by tests with `session=None`); `pair_conflicts_async` is used by the router and `location_conflicts`.
- `useCompatibilityCheck` and `useLocationConflicts` exported from the same `useCompatibility.ts` file.

**Placeholder scan:** No "TBD" / "fill in" steps remain. The two notes that say "verify against the existing X" call for a single grep, not deferred work.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-25-hazards-holistic-redesign.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
