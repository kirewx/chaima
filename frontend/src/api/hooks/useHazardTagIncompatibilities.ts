import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { IncompatibilityCreate, IncompatibilityRead } from "../../types";

const key = (groupId: string) => ["hazard-tag-incompatibilities", groupId];

export function useHazardTagIncompatibilities(groupId: string) {
  return useQuery({
    queryKey: key(groupId),
    queryFn: async () => {
      const r = await client.get<IncompatibilityRead[]>(
        `/groups/${groupId}/hazard-tags/incompatibilities`,
      );
      return r.data;
    },
    enabled: !!groupId,
  });
}

export function useCreateIncompatibility(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: IncompatibilityCreate) => {
      const r = await client.post<IncompatibilityRead>(
        `/groups/${groupId}/hazard-tags/incompatibilities`,
        body,
      );
      return r.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: key(groupId) }),
  });
}

export function useDeleteIncompatibility(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await client.delete(
        `/groups/${groupId}/hazard-tags/incompatibilities/${id}`,
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: key(groupId) }),
  });
}
