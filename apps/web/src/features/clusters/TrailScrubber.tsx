/**
 * TrailScrubber.tsx — scrub or play back the money trail through time.
 *
 * Time here is the INVESTIGATOR's playback position over historic edge timestamps, not
 * simulation time, so it lives in local state (no TimeProvider). Emits a cutoff (epoch ms)
 * that the graph uses to fade out hops that had not yet happened.
 */

import { useEffect, useRef, useState } from "react";
import { formatSimTime } from "../../shared/lib/format";
import type { ClusterEdge } from "./types";

interface Props {
  edges: readonly ClusterEdge[];
  /** null = show everything (playback off). */
  value: number | null;
  onChange: (ms: number | null) => void;
  /** How long a full play-through takes. */
  durationMs?: number;
}

export function timeBounds(edges: readonly ClusterEdge[]): { min: number; max: number } | null {
  let min = Infinity;
  let max = -Infinity;
  for (const e of edges) {
    const t = new Date(e.event_at).getTime();
    if (!Number.isNaN(t)) {
      min = Math.min(min, t);
      max = Math.max(max, t);
    }
  }
  return max > min ? { min, max } : null;
}

export function TrailScrubber({ edges, value, onChange, durationMs = 8000 }: Props) {
  const bounds = timeBounds(edges);
  const [playing, setPlaying] = useState(false);
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (!playing || !bounds) return;
    const span = bounds.max - bounds.min;
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      const from = valueRef.current ?? bounds.min;
      const next = Math.min(bounds.max, from + ((now - last) / durationMs) * span);
      last = now;
      onChange(next);
      if (next >= bounds.max) {
        setPlaying(false);
        onChange(null); // finished: back to showing everything
        return;
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // bounds is derived from edges; restart only when playing toggles or the trail changes
  }, [playing, bounds?.min, bounds?.max, durationMs, onChange]);

  if (!bounds) return null;

  return (
    <div className="nk-scrubber" data-testid="timeline-scrubber">
      <button
        type="button"
        className="nk-btn nk-btn--ghost nk-btn--sm"
        onClick={() => {
          if (!playing && value === null) onChange(bounds.min);
          setPlaying((p) => !p);
        }}
        aria-pressed={playing}
      >
        {playing ? "Pause" : "Play trail"}
      </button>
      <input
        type="range"
        aria-label="Trail playback position"
        min={bounds.min}
        max={bounds.max}
        step={Math.max(1, Math.floor((bounds.max - bounds.min) / 500))}
        value={value ?? bounds.max}
        onChange={(e) => {
          setPlaying(false);
          onChange(Number(e.target.value));
        }}
      />
      <span className="nk-scrubber__time data-digit">
        {value === null ? "All hops" : formatSimTime(new Date(value).toISOString(), { includeSeconds: true })}
      </span>
      {value !== null && (
        <button type="button" className="nk-btn nk-btn--ghost nk-btn--sm" onClick={() => { setPlaying(false); onChange(null); }}>
          Show all
        </button>
      )}
    </div>
  );
}
