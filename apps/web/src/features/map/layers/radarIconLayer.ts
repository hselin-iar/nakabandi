/**
 * radarIconLayer.ts — pulsing threat-radar marker for the hottest heat cells.
 *
 * Overhaul plan §2.3. Canvas-drawn animated icon (MapLibre's StyleImageInterface), used by a
 * `symbol` layer. It is deliberately capped to the top few cells: heavy per-frame canvas
 * animation on many markers is what MapLibre's maintainers warn against. Every other elevated
 * cell is already visible through the GPU heat density + point layers, at no per-frame JS cost.
 *
 * This file draws the image only; maplibre-gl itself is imported in MapLibreAdapter.ts alone.
 */

import type { HeatCell } from "../types";

export const HOT_RADAR_SOURCE_ID = "nk-hot-radar-source";
export const HOT_RADAR_LAYER_ID = "nk-hot-radar";
export const HOT_RADAR_IMAGE_ID = "nk-pulsing-radar";

/** At most this many markers animate at once. */
export const MAX_HOT_RADARS = 3;
/** A cell only pulses if it is genuinely elevated (value is normalised 0-1). */
export const HOT_RADAR_MIN_VALUE = 0.5;

/** Pure: the hottest cells worth animating, hottest first. */
export function pickHotCells(
  cells: readonly HeatCell[],
  max = MAX_HOT_RADARS,
  minValue = HOT_RADAR_MIN_VALUE,
): HeatCell[] {
  return cells
    .filter((c) => c.value >= minValue)
    .sort((a, b) => b.value - a.value)
    .slice(0, max);
}

export function hotCellsToGeoJSON(cells: readonly HeatCell[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: pickHotCells(cells).map((c) => ({
      type: "Feature",
      properties: { id: c.id, value: c.value },
      geometry: { type: "Point", coordinates: [c.lon, c.lat] },
    })),
  };
}

/** Structural twin of maplibre's StyleImageInterface, so this file needs no maplibre import. */
export interface PulsingImage {
  width: number;
  height: number;
  data: Uint8Array | Uint8ClampedArray;
  onAdd?: () => void;
  render: () => boolean;
}

const PERIOD_MS = 1500;
const SIZE = 120;

/**
 * @param isActive       false while there is nothing to animate or the layer is hidden: the
 *                       image then draws nothing and requests no repaint, so an idle radar costs nothing.
 * @param requestRepaint asks the map for another frame (map.triggerRepaint).
 */
export function createPulsingRadarImage(isActive: () => boolean, requestRepaint: () => void): PulsingImage {
  let ctx: CanvasRenderingContext2D | null = null;
  const reduceMotion =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const image: PulsingImage = {
    width: SIZE,
    height: SIZE,
    data: new Uint8Array(SIZE * SIZE * 4),
    onAdd() {
      const canvas = document.createElement("canvas");
      canvas.width = SIZE;
      canvas.height = SIZE;
      ctx = canvas.getContext("2d");
    },
    render() {
      if (!ctx || !isActive()) return false;
      const t = reduceMotion ? 0.35 : (performance.now() % PERIOD_MS) / PERIOD_MS;
      const c = SIZE / 2;
      ctx.clearRect(0, 0, SIZE, SIZE);

      // expanding, fading outer ring
      ctx.beginPath();
      ctx.arc(c, c, c * (0.28 + 0.72 * t), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(239, 68, 68, ${1 - t})`;
      ctx.lineWidth = 3;
      ctx.stroke();

      // steady core
      ctx.beginPath();
      ctx.arc(c, c, c * 0.14, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(239, 68, 68, 1)";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
      ctx.stroke();

      image.data = ctx.getImageData(0, 0, SIZE, SIZE).data;
      if (!reduceMotion) requestRepaint();
      return true;
    },
  };
  return image;
}
