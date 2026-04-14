import { Box } from "@mui/material";
import { useState } from "react";
import type { ChemicalRead } from "../types";
import { ChemicalRow } from "./ChemicalRow";

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
          {/* Task 9 will render an expanded info box here when expanded */}
        </Box>
      ))}
    </Box>
  );
}
