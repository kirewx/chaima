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
import { useState, useEffect, useRef, type KeyboardEvent } from "react";
import { AxiosError } from "axios";
import {
  useCreateChemical,
  useUpdateChemical,
  useChemicalDetail,
  checkChemicalExists,
  type ChemicalExistsResult,
} from "../../api/hooks/useChemicals";
import { useCurrentUser } from "../../api/hooks/useAuth";
import { usePubChemLookup, fetchPubChemGHS } from "../../api/hooks/usePubChem";
import { useDrawer } from "./DrawerContext";
import client from "../../api/client";
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
  const drawer = useDrawer();
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
  const [duplicate, setDuplicate] = useState<ChemicalExistsResult | null>(null);
  const [unarchiving, setUnarchiving] = useState(false);
  const [ghsLoading, setGhsLoading] = useState(false);
  const ghsPromiseRef = useRef<Promise<string[]> | null>(null);

  useEffect(() => {
    if (existing.data) {
      const e = existing.data;
      setName(e.name ?? "");
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

  // Extract duplicate-chemical info from a 409 response
  const conflictDetail =
    err instanceof AxiosError && err.response?.status === 409
      ? (err.response.data?.detail as {
          message?: string;
          existing_chemical_id?: string;
          is_archived?: boolean;
        })
      : null;

  const onFetch = async () => {
    const q = query.trim();
    if (!q) return;
    setLookupError(null);
    setDuplicate(null);

    // Run check-exists and PubChem lookup in parallel
    const checkPromise = groupId
      ? checkChemicalExists(groupId, { name: q, cas: q }).catch(() => null)
      : Promise.resolve(null);

    let result;
    try {
      const [existsResult, pubchemResult] = await Promise.all([
        checkPromise,
        lookup.mutateAsync(q),
      ]);

      // If query already matches an existing chemical, show duplicate alert
      if (existsResult?.exists) {
        setDuplicate(existsResult);
        return;
      }

      result = pubchemResult;
    } catch (e) {
      setExtras(EMPTY_EXTRAS);
      const status = (e as AxiosError).response?.status ?? 0;
      if (status === 404) {
        setLookupError("No PubChem match");
      } else {
        setLookupError("PubChem unavailable");
      }
      return;
    }

    // Populate form immediately with the fast data
    setName(result.name ?? "");
    setCas(result.cas ?? "");
    setMolarMass(
      result.molar_mass != null ? String(result.molar_mass) : "",
    );
    setExtras({
      cid: result.cid,
      smiles: result.smiles,
      synonyms: result.synonyms,
      ghs_codes: [],
      structure_source: "pubchem",
    });

    // Check resolved name/CAS for duplicates (non-blocking)
    if (groupId) {
      checkChemicalExists(groupId, {
        name: result.name,
        cas: result.cas ?? undefined,
      })
        .then((exists) => { if (exists.exists) setDuplicate(exists); })
        .catch(() => {});
    }

    // Fetch GHS codes lazily in the background
    if (result.cid) {
      setGhsLoading(true);
      const ghsP = fetchPubChemGHS(result.cid)
        .then((codes) => {
          const ghsCodes = codes.map((g) => g.code);
          setExtras((prev) => ({ ...prev, ghs_codes: ghsCodes }));
          return ghsCodes;
        })
        .catch(() => [] as string[])
        .finally(() => setGhsLoading(false));
      ghsPromiseRef.current = ghsP;
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

    // Include GHS codes only if already resolved; otherwise patch later
    const ghsReady = !ghsLoading;
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
      ghs_codes: ghsReady ? extras.ghs_codes : [],
    };

    if (chemicalId) {
      await update.mutateAsync(payload);
    } else {
      const created = await create.mutateAsync(payload);

      // If GHS is still loading, patch it onto the chemical once it arrives
      if (!ghsReady && ghsPromiseRef.current) {
        const createdId = created.id;
        ghsPromiseRef.current.then((codes) => {
          if (codes.length > 0) {
            client
              .patch(`/groups/${groupId}/chemicals/${createdId}`, { ghs_codes: codes })
              .catch(() => {});
          }
        });
      }
    }
    onDone();
  };

  const fetched = extras.cid !== null;

  return (
    <Stack spacing={2}>
      {(duplicate?.exists || conflictDetail?.existing_chemical_id) && (() => {
        const chemId = duplicate?.chemical_id ?? conflictDetail?.existing_chemical_id;
        const chemName = duplicate?.chemical_name;
        const archived = duplicate?.is_archived ?? conflictDetail?.is_archived;

        const handleUnarchiveAndAdd = async () => {
          if (!chemId) return;
          setUnarchiving(true);
          try {
            await client.post(`/groups/${groupId}/chemicals/${chemId}/unarchive`);
            drawer.open({ kind: "container-new", chemicalId: chemId });
          } finally {
            setUnarchiving(false);
          }
        };

        return (
          <Alert severity="info">
            <Typography variant="body2" sx={{ mb: 1 }}>
              <strong>{chemName || "This chemical"}</strong> already exists
              {archived ? " (archived)" : ""}.
            </Typography>
            <Stack direction="row" spacing={1}>
              {archived ? (
                <Button
                  variant="outlined"
                  size="small"
                  disabled={unarchiving}
                  onClick={handleUnarchiveAndAdd}
                >
                  {unarchiving ? "Restoring..." : "Restore & add container"}
                </Button>
              ) : (
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => drawer.open({ kind: "container-new", chemicalId: chemId! })}
                >
                  Add container
                </Button>
              )}
            </Stack>
          </Alert>
        );
      })()}
      {!duplicate?.exists && err instanceof Error && !conflictDetail && (
        <Alert severity="error">{err.message}</Alert>
      )}
      {lookupError && <Alert severity="warning">{lookupError}</Alert>}

      <Box
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1,
          p: 1.5,
        }}
      >
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <TextField
            label="Lookup from PubChem"
            placeholder="Name or CAS"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onQueryKey}
            size="small"
            fullWidth
            slotProps={{
              input: {
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
              },
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
            {ghsLoading && " — loading hazard codes..."}
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
        slotProps={{
          input: {
            endAdornment: <InputAdornment position="end">g/mol</InputAdornment>,
          },
          htmlInput: { step: "0.01", min: "0" },
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
          disabled={saving || !name?.trim()}
          onClick={onSubmit}
        >
          {chemicalId ? "Save" : "Create"}
        </Button>
      </Stack>
    </Stack>
  );
}
