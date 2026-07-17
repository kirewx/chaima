import { useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import client from "../client";
import type { ChemicalDetail, ChemicalRead, PaginatedResponse } from "../../types";

export interface GestisResolveResult {
  zvg: string | null;
  url: string | null;
}

// EN deeplink base — linking is explicitly permitted by GESTIS.
export function gestisUrl(zvg: string): string {
  return `https://gestis-database.dguv.de/data?name=${zvg}`;
}

export function useGestisResolve(groupId: string, chemicalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      client
        .post(`/groups/${groupId}/chemicals/${chemicalId}/gestis-resolve`)
        .then((r) => r.data as GestisResolveResult),
    onSuccess: (result) => {
      if (!result.zvg) return; // miss / GESTIS down: nothing to update
      const zvg = result.zvg;
      // Detail query: plain ChemicalDetail object.
      queryClient.setQueryData<ChemicalDetail>(
        ["chemicals", groupId, chemicalId],
        (old) => (old ? { ...old, zvg } : old),
      );
      // List queries: infinite data with paginated pages. The prefix also
      // matches detail keys, so guard on the "pages" shape.
      queryClient.setQueriesData<InfiniteData<PaginatedResponse<ChemicalRead>>>(
        { queryKey: ["chemicals", groupId] },
        (old) => {
          if (!old || !("pages" in old)) return old;
          return {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((c) =>
                c.id === chemicalId ? { ...c, zvg } : c,
              ),
            })),
          };
        },
      );
    },
  });
}
