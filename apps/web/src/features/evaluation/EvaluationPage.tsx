/**
 * EvaluationPage.tsx — Evaluation Harness results: real metrics from scripts/evaluate.py.
 * DOC 3 §Evaluation Harness, §S3, §S4 · DOC 4 Step C7
 *
 * Shows exactly what scripts/evaluate.py computed (hit_rate@k, precision@k, brier_score) against
 * the trained model's real candidate rankings and real oracle truth — nothing invented for
 * metrics that would need data this environment doesn't have yet (see useEvaluation.ts).
 */

import React from "react";
import { useEvalReport } from "./api/useEvaluation";
import type { EvalReport, MetricPoint } from "./api/useEvaluation";
import { ProgressRing } from "../../shared/ui/ProgressRing";

// ---------------------------------------------------------------------------
// MetricsTable
// ---------------------------------------------------------------------------

const METRIC_ROWS: { key: keyof EvalReport["metrics"]; label: string; higherBetter: boolean }[] = [
  { key: "hit_rate_at_1", label: "Hit Rate @1", higherBetter: true },
  { key: "hit_rate_at_3", label: "Hit Rate @3", higherBetter: true },
  { key: "hit_rate_at_5", label: "Hit Rate @5", higherBetter: true },
  { key: "precision_at_1", label: "Precision @1", higherBetter: true },
  { key: "precision_at_3", label: "Precision @3", higherBetter: true },
  { key: "precision_at_5", label: "Precision @5", higherBetter: true },
  { key: "brier_score", label: "Brier Score", higherBetter: false },
];

function MetricsTable({ report }: { report: EvalReport }) {
  return (
    <div className="nk-eval-table-wrapper" data-testid="eval-metrics-table">
      <table className="nk-table nk-eval-table">
        <caption className="nk-table__caption">Evaluation metrics</caption>
        <thead>
          <tr>
            <th className="nk-table__th">Metric</th>
            <th className="nk-table__th nk-table__th--right">Value</th>
            <th className="nk-table__th nk-table__th--right">Sample size (n)</th>
          </tr>
        </thead>
        <tbody>
          {METRIC_ROWS.map(({ key, label }) => {
            const m = report.metrics[key] as MetricPoint;
            return (
              <tr key={key} className="nk-table__row" data-testid={`eval-row-${key}`}>
                <td className="nk-table__td">
                  <span className="nk-eval-metric-name">{label}</span>
                </td>
                <td className="nk-table__td nk-table__td--right nk-eval-value data-digit">
                  {m.value === null
                    ? "insufficient sample"
                    : key === "brier_score"
                      ? m.value.toFixed(4)
                      : `${(m.value * 100).toFixed(1)}%`}
                </td>
                <td className="nk-table__td nk-table__td--right nk-eval-value data-digit">{m.n}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EvaluationPage
// ---------------------------------------------------------------------------

export default function EvaluationPage() {
  const { data: report, isLoading, error } = useEvalReport();

  if (isLoading) {
    return (
      <div className="nk-page-loading" aria-live="polite">
        Loading evaluation results…
      </div>
    );
  }

  if (error) {
    return (
      <div className="nk-error-state" role="alert">
        <span className="nk-error-state__icon" aria-hidden="true">⚠</span>
        <p className="nk-error-state__message">Could not load evaluation run data. Please retry.</p>
      </div>
    );
  }

  return (
    <main className="nk-eval-page" data-testid="eval-page">
      <header className="nk-eval-page__header">
        <h1 className="nk-eval-page__title">Evaluation Harness</h1>
        <p className="nk-eval-page__subtitle">
          Model performance against the ground-truth oracle.
          Numbers are computed by scripts/evaluate.py — not the production API, which may never
          touch the oracle (hidden-truth firewall).
        </p>
      </header>

      {!report ? (
        <div className="nk-empty-state" data-testid="eval-empty-state">
          <p>
            No evaluation run yet. Run <code>uv run python scripts/evaluate.py</code> against a
            trained model, then reload this page.
          </p>
        </div>
      ) : (
        <>
          <div
            className="nk-eval-hero-strip"
            aria-label="Headline model performance metrics"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--nk-space-6)",
              flexWrap: "wrap",
              background: "var(--nk-surface-raised)",
              border: "1px solid var(--nk-border-subtle)",
              borderRadius: "var(--nk-radius-lg)",
              padding: "var(--nk-space-5) var(--nk-space-6)",
              marginBottom: "var(--nk-space-5)",
              boxShadow: "var(--nk-shadow-md)",
            }}
          >
            <ProgressRing
              value={report.metrics.hit_rate_at_5.value}
              n={report.metrics.hit_rate_at_5.n}
              label="Hit Rate @5"
            />
            <div style={{ width: 1, height: 72, background: "var(--nk-border-subtle)", flexShrink: 0 }} />
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--nk-text-secondary)" }}>
                Scorer
              </span>
              <span style={{ fontSize: 20, fontWeight: 700, color: "var(--nk-text-primary)" }}>
                {report.scorer}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--nk-text-secondary)" }}>
                Complaints scored
              </span>
              <span style={{ fontSize: 20, fontWeight: 700, color: "var(--nk-text-primary)" }}>
                {report.metrics.n_complaints}
              </span>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
              <span style={{ fontSize: 11, color: "var(--nk-text-secondary)" }}>
                As of {new Date(report.as_of).toLocaleString("en-IN")}
              </span>
              <span style={{ fontSize: 11, color: "var(--nk-text-secondary)" }}>
                Generated {new Date(report.generated_at).toLocaleString("en-IN")}
              </span>
            </div>
          </div>

          <section className="nk-eval-section" aria-label="Metrics">
            <MetricsTable report={report} />
          </section>
        </>
      )}
    </main>
  );
}
