import { useState } from "react";
import { Box, Card, CardActionArea, Chip, Collapse, Typography } from "@mui/material";
import type { ChemicalRead, ContainerRead, HazardTagRead } from "../types";
import ContainerRow from "./ContainerRow";

interface ChemicalCardProps {
  chemical: ChemicalRead;
  containers: ContainerRead[];
  hazardTags: HazardTagRead[];
  locationPaths: Record<string, string>;
  supplierNames: Record<string, string>;
  onAddContainer?: () => void;
}

export default function ChemicalCard({ chemical, containers, hazardTags, locationPaths, supplierNames }: ChemicalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const activeContainers = containers.filter((c) => !c.is_archived);
  const hasStock = activeContainers.length > 0;

  return (
    <Card sx={{ opacity: hasStock ? 1 : 0.7, bgcolor: "background.paper" }}>
      <CardActionArea onClick={() => setExpanded(!expanded)} sx={{ p: 1.5 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 0.5 }}>
          <Box>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>{chemical.name}</Typography>
            <Typography variant="caption" color="text.secondary">
              {chemical.cas ?? "No CAS"}
              {chemical.structure && ` · ${chemical.structure}`}
            </Typography>
          </Box>
          <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {hazardTags.map((tag) => (
              <Chip key={tag.id} label={tag.name} size="small" color="error" variant="outlined" sx={{ height: 20, fontSize: 10 }} />
            ))}
          </Box>
        </Box>
        {hasStock ? (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
            {activeContainers.map((c) => (
              <ContainerRow key={c.id} container={c} locationPath={locationPaths[c.location_id]} supplierName={c.supplier_id ? supplierNames[c.supplier_id] : undefined} expanded={expanded} />
            ))}
          </Box>
        ) : (
          <Typography variant="caption" color="error.main">No containers</Typography>
        )}
      </CardActionArea>
      <Collapse in={expanded}>
        <Box sx={{ px: 1.5, pb: 1.5 }}>
          <Box sx={{ bgcolor: "#111111", borderRadius: 2, p: 1.5, mt: 1, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1 }}>
            <DetailField label="Molar mass" value={chemical.molar_mass} unit="g/mol" />
            <DetailField label="Density" value={chemical.density} unit="g/cm³" />
            <DetailField label="Melting point" value={chemical.melting_point} unit="°C" />
            <DetailField label="Boiling point" value={chemical.boiling_point} unit="°C" />
          </Box>
          {chemical.comment && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>{chemical.comment}</Typography>
          )}
        </Box>
      </Collapse>
    </Card>
  );
}

function DetailField({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="body2">{value != null ? `${value} ${unit}` : "—"}</Typography>
    </Box>
  );
}
