/**
 * fetchEvalResults.ts — reads apps/web/public/eval-results.json (written by scripts/evaluate.py).
 *
 * That script serialises with Python's json.dumps(allow_nan=True), so any metric with too small
 * a sample is written as a bare `NaN` token, which is NOT valid JSON: res.json() / JSON.parse
 * throw SyntaxError on the whole file. The text is therefore sanitised first (NaN and ±Infinity
 * become null) and every metric is exposed as { value: number | null, n }. A null value means
 * "insufficient sample" and must be rendered as such, never as 0 or an empty chart point.
 */

export interface MetricPoint {
  /** null = the script could not compute it (too few samples). */
  value: number | null;
  n: number;
}

export interface EvalReport {
  generated_at: string;
  as_of: string;
  scorer: string;
  metrics: {
    n_complaints: number;
    hit_rate_at_1: MetricPoint;
    hit_rate_at_3: MetricPoint;
    hit_rate_at_5: MetricPoint;
    precision_at_1: MetricPoint;
    precision_at_3: MetricPoint;
    precision_at_5: MetricPoint;
    brier_score: MetricPoint;
  };
}

/** Pure: replace the non-JSON number tokens Python may emit, only where a value is expected. */
export function sanitizeEvalJson(text: string): string {
  return text.replace(/:\s*(-?Infinity|NaN)\b/g, ": null");
}

/** Pure: parse the (possibly non-standard) text of eval-results.json. */
export function parseEvalResults(text: string): EvalReport {
  return JSON.parse(sanitizeEvalJson(text)) as EvalReport;
}

/** null when the script has never been run (file absent); throws on a genuinely corrupt file. */
export async function fetchEvalResults(): Promise<EvalReport | null> {
  const res = await fetch("/eval-results.json", { cache: "no-store" });
  if (!res.ok) return null;
  return parseEvalResults(await res.text());
}
