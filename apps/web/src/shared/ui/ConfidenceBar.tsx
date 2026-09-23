/**
 * ConfidenceBar.tsx — visual confidence/score bar.
 * DOC 3 Web App Shell: shared/ui — ConfidenceBar
 *
 * Accepts a 0.0–1.0 float and renders a labelled progress bar.
 */

import React from "react";

interface ConfidenceBarProps {
  /** 0.0 – 1.0 score. */
  value: number;
  /** Optional label override; defaults to formatted percentage. */
  label?: string;
  className?: string;
}

export function ConfidenceBar({
  value,
  label,
  className = "",
}: ConfidenceBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const pct = Math.round(clamped * 100);

  const colorClass =
    clamped >= 0.75
      ? "nk-conf-bar__fill--high"
      : clamped >= 0.5
        ? "nk-conf-bar__fill--medium"
        : "nk-conf-bar__fill--low";

  const displayLabel = label ?? `${pct}%`;

  return (
    <div className={`nk-conf-bar ${className}`} aria-label={`Confidence: ${displayLabel}`}>
      <div
        className="nk-conf-bar__track"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={displayLabel}
      >
        <div
          className={`nk-conf-bar__fill ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="nk-conf-bar__label">{displayLabel}</span>
    </div>
  );
}
