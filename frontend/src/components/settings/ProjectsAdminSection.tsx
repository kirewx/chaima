import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import ArchiveIcon from "@mui/icons-material/Archive";
import { useQueryClient } from "@tanstack/react-query";
import client from "../../api/client";
import {
  useProjects,
  useCreateProject,
  useArchiveProject,
} from "../../api/hooks/useProjects";
import { SectionHeader } from "./SectionHeader";
import type { ProjectRead } from "../../types";

interface Props {
  groupId: string;
}

type DialogState =
  | { mode: "closed" }
  | { mode: "create" }
  | { mode: "edit"; project: ProjectRead };

export function ProjectsAdminSection({ groupId }: Props) {
  const [showArchived, setShowArchived] = useState(false);
  const { data, isLoading } = useProjects(groupId, showArchived);
  const projects = data?.items ?? [];

  const qc = useQueryClient();
  const create = useCreateProject(groupId);
  const archive = useArchiveProject(groupId);
  const [dialog, setDialog] = useState<DialogState>({ mode: "closed" });
  const [name, setName] = useState("");

  const submit = async () => {
    if (dialog.mode === "create") {
      await create.mutateAsync({ name });
    } else if (dialog.mode === "edit") {
      await client.patch(`/groups/${groupId}/projects/${dialog.project.id}`, { name });
      qc.invalidateQueries({ queryKey: ["projects", groupId] });
    }
    setDialog({ mode: "closed" });
    setName("");
  };

  return (
    <Box>
      <SectionHeader
        title="Projects"
        subtitle="Group-scoped projects used to tag chemical orders for budget tracking."
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => setShowArchived((s) => !s)}
            >
              {showArchived ? "Hide archived" : "Show archived"}
            </Button>
            <Button
              size="small"
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => {
                setName("");
                setDialog({ mode: "create" });
              }}
            >
              New project
            </Button>
          </Stack>
        }
      />

      {isLoading && (
        <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
          <CircularProgress size={20} />
        </Box>
      )}

      {!isLoading && projects.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No projects yet. Click <b>New project</b> to add one.
        </Typography>
      )}

      {projects.length > 0 && (
        <Stack
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            overflow: "hidden",
            bgcolor: "background.paper",
          }}
        >
          {projects.map((p, i) => (
            <Stack
              key={p.id}
              direction="row"
              sx={{
                px: 2,
                py: 1.25,
                gap: 1,
                alignItems: "center",
                borderBottom: i < projects.length - 1 ? "1px solid" : "none",
                borderColor: "divider",
              }}
            >
              <Box sx={{ flex: 1 }}>
                <Typography variant="body2">{p.name}</Typography>
                {p.is_archived && (
                  <Chip size="small" label="Archived" sx={{ mt: 0.5 }} />
                )}
              </Box>
              <IconButton
                size="small"
                onClick={() => {
                  setName(p.name);
                  setDialog({ mode: "edit", project: p });
                }}
              >
                <EditIcon fontSize="small" />
              </IconButton>
              {!p.is_archived && (
                <IconButton
                  size="small"
                  onClick={() => archive.mutate(p.id)}
                >
                  <ArchiveIcon fontSize="small" />
                </IconButton>
              )}
            </Stack>
          ))}
        </Stack>
      )}

      <Dialog
        open={dialog.mode !== "closed"}
        onClose={() => setDialog({ mode: "closed" })}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>
          {dialog.mode === "create" ? "New project" : "Edit project"}
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            margin="dense"
            label="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          {create.error instanceof Error && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {create.error.message}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog({ mode: "closed" })}>Cancel</Button>
          <Button onClick={submit} variant="contained" disabled={!name.trim()}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
