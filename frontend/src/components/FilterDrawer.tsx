import { useState } from "react";
import {
  SwipeableDrawer, Drawer, Box, Typography, Switch, FormControlLabel,
  Chip, Stack, Button, Divider, TextField, MenuItem, Collapse,
  useMediaQuery, useTheme,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import type { GroupRead, StorageLocationNode } from "../types";
import LocationPicker from "./LocationPicker";
import { HAZARD_LABELS } from "./GHSPictogramRow";

const PICTOGRAM_CODES = Object.keys(HAZARD_LABELS);

export interface FilterState {
  includeArchived: boolean;
  hasContainers: boolean | undefined;
  mySecrets: boolean;
  locationId: string | undefined;
  locationName: string | undefined;
  pictograms: string[];
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
  const [hazardsOpen, setHazardsOpen] = useState(false);

  const handleChange = (patch: Partial<FilterState>) => {
    onApply({ ...filters, ...patch });
  };

  const togglePictogram = (code: string) => {
    const current = filters.pictograms;
    const updated = current.includes(code)
      ? current.filter((c) => c !== code)
      : [...current, code];
    handleChange({ pictograms: updated });
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

      {/* Archived chemicals are hidden by default; this is the only way to
          reach (and then unarchive) them. */}
      <FormControlLabel
        control={
          <Switch
            checked={filters.includeArchived}
            onChange={(_, checked) => handleChange({ includeArchived: checked })}
          />
        }
        label={<Typography variant="body2">Include archived</Typography>}
        sx={{ m: 0, mb: 1 }}
      />

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

      {/* GHS hazard pictograms — collapsed by default; used irregularly, so it
          stays out of the way until expanded. */}
      <Box
        component="button"
        type="button"
        onClick={() => setHazardsOpen((o) => !o)}
        aria-expanded={hazardsOpen}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
          p: 0,
          border: 0,
          bgcolor: "transparent",
          cursor: "pointer",
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Hazard pictograms
          {filters.pictograms.length ? ` (${filters.pictograms.length})` : ""}
        </Typography>
        <ExpandMoreIcon
          fontSize="small"
          sx={{
            color: "text.secondary",
            transform: hazardsOpen ? "rotate(180deg)" : "none",
            transition: "transform 150ms",
          }}
        />
      </Box>
      <Collapse in={hazardsOpen} unmountOnExit>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1.5 }}>
          {PICTOGRAM_CODES.map((code) => {
            const selected = filters.pictograms.includes(code);
            const label = HAZARD_LABELS[code];
            return (
              <Box
                key={code}
                component="button"
                type="button"
                onClick={() => togglePictogram(code)}
                aria-pressed={selected}
                title={`${code} — ${label}`}
                sx={{
                  width: 88,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 0.5,
                  p: 0.75,
                  cursor: "pointer",
                  border: "2px solid",
                  borderColor: selected ? "primary.main" : "transparent",
                  borderRadius: 1,
                  bgcolor: selected ? "action.selected" : "transparent",
                  opacity: selected ? 1 : 0.7,
                  transition: "opacity 120ms, border-color 120ms",
                  "&:hover": { opacity: 1 },
                }}
              >
                <Box
                  component="img"
                  src={`/ghs/${code}.svg`}
                  alt=""
                  sx={{ width: 40, height: 40, display: "block" }}
                />
                <Box sx={{ textAlign: "center", lineHeight: 1.2 }}>
                  <Typography sx={{ fontSize: 10, fontWeight: 700, display: "block" }}>
                    {code}
                  </Typography>
                  <Typography sx={{ fontSize: 10, color: "text.secondary", display: "block" }}>
                    {label}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Box>
      </Collapse>

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
