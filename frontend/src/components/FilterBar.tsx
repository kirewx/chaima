import { Box, Chip } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

export interface ActiveFilter {
  key: string;
  label: string;
  onRemove: () => void;
}

interface Props {
  filters: ActiveFilter[];
}

export function FilterBar({ filters }: Props) {
  if (filters.length === 0) return null;
  return (
    <Box
      sx={{
        display: "flex",
        flexWrap: "wrap",
        gap: 0.75,
        px: 1.5,
        py: 1,
        borderBottom: "1px solid",
        borderColor: "divider",
        bgcolor: "background.default",
      }}
    >
      {filters.map((f) => (
        <Chip
          key={f.key}
          label={f.label}
          size="small"
          onDelete={f.onRemove}
          deleteIcon={<CloseIcon />}
          sx={{
            bgcolor: "primary.main",
            color: "primary.contrastText",
            "& .MuiChip-deleteIcon": { color: "primary.contrastText", opacity: 0.7 },
          }}
        />
      ))}
    </Box>
  );
}
