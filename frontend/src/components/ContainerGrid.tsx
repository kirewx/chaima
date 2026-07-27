import { Box, Button, Stack, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import type { ContainerRead } from "../types";
import { ContainerCard } from "./ContainerCard";
import { useStorageTree } from "../api/hooks/useStorageLocations";
import { useSupplier } from "../api/hooks/useSuppliers";
import { displayTrail, findLocationTrail } from "../utils/locationPath";

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
  const { data: tree = [] } = useStorageTree(groupId);
  const { data: supplier } = useSupplier(groupId, container.supplier_id);
  const trail = findLocationTrail(tree, container.location_id);
  const names = trail ? displayTrail(trail).map((n) => n.name) : undefined;
  const leafColor = trail ? trail[trail.length - 1].color : undefined;
  return (
    <ContainerCard
      container={container}
      groupId={groupId}
      locationNames={names}
      locationColor={leafColor}
      supplierName={supplier?.name}
    />
  );
}
