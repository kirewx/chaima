import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Breadcrumbs,
  Link,
  Button,
  Card,
  CardActionArea,
  CardContent,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import AddIcon from "@mui/icons-material/Add";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import { useGroup } from "../components/GroupContext";
import {
  useStorageTree,
  useCreateStorageLocation,
  useUpdateStorageLocation,
  useDeleteStorageLocation,
} from "../api/hooks/useStorageLocations";
import type { StorageLocationNode } from "../types";

function findNodePath(
  nodes: StorageLocationNode[],
  targetId: string,
  path: StorageLocationNode[] = [],
): StorageLocationNode[] | null {
  for (const node of nodes) {
    const currentPath = [...path, node];
    if (node.id === targetId) return currentPath;
    const found = findNodePath(node.children, targetId, currentPath);
    if (found) return found;
  }
  return null;
}

export default function StoragePage() {
  const { groupId } = useGroup();
  const { id: locationId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const treeQuery = useStorageTree(groupId);
  const createMutation = useCreateStorageLocation(groupId);
  const updateMutation = useUpdateStorageLocation(groupId, locationId ?? "");
  const deleteMutation = useDeleteStorageLocation(groupId);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [dialogName, setDialogName] = useState("");
  const [dialogDescription, setDialogDescription] = useState("");

  const tree = treeQuery.data ?? [];
  const nodePath = locationId ? findNodePath(tree, locationId) : null;
  const currentNode = nodePath ? nodePath[nodePath.length - 1] : null;
  const children = currentNode ? currentNode.children : tree;

  const openCreateDialog = () => {
    setEditMode(false);
    setDialogName("");
    setDialogDescription("");
    setDialogOpen(true);
  };

  const openEditDialog = () => {
    if (!currentNode) return;
    setEditMode(true);
    setDialogName(currentNode.name);
    setDialogDescription(currentNode.description ?? "");
    setDialogOpen(true);
  };

  const handleDialogSubmit = () => {
    if (editMode && locationId) {
      updateMutation.mutate(
        { name: dialogName, description: dialogDescription || null },
        { onSuccess: () => setDialogOpen(false) },
      );
    } else {
      createMutation.mutate(
        {
          name: dialogName,
          description: dialogDescription || undefined,
          parent_id: locationId ?? undefined,
        },
        { onSuccess: () => setDialogOpen(false) },
      );
    }
  };

  const handleDelete = () => {
    if (!locationId) return;
    const parentId = nodePath && nodePath.length > 1 ? nodePath[nodePath.length - 2].id : null;
    deleteMutation.mutate(locationId, {
      onSuccess: () =>
        navigate(parentId ? `/storage/${parentId}` : "/storage"),
    });
  };

  return (
    <Box sx={{ p: 2 }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Box>
          <Breadcrumbs>
            <Link
              component="button"
              underline="hover"
              onClick={() => navigate("/storage")}
            >
              All
            </Link>
            {nodePath?.map((node, i) => {
              const isLast = i === nodePath.length - 1;
              return isLast ? (
                <Typography key={node.id} color="text.primary">
                  {node.name}
                </Typography>
              ) : (
                <Link
                  key={node.id}
                  component="button"
                  underline="hover"
                  onClick={() => navigate(`/storage/${node.id}`)}
                >
                  {node.name}
                </Link>
              );
            })}
          </Breadcrumbs>
          {currentNode && (
            <Typography variant="h6" fontWeight={600} sx={{ mt: 0.5 }}>
              {currentNode.name}
            </Typography>
          )}
          {!currentNode && (
            <Typography variant="h6" fontWeight={600} sx={{ mt: 0.5 }}>
              Storage Locations
            </Typography>
          )}
        </Box>
        <Box sx={{ display: "flex", gap: 1 }}>
          {currentNode && (
            <IconButton onClick={openEditDialog} size="small">
              <EditIcon />
            </IconButton>
          )}
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={openCreateDialog}
          >
            Add
          </Button>
        </Box>
      </Box>

      {children.length > 0 ? (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {children.map((child) => (
            <Card key={child.id}>
              <CardActionArea
                onClick={() => navigate(`/storage/${child.id}`)}
              >
                <CardContent
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    py: 1.5,
                  }}
                >
                  <Box>
                    <Typography variant="body1" fontWeight={500}>
                      {child.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {child.children.length > 0
                        ? `${child.children.length} sub-locations`
                        : "No sub-locations"}
                    </Typography>
                  </Box>
                  <ChevronRightIcon sx={{ color: "text.secondary" }} />
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Box>
      ) : (
        <Typography color="text.secondary" sx={{ textAlign: "center", py: 4 }}>
          {currentNode ? "No sub-locations" : "No storage locations yet"}
        </Typography>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>
          {editMode ? "Edit Location" : "New Location"}
        </DialogTitle>
        <DialogContent>
          <TextField
            label="Name"
            value={dialogName}
            onChange={(e) => setDialogName(e.target.value)}
            fullWidth
            required
            autoFocus
            sx={{ mt: 1, mb: 2 }}
          />
          <TextField
            label="Description"
            value={dialogDescription}
            onChange={(e) => setDialogDescription(e.target.value)}
            fullWidth
            multiline
            rows={2}
          />
        </DialogContent>
        <DialogActions>
          {editMode && (
            <Button color="error" onClick={handleDelete} sx={{ mr: "auto" }}>
              Delete
            </Button>
          )}
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleDialogSubmit}
            disabled={!dialogName}
          >
            {editMode ? "Save" : "Create"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
