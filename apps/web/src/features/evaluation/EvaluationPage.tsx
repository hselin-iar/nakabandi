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
// ProgressRing — animated SVG arc showing a 0-1 score as a ring
// ---------------------------------------------------------------------------

function ProgressRing({
  value,
  size = 80,
  strokeWidth = 7,
  label,
  color = "var(--nk-brand-primary)",
}: {
  value: number;
  size?: number;
  strokeWidth?: number;
  label: string;
  color?: string;
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
          {(value * 100).toFixed(0)}%
        </text>
      </svg>
      <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--nk-text-muted)" }}>
        {label}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// HeroScoreStrip — headline metrics displayed prominently above the table
// ---------------------------------------------------------------------------

function HeroScoreStrip({ run }: { run: EvalRun }) {
  function get(name: string) {
    return run.metrics.find((m) => m.name === name)?.value ?? null;
  }
  const f1        = get("interceptable_f1")       ?? get("f1_at_k")            ?? get("hit_rate_at_k");
  const precision = get("interceptable_precision") ?? get("precision_at_k");
  const recall    = get("interceptable_recall")    ?? get("recall_at_k");
  const hitRate   = get("hit_rate_at_k");
  const latency   = get("median_latency_s")        ?? get("latency_p50_s");

  if (f1 === null) return null;

  return (
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
      {/* F1 ring */}
      <ProgressRing value={f1} size={96} strokeWidth={8} label="F1 Score"
        color={f1 >= 0.7 ? "#22c55e" : f1 >= 0.5 ? "#f59e0b" : "#ef4444"} />

      <div style={{ width: 1, height: 72, background: "var(--nk-border-subtle)", flexShrink: 0 }} />

      {/* Supporting metric pills */}
      <div style={{ display: "flex", gap: "var(--nk-space-4)", flexWrap: "wrap", flex: 1 }}>
        {[
          { label: "Precision",  value: precision, color: "var(--nk-brand-primary)" },
          { label: "Recall",     value: recall,    color: "#a78bfa" },
          { label: "Hit Rate",   value: hitRate,   color: "#22d3ee" },
        ].map(({ label, value, color }) =>
          value !== null ? (
            <div key={label} style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 100 }}>
              <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--nk-text-muted)" }}>
                {label}
              </span>
              <span style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
                {(value * 100).toFixed(1)}%
              </span>
            </div>
          ) : null
        )}

        {latency !== null && (
          <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 100 }}>
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--nk-text-muted)" }}>
              Median Latency
            </span>
            <span style={{ fontSize: 28, fontWeight: 700, color: "#f59e0b", lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
              {latency.toFixed(2)}s
            </span>
          </div>
        )}
      </div>

      {/* Run label + feedback indicator */}
      <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--nk-text-primary)" }}>{run.label}</span>
        <span style={{
          fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 999,
          background: run.feedback_enabled ? "rgba(34,197,94,0.12)" : "rgba(148,163,184,0.1)",
          color: run.feedback_enabled ? "#22c55e" : "var(--nk-text-muted)",
          border: `1px solid ${run.feedback_enabled ? "rgba(34,197,94,0.3)" : "rgba(148,163,184,0.2)"}`,
        }}>
          {run.feedback_enabled ? "✓ Feedback on" : "Feedback off"}
        </span>
      </div>
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

      {/* Hero Score Strip — primary run */}
      <HeroScoreStrip run={runA} />

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
