import { Box, Collapse } from "@mui/material";
import { useState } from "react";
import type { ChemicalRead } from "../types";
import { ChemicalRow } from "./ChemicalRow";
import { ChemicalInfoBox } from "./ChemicalInfoBox";
import { ContainerGrid } from "./ContainerGrid";
import { useContainersForChemical } from "../api/hooks/useContainers";

interface ExpandedBodyProps {
  groupId: string;
  chemical: ChemicalRead;
}

function ExpandedBody({ groupId, chemical }: ExpandedBodyProps) {
  const { data: containers = [] } = useContainersForChemical(groupId, chemical.id);
  const active = containers.filter((c) => !c.is_archived);
  return (
    <>
      <ChemicalInfoBox chemical={chemical} containers={active} />
      <ContainerGrid
        groupId={groupId}
        containers={active}
        onAdd={() => alert("Drawer coming in Task 11/13")}
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
            <ExpandedBody groupId={groupId} chemical={c} />
          </Collapse>
        </Box>
      ))}
    </Box>
  );
}
