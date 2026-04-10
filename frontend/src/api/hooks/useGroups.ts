import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { GroupRead, GroupCreate, GroupUpdate, MemberRead, MemberAdd, MemberUpdate } from "../../types";

export function useGroups() {
  return useQuery<GroupRead[]>({
    queryKey: ["groups"],
    queryFn: () => client.get("/groups").then((r) => r.data),
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
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["groups"] }); },
  });
}

export function useUpdateGroup(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: GroupUpdate) =>
      client.patch(`/groups/${groupId}`, data).then((r) => r.data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["groups"] }); },
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
