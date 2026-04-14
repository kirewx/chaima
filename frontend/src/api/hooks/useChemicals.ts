import { useInfiniteQuery, useQuery, useMutation, useQueryClient, useQueries } from "@tanstack/react-query";
import client from "../client";
import type { PaginatedResponse, ChemicalRead, ChemicalDetail, ChemicalCreate, ChemicalUpdate, ChemicalSearchParams } from "../../types";

const PAGE_SIZE = 20;

export function useChemicals(groupId: string, params: ChemicalSearchParams, includeArchived = false) {
  return useInfiniteQuery<PaginatedResponse<ChemicalRead>>({
    queryKey: ["chemicals", groupId, params, includeArchived],
    queryFn: ({ pageParam }) =>
      client.get(`/groups/${groupId}/chemicals`, {
        params: { ...params, offset: pageParam, limit: params.limit ?? PAGE_SIZE, ...(includeArchived ? { include_archived: true } : {}) },
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

export function useReplaceHazardTags(groupId: string, chemicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ chemicalId: cId, hazardTagIds }: { chemicalId: string; hazardTagIds: string[] }) =>
      client.put(`/groups/${groupId}/chemicals/${cId}/hazard-tags`, { hazard_tag_ids: hazardTagIds }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] });
      queryClient.invalidateQueries({ queryKey: ["chemicals", groupId, chemicalId] });
    },
  });
}

export function useMultiGroupChemicals(groupIds: string[], params: ChemicalSearchParams) {
  return useQueries({
    queries: groupIds.map((gid) => ({
      queryKey: ["chemicals", gid, params] as const,
      queryFn: () =>
        client.get(`/groups/${gid}/chemicals`, {
          params: { ...params, offset: 0, limit: params.limit ?? 100 },
        }).then((r) => r.data as PaginatedResponse<ChemicalRead>),
    })),
  });
}

export function useArchiveChemical(groupId: string, chemicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await client.post(`/groups/${groupId}/chemicals/${chemicalId}/archive`);
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] }); },
  });
}

export function useUnarchiveChemical(groupId: string, chemicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await client.post(`/groups/${groupId}/chemicals/${chemicalId}/unarchive`);
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] }); },
  });
}

export function useUploadSDS(groupId: string, chemicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await client.post(
        `/groups/${groupId}/chemicals/${chemicalId}/sds`,
        fd,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return data;
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] }); },
  });
}
