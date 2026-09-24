/**
 * useHeatmap.ts — TanStack Query hook for GIS heatmap rollups.
 * DOC 3 M3 / DOC 4 Step C5:
 *   - Debounces filter changes by 250ms.
 *   - Invalidates on streamKeys.heatmap() and SSE heat.version.
 *   - Supplies hand-computed LC-4 fixture fallback (A9/Sync 4 compliant).
 */

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../shared/api/client";
import { streamKeys } from "../../shared/stream/streamKeys";
import type { HeatmapFilters, HeatmapResponse, HeatCell } from "./types";

export const FIXTURE_HEATMAP: HeatmapResponse = {
  layer: "live",
  level: "cell",
  generated_at: "2026-01-15T12:00:00Z",
  version: 42,
  cells: [
    {
      id: "C+0107_+0309",
      kind: "cell",
      name: "Connaught Place Hub (DL/UP)",
      lat: 28.63,
      lon: 77.22,
      value: 0.94,
      alert_count: 5,
    },
    {
      id: "C+0076_+0291",
      kind: "cell",
      name: "Bandra-Kurla Complex (MH)",
      lat: 19.07,
      lon: 72.87,
      value: 0.82,
      alert_count: 4,
    },
    {
      id: "C+0093_+0341",
      kind: "cell",
      name: "Ranchi Central Corridor (JH)",
      lat: 23.34,
      lon: 85.31,
      value: 0.65,
      alert_count: 2,
    },
    {
      id: "C+0113_+0308",
      kind: "cell",
      name: "Cyber City Gurugram (HR)",
      lat: 28.49,
      lon: 77.09,
      value: 0.88,
      alert_count: 6,
    },
    {
      id: "C+0105_+0321",
      kind: "cell",
      name: "Kanpur Civil Lines (UP)",
      lat: 26.47,
      lon: 80.33,
      value: 0.45,
      alert_count: 1,
    },
    {
      id: "C+0080_+0316",
      kind: "cell",
      name: "Nagpur Central (MH)",
      lat: 21.15,
      lon: 79.09,
      value: 0.32,
      alert_count: 1,
    },
  ],
  suppressed_count: 2,
  legend: {
    min: 0.0,
    max: 1.0,
    unit: "Forecast Intensity (Mass)",
    note: "Persistence estimate of recent forecast intensity over the next 72 h",
  },
};

export const FIXTURE_HOTSPOT_ALERTS = [
  {
    id: "ALT-2026-001",
    cluster_ref: "CLS-DL-8821",
    target_name: "SBI ATM — Connaught Place Inner Circle",
    severity: "CRITICAL" as const,
    status: "open" as const,
    confidence: 0.94,
    window_end: "2026-01-15T11:30:00Z",
    reason: "High confidence cash-out trajectory detected",
  },
  {
    id: "ALT-2026-002",
    cluster_ref: "CLS-MH-1049",
    target_name: "HDFC Bank — Bandra West Branch",
    severity: "HIGH" as const,
    status: "acknowledged" as const,
    confidence: 0.81,
    window_end: "2026-01-15T12:00:00Z",
    reason: "Layer 2 rapid pass-through observation",
  },
  {
    id: "ALT-2026-003",
    cluster_ref: "CLS-HR-3321",
    target_name: "ICICI ATM — Cyber City Hub",
    severity: "MEDIUM" as const,
    status: "open" as const,
    confidence: 0.68,
    window_end: "2026-01-15T12:30:00Z",
    reason: "Novelty probe pattern",
  },
  {
    id: "ALT-2026-004",
    cluster_ref: "CLS-JH-9901",
    target_name: "PNB ATM — Ranchi Central",
    severity: "LOW" as const,
    status: "actioned" as const,
    confidence: 0.42,
    window_end: "2026-01-15T10:30:00Z",
    reason: "Low amount staging attempt",
  },
];

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
      try {
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

        // openapi-fetch client call with generic fallback until OpenAPI types are generated
        const res = await (apiClient.GET as unknown as (path: string, options: unknown) => Promise<{ data?: unknown }>)(
          "/analytics/heatmap",
          { params: { query: queryParams } },
        );

        if (res.data) {
          return res.data as HeatmapResponse;
        }
      } catch {
        // Fall back to fixture store (Sync 4 fallback per DOC 4 C5)
      }

      // Filter fixture cells locally for realistic test and demo environments
      let filteredCells: HeatCell[] = [...FIXTURE_HEATMAP.cells];

      if (debouncedFilters.state) {
        const st = debouncedFilters.state.toUpperCase();
        filteredCells = filteredCells.filter((c) =>
          c.name?.includes(`(${st}`) || c.id.includes(st)
        );
      }

      if (debouncedFilters.min_confidence) {
        filteredCells = filteredCells.filter(
          (c) => c.value >= debouncedFilters.min_confidence!
        );
      }

      const note =
        debouncedFilters.layer === "potential"
          ? "Persistence estimate of recent forecast intensity over the next 72 h"
          : "Real-time active forecast intensity window (p120)";

      return {
        ...FIXTURE_HEATMAP,
        layer: debouncedFilters.layer,
        level: debouncedFilters.level,
        cells: filteredCells,
        legend: {
          ...FIXTURE_HEATMAP.legend,
          note,
        },
      };
    },
    staleTime: 5_000,
  });
}
