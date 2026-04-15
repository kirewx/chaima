import { Box, Alert, Typography, Stack } from "@mui/material";
import { SectionHeader } from "./SectionHeader";

export function BuildingsSection() {
  return (
    <Box>
      <SectionHeader
        title="Buildings"
        subtitle="System-wide physical buildings. Groups reference buildings to scope their storage tree."
      />
      <Stack spacing={2}>
        <Alert severity="info">
          Building management lives on the <b>Storage</b> page — drill into a building to edit or
          archive it, or use the <b>+ Add building</b> button at the storage root (superuser only).
          A consolidated buildings overview may land here in a later polish pass.
        </Alert>
        <Typography variant="body2" color="text.secondary">
          When that overview ships, this section will list all buildings with edit / archive actions and a
          <b> + New building</b> button.
        </Typography>
      </Stack>
    </Box>
  );
}
