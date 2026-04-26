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
  Autocomplete,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import LinkOffIcon from "@mui/icons-material/LinkOff";
import { SectionHeader } from "./SectionHeader";
import {
  useHazardTags,
  useCreateHazardTag,
  useUpdateHazardTag,
  useDeleteHazardTag,
} from "../../api/hooks/useHazardTags";
import {
  useHazardTagIncompatibilities,
  useCreateIncompatibility,
  useDeleteIncompatibility,
} from "../../api/hooks/useHazardTagIncompatibilities";
import type { HazardTagRead } from "../../types";

interface Props {
  groupId: string;
}

type DialogState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; tag: HazardTagRead }
  | { mode: "incompatibilities"; tag: HazardTagRead };

export function HazardTagsSection({ groupId }: Props) {
  const query = useHazardTags(groupId);
  const remove = useDeleteHazardTag(groupId);
  const [dialog, setDialog] = useState<DialogState>({ mode: "closed" });

  const tags = query.data?.items ?? [];

  return (
    <Box>
      <SectionHeader
        title="Hazard tags"
        subtitle="Group-scoped tags used on chemicals. Click the link icon on a tag to manage incompatibilities."
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
                <Typography variant="body1" sx={{ fontWeight: 500 }} noWrap>
                  {t.name}
                </Typography>
                {t.description && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: "block" }}
                    noWrap
                  >
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
                onClick={() => setDialog({ mode: "incompatibilities", tag: t })}
                aria-label={`Manage incompatibilities for ${t.name}`}
              >
                <LinkOffIcon fontSize="small" />
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

      <IncompatibilityDialog
        open={dialog.mode === "incompatibilities"}
        tag={dialog.mode === "incompatibilities" ? dialog.tag : null}
        groupId={groupId}
        allTags={tags}
        onClose={() => setDialog({ mode: "closed" })}
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
