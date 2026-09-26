/**
 * DashboardPage.tsx — Command: a thin, ambient landing page, not a destination most roles
 * need to visit. Frontend Strategy §3.2/§4.1: "Keep a landing destination — but make it
 * thin: the live-metrics ticker plus the single soonest-expiring critical alert as a call
 * to action, and nothing else. The eight-tile launcher grid can go" — once the sidebar
 * itself is task-shaped, a restated copy of it here is redundant.
 */

import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAlerts } from "../alerts/api/useAlerts";
import { useClusters } from "../clusters/api/useClusters";
import { useHeatmap } from "../map/useHeatmap";
import { useLiveMetrics, useTimeseries } from "./api/useAnalytics";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { formatInr } from "../../shared/lib/format";
import { Countdown } from "../../shared/ui/Countdown";
import { SeverityBadge } from "../../shared/ui/Badge";
import type { Severity } from "../../shared/api/enums.ts";

// ---------------------------------------------------------------------------
// Mini sparkline (SVG) — renders a tiny trend line from an array of 0-1 values
// ---------------------------------------------------------------------------

function Sparkline({ values, color = "var(--nk-brand-primary)" }: { values: number[]; color?: string }) {
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
  value: string | number;
  sub?: string;
  color?: string;
  trend?: number[];
  trendColor?: string;
  onClick?: () => void;
  urgent?: boolean;
}

function KpiCard({ label, value, sub, color, trend, trendColor, onClick, urgent }: KpiCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`nk-dash-kpi-card${urgent ? " nk-dash-kpi-card--urgent" : ""}`}
      style={{ textAlign: "left", cursor: onClick ? "pointer" : "default" }}
    >
      <span className="nk-dash-kpi-card__label">{label}</span>
      <span className="nk-dash-kpi-card__value" style={{ color }}>
        {value}
      </span>
      {sub && <span className="nk-dash-kpi-card__sub">{sub}</span>}
      {trend && trend.length > 1 && (
        <div style={{ marginTop: 8 }}>
          <Sparkline values={trend} color={trendColor ?? color ?? "var(--nk-brand-primary)"} />
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
    const openAlerts   = alerts.filter((a) => a.status === "open").length;
    const criticalAlerts = alerts.filter((a) => a.severity === "CRITICAL" && a.status === "open").length;
    const activeClusters = clusters.filter((c) => c.status === "active").length;
    const totalPaise   = clusters.reduce((s, c) => s + (c.total_paise ?? 0), 0);
    const topIntensity = Math.max(...cells.map((c) => c.value), 0);
    const hotCells     = cells.filter((c) => c.value >= 0.7).length;
    const totalAlerts  = cells.reduce((s, c) => s + (c.alert_count ?? 0), 0);
    // Real hourly trend from GET /analytics/timeseries (the analytics module's own canonical
    // aggregation), not a client-fabricated shape — empty until the timeseries query resolves.
    const trendData    = timeseries?.points.map((p) => p.value) ?? [];
    return { openAlerts, criticalAlerts, activeClusters, totalPaise, topIntensity, hotCells, totalAlerts, trendData };
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
          (a, b) => new Date(a.expires_at).getTime() - new Date(b.expires_at).getTime(),
        )[0];
  }, [alerts]);

  const now = new Date().toLocaleString("en-IN", {
    hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short"
  });

  return (
    <div className="nk-dash-page" data-testid="dashboard-page">
      {/* ── Header ── */}
      <div className="nk-dash-header">
        <div>
          <h1 className="nk-dash-title">Command</h1>
          <p className="nk-dash-subtitle">
            Welcome back, <strong>{principal?.name ?? "Officer"}</strong> ·{" "}
            <span style={{ color: "var(--nk-text-muted)" }}>{now}</span>
          </p>
        </div>
        <div className="nk-dash-header-actions">
          <div className="nk-live-indicator">
            <span className="nk-live-dot" aria-hidden="true" />
            Live
          </div>
        </div>
      </div>

      {/* ── Call to action: the single soonest-expiring alert, not a tile grid ── */}
      {soonestAlert && (
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
                {String(soonestAlert.target.name ?? soonestAlert.target.id ?? "Target")} ·{" "}
                {soonestAlert.cluster_ref}
              </span>
            </div>
          </div>
          <div className="nk-dash-cta__right">
            <Countdown target={soonestAlert.expires_at} warnThreshold={900} />
            <span className="nk-dash-cta__go">Go to Triage →</span>
          </div>
        </button>
      )}

      {/* ── Live metrics ticker ── */}
      <div className="nk-dash-kpi-strip" role="region" aria-label="System-wide KPIs">
        <KpiCard
          label="Open Alerts"
          value={kpis.openAlerts}
          sub={`${kpis.criticalAlerts} critical`}
          color={kpis.criticalAlerts > 0 ? "#ef4444" : "var(--nk-text-primary)"}
          trend={kpis.trendData}
          trendColor={kpis.criticalAlerts > 0 ? "#ef4444" : "var(--nk-brand-primary)"}
          onClick={() => navigate("/alerts")}
          urgent={kpis.criticalAlerts > 0}
        />
        <KpiCard
          label="Active Clusters"
          value={kpis.activeClusters}
          sub={`${clusters.length} total mule networks`}
          color="var(--nk-brand-primary)"
          onClick={() => navigate("/cases")}
        />
        <KpiCard
          label="Total Disputed"
          value={formatInr(kpis.totalPaise)}
          sub="across all active clusters"
          color="#38bdf8"
          onClick={() => navigate("/cases")}
        />
        <KpiCard
          label="Forecast Hotspots"
          value={kpis.hotCells}
          sub={`intensity ≥ 70% · ${kpis.totalAlerts} alert markers`}
          color="#f59e0b"
          onClick={() => navigate("/map")}
        />
        <KpiCard
          label="Peak Intensity"
          value={`${(kpis.topIntensity * 100).toFixed(0)}%`}
          sub="highest cell forecast score"
          color={kpis.topIntensity > 0.8 ? "#ef4444" : kpis.topIntensity > 0.6 ? "#f59e0b" : "#22c55e"}
          onClick={() => navigate("/map")}
        />
        <KpiCard
          label="Forecast Mass (24h)"
          value={liveMetrics ? liveMetrics.expected_mass.toFixed(1) : "—"}
          sub={
            liveMetrics
              ? `probability-weighted cash-out risk · ${liveMetrics.active_locations} active locations`
              : "GET /analytics/live-metrics"
          }
          color="#a78bfa"
          onClick={() => navigate("/map")}
        />
      </div>
    </div>
  );
}
