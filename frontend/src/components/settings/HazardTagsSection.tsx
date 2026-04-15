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
              sx={{
                px: 2,
                py: 1.25,
                gap: 1,
                alignItems: "center",
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

  const key = state.mode === "edit" ? `edit-${state.tag.id}` : state.mode;

  const open = state.mode !== "closed";
  const initial = state.mode === "edit" ? state.tag : null;

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
