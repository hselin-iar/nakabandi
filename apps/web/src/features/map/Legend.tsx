/**
 * Legend.tsx — Visual scale and methodology legend for the Risk Heatmap.
 * DOC 3 M3: "Legend: { min, max, unit, note } ... It is a PERSISTENCE ESTIMATE
 * of recent forecast intensity over the next 72 h, not a separate model, and the legend says so."
 */

import React from "react";
import type { LegendData } from "./types";

interface LegendProps {
  legend: LegendData;
  suppressedCount: number;
}

export function Legend({ legend, suppressedCount }: LegendProps) {
  return (
    <div className="nk-map-legend" aria-label="Risk heatmap legend">
      <div className="nk-legend-header">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">
          Fraud Risk Density
        </span>
        <span className="text-xs font-mono text-muted">{legend.unit}</span>
      </div>

      <div className="nk-legend-scale" aria-hidden="true">
        <div className="nk-legend-bar" />
        <div className="nk-legend-labels">
          <span className="font-mono text-xs">{legend.min.toFixed(1)}</span>
          <span className="font-mono text-xs text-muted">0.25</span>
          <span className="font-mono text-xs text-muted">0.60</span>
          <span className="font-mono text-xs text-muted">0.85</span>
          <span className="font-mono text-xs font-bold">{legend.max.toFixed(1)}</span>
        </div>
      </div>

      <div className="nk-legend-markers">
        <div className="nk-legend-marker">
          <span className="nk-legend-dot nk-legend-dot--low" />
          <span className="text-xs text-muted">Low</span>
        </div>
        <div className="nk-legend-marker">
          <span className="nk-legend-dot nk-legend-dot--med" />
          <span className="text-xs text-muted">Med</span>
        </div>
        <div className="nk-legend-marker">
          <span className="nk-legend-dot nk-legend-dot--high" />
          <span className="text-xs text-muted">High</span>
        </div>
        <div className="nk-legend-marker">
          <span className="nk-legend-dot nk-legend-dot--crit" />
          <span className="text-xs text-muted">Critical</span>
        </div>
      </div>

      <div className="nk-legend-infra">
        <span className="text-xs text-muted">Points:</span>
        <span className="nk-infra-badge nk-infra-badge--atm">ATM</span>
        <span className="nk-infra-badge nk-infra-badge--branch">Branch</span>
        <span className="nk-infra-badge nk-infra-badge--agent">BC Agent</span>
      </div>

      {suppressedCount > 0 && (
        <div className="nk-legend-suppressed">
          <span className="text-xs text-muted">
            🛡️ {suppressedCount} cell{suppressedCount > 1 ? "s" : ""} suppressed below <em>k</em>-threshold
          </span>
        </div>
      )}

      <div className="nk-legend-note">
        <p className="nk-text-xs text-secondary italic">{legend.note}</p>
      </div>
    </div>
  );
}
