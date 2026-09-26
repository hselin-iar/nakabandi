/**
 * radarLayer.ts — Interception Radar: a unit-to-target ETA vector on the map.
 * Frontend Strategy §7.1: "the differentiator is that cash-out is physical, and physical
 * things can be raced against." Colour encodes the interception verdict; the line is a
 * computed animation from eta_min, never a live telemetry feed — label it that way in the UI.
 */

export const RADAR_SOURCE_ID = "nk-radar-source";
export const RADAR_LINE_LAYER_ID = "nk-radar-line";

export interface RadarVector {
  unit: [number, number]; // [lon, lat]
  target: [number, number]; // [lon, lat]
  verdict: string;
}

export function buildRadarGeoJSON(vector: RadarVector | null): GeoJSON.FeatureCollection {
  if (!vector) {
    return { type: "FeatureCollection", features: [] };
  }
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { verdict: vector.verdict },
        geometry: {
          type: "LineString",
          coordinates: [vector.unit, vector.target],
        },
      },
    ],
  };
}

export function radarVerdictColor(verdict: string): string {
  switch (verdict) {
    case "INTERCEPTABLE":
      return "#22c55e";
    case "MARGINAL":
      return "#f59e0b";
    case "NOT_INTERCEPTABLE":
      return "#ef4444";
    default:
      return "#64748b";
  }
}
