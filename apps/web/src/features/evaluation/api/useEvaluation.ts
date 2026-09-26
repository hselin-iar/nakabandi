/**
 * useEvaluation.ts — TanStack Query hook for the Evaluation Harness.
 * DOC 3 § Evaluation Harness · DOC 4 Step C7
 *
 * Reads apps/web/public/eval-results.json, written by scripts/evaluate.py — an offline script
 * (never the live API process, which may never import nakabandi.evaluation or touch world-sim's
 * oracle) that scores the trained model's real candidate rankings against real resolved
 * complaints and real oracle truth. No fixture, no live REST endpoint (the hidden-truth
 * firewall forbids main.py from ever importing evaluation, so there can't be one in-process);
 * re-run scripts/evaluate.py and refresh the page to see updated numbers.
 *
 * Only the metrics scripts/evaluate.py actually computes are modelled here (hit_rate@k,
 * precision@k, brier_score). Richer metrics some earlier iteration of this page assumed
 * (interceptable_precision/recall, dispatches_per_interception, false_hold_rate, a cold-start
 * curve, a feedback-on/off comparison) need real interception/outcome history and a second
 * trained model this environment doesn't have yet — showing them would mean inventing numbers,
 * so they're left out rather than faked.
 */

import { useQuery } from "@tanstack/react-query";
import { fetchEvalResults } from "../../../shared/api/fetchEvalResults";
import type { EvalReport, MetricPoint } from "../../../shared/api/fetchEvalResults";

export type { EvalReport, MetricPoint };

export function useEvalReport() {
  return useQuery<EvalReport | null>({
    queryKey: ["eval-report"],
    // null when scripts/evaluate.py has never been run: an honest empty state, not a fixture.
    // The file can contain bare NaN (Python allow_nan), which fetchEvalResults sanitises.
    queryFn: fetchEvalResults,
    staleTime: 60_000,
  });
}
