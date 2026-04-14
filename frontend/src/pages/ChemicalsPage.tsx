import { Box, TextField, InputAdornment, IconButton, Stack, Badge, Button } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import TuneIcon from "@mui/icons-material/Tune";
import AddIcon from "@mui/icons-material/Add";
import { useState } from "react";
import { useChemicals } from "../api/hooks/useChemicals";
import { useCurrentUser } from "../api/hooks/useAuth";
import { ChemicalList } from "../components/ChemicalList";
import { FilterBar, type ActiveFilter } from "../components/FilterBar";
import { useDrawer } from "../components/drawer/DrawerContext";
import FilterDrawer, { type FilterState } from "../components/FilterDrawer";

export default function ChemicalsPage() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? undefined;
  const drawer = useDrawer();
  const [search, setSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<FilterState>({
    includeArchived: false,
    hasContainers: undefined,
    hazardTagId: undefined,
    ghsCodeId: undefined,
    sort: "name",
    order: "asc",
    selectedGroupIds: groupId ? [groupId] : [],
  });

  const includeArchived = filters.includeArchived;
  const setIncludeArchived = (v: boolean) => setFilters((f) => ({ ...f, includeArchived: v }));

  const { data, isLoading } = useChemicals(
    groupId as string,
    { search: search || undefined },
    includeArchived
  );

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  const activeFilters: ActiveFilter[] = [];
  if (includeArchived) {
    activeFilters.push({
      key: "archived",
      label: "Including archived",
      onRemove: () => setIncludeArchived(false),
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
            New chemical
          </Box>
        </Button>
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
        hazardTags={[]}
        ghsCodes={[]}
        groups={[]}
      />
    </Stack>
  );
}
