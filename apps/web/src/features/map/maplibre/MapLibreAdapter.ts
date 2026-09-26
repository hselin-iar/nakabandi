/**
 * MapLibreAdapter.ts — Concrete MapLibre GL implementation of MapAdapter.
 *
 * CRITICAL ARCHITECTURAL INVARIANT (DOC 3 M3, DOC 4 Step C5):
 *   This is the ONLY file in the entire repository that imports "maplibre-gl".
 *   Basemap: OpenFreeMap Dark — near-black vector map, no API key.
 *   Data overlays: smooth GPU heatmap + alert markers + boundary outlines.
 *   If WebGL is unavailable, initialization fails gracefully to TableViewFallback.
 */

import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, GeoJSONSource } from "maplibre-gl";
import type { MapAdapter, MapInitOptions } from "../MapAdapter";
import {
  HEATMAP_SOURCE_ID,
  HEATMAP_LAYER_ID,
  HEATMAP_POINT_LAYER_ID,
} from "../layers/heatmapLayer";
import {
  LOCATIONS_SOURCE_ID,
  LOCATIONS_CIRCLE_LAYER_ID,
} from "../layers/locationsLayer";
import {
  ALERTS_SOURCE_ID,
  ALERTS_HALO_LAYER_ID,
  ALERTS_POINT_LAYER_ID,
} from "../layers/alertsLayer";
import { RADAR_SOURCE_ID, RADAR_LINE_LAYER_ID } from "../layers/radarLayer";
import {
  HOT_RADAR_SOURCE_ID,
  HOT_RADAR_LAYER_ID,
  HOT_RADAR_IMAGE_ID,
  createPulsingRadarImage,
} from "../layers/radarIconLayer";

// ---------------------------------------------------------------------------
// MapLibre GL v6 + Vite worker fix
// ---------------------------------------------------------------------------
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker?url";
maplibregl.setWorkerUrl(workerUrl as string);

// ---------------------------------------------------------------------------
// Exported layer IDs used by MapPage to set data
// ---------------------------------------------------------------------------
export const BOUNDARIES_SOURCE_ID = "nk-boundaries-source";
export const BOUNDARIES_FILL_LAYER_ID = "nk-boundaries-fill";
export const BOUNDARIES_LINE_LAYER_ID = "nk-boundaries-line";

// Re-export heatmap layer ID so MapPage can call setLayerData with it
export { HEATMAP_LAYER_ID };

/** The selected entity's highlight ring (linked selection). */
export const SELECTION_SOURCE_ID = "nk-selection-source";
export const SELECTION_LAYER_ID = "nk-selection-ring";

/**
 * Basemap: OpenFreeMap Dark
 * Near-black vector basemap matching the tactical theme — no API key required.
 * Style URL: https://tiles.openfreemap.org/styles/dark
 * (Was Positron, a light style, before the overhaul reskin. Still an online tile source:
 * the offline Compose path relies on the bundled boundary GeoJSON when tiles are unreachable.)
 */
const BASEMAP_STYLE_URL = "https://tiles.openfreemap.org/styles/dark";

export class MapLibreAdapter implements MapAdapter {
  private map: MapLibreMap | null = null;
  private isLoaded = false;
  private clickHandlers: Map<string, (feature: unknown) => void> = new Map();
  private pendingLayerData: Map<string, GeoJSON.FeatureCollection | GeoJSON.Feature> = new Map();
  /** How many hot-cell radar markers currently exist, and whether their layer is shown. */
  private hotRadarCount = 0;
  private hotRadarVisible = true;
  private radarAnimationHandle: ReturnType<typeof setInterval> | null = null;
  private radarDashOffset = 0;

  /**
   * Static helper to check WebGL support without initializing full map.
   */
  public static isSupported(): boolean {
    try {
      if (typeof window === "undefined" || typeof document === "undefined") {
        return false;
      }
      const canvas = document.createElement("canvas");
      const gl =
        canvas.getContext("webgl") ||
        canvas.getContext("experimental-webgl") ||
        canvas.getContext("webgl2");
      return Boolean(gl);
    } catch {
      return false;
    }
  }

  /** Push the dark basemap to near-black and mute its labels so the heat carries the contrast. */
  private darkenBasemap(): void {
    const map = this.map;
    if (!map) return;
    for (const layer of map.getStyle().layers ?? []) {
      try {
        if (layer.type === "background") {
          map.setPaintProperty(layer.id, "background-color", "#04060a");
        } else if (layer.type === "fill") {
          map.setPaintProperty(layer.id, "fill-opacity", 0.55);
        } else if (layer.type === "line") {
          map.setPaintProperty(layer.id, "line-opacity", 0.45);
        } else if (layer.type === "symbol") {
          map.setPaintProperty(layer.id, "text-opacity", 0.5);
          map.setPaintProperty(layer.id, "icon-opacity", 0.4);
        }
      } catch {
        /* a layer without that paint property: leave it as styled */
      }
    }
  }

  public isReady(): boolean {
    return this.isLoaded && this.map !== null;
  }

  public async init(
    container: HTMLElement,
    options: MapInitOptions = {},
  ): Promise<void> {
    if (!MapLibreAdapter.isSupported()) {
      throw new Error("WebGL is unavailable in this environment.");
    }

    return new Promise<void>((resolve, reject) => {
      try {
        const center = options.center ?? [79.5, 24.5]; // Centered across UP/MH/HR/JH
        const zoom = options.zoom ?? 5.5;

        const mapInstance = new maplibregl.Map({
          container,
          style: BASEMAP_STYLE_URL,
          center,
          zoom,
          interactive: options.interactive ?? true,
          attributionControl: { compact: true },
        });
        this.map = mapInstance;

        mapInstance.on("load", () => {
          this.isLoaded = true;
          try {
            this.darkenBasemap();
            this.setupDataLayers();

            // Apply any pending data that arrived before load event
            this.pendingLayerData.forEach((data, layerId) => {
              this.setLayerData(layerId, data);
            });
            this.pendingLayerData.clear();
            this.startRadarAnimation();
          } catch (err) {
            console.error("MapLibreAdapter: setupDataLayers failed", err);
            reject(err instanceof Error ? err : new Error("Failed to set up map layers"));
            return;
          }

          resolve();
        });

        mapInstance.on("error", (e) => {
          if (!this.isLoaded) {
            reject(e.error || new Error("Failed to initialize MapLibre GL map"));
          }
        });
      } catch (err) {
        reject(err);
      }
    });
  }

  private setupDataLayers(): void {
    if (!this.map) return;

    const emptyPoints: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: [],
    };

    // -----------------------------------------------------------------------
    // 1. State boundary outlines (subtle on light basemap)
    // -----------------------------------------------------------------------
    if (!this.map.getSource(BOUNDARIES_SOURCE_ID)) {
      this.map.addSource(BOUNDARIES_SOURCE_ID, {
        type: "geojson",
        data: emptyPoints,
      });

      this.map.addLayer({
        id: BOUNDARIES_FILL_LAYER_ID,
        type: "fill",
        source: BOUNDARIES_SOURCE_ID,
        paint: {
          "fill-color": "#6366f1",
          "fill-opacity": 0.04,   // very subtle — let the street map breathe
        },
      });

      this.map.addLayer({
        id: BOUNDARIES_LINE_LAYER_ID,
        type: "line",
        source: BOUNDARIES_SOURCE_ID,
        paint: {
          "line-color": "#4f46e5",   // indigo — visible but not overpowering
          "line-width": 2.5,
          "line-dasharray": [4, 3],
          "line-opacity": 0.7,
        },
      });
    }

    // -----------------------------------------------------------------------
    // 2. Smooth density heatmap (kernel-style, GPU-accelerated)
    //    Uses MapLibre native 'heatmap' layer type on raw Point GeoJSON.
    // -----------------------------------------------------------------------
    if (!this.map.getSource(HEATMAP_SOURCE_ID)) {
      this.map.addSource(HEATMAP_SOURCE_ID, {
        type: "geojson",
        data: emptyPoints,
      });

      // Main smooth density heatmap (inserted under the basemap's labels so place names stay legible)
      const firstLabel = this.map.getStyle().layers?.find((l) => l.type === "symbol")?.id;
      this.map.addLayer({
        id: HEATMAP_LAYER_ID,
        type: "heatmap",
        source: HEATMAP_SOURCE_ID,
        paint: {
          // Weight each point by the 'intensity' property (0–1)
          "heatmap-weight": [
            "interpolate", ["linear"], ["get", "intensity"],
            0, 0,
            1, 1,
          ],
          // Boost intensity — higher at state-overview zoom so blobs are visible
          "heatmap-intensity": [
            "interpolate", ["linear"], ["zoom"],
            3,  2.2,
            6,  3.5,
            10, 5.5,
            14, 8,
          ],
          // Ops-centre ramp: transparent black → dark red → crimson → orange → white-hot core
          "heatmap-color": [
            "interpolate", ["linear"], ["heatmap-density"],
            0,    "rgba(0,0,0,0)",
            0.08, "rgba(60,0,8,0.45)",
            0.25, "rgba(139,0,20,0.7)",
            0.45, "rgba(220,20,40,0.85)",
            0.65, "rgba(255,90,20,0.92)",
            0.85, "rgba(255,190,80,0.97)",
            1,    "rgb(255,250,235)",
          ],
          // Large radius at state overview (zoom 5–6), tighter at street level
          "heatmap-radius": [
            "interpolate", ["linear"], ["zoom"],
            3,  80,
            5,  100,
            8,  60,
            12, 40,
            15, 25,
          ],
          "heatmap-opacity": 0.95,
        },
      }, firstLabel);

      // Optional: individual point dots at high zoom levels for precision
      this.map.addLayer({
        id: HEATMAP_POINT_LAYER_ID,
        type: "circle",
        source: HEATMAP_SOURCE_ID,
        minzoom: 9,   // Only show dots when zoomed in close
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            9, 3,
            14, 8,
          ],
          "circle-color": [
            "interpolate", ["linear"], ["get", "intensity"],
            0,    "#3b82f6",
            0.25, "#f59e0b",
            0.6,  "#f97316",
            0.85, "#ef4444",
            1,    "#b91c1c",
          ],
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#090D12",
          "circle-opacity": 0.9,
        },
      });

      this.bindLayerClick(HEATMAP_POINT_LAYER_ID);
    }

    // -----------------------------------------------------------------------
    // 3. Bank infrastructure locations (ATM / branch / BC agent points)
    // -----------------------------------------------------------------------
    if (!this.map.getSource(LOCATIONS_SOURCE_ID)) {
      this.map.addSource(LOCATIONS_SOURCE_ID, {
        type: "geojson",
        data: emptyPoints,
      });

      this.map.addLayer({
        id: LOCATIONS_CIRCLE_LAYER_ID,
        type: "circle",
        source: LOCATIONS_SOURCE_ID,
        paint: {
          "circle-color": ["coalesce", ["get", "color"], "#38bdf8"],
          "circle-radius": 5,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
          "circle-opacity": 0.9,
        },
      });

      this.bindLayerClick(LOCATIONS_CIRCLE_LAYER_ID);
    }

    // -----------------------------------------------------------------------
    // 4. Active alert point markers (halo + core)
    // -----------------------------------------------------------------------
    if (!this.map.getSource(ALERTS_SOURCE_ID)) {
      this.map.addSource(ALERTS_SOURCE_ID, {
        type: "geojson",
        data: emptyPoints,
      });

      // Halo glow ring
      this.map.addLayer({
        id: ALERTS_HALO_LAYER_ID,
        type: "circle",
        source: ALERTS_SOURCE_ID,
        paint: {
          "circle-color": ["coalesce", ["get", "color"], "#ef4444"],
          "circle-radius": 16,
          "circle-opacity": 0.2,
          "circle-stroke-width": 2,
          "circle-stroke-color": ["coalesce", ["get", "color"], "#ef4444"],
          "circle-stroke-opacity": 0.5,
        },
      });

      // Core dot
      this.map.addLayer({
        id: ALERTS_POINT_LAYER_ID,
        type: "circle",
        source: ALERTS_SOURCE_ID,
        paint: {
          "circle-color": ["coalesce", ["get", "color"], "#ef4444"],
          "circle-radius": 6,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      this.bindLayerClick(ALERTS_POINT_LAYER_ID);
    }

    // -----------------------------------------------------------------------
    // 4b. Pulsing threat radar on the top few hottest cells (canvas-drawn icon).
    //     Capped upstream (pickHotCells); the image is idle unless it has something to show.
    // -----------------------------------------------------------------------
    if (!this.map.getSource(HOT_RADAR_SOURCE_ID)) {
      this.map.addSource(HOT_RADAR_SOURCE_ID, { type: "geojson", data: emptyPoints });
      this.map.addImage(
        HOT_RADAR_IMAGE_ID,
        createPulsingRadarImage(
          () => this.hotRadarCount > 0 && this.hotRadarVisible,
          () => this.map?.triggerRepaint(),
        ) as unknown as maplibregl.StyleImageInterface,
        { pixelRatio: 2 },
      );
      this.map.addLayer({
        id: HOT_RADAR_LAYER_ID,
        type: "symbol",
        source: HOT_RADAR_SOURCE_ID,
        layout: {
          "icon-image": HOT_RADAR_IMAGE_ID,
          "icon-allow-overlap": true,
          "icon-ignore-placement": true,
        },
      });
    }

    // -----------------------------------------------------------------------
    // 4c. Selection highlight ring (linked selection from alerts / palette / graph)
    // -----------------------------------------------------------------------
    if (!this.map.getSource(SELECTION_SOURCE_ID)) {
      this.map.addSource(SELECTION_SOURCE_ID, { type: "geojson", data: emptyPoints });
      this.map.addLayer({
        id: SELECTION_LAYER_ID,
        type: "circle",
        source: SELECTION_SOURCE_ID,
        paint: {
          "circle-radius": 22,
          "circle-color": "rgba(56, 189, 248, 0.08)",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#38BDF8",
        },
      });
    }

    // -----------------------------------------------------------------------
    // 5. Interception Radar — unit-to-target ETA vector (§7.1). Colour by
    //    verdict; an animated dash-offset gives a "closing the gap" motion
    //    cue. This is a computed illustration of eta_min, not a live GPS feed.
    // -----------------------------------------------------------------------
    if (!this.map.getSource(RADAR_SOURCE_ID)) {
      this.map.addSource(RADAR_SOURCE_ID, {
        type: "geojson",
        data: emptyPoints,
      });

      this.map.addLayer({
        id: RADAR_LINE_LAYER_ID,
        type: "line",
        source: RADAR_SOURCE_ID,
        layout: {
          "line-cap": "round",
        },
        paint: {
          "line-color": [
            "match",
            ["get", "verdict"],
            "INTERCEPTABLE", "#22c55e",
            "MARGINAL", "#f59e0b",
            "NOT_INTERCEPTABLE", "#ef4444",
            "#64748b",
          ],
          "line-width": 3,
          "line-dasharray": [0, 4, 3],
        },
      });
    }
  }

  /**
   * Marching-dash animation for the radar line — MapLibre/Mapbox GL has no native
   * line-dash-offset paint property, so "flow" is simulated by cycling through a
   * sequence of dasharray patterns with a shifting phase (the documented technique for
   * this). A decorative "closing the gap" motion cue, not a literal progress readout —
   * there is no live unit telemetry to animate against.
   */
  private static readonly RADAR_DASH_SEQUENCE: number[][] = [
    [0, 4, 3],
    [0.5, 4, 2.5],
    [1, 4, 2],
    [1.5, 4, 1.5],
    [2, 4, 1],
    [2.5, 4, 0.5],
    [3, 4, 0],
    [0, 0.5, 3, 3.5],
    [0, 1, 3, 3],
    [0, 1.5, 3, 2.5],
    [0, 2, 3, 2],
    [0, 2.5, 3, 1.5],
    [0, 3, 3, 1],
    [0, 3.5, 3, 0.5],
  ];

  private startRadarAnimation(): void {
    if (this.radarAnimationHandle) return;
    this.radarAnimationHandle = setInterval(() => {
      if (!this.map || !this.isLoaded || !this.map.getLayer(RADAR_LINE_LAYER_ID)) return;
      const seq = MapLibreAdapter.RADAR_DASH_SEQUENCE;
      this.radarDashOffset = (this.radarDashOffset + 1) % seq.length;
      this.map.setPaintProperty(RADAR_LINE_LAYER_ID, "line-dasharray", seq[this.radarDashOffset]);
    }, 60);
  }

  private stopRadarAnimation(): void {
    if (this.radarAnimationHandle) {
      clearInterval(this.radarAnimationHandle);
      this.radarAnimationHandle = null;
    }
  }

  private bindLayerClick(layerId: string): void {
    if (!this.map) return;

    this.map.on("click", layerId, (e) => {
      const handler = this.clickHandlers.get(layerId);
      if (handler && e.features && e.features.length > 0) {
        handler(e.features[0]);
      }
    });

    this.map.on("mouseenter", layerId, () => {
      if (this.map) this.map.getCanvas().style.cursor = "pointer";
    });

    this.map.on("mouseleave", layerId, () => {
      if (this.map) this.map.getCanvas().style.cursor = "";
    });
  }

  public setLayerData(
    layerId: string,
    data: GeoJSON.FeatureCollection | GeoJSON.Feature,
  ): void {
    if (!this.isLoaded || !this.map) {
      this.pendingLayerData.set(layerId, data);
      return;
    }

    // Map layerId → sourceId
    let sourceId = layerId;
    if (
      layerId === HEATMAP_LAYER_ID ||
      layerId === HEATMAP_POINT_LAYER_ID ||
      layerId === "cells" ||
      layerId === "heatmap"
    ) {
      sourceId = HEATMAP_SOURCE_ID;
    } else if (layerId === LOCATIONS_CIRCLE_LAYER_ID || layerId === "locations") {
      sourceId = LOCATIONS_SOURCE_ID;
    } else if (
      layerId === ALERTS_POINT_LAYER_ID ||
      layerId === ALERTS_HALO_LAYER_ID ||
      layerId === "alerts"
    ) {
      sourceId = ALERTS_SOURCE_ID;
    } else if (
      layerId === BOUNDARIES_FILL_LAYER_ID ||
      layerId === BOUNDARIES_LINE_LAYER_ID ||
      layerId === "boundaries"
    ) {
      sourceId = BOUNDARIES_SOURCE_ID;
    } else if (layerId === RADAR_LINE_LAYER_ID || layerId === "radar") {
      sourceId = RADAR_SOURCE_ID;
    } else if (layerId === HOT_RADAR_LAYER_ID) {
      sourceId = HOT_RADAR_SOURCE_ID;
      const features = (data as GeoJSON.FeatureCollection).features ?? [];
      this.hotRadarCount = features.length;
      this.map.triggerRepaint(); // wake the icon if it just gained something to draw
    } else if (layerId === SELECTION_LAYER_ID) {
      sourceId = SELECTION_SOURCE_ID;
    }

    const source = this.map.getSource(sourceId) as GeoJSONSource | undefined;
    if (source && typeof source.setData === "function") {
      source.setData(data);
    }
  }

  public setLayerVisibility(layerId: string, visible: boolean): void {
    if (!this.map || !this.isLoaded) return;
    const visibility = visible ? "visible" : "none";
    if (layerId === HOT_RADAR_LAYER_ID) {
      this.hotRadarVisible = visible;
      if (visible) this.map.triggerRepaint();
    }
    if (this.map.getLayer(layerId)) {
      this.map.setLayoutProperty(layerId, "visibility", visibility);
    }
  }

  public fitTo(
    bounds:
      | [number, number, number, number]
      | [[number, number], [number, number]],
  ): void {
    if (!this.map || !this.isLoaded) return;
    this.map.fitBounds(bounds, { padding: 60, duration: 800 });
  }

  public onFeatureClick(layerId: string, handler: (feature: unknown) => void): void {
    this.clickHandlers.set(layerId, handler);
  }

  public resize(): void {
    if (this.map) {
      this.map.resize();
    }
  }

  public destroy(): void {
    this.stopRadarAnimation();
    if (this.map) {
      this.clickHandlers.clear();
      this.pendingLayerData.clear();
      this.map.remove();
      this.map = null;
      this.isLoaded = false;
    }
  }

  public onZoomChange(handler: (zoom: number) => void): void {
    if (!this.map) return;
    this.map.on("zoomend", () => {
      if (this.map) handler(this.map.getZoom());
    });
  }

  public onPointerMove(handler: (lngLat: [number, number] | null) => void): void {
    if (!this.map) return;
    this.map.on("mousemove", (e) => handler([e.lngLat.lng, e.lngLat.lat]));
    this.map.on("mouseout", () => handler(null));
  }

  public onViewChange(handler: (view: { zoom: number }) => void): void {
    if (!this.map) return;
    const emit = () => {
      if (this.map) handler({ zoom: this.map.getZoom() });
    };
    this.map.on("move", emit);
    emit();
  }

  public flyTo(lngLat: [number, number], zoom?: number): void {
    if (!this.map || !this.isLoaded) return;
    this.map.flyTo({ center: lngLat, zoom: zoom ?? Math.max(this.map.getZoom(), 9), duration: 900 });
  }

  public setZoom(zoom: number): void {
    if (!this.map || !this.isLoaded) return;
    this.map.easeTo({ zoom, duration: 500 });
  }

  public addHtmlMarker(element: HTMLElement, lngLat: [number, number]): () => void {
    if (!this.map) return () => {};
    const marker = new maplibregl.Marker({ element, anchor: "center" })
      .setLngLat(lngLat)
      .addTo(this.map);
    return () => marker.remove();
  }
}
