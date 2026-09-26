/**
 * LadderDecisionPath.tsx — renders the ladder recommendation as a reasoned comparison,
 * not just a colored badge: window-remaining vs. best-unit ETA, plus the reason_code
 * in plain language. DOC1 §1.2 M6 acceptance: "Every alert shows ETA-vs-window and a
 * recommended ladder level with its reason."
 *
 * Injected-time invariant: uses useSimTime(), never Date.now() (matches Countdown.tsx).
 */

import React from "react";
import { VerdictBadge, LadderBadge } from "../../shared/ui/Badge";
import { useSimTime } from "../../shared/stream/useStream";
import type { InterceptAssessmentModel } from "../../shared/api/types.ts";
import type { LadderLevel, Verdict } from "../../shared/api/enums.ts";

interface LadderDecisionPathProps {
  assessment: InterceptAssessmentModel;
  /** The alert's window close time (AlertDetailModel.expires_at). */
  expiresAt: string;
}

function reasonSentence(
  assessment: InterceptAssessmentModel,
  windowRemainingMin: number | null,
  marginMin: number | null,
): string {
  const unit = assessment.best_unit;
  switch (assessment.reason_code) {
    case "OK":
      if (!unit) return "A response unit is available for this target.";
      if (marginMin == null) {
        return `${unit.unit_kind} ${unit.unit_id} is ${unit.eta_min.toFixed(1)} min out.`;
      }
      return marginMin >= 0
        ? `${unit.unit_kind} ${unit.unit_id} is ${unit.eta_min.toFixed(1)} min out against a window that closes in ${(windowRemainingMin ?? unit.eta_min + marginMin).toFixed(1)} min — ${marginMin.toFixed(1)} min of margin.`
        : `${unit.unit_kind} ${unit.unit_id} is ${unit.eta_min.toFixed(1)} min out, but the window closes ${Math.abs(marginMin).toFixed(1)} min before that.`;
    case "NO_UNITS":
      return "No response unit is registered within reach of this target's channel — interception is not currently possible.";
    case "TIMING_STALE":
      return "Too little of the timing forecast's probability mass remains for this window to assess interception meaningfully.";
    case "UNKNOWN_CHANNEL":
      return "The predicted cash-out channel is not recognised, so interception could not be assessed for it.";
    default:
      return `Reason code: ${assessment.reason_code}`;
  }
}

export function LadderDecisionPath({ assessment, expiresAt }: LadderDecisionPathProps) {
  const simTime = useSimTime();

  const etaMin = assessment.best_unit?.eta_min ?? null;

  let windowRemainingMin: number | null = null;
  let marginMin: number | null = null;
  if (simTime) {
    const nowMs = new Date(simTime).getTime();
    const expMs = new Date(expiresAt).getTime();
    if (!isNaN(nowMs) && !isNaN(expMs)) {
      windowRemainingMin = (expMs - nowMs) / 60000;
      if (etaMin != null) {
        marginMin = windowRemainingMin - etaMin;
      }
    }
  }

  const showBars = etaMin != null && windowRemainingMin != null;
  const barMax = showBars ? Math.max(windowRemainingMin!, etaMin!, 1) : 1;

  return (
    <div className="nk-ladder-path">
      <div className="nk-ladder-path__badges">
        <VerdictBadge verdict={assessment.verdict as Verdict} />
        <LadderBadge level={assessment.ladder_level as LadderLevel} />
      </div>

      {showBars && (
        <div className="nk-ladder-path__bars">
          <div className="nk-ladder-path__bar-row">
            <span className="nk-ladder-path__bar-label">Window remaining</span>
            <div className="nk-ladder-path__bar-track">
              <div
                className="nk-ladder-path__bar-fill nk-ladder-path__bar-fill--window"
                style={{
                  width: `${Math.min(100, (Math.max(windowRemainingMin!, 0) / barMax) * 100)}%`,
                }}
              />
            </div>
            <span className="nk-ladder-path__bar-value font-mono">
              {windowRemainingMin! >= 0 ? `${windowRemainingMin!.toFixed(1)}m` : "expired"}
            </span>
          </div>
          <div className="nk-ladder-path__bar-row">
            <span className="nk-ladder-path__bar-label">Unit ETA</span>
            <div className="nk-ladder-path__bar-track">
              <div
                className="nk-ladder-path__bar-fill nk-ladder-path__bar-fill--eta"
                style={{ width: `${Math.min(100, (etaMin! / barMax) * 100)}%` }}
              />
            </div>
            <span className="nk-ladder-path__bar-value font-mono">{etaMin!.toFixed(1)}m</span>
          </div>
        </div>
      )}

      <p className="nk-ladder-path__reason nk-text-xs">
        {reasonSentence(assessment, windowRemainingMin, marginMin)}
      </p>
    </div>
  );
}
