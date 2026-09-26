/**
 * useSystemHud.ts — data for the System Integrity overview, all from endpoints that exist:
 *   GET /system/metrics        latency + throughput snapshot (no history: buffered client-side)
 *   GET /audit/verify          the SHA-256 audit hash-chain check
 *   GET /analytics/live-metrics exposure tiles
 * Latency "history" is a rolling buffer of the last polls kept in component state; the backend
 * keeps no time series, so this is honestly "since this page opened", not stored history.
 */

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../../shared/api/client";
import { verifyChain } from "../../audit/api/useAudit";

export const HUD_POLL_MS = 10_000;
export const HUD_BUFFER_MAX = 30;

export interface MetricsSample {
  at: string;
  eps: number;
  httpP95: number;
  /** stage name -> p95 ms (dynamic keys: index defensively). */
  stageP95: Record<string, number>;
  outboxPending: number;
  deliveryFailures: number;
  uptimeS: number;
  httpP50: number;
  httpMax: number;
}

/** Pure: append a sample, capped to the newest `max`. */
export function pushSample(buffer: readonly MetricsSample[], sample: MetricsSample, max = HUD_BUFFER_MAX): MetricsSample[] {
  return [...buffer, sample].slice(-max);
}

export function useMetricsBuffer(enabled: boolean) {
  const [buffer, setBuffer] = useState<MetricsSample[]>([]);
  const lastAt = useRef<string | null>(null);

  const query = useQuery({
    queryKey: ["hud-metrics"],
    enabled,
    refetchInterval: HUD_POLL_MS,
    staleTime: HUD_POLL_MS / 2,
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/system/metrics");
      if (error) throw new Error("Failed to load system metrics");
      return data;
    },
  });

  const data = query.data;
  useEffect(() => {
    if (!data || lastAt.current === data.generated_at) return;
    lastAt.current = data.generated_at;
    setBuffer((b) =>
      pushSample(b, {
        at: data.generated_at,
        eps: data.events_per_second,
        httpP95: data.http.p95_ms,
        httpP50: data.http.p50_ms,
        httpMax: data.http.max_ms,
        stageP95: Object.fromEntries(Object.entries(data.stages).map(([k, v]) => [k, v.p95_ms])),
        outboxPending: data.outbox.pending ?? 0,
        deliveryFailures: data.delivery_failures,
        uptimeS: data.uptime_s,
      }),
    );
  }, [data]);

  return { buffer, isError: query.isError, isLoading: query.isLoading };
}

export function useAuditVerify(enabled: boolean) {
  return useQuery({
    queryKey: ["hud-audit-verify"],
    enabled,
    queryFn: verifyChain,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useHudLiveMetrics(enabled: boolean) {
  return useQuery({
    queryKey: ["hud-live-metrics"],
    enabled,
    refetchInterval: 30_000,
    staleTime: 15_000,
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/analytics/live-metrics");
      if (error) throw new Error("Failed to load live metrics");
      return data;
    },
  });
}

// ---------------------------------------------------------------------------
// Brier trend: the backend keeps no run history, so remember the last few runs locally
// ---------------------------------------------------------------------------

const BRIER_KEY = "nk.eval.brier";
export interface BrierRun {
  generated_at: string;
  brier: number;
}

/** Pure: add a run to the history (deduped by generated_at, capped), newest last. */
export function recordRun(history: readonly BrierRun[], run: BrierRun, max = 10): BrierRun[] {
  if (history.some((h) => h.generated_at === run.generated_at)) return [...history];
  return [...history, run].slice(-max);
}

/** Pure: lower Brier is better. */
export function brierTrend(history: readonly BrierRun[]): "better" | "worse" | "same" | null {
  if (history.length < 2) return null;
  const prev = history[history.length - 2]!.brier;
  const cur = history[history.length - 1]!.brier;
  if (Math.abs(cur - prev) < 1e-9) return "same";
  return cur < prev ? "better" : "worse";
}

export function loadBrierHistory(): BrierRun[] {
  try {
    const raw = window.localStorage.getItem(BRIER_KEY);
    const parsed = raw ? (JSON.parse(raw) as BrierRun[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveBrierHistory(h: readonly BrierRun[]): void {
  try {
    window.localStorage.setItem(BRIER_KEY, JSON.stringify(h));
  } catch {
    /* not remembered */
  }
}
