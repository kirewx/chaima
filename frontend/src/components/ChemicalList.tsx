import { Box, Collapse } from "@mui/material";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { ChemicalRead } from "../types";
import { ChemicalRow } from "./ChemicalRow";
import { ChemicalInfoBox } from "./ChemicalInfoBox";
import { ContainerGrid } from "./ContainerGrid";
import { useContainersForChemical } from "../api/hooks/useContainers";
import { useDrawer } from "./drawer/DrawerContext";

interface ExpandedBodyProps {
  groupId: string;
  chemical: ChemicalRead;
}

function ExpandedBody({ groupId, chemical }: ExpandedBodyProps) {
  const { data: containers = [] } = useContainersForChemical(groupId, chemical.id);
  const active = containers.filter((c) => !c.is_archived);
  const drawer = useDrawer();
  return (
    <>
      <ChemicalInfoBox chemical={chemical} containers={active} />
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
}

export function ChemicalList({ items, loading, groupId }: Props) {
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
  return (
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
  );
}
