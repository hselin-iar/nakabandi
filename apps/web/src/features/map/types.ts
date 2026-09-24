/**
 * types.ts — Types for the Risk Heatmap Dashboard (DOC 3 M3, LC-4).
 */

import type { Severity, AlertStatus } from "../../shared/api/enums.ts";

export type HeatmapLayer = "live" | "potential";
export type HeatmapLevel = "district" | "cell" | "location";

export interface HeatmapFilters {
  layer: HeatmapLayer;
  level: HeatmapLevel;
  from?: string;
  to?: string;
  state?: string;
  district?: string;
  category?: string;
  amount_band?: number;
  min_confidence?: number;
  bbox?: string;
}

export interface HeatCell {
  id: string;
  kind: string;
  name: string | null;
  lat: number;
  lon: number;
  value: number;
  alert_count: number;
}

export interface LegendData {
  min: number;
  max: number;
  unit: string;
  note: string;
}

export interface HeatmapResponse {
  layer: HeatmapLayer;
  level: HeatmapLevel;
  generated_at: string;
  version: number;
  cells: HeatCell[];
  suppressed_count: number;
  legend: LegendData;
}

export interface Region {
  id: string;
  level: "state" | "district";
  name: string;
  parent_id: string | null;
  geojson_ref: string | null;
  lat?: number;
  lon?: number;
}

export interface LocationPoint {
  id: string;
  kind: "ATM" | "BRANCH" | "AGENT";
  bank_id: string;
  lat: number;
  lon: number;
  district_id: string;
  cell_id: string;
  display_name: string;
  area_type: string;
}

export interface HotspotContributingAlert {
  id: string;
  cluster_ref: string;
  severity: Severity;
  status: AlertStatus;
  confidence: number;
  window_end: string;
  reason?: string;
}

export interface HotspotDetail {
  id: string;
  kind: string;
  name: string;
  lat: number;
  lon: number;
  value: number;
  alert_count: number;
  contributing_alerts: HotspotContributingAlert[];
}
