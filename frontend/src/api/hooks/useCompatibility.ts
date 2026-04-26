import { keepPreviousData, useQuery } from "@tanstack/react-query";
import client from "../client";
import type { ConflictRead } from "../../types";

export function useLocationConflicts(groupId: string, locationId: string | null) {
  return useQuery({
    queryKey: ["location-conflicts", groupId, locationId],
    queryFn: async () => {
      const r = await client.get<ConflictRead[]>(
        `/groups/${groupId}/locations/${locationId}/conflicts`,
      );
      return r.data;
    },
    enabled: !!groupId && !!locationId,
  });
}

export function useCompatibilityCheck(
  groupId: string,
  chemicalId: string | null,
  locationId: string | null,
) {
  return useQuery({
    queryKey: ["compatibility-check", groupId, chemicalId, locationId],
    queryFn: async () => {
      const r = await client.get<ConflictRead[]>(
        `/groups/${groupId}/compatibility/check`,
        { params: { chemical_id: chemicalId, location_id: locationId } },
      );
      return r.data;
    },
    enabled: !!groupId && !!chemicalId && !!locationId,
    placeholderData: keepPreviousData,
  });
}
