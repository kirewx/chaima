import { Box, Stack, Typography, Chip } from "@mui/material";
import type { ChemicalRead } from "../types";
import { useContainersForChemical } from "../api/hooks/useContainers";
import { useStorageLocation } from "../api/hooks/useStorageLocations";

interface LocationNameProps {
  groupId: string;
  locationId: string;
}

function LocationName({ groupId, locationId }: LocationNameProps) {
  const { data } = useStorageLocation(groupId, locationId);
  return <>{data?.name ?? "—"}</>;
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
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            {first ? (
              <LocationName groupId={groupId} locationId={first.location_id} />
            ) : (
              "—"
            )}
          </Typography>
          {first && (
            <Chip
              label={first.identifier}
              size="small"
              sx={{
                bgcolor: "primary.light",
                color: "primary.dark",
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                fontSize: 10,
                height: 18,
              }}
            />
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
