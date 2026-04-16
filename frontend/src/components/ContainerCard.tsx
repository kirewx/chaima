import { Box, Chip, Stack, Typography } from "@mui/material";
import QrCode2Icon from "@mui/icons-material/QrCode2";
import { Link as RouterLink } from "react-router-dom";
import type { ReactNode } from "react";
import type { ContainerRead } from "../types";
import { ContainerMenu } from "./ContainerMenu";

interface Props {
  container: ContainerRead;
  locationName?: string;
  supplierName?: string;
  /**
   * When true, the card body is wrapped in a router link that navigates to
   * the Chemicals page with `?expand=<chemicalId>`, causing ChemicalList to
   * pre-expand that chemical's row on mount.
   */
  linkToChemical?: boolean;
}

export function ContainerCard({
  container,
  locationName,
  supplierName,
  linkToChemical,
}: Props) {
  const showMenu = !linkToChemical;
  const body: ReactNode = (
    <>
      <QrCode2Icon
        sx={{
          position: "absolute",
          top: 10,
          right: showMenu ? 36 : 10,
          fontSize: 14,
          color: "text.disabled",
        }}
      />
      {showMenu && (
        <Box sx={{ position: "absolute", top: 6, right: 6, zIndex: 2 }}>
          <ContainerMenu container={container} />
        </Box>
      )}
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
    </>
  );

  const baseSx = {
    position: "relative" as const,
    border: "1px solid",
    borderColor: "divider",
    borderRadius: 1,
    bgcolor: "background.paper",
    p: 1.5,
  };

  if (linkToChemical) {
    return (
      <Box
        component={RouterLink}
        to={`/?expand=${container.chemical_id}`}
        sx={{
          ...baseSx,
          display: "block",
          textDecoration: "none",
          color: "inherit",
          "&:hover": { borderColor: "primary.main" },
        }}
      >
        {body}
      </Box>
    );
  }

  return (
    <Box
      sx={{
        ...baseSx,
        cursor: "pointer",
        transition: "border-color 0.15s, box-shadow 0.15s",
        "&:hover": {
          borderColor: "primary.main",
          boxShadow: 1,
        },
      }}
    >
      {body}
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
