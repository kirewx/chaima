import { useState } from "react";
import {
  SwipeableDrawer, Drawer, Box, Typography, Switch, FormControlLabel,
  Chip, Stack, Button, Divider, TextField, MenuItem,
  useMediaQuery, useTheme,
} from "@mui/material";
import type { GroupRead, StorageLocationNode } from "../types";
import LocationPicker from "./LocationPicker";

export interface FilterState {
  includeArchived: boolean;
  hasContainers: boolean | undefined;
  mySecrets: boolean;
  locationId: string | undefined;
  locationName: string | undefined;
  selectedGroupIds: string[];
  sort: string;
  order: "asc" | "desc";
}

interface FilterDrawerProps {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  filters: FilterState;
  onApply: (filters: FilterState) => void;
  groups: GroupRead[];
  storageTree: StorageLocationNode[];
}

export default function FilterDrawer({
  open, onOpen, onClose, filters, onApply, groups, storageTree,
}: FilterDrawerProps) {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [pickerOpen, setPickerOpen] = useState(false);

  const handleChange = (patch: Partial<FilterState>) => {
    onApply({ ...filters, ...patch });
  };

  const toggleGroup = (groupId: string) => {
    const current = filters.selectedGroupIds;
    const updated = current.includes(groupId)
      ? current.filter((id) => id !== groupId)
      : [...current, groupId];
    if (updated.length > 0) {
      handleChange({ selectedGroupIds: updated });
    }
  };

  const content = (
    <Box sx={{ px: isDesktop ? 2 : 3, py: 2, width: isDesktop ? 320 : "auto" }}>
      {!isDesktop && (
        <Box sx={{ width: 40, height: 4, bgcolor: "#444", borderRadius: 2, mx: "auto", mb: 2 }} />
      )}
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>Filters</Typography>

      {/* Has stock + My secrets — side by side */}
      <Stack direction="row" spacing={2} sx={{ mb: 1 }}>
        <FormControlLabel
          control={
            <Switch
              checked={filters.hasContainers === true}
              onChange={(_, checked) =>
                handleChange({ hasContainers: checked ? true : undefined })
              }
            />
          }
          label={<Typography variant="body2">Has stock</Typography>}
          sx={{ flex: 1, m: 0 }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={filters.mySecrets}
              onChange={(_, checked) => handleChange({ mySecrets: checked })}
            />
          }
          label={<Typography variant="body2">My secrets</Typography>}
          sx={{ flex: 1, m: 0 }}
        />
      </Stack>

      <Divider sx={{ my: 2 }} />

      {/* Storage location */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        Storage location
      </Typography>
      <Button
        variant="outlined"
        size="small"
        fullWidth
        onClick={() => setPickerOpen(true)}
        sx={{ justifyContent: "flex-start", textTransform: "none", mb: 1 }}
      >
        {filters.locationName ?? "Select location..."}
      </Button>
      {filters.locationId && (
        <Button
          size="small"
          onClick={() => handleChange({ locationId: undefined, locationName: undefined })}
          sx={{ textTransform: "none", mb: 0.5 }}
        >
          Clear location
        </Button>
      )}

      <LocationPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(id, path) => handleChange({ locationId: id, locationName: path })}
        tree={storageTree}
      />

      {groups.length > 1 && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            Groups
          </Typography>
          <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5 }}>
            {groups.map((g) => (
              <Chip
                key={g.id}
                label={g.name}
                size="small"
                color={filters.selectedGroupIds.includes(g.id) ? "primary" : "default"}
                variant={filters.selectedGroupIds.includes(g.id) ? "filled" : "outlined"}
                onClick={() => toggleGroup(g.id)}
              />
            ))}
          </Stack>
        </>
      )}

      <Divider sx={{ my: 2 }} />

      {/* Sort & Order */}
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <TextField
          select label="Sort by" value={filters.sort}
          onChange={(e) => handleChange({ sort: e.target.value })}
          size="small" sx={{ flex: 1 }}
        >
          <MenuItem value="name">Name</MenuItem>
          <MenuItem value="cas">CAS</MenuItem>
          <MenuItem value="created_at">Created</MenuItem>
          <MenuItem value="updated_at">Updated</MenuItem>
        </TextField>
        <TextField
          select label="Order" value={filters.order}
          onChange={(e) => handleChange({ order: e.target.value as "asc" | "desc" })}
          size="small" sx={{ flex: 1 }}
        >
          <MenuItem value="asc">Ascending</MenuItem>
          <MenuItem value="desc">Descending</MenuItem>
        </TextField>
      </Stack>

      <Button variant="contained" fullWidth onClick={onClose}>Apply</Button>
    </Box>
  );

  if (isDesktop) {
    return (
      <Drawer anchor="right" open={open} onClose={onClose}
        slotProps={{ paper: { sx: { borderTopLeftRadius: 8, borderBottomLeftRadius: 8, bgcolor: "background.default" } } }}>
        {content}
      </Drawer>
    );
  }

  return (
    <SwipeableDrawer anchor="bottom" open={open} onOpen={onOpen} onClose={onClose}
      slotProps={{ paper: { sx: { borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: "70vh" } } }}>
      {content}
    </SwipeableDrawer>
  );
}
