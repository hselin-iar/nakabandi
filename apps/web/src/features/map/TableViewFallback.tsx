/**
 * TableViewFallback.tsx — Accessible tabular fallback for WebGL failure or user preference.
 * DOC 3 M3 / DOC 4 Step C5:
 *   "A map render failure (WebGL unavailable) shows a table view of the same data
 *    so the demo never shows a blank canvas."
 */

import React from "react";
import type { HeatCell } from "./types";
import { Button } from "../../shared/ui/Button";
import { Icon } from "../../shared/ui/Icon";

interface TableViewFallbackProps {
  cells: HeatCell[];
  reason?: string;
  onSelectCell: (cell: HeatCell) => void;
  onRetryWebGL?: () => void;
}

export function TableViewFallback({
  cells,
  reason,
  onSelectCell,
  onRetryWebGL,
}: TableViewFallbackProps) {
  return (
    <div className="nk-table-fallback" aria-label="Risk heatmap tabular view">
      <div className="nk-fallback-banner" role="status">
        <div className="nk-fallback-banner__content">
          <span className="nk-fallback-banner__icon"><Icon name="table" size={18} /></span>
          <div>
            <div className="font-semibold text-sm">
              Tabular Risk View {reason ? `(${reason})` : "Active"}
            </div>
            <p className="text-xs text-secondary">
              Displaying all geographic risk intensity rollups in an accessible tabular format.
            </p>
          </div>
        </div>

        {onRetryWebGL && (
          <Button size="sm" variant="outline" onClick={onRetryWebGL}>
            <Icon name="refresh" /> Try WebGL Map
          </Button>
        )}
      </div>

      <div className="nk-table-container">
        <table className="nk-table" aria-label="Risk cells dataset">
          <thead>
            <tr>
              <th scope="col">Cell / Target ID</th>
              <th scope="col">Name & Geography</th>
              <th scope="col">Type</th>
              <th scope="col">Coordinates</th>
              <th scope="col">Risk Intensity</th>
              <th scope="col">Active Alerts</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {cells.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-secondary">
                  No risk cells match the current filter criteria.
                </td>
              </tr>
            ) : (
              cells.map((cell) => {
                const pct = (cell.value * 100).toFixed(0);
                return (
                  <tr key={cell.id}>
                    <td className="font-mono font-bold text-sm">{cell.id}</td>
                    <td>
                      <div className="font-medium text-sm">{cell.name ?? cell.id}</div>
                    </td>
                    <td>
                      <span className="nk-text-xs font-mono uppercase text-muted">
                        {cell.kind}
                      </span>
                    </td>
                    <td className="font-mono text-xs text-secondary">
                      {cell.lat.toFixed(3)}, {cell.lon.toFixed(3)}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="nk-mini-bar-track">
                          <div
                            className="nk-mini-bar-fill"
                            style={{
                              width: `${pct}%`,
                              backgroundColor:
                                cell.value >= 0.85
                                  ? "#ef4444"
                                  : cell.value >= 0.6
                                    ? "#f97316"
                                    : cell.value >= 0.25
                                      ? "#f59e0b"
                                      : "#06b6d4",
                            }}
                          />
                        </div>
                        <span className="font-mono font-bold text-xs">{pct}%</span>
                      </div>
                    </td>
                    <td>
                      <span
                        className={`font-mono text-sm font-semibold ${
                          cell.alert_count > 0 ? "text-critical" : "text-muted"
                        }`}
                      >
                        {cell.alert_count}
                      </span>
                    </td>
                    <td>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onSelectCell(cell)}
                        aria-label={`Inspect ${cell.id}`}
                      >
                        Inspect
                      </Button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
