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
import { SectionHeader } from "./SectionHeader";
import {
  useAllGroups,
  useCreateGroup,
  useUpdateGroup,
} from "../../api/hooks/useGroups";
import type { GroupRead } from "../../types";

type DialogState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; group: GroupRead };

export function GroupsAdminSection() {
  const query = useAllGroups();
  const [dialog, setDialog] = useState<DialogState>({ mode: "closed" });

  const groups = query.data ?? [];

  return (
    <Box>
      <SectionHeader
        title="Groups"
        subtitle="All groups in the system. Only visible to superusers."
        actions={
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setDialog({ mode: "create" })}
          >
            New group
          </Button>
        }
      />

      {groups.length === 0 && !query.isLoading && (
        <Typography variant="body2" color="text.secondary">
          No groups yet. Click <b>New group</b> to create one.
        </Typography>
      )}

      {groups.length > 0 && (
        <Stack
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            overflow: "hidden",
            bgcolor: "background.paper",
          }}
        >
          {groups.map((g, i) => (
            <Stack
              key={g.id}
              direction="row"
              sx={{
                px: 2,
                py: 1.25,
                gap: 1,
                alignItems: "center",
                borderBottom: i < groups.length - 1 ? "1px solid" : "none",
                borderColor: "divider",
              }}
            >
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="h6" sx={{ fontWeight: 500 }} noWrap>
                  {g.name}
                </Typography>
                {g.description && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: "block" }}
                    noWrap
                  >
                    {g.description}
                  </Typography>
                )}
              </Box>
              <IconButton
                size="small"
                onClick={() => setDialog({ mode: "edit", group: g })}
                aria-label={`Edit ${g.name}`}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}
        </Stack>
      )}

      <GroupDialog
        state={dialog}
        onClose={() => setDialog({ mode: "closed" })}
      />
    </Box>
  );
}

function GroupDialog({
  state,
  onClose,
}: {
  state: DialogState;
  onClose: () => void;
}) {
  const create = useCreateGroup();
  const update = useUpdateGroup(state.mode === "edit" ? state.group.id : "");

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const key = state.mode === "edit" ? `edit-${state.group.id}` : state.mode;

  const open = state.mode !== "closed";
  const initial = state.mode === "edit" ? state.group : null;

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
      <DialogTitle>{state.mode === "edit" ? "Edit group" : "New group"}</DialogTitle>
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
            required
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
