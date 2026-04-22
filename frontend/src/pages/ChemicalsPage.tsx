import { Box, TextField, InputAdornment, IconButton, Stack, Badge, Button } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import TuneIcon from "@mui/icons-material/Tune";
import AddIcon from "@mui/icons-material/Add";
import { useState, useEffect } from "react";
import { useChemicals, useMultiGroupChemicals } from "../api/hooks/useChemicals";
import { useCurrentUser } from "../api/hooks/useAuth";
import { useGroups } from "../api/hooks/useGroups";
import { useStorageTree } from "../api/hooks/useStorageLocations";
import { ChemicalList } from "../components/ChemicalList";
import { FilterBar, type ActiveFilter } from "../components/FilterBar";
import { useDrawer } from "../components/drawer/DrawerContext";
import FilterDrawer, { type FilterState } from "../components/FilterDrawer";
import { ExportButton } from "../components/chemicals/ExportButton";
import type { ChemicalSearchParams } from "../types";

export default function ChemicalsPage() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? undefined;
  const drawer = useDrawer();
  const [search, setSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<FilterState>({
    includeArchived: false,
    hasContainers: undefined,
    mySecrets: false,
    locationId: undefined,
    locationName: undefined,
    selectedGroupIds: groupId ? [groupId] : [],
    sort: "name",
    order: "asc",
  });

  // Task 6: Sync selectedGroupIds when groupId first resolves
  useEffect(() => {
    if (groupId && filters.selectedGroupIds.length === 0) {
      setFilters((f) => ({ ...f, selectedGroupIds: [groupId] }));
    }
  }, [groupId]);

  const groups = useGroups();
  const storageTree = useStorageTree(groupId ?? "");

  const searchParams: ChemicalSearchParams = {
    search: search || undefined,
    has_containers: filters.hasContainers,
    my_secrets: filters.mySecrets || undefined,
    location_id: filters.locationId,
    sort: filters.sort as ChemicalSearchParams["sort"],
    order: filters.order,
  };

  const isMultiGroup =
    filters.selectedGroupIds.length > 1 ||
    (filters.selectedGroupIds.length === 1 && filters.selectedGroupIds[0] !== groupId);

  // Single-group fetch (with infinite scroll)
  const singleGroup = useChemicals(
    filters.selectedGroupIds[0] ?? groupId ?? "",
    searchParams,
    filters.includeArchived,
  );

  // Multi-group fetch (parallel, no infinite scroll)
  const multiGroup = useMultiGroupChemicals(
    isMultiGroup ? filters.selectedGroupIds : [],
    searchParams,
  );

  const singleItems = singleGroup.data?.pages.flatMap((p) => p.items) ?? [];
  const multiItems = multiGroup
    .flatMap((q) => q.data?.items ?? []);
  const items = isMultiGroup ? multiItems : singleItems;
  const isLoading = isMultiGroup
    ? multiGroup.some((q) => q.isLoading)
    : singleGroup.isLoading;

  // Build active filter chips
  const activeFilters: ActiveFilter[] = [];
  if (filters.includeArchived) {
    activeFilters.push({
      key: "archived",
      label: "Including archived",
      onRemove: () => setFilters((f) => ({ ...f, includeArchived: false })),
    });
  }
  if (filters.hasContainers === true) {
    activeFilters.push({
      key: "stock",
      label: "In stock",
      onRemove: () => setFilters((f) => ({ ...f, hasContainers: undefined })),
    });
  }
  if (filters.mySecrets) {
    activeFilters.push({
      key: "secrets",
      label: "My secrets",
      onRemove: () => setFilters((f) => ({ ...f, mySecrets: false })),
    });
  }
  if (filters.locationId) {
    activeFilters.push({
      key: "location",
      label: `Location: ${filters.locationName ?? "selected"}`,
      onRemove: () => setFilters((f) => ({ ...f, locationId: undefined, locationName: undefined })),
    });
  }
  if (!groupId) {
    return <Box sx={{ color: "text.secondary" }}>No group selected.</Box>;
  }

  return (
    <Stack>
      <Stack
        direction="row"
        spacing={1}
        sx={{ alignItems: "center", px: 2, py: 1.5 }}
      >
        <TextField
          size="small"
          fullWidth
          placeholder="Search chemical, CAS or container ID…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={() => drawer.open({ kind: "chemical-new" })}
          sx={{ whiteSpace: "nowrap", minWidth: 0 }}
        >
          <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
            New
          </Box>
        </Button>
        <ExportButton
          groupId={groupId}
          params={searchParams}
          includeArchived={filters.includeArchived}
        />
        <Badge
          color="primary"
          variant="dot"
          invisible={activeFilters.length === 0}
          overlap="circular"
        >
          <IconButton
            aria-label="Filters"
            sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1 }}
            onClick={() => setFiltersOpen(true)}
          >
            <TuneIcon fontSize="small" />
          </IconButton>
        </Badge>
      </Stack>
      <FilterBar filters={activeFilters} />
      <ChemicalList items={items} loading={isLoading} groupId={groupId} />
      <FilterDrawer
        open={filtersOpen}
        onOpen={() => setFiltersOpen(true)}
        onClose={() => setFiltersOpen(false)}
        filters={filters}
        onApply={setFilters}
        groups={groups.data ?? []}
        storageTree={storageTree.data ?? []}
      />
    </Stack>
  );
}
