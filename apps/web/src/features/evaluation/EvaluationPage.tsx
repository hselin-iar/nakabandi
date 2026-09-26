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

// ---------------------------------------------------------------------------
// ProgressRing — animated SVG arc showing a 0-1 score as a ring
// ---------------------------------------------------------------------------

function ProgressRing({
  value,
  size = 96,
  strokeWidth = 8,
  label,
  color,
}: {
  value: number;
  size?: number;
  strokeWidth?: number;
  label: string;
  color: string;
}) {
  const r = (size - strokeWidth) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - Math.max(0, Math.min(1, value)));
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="var(--nk-border-subtle)" strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 0.8s ease" }}
        />
        <text
          x="50%" y="50%" dominantBaseline="middle" textAnchor="middle"
          fill="var(--nk-text-primary)" fontSize={size * 0.22} fontWeight={700}
          fontFamily="var(--nk-font-sans)"
        >
          {(value * 100).toFixed(1)}%
        </text>
      </svg>
      <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--nk-text-muted)" }}>
        {label}
      </span>
    </div>
  );
}

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
                <td className="nk-table__td nk-table__td--right nk-eval-value">
                  {key === "brier_score" ? m.value.toFixed(4) : `${(m.value * 100).toFixed(1)}%`}
                </td>
                <td className="nk-table__td nk-table__td--right nk-eval-value">{m.n}</td>
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
              label="Hit Rate @5"
              color={
                report.metrics.hit_rate_at_5.value >= 0.3
                  ? "#22c55e"
                  : report.metrics.hit_rate_at_5.value >= 0.1
                    ? "#f59e0b"
                    : "#ef4444"
              }
            />
            <div style={{ width: 1, height: 72, background: "var(--nk-border-subtle)", flexShrink: 0 }} />
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--nk-text-muted)" }}>
                Scorer
              </span>
              <span style={{ fontSize: 20, fontWeight: 700, color: "var(--nk-text-primary)" }}>
                {report.scorer}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--nk-text-muted)" }}>
                Complaints scored
              </span>
              <span style={{ fontSize: 20, fontWeight: 700, color: "var(--nk-text-primary)" }}>
                {report.metrics.n_complaints}
              </span>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
              <span style={{ fontSize: 11, color: "var(--nk-text-muted)" }}>
                As of {new Date(report.as_of).toLocaleString("en-IN")}
              </span>
              <span style={{ fontSize: 11, color: "var(--nk-text-muted)" }}>
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
