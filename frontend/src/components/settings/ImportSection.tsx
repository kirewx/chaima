import { useState } from "react";
import {
  Alert, Box, Button, MenuItem, Paper, Stack, Stepper, Step, StepLabel,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { SectionHeader } from "./SectionHeader";
import { useImportPreview, useImportCommit } from "../../api/hooks/useImport";
import type {
  ImportPreviewResponse, ImportTarget, ImportLocationMapping,
  ImportChemicalGroup, ImportCommitBody, ImportCommitResponse,
} from "../../types";
import { IMPORT_TARGETS } from "../../types";
import { useStorageTree } from "../../api/hooks/useStorageLocations";
import LocationPicker from "../LocationPicker";

type WizardState =
  | { step: "upload" }
  | { step: "columns"; preview: ImportPreviewResponse; file: File }
  | { step: "locations"; preview: ImportPreviewResponse; file: File;
      columnMapping: Record<string, string>; quCombined: string | null }
  | { step: "review"; preview: ImportPreviewResponse; file: File;
      columnMapping: Record<string, string>; quCombined: string | null;
      locations: ImportLocationMapping[] }
  | { step: "done"; summary: ImportCommitResponse };

interface Props {
  groupId: string;
}

export function ImportSection({ groupId }: Props) {
  const [state, setState] = useState<WizardState>({ step: "upload" });
  const preview = useImportPreview(groupId);

  const steps = ["Upload", "Columns", "Locations", "Review", "Done"];
  const activeStep = { upload: 0, columns: 1, locations: 2, review: 3, done: 4 }[state.step];

  return (
    <Box>
      <SectionHeader
        title="Import data"
        subtitle="Ingest a lab inventory from Excel or CSV. One-time setup — import once, then use chaima going forward."
      />

      <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
        {steps.map((s) => <Step key={s}><StepLabel>{s}</StepLabel></Step>)}
      </Stepper>

      {state.step === "upload" && (
        <UploadStep
          onPicked={async (file) => {
            const res = await preview.mutateAsync({ file });
            setState({ step: "columns", preview: res, file });
          }}
          loading={preview.isPending}
          error={preview.error}
        />
      )}

      {state.step === "columns" && (
        <ColumnMappingStep
          preview={state.preview}
          onBack={() => setState({ step: "upload" })}
          onNext={(mapping, qu) => {
            setState({
              step: "locations",
              preview: state.preview,
              file: state.file,
              columnMapping: mapping,
              quCombined: qu,
            });
          }}
        />
      )}
      {state.step === "locations" && (
        <LocationMappingStep
          groupId={groupId}
          distinct={distinctLocations(state.preview.rows, state.preview.columns, state.columnMapping)}
          onBack={() =>
            setState({ step: "columns", preview: state.preview, file: state.file })
          }
          onNext={(mappings) => {
            setState({
              step: "review",
              preview: state.preview,
              file: state.file,
              columnMapping: state.columnMapping,
              quCombined: state.quCombined,
              locations: mappings,
            });
          }}
        />
      )}
      {state.step === "review" && (
        <ChemicalReviewStep
          groupId={groupId}
          preview={state.preview}
          columnMapping={state.columnMapping}
          quCombined={state.quCombined}
          locations={state.locations}
          onBack={() =>
            setState({
              step: "locations",
              preview: state.preview,
              file: state.file,
              columnMapping: state.columnMapping,
              quCombined: state.quCombined,
            })}
          onDone={(summary) => setState({ step: "done", summary })}
        />
      )}
      {state.step === "done" && (
        <Alert severity="success">
          Created {state.summary.created_chemicals} chemicals, {state.summary.created_containers} containers,{" "}
          {state.summary.created_locations} new locations.
          <Button sx={{ ml: 2 }} onClick={() => setState({ step: "upload" })}>Import another</Button>
        </Alert>
      )}
    </Box>
  );
}

function UploadStep({
  onPicked, loading, error,
}: {
  onPicked: (file: File) => void;
  loading: boolean;
  error: unknown;
}) {
  return (
    <Stack spacing={2} sx={{ maxWidth: 500 }}>
      <Typography variant="body2" color="text.secondary">
        Accepted formats: <b>.xlsx</b>, <b>.csv</b>. Max size: 5 MB.
      </Typography>
      <Button
        variant="contained"
        component="label"
        startIcon={<UploadFileIcon />}
        disabled={loading}
      >
        {loading ? "Reading\u2026" : "Choose file"}
        <input
          type="file"
          hidden
          accept=".xlsx,.csv"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onPicked(f);
          }}
        />
      </Button>
      {error instanceof Error && (
        <Alert severity="error">{error.message}</Alert>
      )}
    </Stack>
  );
}

function ColumnMappingStep({
  preview,
  onBack,
  onNext,
}: {
  preview: ImportPreviewResponse;
  onBack: () => void;
  onNext: (mapping: Record<string, string>, qu: string | null) => void;
}) {
  const [mapping, setMapping] = useState<Record<string, string>>(preview.detected_mapping);

  const quCombined = Object.entries(mapping).find(([, t]) => t === "quantity_unit_combined")?.[0] ?? null;

  const hasName = Object.values(mapping).includes("name");
  const hasQty = Object.values(mapping).includes("quantity") || quCombined !== null;
  const canProceed = hasName && hasQty;

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Map each column to a chaima field. Columns not needed: choose <b>ignore</b>.
        Required: at least one <b>name</b> and either <b>quantity</b> or <b>quantity_unit_combined</b>.
      </Typography>

      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Source column</TableCell>
              <TableCell>Chaima field</TableCell>
              <TableCell>Sample values</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {preview.columns.map((col, colIdx) => (
              <TableRow key={col}>
                <TableCell sx={{ fontWeight: 500 }}>{col}</TableCell>
                <TableCell>
                  <TextField
                    select size="small" value={mapping[col] ?? "ignore"}
                    onChange={(e) =>
                      setMapping((m) => ({ ...m, [col]: e.target.value as ImportTarget }))
                    }
                    sx={{ minWidth: 200 }}
                  >
                    {IMPORT_TARGETS.map((t) => (
                      <MenuItem key={t} value={t}>{t}</MenuItem>
                    ))}
                  </TextField>
                </TableCell>
                <TableCell sx={{ color: "text.secondary", fontSize: 12 }}>
                  {preview.rows.slice(0, 3).map((r) => r[colIdx]).filter(Boolean).join(", ")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      {!canProceed && (
        <Alert severity="warning">
          At least one column must be mapped to <b>name</b>, and one to either <b>quantity</b> or <b>quantity_unit_combined</b>.
        </Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" disabled={!canProceed} onClick={() => onNext(mapping, quCombined)}>
          Next
        </Button>
      </Stack>
    </Stack>
  );
}

function distinctLocations(rows: string[][], columns: string[], mapping: Record<string, string>): string[] {
  const colIdx = columns.findIndex((c) => mapping[c] === "location_text");
  if (colIdx < 0) return [];
  const set = new Set<string>();
  for (const r of rows) {
    const v = (r[colIdx] ?? "").trim();
    if (v) set.add(v);
  }
  return Array.from(set).sort();
}

function LocationMappingStep({
  groupId,
  distinct,
  onBack,
  onNext,
}: {
  groupId: string;
  distinct: string[];
  onBack: () => void;
  onNext: (mappings: ImportLocationMapping[]) => void;
}) {
  const { data: tree = [] } = useStorageTree(groupId);
  const [rows, setRows] = useState<Record<string, { mode: "existing" | "new"; location_id?: string; new_name?: string; parent_id?: string | null }>>(() => {
    const init: Record<string, { mode: "new"; new_name: string }> = {};
    for (const d of distinct) init[d] = { mode: "new", new_name: d };
    return init;
  });
  const [pickerFor, setPickerFor] = useState<string | null>(null);

  const allMapped = distinct.every((d) => {
    const r = rows[d];
    if (!r) return false;
    if (r.mode === "existing") return !!r.location_id;
    return (r.new_name ?? "").trim() !== "";
  });

  const submit = () => {
    const out: ImportLocationMapping[] = distinct.map((d) => {
      const r = rows[d];
      if (r.mode === "existing") {
        return { source_text: d, location_id: r.location_id ?? null, new_location: null };
      }
      return {
        source_text: d,
        location_id: null,
        new_location: { name: (r.new_name ?? "").trim(), parent_id: r.parent_id ?? null },
      };
    });
    onNext(out);
  };

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        Map each distinct location string to an existing storage location or create a new one.
        Newly created ones are flat (no parent) by default.
      </Typography>

      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Source text</TableCell>
              <TableCell>Mode</TableCell>
              <TableCell>Target</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {distinct.map((d) => {
              const r = rows[d];
              return (
                <TableRow key={d}>
                  <TableCell sx={{ fontWeight: 500 }}>{d}</TableCell>
                  <TableCell>
                    <TextField
                      select size="small" value={r.mode}
                      onChange={(e) => {
                        const mode = e.target.value as "existing" | "new";
                        setRows((s) => ({ ...s, [d]: mode === "existing"
                          ? { mode: "existing" }
                          : { mode: "new", new_name: d } }));
                      }}
                    >
                      <MenuItem value="existing">Pick existing</MenuItem>
                      <MenuItem value="new">Create new</MenuItem>
                    </TextField>
                  </TableCell>
                  <TableCell>
                    {r.mode === "existing" ? (
                      <Button size="small" variant="outlined" onClick={() => setPickerFor(d)}>
                        {r.location_id ? "Change\u2026" : "Pick location"}
                      </Button>
                    ) : (
                      <TextField
                        size="small"
                        value={r.new_name ?? ""}
                        onChange={(e) =>
                          setRows((s) => ({ ...s, [d]: { ...s[d], new_name: e.target.value } }))
                        }
                      />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Paper>

      <LocationPicker
        open={pickerFor !== null}
        onClose={() => setPickerFor(null)}
        onSelect={(id) => {
          if (pickerFor) {
            setRows((s) => ({ ...s, [pickerFor]: { mode: "existing", location_id: id } }));
          }
          setPickerFor(null);
        }}
        tree={tree}
      />

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        <Button onClick={onBack}>Back</Button>
        <Button variant="contained" disabled={!allMapped} onClick={submit}>
          Next
        </Button>
      </Stack>
    </Stack>
  );
}

function ChemicalReviewStep({
  groupId, preview, columnMapping, quCombined, locations, onBack, onDone,
}: {
  groupId: string;
  preview: ImportPreviewResponse;
  columnMapping: Record<string, string>;
  quCombined: string | null;
  locations: ImportLocationMapping[];
  onBack: () => void;
  onDone: (r: ImportCommitResponse) => void;
}) {
  const commit = useImportCommit(groupId);

  const groups = groupOnClient(preview, columnMapping);

  const submit = async () => {
    const body: ImportCommitBody = {
      column_mapping: columnMapping,
      quantity_unit_combined_column: quCombined,
      columns: preview.columns,
      rows: preview.rows,
      location_mapping: locations,
      chemical_groups: groups,
    };
    const r = await commit.mutateAsync(body);
    onDone(r);
  };

  return (
    <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">
        {groups.length} chemicals will be created, {preview.row_count} containers total.
        Review before committing.
      </Typography>

      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Chemical</TableCell>
              <TableCell>CAS</TableCell>
              <TableCell>Container count</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {groups.map((g, i) => (
              <TableRow key={i}>
                <TableCell>{g.canonical_name}</TableCell>
                <TableCell>{g.canonical_cas ?? "\u2014"}</TableCell>
                <TableCell>{g.row_indices.length}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      {commit.error instanceof Error && (
        <Alert severity="error">
          {commit.error.message}
        </Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        <Button onClick={onBack} disabled={commit.isPending}>Back</Button>
        <Button variant="contained" onClick={submit} disabled={commit.isPending}>
          {commit.isPending ? "Importing\u2026" : "Commit import"}
        </Button>
      </Stack>
    </Stack>
  );
}

function groupOnClient(
  preview: ImportPreviewResponse,
  mapping: Record<string, string>,
): ImportChemicalGroup[] {
  const nameIdx = preview.columns.findIndex((c) => mapping[c] === "name");
  const casIdx = preview.columns.findIndex((c) => mapping[c] === "cas");
  const buckets = new Map<string, ImportChemicalGroup>();
  for (let i = 0; i < preview.rows.length; i++) {
    const name = (preview.rows[i][nameIdx] ?? "").trim();
    const cas = casIdx >= 0 ? (preview.rows[i][casIdx] ?? "").trim() : "";
    const key = cas ? `cas:${cas}` : `name:${name.toLowerCase()}`;
    const existing = buckets.get(key);
    if (existing) {
      existing.row_indices.push(i);
    } else {
      buckets.set(key, {
        canonical_name: name,
        canonical_cas: cas || null,
        row_indices: [i],
      });
    }
  }
  return Array.from(buckets.values());
}
