/**
 * ColdStartChart.tsx — Bar chart showing cold-start hit rate vs complaint count.
 * DOC 1 §S4 · DOC 4 Step C7
 *
 * Uses Recharts (approved stack, DOC 2 §2.2).
 * Displays one or two runs side-by-side (feedback-off vs feedback-on).
 * Never computes numbers itself — data comes from the API / fixture.
 */

import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { EvalRun, ColdStartPoint } from "./api/useEvaluation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChartDatum {
  complaints: number;
  [runLabel: string]: number;
}

interface ColdStartChartProps {
  /** 1 or 2 runs (feedback-off + feedback-on comparison) */
  runs: EvalRun[];
}

// ---------------------------------------------------------------------------
// Colour palette — derived from brand tokens (CSS not available in Recharts)
// ---------------------------------------------------------------------------

const PALETTE = ["#6366f1", "#22d3ee"];

// ---------------------------------------------------------------------------
// ColdStartChart
// ---------------------------------------------------------------------------

export function ColdStartChart({ runs }: ColdStartChartProps) {
  if (!runs.length) return null;

  // Merge all runs into a single array keyed by complaint count
  const complaintSet = new Set<number>();
  for (const run of runs) {
    for (const pt of run.cold_start_curve) {
      complaintSet.add(pt.complaints);
    }
  }
  const sortedComplaints = Array.from(complaintSet).sort((a, b) => a - b);

  const data: ChartDatum[] = sortedComplaints.map((c) => {
    const datum: ChartDatum = { complaints: c };
    for (const run of runs) {
      const pt = run.cold_start_curve.find(
        (p: ColdStartPoint) => p.complaints === c,
      );
      datum[run.label] = pt ? parseFloat((pt.hit_rate * 100).toFixed(1)) : 0;
    }
    return datum;
  });

  return (
    <div
      className="nk-cold-start-chart"
      role="img"
      aria-label="Cold-start hit rate by complaints ingested"
    >
      <h3 className="nk-cold-start-chart__title">
        Cold-Start Hit Rate by Complaints Ingested
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--nk-border-subtle)" />
          <XAxis
            dataKey="complaints"
            label={{ value: "Complaints Ingested", position: "insideBottom", offset: -2, fill: "var(--nk-text-secondary)", fontSize: 12 }}
            tick={{ fill: "var(--nk-text-secondary)", fontSize: 11 }}
            height={40}
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
          <Legend
            wrapperStyle={{ fontSize: 12, color: "var(--nk-text-secondary)" }}
          />
          {runs.map((run, i) =>
            runs.length === 1 ? (
              <Bar
                key={run.run_id}
                dataKey={run.label}
                fill={PALETTE[i % PALETTE.length]}
                radius={[3, 3, 0, 0]}
              />
            ) : (
              <Line
                key={run.run_id}
                type="monotone"
                dataKey={run.label}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            ),
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
