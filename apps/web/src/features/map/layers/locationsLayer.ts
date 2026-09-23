/**
 * locationsLayer.ts — Point layer for bank infrastructure (ATMs, Branches, BC Agents).
 * DOC 3 M3: "Location points and unit markers come from /geo/locations (bbox, kind, bank)".
 */

import type { LocationPoint } from "../types";

export const LOCATIONS_SOURCE_ID = "nk-locations-source";
export const LOCATIONS_CIRCLE_LAYER_ID = "nk-locations-circle";
export const LOCATIONS_LABEL_LAYER_ID = "nk-locations-label";

export function getLocationKindColor(kind: string): string {
  switch (kind.toUpperCase()) {
    case "ATM":
      return "#38bdf8"; // Sky blue
    case "BRANCH":
      return "#818cf8"; // Indigo
    case "AGENT":
      return "#34d399"; // Emerald green
    default:
      return "#94a3b8";
  }
}

export function locationsToGeoJSON(
  locations: LocationPoint[],
): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = locations.map((loc) => ({
    type: "Feature",
    id: loc.id,
    properties: {
      id: loc.id,
      kind: loc.kind,
      bank_id: loc.bank_id,
      display_name: loc.display_name,
      district_id: loc.district_id,
      area_type: loc.area_type,
      color: getLocationKindColor(loc.kind),
    },
    geometry: {
      type: "Point",
      coordinates: [loc.lon, loc.lat],
    },
  }));

  return {
    type: "FeatureCollection",
    features,
  };
}
