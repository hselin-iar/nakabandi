/**
 * FeedbackPanel.tsx — Prediction explanation and model feedback panel.
 * DOC 3 Web App Shell: features/alerts — FeedbackPanel (A10)
 *
 * Provides explanation factor breakdown and human feedback submission.
 */

import React, { useState } from "react";
import { Button } from "../../shared/ui/Button";

interface FeedbackPanelProps {
  alertId: string;
  confidence: number;
}

export function FeedbackPanel({ alertId, confidence }: FeedbackPanelProps) {
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [feedbackType, setFeedbackType] = useState<"accurate" | "inaccurate" | null>(null);

  function handleFeedback(type: "accurate" | "inaccurate") {
    setFeedbackType(type);
    setFeedbackSubmitted(true);
  }

  return (
    <div className="nk-feedback-panel" data-alert-id={alertId} aria-label="Model feedback">
      <div className="nk-feedback-header">
        <span className="nk-text-sm font-semibold">Prediction Assessment</span>
        <span className="nk-feedback-score">
          Model Confidence: {(confidence * 100).toFixed(0)}%
        </span>
      </div>

      <div className="nk-feedback-factors">
        <div className="nk-factor-row">
          <span className="nk-factor-name">Velocity & Hop Cadence</span>
          <span className="nk-factor-weight font-mono">+38%</span>
        </div>
        <div className="nk-factor-row">
          <span className="nk-factor-name">Geographic Proximity to Hotspot</span>
          <span className="nk-factor-weight font-mono">+29%</span>
        </div>
        <div className="nk-factor-row">
          <span className="nk-factor-name">Mule Account Co-occurrence</span>
          <span className="nk-factor-weight font-mono">+18%</span>
        </div>
      </div>

      {feedbackSubmitted ? (
        <div className="nk-feedback-success" role="status">
          ✓ Feedback recorded ({feedbackType === "accurate" ? "Accurate" : "Needs Retuning"}).
          This helps tune future forecasts.
        </div>
      ) : (
        <div className="nk-feedback-actions">
          <span className="nk-text-xs nk-text-secondary">Was this forecast trajectory helpful?</span>
          <div className="nk-btn-group">
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleFeedback("accurate")}
            >
              👍 Relevant
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleFeedback("inaccurate")}
            >
              👎 False Positive
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
