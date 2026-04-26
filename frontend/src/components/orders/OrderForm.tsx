import { useState, useEffect } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Collapse,
  CircularProgress,
  Stack,
  TextField,
  Typography,
  createFilterOptions,
} from "@mui/material";
import { useCreateOrder } from "../../api/hooks/useOrders";
import { useSuppliers, useCreateSupplier } from "../../api/hooks/useSuppliers";
import { useProjects, useCreateProject } from "../../api/hooks/useProjects";
import { useChemicalDetail } from "../../api/hooks/useChemicals";
import type { SupplierRead, ProjectRead } from "../../types";
import { PubChemVendorPanel } from "./PubChemVendorPanel";

type SupplierOption = SupplierRead | { inputValue: string; name: string; id?: undefined };
type ProjectOption = ProjectRead | { inputValue: string; name: string; id?: undefined };

const supplierFilter = createFilterOptions<SupplierOption>();
const projectFilter = createFilterOptions<ProjectOption>();

interface Props {
  groupId: string;
  chemicalId?: string;
  wishlistItemId?: string;
  onDone: () => void;
}

export function OrderForm({ groupId, chemicalId, wishlistItemId, onDone }: Props) {
  const create = useCreateOrder(groupId);
  const { data: suppliersPage } = useSuppliers(groupId);
  const suppliers = suppliersPage?.items ?? [];
  const createSupplier = useCreateSupplier(groupId);

  const { data: projectsPage } = useProjects(groupId);
  const projects = projectsPage?.items ?? [];
  const createProject = useCreateProject(groupId);

  const chemical = useChemicalDetail(groupId, chemicalId ?? "");

  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [amount, setAmount] = useState<number | "">("");
  const [unit, setUnit] = useState("");
  const [packageCount, setPackageCount] = useState<number | "">(1);
  const [pricePerPackage, setPricePerPackage] = useState<string>("");
  const [currency, setCurrency] = useState("EUR");
  const [purity, setPurity] = useState("");
  const [vendorCatalog, setVendorCatalog] = useState("");
  const [vendorUrl, setVendorUrl] = useState("");
  const [vendorOrderNumber, setVendorOrderNumber] = useState("");
  const [expectedArrival, setExpectedArrival] = useState("");
  const [comment, setComment] = useState("");
  const [showOptional, setShowOptional] = useState(false);

  useEffect(() => {
    if (projectId === null && projects.length > 0) {
      const general = projects.find((p) => p.name === "General");
      setProjectId(general?.id ?? projects[0].id);
    }
  }, [projects, projectId]);

  const submit = async () => {
    if (!chemicalId || !supplierId || !projectId) return;
    await create.mutateAsync({
      chemical_id: chemicalId,
      supplier_id: supplierId,
      project_id: projectId,
      amount_per_package: Number(amount),
      unit,
      package_count: Number(packageCount),
      price_per_package: pricePerPackage ? pricePerPackage : null,
      currency,
      purity: purity || null,
      vendor_catalog_number: vendorCatalog || null,
      vendor_product_url: vendorUrl || null,
      vendor_order_number: vendorOrderNumber || null,
      expected_arrival: expectedArrival || null,
      comment: comment || null,
      wishlist_item_id: wishlistItemId ?? null,
    });
    onDone();
  };

  const supplierLeadTime = suppliers.find((s) => s.id === supplierId)?.lead_time;

  if (chemicalId && chemical.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  return (
    <Stack spacing={2} sx={{ p: 2 }}>
      <Typography variant="h6">New order</Typography>
      <Box>
        <Typography variant="caption" color="text.secondary">Chemical</Typography>
        <Typography variant="body1">
          {chemical.data?.name ?? "(pick from chemicals page)"}
        </Typography>
      </Box>

      <Autocomplete
        options={suppliers as SupplierOption[]}
        getOptionLabel={(o) => ("name" in o ? o.name : "")}
        value={suppliers.find((s) => s.id === supplierId) ?? null}
        onChange={async (_, value) => {
          if (value && "inputValue" in value) {
            const created = await createSupplier.mutateAsync({ name: value.inputValue });
            setSupplierId(created.id);
          } else {
            setSupplierId(value?.id ?? null);
          }
        }}
        filterOptions={(options, params) => {
          const filtered = supplierFilter(options, params);
          if (params.inputValue && !filtered.some((o) => "name" in o && o.name === params.inputValue)) {
            filtered.push({ inputValue: params.inputValue, name: `Add "${params.inputValue}"` });
          }
          return filtered;
        }}
        renderInput={(params) => <TextField {...params} label="Supplier" />}
        freeSolo={false}
        selectOnFocus
        clearOnBlur
        handleHomeEndKeys
      />

      {chemical.data?.cid && (
        <PubChemVendorPanel
          cid={chemical.data.cid}
          onPick={(name) => {
            const match = suppliers.find(
              (s) => s.name.toLowerCase() === name.toLowerCase(),
            );
            if (match) setSupplierId(match.id);
          }}
        />
      )}

      {supplierLeadTime && (
        <Alert severity="info" variant="outlined" sx={{ py: 0 }}>
          {(suppliers.find((s) => s.id === supplierId)?.name ?? "supplier")} usually takes{" "}
          {supplierLeadTime.p25_days}–{supplierLeadTime.p75_days} days for your group{" "}
          ({supplierLeadTime.order_count} past orders).
        </Alert>
      )}

      <Stack direction="row" spacing={1}>
        <TextField
          label="Amount per package"
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value === "" ? "" : Number(e.target.value))}
          sx={{ flex: 2 }}
        />
        <TextField
          label="Unit"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          sx={{ flex: 1 }}
          placeholder="mL"
        />
        <TextField
          label="× count"
          type="number"
          value={packageCount}
          onChange={(e) => setPackageCount(e.target.value === "" ? "" : Number(e.target.value))}
          sx={{ flex: 1 }}
        />
      </Stack>

      <Stack direction="row" spacing={1}>
        <TextField
          label="Price per package"
          value={pricePerPackage}
          onChange={(e) => setPricePerPackage(e.target.value)}
          sx={{ flex: 2 }}
          inputMode="decimal"
        />
        <TextField
          label="Currency"
          value={currency}
          onChange={(e) => setCurrency(e.target.value.toUpperCase())}
          sx={{ flex: 1 }}
          slotProps={{ htmlInput: { maxLength: 3 } }}
        />
      </Stack>

      <Autocomplete
        options={projects as ProjectOption[]}
        getOptionLabel={(o) => ("name" in o ? o.name : "")}
        value={projects.find((p) => p.id === projectId) ?? null}
        onChange={async (_, value) => {
          if (value && "inputValue" in value) {
            const created = await createProject.mutateAsync({ name: value.inputValue });
            setProjectId(created.id);
          } else {
            setProjectId(value?.id ?? null);
          }
        }}
        filterOptions={(options, params) => {
          const filtered = projectFilter(options, params);
          if (params.inputValue && !filtered.some((o) => "name" in o && o.name === params.inputValue)) {
            filtered.push({ inputValue: params.inputValue, name: `Add "${params.inputValue}"` });
          }
          return filtered;
        }}
        renderInput={(params) => <TextField {...params} label="Project" />}
        selectOnFocus
        clearOnBlur
        handleHomeEndKeys
      />

      <Button onClick={() => setShowOptional((s) => !s)} size="small">
        {showOptional ? "Hide optional details" : "Show optional details"}
      </Button>
      <Collapse in={showOptional}>
        <Stack spacing={1}>
          <TextField label="Vendor catalog #" value={vendorCatalog} onChange={(e) => setVendorCatalog(e.target.value)} />
          <TextField label="Vendor product URL" value={vendorUrl} onChange={(e) => setVendorUrl(e.target.value)} />
          <TextField label="Vendor order #" value={vendorOrderNumber} onChange={(e) => setVendorOrderNumber(e.target.value)} />
          <TextField label="Purity" value={purity} onChange={(e) => setPurity(e.target.value)} />
          <TextField
            label="Expected arrival"
            type="date"
            slotProps={{ inputLabel: { shrink: true } }}
            value={expectedArrival}
            onChange={(e) => setExpectedArrival(e.target.value)}
          />
          <TextField label="Comment" multiline rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
        </Stack>
      </Collapse>

      {create.error instanceof Error && (
        <Alert severity="error">
          {(create.error as any).response?.data?.detail ?? create.error.message}
        </Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ justifyContent: "flex-end" }}>
        <Button onClick={onDone}>Cancel</Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={!chemicalId || !supplierId || !projectId || amount === "" || !unit}
        >
          Place order
        </Button>
      </Stack>
    </Stack>
  );
}
