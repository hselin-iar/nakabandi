/**
 * MapPage.tsx — GIS Risk Heatmap Dashboard (DOC 3 M3, DOC 4 Step C5).
 *
 * Implements interactive risk forecast visualization over the four demo states
 * (UP, MH, HR, JH), resolution drill-down (district, cell, location), time slider replay,
 * and robust automatic fallback to TableView on WebGL failure.
 */

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useHeatmap } from "./useHeatmap";
import { useRegions } from "./useRegions";
import { useLocations } from "./useLocations";
import { useAlerts, useAlert } from "../alerts/api/useAlerts";
import { useSimTime } from "../../shared/stream/useStream";
import { FilterPanel } from "./FilterPanel";
import { TimeSlider } from "./TimeSlider";
import { Legend } from "./Legend";
import { HotspotDrawer } from "./HotspotDrawer";
import { TableViewFallback } from "./TableViewFallback";
import {
  MapLibreAdapter,
  BOUNDARIES_FILL_LAYER_ID,
  HEATMAP_LAYER_ID,
} from "./maplibre/MapLibreAdapter";
import { heatCellsToPointGeoJSON } from "./layers/heatmapLayer";
import { locationsToGeoJSON, LOCATIONS_CIRCLE_LAYER_ID } from "./layers/locationsLayer";
import { alertsToGeoJSON, ALERTS_POINT_LAYER_ID } from "./layers/alertsLayer";
import {
  buildRadarGeoJSON,
  radarVerdictColor,
  RADAR_LINE_LAYER_ID,
} from "./layers/radarLayer";
import type { MapAdapter } from "./MapAdapter";
import type {
  HeatmapFilters,
  HeatmapLevel,
  HotspotDetail,
  HotspotContributingAlert,
} from "./types";

// Zoom bands driving resolution — replaces a disconnected Resolution dropdown as the sole
// input (§7.3): zoomed out shows district rollups, zooming in reveals cell then location
// level. Aligned with the existing HEATMAP_POINT_LAYER_ID minzoom (9) for point precision.
const ZOOM_LEVEL_BREAKS: { max: number; level: HeatmapLevel }[] = [
  { max: 6.5, level: "district" },
  { max: 9.5, level: "cell" },
  { max: Infinity, level: "location" },
];

function levelForZoom(zoom: number): HeatmapLevel {
  return (ZOOM_LEVEL_BREAKS.find((b) => zoom < b.max) ?? ZOOM_LEVEL_BREAKS[ZOOM_LEVEL_BREAKS.length - 1]).level;
}

// A zoom comfortably inside each level's band, for the reverse direction (manual pick -> zoom).
const ZOOM_FOR_LEVEL: Record<HeatmapLevel, number> = {
  district: 5.5,
  cell: 8,
  location: 11,
};

const STATE_BOUNDS: Record<string, [[number, number], [number, number]]> = {
  UP: [
    [77.0, 23.5],
    [84.8, 30.5],
  ],
  MH: [
    [72.5, 15.5],
    [81.0, 22.2],
  ],
  JH: [
    [83.3, 21.9],
    [87.9, 25.3],
  ],
  HR: [
    [74.4, 27.5],
    [77.6, 31.0],
  ],
};

const ALL_STATES_BOUNDS: [[number, number], [number, number]] = [
  [72.5, 15.5],
  [87.9, 31.0],
];

export default function MapPage() {
  const [filters, setFilters] = useState<HeatmapFilters>({
    layer: "live",
    level: "cell",
  });

  // timeOffsetHours drives both the slider UI and filters.from/to.
  // isPaused is derived: any non-zero offset means we are replaying.
  const [timeOffsetHours, setTimeOffsetHours] = useState<number>(0);
  const isPaused = timeOffsetHours !== 0;

  // Live sim time from SSE stream — used as replay baseline.
  const currentSimTime = useSimTime();

  const [viewMode, setViewMode] = useState<"map" | "table">("map");
  const [webGlFailed, setWebGlFailed] = useState<boolean>(false);
  const [webGlErrorMsg, setWebGlErrorMsg] = useState<string>("");
  const [mapReady, setMapReady] = useState<boolean>(false);

  const [selectedHotspot, setSelectedHotspot] = useState<HotspotDetail | null>(
    null,
  );

  // Interception Radar (§7.1) — the alert currently tracked on the map, if any.
  const [radarAlertId, setRadarAlertId] = useState<string | null>(null);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const adapterRef = useRef<MapAdapter | null>(null);
  const radarMarkerCleanupRef = useRef<(() => void) | null>(null);

  const { data: heatmapData } = useHeatmap(filters);
  const { regions, bundledGeoJSON } = useRegions();
  const { data: locations } = useLocations();
  const { data: alerts } = useAlerts();
  const { data: radarAlert } = useAlert(radarAlertId);

  // Coordinates for every kind of alert target (location, cell, or district) so the alerts
  // layer can place a marker regardless of which level the forecast fired at.
  const targetCoords = useMemo(() => {
    const map: Record<string, [number, number]> = {};
    for (const loc of locations ?? []) map[loc.id] = [loc.lon, loc.lat];
    for (const cell of heatmapData?.cells ?? []) map[cell.id] = [cell.lon, cell.lat];
    for (const region of regions) {
      if (region.lat != null && region.lon != null) map[region.id] = [region.lon, region.lat];
    }
    return map;
  }, [locations, heatmapData, regions]);

  // handleOpenHotspot must be defined before the init effect (used inside .then())
  const handleOpenHotspot = useCallback(
    (cell: {
      id: string;
      kind: string;
      name: string;
      lat: number;
      lon: number;
      value: number;
      alert_count: number;
    }) => {
      // Real alerts only — no fixture fallback (DOC1 §1.0 "nothing on our side is mocked").
      // Exact match works for location-level hotspots (alert.target.id is a location id, the
      // same id a location-resolution cell carries); a cell/district aggregate has no single
      // alert to point to without a location lookup, so it correctly shows the drawer's
      // existing "no active alerts linked" empty state rather than an invented list.
      const matchingAlerts: HotspotContributingAlert[] = (alerts ?? [])
        .filter((a) => a.target.id === cell.id)
        .slice(0, 3)
        .map((a) => ({
          id: a.id,
          cluster_ref: a.cluster_ref,
          severity: a.severity as HotspotContributingAlert["severity"],
          status: a.status as HotspotContributingAlert["status"],
          confidence: a.confidence,
          window_end: a.window_end,
        }));

      setSelectedHotspot({
        id: cell.id,
        kind: cell.kind,
        name: cell.name,
        lat: cell.lat,
        lon: cell.lon,
        value: cell.value,
        alert_count: cell.alert_count,
        contributing_alerts: matchingAlerts,
      });
    },
    [alerts],
  );

  // Initialize MapAdapter
  useEffect(() => {
    // If WebGL is not supported in this browser/environment (e.g. test or headless), fall back to table
    if (!MapLibreAdapter.isSupported()) {
      setWebGlFailed(true);
      setWebGlErrorMsg("WebGL is unavailable in this environment");
      setViewMode("table");
      return;
    }

    if (!mapContainerRef.current) return;

    // Reset mapReady so dependent effects know a new adapter is initialising
    setMapReady(false);

    let isMounted = true;
    const adapter = new MapLibreAdapter();
    adapterRef.current = adapter;

    adapter
      .init(mapContainerRef.current, { center: [79.5, 24.5], zoom: 5.5 })
      .then(() => {
        if (!isMounted) return;

        // Set base boundaries from bundled GeoJSON with zero network tile requests
        adapter.setLayerData(BOUNDARIES_FILL_LAYER_ID, bundledGeoJSON);

        // Frame the demo states
        if (filters.state && STATE_BOUNDS[filters.state]) {
          adapter.fitTo(STATE_BOUNDS[filters.state]);
        } else {
          adapter.fitTo(ALL_STATES_BOUNDS);
        }

        // Click handler for heatmap point layer (visible at zoom 9+)
        adapter.onFeatureClick(HEATMAP_LAYER_ID, (feature) => {
          if (!feature || typeof feature !== "object" || !("properties" in feature)) return;
          const props = (feature as { properties?: Record<string, unknown> }).properties;
          if (!props) return;
          handleOpenHotspot({
            id: String(props.id),
            kind: String(props.kind ?? "cell"),
            name: String(props.name ?? props.id),
            lat: Number(props.lat ?? 0),
            lon: Number(props.lon ?? 0),
            value: Number(props.intensity ?? props.value ?? 0),
            alert_count: Number(props.alert_count ?? 0),
          });
        });

        // Zoom-bound resolution (§7.3): bind level to the map's own zoom instead of a
        // disconnected dropdown. levelForZoomRef avoids a stale closure across re-inits.
        adapter.onZoomChange?.((zoom) => {
          const nextLevel = levelForZoom(zoom);
          setFilters((prev) => (prev.level === nextLevel ? prev : { ...prev, level: nextLevel }));
        });

        // Signal that the map is ready — this re-triggers all data-push effects
        // below, ensuring data that arrived before init() resolved is not lost.
        setMapReady(true);
      })
      .catch((err) => {
        if (!isMounted) return;
        setWebGlFailed(true);
        setWebGlErrorMsg(err?.message || "Failed to initialize WebGL canvas");
        setViewMode("table");
      });

    return () => {
      isMounted = false;
      adapter.destroy();
      adapterRef.current = null;
      setMapReady(false);
    };
    // Deliberately re-runs only on bundledGeoJSON: filters.state/handleOpenHotspot are read
    // via refs/functional setState inside the closure, not captured as reactive deps.
  }, [bundledGeoJSON]);

  // Push heatmap points to the smooth density heatmap layer.
  useEffect(() => {
    if (!mapReady || !adapterRef.current || !adapterRef.current.isReady() || !heatmapData) {
      return;
    }
    const geojson = heatCellsToPointGeoJSON(heatmapData.cells);
    adapterRef.current.setLayerData(HEATMAP_LAYER_ID, geojson);
  }, [mapReady, heatmapData]);

  // Push bank infrastructure locations to the map.
  useEffect(() => {
    if (!mapReady || !adapterRef.current || !adapterRef.current.isReady() || !locations) return;
    adapterRef.current.setLayerData(LOCATIONS_CIRCLE_LAYER_ID, locationsToGeoJSON(locations));
  }, [mapReady, locations]);

  // Push alert point markers to the map.
  useEffect(() => {
    if (!mapReady || !adapterRef.current || !adapterRef.current.isReady() || !alerts) return;
    adapterRef.current.setLayerData(ALERTS_POINT_LAYER_ID, alertsToGeoJSON(alerts, targetCoords));
  }, [mapReady, alerts, targetCoords]);

  // Adjust map bounds when state filter changes
  useEffect(() => {
    if (!mapReady || !adapterRef.current || !adapterRef.current.isReady()) return;

    if (filters.state && STATE_BOUNDS[filters.state]) {
      adapterRef.current.fitTo(STATE_BOUNDS[filters.state]);
    } else {
      adapterRef.current.fitTo(ALL_STATES_BOUNDS);
    }
  }, [mapReady, filters.state]);

  // Interception Radar: the tracked alert's best_unit position -> target position vector,
  // plus a unit marker. A computed illustration of eta_min, not live GPS (§7.1, §9.4).
  const radarLatestAssessment = radarAlert?.interception.at(-1) ?? null;
  const radarBestUnit = radarLatestAssessment?.best_unit ?? null;
  const radarTargetCoords = radarAlert ? targetCoords[String(radarAlert.target.id)] : undefined;

  useEffect(() => {
    if (!mapReady || !adapterRef.current || !adapterRef.current.isReady()) return;

    radarMarkerCleanupRef.current?.();
    radarMarkerCleanupRef.current = null;

    if (!radarBestUnit || !radarTargetCoords || !radarLatestAssessment) {
      adapterRef.current.setLayerData(RADAR_LINE_LAYER_ID, buildRadarGeoJSON(null));
      return;
    }

    const unitCoords: [number, number] = [radarBestUnit.lon, radarBestUnit.lat];
    adapterRef.current.setLayerData(
      RADAR_LINE_LAYER_ID,
      buildRadarGeoJSON({
        unit: unitCoords,
        target: radarTargetCoords,
        verdict: radarLatestAssessment.verdict,
      }),
    );

    if (adapterRef.current.addHtmlMarker) {
      const el = document.createElement("div");
      el.className = "nk-radar-unit-marker";
      el.style.color = radarVerdictColor(radarLatestAssessment.verdict);
      el.textContent = "🚓";
      el.title = `${radarBestUnit.unit_kind} ${radarBestUnit.unit_id} — ${radarBestUnit.eta_min.toFixed(1)} min ETA (computed estimate)`;
      radarMarkerCleanupRef.current = adapterRef.current.addHtmlMarker(el, unitCoords);
    }
  }, [mapReady, radarBestUnit, radarTargetCoords, radarLatestAssessment]);

  // Clear the radar line/marker when its alert stops being tracked.
  useEffect(() => {
    return () => {
      radarMarkerCleanupRef.current?.();
      radarMarkerCleanupRef.current = null;
    };
  }, []);

  function handleFilterChange(updated: Partial<HeatmapFilters>) {
    setFilters((prev) => ({ ...prev, ...updated }));
    // Manual resolution pick also nudges the camera into that level's zoom band, so the
    // dropdown and zoom-bound switching stay in agreement rather than fighting each other.
    if (updated.level && adapterRef.current?.setZoom) {
      adapterRef.current.setZoom(ZOOM_FOR_LEVEL[updated.level]);
    }
  }

  function handleTrackAlert(alertId: string) {
    setRadarAlertId(alertId);
  }

  function handleClearRadar() {
    setRadarAlertId(null);
  }

  function handleResetFilters() {
    setFilters({
      layer: "live",
      level: "cell",
    });
    setTimeOffsetHours(0);
  }

  function handleTimeOffsetChange(hours: number) {
    setTimeOffsetHours(hours);

    if (hours === 0) {
      // Back to live — remove time window from query
      setFilters((prev) => {
        const { from: _f, to: _t, ...rest } = prev;
        return rest as HeatmapFilters;
      });
      return;
    }

    // Compute replay window: 1-hour slot ending at the chosen offset.
    // Use sim time if available, otherwise wall clock.
    const base = currentSimTime
      ? new Date(currentSimTime)
      : new Date();
    const windowEnd = new Date(base.getTime() + hours * 3600 * 1000);
    const windowStart = new Date(windowEnd.getTime() - 3600 * 1000);

    setFilters((prev) => ({
      ...prev,
      from: windowStart.toISOString(),
      to: windowEnd.toISOString(),
    }));
  }

  function handleReturnToLive() {
    setTimeOffsetHours(0);
    setFilters((prev) => {
      const { from: _f, to: _t, ...rest } = prev;
      return rest as HeatmapFilters;
    });
  }

  const cells = heatmapData?.cells ?? [];
  const legend = heatmapData?.legend ?? {
    min: 0,
    max: 1,
    unit: "Intensity (Mass)",
    note: "Persistence estimate of recent forecast intensity over the next 72 h",
  };
  const suppressedCount = heatmapData?.suppressed_count ?? 0;

  return (
    <div className="nk-map-page">
      {/* Header with Title and Mode Switcher */}
      <header className="nk-map-header">
        <div>
          <h1 className="nk-map-title">GIS Risk Heatmap Dashboard</h1>
          <p className="nk-map-subtitle">
            Spatial forecast intensity & persistence rollups across UP, MH, HR, and JH.
          </p>
        </div>

        <div className="nk-map-view-toggle">
          <button
            type="button"
            className={`nk-btn nk-btn--sm ${viewMode === "map" ? "nk-btn--primary" : "nk-btn--outline"}`}
            onClick={() => setViewMode("map")}
            disabled={webGlFailed}
            aria-pressed={viewMode === "map"}
          >
            🗺️ Map View
          </button>
          <button
            type="button"
            className={`nk-btn nk-btn--sm ${viewMode === "table" ? "nk-btn--primary" : "nk-btn--outline"}`}
            onClick={() => setViewMode("table")}
            aria-pressed={viewMode === "table"}
          >
            📊 Table View
          </button>
        </div>
      </header>

      {/* Filter Bar */}
      <FilterPanel
        filters={filters}
        regions={regions}
        onChange={handleFilterChange}
        onReset={handleResetFilters}
      />

      {/* Main Map / Table Stage */}
      <div className="nk-map-stage">
        {/* Replay Time Slider */}
        <div className="nk-map-stage__slider">
          <TimeSlider
            isPaused={isPaused}
            offsetHours={timeOffsetHours}
            onOffsetChange={handleTimeOffsetChange}
            onReturnToLive={handleReturnToLive}
          />
        </div>

        {/* View Content: Map Canvas vs Table Fallback */}
        {viewMode === "table" || webGlFailed ? (
          <TableViewFallback
            cells={cells}
            reason={webGlFailed ? webGlErrorMsg : undefined}
            onSelectCell={(c) =>
              handleOpenHotspot({
                id: c.id,
                kind: c.kind,
                name: c.name ?? c.id,
                lat: c.lat,
                lon: c.lon,
                value: c.value,
                alert_count: c.alert_count,
              })
            }
            onRetryWebGL={
              webGlFailed
                ? () => {
                    setWebGlFailed(false);
                    setViewMode("map");
                  }
                : undefined
            }
          />
        ) : (
          <div className="nk-map-viewport">
            <div
              ref={mapContainerRef}
              className="nk-map-canvas"
              data-testid="maplibre-container"
              aria-label="MapLibre GIS Canvas"
            />
          </div>
        )}

        {/* Floating Legend */}
        <div className="nk-map-stage__legend">
          <Legend legend={legend} suppressedCount={suppressedCount} />
        </div>

        {/* Interception Radar panel — visible only while an alert is tracked (§7.1) */}
        {radarAlertId && (
          <div className="nk-map-stage__radar-panel" role="status" aria-label="Interception radar">
            <div className="nk-radar-panel__header">
              <span className="nk-radar-panel__title">📡 Interception Radar</span>
              <button
                type="button"
                className="nk-btn nk-btn--ghost nk-btn--sm"
                onClick={handleClearRadar}
              >
                ✕ Clear
              </button>
            </div>
            {!radarAlert ? (
              <p className="nk-text-xs text-muted">Loading assessment…</p>
            ) : !radarBestUnit ? (
              <p className="nk-text-xs text-muted">
                No response unit is in reach of this target — interception is not currently
                possible.
              </p>
            ) : (
              <>
                <p className="nk-text-xs">
                  {radarBestUnit.unit_kind} <strong>{radarBestUnit.unit_id}</strong> —{" "}
                  {radarBestUnit.eta_min.toFixed(1)} min ETA · verdict{" "}
                  <strong>{radarLatestAssessment?.verdict}</strong>
                </p>
                {radarAlert.forecast?.levels?.location?.abstained && (
                  <p className="nk-radar-panel__abstain nk-text-xs">
                    ⚠ District-level only — insufficient confidence for a specific location at
                    this target.
                  </p>
                )}
                <p className="nk-radar-panel__disclaimer nk-text-xs text-muted">
                  Illustrative vector computed from the unit's ETA — not a live GPS feed.
                </p>
              </>
            )}
          </div>
        )}
      </div>

      {/* Hotspot Inspection Drawer */}
      <HotspotDrawer
        hotspot={selectedHotspot}
        onClose={() => setSelectedHotspot(null)}
        onTrackAlert={handleTrackAlert}
      />
    </div>
  );
}
