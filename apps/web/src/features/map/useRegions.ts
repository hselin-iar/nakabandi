/**
 * useRegions.ts — Loads region metadata and bundled GeoJSON for the four demo states.
 * DOC 3 M3 / DOC 4 Step C5:
 *   "MapPage renders the four states from bundled GeoJSON with no network request"
 */

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../shared/api/client";
import demoStatesData from "./data/demo_states.json";
import type { Region } from "./types";

export const DEMO_REGIONS: Region[] = [
  // Four Demo States
  { id: "UP", level: "state", name: "Uttar Pradesh", parent_id: null, geojson_ref: "UP", lat: 26.85, lon: 80.95 },
  { id: "MH", level: "state", name: "Maharashtra", parent_id: null, geojson_ref: "MH", lat: 19.75, lon: 75.71 },
  { id: "JH", level: "state", name: "Jharkhand", parent_id: null, geojson_ref: "JH", lat: 23.6, lon: 85.3 },
  { id: "HR", level: "state", name: "Haryana", parent_id: null, geojson_ref: "HR", lat: 29.06, lon: 76.08 },

  // Districts — UP
  { id: "UP-LKO", level: "district", name: "Lucknow", parent_id: "UP", geojson_ref: null, lat: 26.85, lon: 80.95 },
  { id: "UP-KNP", level: "district", name: "Kanpur", parent_id: "UP", geojson_ref: null, lat: 26.47, lon: 80.33 },
  { id: "UP-AGR", level: "district", name: "Agra", parent_id: "UP", geojson_ref: null, lat: 27.18, lon: 78.01 },
  { id: "UP-GZB", level: "district", name: "Ghaziabad", parent_id: "UP", geojson_ref: null, lat: 28.67, lon: 77.45 },

  // Districts — MH
  { id: "MH-MUM", level: "district", name: "Mumbai", parent_id: "MH", geojson_ref: null, lat: 19.08, lon: 72.88 },
  { id: "MH-PUN", level: "district", name: "Pune", parent_id: "MH", geojson_ref: null, lat: 18.52, lon: 73.86 },
  { id: "MH-NAG", level: "district", name: "Nagpur", parent_id: "MH", geojson_ref: null, lat: 21.15, lon: 79.09 },
  { id: "MH-NAS", level: "district", name: "Nashik", parent_id: "MH", geojson_ref: null, lat: 20.00, lon: 73.79 },

  // Districts — JH (the 4 highest cybercrime-complaint-weight districts, data/seed/districts.csv)
  { id: "JH-RAN", level: "district", name: "Ranchi", parent_id: "JH", geojson_ref: null, lat: 23.34, lon: 85.31 },
  { id: "JH-DHA", level: "district", name: "Dhanbad", parent_id: "JH", geojson_ref: null, lat: 23.80, lon: 86.43 },
  { id: "JH-ESI", level: "district", name: "East Singhbhum", parent_id: "JH", geojson_ref: null, lat: 22.80, lon: 86.18 },
  { id: "JH-BOK", level: "district", name: "Bokaro", parent_id: "JH", geojson_ref: null, lat: 23.67, lon: 86.15 },

  // Districts — HR
  { id: "HR-GGN", level: "district", name: "Gurugram", parent_id: "HR", geojson_ref: null, lat: 28.46, lon: 77.03 },
  { id: "HR-FBD", level: "district", name: "Faridabad", parent_id: "HR", geojson_ref: null, lat: 28.41, lon: 77.31 },
  { id: "HR-AMB", level: "district", name: "Ambala", parent_id: "HR", geojson_ref: null, lat: 30.38, lon: 76.78 },
  { id: "HR-HIS", level: "district", name: "Hisar", parent_id: "HR", geojson_ref: null, lat: 29.15, lon: 75.72 },
];

export function useRegions() {
  const regionsQuery = useQuery<Region[]>({
    queryKey: ["geo", "regions"],
    queryFn: async () => {
      try {
        const res = await (apiClient.GET as unknown as (path: string, options?: unknown) => Promise<{ data?: unknown }>)(
          "/geo/regions",
        );
        if (res.data && Array.isArray(res.data) && res.data.length > 0) {
          return res.data as Region[];
        }
      } catch {
        // Fall back to bundled demo regions
      }
      return DEMO_REGIONS;
    },
    staleTime: 60_000,
  });

  return {
    regions: regionsQuery.data ?? DEMO_REGIONS,
    isLoading: regionsQuery.isLoading,
    bundledGeoJSON: demoStatesData as GeoJSON.FeatureCollection,
  };
}
