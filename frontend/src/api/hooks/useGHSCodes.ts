import { useQuery } from "@tanstack/react-query";
import client from "../client";
import type { GHSCodeRead, PaginatedResponse } from "../../types";

async function fetchGHSCodes(): Promise<GHSCodeRead[]> {
  const resp = await client.get<PaginatedResponse<GHSCodeRead>>(
    "/ghs-codes",
    { params: { limit: 100, offset: 0 } },
  );
  return resp.data.items;
}

export function useGHSCodes() {
  return useQuery({
    queryKey: ["ghs-codes"],
    queryFn: fetchGHSCodes,
    staleTime: 60 * 60 * 1000,
  });
}
