import { useQuery } from "@tanstack/react-query";
import client from "../client";
import type { PubChemVendorList } from "../../types";

export function usePubChemVendors(cid: string | null | undefined) {
  return useQuery<PubChemVendorList>({
    queryKey: ["pubchem", "vendors", cid],
    queryFn: () =>
      client.get(`/pubchem/vendors/${cid}`).then((r) => r.data),
    enabled: !!cid,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}
