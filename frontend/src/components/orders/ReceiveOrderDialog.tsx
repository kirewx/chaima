import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useReceiveOrder } from "../../api/hooks/useOrders";
import { useStorageTree } from "../../api/hooks/useStorageLocations";
import LocationPicker from "../LocationPicker";
import type { OrderRead } from "../../types";

interface Props {
  open: boolean;
  order: OrderRead;
  onDone: () => void;
}

interface Row {
  identifier: string;
  storage_location_id: string | null;
  storage_location_path: string;
  purity_override: string;
}

export function ReceiveOrderDialog({ open, order, onDone }: Props) {
  const receive = useReceiveOrder(order.group_id, order.id);
  const { data: locationTree = [] } = useStorageTree(order.group_id);
  const [pickingRowIndex, setPickingRowIndex] = useState<number | null>(null);
  const [rows, setRows] = useState<Row[]>(
    Array.from({ length: order.package_count }, () => ({
      identifier: "",
      storage_location_id: null,
      storage_location_path: "",
      purity_override: "",
    })),
  );

  const updateRow = (i: number, patch: Partial<Row>) => {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  };

  const submit = async () => {
    await receive.mutateAsync({
      containers: rows.map((r) => ({
        identifier: r.identifier,
        storage_location_id: r.storage_location_id!,
        purity_override: r.purity_override || null,
      })),
    });
    onDone();
  };

  const allFilled = rows.every(
    (r) => r.identifier.trim() && r.storage_location_id,
  );

  return (
    <Dialog open={open} onClose={onDone} fullWidth maxWidth="sm">
      <DialogTitle>Receive order ({order.package_count} containers)</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {rows.map((row, i) => (
            <Stack
              key={i}
              spacing={1}
              sx={{ borderBottom: "1px solid", borderColor: "divider", pb: 2 }}
            >
              <TextField
                label={`Container ${i + 1} identifier`}
                value={row.identifier}
                onChange={(e) => updateRow(i, { identifier: e.target.value })}
                size="small"
              />
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setPickingRowIndex(i)}
                >
                  Choose location
                </Button>
                <Typography variant="body2" color="text.secondary">
                  {row.storage_location_path || "Pick a location"}
                </Typography>
              </Box>
              <TextField
                label="Purity override (optional)"
                value={row.purity_override}
                onChange={(e) =>
                  updateRow(i, { purity_override: e.target.value })
                }
                size="small"
                placeholder={order.purity ?? ""}
              />
            </Stack>
          ))}
          {receive.error instanceof Error && (
            <Alert severity="error">
              {(receive.error as any).response?.data?.detail ??
                receive.error.message}
            </Alert>
          )}
        </Stack>
        <LocationPicker
          open={pickingRowIndex !== null}
          onClose={() => setPickingRowIndex(null)}
          onSelect={(id, path) => {
            if (pickingRowIndex !== null) {
              updateRow(pickingRowIndex, {
                storage_location_id: id,
                storage_location_path: path,
              });
            }
            setPickingRowIndex(null);
          }}
          tree={locationTree}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onDone}>Cancel</Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={!allFilled || receive.isPending}
        >
          Mark received
        </Button>
      </DialogActions>
    </Dialog>
  );
}
