/**
 * useAnalytics.ts — TanStack Query hooks for GET /analytics/live-metrics and
 * GET /analytics/timeseries. Both are implemented and unused by the frontend today
 * (Frontend Strategy §1.2.4 / §1.3): the Command dashboard instead re-derives its KPI
 * numbers and trend sparkline client-side from cached /alerts and /analytics/heatmap
 * responses, computed by a different method than the analytics module's own canonical
 * one. Wiring these directly removes that discrepancy.
 *
 * No SSE event exists for these two endpoints (streamKeys.ts's SSE_EVENTS), so both
 * hooks poll on a short interval instead of stream-driven invalidation.
 */

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../../shared/api/client";

type AnalyticsLayer = "live" | "potential";

export interface LiveMetrics {
  generated_at: string;
  version: number;
  window_hours: number;
  alert_count: number;
  expected_mass: number;
  active_locations: number;
}

export interface TimePoint {
  hour: string;
  value: number;
  alert_count: number;
}

export interface Timeseries {
  layer: string;
  from_: string;
  to: string;
  version: number;
  points: TimePoint[];
}

/** useLiveMetrics — GET /analytics/live-metrics: expected_mass, alert_count, active_locations. */
export function useLiveMetrics() {
  return useQuery<LiveMetrics>({
    queryKey: ["analytics", "live-metrics"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/analytics/live-metrics");
      if (error) throw new Error("Failed to load live metrics");
      return data;
    },
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

/** useTimeseries — GET /analytics/timeseries: hourly risk trend, real (not client-fabricated). */
export function useTimeseries(layer: AnalyticsLayer = "live") {
  return useQuery<Timeseries>({
    queryKey: ["analytics", "timeseries", layer],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/analytics/timeseries", {
        params: { query: { layer } },
      });
      if (error) throw new Error("Failed to load timeseries");
      return data;
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
