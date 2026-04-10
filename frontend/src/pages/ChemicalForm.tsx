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
  Autocomplete,
  Chip,
  createFilterOptions,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useGroup } from "../components/GroupContext";
import {
  useCreateChemical,
  useUpdateChemical,
  useChemicalDetail,
  useReplaceHazardTags,
} from "../api/hooks/useChemicals";
import { useHazardTags, useCreateHazardTag } from "../api/hooks/useHazardTags";
import type { ChemicalCreate, ChemicalUpdate, ChemicalRead } from "../types";

interface TagOption {
  id?: string;
  name: string;
  isNew?: boolean;
}

const tagFilter = createFilterOptions<TagOption>();

export default function ChemicalForm() {
  const { groupId } = useGroup();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;

  const detailQuery = useChemicalDetail(groupId, id ?? "");
  const createMutation = useCreateChemical(groupId);
  const updateMutation = useUpdateChemical(groupId, id ?? "");
  const replaceTagsMutation = useReplaceHazardTags(groupId, id ?? "");
  const hazardTagsQuery = useHazardTags(groupId);
  const createHazardTag = useCreateHazardTag(groupId);

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
  const [selectedTags, setSelectedTags] = useState<TagOption[]>([]);
  const [tagError, setTagError] = useState<string | null>(null);
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
    setSelectedTags(
      c.hazard_tags.map((t) => ({ id: t.id, name: t.name }))
    );
    setInitialized(true);
  }

  const mutation = isEdit ? updateMutation : createMutation;

  const allTags: TagOption[] = (hazardTagsQuery.data?.items ?? []).map((t) => ({
    id: t.id,
    name: t.name,
  }));

  const assignTags = async (chemicalId: string, tags: TagOption[]) => {
    const tagIds: string[] = [];
    for (const tag of tags) {
      if (tag.isNew) {
        const created = await createHazardTag.mutateAsync({ name: tag.name });
        tagIds.push(created.id);
      } else if (tag.id) {
        tagIds.push(tag.id);
      }
    }
    if (tagIds.length > 0 || isEdit) {
      await replaceTagsMutation.mutateAsync({ chemicalId, hazardTagIds: tagIds });
    }
  };

  const handleSubmit = async (e: FormEvent) => {
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
      updateMutation.mutate(data, {
        onSuccess: async () => {
          try {
            await assignTags(id!, selectedTags);
            navigate("/");
          } catch {
            setTagError("Chemical saved, but hazard tags could not be updated.");
          }
        },
      });
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
      createMutation.mutate(data, {
        onSuccess: async (created: ChemicalRead) => {
          try {
            if (selectedTags.length > 0) {
              await assignTags(created.id, selectedTags);
            }
            navigate("/");
          } catch {
            setTagError("Chemical created, but hazard tags could not be saved.");
          }
        },
      });
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
      {tagError && (
        <Alert severity="warning" sx={{ mb: 2 }}>{tagError}</Alert>
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

        <Autocomplete
          multiple
          value={selectedTags}
          onChange={(_, newValue) => {
            setSelectedTags(
              newValue.map((v) =>
                typeof v === "string" ? { name: v, isNew: true } : v
              )
            );
          }}
          filterOptions={(options, params) => {
            const filtered = tagFilter(options, params);
            if (params.inputValue !== "" && !filtered.some((o) => o.name === params.inputValue)) {
              filtered.push({ name: params.inputValue, isNew: true });
            }
            return filtered;
          }}
          options={allTags}
          getOptionLabel={(option) => {
            if (typeof option === "string") return option;
            return option.isNew ? `Create "${option.name}"` : option.name;
          }}
          isOptionEqualToValue={(option, value) => option.name === value.name}
          freeSolo
          selectOnFocus
          clearOnBlur
          handleHomeEndKeys
          renderTags={(value, getTagProps) =>
            value.map((option, index) => (
              <Chip
                label={option.name}
                size="small"
                color={option.isNew ? "primary" : "error"}
                variant="outlined"
                {...getTagProps({ index })}
                key={option.id ?? option.name}
              />
            ))
          }
          renderInput={(params) => <TextField {...params} label="Hazard Tags" placeholder="Add tags..." />}
          sx={{ mb: 2 }}
        />

        <Accordion sx={{ mb: 2 }} defaultExpanded={isEdit}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>Additional details</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TextField
              label="CAS Number"
              value={cas}
              onChange={(e) => setCas(e.target.value)}
              fullWidth
              sx={{ mb: 2 }}
            />
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
