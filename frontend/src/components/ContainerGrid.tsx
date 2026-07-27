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
  const { data: tree = [] } = useStorageTree(groupId);
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
        {containers.map((c) => {
          const trail = findLocationTrail(tree, c.location_id);
          return (
            <ContainerCardWithSupplier
              key={c.id}
              groupId={groupId}
              container={c}
              locationNames={trail ? displayTrail(trail).map((n) => n.name) : undefined}
              locationColor={trail ? trail[trail.length - 1].color : undefined}
            />
          );
        })}
      </Box>
    </Box>
  );
}

function ContainerCardWithSupplier({
  groupId,
  container,
  locationNames,
  locationColor,
}: {
  groupId: string;
  container: ContainerRead;
  locationNames?: string[];
  locationColor?: string | null;
}) {
  const { data: supplier } = useSupplier(groupId, container.supplier_id);
  return (
    <ContainerCard
      container={container}
      groupId={groupId}
      locationNames={locationNames}
      locationColor={locationColor}
      supplierName={supplier?.name}
    />
  );
}
