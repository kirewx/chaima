import { Drawer, Box, Stack, Typography, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useDrawer } from "./DrawerContext";
import { ChemicalForm } from "./ChemicalForm";
import { ContainerForm } from "./ContainerForm";

const titles: Record<string, string> = {
  "chemical-new": "New chemical",
  "chemical-edit": "Edit chemical",
  "container-new": "New container",
  "container-edit": "Edit container",
};

export function EditDrawer() {
  const { config, close } = useDrawer();
  if (!config) return null;

  return (
    <Drawer
      anchor="right"
      open
      onClose={close}
      slotProps={{ paper: { sx: { width: { xs: "100%", sm: 480 } } } }}
    >
      <Stack
        direction="row"
        sx={{
          alignItems: "center",
          p: 2,
          borderBottom: "1px solid",
          borderColor: "divider",
        }}
      >
        <Typography variant="h3" sx={{ flex: 1 }}>
          {titles[config.kind]}
        </Typography>
        <IconButton onClick={close} size="small" aria-label="Close drawer">
          <CloseIcon />
        </IconButton>
      </Stack>
      <Box sx={{ flex: 1, p: 2, overflowY: "auto" }}>
        {(config.kind === "chemical-new" || config.kind === "chemical-edit") && (
          <ChemicalForm
            chemicalId={config.kind === "chemical-edit" ? config.chemicalId : undefined}
            onDone={close}
          />
        )}
        {(config.kind === "container-new" || config.kind === "container-edit") && (
          <ContainerForm
            chemicalId={config.kind === "container-new" ? config.chemicalId : undefined}
            containerId={
              config.kind === "container-edit" ? config.containerId : undefined
            }
            onDone={close}
          />
        )}
      </Box>
    </Drawer>
  );
}
