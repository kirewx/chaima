import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { PaginatedResponse, ContainerRead, ContainerCreate, ContainerUpdate, ContainerSearchParams } from "../../types";

export function useContainers(groupId: string, params: ContainerSearchParams) {
  return useQuery<PaginatedResponse<ContainerRead>>({
    queryKey: ["containers", groupId, params],
    queryFn: () => client.get(`/groups/${groupId}/containers`, { params }).then((r) => r.data),
  });
}

export function useChemicalContainers(groupId: string, chemicalId: string, params?: ContainerSearchParams) {
  return useQuery<PaginatedResponse<ContainerRead>>({
    queryKey: ["containers", groupId, "chemical", chemicalId, params],
    queryFn: () => client.get(`/groups/${groupId}/chemicals/${chemicalId}/containers`, { params }).then((r) => r.data),
    enabled: !!chemicalId,
  });
}

export function useCreateContainer(groupId: string, chemicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ContainerCreate) =>
      client.post(`/groups/${groupId}/chemicals/${chemicalId}/containers`, data).then((r) => r.data as ContainerRead),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
      queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] });
    },
  });
}

export function useUpdateContainer(groupId: string, containerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ContainerUpdate) =>
      client.patch(`/groups/${groupId}/containers/${containerId}`, data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
      queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] });
    },
  });
}

export function useArchiveContainer(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (containerId: string) => client.delete(`/groups/${groupId}/containers/${containerId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
      queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] });
    },
  });
}

export function useUnarchiveContainer(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (containerId: string) =>
      client.patch(`/groups/${groupId}/containers/${containerId}`, { is_archived: false }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
      queryClient.invalidateQueries({ queryKey: ["chemicals", groupId] });
    },
  });
}
