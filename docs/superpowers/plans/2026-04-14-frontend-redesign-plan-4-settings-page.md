# Frontend Redesign — Plan 4: Settings Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `SettingsPage` as a two-pane layout (left section nav, right content) matching the clinical theme. Sections: **Account** (name/email, password, theme toggle, sign out), **Group** (current group + main-group picker), **Members & Invites** (admin/SU, tabbed), **Hazard tags** (admin, group-scoped CRUD), **Buildings** (SU stub for now), **System** (SU stub). Wire the theme toggle through `PATCH /users/me` so dark mode becomes user-controllable end-to-end.

**Architecture:** One `SettingsPage` shell that owns a `section` state. Each section is a self-contained component under `src/components/settings/`. Reuse Plan 2 primitives: `RoleGate` (admin/superuser gating), `EditDrawer` + `DrawerProvider` (for New-invite and hazard-tag edit), the clinical theme, and `useCurrentUser`. No new drawer kinds for v1 — the new-invite + edit-hazard-tag flows are light enough to use inline `Dialog` (following the existing SettingsPage pattern) rather than extending the `DrawerConfig` union. Decision: keep `EditDrawer` reserved for chemical/container/storage entities and use `Dialog` for settings-scoped sub-forms. This keeps the drawer context simple and avoids cross-domain coupling.

**Tech Stack:** React 19, MUI 9 + `@emotion/react`, `@tanstack/react-query`, React Router 7, axios. Playwright for E2E. Parent spec: `docs/superpowers/specs/2026-04-14-frontend-redesign-design.md`. Plan 2 (`docs/superpowers/plans/2026-04-14-frontend-redesign-plan-2-chemicals-page.md`) is merged and provides the theme, layout shell, `RoleGate`, `useCurrentUser`, `DrawerProvider`, and the clinical palette.

**Dependency notes:**
- Plan 1 (backend) and Plan 2 (theme/layout/Chemicals) must be merged. Plan 4 does **not** depend on Plan 3 (Storage) and can ship independently of it — Plan 3 runs in parallel.
- Backend endpoints already available (verified): `GET /api/v1/users/me`, `PATCH /api/v1/users/me` (fastapi-users, accepts `dark_mode`, `password`, `email`), `PATCH /api/v1/users/me/main-group`, `GET/POST/PATCH/DELETE /api/v1/groups/{gid}/members/{uid}`, `GET/POST /api/v1/groups/{gid}/invites`, `DELETE /api/v1/invites/{id}`, `GET/POST/PATCH/DELETE /api/v1/groups/{gid}/hazard-tags`. These are all already surfaced via hooks in `src/api/hooks/{useAuth,useGroups,useInvites,useHazardTags}.ts`.
- `useCurrentUser` returns `UserRead` which already has `dark_mode: boolean` in `src/types/index.ts`. No backend or schema work needed in Plan 4.
- **No** `PATCH /api/v1/users/me` hook exists yet (Plan 2 never added one). Plan 4 adds `useUpdateMe` in Task 2.
- Plan 4 REUSES Plan 2's `RoleGate`. Admin gating currently falls through to "any group member" because Plan 1 didn't land real group roles; the `MemberRead.is_admin` field does exist and is used inside Members section to render the role pill, but `RoleGate allow={["admin"]}` evaluates `user.is_admin` which isn't set on `UserRead`. Decision: gate "Members & Invites" and "Hazard tags" behind **group-membership** for v1 (i.e. render to anyone with a `main_group_id`) and leave a TODO referencing the future real-role mini-plan. Gate "Buildings" and "System" behind `is_superuser` which *does* exist on `UserRead`. Document this in the section headers.

---

## File map

**New files:**
- `src/components/settings/SettingsNav.tsx`
- `src/components/settings/AccountSection.tsx`
- `src/components/settings/GroupSection.tsx`
- `src/components/settings/MembersInvitesSection.tsx`
- `src/components/settings/HazardTagsSection.tsx`
- `src/components/settings/BuildingsSection.tsx`
- `src/components/settings/SystemSection.tsx`
- `src/components/settings/SectionHeader.tsx`
- `src/api/hooks/useUpdateMe.ts`
- `e2e/settings.spec.ts`

**Modified files:**
- `src/pages/SettingsPage.tsx` (full rewrite — two-pane shell that delegates to section components)
- `src/api/hooks/useAuth.ts` (re-export `useUpdateMe` for convenience, optional)

**Deleted files:** None. Old inline `SupplierSection` / `HazardTagSection` / `SuperuserPanel` / `GroupAdminPanel` were defined inside the old `SettingsPage.tsx` and are removed by its rewrite. Supplier management is intentionally dropped from Settings — Plan 2's container form already picks suppliers inline, and the spec does not list a suppliers section under Settings. If future work needs supplier CRUD, it belongs on its own page or under a "Group data" subsection, not here.

---

## Task 1: `useUpdateMe` hook

**Files:** Create `src/api/hooks/useUpdateMe.ts`. Modify `src/api/hooks/useAuth.ts` (optional re-export).

**Rationale:** fastapi-users exposes `PATCH /api/v1/users/me` that accepts any field on `UserUpdate` (`email`, `password`, `dark_mode`). Plan 2 never wired it — the dark-mode toggle is the first consumer. One hook, invalidates `currentUser` on success so the `useAppTheme` hook (Plan 2, `src/hooks/useTheme.ts`) re-runs and swaps the theme app-wide in one render.

- [ ] **Step 1: Create `src/api/hooks/useUpdateMe.ts`:**

```ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { UserRead } from "../../types";

export interface UpdateMePayload {
  email?: string;
  password?: string;
  dark_mode?: boolean;
}

export function useUpdateMe() {
  const queryClient = useQueryClient();
  return useMutation<UserRead, Error, UpdateMePayload>({
    mutationFn: (payload) =>
      client.patch("/users/me", payload).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.setQueryData(["currentUser"], updated);
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });
}
```

- [ ] **Step 2: Manual verify** via browser devtools — once section components wire it in later tasks, flipping the theme toggle should persist across reload.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/api/hooks/useUpdateMe.ts
git commit -m "feat(api): useUpdateMe hook for PATCH /users/me"
```

---

## Task 2: `SettingsNav` + `SectionHeader` primitives

**Files:** Create `src/components/settings/SettingsNav.tsx` and `src/components/settings/SectionHeader.tsx`.

**Rationale:** The settings page has five to seven sections. Extract a single left-rail nav component that takes an active key and a click handler, and a right-pane section header (title + subtitle + optional actions slot) so every section has consistent chrome. Nothing in MUI's `List` matches the clinical aesthetic out of the box, so style directly.

- [ ] **Step 1: Create `src/components/settings/SettingsNav.tsx`:**

```tsx
import { Box, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

export type SettingsSectionKey =
  | "account"
  | "group"
  | "members"
  | "hazard-tags"
  | "buildings"
  | "system";

export interface NavItem {
  key: SettingsSectionKey;
  label: string;
  group: "PERSONAL" | "GROUP ADMIN" | "SYSTEM";
  visible: boolean;
}

interface Props {
  items: NavItem[];
  active: SettingsSectionKey;
  onSelect: (key: SettingsSectionKey) => void;
  footer?: ReactNode;
}

export function SettingsNav({ items, active, onSelect, footer }: Props) {
  const groups: Array<NavItem["group"]> = ["PERSONAL", "GROUP ADMIN", "SYSTEM"];
  return (
    <Box
      component="nav"
      aria-label="Settings sections"
      sx={{
        width: { xs: "100%", md: 220 },
        flexShrink: 0,
        borderRight: { md: "1px solid" },
        borderBottom: { xs: "1px solid", md: "none" },
        borderColor: "divider",
        pr: { md: 2 },
        pb: { xs: 2, md: 0 },
        mb: { xs: 2, md: 0 },
      }}
    >
      <Stack spacing={2.5}>
        {groups.map((g) => {
          const rows = items.filter((i) => i.group === g && i.visible);
          if (rows.length === 0) return null;
          return (
            <Box key={g}>
              <Typography
                variant="h5"
                sx={{ color: "text.secondary", mb: 0.5, pl: 1 }}
              >
                {g}
              </Typography>
              <Stack>
                {rows.map((r) => {
                  const selected = r.key === active;
                  return (
                    <Box
                      key={r.key}
                      role="button"
                      tabIndex={0}
                      onClick={() => onSelect(r.key)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(r.key);
                        }
                      }}
                      sx={{
                        px: 1,
                        py: 0.75,
                        borderRadius: 1,
                        cursor: "pointer",
                        fontSize: 13,
                        fontWeight: selected ? 600 : 400,
                        color: selected ? "text.primary" : "text.secondary",
                        bgcolor: selected ? "action.selected" : "transparent",
                        "&:hover": { bgcolor: "action.hover" },
                      }}
                    >
                      {r.label}
                    </Box>
                  );
                })}
              </Stack>
            </Box>
          );
        })}
      </Stack>
      {footer && <Box sx={{ mt: 3 }}>{footer}</Box>}
    </Box>
  );
}
```

- [ ] **Step 2: Create `src/components/settings/SectionHeader.tsx`:**

```tsx
import { Box, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function SectionHeader({ title, subtitle, actions }: Props) {
  return (
    <Stack
      direction="row"
      alignItems="flex-start"
      justifyContent="space-between"
      sx={{
        pb: 2,
        mb: 2.5,
        borderBottom: "1px solid",
        borderColor: "divider",
      }}
    >
      <Box>
        <Typography variant="h2">{title}</Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {subtitle}
          </Typography>
        )}
      </Box>
      {actions && <Box>{actions}</Box>}
    </Stack>
  );
}
```

**Acceptance:** Both files compile. `SettingsNav` groups items under the three headers and hides empty groups.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/settings/SettingsNav.tsx frontend/src/components/settings/SectionHeader.tsx
git commit -m "feat(settings): SettingsNav + SectionHeader primitives"
```

---

## Task 3: Rewrite `SettingsPage` shell

**Files:** Replace `src/pages/SettingsPage.tsx` wholesale.

**Rationale:** The existing page is a scrolling stack of cards. Replace it with a two-pane shell that owns the active-section state and delegates rendering to section components (which will be stubbed in this task, filled in Tasks 4-9). Build the shell first so every subsequent task only touches one component.

- [ ] **Step 1: Replace `src/pages/SettingsPage.tsx`:**

```tsx
import { useState } from "react";
import { Box, Stack } from "@mui/material";
import { useCurrentUser } from "../api/hooks/useAuth";
import { SettingsNav, type SettingsSectionKey, type NavItem } from "../components/settings/SettingsNav";
import { AccountSection } from "../components/settings/AccountSection";
import { GroupSection } from "../components/settings/GroupSection";
import { MembersInvitesSection } from "../components/settings/MembersInvitesSection";
import { HazardTagsSection } from "../components/settings/HazardTagsSection";
import { BuildingsSection } from "../components/settings/BuildingsSection";
import { SystemSection } from "../components/settings/SystemSection";

export default function SettingsPage() {
  const { data: user } = useCurrentUser();
  const [active, setActive] = useState<SettingsSectionKey>("account");

  const isMember = Boolean(user?.main_group_id);
  const isSuperuser = Boolean(user?.is_superuser);

  const items: NavItem[] = [
    { key: "account", label: "Account", group: "PERSONAL", visible: true },
    { key: "group", label: "Group", group: "PERSONAL", visible: true },
    { key: "members", label: "Members & Invites", group: "GROUP ADMIN", visible: isMember },
    { key: "hazard-tags", label: "Hazard tags", group: "GROUP ADMIN", visible: isMember },
    { key: "buildings", label: "Buildings", group: "SYSTEM", visible: isSuperuser },
    { key: "system", label: "System", group: "SYSTEM", visible: isSuperuser },
  ];

  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={{ md: 3 }}>
      <SettingsNav items={items} active={active} onSelect={setActive} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {active === "account" && <AccountSection />}
        {active === "group" && <GroupSection />}
        {active === "members" && isMember && user?.main_group_id && (
          <MembersInvitesSection groupId={user.main_group_id} />
        )}
        {active === "hazard-tags" && isMember && user?.main_group_id && (
          <HazardTagsSection groupId={user.main_group_id} />
        )}
        {active === "buildings" && isSuperuser && <BuildingsSection />}
        {active === "system" && isSuperuser && <SystemSection />}
      </Box>
    </Stack>
  );
}
```

- [ ] **Step 2: Create stub files for every section** so the page compiles. Each stub just renders `<SectionHeader title="…" />` plus a "Coming in Task N" body.

```tsx
// src/components/settings/AccountSection.tsx
import { SectionHeader } from "./SectionHeader";
export function AccountSection() {
  return <><SectionHeader title="Account" /></>;
}
```

Replicate that stub pattern for `GroupSection.tsx`, `MembersInvitesSection.tsx` (takes `{ groupId }: { groupId: string }`), `HazardTagsSection.tsx` (same prop), `BuildingsSection.tsx`, `SystemSection.tsx`.

- [ ] **Step 3: Manual verify.** `npm run dev` → log in → visit `/settings` → two-pane layout renders, nav items switch the right-pane header. No runtime errors.

**Acceptance:** Settings page shows the new two-pane layout with all stubs reachable. Old card-based settings no longer render.

- [ ] **Step 4: Commit.**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/components/settings/
git commit -m "feat(settings): two-pane SettingsPage shell with section stubs"
```

---

## Task 4: `AccountSection` — email, password, theme toggle, sign out

**Files:** Replace `src/components/settings/AccountSection.tsx`.

**Rationale:** The most-used section. Covers the three personal controls: editable email, password change (current + new), theme toggle (Light/Dark — drop the spec's "System" third option; decision: the user prefers a persisted server-side preference, and "System" would add a third branch in `useAppTheme` that reads `prefers-color-scheme` without persistence. Keep it binary for v1), and sign out. Email and password reuse `useUpdateMe`; theme uses `useUpdateMe({ dark_mode })`; sign out uses `useLogout` from Plan 2's `useAuth.ts`.

- [ ] **Step 1: Implement the section:**

```tsx
import { useState, useEffect } from "react";
import {
  Box,
  Stack,
  TextField,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  Alert,
  Typography,
  Divider,
} from "@mui/material";
import LightModeIcon from "@mui/icons-material/LightMode";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import { useNavigate } from "react-router-dom";
import { SectionHeader } from "./SectionHeader";
import { useCurrentUser, useLogout } from "../../api/hooks/useAuth";
import { useUpdateMe } from "../../api/hooks/useUpdateMe";

export function AccountSection() {
  const { data: user } = useCurrentUser();
  const updateMe = useUpdateMe();
  const logout = useLogout();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [pwMsg, setPwMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    if (user?.email) setEmail(user.email);
  }, [user?.email]);

  if (!user) return <SectionHeader title="Account" />;

  const emailDirty = email.trim().length > 0 && email.trim() !== user.email;

  const saveEmail = async () => {
    await updateMe.mutateAsync({ email: email.trim() });
  };

  const savePassword = async () => {
    if (!newPassword) return;
    try {
      // fastapi-users PATCH /users/me accepts `password` directly; it does NOT
      // require current_password. We ask for it as UX confirmation only — if
      // the user typed something, require it to match what they know. If the
      // backend later enforces re-auth, surface that here.
      await updateMe.mutateAsync({ password: newPassword });
      setPwMsg({ kind: "ok", text: "Password updated." });
      setCurrentPassword("");
      setNewPassword("");
    } catch (e) {
      setPwMsg({ kind: "err", text: e instanceof Error ? e.message : "Failed to update password." });
    }
  };

  const setMode = async (mode: "light" | "dark") => {
    await updateMe.mutateAsync({ dark_mode: mode === "dark" });
  };

  return (
    <Box>
      <SectionHeader
        title="Account"
        subtitle="Your profile, security, and appearance preferences."
      />

      <Stack spacing={4}>
        <Stack spacing={1.5}>
          <Typography variant="h4">Profile</Typography>
          <TextField
            label="Email"
            size="small"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            sx={{ maxWidth: 360 }}
          />
          <Box>
            <Button
              variant="contained"
              size="small"
              disabled={!emailDirty || updateMe.isPending}
              onClick={saveEmail}
            >
              Save email
            </Button>
          </Box>
        </Stack>

        <Divider />

        <Stack spacing={1.5}>
          <Typography variant="h4">Password</Typography>
          <TextField
            label="Current password"
            type="password"
            size="small"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            sx={{ maxWidth: 360 }}
            autoComplete="current-password"
          />
          <TextField
            label="New password"
            type="password"
            size="small"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            sx={{ maxWidth: 360 }}
            autoComplete="new-password"
          />
          {pwMsg && (
            <Alert severity={pwMsg.kind === "ok" ? "success" : "error"} sx={{ maxWidth: 360 }}>
              {pwMsg.text}
            </Alert>
          )}
          <Box>
            <Button
              variant="contained"
              size="small"
              disabled={!currentPassword || !newPassword || updateMe.isPending}
              onClick={savePassword}
            >
              Update password
            </Button>
          </Box>
        </Stack>

        <Divider />

        <Stack spacing={1.5}>
          <Typography variant="h4">Theme</Typography>
          <Typography variant="body2" color="text.secondary">
            Persisted to your account. Applies immediately across all your browsers.
          </Typography>
          <ToggleButtonGroup
            exclusive
            size="small"
            value={user.dark_mode ? "dark" : "light"}
            onChange={(_, v) => v && setMode(v)}
            aria-label="Theme"
          >
            <ToggleButton value="light" aria-label="Light theme">
              <LightModeIcon fontSize="small" sx={{ mr: 1 }} /> Light
            </ToggleButton>
            <ToggleButton value="dark" aria-label="Dark theme">
              <DarkModeIcon fontSize="small" sx={{ mr: 1 }} /> Dark
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>

        <Divider />

        <Stack spacing={1.5}>
          <Typography variant="h4">Session</Typography>
          <Box>
            <Button
              variant="outlined"
              color="error"
              size="small"
              onClick={() =>
                logout.mutate(undefined, {
                  onSuccess: () => navigate("/login", { replace: true }),
                })
              }
            >
              Sign out
            </Button>
          </Box>
        </Stack>
      </Stack>
    </Box>
  );
}
```

**Decision:** The "current password" field is collected for UX parity with typical reset flows, but because fastapi-users' `PATCH /users/me` accepts `password` without requiring the current one (the session cookie is already proof of identity), we do not forward it. This is a pragmatic v1 choice — add a TODO near the `savePassword` call noting that server-side re-auth enforcement is out of scope for Plan 4 and should be tracked as a follow-up if the security posture tightens.

- [ ] **Step 2: Manual verify.**
  1. Open Account section, change email to a throwaway address, save, reload — new email is shown.
  2. Toggle theme Light/Dark → entire app switches within one render; reload → persists.
  3. Update password, sign out, sign back in with the new one.

**Acceptance:**
- Email PATCH succeeds and `currentUser` query reflects new email.
- Theme toggle flips `user.dark_mode` and `useAppTheme` re-runs (entire app re-renders with new palette).
- Password PATCH succeeds and the user can log back in with the new password.
- Sign out clears the query client and redirects to `/login`.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/settings/AccountSection.tsx
git commit -m "feat(settings): Account section with email, password, theme toggle, sign out"
```

---

## Task 5: `GroupSection` — current group + main-group picker

**Files:** Replace `src/components/settings/GroupSection.tsx`.

**Rationale:** Shows the user's current main group name, lists all groups they belong to, and allows switching the main group via a `Select`. Reuses `useGroups` (returns only groups the user is in) and `useUpdateMainGroup` from `useAuth.ts`. No new endpoints.

- [ ] **Step 1: Implement:**

```tsx
import { Box, Stack, TextField, MenuItem, Typography, Alert, Chip } from "@mui/material";
import { SectionHeader } from "./SectionHeader";
import { useGroups } from "../../api/hooks/useGroups";
import { useCurrentUser, useUpdateMainGroup } from "../../api/hooks/useAuth";

export function GroupSection() {
  const { data: user } = useCurrentUser();
  const { data: groups = [], isLoading } = useGroups();
  const updateMain = useUpdateMainGroup();

  if (!user) return <SectionHeader title="Group" />;

  const current = groups.find((g) => g.id === user.main_group_id);
  const hasMultiple = groups.length > 1;

  return (
    <Box>
      <SectionHeader
        title="Group"
        subtitle="Your lab group determines which chemicals, containers, and storage you can see."
      />

      {groups.length === 0 && !isLoading && (
        <Alert severity="info">
          You are not a member of any group yet. Ask an admin for an invite.
        </Alert>
      )}

      {current && (
        <Stack spacing={2}>
          <Stack spacing={0.5}>
            <Typography variant="h5">CURRENT</Typography>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography variant="h3">{current.name}</Typography>
              <Chip label="MAIN" size="small" color="primary" sx={{ fontSize: 10 }} />
            </Stack>
            {current.description && (
              <Typography variant="body2" color="text.secondary">
                {current.description}
              </Typography>
            )}
          </Stack>

          {hasMultiple && (
            <Stack spacing={1}>
              <Typography variant="h5">CHANGE MAIN GROUP</Typography>
              <TextField
                select
                size="small"
                value={user.main_group_id ?? ""}
                onChange={(e) => updateMain.mutate(e.target.value)}
                sx={{ maxWidth: 360 }}
                helperText="You will still see data from all groups you belong to, but this one will be the default."
              >
                {groups.map((g) => (
                  <MenuItem key={g.id} value={g.id}>
                    {g.name}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
          )}

          {!hasMultiple && (
            <Typography variant="body2" color="text.secondary">
              You only belong to one group. When you join another, you'll be able to change your main group here.
            </Typography>
          )}
        </Stack>
      )}
    </Box>
  );
}
```

**Acceptance:** The section shows the current group name + description. If the user is in ≥2 groups, a `Select` appears and switching it invalidates `currentUser`, which cascades into the Chemicals list scoped to the new group.

- [ ] **Step 2: Manual verify.** Log in as a user in one group → picker is hidden, informative copy. Add the user to a second group via Swagger → picker appears → changing it causes the Chemicals page to show different data.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/settings/GroupSection.tsx
git commit -m "feat(settings): Group section with current group and main-group picker"
```

---

## Task 6: `MembersInvitesSection` — tabs for Members and Pending invites

**Files:** Replace `src/components/settings/MembersInvitesSection.tsx`.

**Rationale:** Spec calls for a tab bar with **Members** and **Pending invites**. Members tab lists rows with email, role pill (Admin indigo / User grey), and a `...` menu (Set role / Remove). Invites tab lists the pending invites with copy button and revoke. `+ New invite` on the invites tab opens a small `Dialog` (not `EditDrawer` — see Plan 4's architecture note) that calls `useCreateInvite` and shows the generated URL with copy. Reuses existing hooks in `useGroups.ts` and `useInvites.ts`.

- [ ] **Step 1: Implement:**

```tsx
import { useState } from "react";
import {
  Box,
  Stack,
  Tabs,
  Tab,
  Button,
  IconButton,
  Typography,
  Chip,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Snackbar,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import AddIcon from "@mui/icons-material/Add";
import { SectionHeader } from "./SectionHeader";
import { useGroup, useGroupMembers, useUpdateMember, useRemoveMember } from "../../api/hooks/useGroups";
import { useGroupInvites, useCreateInvite, useRevokeInvite } from "../../api/hooks/useInvites";
import type { MemberRead } from "../../types";

interface Props {
  groupId: string;
}

export function MembersInvitesSection({ groupId }: Props) {
  const [tab, setTab] = useState<"members" | "invites">("members");
  const group = useGroup(groupId);
  const members = useGroupMembers(groupId);

  return (
    <Box>
      <SectionHeader
        title="Members & Invites"
        subtitle={group.data ? `${group.data.name} · ${members.data?.length ?? 0} members` : undefined}
      />
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ borderBottom: "1px solid", borderColor: "divider", mb: 2 }}
      >
        <Tab value="members" label="Members" />
        <Tab value="invites" label="Pending invites" />
      </Tabs>
      {tab === "members" && <MembersTab groupId={groupId} members={members.data ?? []} />}
      {tab === "invites" && <InvitesTab groupId={groupId} />}
    </Box>
  );
}

function MembersTab({ groupId, members }: { groupId: string; members: MemberRead[] }) {
  if (members.length === 0) {
    return <Typography variant="body2" color="text.secondary">No members yet.</Typography>;
  }
  return (
    <Stack
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        overflow: "hidden",
        bgcolor: "background.paper",
      }}
    >
      {members.map((m, i) => (
        <MemberRow
          key={m.user_id}
          groupId={groupId}
          member={m}
          divider={i < members.length - 1}
        />
      ))}
    </Stack>
  );
}

function MemberRow({
  groupId,
  member,
  divider,
}: {
  groupId: string;
  member: MemberRead;
  divider: boolean;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const update = useUpdateMember(groupId, member.user_id);
  const remove = useRemoveMember(groupId);
  const close = () => setAnchor(null);

  return (
    <Stack
      direction="row"
      alignItems="center"
      sx={{
        px: 2,
        py: 1.25,
        gap: 2,
        borderBottom: divider ? "1px solid" : "none",
        borderColor: "divider",
      }}
    >
      <Box
        sx={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          bgcolor: "action.selected",
          color: "text.secondary",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          fontWeight: 600,
        }}
      >
        {member.email[0]?.toUpperCase() ?? "?"}
      </Box>
      <Typography variant="body1" sx={{ flex: 1, minWidth: 0 }} noWrap>
        {member.email}
      </Typography>
      <Chip
        label={member.is_admin ? "Admin" : "User"}
        size="small"
        sx={{
          bgcolor: member.is_admin ? "primary.light" : "action.selected",
          color: member.is_admin ? "primary.dark" : "text.secondary",
          fontSize: 10,
          height: 20,
        }}
      />
      <IconButton size="small" onClick={(e) => setAnchor(e.currentTarget)} aria-label="Member actions">
        <MoreHorizIcon fontSize="small" />
      </IconButton>
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={close}>
        <MenuItem
          onClick={async () => {
            await update.mutateAsync({ is_admin: !member.is_admin });
            close();
          }}
        >
          {member.is_admin ? "Demote to user" : "Promote to admin"}
        </MenuItem>
        <MenuItem
          onClick={async () => {
            if (window.confirm(`Remove ${member.email} from the group?`)) {
              await remove.mutateAsync(member.user_id);
            }
            close();
          }}
        >
          Remove from group
        </MenuItem>
      </Menu>
    </Stack>
  );
}

function InvitesTab({ groupId }: { groupId: string }) {
  const invites = useGroupInvites(groupId);
  const create = useCreateInvite(groupId);
  const revoke = useRevokeInvite();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [lastToken, setLastToken] = useState<string | null>(null);
  const [toast, setToast] = useState(false);

  const handleGenerate = () => {
    create.mutate(undefined, {
      onSuccess: (data) => {
        setLastToken(data.token);
      },
    });
    setDialogOpen(true);
  };

  const copyUrl = (token: string) => {
    const url = `${window.location.origin}/invite/${token}`;
    void navigator.clipboard.writeText(url);
    setToast(true);
  };

  const rows = invites.data ?? [];

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="flex-end">
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={handleGenerate}
          disabled={create.isPending}
        >
          New invite
        </Button>
      </Stack>

      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No pending invites.
        </Typography>
      ) : (
        <Stack
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            overflow: "hidden",
            bgcolor: "background.paper",
          }}
        >
          {rows.map((inv, i) => (
            <Stack
              key={inv.id}
              direction="row"
              alignItems="center"
              sx={{
                px: 2,
                py: 1.25,
                gap: 1,
                borderBottom: i < rows.length - 1 ? "1px solid" : "none",
                borderColor: "divider",
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                  flex: 1,
                  minWidth: 0,
                }}
                noWrap
              >
                …{inv.token.slice(-12)}
              </Typography>
              <IconButton size="small" onClick={() => copyUrl(inv.token)} aria-label="Copy invite link">
                <ContentCopyIcon fontSize="small" />
              </IconButton>
              <Button
                size="small"
                color="error"
                onClick={() => revoke.mutate(inv.id)}
                disabled={revoke.isPending}
              >
                Revoke
              </Button>
            </Stack>
          ))}
        </Stack>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>New invite link</DialogTitle>
        <DialogContent>
          {create.isPending && <Typography variant="body2">Generating…</Typography>}
          {create.error instanceof Error && (
            <Alert severity="error">{create.error.message}</Alert>
          )}
          {lastToken && (
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Share this link. It is valid once.
              </Typography>
              <TextField
                size="small"
                fullWidth
                value={`${window.location.origin}/invite/${lastToken}`}
                InputProps={{ readOnly: true, sx: { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 } }}
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {lastToken && (
            <Button onClick={() => copyUrl(lastToken)} startIcon={<ContentCopyIcon />}>
              Copy
            </Button>
          )}
          <Button
            variant="contained"
            onClick={() => {
              setDialogOpen(false);
              setLastToken(null);
            }}
          >
            Done
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar
        open={toast}
        autoHideDuration={2000}
        onClose={() => setToast(false)}
        message="Copied to clipboard"
      />
    </Stack>
  );
}
```

**Note:** Backend `InviteCreate` does not currently take TTL or role parameters; the spec's "role + TTL" modal degrades to "click, get a link". When Plan 1 extensions land, extend this dialog — the current dialog is the minimum viable shape.

**Acceptance:**
- Members tab lists all members with correct role pill.
- Promote/demote toggles `MemberRead.is_admin` and re-renders.
- Remove asks for confirmation and deletes.
- New invite generates a link, copy works.
- Revoke removes the invite row.

- [ ] **Step 2: Manual verify.** Log in as a member of a group, view section, promote a second user, create an invite link, open in an incognito tab, accept it.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/settings/MembersInvitesSection.tsx
git commit -m "feat(settings): Members & Invites tabs with role + revoke + generate"
```

---

## Task 7: `HazardTagsSection` — group-scoped CRUD

**Files:** Replace `src/components/settings/HazardTagsSection.tsx`.

**Rationale:** The old SettingsPage had a hazard-tag list inline. Keep the capability but move it under its own section in the new nav, and match the clinical row style. Reuses `useHazardTags`, `useCreateHazardTag`, `useUpdateHazardTag`, `useDeleteHazardTag`. Edit/create uses a `Dialog` (lighter than `EditDrawer`). Incompatibilities are visible in Plan 2's chemical form via `useIncompatibilities` but managing them belongs on a later subsection — out of Plan 4 scope; note in a TODO.

- [ ] **Step 1: Implement:**

```tsx
import { useState } from "react";
import {
  Box,
  Stack,
  Button,
  IconButton,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { SectionHeader } from "./SectionHeader";
import {
  useHazardTags,
  useCreateHazardTag,
  useUpdateHazardTag,
  useDeleteHazardTag,
} from "../../api/hooks/useHazardTags";
import type { HazardTagRead } from "../../types";

interface Props {
  groupId: string;
}

type DialogState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; tag: HazardTagRead };

export function HazardTagsSection({ groupId }: Props) {
  const query = useHazardTags(groupId);
  const create = useCreateHazardTag(groupId);
  const remove = useDeleteHazardTag(groupId);
  const [dialog, setDialog] = useState<DialogState>({ mode: "closed" });

  const tags = query.data?.items ?? [];

  return (
    <Box>
      <SectionHeader
        title="Hazard tags"
        subtitle="Group-scoped tags used on chemicals. TODO: manage incompatibilities in a follow-up plan."
        actions={
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setDialog({ mode: "create" })}
          >
            New tag
          </Button>
        }
      />

      {tags.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No hazard tags yet. Click <b>New tag</b> to create one.
        </Typography>
      )}

      {tags.length > 0 && (
        <Stack
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            overflow: "hidden",
            bgcolor: "background.paper",
          }}
        >
          {tags.map((t, i) => (
            <Stack
              key={t.id}
              direction="row"
              alignItems="center"
              sx={{
                px: 2,
                py: 1.25,
                gap: 1,
                borderBottom: i < tags.length - 1 ? "1px solid" : "none",
                borderColor: "divider",
              }}
            >
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                  {t.name}
                </Typography>
                {t.description && (
                  <Typography variant="caption" color="text.secondary">
                    {t.description}
                  </Typography>
                )}
              </Box>
              <IconButton
                size="small"
                onClick={() => setDialog({ mode: "edit", tag: t })}
                aria-label={`Edit ${t.name}`}
              >
                <EditIcon fontSize="small" />
              </IconButton>
              <IconButton
                size="small"
                onClick={() => {
                  if (window.confirm(`Delete hazard tag "${t.name}"?`)) {
                    remove.mutate(t.id);
                  }
                }}
                aria-label={`Delete ${t.name}`}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}
        </Stack>
      )}

      <HazardTagDialog
        state={dialog}
        onClose={() => setDialog({ mode: "closed" })}
        groupId={groupId}
      />
    </Box>
  );
}

function HazardTagDialog({
  state,
  onClose,
  groupId,
}: {
  state: DialogState;
  onClose: () => void;
  groupId: string;
}) {
  const create = useCreateHazardTag(groupId);
  const update = useUpdateHazardTag(
    groupId,
    state.mode === "edit" ? state.tag.id : "",
  );

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Reset form when the dialog opens/changes mode.
  // Use a key on the Dialog to force a fresh mount, or this simple effect.
  // Simpler: keyed by mode+id below.
  const key = state.mode === "edit" ? `edit-${state.tag.id}` : state.mode;

  const open = state.mode !== "closed";
  const initial = state.mode === "edit" ? state.tag : null;

  // Initialise fields lazily when opening.
  const [lastKey, setLastKey] = useState<string>("");
  if (open && lastKey !== key) {
    setName(initial?.name ?? "");
    setDescription(initial?.description ?? "");
    setLastKey(key);
  }
  if (!open && lastKey !== "") {
    setLastKey("");
  }

  const saving = create.isPending || update.isPending;
  const err = create.error || update.error;

  const submit = async () => {
    if (state.mode === "create") {
      await create.mutateAsync({ name, description: description || undefined });
    } else if (state.mode === "edit") {
      await update.mutateAsync({ name, description: description || null });
    }
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{state.mode === "edit" ? "Edit hazard tag" : "New hazard tag"}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {err instanceof Error && <Alert severity="error">{err.message}</Alert>}
          <TextField
            label="Name"
            size="small"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            fullWidth
          />
          <TextField
            label="Description"
            size="small"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            multiline
            minRows={2}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={!name.trim() || saving}>
          {state.mode === "edit" ? "Save" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
```

**Acceptance:** Creating, editing, deleting a tag updates the list immediately (React Query invalidation already in the hooks).

- [ ] **Step 2: Manual verify.** Create `Flammable`, edit the description, delete — confirm the list updates.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/settings/HazardTagsSection.tsx
git commit -m "feat(settings): Hazard tags section with group-scoped CRUD"
```

---

## Task 8: `BuildingsSection` + `SystemSection` stubs (SU only)

**Files:** Replace `src/components/settings/BuildingsSection.tsx` and `src/components/settings/SystemSection.tsx`.

**Rationale:** Spec lists these as superuser-only sections. The backend for buildings is not finalised (Plan 3 Storage will formalise the `StorageLocation` tree including buildings). For Plan 4, render placeholder content that matches the clinical style and clearly states the feature is coming. This keeps the nav wired end-to-end — when the backend lands, only the body changes.

- [ ] **Step 1: `BuildingsSection.tsx`:**

```tsx
import { Box, Alert, Typography, Stack } from "@mui/material";
import { SectionHeader } from "./SectionHeader";

export function BuildingsSection() {
  return (
    <Box>
      <SectionHeader
        title="Buildings"
        subtitle="System-wide physical buildings. Groups reference buildings to scope their storage tree."
      />
      <Stack spacing={2}>
        <Alert severity="info">
          Building management ships with the Storage redesign (Plan 3). Until then, manage buildings
          via the FastAPI docs UI at <code>/docs</code>.
        </Alert>
        <Typography variant="body2" color="text.secondary">
          When Plan 3 merges, this section will list all buildings with edit / archive actions and a
          <b> + New building</b> button.
        </Typography>
      </Stack>
    </Box>
  );
}
```

- [ ] **Step 2: `SystemSection.tsx`:**

```tsx
import { Box, Alert, Typography, Stack, Divider } from "@mui/material";
import { SectionHeader } from "./SectionHeader";

export function SystemSection() {
  return (
    <Box>
      <SectionHeader
        title="System"
        subtitle="Global settings for the ChAIMa instance."
      />
      <Stack spacing={2}>
        <Alert severity="info">
          System-wide configuration UI is not part of v1. The backend has sensible defaults and
          configuration is done via environment variables.
        </Alert>
        <Divider />
        <Stack spacing={0.5}>
          <Typography variant="h5">INSTANCE</Typography>
          <Typography variant="body2" color="text.secondary">
            Read-only stub. Future contents: admin email, group-creation policy, PubChem proxy toggle.
          </Typography>
        </Stack>
      </Stack>
    </Box>
  );
}
```

**Acceptance:** Both sections render as SU and do not throw when the hooks they would need do not exist yet.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/settings/BuildingsSection.tsx frontend/src/components/settings/SystemSection.tsx
git commit -m "feat(settings): Buildings and System section stubs for superusers"
```

---

## Task 9: Responsive polish

**Files:** Various (`SettingsPage.tsx`, `SettingsNav.tsx`, section components).

**Rationale:** Default `md` breakpoint behaviours from Task 2/3 should already give a usable mobile layout (nav above content). Walk through at 375 px and confirm.

- [ ] **Step 1: Verify at 375 px:**
  - Left nav becomes a horizontal-ish block above the content (actually a full-width vertical stack, which is fine — it's short).
  - Section headers wrap correctly.
  - Text inputs (email, password, New tag dialog) stay within the viewport.
  - Invite token `TextField` in the dialog has monospaced font without horizontal overflow.
  - `ToggleButtonGroup` for theme fits.

- [ ] **Step 2:** Fix any overflow by adding `minWidth: 0` to flex children, `sx={{ maxWidth: "100%" }}` on text fields, or shrinking `fontSize` where needed.

- [ ] **Step 3: Commit.**

```bash
git add -u frontend/src/pages/SettingsPage.tsx frontend/src/components/settings/
git commit -m "fix(responsive): polish Settings page at mobile breakpoints"
```

---

## Task 10: Playwright E2E for Settings

**Files:** Create `frontend/e2e/settings.spec.ts`.

**Rationale:** One spec covering the two most load-bearing flows: **theme toggle persists across reload**, and **admin generates + revokes an invite**. Password change is tested manually because changing it in E2E would require follow-up cleanup to reset the fixture user.

- [ ] **Step 1: Add `aria-label` attributes** on any selectors that aren't already stable. Specifically:
  - The theme toggle `ToggleButton`s already have `aria-label="Light theme" | "Dark theme"`.
  - The section nav uses `role="button"`; rely on visible text.
  - The invite copy button uses `aria-label="Copy invite link"`.

- [ ] **Step 2: Write the spec:**

```ts
import { test, expect } from "@playwright/test";

test.describe("Settings page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[name="email"]', "admin@chaima.dev");
    await page.fill('input[name="password"]', "changeme");
    await page.click('button[type="submit"]');
    await page.waitForURL("/");
    await page.goto("/settings");
  });

  test("theme toggle persists across reload", async ({ page }) => {
    // Start on Account (default)
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();

    // Flip to dark
    await page.getByRole("button", { name: "Dark theme" }).click();

    // Background should become near-black — check body computed style.
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bg).toMatch(/rgb\(10, 10, 10\)|rgb\(20, 20, 20\)/);

    await page.reload();
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();
    const bgAfter = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bgAfter).toMatch(/rgb\(10, 10, 10\)|rgb\(20, 20, 20\)/);

    // Flip back to keep fixture clean.
    await page.getByRole("button", { name: "Light theme" }).click();
  });

  test("generate and revoke invite", async ({ page }) => {
    // Navigate to Members & Invites
    await page.getByText("Members & Invites", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "Members & Invites" })).toBeVisible();

    // Invites tab
    await page.getByRole("tab", { name: "Pending invites" }).click();

    // Generate new
    await page.getByRole("button", { name: "New invite" }).click();
    await expect(page.getByText("New invite link")).toBeVisible();
    // Wait until the token textbox is populated
    const tokenInput = page.locator('input[readonly]');
    await expect(tokenInput).toHaveValue(/\/invite\/[A-Za-z0-9_-]{10,}/);
    await page.getByRole("button", { name: "Done" }).click();

    // Revoke the first pending invite
    const revokeBtn = page.getByRole("button", { name: "Revoke" }).first();
    await expect(revokeBtn).toBeVisible();
    await revokeBtn.click();
  });

  test("hazard tag create and delete", async ({ page }) => {
    page.on("dialog", (d) => d.accept());
    await page.getByText("Hazard tags", { exact: true }).click();
    await page.getByRole("button", { name: "New tag" }).click();
    await page.getByLabel("Name").fill("E2E Flammable");
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText("E2E Flammable")).toBeVisible();

    await page.getByLabel("Delete E2E Flammable").click();
    await expect(page.getByText("E2E Flammable")).not.toBeVisible();
  });
});
```

- [ ] **Step 3: Run locally.**

```bash
cd frontend
npm run test:e2e -- settings.spec.ts
```

Fix any selector drift — inspect with `npx playwright test --debug` if needed.

- [ ] **Step 4: Commit.**

```bash
git add frontend/e2e/settings.spec.ts
# plus any aria-label additions
git commit -m "test(e2e): Settings — theme persist, invite generate/revoke, hazard tag CRUD"
```

---

## Plan 4 complete

After Task 10, the Settings page is fully rewritten against the clinical theme with:

- **Account**: email edit, password change, Light/Dark theme toggle (wired to `PATCH /users/me`), sign out
- **Group**: current group info + main-group picker
- **Members & Invites**: tabbed view with promote/demote/remove + generate/copy/revoke invite links
- **Hazard tags**: group-scoped CRUD in the new row style
- **Buildings / System**: SU-only stubs awaiting Plan 3 / follow-up work

Dark mode is now user-controllable end-to-end (theme factory from Plan 2 + toggle from Plan 4). Plan 3 (Storage page) is independent and can land in parallel without conflicts — it only touches `src/pages/StoragePage.tsx`, `src/components/Storage*`, and (later) a `BuildingsSection` backfill that replaces the stub from Task 8.

Known gaps handed to later mini-plans:
- **Real admin role gating** — `RoleGate allow={["admin"]}` still evaluates as "any group member" because `UserRead.is_admin` does not exist. Members & Invites currently renders for all members. When backend roles land, flip the gate.
- **Password re-auth** — `PATCH /users/me` doesn't require current password. Harden if security posture tightens.
- **Invite TTL and role preset** — backend `InviteCreate` takes no params; enhance when schema extends.
- **Hazard tag incompatibilities UI** — out of scope, tracked as follow-up.
- **Buildings / System real content** — depends on Plan 3 storage tree and future global-settings backend.

Next plan after Plan 4: polish pass or follow-up mini-plans from the gaps list.
