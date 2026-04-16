import {
  Autocomplete,
  Button,
  Stack,
  TextField,
  Alert,
  CircularProgress,
  Box,
  createFilterOptions,
} from "@mui/material";
import { useState, useEffect } from "react";
import {
  useCreateContainer,
  useUpdateContainer,
  useContainer,
} from "../../api/hooks/useContainers";
import { useSuppliers, useCreateSupplier } from "../../api/hooks/useSuppliers";
import type { SupplierRead } from "../../types";
import { useCurrentUser } from "../../api/hooks/useAuth";
import { useStorageTree } from "../../api/hooks/useStorageLocations";
import LocationPicker from "../LocationPicker";

type SupplierOption = SupplierRead | { inputValue: string; name: string; id?: undefined };

const supplierFilter = createFilterOptions<SupplierOption>();

interface Props {
  chemicalId?: string;
  containerId?: string;
  onDone: () => void;
}

export function ContainerForm({ chemicalId, containerId, onDone }: Props) {
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

  const [identifier, setIdentifier] = useState("");
  const [amount, setAmount] = useState<number | "">("");
  const [unit, setUnit] = useState("");
  const [purity, setPurity] = useState("");
  const [locationId, setLocationId] = useState<string | null>(null);
  const [locationPath, setLocationPath] = useState<string>("");
  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [receivedDate, setReceivedDate] = useState<string | null>(null);

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

  return (
    <Stack spacing={2}>
      {otherErr && <Alert severity="error">{otherErr}</Alert>}

      <TextField
        label="Identifier"
        required
        value={identifier}
        onChange={(e) => setIdentifier(e.target.value)}
        size="small"
        helperText={identifierErr ?? "Must be unique within your group (e.g. AB01)"}
        error={!!identifierErr}
        autoFocus
      />

      <Stack direction="row" spacing={1}>
        <TextField
          label="Amount"
          type="number"
          required
          value={amount}
          onChange={(e) =>
            setAmount(e.target.value === "" ? "" : Number(e.target.value))
          }
          size="small"
          sx={{ flex: 1 }}
        />
        <TextField
          label="Unit"
          required
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          size="small"
          sx={{ width: 96 }}
          placeholder="g, mL, L…"
        />
      </Stack>

      <TextField
        label="Purity"
        value={purity}
        onChange={(e) => setPurity(e.target.value)}
        size="small"
        placeholder="e.g. 99.8%"
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
        slotProps={{ inputLabel: { shrink: true } }}
        value={receivedDate ?? ""}
        onChange={(e) => setReceivedDate(e.target.value || null)}
        size="small"
      />

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
