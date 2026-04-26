import type { OrderStatus } from "../../types";

interface Props {
  groupId: string;
  status: OrderStatus;
}

export function OrderList({ groupId, status }: Props) {
  void groupId;
  return <div>OrderList placeholder ({status})</div>;
}
