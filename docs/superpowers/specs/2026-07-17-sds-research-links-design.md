# SDS Research Links ("Hilfsliste") — Design

**Date:** 2026-07-17
**Status:** Approved by user (chat), pending spec review
**Prerequisite:** `feat/gestis-deeplinks` is merged to `main` first; this feature branches from `main` afterwards.

## Problem

Chemicals without an uploaded SDS require manual research. Click-testing (see
`notebooks/sds-links-schnelltest.html`, untracked) showed that vendor search URLs
(Merck, Carl Roth, Fisher, VWR, TCI) resolve poorly for specialized chemicals,
while plain Google searches on the CAS number work reliably:

- `"{cas}"` — finds the chemical and its SDS quickly, even for specialized ones
- `"{cas}" sicherheitsdatenblatt filetype:pdf` — often hits the SDS PDF directly
  (frequently Carl Roth) for well-known chemicals

Goal: give the group's SDS-responsible person (a group admin) these two research
links directly in the chemical view so missing SDS can be backfilled quickly.
Long-term, SDS mapping at order time may supersede this; the list is the
pragmatic interim tool.

## Decisions (user-confirmed)

1. **Link set:** Google CAS search + Google SDS-PDF search only. No vendor links.
2. **Presentation:** Variant A — two flat link rows with a magnifier icon,
   directly below the GESTIS row in the ChemicalInfoBox Links section.
3. **Visibility:** only group admins, only while the chemical has **no** SDS
   uploaded, and only when the chemical has a CAS number. (No CAS → no rows;
   name-based search is a possible later extension, out of scope.)
4. **Toggle:** per group, persisted in the DB, default **on**. Group admins
   switch the display on/off in Settings → Chemicals.

## Design

### Backend

- New column `show_sds_research_links: bool` on `Group`
  (`server_default="1"`, non-nullable). Alembic migration on top of the
  then-current head (post-GESTIS-merge: `d2f4a6b8c0e2`).
- Field added to `GroupRead` and `GroupUpdate` schemas. No new endpoints —
  the existing admin-gated `PATCH /groups/{group_id}` handles updates.
- No backend link logic; URLs are constructed client-side.

### Frontend — ChemicalInfoBox

Below the GESTIS link row, render two rows when ALL hold:

- current user is group admin (`useIsGroupAdmin`)
- `!chemical.sds_path`
- group's `show_sds_research_links` is true (group fetched via existing hook)
- `chemical.cas` is set

Rows (styling identical to existing link rows: 11px link, 12px icon,
`target="_blank" rel="noopener"`, CAS URL-encoded):

- `CAS-Recherche (Google)` → `https://www.google.com/search?q=%22{cas}%22`
- `SDS-PDF-Suche (Google)` →
  `https://www.google.com/search?q=%22{cas}%22+sicherheitsdatenblatt+filetype%3Apdf`

### Frontend — Settings → Chemicals

In `ChemicalsAdminSection` (next to the GESTIS backfill control): a switch
"SDS-Recherche-Links anzeigen" with a one-line help text, wired to the group
patch mutation, invalidating the group query on success.

### Testing

- Backend: `show_sds_research_links` present in group read; patch roundtrip
  by admin; non-admin patch rejected (existing pattern).
- Frontend: production build clean.
- E2E: rows appear for an admin on a CAS-bearing chemical without SDS;
  disappear after toggling off in Settings.

## Out of scope

- Vendor search links (tested, rejected for now)
- Name-based search fallback for chemicals without CAS
- SDS mapping at order time / per-supplier SDS links (future idea via Orders)
