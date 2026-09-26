/**
 * MapHud.tsx — instrument readouts over the map: cursor lat/lon, zoom, layers/entities.
 *
 * Cursor coordinates change on every mouse move, so they are written straight into a DOM
 * node through the imperative handle instead of React state; going through state would
 * re-render the whole map page dozens of times a second.
 */

import { forwardRef, useImperativeHandle, useRef } from "react";

export interface MapHudHandle {
  setCursor(lngLat: [number, number] | null): void;
  setZoom(zoom: number): void;
}

interface MapHudProps {
  layersOn: number;
  layersTotal: number;
  entities: number;
}

export const MapHud = forwardRef<MapHudHandle, MapHudProps>(function MapHud(
  { layersOn, layersTotal, entities },
  ref,
) {
  const cursorRef = useRef<HTMLSpanElement>(null);
  const zoomRef = useRef<HTMLSpanElement>(null);

  useImperativeHandle(ref, () => ({
    setCursor(lngLat) {
      if (cursorRef.current) {
        cursorRef.current.textContent = lngLat
          ? `${lngLat[1].toFixed(4)}°N ${lngLat[0].toFixed(4)}°E`
          : "—";
      }
    },
    setZoom(zoom) {
      if (zoomRef.current) zoomRef.current.textContent = zoom.toFixed(1);
    },
  }));

  return (
    <div className="nk-map-hud" aria-hidden="true">
      <span>
        <span className="nk-map-hud__k">CURSOR</span>
        <span ref={cursorRef}>—</span>
      </span>
      <span>
        <span className="nk-map-hud__k">ZOOM</span>
        <span ref={zoomRef}>—</span>
      </span>
      <span>
        <span className="nk-map-hud__k">LAYERS</span>
        {layersOn}/{layersTotal}
      </span>
      <span>
        <span className="nk-map-hud__k">ENTITIES</span>
        {entities}
      </span>
    </div>
  );
});
