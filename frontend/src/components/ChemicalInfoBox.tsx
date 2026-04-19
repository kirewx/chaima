import { Box, Stack, Typography, Link as MuiLink } from "@mui/material";
import LinkIcon from "@mui/icons-material/Link";
import DescriptionIcon from "@mui/icons-material/Description";
import type {
  ChemicalRead,
  ContainerRead,
  GHSCodeRead,
  HazardTagRead,
} from "../types";
import { ChemicalMenu } from "./ChemicalMenu";
import { GHSPictogramRow } from "./GHSPictogramRow";
import { HazardTagChips } from "./HazardTagChips";
import { useChemicalStructureSvg } from "../api/hooks/useChemicalStructureSvg";

interface Props {
  chemical: ChemicalRead;
  containers: ContainerRead[];
  ghsCodes?: GHSCodeRead[];
  hazardTags?: HazardTagRead[];
  groupId: string;
}

function propertyBullets(c: ChemicalRead): { k: string; v: string }[] {
  const out: { k: string; v: string }[] = [];
  if (c.molar_mass != null) out.push({ k: "Molar mass", v: `${c.molar_mass} g/mol` });
  if (c.boiling_point != null) out.push({ k: "Boiling point", v: `${c.boiling_point} °C` });
  if (c.melting_point != null) out.push({ k: "Melting point", v: `${c.melting_point} °C` });
  if (c.density != null) out.push({ k: "Density", v: `${c.density} g/cm³` });
  return out;
}

export function ChemicalInfoBox({
  chemical,
  containers,
  ghsCodes = [],
  hazardTags = [],
  groupId,
}: Props) {
  // Total stock grouped by unit so we don't mix L + mL
  const totals = containers.reduce<Record<string, number>>((acc, cont) => {
    acc[cont.unit] = (acc[cont.unit] ?? 0) + cont.amount;
    return acc;
  }, {});
  const totalText =
    Object.entries(totals)
      .map(([u, v]) => `${Number(v.toFixed(3))} ${u}`)
      .join(" · ") || "—";
  const props = propertyBullets(chemical);
  const { data: structureSvg, isLoading: svgLoading } =
    useChemicalStructureSvg(groupId, chemical.id);

  return (
    <Box
      sx={{
        m: 2,
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: "1fr 240px" },
        bgcolor: "background.paper",
        overflow: "hidden",
        position: "relative",
      }}
    >
      <Box sx={{ position: "absolute", bottom: 10, right: 10, zIndex: 2 }}>
        <ChemicalMenu chemical={chemical} />
      </Box>
      {/* Main area */}
      <Box sx={{ p: 2.5, display: "flex", gap: 2 }}>
        <Box sx={{ flexShrink: 0 }}>
          <Box
            sx={{
              width: { xs: 80, md: 100 },
              height: { xs: 80, md: 100 },
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
              bgcolor: "background.default",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              p: 1,
              overflow: "hidden",
            }}
          >
            {structureSvg ? (
              <Box
                aria-label={`${chemical.name} structure`}
                sx={{
                  maxWidth: "100%",
                  maxHeight: "100%",
                  color: "text.primary",
                  "& svg": {
                    width: "100%",
                    height: "100%",
                    display: "block",
                  },
                }}
                dangerouslySetInnerHTML={{ __html: structureSvg }}
              />
            ) : svgLoading ? (
              <Typography variant="caption" color="text.disabled">
                …
              </Typography>
            ) : (
              <Typography variant="caption" color="text.disabled">
                no structure
              </Typography>
            )}
          </Box>
        </Box>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack component="ul" sx={{ listStyle: "none", p: 0, m: 0 }}>
            {props.map((p) => (
              <Box
                component="li"
                key={p.k}
                sx={{
                  display: "flex",
                  fontSize: 12,
                  color: "text.primary",
                  py: 0.3,
                  lineHeight: 1.55,
                }}
              >
                <Box sx={{ minWidth: { xs: 70, md: 92 }, color: "text.secondary" }}>
                  {p.k}
                </Box>
                <Box>{p.v}</Box>
              </Box>
            ))}
            {chemical.comment && (
              <Box
                component="li"
                sx={{
                  mt: 1,
                  p: 1.25,
                  bgcolor: "warning.light",
                  borderLeft: "2px solid",
                  borderColor: "warning.main",
                  borderRadius: "0 3px 3px 0",
                  fontSize: 12,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    display: "block",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    color: "warning.dark",
                    fontWeight: 600,
                    mb: 0.25,
                  }}
                >
                  Comment
                </Typography>
                {chemical.comment}
              </Box>
            )}
          </Stack>
          {chemical.synonym_names?.length > 0 && (
            <Box sx={{ mt: 1.5 }}>
              <Typography
                variant="caption"
                sx={{
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  color: "text.secondary",
                  fontWeight: 600,
                  mb: 0.5,
                  display: "block",
                }}
              >
                Also known as
              </Typography>
              <Typography variant="caption" sx={{ color: "text.disabled", fontSize: 11 }}>
                {chemical.synonym_names.slice(0, 5).join(" · ")}
              </Typography>
            </Box>
          )}
        </Box>
      </Box>

      {/* Sidebar */}
      <Box
        sx={{
          p: 2,
          bgcolor: "background.default",
        }}
      >
        <Box sx={{ pb: 1.5, mb: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
          <Typography
            sx={{ fontSize: 20, fontWeight: 600, lineHeight: 1, color: "text.primary" }}
          >
            {totalText}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.4 }}>
            <b>{containers.length} containers</b>
          </Typography>
        </Box>

        {(ghsCodes.length > 0 || hazardTags.length > 0) && (
          <Box sx={{ mb: 1.5 }}>
            <Typography variant="h5" sx={{ mb: 0.75 }}>
              Hazards
            </Typography>
            {ghsCodes.length > 0 && (
              <Box sx={{ mb: hazardTags.length > 0 ? 1 : 0 }}>
                <GHSPictogramRow codes={ghsCodes} size={40} />
              </Box>
            )}
            {hazardTags.length > 0 && <HazardTagChips tags={hazardTags} />}
          </Box>
        )}

        <Typography variant="h5" sx={{ mb: 0.5 }}>
          Links
        </Typography>
        {chemical.cid ? (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", mb: 0.5 }}>
            <LinkIcon sx={{ fontSize: 12, color: "primary.main" }} />
            <MuiLink
              href={`https://pubchem.ncbi.nlm.nih.gov/compound/${chemical.cid}`}
              target="_blank"
              rel="noopener"
              sx={{ fontSize: 11 }}
            >
              PubChem {chemical.cid}
            </MuiLink>
          </Stack>
        ) : (
          <Typography variant="caption" color="text.disabled" sx={{ display: "block", mb: 0.5 }}>
            No PubChem link
          </Typography>
        )}
        {chemical.sds_path ? (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
            <DescriptionIcon sx={{ fontSize: 12, color: "primary.main" }} />
            <MuiLink
              href={`/uploads/${chemical.sds_path}`}
              target="_blank"
              rel="noopener"
              sx={{ fontSize: 11 }}
            >
              Safety data sheet
            </MuiLink>
          </Stack>
        ) : (
          <Typography variant="caption" color="text.disabled" sx={{ display: "block" }}>
            No SDS uploaded
          </Typography>
        )}
      </Box>
    </Box>
  );
}
