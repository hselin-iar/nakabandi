/**
 * useEvaluation.ts — Fixture data + TanStack Query hook for Evaluation Harness.
 * DOC 3 § Evaluation Harness · DOC 4 Step C7
 *
 * STUB STRATEGY (DOC4 C7): hand-written fixture matching the documented
 * endpoint shape. Swap the data source for a real API call when Track B
 * Step B7 (Evaluation Harness) lands.
 *
 * Two runs are provided so the evaluation page can display them side-by-side:
 *   FIXTURE_EVAL_FEEDBACK_OFF — baseline run (feedback loop disabled)
 *   FIXTURE_EVAL_FEEDBACK_ON  — post-feedback run
 */

import { useQuery } from "@tanstack/react-query";
import type { MetricName } from "../../../shared/api/schema.d.ts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MetricRow {
  name: MetricName;
  label: string;
  value: number;
  /** Higher-is-better (true) or lower-is-better (false) */
  higherBetter: boolean;
  /** 0–1 scale for the metric bar; null if not applicable */
  normalised: number | null;
  unit?: string;
}

/** One cold-start checkpoint in the hit-rate curve */
export interface ColdStartPoint {
  /** Complaints ingested before this checkpoint */
  complaints: number;
  /** Hit rate at that checkpoint (0–1) */
  hit_rate: number;
}

export interface EvalRun {
  run_id: string;
  label: string;
  feedback_enabled: boolean;
  completed_at: string;
  /** Metrics for this run */
  metrics: MetricRow[];
  /** Cold-start hit-rate curve (for ColdStartChart) */
  cold_start_curve: ColdStartPoint[];
}

// ---------------------------------------------------------------------------
// Metric metadata (label + direction)
// ---------------------------------------------------------------------------

const META: Record<MetricName, { label: string; higherBetter: boolean; unit?: string }> = {
  hit_rate_at_k:               { label: "Hit Rate @K",              higherBetter: true  },
  precision_at_k:              { label: "Precision @K",             higherBetter: true  },
  lead_time_median:            { label: "Median Lead Time",         higherBetter: true,  unit: "min" },
  brier:                       { label: "Brier Score",              higherBetter: false },
  interceptable_precision:     { label: "Intercept Precision",      higherBetter: true  },
  interceptable_recall:        { label: "Intercept Recall",         higherBetter: true  },
  dispatches_per_interception: { label: "Dispatches / Intercept",   higherBetter: false },
  false_hold_rate:             { label: "False Hold Rate",          higherBetter: false },
  cold_start_hit_rate:         { label: "Cold-Start Hit Rate",      higherBetter: true  },
  abstention_rate:             { label: "Abstention Rate",          higherBetter: false },
};

function row(
  name: MetricName,
  value: number,
  normalised: number | null,
): MetricRow {
  const m = META[name];
  return { name, label: m.label, value, higherBetter: m.higherBetter, normalised, unit: m.unit };
}

// ---------------------------------------------------------------------------
// Fixture A: Feedback OFF (baseline)
// ---------------------------------------------------------------------------

export const FIXTURE_EVAL_FEEDBACK_OFF: EvalRun = {
  run_id: "RUN-2026-NOFB-001",
  label: "Baseline (feedback off)",
  feedback_enabled: false,
  completed_at: "2026-09-10T14:22:00Z",
  metrics: [
    row("hit_rate_at_k",               0.61, 0.61),
    row("precision_at_k",              0.54, 0.54),
    row("lead_time_median",            22,   null),
    row("brier",                       0.18, 0.82),
    row("interceptable_precision",     0.70, 0.70),
    row("interceptable_recall",        0.62, 0.62),
    row("dispatches_per_interception", 2.8,  0.44),
    row("false_hold_rate",             0.09, 0.91),
    row("cold_start_hit_rate",         0.38, 0.38),
    row("abstention_rate",             0.11, 0.89),
  ],
  cold_start_curve: [
    { complaints: 0,   hit_rate: 0.00 },
    { complaints: 5,   hit_rate: 0.12 },
    { complaints: 10,  hit_rate: 0.21 },
    { complaints: 20,  hit_rate: 0.30 },
    { complaints: 50,  hit_rate: 0.38 },
    { complaints: 100, hit_rate: 0.45 },
    { complaints: 200, hit_rate: 0.55 },
    { complaints: 500, hit_rate: 0.61 },
  ],
};

// ---------------------------------------------------------------------------
// Fixture B: Feedback ON (improved)
// ---------------------------------------------------------------------------

export const FIXTURE_EVAL_FEEDBACK_ON: EvalRun = {
  run_id: "RUN-2026-FB-002",
  label: "With feedback loop",
  feedback_enabled: true,
  completed_at: "2026-09-20T10:05:00Z",
  metrics: [
    row("hit_rate_at_k",               0.74, 0.74),
    row("precision_at_k",              0.69, 0.69),
    row("lead_time_median",            27,   null),
    row("brier",                       0.12, 0.88),
    row("interceptable_precision",     0.79, 0.79),
    row("interceptable_recall",        0.71, 0.71),
    row("dispatches_per_interception", 2.1,  0.58),
    row("false_hold_rate",             0.05, 0.95),
    row("cold_start_hit_rate",         0.48, 0.48),
    row("abstention_rate",             0.08, 0.92),
  ],
  cold_start_curve: [
    { complaints: 0,   hit_rate: 0.00 },
    { complaints: 5,   hit_rate: 0.18 },
    { complaints: 10,  hit_rate: 0.28 },
    { complaints: 20,  hit_rate: 0.38 },
    { complaints: 50,  hit_rate: 0.48 },
    { complaints: 100, hit_rate: 0.58 },
    { complaints: 200, hit_rate: 0.66 },
    { complaints: 500, hit_rate: 0.74 },
  ],
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useEvalRuns() {
  return useQuery<EvalRun[]>({
    queryKey: ["eval-runs"],
    queryFn: () =>
      Promise.resolve([FIXTURE_EVAL_FEEDBACK_OFF, FIXTURE_EVAL_FEEDBACK_ON]),
    staleTime: Infinity,
  });
}
