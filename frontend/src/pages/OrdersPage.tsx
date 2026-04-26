import { useState } from "react";
import { Box, Tab, Tabs } from "@mui/material";
import { useCurrentUser } from "../api/hooks/useAuth";
import { OrderList } from "../components/orders/OrderList";
import { WishlistList } from "../components/orders/WishlistList";
import type { OrderStatus } from "../types";

type TabKey = OrderStatus | "wishlist";

export default function OrdersPage() {
  const { data: user } = useCurrentUser();
  const groupId = user?.main_group_id ?? "";
  const [tab, setTab] = useState<TabKey>("ordered");

  if (!groupId) {
    return <Box sx={{ p: 2 }}>Join a group to see orders.</Box>;
  }

  return (
    <Box>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab value="ordered" label="Open" />
        <Tab value="received" label="Received" />
        <Tab value="cancelled" label="Cancelled" />
        <Tab value="wishlist" label="Wishlist" />
      </Tabs>

      {tab === "wishlist" ? (
        <WishlistList groupId={groupId} />
      ) : (
        <OrderList groupId={groupId} status={tab} />
      )}
    </Box>
  );
}
