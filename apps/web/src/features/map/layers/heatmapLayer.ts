/**
 * heatmapLayer.ts — Smooth kernel-density heatmap layer for fraud intensity.
 * DOC 3 M3 / DOC 4 Step C5:
 *   Uses MapLibre's native GPU-accelerated heatmap layer type with raw Point GeoJSON.
 *   Replaces the old blocky polygon grid approach for a continuous smooth density look.
 */

import type { HeatCell } from "../types";

export const HEATMAP_SOURCE_ID = "nk-heatmap-source";
export const HEATMAP_LAYER_ID = "nk-heatmap-density";
export const HEATMAP_POINT_LAYER_ID = "nk-heatmap-points";

/**
 * Converts heatmap cells to raw Point GeoJSON for smooth kernel-density rendering.
 * Each point carries an `intensity` property (0–1) used as the heatmap weight.
 */
export function heatCellsToPointGeoJSON(cells: HeatCell[]): GeoJSON.FeatureCollection {
  // The potential layer's masses are unbounded (a busy cell can be 35 while the rest are 3):
  // scale to the largest so the ramp separates them instead of clamping everything at 1.
  const max = cells.reduce((m, c) => Math.max(m, c.value), 0);
  const scale = max > 1 ? max : 1;
  return {
    type: "FeatureCollection",
    features: cells.map((cell) => ({
      type: "Feature",
      id: cell.id,
      properties: {
        id: cell.id,
        kind: cell.kind,
        name: cell.name ?? cell.id,
        lat: cell.lat,
        lon: cell.lon,
        intensity: cell.value / scale, // 0–1, used as heatmap-weight
        alert_count: cell.alert_count,
      },
      geometry: {
        type: "Point",
        coordinates: [cell.lon, cell.lat],
      },
    })),
  };
}
