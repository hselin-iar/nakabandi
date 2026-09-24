/**
 * MapLibreAdapter.ts — Concrete MapLibre GL implementation of MapAdapter.
 *
 * CRITICAL ARCHITECTURAL INVARIANT (DOC 3 M3, DOC 4 Step C5):
 *   This is the ONLY file in the entire repository that imports "maplibre-gl".
 *   Zero external CDN or tile server URLs are fetched (DOC 2 §2.7 offline NFR).
 *   If WebGL is unavailable, initialization fails gracefully, prompting the UI
 *   to render the TableViewFallback component.
 */

import * as maplibregl from "maplibre-gl";
import type { Map as MapLibreMap, StyleSpecification, GeoJSONSource } from "maplibre-gl";
import type { MapAdapter, MapInitOptions } from "../MapAdapter";
import {
  CELLS_SOURCE_ID,
  CELLS_FILL_LAYER_ID,
  CELLS_LINE_LAYER_ID,
} from "../layers/cellsLayer";
import {
  LOCATIONS_SOURCE_ID,
  LOCATIONS_CIRCLE_LAYER_ID,
} from "../layers/locationsLayer";
import {
  ALERTS_SOURCE_ID,
  ALERTS_HALO_LAYER_ID,
  ALERTS_POINT_LAYER_ID,
} from "../layers/alertsLayer";

export const BOUNDARIES_SOURCE_ID = "nk-boundaries-source";
export const BOUNDARIES_FILL_LAYER_ID = "nk-boundaries-fill";
export const BOUNDARIES_LINE_LAYER_ID = "nk-boundaries-line";

/**
 * 100% Offline style with zero CDN or external tile dependencies.
 */
const OFFLINE_MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "nk-base-bg",
      type: "background",
      paint: {
        "background-color": "#0d131f", // Dark theme grid background
      },
    },
  ],
};

export class MapLibreAdapter implements MapAdapter {
  private map: MapLibreMap | null = null;
  private isLoaded = false;
  private clickHandlers: Map<string, (feature: unknown) => void> = new Map();
  private pendingLayerData: Map<string, GeoJSON.FeatureCollection | GeoJSON.Feature> = new Map();

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
        const zoom = options.zoom ?? 5;

        const mapInstance = new maplibregl.Map({
          container,
          style: OFFLINE_MAP_STYLE,
          center,
          zoom,
          interactive: options.interactive ?? true,
          attributionControl: false,
        });
        this.map = mapInstance;

        mapInstance.on("load", () => {
          this.isLoaded = true;
          try {
            this.setupSourcesAndLayers();

            // Apply any pending data that arrived before load event
            this.pendingLayerData.forEach((data, layerId) => {
              this.setLayerData(layerId, data);
            });
            this.pendingLayerData.clear();
          } catch (err) {
            console.error("MapLibreAdapter: setupSourcesAndLayers failed", err);
            reject(err instanceof Error ? err : new Error("Failed to set up map layers"));
            return;
          }

          resolve();
        });

        mapInstance.on("error", (e) => {
          // Log or reject on fatal errors
          if (!this.isLoaded) {
            reject(e.error || new Error("Failed to initialize MapLibre GL map"));
          }
        });
      } catch (err) {
        reject(err);
      }
    });
  }

  private setupSourcesAndLayers(): void {
    if (!this.map) return;

    const emptyGeoJSON: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: [],
    };

    // 1. Boundaries (Demo states)
    if (!this.map.getSource(BOUNDARIES_SOURCE_ID)) {
      this.map.addSource(BOUNDARIES_SOURCE_ID, {
        type: "geojson",
        data: emptyGeoJSON,
      });

      this.map.addLayer({
        id: BOUNDARIES_FILL_LAYER_ID,
        type: "fill",
        source: BOUNDARIES_SOURCE_ID,
        paint: {
          "fill-color": "#1e293b",
          "fill-opacity": 0.35,
        },
      });

      this.map.addLayer({
        id: BOUNDARIES_LINE_LAYER_ID,
        type: "line",
        source: BOUNDARIES_SOURCE_ID,
        paint: {
          "line-color": "#475569",
          "line-width": 1.5,
          "line-dasharray": [2, 2],
        },
      });
    }

    // 2. Risk Cells Layer
    if (!this.map.getSource(CELLS_SOURCE_ID)) {
      this.map.addSource(CELLS_SOURCE_ID, {
        type: "geojson",
        data: emptyGeoJSON,
      });

      this.map.addLayer({
        id: CELLS_FILL_LAYER_ID,
        type: "fill",
        source: CELLS_SOURCE_ID,
        paint: {
          "fill-color": ["coalesce", ["get", "color"], "#3b82f6"],
          "fill-opacity": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "value"], 0],
            0,
            0.15,
            0.5,
            0.45,
            1.0,
            0.8,
          ],
        },
      });

      this.map.addLayer({
        id: CELLS_LINE_LAYER_ID,
        type: "line",
        source: CELLS_SOURCE_ID,
        paint: {
          "line-color": ["coalesce", ["get", "color"], "#60a5fa"],
          "line-width": 1,
          "line-opacity": 0.6,
        },
      });

      this.bindLayerClick(CELLS_FILL_LAYER_ID);
    }

    // 3. Location Points Layer
    if (!this.map.getSource(LOCATIONS_SOURCE_ID)) {
      this.map.addSource(LOCATIONS_SOURCE_ID, {
        type: "geojson",
        data: emptyGeoJSON,
      });

      this.map.addLayer({
        id: LOCATIONS_CIRCLE_LAYER_ID,
        type: "circle",
        source: LOCATIONS_SOURCE_ID,
        paint: {
          "circle-color": ["coalesce", ["get", "color"], "#38bdf8"],
          "circle-radius": 4,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
          "circle-opacity": 0.85,
        },
      });

      this.bindLayerClick(LOCATIONS_CIRCLE_LAYER_ID);
    }

    // 4. Alerts Layer
    if (!this.map.getSource(ALERTS_SOURCE_ID)) {
      this.map.addSource(ALERTS_SOURCE_ID, {
        type: "geojson",
        data: emptyGeoJSON,
      });

      this.map.addLayer({
        id: ALERTS_HALO_LAYER_ID,
        type: "circle",
        source: ALERTS_SOURCE_ID,
        paint: {
          "circle-color": ["coalesce", ["get", "color"], "#ef4444"],
          "circle-radius": 12,
          "circle-opacity": 0.25,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": ["coalesce", ["get", "color"], "#ef4444"],
        },
      });

      this.map.addLayer({
        id: ALERTS_POINT_LAYER_ID,
        type: "circle",
        source: ALERTS_SOURCE_ID,
        paint: {
          "circle-color": ["coalesce", ["get", "color"], "#ef4444"],
          "circle-radius": 5,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffffff",
        },
      });

      this.bindLayerClick(ALERTS_POINT_LAYER_ID);
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

    // Map layerId to appropriate sourceId
    let sourceId = layerId;
    if (layerId === CELLS_FILL_LAYER_ID || layerId === CELLS_LINE_LAYER_ID || layerId === "cells") {
      sourceId = CELLS_SOURCE_ID;
    } else if (layerId === LOCATIONS_CIRCLE_LAYER_ID || layerId === "locations") {
      sourceId = LOCATIONS_SOURCE_ID;
    } else if (layerId === ALERTS_POINT_LAYER_ID || layerId === ALERTS_HALO_LAYER_ID || layerId === "alerts") {
      sourceId = ALERTS_SOURCE_ID;
    } else if (layerId === BOUNDARIES_FILL_LAYER_ID || layerId === BOUNDARIES_LINE_LAYER_ID || layerId === "boundaries") {
      sourceId = BOUNDARIES_SOURCE_ID;
    }

    const source = this.map.getSource(sourceId) as GeoJSONSource | undefined;
    if (source && typeof source.setData === "function") {
      source.setData(data);
    }
  }

  public setLayerVisibility(layerId: string, visible: boolean): void {
    if (!this.map || !this.isLoaded) return;
    const visibility = visible ? "visible" : "none";
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
    this.map.fitBounds(bounds, { padding: 40, duration: 600 });
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
    if (this.map) {
      this.clickHandlers.clear();
      this.pendingLayerData.clear();
      this.map.remove();
      this.map = null;
      this.isLoaded = false;
    }
  }
}
