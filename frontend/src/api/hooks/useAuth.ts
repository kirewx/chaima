import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type { UserRead } from "../../types";

export function useCurrentUser() {
  return useQuery<UserRead>({
    queryKey: ["currentUser"],
    queryFn: () => client.get("/users/me").then((r) => r.data),
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { username: string; password: string }) => {
      const form = new URLSearchParams();
      form.append("username", data.username);
      form.append("password", data.password);
      return client.post("/auth/cookie/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => client.post("/auth/cookie/logout"),
    onSuccess: () => {
      queryClient.clear();
    },
  });
}

export function useUpdateMainGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) =>
      client.patch("/users/me/main-group", { group_id: groupId }).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["currentUser"] });
    },
  });
}
