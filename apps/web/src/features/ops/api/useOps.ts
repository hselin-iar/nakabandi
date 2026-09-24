/**
 * useOps.ts — TanStack Query hook for Ops Metrics.
 * DOC 3 §M4 (outbox), DOC 2 §2.7 · DOC 4 Step C7
 *
 * Real backend only: polls GET /system/metrics every 30s. That endpoint is a point-in-time
 * snapshot (no history, no per-channel breakdown, no sim-control state — DOC 4 A11/A12
 * Learnings), so eps_series is built by accumulating each poll's reading client-side (session-
 * local, resets on reload — an honest "since this page opened" series, not fabricated history).
 * channel_health, sim_speed_ratio and auto_paused have no backend source yet and are always
 * empty/absent; OpsPage hides those sections rather than showing fabricated numbers.
 */

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../../shared/api/client";

export interface StageLatency {
  stage: string;
  p50_ms: number;
  p95_ms: number;
}

export interface ChannelHealth {
  channel: "bank_webhook" | "sms" | "email" | "outbox_sms";
  pending: number;
  failed_24h: number;
  delivered_24h: number;
}

export interface EventsPerSecondPoint {
  at: string;
  eps: number;
}

export interface OpsMetrics {
  captured_at: string;
  events_per_second: number;
  eps_series: EventsPerSecondPoint[];
  stage_latencies: StageLatency[];
  outbox_depth: number;
  delivery_failures_24h: number;
  channel_health: ChannelHealth[];
  sim_speed_ratio: number | null;
  auto_paused: boolean;
}

const EPS_HISTORY_MAX = 20;
let epsHistory: EventsPerSecondPoint[] = [];

export function useOpsMetrics() {
  return useQuery<OpsMetrics>({
    queryKey: ["ops-metrics"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/system/metrics");
      if (error) throw new Error("Failed to load system metrics");

      epsHistory = [
        ...epsHistory,
        { at: data.generated_at, eps: data.events_per_second },
      ].slice(-EPS_HISTORY_MAX);

      return {
        captured_at: data.generated_at,
        events_per_second: data.events_per_second,
        eps_series: epsHistory,
        stage_latencies: Object.entries(data.stages).map(([stage, s]) => ({
          stage,
          p50_ms: s.p50_ms,
          p95_ms: s.p95_ms,
        })),
        outbox_depth: data.outbox.pending ?? 0,
        delivery_failures_24h: data.delivery_failures,
        channel_health: [],
        sim_speed_ratio: null,
        auto_paused: false,
      };
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}
