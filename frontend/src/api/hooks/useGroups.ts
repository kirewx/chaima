import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { GroupRead, GroupCreate, GroupUpdate, MemberRead, MemberAdd, MemberUpdate, PaginatedResponse } from "../../types";

export function useGroups() {
  return useQuery<GroupRead[]>({
    queryKey: ["groups"],
    queryFn: () =>
      client
        .get<PaginatedResponse<GroupRead>>("/groups")
        .then((r) => r.data.items),
  });
}

export function useAllGroups(enabled: boolean = true) {
  return useQuery<GroupRead[]>({
    queryKey: ["groups", "all"],
    queryFn: () =>
      client
        .get<PaginatedResponse<GroupRead>>("/groups", { params: { scope: "all" } })
        .then((r) => r.data.items),
    enabled,
  });
}

export function useGroup(groupId: string) {
  return useQuery<GroupRead>({
    queryKey: ["groups", groupId],
    queryFn: () => client.get(`/groups/${groupId}`).then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useCreateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: GroupCreate) =>
      client.post("/groups", data).then((r) => r.data as GroupRead),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["groups", "all"] });
    },
  });
}

export function useUpdateGroup(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: GroupUpdate) =>
      client.patch(`/groups/${groupId}`, data).then((r) => r.data as GroupRead),
    onSuccess: (updated) => {
      const patchCache = (key: readonly unknown[]) => {
        const existing = queryClient.getQueryData<GroupRead[]>(key);
        if (existing === undefined) {
          queryClient.invalidateQueries({ queryKey: key });
          return;
        }
        const next = existing.map((g) => (g.id === updated.id ? updated : g));
        queryClient.setQueryData<GroupRead[]>(key, next);
      };
      patchCache(["groups"]);
      patchCache(["groups", "all"]);
      // Also patch the single-group cache if present.
      queryClient.setQueryData<GroupRead>(["groups", groupId], updated);
    },
  });
}

export function useGroupMembers(groupId: string) {
  return useQuery<MemberRead[]>({
    queryKey: ["groups", groupId, "members"],
    queryFn: () => client.get(`/groups/${groupId}/members`).then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useAddMember(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: MemberAdd) =>
      client.post(`/groups/${groupId}/members`, data).then((r) => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["groups", groupId, "members"] }); },
  });
}

export function useUpdateMember(groupId: string, userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: MemberUpdate) =>
      client.patch(`/groups/${groupId}/members/${userId}`, data).then((r) => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["groups", groupId, "members"] }); },
  });
}

export function useRemoveMember(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      client.delete(`/groups/${groupId}/members/${userId}`),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["groups", groupId, "members"] }); },
  });
}
