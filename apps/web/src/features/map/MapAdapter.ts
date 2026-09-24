/**
 * MapAdapter.ts — Abstract interface for GIS Map rendering.
 * DOC 3 M3 / DOC 4 Step C5:
 *   "MapAdapter.ts interface: setLayerData(), fitTo(), onFeatureClick(), destroy() ...
 *    All maplibre-gl imports stay inside MapLibreAdapter.ts — every other file
 *    talks to the MapAdapter interface only, so a fallback renderer is a drop-in swap."
 */

export interface MapInitOptions {
  center?: [number, number]; // [lon, lat]
  zoom?: number;
  interactive?: boolean;
}

export interface MapAdapter {
  /**
   * Initializes the map inside the given container element.
   * Resolves when the map is fully loaded and ready for layer updates.
   */
  init(container: HTMLElement, options?: MapInitOptions): Promise<void>;

  /**
   * Returns true if the map engine is initialized and ready.
   */
  isReady(): boolean;

  /**
   * Updates or sets the GeoJSON data for a specific layer.
   */
  setLayerData(
    layerId: string,
    data: GeoJSON.FeatureCollection | GeoJSON.Feature,
  ): void;

  /**
   * Toggles visibility of a specific map layer.
   */
  setLayerVisibility(layerId: string, visible: boolean): void;

  /**
   * Fits the camera to the specified bounding box: [minLon, minLat, maxLon, maxLat]
   * or [[minLon, minLat], [maxLon, maxLat]].
   */
  fitTo(
    bounds:
      | [number, number, number, number]
      | [[number, number], [number, number]],
  ): void;

  /**
   * Registers a click handler for features on a given layer.
   */
  onFeatureClick(layerId: string, handler: (feature: unknown) => void): void;

  /**
   * Triggers map viewport resize recalculation.
   */
  resize(): void;

  /**
   * Cleanly destroys map instance and unbinds event handlers.
   */
  destroy(): void;
}
