import { Box } from "@mui/material";
import type { ChemicalRead } from "../types";

interface Props {
  items: ChemicalRead[];
  loading: boolean;
}

export function ChemicalList({ items, loading }: Props) {
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
            p: 1.5,
            borderBottom: i < items.length - 1 ? "1px solid" : "none",
            borderColor: "divider",
          }}
        >
          {c.name}
        </Box>
      ))}
    </Box>
  );
}
