import { Box, Typography, Chip, CircularProgress, Button, IconButton } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import type { ChemicalRead, ContainerRead } from "../types";
import { useChemicalDetail } from "../api/hooks/useChemicals";

interface ChemicalDetailProps {
  groupId: string;
  chemical: ChemicalRead;
  containers: ContainerRead[];
  locationPaths: Record<string, string>;
  onClose?: () => void;
  onAddContainer?: () => void;
}

const mono = "'JetBrains Mono', ui-monospace, monospace";

export default function ChemicalDetail({
  groupId,
  chemical,
  containers,
  locationPaths,
  onClose,
  onAddContainer,
}: ChemicalDetailProps) {
  const detailQuery = useChemicalDetail(groupId, chemical.id);
  const detail = detailQuery.data;
  const active = containers.filter((c) => !c.is_archived);

  return (
    <Box sx={{ p: 3, position: "relative" }}>
      {onClose && (
        <IconButton
          onClick={onClose}
          size="small"
          sx={{
            position: "absolute",
            top: 12,
            right: 12,
            color: "text.secondary",
            display: { md: "none" },
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      )}

      <Typography variant="h2" sx={{ mb: 2, pr: 4 }}>
        {chemical.name}
      </Typography>

      <StructurePlaceholder imagePath={chemical.image_path} />

      {detailQuery.isLoading && (
        <Box sx={{ py: 2, display: "flex", justifyContent: "center" }}>
          <CircularProgress size={16} thickness={4} />
        </Box>
      )}

      {detail?.synonyms && detail.synonyms.length > 0 && (
        <Field label="Synonyms">
          <Typography sx={{ fontSize: 13, color: "text.primary", lineHeight: 1.5 }}>
            {detail.synonyms.map((s) => s.name).join(", ")}
          </Typography>
        </Field>
      )}

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "14px 20px",
          pb: 2,
          mb: 2,
          borderBottom: "1px solid",
          borderColor: "divider",
        }}
      >
        <Field label="CAS" inline>
          <MonoValue>{chemical.cas ?? "—"}</MonoValue>
        </Field>
        <Field label="PubChem CID" inline>
          <MonoValue>{chemical.cid ?? "—"}</MonoValue>
        </Field>
        <Field label="Molar mass" inline>
          <MonoValue>{chemical.molar_mass != null ? `${chemical.molar_mass} g/mol` : "—"}</MonoValue>
        </Field>
        <Field label="Density" inline>
          <MonoValue>{chemical.density != null ? `${chemical.density} g/cm³` : "—"}</MonoValue>
        </Field>
      </Box>

      {detail?.hazard_tags && detail.hazard_tags.length > 0 && (
        <Field label="Hazard tags">
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
            {detail.hazard_tags.map((t) => (
              <Chip
                key={t.id}
                label={t.name}
                size="small"
                sx={{
                  height: 22,
                  bgcolor: "text.primary",
                  color: "background.default",
                  fontSize: 10,
                }}
              />
            ))}
          </Box>
        </Field>
      )}

      {detail?.ghs_codes && detail.ghs_codes.length > 0 && (
        <Field label="GHS classification">
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
            {detail.ghs_codes.map((g) => (
              <Box key={g.id} sx={{ textAlign: "center", width: 60 }} title={g.description}>
                {g.pictogram ? (
                  <Box
                    component="img"
                    src={g.pictogram}
                    alt={g.code}
                    sx={{ width: 44, height: 44, display: "block", mx: "auto" }}
                  />
                ) : (
                  <Box
                    sx={{
                      width: 44,
                      height: 44,
                      border: "1.5px solid",
                      borderColor: "text.primary",
                      transform: "rotate(45deg)",
                      mx: "auto",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      bgcolor: "background.default",
                    }}
                  >
                    <Typography sx={{ transform: "rotate(-45deg)", fontSize: 18, fontWeight: 600 }}>
                      !
                    </Typography>
                  </Box>
                )}
                <Typography sx={{ fontFamily: mono, fontSize: 9, color: "text.secondary", mt: 0.5 }}>
                  {g.code}
                </Typography>
              </Box>
            ))}
          </Box>
        </Field>
      )}

      {active.length > 0 && (
        <Field label={`Containers · ${active.length}`}>
          <Box sx={{ display: "flex", flexDirection: "column" }}>
            {active.map((c) => (
              <Box
                key={c.id}
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  py: 0.75,
                  borderBottom: "1px solid",
                  borderColor: "divider",
                  fontFamily: mono,
                  fontSize: 11,
                  "&:last-child": { borderBottom: "none" },
                }}
              >
                <Typography sx={{ fontFamily: mono, fontSize: 11, color: "text.secondary" }}>
                  {c.identifier} · {locationPaths[c.location_id] ?? "—"}
                </Typography>
                <Typography sx={{ fontFamily: mono, fontSize: 11, color: "text.primary" }}>
                  {c.amount} {c.unit}
                </Typography>
              </Box>
            ))}
          </Box>
        </Field>
      )}

      <Button
        fullWidth
        variant="contained"
        startIcon={<AddIcon />}
        onClick={onAddContainer}
        sx={{ mt: 2, py: 1.25 }}
      >
        Add container
      </Button>
    </Box>
  );
}

function Field({
  label,
  children,
  inline,
}: {
  label: string;
  children: React.ReactNode;
  inline?: boolean;
}) {
  return (
    <Box sx={{ mb: inline ? 0 : 2 }}>
      <Typography
        sx={{
          fontFamily: mono,
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          color: "text.secondary",
          mb: 0.5,
        }}
      >
        {label}
      </Typography>
      {children}
    </Box>
  );
}

function MonoValue({ children }: { children: React.ReactNode }) {
  return (
    <Typography sx={{ fontFamily: mono, fontSize: 13, color: "text.primary" }}>
      {children}
    </Typography>
  );
}

function StructurePlaceholder({ imagePath }: { imagePath: string | null }) {
  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "background.default",
        borderRadius: 0.5,
        p: 2,
        mb: 2.5,
        minHeight: 140,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
      }}
    >
      <Typography
        sx={{
          position: "absolute",
          top: 8,
          left: 10,
          fontFamily: mono,
          fontSize: 9,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          color: "text.secondary",
        }}
      >
        Structure
      </Typography>
      {imagePath ? (
        <Box component="img" src={imagePath} alt="structure" sx={{ maxWidth: "100%", maxHeight: 180 }} />
      ) : (
        <Typography sx={{ fontSize: 12, color: "text.secondary", fontStyle: "italic" }}>
          No structure available
        </Typography>
      )}
    </Box>
  );
}
