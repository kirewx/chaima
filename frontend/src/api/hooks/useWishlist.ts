import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../client";
import type {
  PaginatedResponse,
  WishlistRead,
  WishlistCreate,
  WishlistPromoteResult,
} from "../../types";

export function useWishlist(groupId: string) {
  return useQuery<PaginatedResponse<WishlistRead>>({
    queryKey: ["wishlist", groupId],
    queryFn: () =>
      client.get(`/groups/${groupId}/wishlist`).then((r) => r.data),
    enabled: !!groupId,
  });
}

export function useCreateWishlist(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WishlistCreate) =>
      client
        .post(`/groups/${groupId}/wishlist`, data)
        .then((r) => r.data as WishlistRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wishlist", groupId] });
    },
  });
}

export function useDismissWishlist(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (wishlistId: string) =>
      client
        .post(`/groups/${groupId}/wishlist/${wishlistId}/dismiss`)
        .then((r) => r.data as WishlistRead),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["wishlist", groupId] });
    },
  });
}

export function usePromoteWishlist(groupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (wishlistId: string) =>
      client
        .post(`/groups/${groupId}/wishlist/${wishlistId}/promote`)
        .then((r) => r.data as WishlistPromoteResult),
    onSuccess: () => {
      // Promotion may resolve/create a chemical and changes the item status.
      qc.invalidateQueries({ queryKey: ["wishlist", groupId] });
      qc.invalidateQueries({ queryKey: ["chemicals", groupId] });
    },
  });
}
