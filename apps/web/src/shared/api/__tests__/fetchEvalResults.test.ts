import { describe, it, expect } from "vitest";
import { parseEvalResults, sanitizeEvalJson } from "../fetchEvalResults";

// Exactly the shape scripts/evaluate.py writes when a metric's sample is too small.
const WITH_NAN = `{
  "generated_at": "2026-09-26T09:09:42+00:00",
  "as_of": "2026-01-17T10:15:38+00:00",
  "scorer": "hgb_v1",
  "metrics": {
    "n_complaints": 17,
    "hit_rate_at_1": { "value": NaN, "n": 17 },
    "precision_at_1": { "value": Infinity, "n": 17 },
    "hit_rate_at_3": { "value": -Infinity, "n": 17 },
    "precision_at_3": { "value": NaN, "n": 17 },
    "hit_rate_at_5": { "value": NaN, "n": 17 },
    "precision_at_5": { "value": NaN, "n": 17 },
    "brier_score": { "value": 0.0082, "n": 2047 }
  }
}`;

describe("eval-results.json parsing", () => {
  it("is not valid JSON as written (the landmine)", () => {
    expect(() => JSON.parse(WITH_NAN)).toThrow(SyntaxError);
  });

  it("turns NaN / ±Infinity into null instead of throwing, and keeps real numbers and n", () => {
    const r = parseEvalResults(WITH_NAN);
    expect(r.metrics.hit_rate_at_1).toEqual({ value: null, n: 17 });
    expect(r.metrics.precision_at_1.value).toBeNull();
    expect(r.metrics.hit_rate_at_3.value).toBeNull();
    expect(r.metrics.brier_score).toEqual({ value: 0.0082, n: 2047 });
    expect(r.metrics.n_complaints).toBe(17);
  });

  it("leaves a clean file untouched", () => {
    const clean = '{"a": {"value": 0.5, "n": 40}}';
    expect(sanitizeEvalJson(clean)).toBe(clean);
  });

  it("does not rewrite the word NaN inside a string value", () => {
    const text = '{"scorer": "NaN-tolerant model", "metrics": {}}';
    expect(parseEvalResults(text).scorer).toBe("NaN-tolerant model");
  });
});
