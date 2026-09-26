/**
 * TimeProvider.tsx — one requestAnimationFrame loop for the whole app.
 *
 * Interpolates smoothly BETWEEN sparse `sim.time` SSE ticks so countdown rings can
 * animate. It is not wall-clock time: it anchors to the last real sim.time tick and
 * advances at the rate the last two ticks imply (the simulator can run faster or slower
 * than real time). If ticks stop (simulator paused, stream down) the interpolated clock
 * stops too, after a short grace period, rather than running on and lying.
 *
 * Non-animated consumers keep using useSimTime() from the stream provider.
 */

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useSimTime } from "../stream/useStream";

interface TimeCtx {
  /** Interpolated sim time in epoch ms, or null before the first sim.time tick. */
  simTimeMs: number | null;
}

const TimeContext = createContext<TimeCtx>({ simTimeMs: null });

/** Never extrapolate further than this past the last tick (ms of wall time). */
const MIN_GRACE_MS = 1_500;
/** Rate bounds: sim-seconds per wall-second. Keeps a bad pair of ticks from flinging the clock. */
const MAX_RATE = 3_600;

interface Anchor {
  simMs: number;
  wallMs: number;
  /** sim ms advanced per wall ms. */
  rate: number;
  /** wall ms between the last two ticks (drives the grace window). */
  intervalMs: number;
}

/** Pure: the interpolated sim time for `nowWallMs`, given the latest anchor. */
export function interpolateSimMs(anchor: Anchor, nowWallMs: number): number {
  const elapsed = Math.max(0, nowWallMs - anchor.wallMs);
  const grace = Math.max(MIN_GRACE_MS, anchor.intervalMs * 2);
  return anchor.simMs + Math.min(elapsed, grace) * anchor.rate;
}

/** Pure: build the next anchor from the previous one and a new tick. */
export function nextAnchor(prev: Anchor | null, simMs: number, wallMs: number): Anchor {
  if (!prev || simMs <= prev.simMs || wallMs <= prev.wallMs) {
    // First tick, or the clock moved backwards (a reset): restart at real-time rate.
    return { simMs, wallMs, rate: 1, intervalMs: 0 };
  }
  const intervalMs = wallMs - prev.wallMs;
  const rate = Math.min((simMs - prev.simMs) / intervalMs, MAX_RATE);
  return { simMs, wallMs, rate, intervalMs };
}

export function TimeProvider({ children }: { children: React.ReactNode }) {
  const simTimeIso = useSimTime();
  const anchorRef = useRef<Anchor | null>(null);
  const [simTimeMs, setSimTimeMs] = useState<number | null>(null);

  useEffect(() => {
    if (!simTimeIso) return;
    const simMs = new Date(simTimeIso).getTime();
    if (Number.isNaN(simMs)) return;
    anchorRef.current = nextAnchor(anchorRef.current, simMs, performance.now());
    setSimTimeMs(simMs);
  }, [simTimeIso]);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const anchor = anchorRef.current;
      if (anchor) setSimTimeMs(interpolateSimMs(anchor, performance.now()));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <TimeContext.Provider value={{ simTimeMs }}>{children}</TimeContext.Provider>;
}

/** Interpolated sim time (epoch ms), updated every animation frame. */
export function useTactileTime(): number | null {
  return useContext(TimeContext).simTimeMs;
}
