import { useInfiniteQuery, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { PaginatedResponse, ChemicalRead, ChemicalDetail, ChemicalCreate, ChemicalUpdate, ChemicalSearchParams } from "../../types";

const PAGE_SIZE = 20;

export function useChemicals(groupId: string, params: ChemicalSearchParams) {
  return useInfiniteQuery<PaginatedResponse<ChemicalRead>>({
    queryKey: ["chemicals", groupId, params],
    queryFn: ({ pageParam }) =>
      client.get(`/groups/${groupId}/chemicals`, {
        params: { ...params, offset: pageParam, limit: params.limit ?? PAGE_SIZE },
      }).then((r) => r.data),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.limit;
      return next < lastPage.total ? next : undefined;
    },
  });
}

export function useChemicalDetail(groupId: string, chemicalId: string) {
  return useQuery<ChemicalDetail>({
    queryKey: ["chemicals", groupId, chemicalId],
    queryFn: () => client.get(`/groups/${groupId}/chemicals/${chemicalId}`).then((r) => r.data),
    enabled: !!chemicalId,
  });
}

export function useCreateChemical(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChemicalCreate) =>
      client.post(`/groups/${groupId}/chemicals`, data).then((r) => r.data as ChemicalRead),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] }); },
  });
}

export function useUpdateChemical(groupId: string, chemicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChemicalUpdate) =>
      client.patch(`/groups/${groupId}/chemicals/${chemicalId}`, data).then((r) => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] }); },
  });
}

export function useDeleteChemical(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (chemicalId: string) =>
      client.delete(`/groups/${groupId}/chemicals/${chemicalId}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] }); },
  });
}
