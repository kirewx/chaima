import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Alert, Box, Button, Chip, Stack, Typography, Link as MuiLink } from "@mui/material";
import LinkIcon from "@mui/icons-material/Link";
import DescriptionIcon from "@mui/icons-material/Description";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import SearchIcon from "@mui/icons-material/Search";
import type {
  ChemicalRead,
  ContainerRead,
  GHSCodeRead,
  HazardTagRead,
  PStatementRead,
} from "../types";
import { ChemicalMenu } from "./ChemicalMenu";
import { GHSPictogramRow } from "./GHSPictogramRow";
import { HazardTagChips } from "./HazardTagChips";
import { HazardStatementsDialog } from "./HazardStatementsDialog";
import { StructureDialog } from "./StructureDialog";
import { worstSignalWord } from "../utils/hazardSignal";
import { useChemicalStructureSvg } from "../api/hooks/useChemicalStructureSvg";
import { useUploadSDS } from "../api/hooks/useChemicals";
import { gestisUrl, useGestisResolve } from "../api/hooks/useGestis";
import { useGroup, useIsGroupAdmin } from "../api/hooks/useGroups";
import { useDrawer } from "./drawer/DrawerContext";
import { useOrders } from "../api/hooks/useOrders";
import { RoleGate } from "./RoleGate";
import { casSearchUrl, sdsPdfSearchUrl } from "../utils/sdsResearch";

interface Props {
  chemical: ChemicalRead;
  containers: ContainerRead[];
  ghsCodes?: GHSCodeRead[];
  hazardTags?: HazardTagRead[];
  pStatements?: PStatementRead[];
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
  pStatements = [],
  groupId,
}: Props) {
  const [hpOpen, setHpOpen] = useState(false);
  const [structureOpen, setStructureOpen] = useState(false);
  const sdsInputRef = useRef<HTMLInputElement | null>(null);
  const uploadSds = useUploadSDS(groupId, chemical.id);
  const [sdsError, setSdsError] = useState<string | null>(null);
  const isAdmin = useIsGroupAdmin(groupId);
  const { data: group } = useGroup(groupId);

  const resolveGestis = useGestisResolve(groupId, chemical.id);
  const resolveGestisMutate = resolveGestis.mutate;
  // Auto-resolve once per opened chemical: only when a CAS exists but no
  // zvg is stored yet. A miss changes nothing, so the effect won't re-fire
  // until the box is reopened — misses are retried on the next open.
  useEffect(() => {
    if (chemical.zvg || !chemical.cas) return;
    resolveGestisMutate();
  }, [chemical.id, chemical.zvg, chemical.cas, resolveGestisMutate]);

  const onSdsSelected = async (file: File) => {
    setSdsError(null);
    if (file.type !== "application/pdf") {
      setSdsError("SDS muss eine PDF-Datei sein.");
      return;
    }
    try {
      await uploadSds.mutateAsync(file);
    } catch (e) {
      const status = (e as { response?: { status?: number } }).response?.status;
      setSdsError(
        status === 415
          ? "SDS muss eine PDF-Datei sein."
          : "Upload fehlgeschlagen — bitte erneut versuchen.",
      );
    }
  };
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
  const drawer = useDrawer();
  const openOrders = useOrders(groupId, { chemical_id: chemical.id, status: "ordered" });
  const onOrderItems = openOrders.data?.items ?? [];
  const onOrderCount = onOrderItems.reduce((sum, o) => sum + o.package_count, 0);
  const nextArrival = onOrderItems
    .map((o) => o.expected_arrival)
    .filter((d): d is string => Boolean(d))
    .sort()[0];

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
        <ChemicalMenu chemical={chemical} groupId={groupId} />
      </Box>
      {/* Main area */}
      <Box sx={{ p: 2.5, display: "flex", gap: 2 }}>
        <Box sx={{ flexShrink: 0 }}>
          <Box
            {...(structureSvg
              ? {
                  role: "button",
                  tabIndex: 0,
                  "aria-label": `Show enlarged structure of ${chemical.name}`,
                  onClick: () => setStructureOpen(true),
                  onKeyDown: (e: KeyboardEvent) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setStructureOpen(true);
                    }
                  },
                }
              : {})}
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
              position: "relative",
              ...(structureSvg && {
                "@media (hover: hover)": {
                  cursor: "zoom-in",
                  "&:hover": { borderColor: "primary.main" },
                  "&:hover .structure-thumb": { opacity: 0.55 },
                  "&:hover .structure-zoom-icon": { opacity: 1 },
                },
              }),
            }}
          >
            {structureSvg ? (
              <>
                <Box
                  className="structure-thumb"
                  aria-hidden
                  sx={{
                    maxWidth: "100%",
                    maxHeight: "100%",
                    color: "text.primary",
                    transition: "opacity 0.15s",
                    "& svg": {
                      width: "100%",
                      height: "100%",
                      display: "block",
                    },
                  }}
                  dangerouslySetInnerHTML={{ __html: structureSvg }}
                />
                <SearchIcon
                  className="structure-zoom-icon"
                  sx={{
                    position: "absolute",
                    fontSize: 28,
                    color: "text.primary",
                    opacity: 0,
                    transition: "opacity 0.15s",
                    pointerEvents: "none",
                  }}
                />
              </>
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
          {chemical.is_archived && (
            <Alert severity="warning" sx={{ mt: 1, py: 0 }}>
              This chemical is archived. Ordering it does not auto-unarchive.
            </Alert>
          )}
          <Stack spacing={0.5} sx={{ mt: 1 }}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => drawer.open({ kind: "new-order", groupId, chemicalId: chemical.id })}
              sx={{ alignSelf: "flex-start" }}
            >
              Order more
            </Button>
            {onOrderCount > 0 && (
              <Typography variant="caption" color="text.secondary">
                On order: {onOrderCount} package{onOrderCount === 1 ? "" : "s"}
                {nextArrival ? `, expected ${nextArrival}` : ""}
              </Typography>
            )}
          </Stack>
        </Box>

        <Box sx={{ mb: 1.5 }}>
          <Typography variant="h5" sx={{ mb: 0.75 }}>
            Hazards
          </Typography>
          {(() => {
            const signal = worstSignalWord(ghsCodes);
            if (ghsCodes.length === 0 && hazardTags.length === 0) {
              return (
                <Stack spacing={0.75}>
                  <Typography variant="caption" color="text.disabled">
                    No hazard data
                  </Typography>
                  <RoleGate
                    allow={["admin", "superuser", "creator"]}
                    creatorId={chemical.created_by}
                  >
                    <Button
                      size="small"
                      variant="text"
                      onClick={() =>
                        drawer.open({ kind: "chemical-edit", chemicalId: chemical.id, groupId })
                      }
                      sx={{ alignSelf: "flex-start", px: 0 }}
                    >
                      Add hazard data
                    </Button>
                  </RoleGate>
                </Stack>
              );
            }
            return (
              <Stack spacing={0.75}>
                {signal && (
                  <Chip
                    label={signal}
                    size="small"
                    color={signal === "Danger" ? "error" : "warning"}
                    sx={{ alignSelf: "flex-start", fontWeight: 600 }}
                  />
                )}
                {ghsCodes.length > 0 && (
                  <GHSPictogramRow codes={ghsCodes} size={40} />
                )}
                {hazardTags.length > 0 && <HazardTagChips tags={hazardTags} />}
              </Stack>
            );
          })()}
        </Box>

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
        {chemical.zvg && (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", mb: 0.5 }}>
            <LinkIcon sx={{ fontSize: 12, color: "primary.main" }} />
            <MuiLink
              href={gestisUrl(chemical.zvg)}
              target="_blank"
              rel="noopener"
              sx={{ fontSize: 11 }}
            >
              GESTIS {chemical.zvg}
            </MuiLink>
          </Stack>
        )}
        {isAdmin && !chemical.sds_path && chemical.cas && group?.show_sds_research_links && (
          <>
            <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", mb: 0.5 }}>
              <SearchIcon sx={{ fontSize: 12, color: "primary.main" }} />
              <MuiLink
                href={casSearchUrl(chemical.cas)}
                target="_blank"
                rel="noopener"
                sx={{ fontSize: 11 }}
              >
                CAS-Recherche (Google)
              </MuiLink>
            </Stack>
            <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", mb: 0.5 }}>
              <SearchIcon sx={{ fontSize: 12, color: "primary.main" }} />
              <MuiLink
                href={sdsPdfSearchUrl(chemical.cas)}
                target="_blank"
                rel="noopener"
                sx={{ fontSize: 11 }}
              >
                SDS-PDF-Suche (Google)
              </MuiLink>
            </Stack>
          </>
        )}
        {chemical.sds_path ? (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", flexWrap: "wrap" }}>
            <DescriptionIcon sx={{ fontSize: 12, color: "primary.main" }} />
            <MuiLink
              href={`/api/v1/groups/${groupId}/chemicals/${chemical.id}/sds`}
              target="_blank"
              rel="noopener"
              sx={{ fontSize: 11 }}
            >
              Safety data sheet
            </MuiLink>
            {isAdmin && (
              <MuiLink
                component="button"
                type="button"
                disabled={uploadSds.isPending}
                onClick={() => sdsInputRef.current?.click()}
                sx={{ fontSize: 11, display: "inline-flex", alignItems: "center", gap: 0.25 }}
              >
                <UploadFileIcon sx={{ fontSize: 12 }} />
                {uploadSds.isPending ? "Uploading…" : "Replace"}
              </MuiLink>
            )}
          </Stack>
        ) : isAdmin ? (
          <Stack direction="row" spacing={0.5} sx={{ alignItems: "center", flexWrap: "wrap" }}>
            <Typography variant="caption" color="text.disabled">
              No SDS uploaded
            </Typography>
            <MuiLink
              component="button"
              type="button"
              disabled={uploadSds.isPending}
              onClick={() => sdsInputRef.current?.click()}
              sx={{ fontSize: 11, display: "inline-flex", alignItems: "center", gap: 0.25 }}
            >
              <UploadFileIcon sx={{ fontSize: 12 }} />
              {uploadSds.isPending ? "Uploading…" : "Upload SDS"}
            </MuiLink>
          </Stack>
        ) : null}
        {isAdmin && (
          <input
            ref={sdsInputRef}
            type="file"
            accept="application/pdf"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onSdsSelected(f);
              e.target.value = "";
            }}
          />
        )}
        {sdsError && (
          <Alert severity="warning" sx={{ mt: 0.5, py: 0 }} onClose={() => setSdsError(null)}>
            {sdsError}
          </Alert>
        )}
        {ghsCodes.length > 0 || pStatements.length > 0 ? (
          <Stack
            direction="row"
            spacing={0.5}
            sx={{ alignItems: "center", mt: 0.5 }}
          >
            <WarningAmberIcon sx={{ fontSize: 12, color: "warning.main" }} />
            <MuiLink
              component="button"
              type="button"
              onClick={() => setHpOpen(true)}
              sx={{ fontSize: 11 }}
            >
              H + P statements ({ghsCodes.length}·H {pStatements.length}·P)
            </MuiLink>
          </Stack>
        ) : (
          <Typography
            variant="caption"
            color="text.disabled"
            sx={{ display: "block", mt: 0.5 }}
          >
            No H/P statements
          </Typography>
        )}
      </Box>
      <HazardStatementsDialog
        open={hpOpen}
        onClose={() => setHpOpen(false)}
        chemicalName={chemical.name}
        ghsCodes={ghsCodes}
        pStatements={pStatements}
      />
      {structureSvg && (
        <StructureDialog
          open={structureOpen}
          onClose={() => setStructureOpen(false)}
          chemicalName={chemical.name}
          svg={structureSvg}
        />
      )}
    </Box>
  );
}
