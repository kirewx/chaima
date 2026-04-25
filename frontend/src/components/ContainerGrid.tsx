import { Box, Button, Stack, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import type { ContainerRead } from "../types";
import { ContainerCard } from "./ContainerCard";
import { useStorageLocation } from "../api/hooks/useStorageLocations";
import { useSupplier } from "../api/hooks/useSuppliers";

interface Props {
  groupId: string;
  containers: ContainerRead[];
  onAdd: () => void;
}

export function ContainerGrid({ groupId, containers, onAdd }: Props) {
  return (
    <Box sx={{ px: 2, pb: 2 }}>
      <Stack
        direction="row"
        sx={{ alignItems: "center", justifyContent: "space-between", mb: 1 }}
      >
        <Typography variant="h5">Containers ({containers.length})</Typography>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={onAdd}
        >
          Container
        </Button>
      </Stack>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: {
            xs: "1fr",
            sm: "repeat(auto-fill, minmax(210px, 1fr))",
          },
          gap: 1.25,
        }}
      >
        {containers.map((c) => (
          <ContainerCardWithLookups key={c.id} groupId={groupId} container={c} />
        ))}
      </Box>
    </Box>
  );
}

function ContainerCardWithLookups({
  groupId,
  container,
}: {
  groupId: string;
  container: ContainerRead;
}) {
  const { data: loc } = useStorageLocation(groupId, container.location_id);
  const { data: supplier } = useSupplier(groupId, container.supplier_id);
  return (
    <ContainerCard
      container={container}
      locationName={loc?.name}
      locationColor={loc?.color}
      supplierName={supplier?.name}
    />
  );
}
