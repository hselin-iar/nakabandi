/**
 * EvaluationPage.tsx — Evaluation Harness results: metrics table + charts.
 * DOC 3 §Evaluation Harness, §S3, §S4 · DOC 4 Step C7
 *
 * Displays:
 *   1. Run selector (feedback-off vs feedback-on)
 *   2. Side-by-side comparison toggle
 *   3. Metrics table with metric bars (values from the API, never recomputed)
 *   4. ColdStartChart
 *   5. Before/after feedback plot (S3)
 */

import React, { useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { useEvalRuns } from "./api/useEvaluation";
import type { EvalRun, MetricRow } from "./api/useEvaluation";
import { ColdStartChart } from "./ColdStartChart";


// ---------------------------------------------------------------------------
// MetricBar
// ---------------------------------------------------------------------------

function MetricBar({ normalised, higherBetter }: { normalised: number; higherBetter: boolean }) {
  const good = higherBetter ? normalised > 0.6 : normalised > 0.6;
  const colorClass = good
    ? "nk-metric-bar__fill--good"
    : normalised > 0.4
    ? "nk-metric-bar__fill--warn"
    : "nk-metric-bar__fill--bad";
  return (
    <div className="nk-metric-bar" role="presentation">
      <div
        className={`nk-metric-bar__fill ${colorClass}`}
        style={{ width: `${Math.round(normalised * 100)}%` }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// MetricsTable
// ---------------------------------------------------------------------------

function MetricsTable({ runs }: { runs: EvalRun[] }) {
  const firstRun = runs[0];
  const secondRun = runs[1] as EvalRun | undefined;

  return (
    <div className="nk-eval-table-wrapper" data-testid="eval-metrics-table">
      <table className="nk-table nk-eval-table">
        <caption className="nk-table__caption">Evaluation metrics</caption>
        <thead>
          <tr>
            <th className="nk-table__th">Metric</th>
            <th className="nk-table__th nk-table__th--right">{firstRun.label}</th>
            {secondRun && (
              <th className="nk-table__th nk-table__th--right">{secondRun.label}</th>
            )}
            <th className="nk-table__th">Distribution</th>
            <th className="nk-table__th nk-table__th--center">↕</th>
          </tr>
        </thead>
        <tbody>
          {firstRun.metrics.map((m: MetricRow) => {
            const m2 = secondRun?.metrics.find((x) => x.name === m.name);
            const delta = m2 ? m2.value - m.value : null;
            const deltaGood =
              delta === null
                ? null
                : m.higherBetter
                ? delta > 0
                : delta < 0;
            return (
              <tr key={m.name} className="nk-table__row" data-testid={`eval-row-${m.name}`}>
                <td className="nk-table__td">
                  <span className="nk-eval-metric-name">{m.label}</span>
                </td>
                <td className="nk-table__td nk-table__td--right nk-eval-value">
                  {m.unit
                    ? `${m.value} ${m.unit}`
                    : m.value < 1
                    ? (m.value * 100).toFixed(1) + "%"
                    : m.value.toFixed(1)}
                </td>
                {m2 && (
                  <td className="nk-table__td nk-table__td--right nk-eval-value">
                    {m2.unit
                      ? `${m2.value} ${m2.unit}`
                      : m2.value < 1
                      ? (m2.value * 100).toFixed(1) + "%"
                      : m2.value.toFixed(1)}
                  </td>
                )}
                <td className="nk-table__td">
                  {m.normalised !== null && (
                    <MetricBar
                      normalised={m2?.normalised ?? m.normalised}
                      higherBetter={m.higherBetter}
                    />
                  )}
                </td>
                <td className="nk-table__td nk-table__td--center">
                  {delta !== null && (
                    <span
                      className={`nk-eval-delta ${
                        deltaGood
                          ? "nk-eval-delta--good"
                          : delta === 0
                          ? ""
                          : "nk-eval-delta--bad"
                      }`}
                      aria-label={`Change: ${delta > 0 ? "+" : ""}${
                        m.value < 1
                          ? (delta * 100).toFixed(1) + "%"
                          : delta.toFixed(2)
                      }`}
                    >
                      {delta > 0 ? "▲" : delta < 0 ? "▼" : "—"}
                      {" "}
                      {m.value < 1
                        ? Math.abs(delta * 100).toFixed(1) + "%"
                        : Math.abs(delta).toFixed(2)}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Before/after feedback plot (S3)
// ---------------------------------------------------------------------------

function FeedbackPlot({ runs }: { runs: EvalRun[] }) {
  const SHOW_METRICS = [
    "hit_rate_at_k",
    "precision_at_k",
    "interceptable_precision",
    "interceptable_recall",
    "false_hold_rate",
  ] as const;

  const data = SHOW_METRICS.map((name) => {
    const datum: Record<string, string | number> = { metric: "" };
    for (const run of runs) {
      const m = run.metrics.find((x) => x.name === name);
      if (m) {
        datum["metric"] = m.label;
        datum[run.label] = parseFloat(
          (m.value < 1 ? m.value * 100 : m.value).toFixed(1),
        );
      }
    }
    return datum;
  });

  return (
    <div
      className="nk-feedback-plot"
      role="img"
      aria-label="Before/after feedback comparison"
      data-testid="eval-feedback-plot"
    >
      <h3 className="nk-feedback-plot__title">Before / After Feedback Loop (S3)</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 8, right: 24, bottom: 32, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--nk-border-subtle)" />
          <XAxis
            dataKey="metric"
            tick={{ fill: "var(--nk-text-secondary)", fontSize: 10 }}
            angle={-15}
            textAnchor="end"
            interval={0}
            height={50}
          />
          <YAxis
            unit="%"
            domain={[0, 100]}
            tick={{ fill: "var(--nk-text-secondary)", fontSize: 11 }}
            width={44}
          />
          <Tooltip
            formatter={(v, name) => [`${Number(v ?? 0).toFixed(1)}%`, String(name)]}
            contentStyle={{
              background: "var(--nk-surface-raised)",
              border: "1px solid var(--nk-border-subtle)",
              color: "var(--nk-text-primary)",
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--nk-text-secondary)" }} />
          {runs.map((run, i) => (
            <Bar
              key={run.run_id}
              dataKey={run.label}
              fill={i === 0 ? "#6366f1" : "#22d3ee"}
              radius={[3, 3, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EvaluationPage
// ---------------------------------------------------------------------------

export default function EvaluationPage() {
  const { data: runs, isLoading, error } = useEvalRuns();
  const [compareMode, setCompareMode] = useState(false);

  if (isLoading) {
    return (
      <div className="nk-page-loading" aria-live="polite">
        Loading evaluation results…
      </div>
    );
  }

  if (error || !runs?.length) {
    return (
      <div className="nk-error-state" role="alert">
        <span className="nk-error-state__icon" aria-hidden="true">⚠</span>
        <p className="nk-error-state__message">Could not load evaluation run data. Please retry.</p>
      </div>
    );
  }

  const [runA, runB] = runs;
  const displayRuns = compareMode && runB ? [runA, runB] : [runA];

  return (
    <main className="nk-eval-page" data-testid="eval-page">
      <header className="nk-eval-page__header">
        <h1 className="nk-eval-page__title">Evaluation Harness</h1>
        <p className="nk-eval-page__subtitle">
          Model performance against the ground-truth oracle.
          Numbers are computed by the evaluation harness — not the production API.
        </p>
      </header>

      {/* Run selector */}
      <div className="nk-eval-controls" data-testid="eval-controls">
        <div className="nk-eval-run-pills">
          {runs.map((run, i) => (
            <span key={run.run_id} className="nk-eval-run-pill" data-testid={`eval-run-pill-${i}`}>
              <span
                className={`nk-eval-run-swatch nk-eval-run-swatch--${i === 0 ? "a" : "b"}`}
              />
              <span data-testid={`eval-run-label-${i}`}>{run.label}</span>
              {run.feedback_enabled ? (
                <span className="nk-eval-run-tag nk-eval-run-tag--fb">FB on</span>
              ) : (
                <span className="nk-eval-run-tag nk-eval-run-tag--nofb">FB off</span>
              )}
              <span className="nk-eval-run-date">
                {new Date(run.completed_at).toLocaleDateString("en-IN")}
              </span>
            </span>
          ))}
        </div>

        {runB && (
          <label className="nk-eval-compare-toggle" htmlFor="eval-compare-toggle">
            <input
              id="eval-compare-toggle"
              type="checkbox"
              className="nk-checkbox"
              checked={compareMode}
              onChange={(e) => setCompareMode(e.target.checked)}
            />
            Compare runs side by side
          </label>
        )}
      </div>

      {/* Metrics table */}
      <section className="nk-eval-section" aria-label="Metrics">
        <MetricsTable runs={displayRuns} />
      </section>

      {/* Cold-start chart */}
      <section className="nk-eval-section" aria-label="Cold-start performance">
        <ColdStartChart runs={displayRuns} />
      </section>

      {/* Before/after feedback plot — only shown in compare mode */}
      {compareMode && runB && (
        <section className="nk-eval-section" aria-label="Feedback comparison">
          <FeedbackPlot runs={[runA, runB]} />
        </section>
      )}
    </main>
  );
}
