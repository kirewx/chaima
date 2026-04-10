import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { StorageLocationNode, StorageLocationRead, StorageLocationCreate, StorageLocationUpdate } from "../../types";

export function useStorageTree(groupId: string) {
  return useQuery<StorageLocationNode[]>({
    queryKey: ["storageLocations", groupId, "tree"],
    queryFn: () => client.get(`/groups/${groupId}/storage-locations`).then((r) => r.data),
  });
}

export function useStorageLocation(groupId: string, locationId: string) {
  return useQuery<StorageLocationRead>({
    queryKey: ["storageLocations", groupId, locationId],
    queryFn: () => client.get(`/groups/${groupId}/storage-locations/${locationId}`).then((r) => r.data),
    enabled: !!locationId,
  });
}

export function useCreateStorageLocation(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StorageLocationCreate) =>
      client.post(`/groups/${groupId}/storage-locations`, data).then((r) => r.data as StorageLocationRead),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["storageLocations", groupId] }); },
  });
}

export function useUpdateStorageLocation(groupId: string, locationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StorageLocationUpdate) =>
      client.patch(`/groups/${groupId}/storage-locations/${locationId}`, data).then((r) => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["storageLocations", groupId] }); },
  });
}

export function useDeleteStorageLocation(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (locationId: string) => client.delete(`/groups/${groupId}/storage-locations/${locationId}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["storageLocations", groupId] }); },
  });
}
