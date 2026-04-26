import { Alert, Box, Typography, Stack, CircularProgress, Button } from "@mui/material";
import { useStorageNavigation } from "../hooks/useStorageNavigation";
import { StorageBreadcrumbs } from "../components/StorageBreadcrumbs";
import { StorageChildList } from "../components/StorageChildList";
import { ContainerCard } from "../components/ContainerCard";
import { useShelfContainers } from "../api/hooks/useStorageLocations";
import { useLocationConflicts } from "../api/hooks/useCompatibility";
import { useGroup } from "../components/GroupContext";
import { RoleGate } from "../components/RoleGate";
import { useDrawer } from "../components/drawer/DrawerContext";

export default function StoragePage() {
  const { groupId } = useGroup();
  const nav = useStorageNavigation();
  const { open } = useDrawer();

  const containers = useShelfContainers(
    groupId,
    nav.isLeaf && nav.current ? nav.current.id : null,
  );

  const conflicts = useLocationConflicts(groupId, nav.current?.id ?? null);

  if (nav.loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress size={22} />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      <StorageBreadcrumbs path={nav.path} />

      {nav.current && conflicts.data && conflicts.data.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <strong>
            This location has {conflicts.data.length} storage conflict
            {conflicts.data.length === 1 ? "" : "s"}.
          </strong>
          <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
            {conflicts.data.map((c, i) => (
              <li key={i}>
                {c.chem_a_name} and {c.chem_b_name}: {c.reason}
              </li>
            ))}
          </ul>
        </Alert>
      )}

      <Stack direction="row" sx={{ alignItems: "baseline", justifyContent: "space-between", mb: 2 }}>
        <Typography variant="h1">{nav.current?.name ?? "Storage"}</Typography>
        {nav.current && (
          <RoleGate allow={["admin", "superuser"]}>
            <Button
              size="small"
              onClick={() => open({ kind: "storage-edit", locationId: nav.current!.id })}
              sx={{ color: "text.secondary" }}
            >
              Edit {nav.current.kind}
            </Button>
          </RoleGate>
        )}
      </Stack>

      {nav.current?.description && (
        <Typography color="text.secondary" sx={{ mb: 2, fontSize: 13 }}>
          {nav.current.description}
        </Typography>
      )}

      {nav.isLeaf ? (
        <Box>
          <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="h5">Containers ({containers.data?.total ?? 0})</Typography>
          </Stack>
          {containers.isLoading ? (
            <CircularProgress size={18} />
          ) : (containers.data?.items.length ?? 0) === 0 ? (
            <Typography color="text.secondary" sx={{ py: 3, textAlign: "center", fontSize: 13 }}>
              No containers on this shelf yet. Create one from the Chemicals page.
            </Typography>
          ) : (
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "repeat(auto-fill, minmax(210px, 1fr))" },
                gap: 1.5,
              }}
            >
              {containers.data!.items.map((c) => (
                <ContainerCard key={c.id} container={c} locationColor={nav.current?.color} linkToChemical />
              ))}
            </Box>
          )}
        </Box>
      ) : (
        <StorageChildList
          children={nav.children}
          parentId={nav.current?.id ?? null}
          nextChildKind={nav.nextChildKind}
          parentHintForNewChild={nav.current?.id ?? null}
        />
      )}
    </Box>
  );
}
