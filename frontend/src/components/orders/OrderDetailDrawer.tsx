import {
  Alert,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useOrder, useCancelOrder } from "../../api/hooks/useOrders";
import { useCurrentUser } from "../../api/hooks/useAuth";
import { useGroupMembers } from "../../api/hooks/useGroups";
import { useDrawer } from "../drawer/DrawerContext";
import { ReceiveOrderDialog } from "./ReceiveOrderDialog";

interface Props {
  groupId: string;
  orderId: string;
  onDone: () => void;
}

export function OrderDetailDrawer({ groupId, orderId, onDone }: Props) {
  const { data: order, isLoading } = useOrder(groupId, orderId);
  const cancel = useCancelOrder(groupId, orderId);
  const { data: user } = useCurrentUser();
  const { data: members = [] } = useGroupMembers(groupId);
  const { open: openDrawer } = useDrawer();
  const [showReceive, setShowReceive] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState("");

  const isCreator = !!user && !!order && user.id === order.ordered_by_user_id;
  const isGroupAdmin = !!user && members.some((m) => m.user_id === user.id && m.is_admin);
  const canCancel = !!user && (isCreator || isGroupAdmin || user.is_superuser);

  if (isLoading || !order) {
    return (
      <Stack sx={{ p: 4, alignItems: "center" }}>
        <CircularProgress size={20} />
      </Stack>
    );
  }

  const reorder = () =>
    openDrawer({ kind: "new-order", groupId, chemicalId: order.chemical_id });

  return (
    <Stack spacing={2} sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="h6" sx={{ flex: 1 }}>
          {order.chemical_name}
        </Typography>
        <Chip
          size="small"
          color={
            order.status === "ordered"
              ? "warning"
              : order.status === "received"
              ? "success"
              : "default"
          }
          label={order.status}
        />
      </Stack>

      <Typography variant="body2" color="text.secondary">
        {order.package_count} × {order.amount_per_package} {order.unit} from{" "}
        {order.supplier_name} ({order.project_name})
      </Typography>

      <Typography variant="caption" color="text.secondary">
        Ordered by {order.ordered_by_user_email ?? "(unknown)"} on{" "}
        {new Date(order.ordered_at).toLocaleDateString()}
        {order.received_by_user_email && order.received_at && (
          <>
            {" · "}received by {order.received_by_user_email} on{" "}
            {new Date(order.received_at).toLocaleDateString()}
          </>
        )}
      </Typography>

      {order.price_per_package && (
        <Typography variant="body2">
          {order.currency} {order.price_per_package} per package · total{" "}
          {order.currency}{" "}
          {(Number(order.price_per_package) * order.package_count).toFixed(2)}
        </Typography>
      )}

      {order.expected_arrival && (
        <Typography variant="caption">
          Expected: {order.expected_arrival}
        </Typography>
      )}

      {order.vendor_product_url && (
        <Typography variant="caption">
          <a href={order.vendor_product_url} target="_blank" rel="noopener">
            Vendor product page ↗
          </a>
        </Typography>
      )}

      {order.comment && (
        <Typography variant="body2" sx={{ fontStyle: "italic" }}>
          {order.comment}
        </Typography>
      )}

      {order.status === "cancelled" && order.cancellation_reason && (
        <Alert severity="info">Cancelled: {order.cancellation_reason}</Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
        {order.status === "ordered" && (
          <Button variant="contained" onClick={() => setShowReceive(true)}>
            Mark received
          </Button>
        )}
        {order.status === "ordered" && canCancel && (
          <Button
            variant="outlined"
            color="error"
            onClick={() => setShowCancel(true)}
          >
            Cancel
          </Button>
        )}
        <Button variant="outlined" onClick={reorder}>
          Reorder
        </Button>
        <Button onClick={onDone}>Close</Button>
      </Stack>

      {showReceive && (
        <ReceiveOrderDialog
          open
          order={order}
          onDone={() => {
            setShowReceive(false);
            onDone();
          }}
        />
      )}

      <Dialog open={showCancel} onClose={() => setShowCancel(false)}>
        <DialogTitle>Cancel order</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            multiline
            rows={2}
            margin="dense"
            label="Reason (optional)"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCancel(false)}>Back</Button>
          <Button
            color="error"
            onClick={async () => {
              await cancel.mutateAsync({
                cancellation_reason: cancelReason || null,
              });
              setShowCancel(false);
              onDone();
            }}
          >
            Confirm cancel
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
