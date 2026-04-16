import { Box, Tooltip } from "@mui/material";
import type { GHSCodeRead } from "../types";

const HAZARD_LABELS: Record<string, string> = {
  GHS01: "Explosive",
  GHS02: "Flammable",
  GHS03: "Oxidizer",
  GHS04: "Compressed gas",
  GHS05: "Corrosive",
  GHS06: "Acute toxicity",
  GHS07: "Harmful / irritant",
  GHS08: "Serious health hazard",
  GHS09: "Environmental hazard",
};

const KNOWN_CODES = new Set(Object.keys(HAZARD_LABELS));

interface Props {
  codes: GHSCodeRead[];
  size?: number;
}

export function GHSPictogramRow({ codes, size = 48 }: Props) {
  const pictograms = Array.from(
    new Set(codes.map((c) => c.pictogram).filter((p): p is string => !!p)),
  ).filter((p) => KNOWN_CODES.has(p));

  if (pictograms.length === 0) return null;

  return (
    <Box
      role="list"
      aria-label="GHS hazard pictograms"
      sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}
    >
      {pictograms.map((code) => {
        const label = HAZARD_LABELS[code] ?? code;
        return (
          <Tooltip key={code} title={`${code} — ${label}`} arrow>
            <Box
              component="img"
              role="listitem"
              src={`/ghs/${code}.svg`}
              alt={`${code} — ${label}`}
              sx={{ width: size, height: size, flexShrink: 0 }}
            />
          </Tooltip>
        );
      })}
    </Box>
  );
}
