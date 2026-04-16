import { useMutation } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import client from "../client";
import type { PubChemLookupResult, PubChemGHSHit } from "../../types";

export function usePubChemLookup() {
  return useMutation<PubChemLookupResult, AxiosError, string>({
    mutationFn: (q) =>
      client
        .get<PubChemLookupResult>("/pubchem/lookup", { params: { q } })
        .then((r) => r.data),
  });
}

export async function fetchPubChemGHS(cid: string): Promise<PubChemGHSHit[]> {
  const { data } = await client.get<PubChemGHSHit[]>("/pubchem/ghs", {
    params: { cid },
  });
  return data;
}
