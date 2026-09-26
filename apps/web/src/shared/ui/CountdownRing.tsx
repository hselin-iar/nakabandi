/**
 * CountdownRing.tsx — SVG ring counting down to an alert's expiry.
 *
 * Driven by useTactileTime() (interpolated SIM time), never wall-clock. The ring drains
 * clockwise from 12 o'clock; its colour steps through severity bands as the window closes:
 * > 50% remaining low, > 20% medium, otherwise critical (and the digits pulse).
 * Fixed footprint so animating it never shifts the row's layout.
 */

import { useTactileTime } from "../time/TimeProvider";
import { formatDuration } from "../lib/format";

interface CountdownRingProps {
  /** ISO time the window closes. */
  expiresAt: string;
  /** ISO time the window opened (the ring's 100%). */
  createdAt: string;
  /** Outer size in px. */
  size?: number;
  className?: string;
}

const R = 14;
const CIRCUMFERENCE = 2 * Math.PI * R;

export type RingBand = "ok" | "warn" | "urgent" | "expired";

/** Pure: fraction of the window remaining (0..1) or null when it can't be computed. */
export function remainingFraction(nowMs: number | null, createdAt: string, expiresAt: string) {
  if (nowMs === null) return null;
  const start = new Date(createdAt).getTime();
  const end = new Date(expiresAt).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return null;
  return Math.min(1, Math.max(0, (end - nowMs) / (end - start)));
}

export function ringBand(pct: number, remainingSec: number): RingBand {
  if (remainingSec <= 0) return "expired";
  if (pct > 0.5) return "ok";
  if (pct > 0.2) return "warn";
  return "urgent";
}

export function CountdownRing({ expiresAt, createdAt, size = 44, className = "" }: CountdownRingProps) {
  const nowMs = useTactileTime();
  const pct = remainingFraction(nowMs, createdAt, expiresAt);

  if (nowMs === null || pct === null) {
    return (
      <span className={`nk-ring nk-ring--idle ${className}`} style={{ width: size, height: size }} aria-label="Time remaining unknown">
        <span className="nk-ring__label data-digit">--:--</span>
      </span>
    );
  }

  const remainingSec = Math.round((new Date(expiresAt).getTime() - nowMs) / 1000);
  const band = ringBand(pct, remainingSec);
  const label = formatDuration(remainingSec);

  return (
    <span
      className={`nk-ring nk-ring--${band} ${className}`}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Time remaining: ${label}`}
    >
      <svg viewBox="0 0 36 36" width={size} height={size} aria-hidden="true">
        <circle className="nk-ring__track" cx="18" cy="18" r={R} fill="none" strokeWidth="3" />
        <circle
          className="nk-ring__arc"
          cx="18"
          cy="18"
          r={R}
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={CIRCUMFERENCE * (1 - pct)}
          transform="rotate(-90 18 18)"
        />
      </svg>
      <span className={`nk-ring__label data-digit${band === "urgent" ? " nk-countdown--urgent" : ""}`}>
        {label}
      </span>
    </span>
  );
}
