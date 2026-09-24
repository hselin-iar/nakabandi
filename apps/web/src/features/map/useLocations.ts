/**
 * useLocations.ts — TanStack Query hook for bank infrastructure points on the map.
 * DOC 3 M3: "Location points ... come from /geo/locations (bbox, kind, bank)".
 */

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../shared/api/client";
import type { LocationPoint } from "./types";

export function useLocations() {
  return useQuery<LocationPoint[]>({
    queryKey: ["geo", "locations"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/geo/locations", {
        params: { query: { limit: 2000 } },
      });
      if (error) throw new Error("Failed to load locations");
      return data.items as LocationPoint[];
    },
    staleTime: 60_000,
  });
}
