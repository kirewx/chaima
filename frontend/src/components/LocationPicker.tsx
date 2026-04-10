import { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItemButton,
  ListItemText,
  Breadcrumbs,
  Link,
  Typography,
  Button,
  Box,
} from "@mui/material";
import type { StorageLocationNode } from "../types";

interface LocationPickerProps {
  open: boolean;
  onClose: () => void;
  onSelect: (locationId: string, path: string) => void;
  tree: StorageLocationNode[];
}

export default function LocationPicker({
  open,
  onClose,
  onSelect,
  tree,
}: LocationPickerProps) {
  const [breadcrumbs, setBreadcrumbs] = useState<
    { id: string; name: string; children: StorageLocationNode[] }[]
  >([]);

  const currentNodes =
    breadcrumbs.length > 0
      ? breadcrumbs[breadcrumbs.length - 1].children
      : tree;

  const handleDrillDown = (node: StorageLocationNode) => {
    if (node.children.length > 0) {
      setBreadcrumbs((prev) => [
        ...prev,
        { id: node.id, name: node.name, children: node.children },
      ]);
    } else {
      const path = [...breadcrumbs.map((b) => b.name), node.name].join(" > ");
      onSelect(node.id, path);
      handleClose();
    }
  };

  const handleSelectCurrent = (node: StorageLocationNode) => {
    const path = [...breadcrumbs.map((b) => b.name), node.name].join(" > ");
    onSelect(node.id, path);
    handleClose();
  };

  const handleBreadcrumbClick = (index: number) => {
    setBreadcrumbs((prev) => prev.slice(0, index));
  };

  const handleClose = () => {
    setBreadcrumbs([]);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
      <DialogTitle>Select Location</DialogTitle>
      <DialogContent>
        <Breadcrumbs sx={{ mb: 2 }}>
          <Link
            component="button"
            underline="hover"
            onClick={() => setBreadcrumbs([])}
          >
            All
          </Link>
          {breadcrumbs.map((crumb, i) => {
            const isLast = i === breadcrumbs.length - 1;
            return isLast ? (
              <Typography key={crumb.id} color="text.primary">
                {crumb.name}
              </Typography>
            ) : (
              <Link
                key={crumb.id}
                component="button"
                underline="hover"
                onClick={() => handleBreadcrumbClick(i + 1)}
              >
                {crumb.name}
              </Link>
            );
          })}
        </Breadcrumbs>

        <List>
          {currentNodes.map((node) => (
            <ListItemButton key={node.id} sx={{ borderRadius: 2, mb: 0.5 }}>
              <ListItemText
                primary={node.name}
                secondary={
                  node.children.length > 0
                    ? `${node.children.length} sub-locations`
                    : "No sub-locations"
                }
                onClick={() => handleDrillDown(node)}
              />
              <Box sx={{ display: "flex", gap: 1 }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSelectCurrent(node);
                  }}
                >
                  Select
                </Button>
              </Box>
            </ListItemButton>
          ))}
          {currentNodes.length === 0 && (
            <Typography
              color="text.secondary"
              sx={{ textAlign: "center", py: 2 }}
            >
              No locations
            </Typography>
          )}
        </List>
      </DialogContent>
    </Dialog>
  );
}
