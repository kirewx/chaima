import { useQuery } from "@tanstack/react-query";
import client from "../client";

/**
 * Fetch a chemical's structure as an SVG, rendered on demand from its
 * SMILES via RDKit. Returns `null` when the chemical has no SMILES
 * (backend responds 404 with a known detail).
 */
export function useChemicalStructureSvg(
  groupId: string,
  chemicalId: string | undefined,
) {
  return useQuery<string | null>({
    enabled: !!groupId && !!chemicalId,
    queryKey: ["chemical-structure-svg", groupId, chemicalId],
    staleTime: 60 * 60 * 1000,
    queryFn: async () => {
      try {
        const resp = await client.get<string>(
          `/groups/${groupId}/chemicals/${chemicalId}/structure.svg`,
          { responseType: "text" },
        );
        return typeof resp.data === "string" ? resp.data : null;
      } catch (err: any) {
        if (err?.response?.status === 404) return null;
        throw err;
      }
    },
  });
}
