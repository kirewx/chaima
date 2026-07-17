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
      // List queries come in two shapes under the ["chemicals", groupId]
      // prefix: infinite data ({ pages }) from useChemicals, and plain
      // PaginatedResponse ({ items }) from useMultiGroupChemicals. The
      // prefix also matches detail keys — anything else passes through.
      const patchItems = (page: PaginatedResponse<ChemicalRead>) => ({
        ...page,
        items: page.items.map((c) =>
          c.id === chemicalId ? { ...c, zvg } : c,
        ),
      });
      queryClient.setQueriesData<
        InfiniteData<PaginatedResponse<ChemicalRead>> | PaginatedResponse<ChemicalRead>
      >({ queryKey: ["chemicals", groupId] }, (old) => {
        if (!old) return old;
        if ("pages" in old) {
          return { ...old, pages: old.pages.map(patchItems) };
        }
        if ("items" in old) {
          return patchItems(old);
        }
        return old;
      });
    },
  });
}
