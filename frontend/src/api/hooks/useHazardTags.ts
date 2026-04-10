import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { PaginatedResponse, HazardTagRead, HazardTagCreate, HazardTagUpdate, IncompatibilityRead, IncompatibilityCreate } from "../../types";

export function useHazardTags(groupId: string, search?: string) {
  return useQuery<PaginatedResponse<HazardTagRead>>({
    queryKey: ["hazardTags", groupId, search],
    queryFn: () => client.get(`/groups/${groupId}/hazard-tags`, { params: { search, limit: 100 } }).then((r) => r.data),
  });
}

export function useCreateHazardTag(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: HazardTagCreate) =>
      client.post(`/groups/${groupId}/hazard-tags`, data).then((r) => r.data as HazardTagRead),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["hazardTags", groupId] }); },
  });
}

export function useUpdateHazardTag(groupId: string, tagId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: HazardTagUpdate) =>
      client.patch(`/groups/${groupId}/hazard-tags/${tagId}`, data).then((r) => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["hazardTags", groupId] }); },
  });
}

export function useDeleteHazardTag(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tagId: string) => client.delete(`/groups/${groupId}/hazard-tags/${tagId}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["hazardTags", groupId] }); },
  });
}

export function useIncompatibilities(groupId: string) {
  return useQuery<PaginatedResponse<IncompatibilityRead>>({
    queryKey: ["incompatibilities", groupId],
    queryFn: () => client.get(`/groups/${groupId}/hazard-tags/incompatibilities`).then((r) => r.data),
  });
}

export function useCreateIncompatibility(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: IncompatibilityCreate) =>
      client.post(`/groups/${groupId}/hazard-tags/incompatibilities`, data).then((r) => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["incompatibilities", groupId] }); },
  });
}

export function useDeleteIncompatibility(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (incompatibilityId: string) =>
      client.delete(`/groups/${groupId}/hazard-tags/incompatibilities/${incompatibilityId}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["incompatibilities", groupId] }); },
  });
}
