/**
 * TimeSlider.tsx — Sim-time driven replay timeline for the Risk Heatmap.
 * DOC 3 M3 / DOC 4 Step C5:
 *   "moving the time slider pauses live updates and shows 'return to live'."
 */

import React from "react";
import { useSimTime } from "../../shared/stream/useStream";
import { formatSimTime } from "../../shared/lib/format";

interface TimeSliderProps {
  isPaused: boolean;
  offsetHours: number; // 0 means live; -1 to -72 means past replay window
  onOffsetChange: (hours: number) => void;
  onReturnToLive: () => void;
}

export function TimeSlider({
  isPaused,
  offsetHours,
  onOffsetChange,
  onReturnToLive,
}: TimeSliderProps) {
  const currentSimTime = useSimTime();
  const baseTime = currentSimTime ? new Date(currentSimTime) : new Date("2026-01-15T12:00:00Z");
  const replayTime = new Date(baseTime.getTime() + offsetHours * 3600 * 1000);

  const isReplaying = isPaused || offsetHours < 0;

  return (
    <div className="nk-time-slider" aria-label="Replay time slider">
      <div className="nk-time-slider__header">
        <div className="nk-time-slider__status">
          <span
            className={`nk-live-indicator ${isReplaying ? "nk-live-indicator--paused" : "nk-live-indicator--live"}`}
          />
          <span className="font-semibold text-xs uppercase tracking-wider">
            {isReplaying ? "Replay Mode (Paused)" : "Live Ingestion"}
          </span>
        </div>

        <div className="nk-time-slider__timestamp font-mono text-xs">
          {formatSimTime(replayTime.toISOString())}
          {offsetHours < 0 && (
            <span className="nk-text-secondary ml-1 font-sans">
              ({Math.abs(offsetHours)}h ago)
            </span>
          )}
        </div>

        {isReplaying && (
          <button
            type="button"
            className="nk-btn nk-btn--primary nk-btn--sm nk-time-slider__return-btn"
            onClick={onReturnToLive}
          >
            ▶ Return to Live
          </button>
        )}
      </div>

      <div className="nk-time-slider__control">
        <span className="text-xs text-muted font-mono">-72h</span>
        <input
          type="range"
          min="-72"
          max="0"
          step="1"
          aria-label="Replay time offset hours"
          value={offsetHours}
          onChange={(e) => onOffsetChange(parseInt(e.target.value, 10))}
          className="nk-slider"
        />
        <span className="text-xs text-muted font-mono">NOW</span>
      </div>
    </div>
  );
}
