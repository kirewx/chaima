import { Stack, Chip } from "@mui/material";

export interface FilterBadge {
  key: string;
  label: string;
  color?: "default" | "primary" | "success" | "error" | "warning";
}

interface FilterBadgesProps {
  badges: FilterBadge[];
  onRemove: (key: string) => void;
}

export default function FilterBadges({ badges, onRemove }: FilterBadgesProps) {
  if (badges.length === 0) return null;
  return (
    <Stack direction="row" spacing={0.5} sx={{ flexWrap: "wrap", gap: 0.5 }}>
      {badges.map((badge) => (
        <Chip key={badge.key} label={badge.label} color={badge.color ?? "default"} size="small" onDelete={() => onRemove(badge.key)} variant="outlined" />
      ))}
    </Stack>
  );
}
