/**
 * cellsLayer.ts — GeoJSON builder and layer styling for risk heatmap cells.
 * DOC 3 M3 / DOC 4 Step C5:
 *   Builds GeoJSON features for district rollups or equirectangular cells.
 */

import type { HeatCell } from "../types";

export const CELLS_SOURCE_ID = "nk-cells-source";
export const CELLS_FILL_LAYER_ID = "nk-cells-fill";
export const CELLS_LINE_LAYER_ID = "nk-cells-line";

export function getRiskColor(value: number): string {
  if (value >= 0.85) return "#ef4444"; // Critical (Red)
  if (value >= 0.6) return "#f97316"; // High (Orange)
  if (value >= 0.25) return "#f59e0b"; // Medium (Amber)
  return "#06b6d4"; // Low (Cyan)
}

export function cellsToGeoJSON(
  cells: HeatCell[],
  cellSizeDeg = 1.5,           // 1.5° ≈ ~165 km — visible at zoom 5–7
): GeoJSON.FeatureCollection {
  const half = cellSizeDeg / 2;
  const features: GeoJSON.Feature[] = cells.map((cell) => {
    // Generate square bounding polygon for the cell
    const minLon = cell.lon - half;
    const maxLon = cell.lon + half;
    const minLat = cell.lat - half;
    const maxLat = cell.lat + half;

    return {
      type: "Feature",
      id: cell.id,
      properties: {
        id: cell.id,
        kind: cell.kind,
        name: cell.name ?? cell.id,
        lat: cell.lat,
        lon: cell.lon,
        value: cell.value,
        alert_count: cell.alert_count,
        color: getRiskColor(cell.value),
      },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [minLon, minLat],
            [maxLon, minLat],
            [maxLon, maxLat],
            [minLon, maxLat],
            [minLon, minLat],
          ],
        ],
      },
    };
  });

  return {
    type: "FeatureCollection",
    features,
  };
}
