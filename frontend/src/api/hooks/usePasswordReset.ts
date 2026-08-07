import { useMutation } from "@tanstack/react-query";
import client from "../client";
import type { ResetLinkRead } from "../../types";

export function useCreateResetLink(groupId: string) {
  return useMutation({
    mutationFn: (userId: string) =>
      client
        .post(`/groups/${groupId}/members/${userId}/reset-link`)
        .then((r) => r.data as ResetLinkRead),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: (data: { token: string; password: string }) =>
      client.post("/auth/reset-password", data).then((r) => r.data),
  });
}
