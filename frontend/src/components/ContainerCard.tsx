import { Box, Chip, Stack, Typography } from "@mui/material";
import QrCode2Icon from "@mui/icons-material/QrCode2";
import type { ContainerRead } from "../types";

interface Props {
  container: ContainerRead;
  locationName?: string;
  supplierName?: string;
}

export function ContainerCard({ container, locationName, supplierName }: Props) {
  return (
    <Box
      sx={{
        position: "relative",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        bgcolor: "background.paper",
        p: 1.5,
      }}
    >
      <QrCode2Icon
        sx={{
          position: "absolute",
          top: 10,
          right: 10,
          fontSize: 14,
          color: "text.disabled",
        }}
      />
      <Chip
        label={container.identifier}
        size="small"
        sx={{
          bgcolor: "primary.light",
          color: "primary.dark",
          fontFamily: "'JetBrains Mono', ui-monospace, monospace",
          fontWeight: 700,
          fontSize: 11,
          height: 20,
        }}
      />
      <Typography sx={{ fontSize: 15, fontWeight: 600, mt: 1 }}>
        {container.amount} {container.unit}
      </Typography>
      {container.purity && (
        <Typography variant="caption" color="text.secondary">
          Purity {container.purity}
        </Typography>
      )}
      <Stack
        spacing={0.25}
        sx={{
          mt: 1,
          pt: 1,
          borderTop: "1px solid",
          borderColor: "divider",
          fontSize: 11,
          color: "text.secondary",
        }}
      >
        <MetaRow k="Location" v={locationName ?? "—"} />
        <MetaRow k="Supplier" v={supplierName ?? "—"} />
        <MetaRow k="Received" v={container.purchased_at ?? "—"} />
      </Stack>
    </Box>
  );
}

function MetaRow({ k, v }: { k: string; v: string }) {
  return (
    <Stack direction="row" spacing={0.75}>
      <Box sx={{ minWidth: 60, color: "text.disabled" }}>{k}</Box>
      <Box sx={{ color: "text.primary" }}>{v}</Box>
    </Stack>
  );
}
