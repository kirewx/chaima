import { useQuery } from "@tanstack/react-query";
import client from "../client";
import type { PaginatedResponse, GHSCodeRead } from "../../types";

export function useGHSCodes(search?: string) {
  return useQuery<PaginatedResponse<GHSCodeRead>>({
    queryKey: ["ghsCodes", search],
    queryFn: () => client.get("/ghs-codes", { params: { search, limit: 100 } }).then((r) => r.data),
  });
}
