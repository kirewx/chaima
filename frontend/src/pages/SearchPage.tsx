import { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Box, IconButton, CircularProgress, Typography } from "@mui/material";
import TuneIcon from "@mui/icons-material/Tune";
import { useGroup } from "../components/GroupContext";
import { useChemicals } from "../api/hooks/useChemicals";
import { useHazardTags } from "../api/hooks/useHazardTags";
import { useGHSCodes } from "../api/hooks/useGHSCodes";
import SearchBar from "../components/SearchBar";
import FilterDrawer, { type FilterState } from "../components/FilterDrawer";
import FilterBadges, { type FilterBadge } from "../components/FilterBadges";
import ChemicalCard from "../components/ChemicalCard";
import SwipeableRow from "../components/SwipeableRow";
import UndoSnackbar from "../components/UndoSnackbar";
import { useArchiveContainer, useUnarchiveContainer } from "../api/hooks/useContainers";

const DEFAULT_FILTERS: FilterState = {
  hasContainers: undefined,
  hazardTagId: undefined,
  ghsCodeId: undefined,
  sort: "name",
  order: "asc",
};

export default function SearchPage() {
  const { groupId } = useGroup();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [undoState, setUndoState] = useState<{ open: boolean; containerId: string; message: string }>({ open: false, containerId: "", message: "" });

  const chemicalsQuery = useChemicals(groupId, {
    search: search || undefined,
    has_containers: filters.hasContainers,
    hazard_tag_id: filters.hazardTagId,
    ghs_code_id: filters.ghsCodeId,
    sort: filters.sort as "name" | "created_at" | "updated_at" | "cas",
    order: filters.order,
  });

  const hazardTagsQuery = useHazardTags(groupId);
  const ghsCodesQuery = useGHSCodes();
  const archiveContainer = useArchiveContainer(groupId);
  const unarchiveContainer = useUnarchiveContainer(groupId);

  const hazardTags = hazardTagsQuery.data?.items ?? [];
  const ghsCodes = ghsCodesQuery.data?.items ?? [];
  const chemicals = useMemo(() => chemicalsQuery.data?.pages.flatMap((p) => p.items) ?? [], [chemicalsQuery.data]);

  const badges = useMemo(() => {
    const result: FilterBadge[] = [];
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
  }, [filters, hazardTags, ghsCodes]);

  const handleRemoveBadge = useCallback((key: string) => {
    setFilters((prev) => ({ ...prev, [key]: undefined }));
  }, []);

  const handleArchive = useCallback((containerId: string, identifier: string) => {
    archiveContainer.mutate(containerId, {
      onSuccess: () => { setUndoState({ open: true, containerId, message: `Container ${identifier} archived` }); },
    });
  }, [archiveContainer]);

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
        {chemicalsQuery.isLoading && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>}
        {chemicalsQuery.isError && <Typography color="error" sx={{ textAlign: "center", py: 4 }}>Failed to load chemicals</Typography>}
        {chemicals.map((chemical) => (
          <SwipeableRow key={chemical.id} onSwipeRight={() => navigate(`/containers/new?chemicalId=${chemical.id}`)}>
            <ChemicalCard chemical={chemical} containers={[]} hazardTags={[]} locationPaths={{}} supplierNames={{}} onAddContainer={() => navigate(`/containers/new?chemicalId=${chemical.id}`)} />
          </SwipeableRow>
        ))}
        {!chemicalsQuery.isLoading && chemicals.length === 0 && (
          <Typography color="text.secondary" sx={{ textAlign: "center", py: 4 }}>
            {search ? "No chemicals found" : "No chemicals yet"}
          </Typography>
        )}
      </Box>
      <FilterDrawer open={drawerOpen} onOpen={() => setDrawerOpen(true)} onClose={() => setDrawerOpen(false)} filters={filters} onApply={setFilters} hazardTags={hazardTags} ghsCodes={ghsCodes} />
      <UndoSnackbar open={undoState.open} message={undoState.message} onUndo={handleUndo} onClose={() => setUndoState((prev) => ({ ...prev, open: false }))} />
    </Box>
  );
}
