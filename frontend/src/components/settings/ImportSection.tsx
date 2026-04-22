import { useState } from "react";
import { Alert, Box, Button, Stack, Stepper, Step, StepLabel, Typography } from "@mui/material";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { SectionHeader } from "./SectionHeader";
import { useImportPreview } from "../../api/hooks/useImport";
import type { ImportPreviewResponse } from "../../types";

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
        <Alert severity="info">Column mapping — coming in Task 2.9.</Alert>
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
