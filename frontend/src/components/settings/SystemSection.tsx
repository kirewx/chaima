import { Box, Alert, Typography, Stack, Divider } from "@mui/material";
import { SectionHeader } from "./SectionHeader";

export function SystemSection() {
  return (
    <Box>
      <SectionHeader
        title="System"
        subtitle="Global settings for the ChAIMa instance."
      />
      <Stack spacing={2}>
        <Alert severity="info">
          System-wide configuration UI is not part of v1. The backend has sensible defaults and
          configuration is done via environment variables.
        </Alert>
        <Divider />
        <Stack spacing={0.5}>
          <Typography variant="h5">INSTANCE</Typography>
          <Typography variant="body2" color="text.secondary">
            Read-only stub. Future contents: admin email, group-creation policy, PubChem proxy toggle.
          </Typography>
        </Stack>
      </Stack>
    </Box>
  );
}
