import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { PaginatedResponse, SupplierRead, SupplierCreate, SupplierUpdate } from "../../types";

export function useSuppliers(groupId: string, search?: string) {
  return useQuery<PaginatedResponse<SupplierRead>>({
    queryKey: ["suppliers", groupId, search],
    queryFn: () => client.get(`/groups/${groupId}/suppliers`, { params: { search, limit: 100 } }).then((r) => r.data),
  });
}

export function useCreateSupplier(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SupplierCreate) =>
      client.post(`/groups/${groupId}/suppliers`, data).then((r) => r.data as SupplierRead),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["suppliers", groupId] }); },
  });
}

export function useUpdateSupplier(groupId: string, supplierId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SupplierUpdate) =>
      client.patch(`/groups/${groupId}/suppliers/${supplierId}`, data).then((r) => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["suppliers", groupId] }); },
  });
}

export function useDeleteSupplier(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (supplierId: string) => client.delete(`/groups/${groupId}/suppliers/${supplierId}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["suppliers", groupId] }); },
  });
}

export function useSupplier(groupId: string, supplierId: string | null | undefined) {
  const { data: page } = useSuppliers(groupId);
  const supplier = supplierId ? (page?.items ?? []).find((s) => s.id === supplierId) : undefined;
  return { data: supplier };
}
