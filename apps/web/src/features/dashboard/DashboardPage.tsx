/**
 * DashboardPage.tsx — Command: a thin, ambient landing page, not a destination most roles
 * need to visit. Frontend Strategy §3.2/§4.1: "Keep a landing destination — but make it
 * thin: the live-metrics ticker plus the single soonest-expiring critical alert as a call
 * to action, and nothing else. The eight-tile launcher grid can go" — once the sidebar
 * itself is task-shaped, a restated copy of it here is redundant.
 */

import React, { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAlerts } from "../alerts/api/useAlerts";
import { useClusters } from "../clusters/api/useClusters";
import { useHeatmap } from "../map/useHeatmap";
import { useLiveMetrics, useTimeseries } from "./api/useAnalytics";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { formatInr } from "../../shared/lib/format";
import { Countdown } from "../../shared/ui/Countdown";
import { RollingCounter } from "../../shared/ui/RollingCounter";
import { SeverityBadge, StatusBadge } from "../../shared/ui/Badge";
import { useSimTime } from "../../shared/stream/useStream";
import { formatSimTime } from "../../shared/lib/format";
import type { AlertStatus, Severity } from "../../shared/api/enums.ts";

const SEVERITY_RANK: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

// ---------------------------------------------------------------------------
// Mini sparkline (SVG) — renders a tiny trend line from an array of 0-1 values
// ---------------------------------------------------------------------------

function Sparkline({
  values,
  color = "var(--nk-accent)",
}: {
  values: number[];
  color?: string;
}) {
  if (values.length < 2) return null;
  const w = 80;
  const h = 28;
  const max = Math.max(...values, 0.01);
  const pts = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - (v / max) * h}`)
    .join(" ");
  return (
    <svg width={w} height={h} aria-hidden="true" style={{ display: "block" }}>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={1.8}
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity={0.8}
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// KPI card
// ---------------------------------------------------------------------------

interface KpiCardProps {
  label: string;
  /** Static text; ignored when `rolling` is given. */
  value?: string | number;
  /** Numeric value that rolls to its new figure on every update instead of snapping. */
  rolling?: { value: number; format?: (n: number) => string };
  sub?: string;
  color?: string;
  trend?: number[];
  trendColor?: string;
  onClick?: () => void;
  urgent?: boolean;
}

function KpiCard({
  label,
  value,
  rolling,
  sub,
  color,
  trend,
  trendColor,
  onClick,
  urgent,
}: KpiCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`nk-dash-kpi-card${urgent ? " nk-dash-kpi-card--urgent" : ""}`}
      style={{ textAlign: "left", cursor: onClick ? "pointer" : "default" }}
    >
      <span className="nk-dash-kpi-card__label">{label}</span>
      <span className="nk-dash-kpi-card__value" style={{ color }}>
        {rolling ? (
          <RollingCounter value={rolling.value} format={rolling.format} />
        ) : (
          value
        )}
      </span>
      {sub && <span className="nk-dash-kpi-card__sub">{sub}</span>}
      {trend && trend.length > 1 && (
        <div style={{ marginTop: 8 }}>
          <Sparkline
            values={trend}
            color={trendColor ?? color ?? "var(--nk-accent)"}
          />
        </div>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// DashboardPage
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const navigate = useNavigate();
  const { principal } = usePrincipal();

  const { data: alerts = [] } = useAlerts();
  const { data: clusters = [] } = useClusters();
  const { data: heatmapData } = useHeatmap({ layer: "live", level: "cell" });
  const { data: liveMetrics } = useLiveMetrics();
  const { data: timeseries } = useTimeseries("live");

  const cells = heatmapData?.cells ?? [];

  const kpis = useMemo(() => {
    const openAlerts = alerts.filter((a) => a.status === "open").length;
    const criticalAlerts = alerts.filter(
      (a) => a.severity === "CRITICAL" && a.status === "open",
    ).length;
    const activeClusters = clusters.filter((c) => c.status === "active").length;
    const totalPaise = clusters.reduce((s, c) => s + (c.total_paise ?? 0), 0);
    const topIntensity = Math.max(...cells.map((c) => c.value), 0);
    const hotCells = cells.filter((c) => c.value >= 0.7).length;
    const totalAlerts = cells.reduce((s, c) => s + (c.alert_count ?? 0), 0);
    // Real hourly trend from GET /analytics/timeseries (the analytics module's own canonical
    // aggregation), not a client-fabricated shape — empty until the timeseries query resolves.
    const trendData = timeseries?.points.map((p) => p.value) ?? [];
    return {
      openAlerts,
      criticalAlerts,
      activeClusters,
      totalPaise,
      topIntensity,
      hotCells,
      totalAlerts,
      trendData,
    };
  }, [alerts, clusters, cells, timeseries]);

  // The single soonest-expiring critical alert — the call to action (§4.1), not a restated
  // module launcher. Falls back to the soonest-expiring open alert of any severity.
  const soonestAlert = useMemo(() => {
    const open = alerts.filter((a) => a.status === "open");
    const critical = open.filter((a) => a.severity === "CRITICAL");
    const pool = critical.length > 0 ? critical : open;
    return pool.length === 0
      ? null
      : [...pool].sort(
          (a, b) =>
            new Date(a.expires_at).getTime() - new Date(b.expires_at).getTime(),
        )[0];
  }, [alerts]);

  const simTime = useSimTime();
  const nowMs = simTime ? new Date(simTime).getTime() : Date.now();

  // Top of the queue: live alerts first (most severe, soonest to close), then the latest closed ones
  const priorityAlerts = useMemo(() => {
    const isLive = (a: (typeof alerts)[number]) =>
      a.status !== "expired" && new Date(a.expires_at).getTime() > nowMs;
    return [...alerts]
      .sort(
        (a, b) =>
          Number(isLive(b)) - Number(isLive(a)) ||
          (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0) ||
          b.created_at.localeCompare(a.created_at),
      )
      .slice(0, 6);
  }, [alerts, nowMs]);

  const largestNetworks = useMemo(
    () =>
      [...clusters]
        .sort((a, b) => (b.total_paise ?? 0) - (a.total_paise ?? 0))
        .slice(0, 6),
    [clusters],
  );

  return (
    <div className="nk-cmd" data-testid="dashboard-page">
      <header className="nk-cmd__head">
        <h1 className="nk-console-title">Command</h1>
        <p className="nk-cmd__sub">
          Operator <strong>{principal?.name ?? "Officer"}</strong>
          {simTime && (
            <> · DTG {formatSimTime(simTime, { includeSeconds: true })}Z</>
          )}
        </p>
      </header>

      {soonestAlert ? (
        <button
          type="button"
          className="nk-dash-cta"
          onClick={() => navigate(`/alerts/${soonestAlert.id}`)}
        >
          <div className="nk-dash-cta__left">
            <SeverityBadge severity={soonestAlert.severity as Severity} />
            <div className="nk-dash-cta__text">
              <span className="nk-dash-cta__label">Closest to closing</span>
              <span className="nk-dash-cta__target">
                {String(
                  soonestAlert.target.name ??
                    soonestAlert.target.id ??
                    "Target",
                )}{" "}
                · {soonestAlert.cluster_ref}
              </span>
            </div>
          </div>
          <div className="nk-dash-cta__right">
            <Countdown target={soonestAlert.expires_at} warnThreshold={900} />
            <span className="nk-dash-cta__go">Go to Triage →</span>
          </div>
        </button>
      ) : (
        <div className="nk-cmd__idle" role="status">
          No alert is open right now. The queue is clear.
        </div>
      )}

      <section
        className="nk-cmd__kpis"
        role="region"
        aria-label="System-wide KPIs"
      >
        <KpiCard
          label="Open Alerts"
          rolling={{ value: kpis.openAlerts }}
          sub={`${kpis.criticalAlerts} critical`}
          color={
            kpis.criticalAlerts > 0
              ? "var(--nk-severity-critical)"
              : "var(--nk-text-primary)"
          }
          trend={kpis.trendData}
          trendColor={
            kpis.criticalAlerts > 0
              ? "var(--nk-severity-critical)"
              : "var(--nk-accent)"
          }
          onClick={() => navigate("/alerts")}
          urgent={kpis.criticalAlerts > 0}
        />
        <KpiCard
          label="Active Clusters"
          rolling={{ value: kpis.activeClusters }}
          sub={`${clusters.length} mule networks tracked`}
          color="var(--nk-text-primary)"
          onClick={() => navigate("/cases")}
        />
        <KpiCard
          label="Total Disputed"
          rolling={{
            value: kpis.totalPaise,
            format: (n) => formatInr(Math.round(n), { compact: true }),
          }}
          sub="across all clusters"
          color="var(--nk-text-primary)"
          onClick={() => navigate("/cases")}
        />
        <KpiCard
          label="Forecast Hotspots"
          rolling={{ value: kpis.hotCells }}
          sub={`intensity ≥ 70% · ${kpis.totalAlerts} alert markers`}
          color="var(--nk-text-primary)"
          onClick={() => navigate("/map")}
        />
        <KpiCard
          label="Peak Intensity"
          rolling={{
            value: kpis.topIntensity * 100,
            format: (n) => `${n.toFixed(0)}%`,
          }}
          sub="highest cell forecast score"
          color="var(--nk-text-primary)"
          onClick={() => navigate("/map")}
        />
        <KpiCard
          label="Forecast Mass (24h)"
          {...(liveMetrics
            ? {
                rolling: {
                  value: liveMetrics.expected_mass,
                  format: (n: number) => n.toFixed(1),
                },
              }
            : { value: "—" })}
          sub={
            liveMetrics
              ? `cash-out risk · ${liveMetrics.active_locations} active locations`
              : "awaiting live metrics"
          }
          color="var(--nk-text-primary)"
          onClick={() => navigate("/map")}
        />
      </section>

      <div className="nk-cmd__cols">
        <section className="nk-cmd__panel" aria-label="Priority alerts">
          <header className="nk-cmd__panel-head">
            <h2 className="nk-dossier-h">Priority alerts</h2>
            <Link to="/alerts" className="nk-cmd__more">
              View all →
            </Link>
          </header>
          {priorityAlerts.length === 0 ? (
            <p className="nk-cmd__empty">No alerts in the current window.</p>
          ) : (
            <ul className="nk-cmd__list">
              {priorityAlerts.map((a) => {
                const closed =
                  a.status === "expired" ||
                  new Date(a.expires_at).getTime() <= nowMs;
                return (
                  <li key={a.id}>
                    <button
                      type="button"
                      className="nk-cmd__row"
                      onClick={() => navigate(`/alerts/${a.id}`)}
                    >
                      <SeverityBadge severity={a.severity as Severity} />
                      <span className="nk-cmd__row-main">
                        <span className="nk-cmd__row-title">
                          {String(a.target.name ?? a.target.id ?? "Target")}
                        </span>
                        <span className="nk-cmd__row-sub">{a.cluster_ref}</span>
                      </span>
                      <StatusBadge status={a.status as AlertStatus} />
                      <span className="nk-cmd__row-end">
                        {closed ? (
                          "WINDOW CLOSED"
                        ) : (
                          <Countdown
                            target={a.expires_at}
                            warnThreshold={900}
                          />
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="nk-cmd__panel" aria-label="Largest networks">
          <header className="nk-cmd__panel-head">
            <h2 className="nk-dossier-h">Largest networks</h2>
            <Link to="/cases" className="nk-cmd__more">
              View all →
            </Link>
          </header>
          {largestNetworks.length === 0 ? (
            <p className="nk-cmd__empty">No mule networks identified yet.</p>
          ) : (
            <ul className="nk-cmd__list">
              {largestNetworks.map((c) => (
                <li key={c.cluster_ref}>
                  <button
                    type="button"
                    className="nk-cmd__row"
                    onClick={() => navigate(`/clusters/${c.cluster_ref}`)}
                  >
                    <span className="nk-cmd__row-main">
                      <span className="nk-cmd__row-title nk-cmd__mono">
                        {c.cluster_ref}
                      </span>
                      <span className="nk-cmd__row-sub">
                        {c.size ?? "?"} {c.size === 1 ? "account" : "accounts"}
                      </span>
                    </span>
                    <span className="nk-cmd__row-end nk-cmd__amount">
                      {formatInr(c.total_paise ?? 0, { compact: true })}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
