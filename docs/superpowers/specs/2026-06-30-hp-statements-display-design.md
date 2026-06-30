# H + P Statements Display — Design

**Date:** 2026-06-30
**Status:** Approved
**Scope:** Frontend display only. This refines **Task 10** of the implementation plan
`docs/superpowers/plans/2026-06-30-pubchem-precautionary-statements.md`. Backend
tasks (catalog, models, migration, seed, parser, schema, persistence, refetch —
Tasks 1–9) are unchanged.

## Goal

Surface a chemical's GHS **Hazard statements (H)** and **Precautionary
statements (P)** as a textual overview, opened from a link in the chemical
detail panel. Today only GHS *pictograms* (icons) are shown; the underlying H/P
*text* is not visible anywhere.

## Placement

In `ChemicalInfoBox.tsx`, inside the existing **Links** section (alongside the
PubChem and SDS links). The current **Hazards** section (signal-word chip, GHS
pictogram row, hazard-tag chips) stays exactly as it is — this feature is
purely additive.

```
Hazards                          (unchanged)
  [Danger]
  ⬡ ⬡ ⬡            ← GHS pictograms, hover = code/text
  [Corrosive]

Links
  🔗 PubChem 180
  📄 Safety data sheet  (or "No SDS uploaded")
  ⚠ H + P statements (3·H 19·P)   ← NEW trigger (opens dialog)
```

## Trigger element (in the Links section)

- **When the chemical has ≥1 H-code OR ≥1 P-code:** a clickable link/button
  labeled `H + P statements (N·H M·P)`, where `N = ghsCodes.length` and
  `M = pStatements.length`. **Both counts are always shown**, even when one is
  zero (e.g. `(3·H 0·P)`) — simpler and predictable. Styled like the other
  links in the section (small font, primary color, a warning/hazard icon).
  Clicking opens the dialog.
- **When the chemical has no H and no P codes:** a non-clickable, greyed-out
  line `No H/P statements` — consistent with how `No SDS uploaded` renders when
  no SDS is present. This actively signals "checked, nothing here" rather than
  hiding the row.

## New component: `HazardStatementsDialog.tsx`

A self-contained MUI `Dialog`. Closeable via the × button, ESC, and backdrop
click (MUI default). Created at `frontend/src/components/HazardStatementsDialog.tsx`.

**Props (the only interface — fully isolated, testable in isolation):**

```typescript
interface Props {
  open: boolean;
  onClose: () => void;
  chemicalName: string;
  ghsCodes: GHSCodeRead[];
  pStatements: PStatementRead[];
}
```

**Content, top to bottom:**

1. **Title bar:** `Hazard & precautionary statements` plus the chemical name as
   context (e.g. as a subtitle), and a close (×) button.
2. **Header block:** the GHS pictograms + the worst signal word
   (Danger/Warning), reusing the existing `GHSPictogramRow` component and the
   `worstSignalWord(ghsCodes)` helper currently in `ChemicalInfoBox.tsx`. Shown
   only when there is at least one pictogram / a signal word.
   - To reuse `worstSignalWord` from both files, lift it out of
     `ChemicalInfoBox.tsx` into a small shared module
     (`frontend/src/components/hazardSignal.ts`) and import it in both places.
     This avoids duplicating the logic.
3. **Hazard statements (H)** section — a labeled list, one row per H-code:
   `H225 — Highly flammable liquid and vapor` (full text from
   `GHSCodeRead.description`). Hidden if `ghsCodes` is empty.
4. **Precautionary statements (P)** section — a row of MUI `Chip`s, each
   showing the P-code (`P210`, `P305+P351+P338`, …). Hovering a chip shows the
   full statement text via a `Tooltip` (same interaction model as the GHS
   pictograms today). Hidden if `pStatements` is empty.

The P-chips-with-tooltip block is the `PStatementList` component from the plan's
original Task 10 — reused **inside the dialog** rather than rendered inline in
the Hazards section.

## Data flow

`ChemicalInfoBox` already receives `ghsCodes: GHSCodeRead[]`. It additionally
receives a new `pStatements: PStatementRead[]` prop. Both are threaded from
`ChemicalList.tsx` out of the loaded `ChemicalDetail`:

```tsx
<ChemicalInfoBox
  ...
  ghsCodes={detail?.ghs_codes ?? []}
  pStatements={detail?.precautionary_codes ?? []}
/>
```

`ChemicalInfoBox` owns a local `const [hpOpen, setHpOpen] = useState(false)`
state, renders the trigger link (which calls `setHpOpen(true)`), and renders
`<HazardStatementsDialog open={hpOpen} onClose={() => setHpOpen(false)} ... />`.

`ChemicalDetail.precautionary_codes` (type `PStatementRead[]`) is produced by
the backend detail endpoint (plan Task 8) and typed in `frontend/src/types/index.ts`
(plan Task 10, types portion).

## Components & responsibilities

| Unit | Responsibility | Depends on |
|---|---|---|
| `HazardStatementsDialog.tsx` (new) | Render the H/P overview modal given two lists + name | `GHSPictogramRow`, `hazardSignal.ts`, MUI `Dialog/Tooltip/Chip` |
| `hazardSignal.ts` (new) | `worstSignalWord(codes)` shared helper | none |
| `ChemicalInfoBox.tsx` (modified) | Render trigger link (or disabled empty-state) + own dialog open/close state | `HazardStatementsDialog`, `hazardSignal.ts` |
| `ChemicalList.tsx` (modified) | Thread `pStatements` prop from loaded detail | — |
| `frontend/src/types/index.ts` (modified) | `PStatementRead`; extend `ChemicalDetail`, `PubChemLookupResult` | — |

## Out of scope

- No editing of P-codes from the dialog (read-only overview). Manual GHS/P
  editing remains via existing admin flows / refetch.
- No change to the Hazards section's pictogram/tag rendering.
- No literal browser `window.open` popup — explicitly an in-app MUI Dialog.

## Testing

- `HazardStatementsDialog` renders H rows with descriptions and P chips with
  tooltips given sample lists; renders header pictograms/signal only when
  present; hides an empty H or P section.
- `ChemicalInfoBox` shows the trigger link with correct counts when codes
  exist, and the disabled `No H/P statements` line when both lists are empty.
- Frontend typecheck/build passes (`npm run build`).
