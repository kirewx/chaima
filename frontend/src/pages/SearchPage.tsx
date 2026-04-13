import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Box, IconButton, CircularProgress, Typography, Drawer, useMediaQuery, useTheme } from "@mui/material";
import TuneIcon from "@mui/icons-material/Tune";
import { useGroup } from "../components/GroupContext";
import { useMultiGroupChemicals } from "../api/hooks/useChemicals";
import { useHazardTags } from "../api/hooks/useHazardTags";
import { useGHSCodes } from "../api/hooks/useGHSCodes";
import { useGroups } from "../api/hooks/useGroups";
import { useContainers, useUnarchiveContainer } from "../api/hooks/useContainers";
import { useStorageTree } from "../api/hooks/useStorageLocations";
import SearchBar from "../components/SearchBar";
import FilterDrawer, { type FilterState } from "../components/FilterDrawer";
import FilterBadges, { type FilterBadge } from "../components/FilterBadges";
import ChemicalCard from "../components/ChemicalCard";
import ChemicalDetail from "../components/ChemicalDetail";
import UndoSnackbar from "../components/UndoSnackbar";
import type { StorageLocationNode, ContainerRead, ChemicalRead } from "../types";

interface ListRow {
  chemical: ChemicalRead;
  container: ContainerRead | null;
  key: string;
}

const mono = "'JetBrains Mono', ui-monospace, monospace";

export default function SearchPage() {
  const { groupId: mainGroupId } = useGroup();
  const navigate = useNavigate();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const groupsQuery = useGroups();
  const allGroups = groupsQuery.data ?? [];
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<FilterState>({
    hasContainers: undefined,
    hazardTagId: undefined,
    ghsCodeId: undefined,
    sort: "name",
    order: "asc",
    selectedGroupIds: [mainGroupId],
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedChemicalId, setSelectedChemicalId] = useState<string | null>(null);
  const [undoState, setUndoState] = useState<{ open: boolean; containerId: string; message: string }>({
    open: false,
    containerId: "",
    message: "",
  });

  const searchParams = {
    search: search || undefined,
    has_containers: filters.hasContainers,
    hazard_tag_id: filters.hazardTagId,
    ghs_code_id: filters.ghsCodeId,
    sort: filters.sort as "name" | "created_at" | "updated_at" | "cas",
    order: filters.order,
  };

  const chemicalQueries = useMultiGroupChemicals(filters.selectedGroupIds, searchParams);
  const chemicals = useMemo(() => chemicalQueries.flatMap((q) => q.data?.items ?? []), [chemicalQueries]);
  const isLoading = chemicalQueries.some((q) => q.isLoading);
  const isError = chemicalQueries.some((q) => q.isError);

  const hazardTagsQuery = useHazardTags(mainGroupId);
  const ghsCodesQuery = useGHSCodes();
  const containersQuery = useContainers(mainGroupId, { limit: 500 });
  const storageTreeQuery = useStorageTree(mainGroupId);
  const unarchiveContainer = useUnarchiveContainer(mainGroupId);

  const hazardTags = hazardTagsQuery.data?.items ?? [];
  const ghsCodes = ghsCodesQuery.data?.items ?? [];

  const containersByChemical = useMemo(() => {
    const map: Record<string, ContainerRead[]> = {};
    for (const c of containersQuery.data?.items ?? []) {
      (map[c.chemical_id] ??= []).push(c);
    }
    return map;
  }, [containersQuery.data]);

  const locationPaths = useMemo(() => {
    const map: Record<string, string> = {};
    const buildPaths = (nodes: StorageLocationNode[], prefix: string) => {
      for (const node of nodes) {
        const path = prefix ? `${prefix} / ${node.name}` : node.name;
        map[node.id] = path;
        buildPaths(node.children, path);
      }
    };
    buildPaths(storageTreeQuery.data ?? [], "");
    return map;
  }, [storageTreeQuery.data]);

  const groupNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const g of allGroups) map[g.id] = g.name;
    return map;
  }, [allGroups]);

  const rows = useMemo<ListRow[]>(() => {
    const out: ListRow[] = [];
    for (const ch of chemicals) {
      const cs = (containersByChemical[ch.id] ?? []).filter((c) => !c.is_archived);
      if (cs.length === 0) {
        out.push({ chemical: ch, container: null, key: ch.id });
      } else {
        for (const c of cs) out.push({ chemical: ch, container: c, key: c.id });
      }
    }
    return out;
  }, [chemicals, containersByChemical]);

  const selectedChemical = useMemo(
    () => chemicals.find((c) => c.id === selectedChemicalId) ?? null,
    [chemicals, selectedChemicalId],
  );

  const badges = useMemo(() => {
    const result: FilterBadge[] = [];
    if (filters.selectedGroupIds.length !== 1 || filters.selectedGroupIds[0] !== mainGroupId) {
      for (const gid of filters.selectedGroupIds) {
        if (gid !== mainGroupId && groupNames[gid]) {
          result.push({ key: `group:${gid}`, label: groupNames[gid], color: "primary" });
        }
      }
    }
    if (filters.hasContainers) result.push({ key: "hasContainers", label: "Has stock", color: "success" });
    if (filters.hazardTagId) {
      const tag = hazardTags.find((t) => t.id === filters.hazardTagId);
      if (tag) result.push({ key: "hazardTagId", label: tag.name, color: "error" });
    }
    if (filters.ghsCodeId) {
      const code = ghsCodes.find((c) => c.id === filters.ghsCodeId);
      if (code) result.push({ key: "ghsCodeId", label: code.code, color: "warning" });
    }
    return result;
  }, [filters, hazardTags, ghsCodes, mainGroupId, groupNames]);

  const handleRemoveBadge = useCallback((key: string) => {
    if (key.startsWith("group:")) {
      const gid = key.slice(6);
      setFilters((prev) => ({ ...prev, selectedGroupIds: prev.selectedGroupIds.filter((id) => id !== gid) }));
    } else {
      setFilters((prev) => ({ ...prev, [key]: undefined }));
    }
  }, []);

  const handleUndo = useCallback(() => {
    unarchiveContainer.mutate(undoState.containerId);
    setUndoState((prev) => ({ ...prev, open: false }));
  }, [unarchiveContainer, undoState.containerId]);

  const detailContent =
    selectedChemical && (
      <ChemicalDetail
        groupId={mainGroupId}
        chemical={selectedChemical}
        containers={containersByChemical[selectedChemical.id] ?? []}
        locationPaths={locationPaths}
        onClose={() => setSelectedChemicalId(null)}
        onAddContainer={() => navigate(`/containers/new?chemicalId=${selectedChemical.id}`)}
      />
    );

  const listPane = (
    <Box sx={{ pt: 3, pb: 4 }}>
      <Box sx={{ px: { xs: 2, md: 3 }, mb: 2 }}>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Box sx={{ flex: 1 }}>
            <SearchBar value={search} onChange={setSearch} />
          </Box>
          <IconButton
            onClick={() => setDrawerOpen(true)}
            sx={{ border: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}
          >
            <TuneIcon />
          </IconButton>
        </Box>
        <FilterBadges badges={badges} onRemove={handleRemoveBadge} />
      </Box>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "10px 1fr auto", md: "14px 1fr 1.2fr 130px" },
          gap: { xs: "0 10px", md: "0 16px" },
          px: { xs: 2, md: 2.5 },
          py: 1,
          fontFamily: mono,
          fontSize: 9,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: "text.secondary",
          borderTop: "1px solid",
          borderBottom: "1px solid",
          borderColor: "divider",
          display: { xs: "none", md: "grid" },
        }}
      >
        <Box />
        <Box>Name</Box>
        <Box>Location</Box>
        <Box sx={{ textAlign: "right" }}>Label</Box>
      </Box>

      {isLoading && (
        <Box sx={{ textAlign: "center", py: 6 }}>
          <CircularProgress size={20} thickness={4} />
        </Box>
      )}
      {isError && (
        <Typography color="error" sx={{ textAlign: "center", py: 4 }}>
          Failed to load chemicals
        </Typography>
      )}

      {rows.map((row) => (
        <ChemicalCard
          key={row.key}
          chemical={row.chemical}
          container={row.container}
          locationPath={row.container ? locationPaths[row.container.location_id] : undefined}
          selected={row.chemical.id === selectedChemicalId}
          onClick={() => setSelectedChemicalId(row.chemical.id)}
        />
      ))}

      {!isLoading && rows.length === 0 && (
        <Typography color="text.secondary" sx={{ textAlign: "center", py: 6 }}>
          {search ? "No chemicals found" : "No chemicals yet"}
        </Typography>
      )}
    </Box>
  );

  return (
    <>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: selectedChemicalId ? "1fr 420px" : "1fr" },
          minHeight: "100vh",
        }}
      >
        <Box sx={{ overflow: "auto" }}>{listPane}</Box>

        {isDesktop && selectedChemicalId && selectedChemical && (
          <Box
            sx={{
              borderLeft: "1px solid",
              borderColor: "divider",
              bgcolor: "background.paper",
              overflow: "auto",
              position: "sticky",
              top: 0,
              maxHeight: "100vh",
            }}
          >
            {detailContent}
          </Box>
        )}
      </Box>

      {!isDesktop && (
        <Drawer
          anchor="bottom"
          open={!!selectedChemicalId}
          onClose={() => setSelectedChemicalId(null)}
          PaperProps={{
            sx: {
              maxHeight: "85vh",
              borderTopLeftRadius: 8,
              borderTopRightRadius: 8,
            },
          }}
        >
          {detailContent}
        </Drawer>
      )}

      <FilterDrawer
        open={drawerOpen}
        onOpen={() => setDrawerOpen(true)}
        onClose={() => setDrawerOpen(false)}
        filters={filters}
        onApply={setFilters}
        hazardTags={hazardTags}
        ghsCodes={ghsCodes}
        groups={allGroups}
      />
      <UndoSnackbar
        open={undoState.open}
        message={undoState.message}
        onUndo={handleUndo}
        onClose={() => setUndoState((prev) => ({ ...prev, open: false }))}
      />
    </>
  );
}
