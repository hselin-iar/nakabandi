/**
 * useOps.ts — Fixture data + TanStack Query hook for Ops Metrics.
 * DOC 3 §M4 (outbox), DOC 2 §2.7 · DOC 4 Step C7
 *
 * STUB STRATEGY: fixture matching the documented endpoint shape.
 * Swap for a real poll of /ops/metrics when Track A Step A11 lands.
 */

import { useQuery } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** One pipeline stage's latency snapshot */
export interface StageLatency {
  stage: string;
  p50_ms: number;
  p95_ms: number;
}

/** Outbox delivery channel health */
export interface ChannelHealth {
  channel: "bank_webhook" | "sms" | "email" | "outbox_sms";
  pending: number;
  failed_24h: number;
  delivered_24h: number;
}

/** Point on the events/s time series */
export interface EventsPerSecondPoint {
  /** ISO-8601 timestamp */
  at: string;
  eps: number;
}

export interface OpsMetrics {
  captured_at: string;
  events_per_second: number;
  /** Last 20 samples (1 per minute) */
  eps_series: EventsPerSecondPoint[];
  stage_latencies: StageLatency[];
  outbox_depth: number;
  delivery_failures_24h: number;
  channel_health: ChannelHealth[];
  /** Simulator sim-time vs wall-time ratio */
  sim_speed_ratio: number;
  /** Whether auto-pause is active */
  auto_paused: boolean;
}

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

function tsAt(minutesAgo: number): string {
  const d = new Date("2026-09-24T03:00:00Z");
  d.setMinutes(d.getMinutes() - minutesAgo);
  return d.toISOString();
}

export const FIXTURE_OPS_METRICS: OpsMetrics = {
  captured_at: "2026-09-24T03:00:00Z",
  events_per_second: 47.3,
  eps_series: Array.from({ length: 20 }, (_, i) => ({
    at: tsAt(19 - i),
    eps: 30 + Math.round(Math.sin(i * 0.6) * 12 + (i > 12 ? 10 : 0)),
  })),
  stage_latencies: [
    { stage: "ingest",        p50_ms:  3, p95_ms:  12 },
    { stage: "graph_resolve", p50_ms: 14, p95_ms:  42 },
    { stage: "forecast",      p50_ms: 38, p95_ms: 110 },
    { stage: "interception",  p50_ms:  8, p95_ms:  28 },
    { stage: "alerting",      p50_ms:  5, p95_ms:  16 },
    { stage: "outbox",        p50_ms:  2, p95_ms:   7 },
  ],
  outbox_depth: 12,
  delivery_failures_24h: 2,
  channel_health: [
    { channel: "bank_webhook", pending: 3,  failed_24h: 1, delivered_24h: 87  },
    { channel: "sms",          pending: 8,  failed_24h: 1, delivered_24h: 124 },
    { channel: "email",        pending: 1,  failed_24h: 0, delivered_24h: 34  },
    { channel: "outbox_sms",   pending: 0,  failed_24h: 0, delivered_24h: 11  },
  ],
  sim_speed_ratio: 6.0,
  auto_paused: false,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useOpsMetrics() {
  return useQuery<OpsMetrics>({
    queryKey: ["ops-metrics"],
    queryFn: () => Promise.resolve(FIXTURE_OPS_METRICS),
    /**
     * Refetch every 30 s so the page feels live even against the fixture.
     * Swap for a real /ops/metrics poll when Track A A11 lands.
     */
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}
