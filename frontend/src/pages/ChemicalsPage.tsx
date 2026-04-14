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

export default function ChemicalsPage() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? undefined;
  const drawer = useDrawer();
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

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
          sx={{ whiteSpace: "nowrap" }}
        >
          New chemical
        </Button>
        {/* TODO: Task 15 — open FilterDrawer */}
        <Badge
          color="primary"
          variant="dot"
          invisible={activeFilters.length === 0}
          overlap="circular"
        >
          <IconButton
            aria-label="Filters"
            sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1 }}
            onClick={() => setIncludeArchived((v) => !v)}
          >
            <TuneIcon fontSize="small" />
          </IconButton>
        </Badge>
      </Stack>
      <FilterBar filters={activeFilters} />
      <ChemicalList items={items} loading={isLoading} groupId={groupId} />
    </Stack>
  );
}
