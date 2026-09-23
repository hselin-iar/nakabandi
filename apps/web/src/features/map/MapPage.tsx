/**
 * MapPage.tsx — GIS Risk Heatmap Dashboard (DOC 3 M3, DOC 4 Step C5).
 *
 * Implements interactive risk forecast visualization over the four demo states
 * (UP, MH, RJ, HR), resolution drill-down (district, cell, location), time slider replay,
 * and robust automatic fallback to TableView on WebGL failure.
 */

import React, { useState, useEffect, useRef } from "react";
import { useHeatmap, FIXTURE_HOTSPOT_ALERTS } from "./useHeatmap";
import { useRegions } from "./useRegions";
import { FilterPanel } from "./FilterPanel";
import { TimeSlider } from "./TimeSlider";
import { Legend } from "./Legend";
import { HotspotDrawer } from "./HotspotDrawer";
import { TableViewFallback } from "./TableViewFallback";
import { MapLibreAdapter, BOUNDARIES_FILL_LAYER_ID } from "./maplibre/MapLibreAdapter";
import { cellsToGeoJSON, CELLS_FILL_LAYER_ID } from "./layers/cellsLayer";
import type { MapAdapter } from "./MapAdapter";
import type {
  HeatmapFilters,
  HotspotDetail,
  HotspotContributingAlert,
} from "./types";

const STATE_BOUNDS: Record<string, [[number, number], [number, number]]> = {
  UP: [
    [77.0, 23.5],
    [84.8, 30.5],
  ],
  MH: [
    [72.5, 15.5],
    [81.0, 22.2],
  ],
  RJ: [
    [69.5, 23.0],
    [78.5, 30.2],
  ],
  HR: [
    [74.4, 27.5],
    [77.6, 31.0],
  ],
};

const ALL_STATES_BOUNDS: [[number, number], [number, number]] = [
  [69.0, 15.0],
  [85.0, 31.0],
];

export default function MapPage() {
  const [filters, setFilters] = useState<HeatmapFilters>({
    layer: "live",
    level: "cell",
  });

  const [timeOffsetHours, setTimeOffsetHours] = useState<number>(0);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<"map" | "table">("map");
  const [webGlFailed, setWebGlFailed] = useState<boolean>(false);
  const [webGlErrorMsg, setWebGlErrorMsg] = useState<string>("");

  const [selectedHotspot, setSelectedHotspot] = useState<HotspotDetail | null>(
    null,
  );

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const adapterRef = useRef<MapAdapter | null>(null);

  const { data: heatmapData } = useHeatmap(filters);
  const { regions, bundledGeoJSON } = useRegions();

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

    let isMounted = true;
    const adapter = new MapLibreAdapter();
    adapterRef.current = adapter;

    adapter
      .init(mapContainerRef.current, { center: [76.5, 24.5], zoom: 5 })
      .then(() => {
        if (!isMounted) return;

        // Set base boundaries from bundled GeoJSON with zero network tile requests
        adapter.setLayerData(BOUNDARIES_FILL_LAYER_ID, bundledGeoJSON);

        // Click handler for cells
        adapter.onFeatureClick(CELLS_FILL_LAYER_ID, (feature) => {
          if (!feature || typeof feature !== "object" || !("properties" in feature)) return;
          const props = (feature as { properties?: Record<string, unknown> }).properties;
          if (!props) return;
          handleOpenHotspot({
            id: String(props.id),
            kind: String(props.kind ?? "cell"),
            name: String(props.name ?? props.id),
            lat: Number(props.lat ?? 0),
            lon: Number(props.lon ?? 0),
            value: Number(props.value ?? 0),
            alert_count: Number(props.alert_count ?? 0),
          });
        });
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
    };
  }, [bundledGeoJSON]);

  // Update map data when heatmap cells or boundaries change
  useEffect(() => {
    if (!adapterRef.current || !adapterRef.current.isReady() || !heatmapData) {
      return;
    }

    const geojson = cellsToGeoJSON(heatmapData.cells);
    adapterRef.current.setLayerData(CELLS_FILL_LAYER_ID, geojson);
  }, [heatmapData]);

  // Adjust map bounds when state filter changes
  useEffect(() => {
    if (!adapterRef.current || !adapterRef.current.isReady()) return;

    if (filters.state && STATE_BOUNDS[filters.state]) {
      adapterRef.current.fitTo(STATE_BOUNDS[filters.state]);
    } else {
      adapterRef.current.fitTo(ALL_STATES_BOUNDS);
    }
  }, [filters.state]);

  function handleFilterChange(updated: Partial<HeatmapFilters>) {
    setFilters((prev) => ({ ...prev, ...updated }));
  }

  function handleResetFilters() {
    setFilters({
      layer: "live",
      level: "cell",
    });
  }

  function handleTimeOffsetChange(hours: number) {
    setTimeOffsetHours(hours);
    setIsPaused(hours !== 0);
  }

  function handleReturnToLive() {
    setTimeOffsetHours(0);
    setIsPaused(false);
  }

  function handleOpenHotspot(cell: {
    id: string;
    kind: string;
    name: string;
    lat: number;
    lon: number;
    value: number;
    alert_count: number;
  }) {
    // Correlate with active fixture alerts in the same vicinity or cluster
    let matchingAlerts: HotspotContributingAlert[] = FIXTURE_HOTSPOT_ALERTS.filter(
      (a) =>
        a.cluster_ref.includes(cell.id) ||
        (cell.name && a.target_name.toLowerCase().includes(cell.name.toLowerCase().split(" ")[0])),
    );
    if (matchingAlerts.length === 0) {
      matchingAlerts = FIXTURE_HOTSPOT_ALERTS.slice(0, 3);
    } else {
      matchingAlerts = matchingAlerts.slice(0, 3);
    }

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
            Spatial forecast intensity & persistence rollups across UP, MH, RJ, and HR.
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
      </div>

      {/* Hotspot Inspection Drawer */}
      <HotspotDrawer
        hotspot={selectedHotspot}
        onClose={() => setSelectedHotspot(null)}
      />
    </div>
  );
}
