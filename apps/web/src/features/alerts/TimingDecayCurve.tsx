/**
 * TimingDecayCurve.tsx — turns three point-probabilities (p30/p60/p120) into a shape.
 * Frontend Strategy §7.2: "a shape communicates 'climbing fast' or 'already flat' in a way
 * three numbers in a row do not." Recharts (approved stack, DOC 2 §2.2) — no new dependency.
 */

import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import type { TimingForecastModel } from "../../shared/api/types.ts";

interface TimingDecayCurveProps {
  timing: TimingForecastModel;
}

export function TimingDecayCurve({ timing }: TimingDecayCurveProps) {
  const data = [
    { minute: 0, prob: 0 },
    { minute: 30, prob: timing.p30 },
    { minute: 60, prob: timing.p60 },
    { minute: 120, prob: timing.p120 },
  ];

  return (
    <div className="nk-timing-curve" role="img" aria-label="Cumulative cash-out probability over time">
      <p className="nk-timing-curve__caption nk-text-xs text-muted">
        {timing.elapsed_min.toFixed(0)} min elapsed ·{" "}
        {(timing.residual_mass * 100).toFixed(0)}% of probability mass remains unresolved
      </p>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--nk-border-subtle)" />
          <XAxis
            dataKey="minute"
            type="number"
            domain={[0, 120]}
            unit="m"
            tick={{ fill: "var(--nk-text-secondary)", fontSize: 11 }}
          />
          <YAxis
            domain={[0, 1]}
            tickFormatter={(v) => `${Math.round(Number(v) * 100)}%`}
            tick={{ fill: "var(--nk-text-secondary)", fontSize: 11 }}
            width={40}
          />
          <Tooltip
            formatter={(v) => [`${(Number(v ?? 0) * 100).toFixed(0)}%`, "Cumulative probability"]}
            labelFormatter={(v) => `${v} min`}
            contentStyle={{
              background: "var(--nk-surface-raised)",
              border: "1px solid var(--nk-border-subtle)",
              color: "var(--nk-text-primary)",
              fontSize: 12,
            }}
          />
          <Area
            type="monotone"
            dataKey="prob"
            stroke="var(--nk-brand-primary)"
            fill="var(--nk-brand-primary)"
            fillOpacity={0.2}
          />
          {timing.elapsed_min >= 0 && timing.elapsed_min <= 120 && (
            <ReferenceLine
              x={Math.round(timing.elapsed_min)}
              stroke="var(--nk-verdict-warn)"
              strokeDasharray="4 4"
              label={{ value: "Now", position: "top", fill: "var(--nk-verdict-warn)", fontSize: 11 }}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
