import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Box,
  TextField,
  Button,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useGroup } from "../components/GroupContext";
import {
  useCreateChemical,
  useUpdateChemical,
  useChemicalDetail,
} from "../api/hooks/useChemicals";
import type { ChemicalCreate, ChemicalUpdate } from "../types";

export default function ChemicalForm() {
  const { groupId } = useGroup();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;

  const detailQuery = useChemicalDetail(groupId, id ?? "");
  const createMutation = useCreateChemical(groupId);
  const updateMutation = useUpdateChemical(groupId, id ?? "");

  const [name, setName] = useState("");
  const [cas, setCas] = useState("");
  const [smiles, setSmiles] = useState("");
  const [cid, setCid] = useState("");
  const [structure, setStructure] = useState("");
  const [molarMass, setMolarMass] = useState("");
  const [density, setDensity] = useState("");
  const [meltingPoint, setMeltingPoint] = useState("");
  const [boilingPoint, setBoilingPoint] = useState("");
  const [comment, setComment] = useState("");
  const [initialized, setInitialized] = useState(false);

  if (isEdit && detailQuery.data && !initialized) {
    const c = detailQuery.data;
    setName(c.name);
    setCas(c.cas ?? "");
    setSmiles(c.smiles ?? "");
    setCid(c.cid ?? "");
    setStructure(c.structure ?? "");
    setMolarMass(c.molar_mass?.toString() ?? "");
    setDensity(c.density?.toString() ?? "");
    setMeltingPoint(c.melting_point?.toString() ?? "");
    setBoilingPoint(c.boiling_point?.toString() ?? "");
    setComment(c.comment ?? "");
    setInitialized(true);
  }

  const mutation = isEdit ? updateMutation : createMutation;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const numOrNull = (v: string) => (v ? parseFloat(v) : null);

    if (isEdit) {
      const data: ChemicalUpdate = {
        name: name || null,
        cas: cas || null,
        smiles: smiles || null,
        cid: cid || null,
        structure: structure || null,
        molar_mass: numOrNull(molarMass),
        density: numOrNull(density),
        melting_point: numOrNull(meltingPoint),
        boiling_point: numOrNull(boilingPoint),
        comment: comment || null,
      };
      updateMutation.mutate(data, { onSuccess: () => navigate("/") });
    } else {
      const data: ChemicalCreate = {
        name,
        cas: cas || undefined,
        smiles: smiles || undefined,
        cid: cid || undefined,
        structure: structure || undefined,
        molar_mass: numOrNull(molarMass) ?? undefined,
        density: numOrNull(density) ?? undefined,
        melting_point: numOrNull(meltingPoint) ?? undefined,
        boiling_point: numOrNull(boilingPoint) ?? undefined,
        comment: comment || undefined,
      };
      createMutation.mutate(data, { onSuccess: () => navigate("/") });
    }
  };

  return (
    <Box sx={{ p: 2, maxWidth: 600 }}>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
        {isEdit ? "Edit Chemical" : "Add Chemical"}
      </Typography>

      {mutation.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {isEdit ? "Failed to update chemical" : "Failed to create chemical. Name may already exist."}
        </Alert>
      )}

      <Box component="form" onSubmit={handleSubmit}>
        <TextField
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          fullWidth
          required
          autoFocus
          sx={{ mb: 2 }}
        />

        <TextField
          label="CAS Number"
          value={cas}
          onChange={(e) => setCas(e.target.value)}
          fullWidth
          sx={{ mb: 2 }}
        />

        <Accordion sx={{ mb: 2 }} defaultExpanded={isEdit}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Additional details</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TextField
              label="SMILES"
              value={smiles}
              onChange={(e) => setSmiles(e.target.value)}
              fullWidth
              sx={{ mb: 2 }}
            />
            <TextField
              label="PubChem CID"
              value={cid}
              onChange={(e) => setCid(e.target.value)}
              fullWidth
              sx={{ mb: 2 }}
            />
            <TextField
              label="Molecular Formula"
              value={structure}
              onChange={(e) => setStructure(e.target.value)}
              fullWidth
              sx={{ mb: 2 }}
            />
            <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 2, mb: 2 }}>
              <TextField
                label="Molar Mass (g/mol)"
                value={molarMass}
                onChange={(e) => setMolarMass(e.target.value)}
                type="number"
              />
              <TextField
                label="Density (g/cm³)"
                value={density}
                onChange={(e) => setDensity(e.target.value)}
                type="number"
              />
              <TextField
                label="Melting Point (°C)"
                value={meltingPoint}
                onChange={(e) => setMeltingPoint(e.target.value)}
                type="number"
              />
              <TextField
                label="Boiling Point (°C)"
                value={boilingPoint}
                onChange={(e) => setBoilingPoint(e.target.value)}
                type="number"
              />
            </Box>
            <TextField
              label="Comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              fullWidth
              multiline
              rows={3}
            />
          </AccordionDetails>
        </Accordion>

        <Button
          type="submit"
          variant="contained"
          fullWidth
          size="large"
          disabled={mutation.isPending || !name}
        >
          {mutation.isPending ? "Saving..." : isEdit ? "Update" : "Create"}
        </Button>
      </Box>
    </Box>
  );
}
