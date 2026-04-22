import { useState } from "react";
import {
  Alert, Box, Button, MenuItem, Paper, Stack, Stepper, Step, StepLabel,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { SectionHeader } from "./SectionHeader";
import { useImportPreview } from "../../api/hooks/useImport";
import type { ImportPreviewResponse, ImportTarget } from "../../types";
import { IMPORT_TARGETS } from "../../types";

type WizardState =
  | { step: "upload" }
  | { step: "columns"; preview: ImportPreviewResponse; file: File }
  | { step: "locations"; preview: ImportPreviewResponse; columnMapping: Record<string, string>; quCombined: string | null }
  | { step: "review" }
  | { step: "done"; summary: unknown };

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
              columnMapping: mapping,
              quCombined: qu,
            });
          }}
        />
      )}
      {state.step === "locations" && (
        <Alert severity="info">Location mapping — coming in Task 2.10.</Alert>
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
