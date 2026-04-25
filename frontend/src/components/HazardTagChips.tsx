import { Chip, Stack } from "@mui/material";
import type { HazardTagRead } from "../types";

interface Props {
  tags: HazardTagRead[];
}

export function HazardTagChips({ tags }: Props) {
  if (tags.length === 0) return null;
  return (
    <Stack direction="row" spacing={0.5} useFlexGap sx={{ flexWrap: "wrap" }}>
      {tags.map((t) => (
        <Chip key={t.id} label={t.name} size="small" variant="outlined" />
      ))}
    </Stack>
  );
}
