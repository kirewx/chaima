import { Box, Stack, Typography, Chip } from "@mui/material";
import type { ChemicalRead } from "../types";
import { useContainersForChemical } from "../api/hooks/useContainers";
import { useStorageLocation } from "../api/hooks/useStorageLocations";
import { DEFAULT_STORAGE_COLOR } from "./drawer/StorageForm";

function chipTextColor(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? "rgba(0,0,0,0.8)" : "rgba(255,255,255,0.9)";
}

interface FirstContainerLabelProps {
  groupId: string;
  locationId: string;
  identifier: string;
}

function FirstContainerLabel({ groupId, locationId, identifier }: FirstContainerLabelProps) {
  const { data } = useStorageLocation(groupId, locationId);
  const color = data?.color ?? DEFAULT_STORAGE_COLOR;
  return (
    <>
      <Typography variant="body2" sx={{ fontWeight: 500 }}>
        {data?.name ?? "—"}
      </Typography>
      <Chip
        label={identifier}
        size="small"
        sx={{
          bgcolor: color,
          color: chipTextColor(color),
          fontFamily: "'JetBrains Mono', ui-monospace, monospace",
          fontSize: 10,
          height: 18,
        }}
      />
    </>
  );
}

interface Props {
  chemical: ChemicalRead;
  groupId: string;
  expanded: boolean;
  onToggle: () => void;
}

export function ChemicalRow({ chemical, groupId, expanded, onToggle }: Props) {
  const { data: containers = [] } = useContainersForChemical(groupId, chemical.id);
  const active = containers.filter((c) => !c.is_archived);
  const first = active[0];
  const more = active.length - 1;

  return (
    <Box
      onClick={onToggle}
      sx={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        px: 2,
        py: 1.25,
        gap: 2,
        cursor: "pointer",
        bgcolor: expanded ? "background.default" : "transparent",
        "&:hover": { bgcolor: "action.hover" },
      }}
    >
      <Stack sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="body1" noWrap sx={{ fontWeight: 500, lineHeight: 1.2 }}>
          {chemical.name}
        </Typography>
        <Typography
          variant="caption"
          sx={{
            color: chemical.cas ? "text.secondary" : "text.disabled",
            fontStyle: chemical.cas ? "normal" : "italic",
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            mt: 0.4,
          }}
        >
          {chemical.cas ?? "no CAS"}
        </Typography>
      </Stack>
      <Stack sx={{ textAlign: "right", pl: 2, flexShrink: 0 }}>
        <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", justifyContent: "flex-end" }}>
          {first ? (
            <FirstContainerLabel
              groupId={groupId}
              locationId={first.location_id}
              identifier={first.identifier}
            />
          ) : (
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              —
            </Typography>
          )}
        </Stack>
        <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", justifyContent: "flex-end", mt: 0.4 }}>
          <Typography variant="caption" color="text.disabled">
            {first ? `${first.amount} ${first.unit}` : "no containers"}
          </Typography>
          {more > 0 && (
            <Chip
              label={`+${more}`}
              size="small"
              sx={{ height: 16, fontSize: 10, bgcolor: "action.selected" }}
            />
          )}
        </Stack>
      </Stack>
    </Box>
  );
}
