/**
 * OpsPage.tsx — Operations console: events/s, latencies, outbox depth.
 * DOC 2 §2.7 · DOC 4 Step C7
 *
 * All numbers come from the API (fixture until Track A Step A11 lands).
 * Browser only formats and renders — never recomputes p95 or event rates.
 */

import React from "react";
import { Link } from "react-router-dom";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { useOpsMetrics } from "./api/useOps";
import { formatSimTime } from "../../shared/lib/format";
import type { StageLatency, ChannelHealth } from "./api/useOps";

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  warn?: boolean;
  testId?: string;
  linkTo?: string;
}

function StatCard({ label, value, unit, warn, testId, linkTo }: StatCardProps) {
  const body = (
    <>
      <span className="nk-ops-stat-card__label">{label}</span>
      <span className="nk-ops-stat-card__value">
        {value}
        {unit && <span className="nk-ops-stat-card__unit"> {unit}</span>}
      </span>
    </>
  );
  const className = `nk-ops-stat-card${warn ? " nk-ops-stat-card--warn" : ""}`;
  if (linkTo) {
    return (
      <Link to={linkTo} className={className} data-testid={testId}>
        {body}
      </Link>
    );
  }
  return (
    <div className={className} data-testid={testId}>
      {body}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stage latency chart
// ---------------------------------------------------------------------------

function LatencyChart({ stages }: { stages: StageLatency[] }) {
  const data = stages.map((s) => ({
    stage: s.stage,
    p50: s.p50_ms,
    p95: s.p95_ms,
  }));

  return (
    <div className="nk-ops-chart" role="img" aria-label="Pipeline stage latencies">
      <h3 className="nk-ops-chart__title">Stage Latencies (ms)</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--nk-border-subtle)" />
          <XAxis dataKey="stage" tick={{ fill: "var(--nk-text-secondary)", fontSize: 11 }} />
          <YAxis
            unit="ms"
            tick={{ fill: "var(--nk-text-secondary)", fontSize: 11 }}
            width={50}
          />
          <Tooltip
            formatter={(v, name) => [`${Number(v ?? 0)} ms`, name === "p50" ? "p50" : "p95"]}
            contentStyle={{
              background: "var(--nk-surface-raised)",
              border: "1px solid var(--nk-border-subtle)",
              color: "var(--nk-text-primary)",
              fontSize: 12,
            }}
          />
          <Bar dataKey="p50" name="p50" fill="var(--nk-text-secondary)" radius={[3, 3, 0, 0]} />
          <Bar dataKey="p95" name="p95" fill="var(--nk-accent)" radius={[3, 3, 0, 0]} />
          {/* SLO reference line at 200 ms */}
          <ReferenceLine y={200} stroke="var(--nk-severity-high)" strokeDasharray="4 2" label={{ value: "200 ms SLO", fill: "var(--nk-severity-high)", fontSize: 10 }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Events/s sparkline
// ---------------------------------------------------------------------------

function EpsChart({ series }: { series: { at: string; eps: number }[] }) {
  const data = series.map((pt) => ({
    t: new Date(pt.at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false }),
    eps: pt.eps,
  }));

  return (
    <div className="nk-ops-chart" role="img" aria-label="Events per second time series">
      <h3 className="nk-ops-chart__title">Events / s (last 20 min)</h3>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--nk-border-subtle)" />
          <XAxis dataKey="t" tick={{ fill: "var(--nk-text-secondary)", fontSize: 10 }} />
          <YAxis tick={{ fill: "var(--nk-text-secondary)", fontSize: 11 }} width={36} />
          <Tooltip
            formatter={(v) => [`${Number(v ?? 0)} ev/s`, "Events/s"]}
            contentStyle={{
              background: "var(--nk-surface-raised)",
              border: "1px solid var(--nk-border-subtle)",
              color: "var(--nk-text-primary)",
              fontSize: 12,
            }}
          />
          <Line type="monotone" dataKey="eps" stroke="var(--nk-accent)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Channel health table
// ---------------------------------------------------------------------------

function ChannelTable({ channels }: { channels: ChannelHealth[] }) {
  return (
    <div className="nk-ops-channel-table-wrapper">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h3 className="nk-ops-section-title">Outbox Channel Health</h3>
        <Link to="/outbox" className="nk-text-xs">View full outbox →</Link>
      </div>
      <table className="nk-table" data-testid="ops-channel-table">
        <thead>
          <tr>
            <th className="nk-table__th">Channel</th>
            <th className="nk-table__th nk-table__th--right">Pending</th>
            <th className="nk-table__th nk-table__th--right">Delivered 24 h</th>
            <th className="nk-table__th nk-table__th--right">Failed 24 h</th>
          </tr>
        </thead>
        <tbody>
          {channels.map((ch) => (
            <tr
              key={ch.channel}
              className={`nk-table__row${ch.failed_24h > 0 ? " nk-table__row--warn" : ""}`}
              data-testid={`ops-channel-${ch.channel}`}
            >
              <td className="nk-table__td">
                <code className="nk-mono">{ch.channel}</code>
              </td>
              <td className="nk-table__td nk-table__td--right">{ch.pending}</td>
              <td className="nk-table__td nk-table__td--right nk-text-good">
                {ch.delivered_24h}
              </td>
              <td
                className={`nk-table__td nk-table__td--right ${
                  ch.failed_24h > 0 ? "nk-text-bad" : ""
                }`}
              >
                {ch.failed_24h > 0 ? `⚠ ${ch.failed_24h}` : ch.failed_24h}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// OpsPage
// ---------------------------------------------------------------------------

export default function OpsPage() {
  const { data: metrics, isLoading, error } = useOpsMetrics();

  if (isLoading) {
    return (
      <div className="nk-page-loading" aria-live="polite">
        Loading ops metrics…
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="nk-error-state" role="alert">
        <span className="nk-error-state__icon" aria-hidden="true">⚠</span>
        <p className="nk-error-state__message">Could not load operations metrics. Please retry.</p>
      </div>
    );
  }

  return (
    <main className="nk-ops-page" data-testid="ops-page">
      <header className="nk-ops-page__header">
        <h1 className="nk-ops-page__title">Operations Console</h1>
        {metrics.auto_paused && (
          <div className="nk-ops-auto-pause-banner" role="alert" data-testid="ops-auto-pause-banner">
            ⏸ Auto-paused — simulator has been suspended
          </div>
        )}
        <p className="nk-ops-page__subtitle">
          Captured at {formatSimTime(metrics.captured_at)}
          {metrics.sim_speed_ratio != null && ` · Sim speed ×${metrics.sim_speed_ratio.toFixed(1)}`}
        </p>
      </header>

      {/* Key stat cards */}
      <section className="nk-ops-stats-grid" aria-label="Key metrics" data-testid="ops-stats-grid">
        <StatCard
          label="Events / s"
          value={metrics.events_per_second.toFixed(1)}
          testId="ops-stat-eps"
        />
        <StatCard
          label="Outbox Depth"
          value={metrics.outbox_depth}
          warn={metrics.outbox_depth > 50}
          testId="ops-stat-outbox-depth"
          linkTo="/outbox"
        />
        <StatCard
          label="Delivery Failures (24 h)"
          value={metrics.delivery_failures_24h}
          warn={metrics.delivery_failures_24h > 0}
          testId="ops-stat-failures"
        />
        {metrics.sim_speed_ratio != null && (
          <StatCard
            label="Sim Speed"
            value={`×${metrics.sim_speed_ratio.toFixed(1)}`}
            testId="ops-stat-sim-speed"
          />
        )}
      </section>

      {/* Events/s time series (session-local: accumulates from when this page opened) */}
      <section className="nk-ops-section" aria-label="Events per second">
        <EpsChart series={metrics.eps_series} />
      </section>

      {/* Stage latency chart */}
      <section className="nk-ops-section" aria-label="Stage latencies">
        <LatencyChart stages={metrics.stage_latencies} />
      </section>

      {/* Channel health: not broken down by channel on the backend yet */}
      {metrics.channel_health.length > 0 && (
        <section className="nk-ops-section" aria-label="Channel health">
          <ChannelTable channels={metrics.channel_health} />
        </section>
      )}
    </main>
  );
}
