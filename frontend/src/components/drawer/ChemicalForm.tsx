import {
  Button,
  Stack,
  TextField,
  FormControlLabel,
  Switch,
  Alert,
  Typography,
  CircularProgress,
  Box,
  IconButton,
  InputAdornment,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useState, useEffect, type KeyboardEvent } from "react";
import { AxiosError } from "axios";
import {
  useCreateChemical,
  useUpdateChemical,
  useChemicalDetail,
} from "../../api/hooks/useChemicals";
import { useCurrentUser } from "../../api/hooks/useAuth";
import { usePubChemLookup } from "../../api/hooks/usePubChem";
import type { StructureSource } from "../../types";

interface Props {
  chemicalId?: string;
  onDone: () => void;
}

interface FetchedExtras {
  cid: string | null;
  smiles: string | null;
  synonyms: string[];
  ghs_codes: string[];
  structure_source: StructureSource;
}

const EMPTY_EXTRAS: FetchedExtras = {
  cid: null,
  smiles: null,
  synonyms: [],
  ghs_codes: [],
  structure_source: "none",
};

export function ChemicalForm({ chemicalId, onDone }: Props) {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";
  const existing = useChemicalDetail(groupId, chemicalId ?? "");
  const create = useCreateChemical(groupId);
  const update = useUpdateChemical(groupId, chemicalId ?? "");
  const lookup = usePubChemLookup();

  const [name, setName] = useState("");
  const [cas, setCas] = useState("");
  const [molarMass, setMolarMass] = useState<string>("");
  const [comment, setComment] = useState("");
  const [isSecret, setIsSecret] = useState(false);

  const [query, setQuery] = useState("");
  const [extras, setExtras] = useState<FetchedExtras>(EMPTY_EXTRAS);
  const [lookupError, setLookupError] = useState<string | null>(null);

  useEffect(() => {
    if (existing.data) {
      const e = existing.data;
      setName(e.name);
      setCas(e.cas ?? "");
      setMolarMass(e.molar_mass != null ? String(e.molar_mass) : "");
      setComment(e.comment ?? "");
      setIsSecret(e.is_secret);
      setExtras({
        cid: e.cid ?? null,
        smiles: e.smiles ?? null,
        synonyms: (e.synonyms ?? []).map((s) => s.name),
        ghs_codes: (e.ghs_codes ?? []).map((g) => g.code),
        structure_source: e.structure_source,
      });
    }
  }, [existing.data?.id]);

  if (chemicalId && existing.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  const saving = create.isPending || update.isPending;
  const err = create.error || update.error;

  const onFetch = async () => {
    const q = query.trim();
    if (!q) return;
    setLookupError(null);
    try {
      const result = await lookup.mutateAsync(q);
      setName(result.name);
      setCas(result.cas ?? "");
      setMolarMass(
        result.molar_mass != null ? String(result.molar_mass) : "",
      );
      setExtras({
        cid: result.cid,
        smiles: result.smiles,
        synonyms: result.synonyms,
        ghs_codes: result.ghs_codes.map((g) => g.code),
        structure_source: "pubchem",
      });
    } catch (e) {
      setExtras(EMPTY_EXTRAS);
      const status = (e as AxiosError).response?.status ?? 0;
      if (status === 404) {
        setLookupError("No PubChem match");
      } else {
        setLookupError("PubChem unavailable");
      }
    }
  };

  const onQueryKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void onFetch();
    }
  };

  const onClearLookup = () => {
    setQuery("");
    setExtras(EMPTY_EXTRAS);
    setLookupError(null);
  };

  const onSubmit = async () => {
    const parsedMolarMass = molarMass.trim() === "" ? null : Number(molarMass);
    const payload = {
      name: name.trim(),
      cas: cas.trim() || null,
      comment: comment.trim() || null,
      is_secret: isSecret,
      molar_mass: Number.isFinite(parsedMolarMass as number)
        ? (parsedMolarMass as number)
        : null,
      cid: extras.cid,
      smiles: extras.smiles,
      structure_source: extras.structure_source,
      synonyms: extras.synonyms,
      ghs_codes: extras.ghs_codes,
    };
    if (chemicalId) {
      await update.mutateAsync(payload);
    } else {
      await create.mutateAsync(payload);
    }
    onDone();
  };

  const fetched = extras.cid !== null;

  return (
    <Stack spacing={2}>
      {err instanceof Error && <Alert severity="error">{err.message}</Alert>}
      {lookupError && <Alert severity="warning">{lookupError}</Alert>}

      <Box
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1,
          p: 1.5,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <TextField
            label="Lookup from PubChem"
            placeholder="Name or CAS"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onQueryKey}
            size="small"
            fullWidth
            InputProps={{
              endAdornment: fetched ? (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={onClearLookup}
                    aria-label="Clear PubChem lookup"
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ) : null,
            }}
          />
          <Button
            variant="outlined"
            onClick={() => void onFetch()}
            disabled={lookup.isPending || query.trim() === ""}
          >
            {lookup.isPending ? (
              <CircularProgress size={16} />
            ) : (
              "Fetch"
            )}
          </Button>
        </Stack>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mt: 0.5, display: "block" }}
        >
          Fills name, CAS, molar mass and hazards from PubChem.
        </Typography>
        {fetched && (
          <Typography
            variant="caption"
            color="success.main"
            sx={{ mt: 0.5, display: "block" }}
          >
            ✓ Fetched from PubChem (CID {extras.cid})
          </Typography>
        )}
      </Box>

      <TextField
        label="Name"
        required
        value={name}
        onChange={(e) => setName(e.target.value)}
        size="small"
      />
      <TextField
        label="CAS number"
        value={cas}
        onChange={(e) => setCas(e.target.value)}
        size="small"
        helperText="Optional. Leave blank for internal materials."
      />
      <TextField
        label="Molar mass"
        value={molarMass}
        onChange={(e) => setMolarMass(e.target.value)}
        size="small"
        type="number"
        inputProps={{ step: "0.01", min: "0" }}
        InputProps={{
          endAdornment: <InputAdornment position="end">g/mol</InputAdornment>,
        }}
      />
      <TextField
        label="Comment"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        multiline
        minRows={2}
        size="small"
      />
      <FormControlLabel
        control={
          <Switch
            checked={isSecret}
            onChange={(_, v) => setIsSecret(v)}
          />
        }
        label={
          <Stack>
            <Typography variant="body2">Mark as secret</Typography>
            <Typography variant="caption" color="text.secondary">
              Only you and system admins will see this chemical.
            </Typography>
          </Stack>
        }
        sx={{ alignItems: "flex-start", m: 0 }}
      />

      <Stack
        direction="row"
        spacing={1}
        sx={{ justifyContent: "flex-end", mt: 2 }}
      >
        <Button onClick={onDone} disabled={saving}>
          Cancel
        </Button>
        <Button
          variant="contained"
          disabled={saving || !name.trim()}
          onClick={onSubmit}
        >
          {chemicalId ? "Save" : "Create"}
        </Button>
      </Stack>
    </Stack>
  );
}
