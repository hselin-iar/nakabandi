/**
 * RollingCounter.tsx — a number that visibly rolls to its new value instead of snapping.
 *
 * Plain rAF tween (no animation library). Respects prefers-reduced-motion by snapping.
 * The formatted text is what assistive tech reads; the tween only drives what is drawn.
 */

import { useEffect, useRef, useState } from "react";

interface RollingCounterProps {
  value: number;
  /** Format the (possibly fractional) in-flight value for display. Default: rounded integer. */
  format?: (n: number) => string;
  durationMs?: number;
  className?: string;
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function RollingCounter({
  value,
  format = (n) => String(Math.round(n)),
  durationMs = 450,
  className = "",
}: RollingCounterProps) {
  const [shown, setShown] = useState(value);
  const shownRef = useRef(value);
  shownRef.current = shown;

  useEffect(() => {
    const from = shownRef.current;
    if (from === value) return;
    if (prefersReducedMotion() || durationMs <= 0) {
      setShown(value);
      return;
    }
    const start = performance.now();
    let raf = 0;
    const tick = () => {
      const t = Math.min(1, (performance.now() - start) / durationMs);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(from + (value - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, durationMs]);

  return (
    <span className={`data-digit ${className}`} data-value={value} aria-label={format(value)}>
      {format(shown)}
    </span>
  );
}
