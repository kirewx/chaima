import { useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { UserRead } from "../../types";

export interface UpdateMePayload {
  email?: string;
  password?: string;
  dark_mode?: boolean;
}

export function useUpdateMe() {
  const queryClient = useQueryClient();
  return useMutation<UserRead, Error, UpdateMePayload>({
    mutationFn: (payload) =>
      client.patch("/users/me", payload).then((r) => r.data),
    onSuccess: (updated) => {
      queryClient.setQueryData(["currentUser"], updated);
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });
}
