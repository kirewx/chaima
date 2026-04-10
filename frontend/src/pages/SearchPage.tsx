import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Box, IconButton, CircularProgress, Typography } from "@mui/material";
import TuneIcon from "@mui/icons-material/Tune";
import { useGroup } from "../components/GroupContext";
import { useMultiGroupChemicals } from "../api/hooks/useChemicals";
import { useHazardTags } from "../api/hooks/useHazardTags";
import { useGHSCodes } from "../api/hooks/useGHSCodes";
import { useGroups } from "../api/hooks/useGroups";
import SearchBar from "../components/SearchBar";
import FilterDrawer, { type FilterState } from "../components/FilterDrawer";
import FilterBadges, { type FilterBadge } from "../components/FilterBadges";
import ChemicalCard from "../components/ChemicalCard";
import SwipeableRow from "../components/SwipeableRow";
import UndoSnackbar from "../components/UndoSnackbar";
import { useUnarchiveContainer } from "../api/hooks/useContainers";

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
  const unarchiveContainer = useUnarchiveContainer(mainGroupId);

  const hazardTags = hazardTagsQuery.data?.items ?? [];
  const ghsCodes = ghsCodesQuery.data?.items ?? [];

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
    <Box sx={{ p: 2, pb: 4 }}>
      <Box sx={{ display: "flex", gap: 1, mb: 1 }}>
        <Box sx={{ flex: 1 }}><SearchBar value={search} onChange={setSearch} /></Box>
        <IconButton onClick={() => setDrawerOpen(true)} sx={{ bgcolor: "background.paper", border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
          <TuneIcon />
        </IconButton>
      </Box>
      <FilterBadges badges={badges} onRemove={handleRemoveBadge} />
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1, mt: 1 }}>
        {isLoading && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>}
        {isError && <Typography color="error" sx={{ textAlign: "center", py: 4 }}>Failed to load chemicals</Typography>}
        {chemicals.map((chemical) => (
          <SwipeableRow key={chemical.id} onSwipeRight={() => navigate(`/containers/new?chemicalId=${chemical.id}`)}>
            <ChemicalCard chemical={chemical} containers={[]} hazardTags={[]} locationPaths={{}} supplierNames={{}} onAddContainer={() => navigate(`/containers/new?chemicalId=${chemical.id}`)} />
          </SwipeableRow>
        ))}
        {!isLoading && chemicals.length === 0 && (
          <Typography color="text.secondary" sx={{ textAlign: "center", py: 4 }}>
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
