import { Drawer, Box, Stack, Typography, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useDrawer } from "./DrawerContext";
import { ChemicalForm } from "./ChemicalForm";
import { ContainerForm } from "./ContainerForm";
import { StorageForm } from "./StorageForm";
import { OrderForm } from "../orders/OrderForm";
import { OrderDetailDrawer } from "../orders/OrderDetailDrawer";

const titles: Record<string, string> = {
  "chemical-new": "New chemical",
  "chemical-edit": "Edit chemical",
  "container-new": "New container",
  "container-edit": "Edit container",
  "storage-new": "New storage location",
  "storage-edit": "Edit storage location",
  "new-order": "New order",
  "order-detail": "Order details",
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
        {config.kind === "storage-new" && (
          <StorageForm
            mode="create"
            childKind={config.childKind}
            parentId={config.parentId}
          />
        )}
        {config.kind === "storage-edit" && (
          <StorageForm mode="edit" locationId={config.locationId} />
        )}
        {config.kind === "new-order" && (
          <OrderForm
            groupId={config.groupId}
            chemicalId={config.chemicalId}
            wishlistItemId={config.wishlistItemId}
            onDone={close}
          />
        )}
        {config.kind === "order-detail" && (
          <OrderDetailDrawer
            groupId={config.groupId}
            orderId={config.orderId}
            onDone={close}
          />
        )}
      </Box>
    </Drawer>
  );
}
