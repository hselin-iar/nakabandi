/**
 * HotspotDrawer.tsx — Slide-out inspection drawer for selected map cells and locations.
 * DOC 3 M3: "HotspotDrawer (click a cell or location -> underlying alerts with links and their evidence statements)"
 */

import React from "react";
import { Link } from "react-router-dom";
import { Drawer } from "../../shared/ui/Drawer";
import { SeverityBadge, StatusBadge } from "../../shared/ui/Badge";
import { Button } from "../../shared/ui/Button";
import { Countdown } from "../../shared/ui/Countdown";
import type { HotspotDetail } from "./types";

interface HotspotDrawerProps {
  hotspot: HotspotDetail | null;
  onClose: () => void;
  onSelectAlert?: (alertId: string) => void;
}

export function HotspotDrawer({
  hotspot,
  onClose,
  onSelectAlert,
}: HotspotDrawerProps) {
  if (!hotspot) return null;

  return (
    <Drawer
      open={Boolean(hotspot)}
      onClose={onClose}
      title={`Hotspot · ${hotspot.name || hotspot.id}`}
      width="md"
    >
      <div className="nk-hotspot-detail">
        {/* Metric summary banner */}
        <div className="nk-hotspot-summary-card">
          <div className="nk-hotspot-metric">
            <span className="nk-text-xs text-muted">Risk Score (p120)</span>
            <div className="text-xl font-bold font-mono">
              {(hotspot.value * 100).toFixed(0)}%
            </div>
          </div>
          <div className="nk-hotspot-metric">
            <span className="nk-text-xs text-muted">Active Alerts</span>
            <div className="text-xl font-bold font-mono text-critical">
              {hotspot.alert_count}
            </div>
          </div>
          <div className="nk-hotspot-metric">
            <span className="nk-text-xs text-muted">Location / Coordinates</span>
            <div className="text-xs font-mono text-secondary">
              {hotspot.lat.toFixed(4)}, {hotspot.lon.toFixed(4)}
            </div>
          </div>
        </div>

        {/* Contributing alerts list */}
        <div className="nk-hotspot-alerts-section">
          <h4 className="nk-text-sm font-semibold mb-2">
            Contributing Active Trajectories ({hotspot.contributing_alerts.length})
          </h4>

          {hotspot.contributing_alerts.length === 0 ? (
            <p className="text-xs text-secondary italic">
              No active alerts linked to this specific coordinate cluster.
            </p>
          ) : (
            <div className="nk-hotspot-alerts-list">
              {hotspot.contributing_alerts.map((alert) => (
                <div key={alert.id} className="nk-hotspot-alert-card">
                  <div className="nk-hotspot-alert-header">
                    <span className="font-mono font-bold text-sm">{alert.id}</span>
                    <div className="flex gap-1">
                      <SeverityBadge severity={alert.severity} />
                      <StatusBadge status={alert.status} />
                    </div>
                  </div>

                  <div className="text-xs text-secondary font-mono">
                    Cluster: {alert.cluster_ref}
                  </div>

                  {alert.reason && (
                    <div className="text-xs text-muted mt-1">
                      Evidence: {alert.reason}
                    </div>
                  )}

                  <div className="nk-hotspot-alert-footer mt-2">
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-muted">Window:</span>
                      <Countdown target={alert.window_end} warnThreshold={900} />
                    </div>

                    {onSelectAlert ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onSelectAlert(alert.id)}
                      >
                        Inspect Alert →
                      </Button>
                    ) : (
                      <Link to={`/alerts/${alert.id}`} className="nk-btn nk-btn--outline nk-btn--sm">
                        Inspect Alert →
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Drawer>
  );
}
