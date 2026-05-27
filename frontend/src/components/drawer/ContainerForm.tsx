import {
  Autocomplete,
  Button,
  Stack,
  TextField,
  Alert,
  CircularProgress,
  Box,
  InputAdornment,
  Typography,
  createFilterOptions,
} from "@mui/material";
import CameraAltIcon from "@mui/icons-material/CameraAlt";
import { useState, useEffect, useRef } from "react";
import {
  useCreateContainer,
  useUpdateContainer,
  useContainer,
} from "../../api/hooks/useContainers";
import { useSuppliers, useCreateSupplier } from "../../api/hooks/useSuppliers";
import { useExtractFromPhoto } from "../../api/hooks/useExtractFromPhoto";
import type { ContainerPrefill, SupplierRead } from "../../types";
import { useCurrentUser } from "../../api/hooks/useAuth";
import { useStorageTree } from "../../api/hooks/useStorageLocations";
import { useCompatibilityCheck } from "../../api/hooks/useCompatibility";
import LocationPicker from "../LocationPicker";

function todayIsoDate(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

type SupplierOption = SupplierRead | { inputValue: string; name: string; id?: undefined };

const supplierFilter = createFilterOptions<SupplierOption>();

interface Props {
  chemicalId?: string;
  containerId?: string;
  prefill?: ContainerPrefill;
  photoFile?: File;
  onDone: () => void;
}

export function ContainerForm({ chemicalId, containerId, prefill, photoFile: initialPhotoFile, onDone }: Props) {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";

  const existing = useContainer(groupId, containerId ?? "");
  const create = useCreateContainer(groupId, chemicalId ?? "");
  const update = useUpdateContainer(groupId, containerId ?? "");

  const { data: suppliersPage } = useSuppliers(groupId);
  const suppliers = suppliersPage?.items ?? [];
  const createSupplier = useCreateSupplier(groupId);

  const { data: locationTree = [] } = useStorageTree(groupId);
  const [locationPickerOpen, setLocationPickerOpen] = useState(false);

  const [identifier, setIdentifier] = useState(prefill?.identifier ?? "");
  const [amount, setAmount] = useState<number | "">(prefill?.amount ?? "");
  const [unit, setUnit] = useState(prefill?.unit ?? "");
  const [purity, setPurity] = useState(prefill?.purity ?? "");
  const [locationId, setLocationId] = useState<string | null>(null);
  const [locationPath, setLocationPath] = useState<string>("");
  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [receivedDate, setReceivedDate] = useState<string | null>(
    containerId ? null : (prefill?.purchased_at ?? todayIsoDate()),
  );

  const [extractedFields, setExtractedFields] = useState<Set<string>>(() => {
    const s = new Set<string>();
    if (prefill?.identifier) s.add("identifier");
    if (prefill?.amount !== undefined) s.add("amount");
    if (prefill?.unit) s.add("unit");
    if (prefill?.purity) s.add("purity");
    if (prefill?.purchased_at) s.add("purchased_at");
    if (prefill?.supplier_name) s.add("supplier");
    return s;
  });
  const [photoFile, setPhotoFile] = useState<File | null>(initialPhotoFile ?? null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(() =>
    initialPhotoFile ? URL.createObjectURL(initialPhotoFile) : null,
  );
  const [extractError, setExtractError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const extract = useExtractFromPhoto();

  useEffect(() => () => {
    if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
  }, [photoPreviewUrl]);

  useEffect(() => {
    if (existing.data) {
      setIdentifier(existing.data.identifier);
      setAmount(existing.data.amount);
      setUnit(existing.data.unit);
      setPurity(existing.data.purity ?? "");
      setLocationId(existing.data.location_id);
      setSupplierId(existing.data.supplier_id);
      setReceivedDate(existing.data.purchased_at ?? null);
    }
  }, [existing.data]);

  // If prefill carries a supplier_name, match it to an existing supplier or create one.
  useEffect(() => {
    if (!prefill?.supplier_name || supplierId) return;
    if (!suppliersPage) return;  // wait for the supplier list
    const wanted = prefill.supplier_name.trim().toLowerCase();
    const match = suppliers.find((s) => s.name.toLowerCase() === wanted);
    if (match) {
      setSupplierId(match.id);
    } else {
      createSupplier.mutateAsync({ name: prefill.supplier_name.trim() }).then((c) => setSupplierId(c.id)).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suppliersPage, prefill?.supplier_name]);

  if (containerId && existing.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  const saving = create.isPending || update.isPending;
  const rawErr = create.error || update.error;
  const errMsg =
    rawErr instanceof Error
      ? ((rawErr as any).response?.data?.detail ?? rawErr.message)
      : null;
  const identifierErr =
    typeof errMsg === "string" && errMsg.toLowerCase().includes("identifier")
      ? errMsg
      : undefined;
  const otherErr = errMsg && !identifierErr ? errMsg : undefined;

  const conflicts = useCompatibilityCheck(
    groupId,
    chemicalId ?? null,
    locationId ?? null,
  );

  const canSubmit =
    !!identifier.trim() && amount !== "" && !!unit.trim() && !!locationId;

  const onSubmit = async () => {
    const payload = {
      identifier: identifier.trim(),
      amount: Number(amount),
      unit: unit.trim(),
      purity: purity.trim() || null,
      location_id: locationId!,
      supplier_id: supplierId || null,
      purchased_at: receivedDate,
    };

    if (containerId) {
      await update.mutateAsync(payload);
    } else {
      await create.mutateAsync(payload);
    }
    onDone();
  };

  const handleFile = async (file: File) => {
    setExtractError(null);
    setPhotoFile(file);
    if (photoPreviewUrl) URL.revokeObjectURL(photoPreviewUrl);
    setPhotoPreviewUrl(URL.createObjectURL(file));

    try {
      const result = await extract.mutateAsync(file);
      const next = new Set(extractedFields);
      if (result.identifier) { setIdentifier(result.identifier); next.add("identifier"); }
      if (result.amount != null) { setAmount(result.amount); next.add("amount"); }
      if (result.unit) { setUnit(result.unit); next.add("unit"); }
      if (result.purity) { setPurity(result.purity); next.add("purity"); }
      if (result.purchased_at) { setReceivedDate(result.purchased_at); next.add("purchased_at"); }
      if (result.supplier_name) {
        const wanted = result.supplier_name.trim().toLowerCase();
        const match = suppliers.find((s) => s.name.toLowerCase() === wanted);
        if (match) { setSupplierId(match.id); next.add("supplier"); }
        else {
          try {
            const created = await createSupplier.mutateAsync({ name: result.supplier_name.trim() });
            setSupplierId(created.id);
            next.add("supplier");
          } catch { /* ignore */ }
        }
      }
      setExtractedFields(next);
    } catch (e) {
      const axiosErr = e as { response?: { status?: number } };
      const status = axiosErr.response?.status;
      if (status === 503) setExtractError("Foto-Erkennung ist auf dieser Instanz deaktiviert.");
      else if (status === 502) setExtractError("Erkennung gerade nicht möglich — bitte manuell eingeben.");
      else if (status === 413) setExtractError("Bild zu groß (max. 10 MB).");
      else if (status === 415) setExtractError("Bildformat nicht unterstützt.");
      else setExtractError("Erkennung fehlgeschlagen — bitte manuell eingeben.");
    }
  };

  return (
    <Stack spacing={2}>
      {!containerId && (
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1.5,
            p: 1,
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
          }}
        >
          {photoPreviewUrl ? (
            <Box
              component="img"
              src={photoPreviewUrl}
              sx={{ width: 48, height: 48, objectFit: "cover", borderRadius: 1 }}
            />
          ) : (
            <Box
              sx={{
                width: 48, height: 48, display: "flex",
                alignItems: "center", justifyContent: "center",
                color: "text.secondary", border: "1px dashed",
                borderColor: "divider", borderRadius: 1,
              }}
            >
              <CameraAltIcon fontSize="small" />
            </Box>
          )}
          <Box sx={{ flex: 1 }}>
            <Typography variant="body2">Etikett-Foto (optional)</Typography>
            <Typography variant="caption" color="text.secondary">
              {extract.isPending
                ? "Erkennung läuft…"
                : photoFile
                ? "Foto wird beim Save am Container abgelegt"
                : "Foto aufnehmen oder hochladen"}
            </Typography>
          </Box>
          <Button
            variant="outlined"
            size="small"
            startIcon={<CameraAltIcon />}
            onClick={() => fileInputRef.current?.click()}
            disabled={extract.isPending}
          >
            {photoFile ? "Ersetzen" : "Foto"}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleFile(f);
              e.target.value = "";
            }}
          />
        </Box>
      )}

      {extractError && <Alert severity="warning" onClose={() => setExtractError(null)}>{extractError}</Alert>}

      {otherErr && <Alert severity="error">{otherErr}</Alert>}

      <TextField
        label="Identifier"
        required
        value={identifier}
        onChange={(e) => {
          setIdentifier(e.target.value);
          if (extractedFields.has("identifier")) {
            setExtractedFields((s) => { const ns = new Set(s); ns.delete("identifier"); return ns; });
          }
        }}
        size="small"
        helperText={identifierErr ?? "Must be unique within your group (e.g. AB01)"}
        error={!!identifierErr}
        autoFocus
        sx={extractedFields.has("identifier")
          ? { "& .MuiOutlinedInput-root": { backgroundColor: "rgba(67, 56, 202, 0.06)" } }
          : undefined}
        slotProps={{
          input: extractedFields.has("identifier")
            ? {
                startAdornment: (
                  <InputAdornment position="start">
                    <CameraAltIcon fontSize="small" color="primary" />
                  </InputAdornment>
                ),
              }
            : undefined,
        }}
      />

      <Stack direction="row" spacing={1}>
        <TextField
          label="Amount"
          type="number"
          required
          value={amount}
          onChange={(e) => {
            setAmount(e.target.value === "" ? "" : Number(e.target.value));
            if (extractedFields.has("amount")) {
              setExtractedFields((s) => { const ns = new Set(s); ns.delete("amount"); return ns; });
            }
          }}
          size="small"
          sx={extractedFields.has("amount")
            ? { flex: 1, "& .MuiOutlinedInput-root": { backgroundColor: "rgba(67, 56, 202, 0.06)" } }
            : { flex: 1 }}
          slotProps={{
            input: extractedFields.has("amount")
              ? {
                  startAdornment: (
                    <InputAdornment position="start">
                      <CameraAltIcon fontSize="small" color="primary" />
                    </InputAdornment>
                  ),
                }
              : undefined,
          }}
        />
        <TextField
          label="Unit"
          required
          value={unit}
          onChange={(e) => {
            setUnit(e.target.value);
            if (extractedFields.has("unit")) {
              setExtractedFields((s) => { const ns = new Set(s); ns.delete("unit"); return ns; });
            }
          }}
          size="small"
          sx={extractedFields.has("unit")
            ? { width: 96, "& .MuiOutlinedInput-root": { backgroundColor: "rgba(67, 56, 202, 0.06)" } }
            : { width: 96 }}
          placeholder="g, mL, L…"
          slotProps={{
            input: extractedFields.has("unit")
              ? {
                  startAdornment: (
                    <InputAdornment position="start">
                      <CameraAltIcon fontSize="small" color="primary" />
                    </InputAdornment>
                  ),
                }
              : undefined,
          }}
        />
      </Stack>

      <TextField
        label="Purity"
        value={purity}
        onChange={(e) => {
          setPurity(e.target.value);
          if (extractedFields.has("purity")) {
            setExtractedFields((s) => { const ns = new Set(s); ns.delete("purity"); return ns; });
          }
        }}
        size="small"
        placeholder="e.g. 99.8%"
        sx={extractedFields.has("purity")
          ? { "& .MuiOutlinedInput-root": { backgroundColor: "rgba(67, 56, 202, 0.06)" } }
          : undefined}
        slotProps={{
          input: extractedFields.has("purity")
            ? {
                startAdornment: (
                  <InputAdornment position="start">
                    <CameraAltIcon fontSize="small" color="primary" />
                  </InputAdornment>
                ),
              }
            : undefined,
        }}
      />

      <Box>
        <Button
          variant="outlined"
          size="small"
          onClick={() => setLocationPickerOpen(true)}
          sx={{ textTransform: "none", justifyContent: "flex-start", width: "100%" }}
        >
          {locationPath || locationId
            ? (locationPath || locationId)
            : "Select location *"}
        </Button>
        <LocationPicker
          open={locationPickerOpen}
          onClose={() => setLocationPickerOpen(false)}
          onSelect={(id, path) => {
            setLocationId(id);
            setLocationPath(path);
            setLocationPickerOpen(false);
          }}
          tree={locationTree}
        />
      </Box>

      <Autocomplete<SupplierOption, false, false, true>
        freeSolo
        selectOnFocus
        clearOnBlur
        handleHomeEndKeys
        size="small"
        options={suppliers}
        value={
          supplierId
            ? (suppliers.find((s) => s.id === supplierId) ?? null)
            : null
        }
        disabled={createSupplier.isPending}
        getOptionLabel={(option) => {
          if (typeof option === "string") return option;
          return option.name;
        }}
        isOptionEqualToValue={(option, value) =>
          typeof option !== "string" &&
          typeof value !== "string" &&
          option.id === (value as SupplierRead).id
        }
        filterOptions={(options, params) => {
          const filtered = supplierFilter(options, params);
          const { inputValue } = params;
          const exists = options.some(
            (o) =>
              typeof o !== "string" &&
              o.name.toLowerCase() === inputValue.toLowerCase(),
          );
          if (inputValue.trim() && !exists) {
            filtered.push({
              inputValue: inputValue.trim(),
              name: `Create "${inputValue.trim()}"`,
            });
          }
          return filtered;
        }}
        onChange={async (_e, value) => {
          if (value == null) {
            setSupplierId(null);
            return;
          }
          if (typeof value === "string") {
            const created = await createSupplier.mutateAsync({ name: value });
            setSupplierId(created.id);
            return;
          }
          if ("inputValue" in value && value.inputValue) {
            const created = await createSupplier.mutateAsync({
              name: value.inputValue,
            });
            setSupplierId(created.id);
            return;
          }
          setSupplierId((value as SupplierRead).id);
        }}
        renderInput={(params) => {
          const createErr =
            createSupplier.error instanceof Error
              ? ((createSupplier.error as any).response?.data?.detail ??
                createSupplier.error.message)
              : undefined;
          return (
            <TextField
              {...params}
              label="Supplier"
              error={!!createErr}
              helperText={
                createErr ??
                (createSupplier.isPending ? "Creating supplier…" : undefined)
              }
            />
          );
        }}
      />

      <TextField
        label="Received"
        type="date"
        slotProps={{
          inputLabel: { shrink: true },
          input: extractedFields.has("purchased_at")
            ? {
                startAdornment: (
                  <InputAdornment position="start">
                    <CameraAltIcon fontSize="small" color="primary" />
                  </InputAdornment>
                ),
              }
            : undefined,
        }}
        value={receivedDate ?? ""}
        onChange={(e) => {
          setReceivedDate(e.target.value || null);
          if (extractedFields.has("purchased_at")) {
            setExtractedFields((s) => { const ns = new Set(s); ns.delete("purchased_at"); return ns; });
          }
        }}
        size="small"
        sx={extractedFields.has("purchased_at")
          ? { "& .MuiOutlinedInput-root": { backgroundColor: "rgba(67, 56, 202, 0.06)" } }
          : undefined}
      />

      {conflicts.data && conflicts.data.length > 0 && (
        <Alert severity="warning" sx={{ mt: 1 }}>
          <strong>Storage conflict.</strong>
          <ul style={{ margin: "4px 0 0 16px", padding: 0 }}>
            {conflicts.data.map((c, i) => (
              <li key={i}>
                {c.chem_a_name} and {c.chem_b_name}: {c.reason}
              </li>
            ))}
          </ul>
        </Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end", mt: 2 }}>
        <Button onClick={onDone} disabled={saving}>
          Cancel
        </Button>
        <Button
          variant="contained"
          disabled={saving || !canSubmit}
          onClick={onSubmit}
        >
          {containerId ? "Save" : "Create"}
        </Button>
      </Stack>
    </Stack>
  );
}
