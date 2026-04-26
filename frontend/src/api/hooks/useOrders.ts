import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type {
  PaginatedResponse,
  OrderRead,
  OrderCreate,
  OrderUpdate,
  OrderReceive,
  OrderCancel,
  ContainerRead,
  OrderStatus,
} from "../../types";

export interface OrdersFilters {
  status?: OrderStatus;
  supplier_id?: string;
  project_id?: string;
  chemical_id?: string;
}

export function useOrders(groupId: string, filters: OrdersFilters = {}) {
  return useQuery<PaginatedResponse<OrderRead>>({
    queryKey: ["orders", groupId, filters],
    queryFn: () =>
      client
        .get(`/groups/${groupId}/orders`, { params: { ...filters, limit: 500 } })
        .then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useOrder(groupId: string, orderId: string | null | undefined) {
  return useQuery<OrderRead>({
    queryKey: ["orders", groupId, orderId],
    queryFn: () =>
      client.get(`/groups/${groupId}/orders/${orderId}`).then((r) => r.data),
    enabled: !!groupId && !!orderId,
  });
}

export function useCreateOrder(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderCreate) =>
      client
        .post(`/groups/${groupId}/orders`, data)
        .then((r) => r.data as OrderRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders", groupId] });
      qc.invalidateQueries({ queryKey: ["wishlist", groupId] });
    },
  });
}

export function useUpdateOrder(groupId: string, orderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderUpdate) =>
      client
        .patch(`/groups/${groupId}/orders/${orderId}`, data)
        .then((r) => r.data as OrderRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders", groupId] });
    },
  });
}

export function useReceiveOrder(groupId: string, orderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderReceive) =>
      client
        .post(`/groups/${groupId}/orders/${orderId}/receive`, data)
        .then((r) => r.data as ContainerRead[]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders", groupId] });
      qc.invalidateQueries({ queryKey: ["containers"] });
      qc.invalidateQueries({ queryKey: ["chemicals"] });
    },
  });
}

export function useCancelOrder(groupId: string, orderId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderCancel) =>
      client
        .post(`/groups/${groupId}/orders/${orderId}/cancel`, data)
        .then((r) => r.data as OrderRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders", groupId] });
    },
  });
}
