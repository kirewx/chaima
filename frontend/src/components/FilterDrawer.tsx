import { SwipeableDrawer, Box, Typography, Switch, FormControlLabel, Chip, Stack, Button, Divider, TextField, MenuItem } from "@mui/material";
import type { HazardTagRead, GHSCodeRead } from "../types";

export interface FilterState {
  hasContainers: boolean | undefined;
  hazardTagId: string | undefined;
  ghsCodeId: string | undefined;
  sort: string;
  order: "asc" | "desc";
}

interface FilterDrawerProps {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  filters: FilterState;
  onApply: (filters: FilterState) => void;
  hazardTags: HazardTagRead[];
  ghsCodes: GHSCodeRead[];
}

export default function FilterDrawer({ open, onOpen, onClose, filters, onApply, hazardTags, ghsCodes }: FilterDrawerProps) {
  const handleChange = (patch: Partial<FilterState>) => { onApply({ ...filters, ...patch }); };

  return (
    <SwipeableDrawer anchor="bottom" open={open} onOpen={onOpen} onClose={onClose}
      PaperProps={{ sx: { borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: "70vh", px: 3, py: 2 } }}>
      <Box sx={{ width: 40, height: 4, bgcolor: "#444", borderRadius: 2, mx: "auto", mb: 2 }} />
      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>Filters</Typography>
      <FormControlLabel
        control={<Switch checked={filters.hasContainers === true} onChange={(_, checked) => handleChange({ hasContainers: checked ? true : undefined })} />}
        label="Has stock"
      />
      <Divider sx={{ my: 2 }} />
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Hazard Tags</Typography>
      <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5, mb: 2 }}>
        {hazardTags.map((tag) => (
          <Chip key={tag.id} label={tag.name} size="small"
            color={filters.hazardTagId === tag.id ? "error" : "default"}
            variant={filters.hazardTagId === tag.id ? "filled" : "outlined"}
            onClick={() => handleChange({ hazardTagId: filters.hazardTagId === tag.id ? undefined : tag.id })} />
        ))}
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>GHS Codes</Typography>
      <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5, mb: 2 }}>
        {ghsCodes.map((code) => (
          <Chip key={code.id} label={code.code} size="small"
            color={filters.ghsCodeId === code.id ? "warning" : "default"}
            variant={filters.ghsCodeId === code.id ? "filled" : "outlined"}
            onClick={() => handleChange({ ghsCodeId: filters.ghsCodeId === code.id ? undefined : code.id })} />
        ))}
      </Stack>
      <Divider sx={{ my: 2 }} />
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <TextField select label="Sort by" value={filters.sort} onChange={(e) => handleChange({ sort: e.target.value })} size="small" sx={{ flex: 1 }}>
          <MenuItem value="name">Name</MenuItem>
          <MenuItem value="cas">CAS</MenuItem>
          <MenuItem value="created_at">Created</MenuItem>
          <MenuItem value="updated_at">Updated</MenuItem>
        </TextField>
        <TextField select label="Order" value={filters.order} onChange={(e) => handleChange({ order: e.target.value as "asc" | "desc" })} size="small" sx={{ flex: 1 }}>
          <MenuItem value="asc">Ascending</MenuItem>
          <MenuItem value="desc">Descending</MenuItem>
        </TextField>
      </Stack>
      <Button variant="contained" fullWidth onClick={onClose}>Apply</Button>
    </SwipeableDrawer>
  );
}
