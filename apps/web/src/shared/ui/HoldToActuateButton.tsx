/**
 * HoldToActuateButton.tsx — press-and-hold confirmation for consequential actions.
 *
 * Holding fills the button over `durationMs` (default 600); reaching 100% fires
 * `onActuate` exactly once. Releasing early cancels instantly with no side effect.
 * Works with pointer, and with Space/Enter for keyboard operators. The hold itself is
 * the confirmation, so there is no second dialog.
 *
 * No animation library: one requestAnimationFrame loop while held.
 */

import { useCallback, useEffect, useRef, useState } from "react";

interface HoldToActuateButtonProps {
  label: string;
  onActuate: () => void;
  durationMs?: number;
  disabled?: boolean;
  loading?: boolean;
  /** Visual tone; "danger" for irreversible-feeling actions. */
  variant?: "danger" | "primary";
  autoFocus?: boolean;
  className?: string;
}

export function HoldToActuateButton({
  label,
  onActuate,
  durationMs = 600,
  disabled = false,
  loading = false,
  variant = "danger",
  autoFocus = false,
  className = "",
}: HoldToActuateButtonProps) {
  const [pct, setPct] = useState(0);
  const rafRef = useRef(0);
  const startRef = useRef<number | null>(null);
  const firedRef = useRef(false);
  const onActuateRef = useRef(onActuate);
  onActuateRef.current = onActuate;

  const cancel = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    startRef.current = null;
    setPct(0);
  }, []);

  const step = useCallback(() => {
    if (startRef.current === null) return;
    const next = Math.min(100, ((performance.now() - startRef.current) / durationMs) * 100);
    setPct(next);
    if (next >= 100) {
      startRef.current = null;
      if (!firedRef.current) {
        firedRef.current = true;
        onActuateRef.current();
      }
      return;
    }
    rafRef.current = requestAnimationFrame(step);
  }, [durationMs]);

  const start = useCallback(() => {
    if (disabled || loading || startRef.current !== null) return;
    firedRef.current = false;
    startRef.current = performance.now();
    rafRef.current = requestAnimationFrame(step);
  }, [disabled, loading, step]);

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  const inactive = disabled || loading;

  return (
    <button
      type="button"
      className={`nk-hold nk-hold--${variant} ${className}`}
      disabled={inactive}
      autoFocus={autoFocus}
      aria-label={`${label} — press and hold`}
      onPointerDown={(e) => {
        if (e.button === 0 || e.pointerType !== "mouse") start();
      }}
      onPointerUp={cancel}
      onPointerLeave={cancel}
      onPointerCancel={cancel}
      onKeyDown={(e) => {
        if ((e.key === " " || e.key === "Enter") && !e.repeat) {
          e.preventDefault();
          start();
        }
      }}
      onKeyUp={(e) => {
        if (e.key === " " || e.key === "Enter") cancel();
      }}
      onBlur={cancel}
    >
      <span className="nk-hold__fill" style={{ width: `${pct}%` }} aria-hidden="true" />
      <span className="nk-hold__label">{loading ? "Sending…" : pct > 0 && pct < 100 ? "Keep holding…" : label}</span>
    </button>
  );
}
