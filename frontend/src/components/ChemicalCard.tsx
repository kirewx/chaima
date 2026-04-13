import { useState, useMemo } from "react";
import { Box, Collapse, Typography, ButtonBase, CircularProgress } from "@mui/material";
import type { ChemicalRead, ContainerRead, HazardTagRead } from "../types";
import { useChemicalDetail } from "../api/hooks/useChemicals";
import { useGroup } from "./GroupContext";

interface ChemicalCardProps {
  chemical: ChemicalRead;
  containers: ContainerRead[];
  hazardTags: HazardTagRead[];
  locationPaths: Record<string, string>;
  supplierNames: Record<string, string>;
  onAddContainer?: () => void;
}

const mono = "'JetBrains Mono', ui-monospace, monospace";
const serif = "'Fraunces', Georgia, serif";

export default function ChemicalCard({ chemical, containers, locationPaths }: ChemicalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { groupId } = useGroup();
  const detailQuery = useChemicalDetail(groupId, expanded ? chemical.id : "");

  const activeContainers = containers.filter((c) => !c.is_archived);
  const hasStock = activeContainers.length > 0;

  const totals = useMemo(() => {
    const byUnit: Record<string, number> = {};
    for (const c of activeContainers) {
      byUnit[c.unit] = (byUnit[c.unit] ?? 0) + c.amount;
    }
    return Object.entries(byUnit);
  }, [activeContainers]);

  const uniqueLocations = useMemo(() => {
    const set = new Set<string>();
    for (const c of activeContainers) {
      const path = locationPaths[c.location_id];
      if (path) set.add(path);
    }
    return Array.from(set);
  }, [activeContainers, locationPaths]);

  const detail = detailQuery.data;
  const synonyms = detail?.synonyms ?? [];
  const ghsCodes = detail?.ghs_codes ?? [];

  return (
    <Box
      sx={{
        borderBottom: "1px solid",
        borderColor: "divider",
        bgcolor: "background.paper",
        opacity: hasStock ? 1 : 0.55,
        transition: "opacity 200ms ease",
      }}
    >
      <ButtonBase
        onClick={() => setExpanded(!expanded)}
        sx={{
          width: "100%",
          display: "block",
          textAlign: "left",
          px: 2.5,
          py: 2,
          "&:hover": { bgcolor: "rgba(184, 67, 28, 0.03)" },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "baseline", gap: 2, flexWrap: "wrap" }}>
          <Typography
            sx={{
              fontFamily: serif,
              fontSize: 20,
              fontWeight: 500,
              letterSpacing: "-0.015em",
              color: "text.primary",
              lineHeight: 1.2,
              flex: "0 1 auto",
            }}
          >
            {chemical.name}
          </Typography>

          {chemical.cas && (
            <Typography
              component="span"
              sx={{
                fontFamily: mono,
                fontSize: 12,
                color: "text.secondary",
                opacity: 0.55,
                letterSpacing: "0.02em",
              }}
            >
              CAS {chemical.cas}
            </Typography>
          )}

          <Box sx={{ flex: 1 }} />

          {chemical.cid && (
            <Typography
              component="span"
              sx={{
                fontFamily: mono,
                fontSize: 11,
                color: "primary.main",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                px: 1,
                py: 0.25,
                border: "1px solid",
                borderColor: "primary.main",
                borderRadius: 0.5,
              }}
            >
              CID {chemical.cid}
            </Typography>
          )}
        </Box>

        {hasStock && totals.length > 0 && (
          <Box sx={{ display: "flex", gap: 1.5, mt: 0.75, flexWrap: "wrap" }}>
            {totals.map(([unit, amount]) => (
              <Typography
                key={unit}
                sx={{
                  fontFamily: mono,
                  fontSize: 11,
                  color: "text.secondary",
                  letterSpacing: "0.02em",
                }}
              >
                {formatAmount(amount)} {unit}
              </Typography>
            ))}
            <Typography sx={{ fontFamily: mono, fontSize: 11, color: "text.secondary", opacity: 0.5 }}>
              · {activeContainers.length} container{activeContainers.length !== 1 ? "s" : ""}
            </Typography>
          </Box>
        )}
        {!hasStock && (
          <Typography sx={{ fontFamily: mono, fontSize: 11, color: "text.secondary", mt: 0.75, opacity: 0.6 }}>
            no stock
          </Typography>
        )}
      </ButtonBase>

      <Collapse in={expanded} unmountOnExit>
        <Box sx={{ px: 2.5, pb: 2.5, pt: 0.5, borderTop: "1px solid", borderColor: "divider", bgcolor: "rgba(184, 67, 28, 0.025)" }}>
          {detailQuery.isLoading && (
            <Box sx={{ py: 2, display: "flex", justifyContent: "center" }}>
              <CircularProgress size={18} thickness={4} />
            </Box>
          )}

          {detail && (
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2.5, mt: 2 }}>
              {synonyms.length > 0 && (
                <Field label="Synonyms">
                  <Typography sx={{ fontFamily: serif, fontSize: 14, fontStyle: "italic", color: "text.primary", lineHeight: 1.5 }}>
                    {synonyms.map((s) => s.name).join(", ")}
                  </Typography>
                </Field>
              )}

              {chemical.molar_mass != null && (
                <Field label="Molar mass">
                  <Typography sx={{ fontFamily: mono, fontSize: 14, color: "text.primary" }}>
                    {chemical.molar_mass} <span style={{ opacity: 0.5 }}>g/mol</span>
                  </Typography>
                </Field>
              )}

              {uniqueLocations.length > 0 && (
                <Field label={uniqueLocations.length > 1 ? "Locations" : "Location"}>
                  <Box sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}>
                    {uniqueLocations.map((loc) => (
                      <Typography
                        key={loc}
                        sx={{ fontFamily: mono, fontSize: 12, color: "text.primary", letterSpacing: "0.01em" }}
                      >
                        {loc}
                      </Typography>
                    ))}
                  </Box>
                </Field>
              )}

              {totals.length > 0 && (
                <Field label="Total stock">
                  <Box sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}>
                    {totals.map(([unit, amount]) => (
                      <Typography key={unit} sx={{ fontFamily: mono, fontSize: 14, color: "text.primary" }}>
                        {formatAmount(amount)} <span style={{ opacity: 0.5 }}>{unit}</span>
                      </Typography>
                    ))}
                  </Box>
                </Field>
              )}

              {ghsCodes.length > 0 && (
                <Box sx={{ gridColumn: "1 / -1" }}>
                  <Field label="GHS hazards">
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5, mt: 0.5 }}>
                      {ghsCodes.map((g) => (
                        <Box
                          key={g.id}
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                            px: 1,
                            py: 0.75,
                            border: "1px solid",
                            borderColor: "divider",
                            bgcolor: "background.paper",
                            borderRadius: 0.5,
                          }}
                          title={g.description}
                        >
                          {g.pictogram ? (
                            <Box
                              component="img"
                              src={g.pictogram}
                              alt={g.code}
                              sx={{ width: 32, height: 32, display: "block" }}
                            />
                          ) : (
                            <Box
                              sx={{
                                width: 32,
                                height: 32,
                                border: "1px dashed",
                                borderColor: "divider",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                            >
                              <Typography sx={{ fontFamily: mono, fontSize: 9, color: "text.secondary" }}>
                                {g.code}
                              </Typography>
                            </Box>
                          )}
                          <Box>
                            <Typography sx={{ fontFamily: mono, fontSize: 10, color: "text.secondary", lineHeight: 1 }}>
                              {g.code}
                            </Typography>
                            {g.signal_word && (
                              <Typography sx={{ fontFamily: serif, fontSize: 12, color: "text.primary", fontStyle: "italic", lineHeight: 1.2, mt: 0.25 }}>
                                {g.signal_word}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      ))}
                    </Box>
                  </Field>
                </Box>
              )}
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Box>
      <Typography
        sx={{
          fontFamily: mono,
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          color: "text.secondary",
          mb: 0.5,
          opacity: 0.7,
        }}
      >
        {label}
      </Typography>
      {children}
    </Box>
  );
}

function formatAmount(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(2).replace(/\.?0+$/, "");
  if (Number.isInteger(n)) return n.toString();
  return n.toFixed(2).replace(/\.?0+$/, "");
}
