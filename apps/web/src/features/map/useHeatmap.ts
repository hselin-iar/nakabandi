/**
 * useHeatmap.ts — TanStack Query hook for GIS heatmap rollups.
 * DOC 3 M3 / DOC 4 Step C5:
 *   - Debounces filter changes by 250ms.
 *   - Invalidates on streamKeys.heatmap() and SSE heat.version.
 */

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../shared/api/client";
import { streamKeys } from "../../shared/stream/streamKeys";
import type { HeatmapFilters, HeatmapResponse } from "./types";

export function useDebounce<T>(value: T, delayMs = 250): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delayMs]);

  return debouncedValue;
}

export function useHeatmap(filters: HeatmapFilters) {
  const debouncedFilters = useDebounce(filters, 250);

  return useQuery<HeatmapResponse>({
    queryKey: [...streamKeys.heatmap(), debouncedFilters],
    queryFn: async () => {
      const queryParams: Record<string, string | number | undefined> = {
        layer: debouncedFilters.layer,
        level: debouncedFilters.level,
      };
      if (debouncedFilters.state) queryParams.state = debouncedFilters.state;
      if (debouncedFilters.district) queryParams.district = debouncedFilters.district;
      if (debouncedFilters.category) queryParams.category = debouncedFilters.category;
      if (debouncedFilters.amount_band) queryParams.amount_band = debouncedFilters.amount_band;
      if (debouncedFilters.min_confidence) queryParams.min_confidence = debouncedFilters.min_confidence;
      if (debouncedFilters.bbox) queryParams.bbox = debouncedFilters.bbox;
      if (debouncedFilters.from) queryParams.from_ = debouncedFilters.from;
      if (debouncedFilters.to) queryParams.to = debouncedFilters.to;

      // Real API call only — no fixture fallback (DOC1 §1.0 "nothing on our side is mocked").
      // An empty `cells` array is a legitimate state (no hotspots right now) and must render
      // as such, not be silently swapped for invented Delhi/Mumbai/Gurugram data; a real fetch
      // failure surfaces as `isError` for the caller to show, not as fake data either.
      const { data, error } = await apiClient.GET("/analytics/heatmap", {
        params: { query: queryParams },
      });
      if (error) throw new Error("Failed to load heatmap");
      // The generated schema widens `layer`/`level` to `string`; the API's own enum guarantees
      // the narrower literal values this hook's callers rely on.
      return data as HeatmapResponse;
    },
    staleTime: 5_000,
  });
}

