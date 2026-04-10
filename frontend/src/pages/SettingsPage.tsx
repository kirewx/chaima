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
  Snackbar,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { useGroupOptional } from "../components/GroupContext";
import { useGroups, useGroupMembers, useCreateGroup } from "../api/hooks/useGroups";
import { useCurrentUser, useLogout, useUpdateMainGroup } from "../api/hooks/useAuth";
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
import { useCreateInvite, useGroupInvites, useRevokeInvite } from "../api/hooks/useInvites";
import type { GroupRead } from "../types";

export default function SettingsPage() {
  const { groupId } = useGroupOptional();
  const groupsQuery = useGroups();
  const userQuery = useCurrentUser();
  const logout = useLogout();
  const updateMainGroup = useUpdateMainGroup();

  const groups = groupsQuery.data ?? [];
  const mainGroupId = userQuery.data?.main_group_id ?? "";

  return (
    <Box sx={{ p: 2, maxWidth: 600 }}>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
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
            Main Group
          </Typography>
          <TextField
            select
            value={mainGroupId}
            onChange={(e) => updateMainGroup.mutate(e.target.value)}
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

      {userQuery.data?.is_superuser && <SuperuserPanel />}

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

function SuperuserPanel() {
  const groupsQuery = useGroups();
  const createGroup = useCreateGroup();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [selectedGroup, setSelectedGroup] = useState<GroupRead | null>(null);

  const groups = groupsQuery.data ?? [];

  const handleCreateGroup = () => {
    createGroup.mutate(
      { name: newGroupName },
      {
        onSuccess: () => {
          setCreateDialogOpen(false);
          setNewGroupName("");
        },
      },
    );
  };

  if (selectedGroup) {
    return (
      <GroupAdminPanel
        group={selectedGroup}
        onClose={() => setSelectedGroup(null)}
      />
    );
  }

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
        Admin Panel
      </Typography>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Groups
            </Typography>
            <IconButton size="small" onClick={() => setCreateDialogOpen(true)}>
              <AddIcon fontSize="small" />
            </IconButton>
          </Box>
          <List dense disablePadding>
            {groups.map((g) => (
              <ListItem
                key={g.id}
                disablePadding
                sx={{ cursor: "pointer" }}
                onClick={() => setSelectedGroup(g)}
              >
                <ListItemText primary={g.name} secondary={g.description} />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      <Dialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>New Group</DialogTitle>
        <DialogContent>
          <TextField
            label="Name"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            fullWidth
            autoFocus
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateGroup}
            disabled={!newGroupName}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

function GroupAdminPanel({
  group,
  onClose,
}: {
  group: GroupRead;
  onClose: () => void;
}) {
  const membersQuery = useGroupMembers(group.id);
  const invitesQuery = useGroupInvites(group.id);
  const createInvite = useCreateInvite(group.id);
  const revokeInvite = useRevokeInvite();
  const [snackbarOpen, setSnackbarOpen] = useState(false);

  const members = membersQuery.data ?? [];
  const invites = invitesQuery.data ?? [];

  const handleGenerateLink = () => {
    createInvite.mutate(undefined, {
      onSuccess: (data) => {
        const url = `${window.location.origin}/invite/${data.token}`;
        navigator.clipboard.writeText(url);
        setSnackbarOpen(true);
      },
    });
  };

  const handleCopyInvite = (token: string) => {
    const url = `${window.location.origin}/invite/${token}`;
    navigator.clipboard.writeText(url);
    setSnackbarOpen(true);
  };

  return (
    <Box sx={{ mt: 2 }}>
      <Box sx={{ display: "flex", alignItems: "center", mb: 1, gap: 1 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, flex: 1 }}>
          {group.name}
        </Typography>
        <Button size="small" onClick={onClose}>
          Close
        </Button>
      </Box>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
            Members
          </Typography>
          <List dense disablePadding>
            {members.map((m) => (
              <ListItem key={m.user_id} disablePadding>
                <ListItemText
                  primary={m.email}
                  secondary={m.is_admin ? "Admin" : "Member"}
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Pending Invites
            </Typography>
            <Button
              size="small"
              startIcon={<AddIcon />}
              onClick={handleGenerateLink}
              disabled={createInvite.isPending}
            >
              Generate Link
            </Button>
          </Box>
          <List dense disablePadding>
            {invites.map((inv) => (
              <ListItem
                key={inv.id}
                disablePadding
                secondaryAction={
                  <Box>
                    <IconButton
                      size="small"
                      onClick={() => handleCopyInvite(inv.token)}
                    >
                      <ContentCopyIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => revokeInvite.mutate(inv.id)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
                }
              >
                <ListItemText primary={`...${inv.token.slice(-8)}`} />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      <Snackbar
        open={snackbarOpen}
        autoHideDuration={3000}
        onClose={() => setSnackbarOpen(false)}
        message="Copied to clipboard"
      />
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
