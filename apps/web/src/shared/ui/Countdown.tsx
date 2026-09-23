/**
 * Countdown.tsx — sim-time countdown display.
 * DOC 3 Web App Shell: shared/ui — Countdown
 *
 * Renders time remaining to `target` using the SIM clock from the stream,
 * NEVER the browser clock. Respects prefers-reduced-motion.
 *
 * Injected-time invariant: only useSimTime() is used — no Date.now().
 */

import React, { useMemo } from "react";
import { useSimTime } from "../stream/useStream";
import { formatDuration } from "../lib/format";

interface CountdownProps {
  /** ISO sim-time string of the deadline. */
  target: string;
  /** Seconds below which to show a warning state. Default: 300 (5 min). */
  warnThreshold?: number;
  className?: string;
}

export function Countdown({
  target,
  warnThreshold = 300,
  className = "",
}: CountdownProps) {
  const simTime = useSimTime();

  const { remainingSec, label } = useMemo(() => {
    if (!simTime) {
      return { remainingSec: null, label: "--:--" };
    }
    const nowMs = new Date(simTime).getTime();
    const targetMs = new Date(target).getTime();
    if (isNaN(nowMs) || isNaN(targetMs)) {
      return { remainingSec: null, label: "--:--" };
    }
    const sec = Math.round((targetMs - nowMs) / 1000);
    return { remainingSec: sec, label: formatDuration(sec) };
  }, [simTime, target]);

  const isWarn =
    remainingSec !== null && remainingSec >= 0 && remainingSec < warnThreshold;
  const isExpired = remainingSec !== null && remainingSec < 0;

  const stateClass = isExpired
    ? "nk-countdown--expired"
    : isWarn
      ? "nk-countdown--warn"
      : "";

  return (
    <time
      dateTime={target}
      className={`nk-countdown ${stateClass} ${className}`}
      aria-label={`Time remaining: ${label}`}
    >
      {label}
    </time>
  );
}
