/**
 * FeedbackPanel.tsx — narrative forecast evidence and human feedback panel.
 * DOC 3 Web App Shell: features/alerts — FeedbackPanel (A10)
 *
 * Renders forecast.evidence[].text_en verbatim, as narrative statements — never as
 * feature-attribution percentages. DOC 2 §2.8 risk T12: evidence statements may be read
 * as causal explanations; they are evidence FROM the model, not a rendering of WHY it decided.
 */

import React, { useState } from "react";
import { Button } from "../../shared/ui/Button";
import type { EvidenceModel } from "../../shared/api/types.ts";

interface FeedbackPanelProps {
  alertId: string;
  confidence: number;
  evidence: EvidenceModel[];
}

export function FeedbackPanel({ alertId, confidence, evidence }: FeedbackPanelProps) {
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [feedbackType, setFeedbackType] = useState<"accurate" | "inaccurate" | null>(null);

  function handleFeedback(type: "accurate" | "inaccurate") {
    setFeedbackType(type);
    setFeedbackSubmitted(true);
  }

  return (
    <div className="nk-feedback-panel" data-alert-id={alertId} aria-label="Forecast evidence">
      <div className="nk-feedback-header">
        <span className="nk-text-sm font-semibold">Evidence</span>
        <span className="nk-feedback-score">
          Model Confidence: {(confidence * 100).toFixed(0)}%
        </span>
      </div>

      <div className="nk-evidence-list">
        {evidence.length === 0 ? (
          <p className="nk-evidence-empty nk-text-xs text-muted">
            No narrative evidence recorded for this forecast.
          </p>
        ) : (
          evidence.map((item, idx) => (
            <div className="nk-evidence-card" key={`${item.code}-${idx}`}>
              <p className="nk-evidence-text">{item.text_en}</p>
            </div>
          ))
        )}
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
