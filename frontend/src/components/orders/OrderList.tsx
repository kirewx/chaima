import {
  Box,
  Button,
  Card,
  CardActionArea,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { useOrders } from "../../api/hooks/useOrders";
import { useDrawer } from "../drawer/DrawerContext";
import type { OrderRead, OrderStatus } from "../../types";

interface Props {
  groupId: string;
  status: OrderStatus;
}

function formatPrice(o: OrderRead): string {
  if (o.price_per_package == null) return "no price";
  return `${o.currency} ${o.price_per_package}`;
}

function isOverdue(o: OrderRead): boolean {
  if (!o.expected_arrival || o.status !== "ordered") return false;
  return new Date(o.expected_arrival) < new Date();
}

export function OrderList({ groupId, status }: Props) {
  const { data, isLoading } = useOrders(groupId, { status });
  const { open: openDrawer } = useDrawer();
  const orders = data?.items ?? [];

  const newOrder = () => openDrawer({ kind: "new-order", groupId });

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  return (
    <Box>
      <Stack direction="row" sx={{ mb: 2, justifyContent: "flex-end" }}>
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={newOrder}
        >
          New order
        </Button>
      </Stack>

      {orders.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          No {status} orders.
        </Typography>
      )}

      <Stack spacing={1}>
        {orders.map((o) => (
          <Card key={o.id} variant="outlined">
            <CardActionArea
              onClick={() => openDrawer({ kind: "order-detail", groupId, orderId: o.id })}
              sx={{ p: 2 }}
            >
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={1}
                sx={{ alignItems: { sm: "center" } }}
              >
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="subtitle2" noWrap>
                    {o.chemical_name ?? "(unknown)"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {o.supplier_name} • {o.project_name}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2">
                    {o.package_count} × {o.amount_per_package} {o.unit} @ {formatPrice(o)}
                  </Typography>
                </Box>
                <Box>
                  {o.expected_arrival && (
                    <Chip
                      size="small"
                      label={`exp ${o.expected_arrival}`}
                      color={isOverdue(o) ? "error" : "default"}
                    />
                  )}
                </Box>
              </Stack>
            </CardActionArea>
          </Card>
        ))}
      </Stack>
    </Box>
  );
}
