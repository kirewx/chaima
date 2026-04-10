import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { InviteInfo, InviteRead } from "../../types";

export function useInviteInfo(token: string) {
  return useQuery<InviteInfo>({
    queryKey: ["invite", token],
    queryFn: () => client.get(`/invites/${token}`).then((r) => r.data),
    enabled: !!token,
    retry: false,
  });
}

export function useAcceptInviteNewUser(token: string) {
  return useMutation({
    mutationFn: (data: { email: string; password: string }) =>
      client.patch(`/invites/${token}`, data).then((r) => r.data),
  });
}

export function useAcceptInviteExistingUser(token: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => client.patch(`/invites/${token}`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });
}

export function useCreateInvite(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      client.post(`/groups/${groupId}/invites`).then((r) => r.data as InviteRead),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invites", groupId] });
    },
  });
}

export function useGroupInvites(groupId: string) {
  return useQuery<InviteRead[]>({
    queryKey: ["invites", groupId],
    queryFn: () => client.get(`/groups/${groupId}/invites`).then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useRevokeInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (inviteId: string) => client.delete(`/invites/${inviteId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invites"] });
    },
  });
}
