import {
  Button,
  Stack,
  TextField,
  FormControlLabel,
  Switch,
  Alert,
  Typography,
  CircularProgress,
  Box,
} from "@mui/material";
import { useState, useEffect } from "react";
import {
  useCreateChemical,
  useUpdateChemical,
  useChemicalDetail,
} from "../../api/hooks/useChemicals";
import { useCurrentUser } from "../../api/hooks/useAuth";

interface Props {
  chemicalId?: string;
  onDone: () => void;
}

export function ChemicalForm({ chemicalId, onDone }: Props) {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";
  const existing = useChemicalDetail(groupId, chemicalId ?? "");
  const create = useCreateChemical(groupId);
  const update = useUpdateChemical(groupId, chemicalId ?? "");

  const [name, setName] = useState("");
  const [cas, setCas] = useState("");
  const [comment, setComment] = useState("");
  const [isSecret, setIsSecret] = useState(false);

  useEffect(() => {
    if (existing.data) {
      setName(existing.data.name);
      setCas(existing.data.cas ?? "");
      setComment(existing.data.comment ?? "");
      setIsSecret(existing.data.is_secret);
    }
  }, [existing.data]);

  if (chemicalId && existing.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  const saving = create.isPending || update.isPending;
  const err = create.error || update.error;

  const onSubmit = async () => {
    const payload = {
      name: name.trim(),
      cas: cas.trim() || null,
      comment: comment.trim() || null,
      is_secret: isSecret,
    };
    if (chemicalId) {
      await update.mutateAsync(payload);
    } else {
      await create.mutateAsync(payload);
    }
    onDone();
  };

  return (
    <Stack spacing={2}>
      {err instanceof Error && <Alert severity="error">{err.message}</Alert>}

      <TextField
        label="Name"
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
        size="small"
        autoFocus
      />
      <TextField
        label="CAS number"
        value={cas}
        onChange={(e) => setCas(e.target.value)}
        size="small"
        helperText="Optional. Leave blank for internal materials."
      />
      <TextField
        label="Comment"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        multiline
        minRows={2}
        size="small"
      />
      <FormControlLabel
        control={
          <Switch
            checked={isSecret}
            onChange={(_, v) => setIsSecret(v)}
          />
        }
        label={
          <Stack>
            <Typography variant="body2">Mark as secret</Typography>
            <Typography variant="caption" color="text.secondary">
              Only you and system admins will see this chemical.
            </Typography>
          </Stack>
        }
        sx={{ alignItems: "flex-start", m: 0 }}
      />

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", mt: 2 }}>
        <Button onClick={onDone} disabled={saving}>
          Cancel
        </Button>
        <Button
          variant="contained"
          disabled={saving || !name.trim()}
          onClick={onSubmit}
        >
          {chemicalId ? "Save" : "Create"}
        </Button>
      </Stack>
    </Stack>
  );
}
