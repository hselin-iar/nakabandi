/**
 * alertsLayer.ts — Point / halo layer for active fraud alerts on the map.
 * DOC 3 M3 / DOC 4 Step C5:
 *   Visual markers for active cash-out hotspots and alert targets.
 */

import type { AlertSummary } from "../../../shared/api/schema.d.ts";

export const ALERTS_SOURCE_ID = "nk-alerts-source";
export const ALERTS_HALO_LAYER_ID = "nk-alerts-halo";
export const ALERTS_POINT_LAYER_ID = "nk-alerts-point";

export function getAlertSeverityColor(severity: string): string {
  switch (severity.toUpperCase()) {
    case "CRITICAL":
      return "#ef4444";
    case "HIGH":
      return "#f97316";
    case "MEDIUM":
      return "#f59e0b";
    case "LOW":
      return "#3b82f6";
    default:
      return "#64748b";
  }
}

export function alertsToGeoJSON(
  alerts: AlertSummary[],
  coordsMap: Record<string, [number, number]> = {},
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  for (const alert of alerts) {
    const coords = coordsMap[alert.target.id] ??
      coordsMap[alert.id] ?? [77.21, 28.61]; // Default to center if unmapped

    features.push({
      type: "Feature",
      id: alert.id,
      properties: {
        id: alert.id,
        cluster_ref: alert.cluster_ref,
        target_name: alert.target.name ?? alert.target.id,
        target_kind: alert.target.kind,
        severity: alert.severity,
        status: alert.status,
        confidence: alert.confidence,
        expires_at: alert.expires_at,
        color: getAlertSeverityColor(alert.severity),
      },
      geometry: {
        type: "Point",
        coordinates: coords,
      },
    });
  }

  return {
    type: "FeatureCollection",
    features,
  };
}
