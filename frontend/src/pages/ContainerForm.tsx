import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Box,
  TextField,
  Button,
  Typography,
  Alert,
  Autocomplete,
  createFilterOptions,
} from "@mui/material";
import { useGroup } from "../components/GroupContext";
import { useCreateContainer } from "../api/hooks/useContainers";
import { useStorageTree } from "../api/hooks/useStorageLocations";
import { useSuppliers, useCreateSupplier } from "../api/hooks/useSuppliers";
import LocationPicker from "../components/LocationPicker";
import type { ContainerCreate, SupplierRead } from "../types";

interface SupplierOption {
  id?: string;
  name: string;
  isNew?: boolean;
}

const supplierFilter = createFilterOptions<SupplierOption>();

export default function ContainerForm() {
  const { groupId } = useGroup();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const chemicalId = searchParams.get("chemicalId") ?? "";

  const createMutation = useCreateContainer(groupId, chemicalId);
  const storageTree = useStorageTree(groupId);
  const suppliersQuery = useSuppliers(groupId);
  const createSupplier = useCreateSupplier(groupId);

  const [locationId, setLocationId] = useState("");
  const [locationPath, setLocationPath] = useState("");
  const [supplierOption, setSupplierOption] = useState<SupplierOption | null>(null);
  const [identifier, setIdentifier] = useState("");
  const [amount, setAmount] = useState("");
  const [unit, setUnit] = useState("mL");
  const [purchasedAt, setPurchasedAt] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);

  const suppliers: SupplierOption[] = (suppliersQuery.data?.items ?? []).map((s: SupplierRead) => ({
    id: s.id,
    name: s.name,
  }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    let supplierId: string | undefined;
    if (supplierOption) {
      if (supplierOption.isNew) {
        const created = await createSupplier.mutateAsync({ name: supplierOption.name });
        supplierId = created.id;
      } else {
        supplierId = supplierOption.id;
      }
    }

    const data: ContainerCreate = {
      location_id: locationId,
      supplier_id: supplierId || undefined,
      identifier,
      amount: parseFloat(amount),
      unit,
      purchased_at: purchasedAt || undefined,
    };
    createMutation.mutate(data, {
      onSuccess: () => navigate("/"),
    });
  };

  return (
    <Box sx={{ p: 2, maxWidth: 600 }}>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
        Add Container
      </Typography>

      {createMutation.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to create container. Identifier may already exist.
        </Alert>
      )}

      <Box component="form" onSubmit={handleSubmit}>
        <TextField
          label="Identifier"
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
          fullWidth
          required
          autoFocus
          sx={{ mb: 2 }}
        />

        <Button
          variant="outlined"
          fullWidth
          onClick={() => setPickerOpen(true)}
          sx={{ mb: 2, justifyContent: "flex-start", textTransform: "none" }}
        >
          {locationPath || "Select storage location *"}
        </Button>

        <Autocomplete
          value={supplierOption}
          onChange={(_, newValue) => {
            if (typeof newValue === "string") {
              setSupplierOption({ name: newValue, isNew: true });
            } else {
              setSupplierOption(newValue);
            }
          }}
          filterOptions={(options, params) => {
            const filtered = supplierFilter(options, params);
            if (params.inputValue !== "" && !filtered.some((o) => o.name === params.inputValue)) {
              filtered.push({ name: params.inputValue, isNew: true });
            }
            return filtered;
          }}
          options={suppliers}
          getOptionLabel={(option) => {
            if (typeof option === "string") return option;
            return option.isNew ? `Create "${option.name}"` : option.name;
          }}
          isOptionEqualToValue={(option, value) => option.id === value.id && option.name === value.name}
          freeSolo
          selectOnFocus
          clearOnBlur
          handleHomeEndKeys
          renderInput={(params) => <TextField {...params} label="Supplier" />}
          sx={{ mb: 2 }}
        />

        <Box sx={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 2, mb: 2 }}>
          <TextField
            label="Amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            type="number"
            required
          />
          <TextField
            label="Unit"
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            required
          />
        </Box>

        <TextField
          label="Purchase Date"
          type="date"
          value={purchasedAt}
          onChange={(e) => setPurchasedAt(e.target.value)}
          fullWidth
          sx={{ mb: 3 }}
          slotProps={{ inputLabel: { shrink: true } }}
        />

        <Button
          type="submit"
          variant="contained"
          fullWidth
          size="large"
          disabled={createMutation.isPending || !identifier || !locationId || !amount}
        >
          {createMutation.isPending ? "Creating..." : "Create Container"}
        </Button>
      </Box>

      <LocationPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(id, path) => {
          setLocationId(id);
          setLocationPath(path);
        }}
        tree={storageTree.data ?? []}
      />
    </Box>
  );
}
