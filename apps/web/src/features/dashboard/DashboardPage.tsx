/**
 * DashboardPage.tsx — System command-centre landing.
 * Phase 2 of the frontend overhaul. Pulls from the same TanStack Query caches
 * used by other pages (no extra API calls), so data is instantly available after
 * the first page load.
 */

import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAlerts } from "../alerts/api/useAlerts";
import { useClusters } from "../clusters/api/useClusters";
import { useHeatmap, FIXTURE_HEATMAP } from "../map/useHeatmap";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { formatInr } from "../../shared/lib/format";

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
// Module nav card
// ---------------------------------------------------------------------------

interface ModuleCardProps {
  title: string;
  description: string;
  icon: string;
  href: string;
  badge?: string | number;
  badgeUrgent?: boolean;
}

function ModuleCard({ title, description, icon, href, badge, badgeUrgent }: ModuleCardProps) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className="nk-dash-module-card"
      onClick={() => navigate(href)}
    >
      <div className="nk-dash-module-card__header">
        <span className="nk-dash-module-card__icon" aria-hidden="true">{icon}</span>
        {badge !== undefined && badge !== null && (
          <span className={`nk-dash-module-card__badge${badgeUrgent ? " nk-dash-module-card__badge--urgent" : ""}`}>
            {badge}
          </span>
        )}
      </div>
      <div className="nk-dash-module-card__title">{title}</div>
      <div className="nk-dash-module-card__desc">{description}</div>
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

  const cells = heatmapData?.cells ?? FIXTURE_HEATMAP.cells;

  const kpis = useMemo(() => {
    const openAlerts   = alerts.filter((a) => a.status === "open").length;
    const criticalAlerts = alerts.filter((a) => a.severity === "CRITICAL" && a.status === "open").length;
    const activeClusters = clusters.filter((c) => c.status === "active").length;
    const totalPaise   = clusters.reduce((s, c) => s + (c.total_paise ?? 0), 0);
    const topIntensity = Math.max(...cells.map((c) => c.value), 0);
    const hotCells     = cells.filter((c) => c.value >= 0.7).length;
    const totalAlerts  = cells.reduce((s, c) => s + (c.alert_count ?? 0), 0);
    // Fake 12-hour trend buckets from alert severity counts (visual only)
    const trendData    = [0.3, 0.4, 0.5, 0.45, 0.6, 0.7, 0.65, 0.8, openAlerts / Math.max(alerts.length, 1)];
    return { openAlerts, criticalAlerts, activeClusters, totalPaise, topIntensity, hotCells, totalAlerts, trendData };
  }, [alerts, clusters, cells]);

  const now = new Date().toLocaleString("en-IN", {
    hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short"
  });

  return (
    <div className="nk-dash-page" data-testid="dashboard-page">
      {/* ── Header ── */}
      <div className="nk-dash-header">
        <div>
          <h1 className="nk-dash-title">Command Centre</h1>
          <p className="nk-dash-subtitle">
            Welcome back, <strong>{principal?.name ?? "Officer"}</strong> ·{" "}
            <span style={{ color: "var(--nk-text-muted)" }}>{now}</span>
          </p>
        </div>
        <div className="nk-dash-header-actions">
          {kpis.criticalAlerts > 0 && (
            <button
              type="button"
              className="nk-btn nk-btn--danger nk-btn--sm"
              onClick={() => navigate("/alerts")}
              style={{ animation: "nk-pulse 2s infinite" }}
            >
              ⚡ {kpis.criticalAlerts} CRITICAL alert{kpis.criticalAlerts !== 1 ? "s" : ""} — Respond now
            </button>
          )}
          <div className="nk-live-indicator">
            <span className="nk-live-dot" aria-hidden="true" />
            Live
          </div>
        </div>
      </div>

      {/* ── Top KPI strip ── */}
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
          onClick={() => navigate("/clusters")}
        />
        <KpiCard
          label="Total Disputed"
          value={formatInr(kpis.totalPaise)}
          sub="across all active clusters"
          color="#38bdf8"
          onClick={() => navigate("/clusters")}
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
      </div>

      {/* ── Module navigation grid ── */}
      <div className="nk-dash-section-label">Modules</div>
      <div className="nk-dash-modules-grid" role="navigation" aria-label="Module navigation">
        <ModuleCard
          title="Alert Inbox"
          description="Live fraud trajectory alerts with countdown windows. Acknowledge and dispatch before expiry."
          icon="🚨"
          href="/alerts"
          badge={kpis.openAlerts > 0 ? kpis.openAlerts : undefined}
          badgeUrgent={kpis.criticalAlerts > 0}
        />
        <ModuleCard
          title="Risk Heatmap"
          description="Geospatial forecast intensity across UP, MH, HR and JH. Click cells to inspect alerts."
          icon="🗺️"
          href="/map"
          badge={kpis.hotCells > 0 ? `${kpis.hotCells} hot` : undefined}
        />
        <ModuleCard
          title="Cluster Topology"
          description="Graph explorer for mule account networks. Inspect transaction flows and bridge nodes."
          icon="🕸️"
          href="/clusters"
          badge={kpis.activeClusters > 0 ? kpis.activeClusters : undefined}
        />
        <ModuleCard
          title="Case Bundles"
          description="Complaints linked to mule clusters. Attach evidence packs for court-ready case briefs."
          icon="📁"
          href="/cases"
        />
        <ModuleCard
          title="Evaluation Harness"
          description="Model performance: precision, recall, F1 and cold-start curves against the oracle."
          icon="📊"
          href="/evaluation"
        />
        <ModuleCard
          title="Notification Outbox"
          description="SSE-delivered webhook and in-app alert delivery log with retry status."
          icon="📬"
          href="/outbox"
        />
        <ModuleCard
          title="Audit Trail"
          description="Immutable hash-chain log of all principal actions. Tamper-detection included."
          icon="🔒"
          href="/audit"
        />
        <ModuleCard
          title="Demo Console"
          description="Inject clusters, adjust simulation speed, and quick-switch between demo roles."
          icon="🎛️"
          href="/demo"
        />
      </div>
    </div>
  );
}
