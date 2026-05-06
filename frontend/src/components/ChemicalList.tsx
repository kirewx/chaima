import { Box, Button, CircularProgress, Collapse, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ChemicalRead } from "../types";
import { ChemicalRow } from "./ChemicalRow";
import { ChemicalInfoBox } from "./ChemicalInfoBox";
import { ContainerGrid } from "./ContainerGrid";
import { useContainersForChemical } from "../api/hooks/useContainers";
import { useChemicalDetail } from "../api/hooks/useChemicals";
import { useDrawer } from "./drawer/DrawerContext";

interface ExpandedBodyProps {
  groupId: string;
  chemical: ChemicalRead;
}

function ExpandedBody({ groupId, chemical }: ExpandedBodyProps) {
  const { data: containers = [] } = useContainersForChemical(groupId, chemical.id);
  const { data: detail } = useChemicalDetail(groupId, chemical.id);
  const active = containers.filter((c) => !c.is_archived);
  const drawer = useDrawer();
  return (
    <>
      <ChemicalInfoBox
        chemical={chemical}
        containers={active}
        groupId={groupId}
        ghsCodes={detail?.ghs_codes ?? []}
        hazardTags={detail?.hazard_tags ?? []}
      />
      <ContainerGrid
        groupId={groupId}
        containers={active}
        onAdd={() => drawer.open({ kind: "container-new", chemicalId: chemical.id })}
      />
    </>
  );
}

interface Props {
  items: ChemicalRead[];
  loading: boolean;
  groupId: string;
  /** When set, a "+ Load N more" button appears at the end of the list. Omit in multi-group mode. */
  onLoadMore?: () => void;
  hasMore?: boolean;
  loadingMore?: boolean;
  /** Page size hint shown on the load-more button. Defaults to 20. */
  loadMoreSize?: number;
  /** Optional footer text shown when there's no more to load (or in modes that don't paginate). */
  footerNote?: string;
}

export function ChemicalList({
  items,
  loading,
  groupId,
  onLoadMore,
  hasMore,
  loadingMore,
  loadMoreSize = 20,
  footerNote,
}: Props) {
  const [openIds, setOpenIds] = useState<Set<string>>(new Set());
  const [searchParams, setSearchParams] = useSearchParams();

  // Deep-link support: `?expand=<chemicalId>` (used by ContainerCard on
  // the Storage page to jump back here and pre-expand that chemical's row).
  useEffect(() => {
    const expandId = searchParams.get("expand");
    if (!expandId) return;
    if (!items.some((i) => i.id === expandId)) return;
    setOpenIds((prev) => {
      if (prev.has(expandId)) return prev;
      const next = new Set(prev);
      next.add(expandId);
      return next;
    });
    const next = new URLSearchParams(searchParams);
    next.delete("expand");
    setSearchParams(next, { replace: true });
  }, [items, searchParams, setSearchParams]);

  const toggle = (id: string) =>
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (loading) {
    return <Box sx={{ p: 2, color: "text.secondary" }}>Loading…</Box>;
  }
  if (items.length === 0) {
    return <Box sx={{ p: 2, color: "text.secondary" }}>No chemicals.</Box>;
  }
  const showLoadMore = !!onLoadMore && !!hasMore;
  const showAllLoadedNote =
    !!onLoadMore && !hasMore && items.length > 0;

  return (
    <Box>
      <Box
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1,
          overflow: "hidden",
          bgcolor: "background.paper",
        }}
      >
        {items.map((c, i) => (
          <Box
            key={c.id}
            sx={{
              borderBottom: i < items.length - 1 ? "1px solid" : "none",
              borderColor: "divider",
            }}
          >
            <ChemicalRow
              chemical={c}
              groupId={groupId}
              expanded={openIds.has(c.id)}
              onToggle={() => toggle(c.id)}
            />
            <Collapse in={openIds.has(c.id)} unmountOnExit>
              <Box
                sx={{
                  borderTop: "1px solid",
                  borderColor: "divider",
                  bgcolor: "action.hover",
                  pb: 0.5,
                }}
              >
                <ExpandedBody groupId={groupId} chemical={c} />
              </Box>
            </Collapse>
          </Box>
        ))}
      </Box>

      {showLoadMore && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={
              loadingMore ? <CircularProgress size={14} /> : <AddIcon />
            }
            onClick={onLoadMore}
            disabled={loadingMore}
          >
            {loadingMore ? "Loading…" : `Load ${loadMoreSize} more`}
          </Button>
        </Box>
      )}

      {showAllLoadedNote && (
        <Typography
          variant="caption"
          color="text.disabled"
          sx={{ display: "block", textAlign: "center", py: 1.5 }}
        >
          All {items.length} chemicals loaded.
        </Typography>
      )}

      {footerNote && !showLoadMore && !showAllLoadedNote && (
        <Typography
          variant="caption"
          color="text.disabled"
          sx={{ display: "block", textAlign: "center", py: 1.5 }}
        >
          {footerNote}
        </Typography>
      )}
    </Box>
  );
}
