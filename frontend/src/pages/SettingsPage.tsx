import { useState } from "react";
import {
  Box,
  Typography,
  TextField,
  MenuItem,
  Button,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";
import { useGroupOptional } from "../components/GroupContext";
import { useGroups } from "../api/hooks/useGroups";
import { useCurrentUser, useLogout } from "../api/hooks/useAuth";
import {
  useSuppliers,
  useCreateSupplier,
  useUpdateSupplier,
  useDeleteSupplier,
} from "../api/hooks/useSuppliers";
import {
  useHazardTags,
  useCreateHazardTag,
  useUpdateHazardTag,
  useDeleteHazardTag,
} from "../api/hooks/useHazardTags";

export default function SettingsPage() {
  const { groupId, setGroupId } = useGroupOptional();
  const groupsQuery = useGroups();
  const userQuery = useCurrentUser();
  const logout = useLogout();

  const groups = groupsQuery.data ?? [];

  return (
    <Box sx={{ p: 2, maxWidth: 600 }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        Settings
      </Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Account
          </Typography>
          <Typography variant="body2">
            {userQuery.data?.email ?? "Loading..."}
          </Typography>
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Active Group
          </Typography>
          <TextField
            select
            value={groupId ?? ""}
            onChange={(e) => setGroupId(e.target.value)}
            fullWidth
            size="small"
          >
            {groups.map((g) => (
              <MenuItem key={g.id} value={g.id}>
                {g.name}
              </MenuItem>
            ))}
          </TextField>
        </CardContent>
      </Card>

      {groupId && <SupplierSection groupId={groupId} />}
      {groupId && <HazardTagSection groupId={groupId} />}

      <Button
        variant="outlined"
        color="error"
        fullWidth
        sx={{ mt: 2 }}
        onClick={() =>
          logout.mutate(undefined, {
            onSuccess: () => (window.location.href = "/login"),
          })
        }
      >
        Logout
      </Button>
    </Box>
  );
}

function SupplierSection({ groupId }: { groupId: string }) {
  const suppliersQuery = useSuppliers(groupId);
  const createSupplier = useCreateSupplier(groupId);
  const deleteSupplier = useDeleteSupplier(groupId);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");

  const updateSupplier = useUpdateSupplier(groupId, editId ?? "");
  const suppliers = suppliersQuery.data?.items ?? [];

  const openCreate = () => {
    setEditId(null);
    setName("");
    setDialogOpen(true);
  };

  const openEdit = (id: string, currentName: string) => {
    setEditId(id);
    setName(currentName);
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (editId) {
      updateSupplier.mutate({ name }, { onSuccess: () => setDialogOpen(false) });
    } else {
      createSupplier.mutate({ name }, { onSuccess: () => setDialogOpen(false) });
    }
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Suppliers
          </Typography>
          <IconButton size="small" onClick={openCreate}>
            <AddIcon fontSize="small" />
          </IconButton>
        </Box>
        <List dense disablePadding>
          {suppliers.map((s) => (
            <ListItem
              key={s.id}
              disablePadding
              secondaryAction={
                <Box>
                  <IconButton size="small" onClick={() => openEdit(s.id, s.name)}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={() => deleteSupplier.mutate(s.id)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Box>
              }
            >
              <ListItemText primary={s.name} />
            </ListItem>
          ))}
        </List>
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="xs">
          <DialogTitle>{editId ? "Edit Supplier" : "New Supplier"}</DialogTitle>
          <DialogContent>
            <TextField
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              fullWidth
              autoFocus
              sx={{ mt: 1 }}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button variant="contained" onClick={handleSubmit} disabled={!name}>
              {editId ? "Save" : "Create"}
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
}

function HazardTagSection({ groupId }: { groupId: string }) {
  const tagsQuery = useHazardTags(groupId);
  const createTag = useCreateHazardTag(groupId);
  const deleteTag = useDeleteHazardTag(groupId);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const updateTag = useUpdateHazardTag(groupId, editId ?? "");
  const tags = tagsQuery.data?.items ?? [];

  const openCreate = () => {
    setEditId(null);
    setName("");
    setDescription("");
    setDialogOpen(true);
  };

  const openEdit = (id: string, currentName: string, currentDesc: string | null) => {
    setEditId(id);
    setName(currentName);
    setDescription(currentDesc ?? "");
    setDialogOpen(true);
  };

  const handleSubmit = () => {
    if (editId) {
      updateTag.mutate(
        { name, description: description || null },
        { onSuccess: () => setDialogOpen(false) },
      );
    } else {
      createTag.mutate(
        { name, description: description || undefined },
        { onSuccess: () => setDialogOpen(false) },
      );
    }
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Hazard Tags
          </Typography>
          <IconButton size="small" onClick={openCreate}>
            <AddIcon fontSize="small" />
          </IconButton>
        </Box>
        <List dense disablePadding>
          {tags.map((t) => (
            <ListItem
              key={t.id}
              disablePadding
              secondaryAction={
                <Box>
                  <IconButton
                    size="small"
                    onClick={() => openEdit(t.id, t.name, t.description)}
                  >
                    <EditIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={() => deleteTag.mutate(t.id)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Box>
              }
            >
              <ListItemText primary={t.name} secondary={t.description} />
            </ListItem>
          ))}
        </List>
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="xs">
          <DialogTitle>{editId ? "Edit Hazard Tag" : "New Hazard Tag"}</DialogTitle>
          <DialogContent>
            <TextField
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              fullWidth
              autoFocus
              sx={{ mt: 1, mb: 2 }}
            />
            <TextField
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              fullWidth
              multiline
              rows={2}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button variant="contained" onClick={handleSubmit} disabled={!name}>
              {editId ? "Save" : "Create"}
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
}
