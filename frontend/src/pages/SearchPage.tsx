import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Box, IconButton, CircularProgress, Typography } from "@mui/material";
import TuneIcon from "@mui/icons-material/Tune";
import { useGroup } from "../components/GroupContext";
import { useMultiGroupChemicals } from "../api/hooks/useChemicals";
import { useHazardTags } from "../api/hooks/useHazardTags";
import { useGHSCodes } from "../api/hooks/useGHSCodes";
import { useGroups } from "../api/hooks/useGroups";
import { useContainers, useUnarchiveContainer } from "../api/hooks/useContainers";
import { useSuppliers } from "../api/hooks/useSuppliers";
import { useStorageTree } from "../api/hooks/useStorageLocations";
import SearchBar from "../components/SearchBar";
import FilterDrawer, { type FilterState } from "../components/FilterDrawer";
import FilterBadges, { type FilterBadge } from "../components/FilterBadges";
import ChemicalCard from "../components/ChemicalCard";
import SwipeableRow from "../components/SwipeableRow";
import UndoSnackbar from "../components/UndoSnackbar";
import type { StorageLocationNode, ContainerRead } from "../types";

export default function SearchPage() {
  const { groupId: mainGroupId } = useGroup();
  const navigate = useNavigate();
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
  const [undoState, setUndoState] = useState<{ open: boolean; containerId: string; message: string }>({ open: false, containerId: "", message: "" });

  const searchParams = {
    search: search || undefined,
    has_containers: filters.hasContainers,
    hazard_tag_id: filters.hazardTagId,
    ghs_code_id: filters.ghsCodeId,
    sort: filters.sort as "name" | "created_at" | "updated_at" | "cas",
    order: filters.order,
  };

  const chemicalQueries = useMultiGroupChemicals(filters.selectedGroupIds, searchParams);

  const chemicals = useMemo(() => {
    return chemicalQueries.flatMap((q) => q.data?.items ?? []);
  }, [chemicalQueries]);

  const isLoading = chemicalQueries.some((q) => q.isLoading);
  const isError = chemicalQueries.some((q) => q.isError);

  const hazardTagsQuery = useHazardTags(mainGroupId);
  const ghsCodesQuery = useGHSCodes();
  const containersQuery = useContainers(mainGroupId, { limit: 500 });
  const suppliersQuery = useSuppliers(mainGroupId);
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

  const supplierNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const s of suppliersQuery.data?.items ?? []) {
      map[s.id] = s.name;
    }
    return map;
  }, [suppliersQuery.data]);

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

  const badges = useMemo(() => {
    const result: FilterBadge[] = [];
    if (
      filters.selectedGroupIds.length !== 1 ||
      filters.selectedGroupIds[0] !== mainGroupId
    ) {
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
      setFilters((prev) => ({
        ...prev,
        selectedGroupIds: prev.selectedGroupIds.filter((id) => id !== gid),
      }));
    } else {
      setFilters((prev) => ({ ...prev, [key]: undefined }));
    }
  }, []);

  const handleUndo = useCallback(() => {
    unarchiveContainer.mutate(undoState.containerId);
    setUndoState((prev) => ({ ...prev, open: false }));
  }, [unarchiveContainer, undoState.containerId]);

  return (
    <Box sx={{ pb: 8 }}>
      <Box sx={{ px: 2.5, pt: 3, pb: 2 }}>
        <Typography
          sx={{
            fontFamily: "'Fraunces', Georgia, serif",
            fontSize: 32,
            fontWeight: 500,
            letterSpacing: "-0.025em",
            lineHeight: 1,
            mb: 0.5,
          }}
        >
          Chemicals
        </Typography>
        <Typography
          sx={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            color: "text.secondary",
            opacity: 0.7,
            mb: 2.5,
          }}
        >
          {chemicals.length} {chemicals.length === 1 ? "entry" : "entries"} · inventory
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Box sx={{ flex: 1 }}><SearchBar value={search} onChange={setSearch} /></Box>
          <IconButton onClick={() => setDrawerOpen(true)} sx={{ bgcolor: "background.paper", border: "1px solid", borderColor: "divider", borderRadius: 0.5 }}>
            <TuneIcon />
          </IconButton>
        </Box>
        <FilterBadges badges={badges} onRemove={handleRemoveBadge} />
      </Box>
      <Box sx={{ borderTop: "1px solid", borderColor: "divider" }}>
        {isLoading && <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress size={20} thickness={4} /></Box>}
        {isError && <Typography color="error" sx={{ textAlign: "center", py: 4 }}>Failed to load chemicals</Typography>}
        {chemicals.map((chemical) => (
          <SwipeableRow key={chemical.id} onSwipeRight={() => navigate(`/containers/new?chemicalId=${chemical.id}`)}>
            <ChemicalCard chemical={chemical} containers={containersByChemical[chemical.id] ?? []} hazardTags={[]} locationPaths={locationPaths} supplierNames={supplierNames} onAddContainer={() => navigate(`/containers/new?chemicalId=${chemical.id}`)} />
          </SwipeableRow>
        ))}
        {!isLoading && chemicals.length === 0 && (
          <Typography color="text.secondary" sx={{ textAlign: "center", py: 6, fontFamily: "'Fraunces', serif", fontStyle: "italic" }}>
            {search ? "No chemicals found" : "No chemicals yet"}
          </Typography>
        )}
      </Box>
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
      <UndoSnackbar open={undoState.open} message={undoState.message} onUndo={handleUndo} onClose={() => setUndoState((prev) => ({ ...prev, open: false }))} />
    </Box>
  );
}
