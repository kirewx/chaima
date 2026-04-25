import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import { useContainers } from "./useContainers";
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
      client
        .patch(`/groups/${groupId}/storage-locations/${locationId}`, data)
        .then((r) => r.data as StorageLocationRead),
    onSuccess: (data) => {
      queryClient.setQueryData(["storageLocations", groupId, locationId], data);
      queryClient.invalidateQueries({ queryKey: ["storageLocations", groupId] });
    },
  });
}

/**
 * Archive (soft-delete) a storage location. Note: as of Plan 3 Task 3, the backend
 * `delete_location` service still hard-deletes the row and raises
 * `LocationHasContainersError` if containers exist. The soft-delete contract promised
 * by Plan 1 is NOT yet honored server-side — follow-up required.
 */
export function useArchiveStorageLocation(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (locationId: string) =>
      client.delete(`/groups/${groupId}/storage-locations/${locationId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storageLocations", groupId] });
      queryClient.invalidateQueries({ queryKey: ["containers", groupId] });
    },
  });
}

/**
 * Thin wrapper over `useContainers` scoped to a shelf (leaf storage location).
 * Returns non-archived containers for the given location, up to 200.
 * When `locationId` is null, returns the unfiltered list — callers should ignore
 * the data in that case (the query still runs because `useContainers` only
 * gates on `groupId`).
 */
export function useShelfContainers(groupId: string, locationId: string | null) {
  return useContainers(
    groupId,
    locationId ? { location_id: locationId, is_archived: false, limit: 200 } : {},
  );
}
