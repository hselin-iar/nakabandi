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

  /**
   * Adds an HTML overlay marker at the given [lon, lat] coordinate.
   * Returns a cleanup function to remove it.
   */
  addHtmlMarker?(element: HTMLElement, lngLat: [number, number]): () => void;

  /**
   * Registers a handler fired when the user finishes a zoom gesture, with the new zoom level.
   * Drives zoom-bound resolution switching (Frontend Strategy §7.3) instead of a disconnected
   * resolution dropdown.
   */
  onZoomChange?(handler: (zoom: number) => void): void;

  /**
   * Sets the camera zoom level directly (no bounds change), so a manual resolution pick can
   * still move the map into that resolution's zoom band — two-way binding, not just one-way.
   */
  setZoom?(zoom: number): void;
}
