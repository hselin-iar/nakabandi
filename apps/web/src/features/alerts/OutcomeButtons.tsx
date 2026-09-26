/**
 * OutcomeButtons.tsx — Hit / Miss / Late outcome classification buttons.
 * DOC 3 Web App Shell: features/alerts — OutcomeButtons (S3)
 *
 * Gated by MARK_OUTCOME permission.
 */

import React, { useState } from "react";
import { toast } from "sonner";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { can } from "../../shared/lib/permissions";
import { useAlertOutcome } from "./api/useAlerts";
import { Button } from "../../shared/ui/Button";

interface OutcomeButtonsProps {
  alertId: string;
  currentVerdict?: "hit" | "miss" | "late";
  disabled?: boolean;
}

export function OutcomeButtons({
  alertId,
  currentVerdict,
  disabled = false,
}: OutcomeButtonsProps) {
  const { principal } = usePrincipal();
  const outcomeMutation = useAlertOutcome();
  const [selectedVerdict, setSelectedVerdict] = useState<"hit" | "miss" | "late" | null>(
    currentVerdict ?? null,
  );
  const [notes, setNotes] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);

  const canMark = can(principal, "MARK_OUTCOME");

  if (!canMark && !currentVerdict) {
    return null;
  }

  function handleSelect(verdict: "hit" | "miss" | "late") {
    setSelectedVerdict(verdict);
    setShowConfirm(true);
  }

  function handleConfirm() {
    if (!selectedVerdict) return;
    const request = outcomeMutation.mutateAsync({
      alertId,
      outcome: { result: selectedVerdict, reason: notes || undefined },
    });
    setShowConfirm(false);
    toast.promise(request, {
      loading: "Recording outcome…",
      success: `Outcome recorded: ${selectedVerdict.toUpperCase()}`,
      error: (err: unknown) => (err instanceof Error ? err.message : "Outcome could not be recorded"),
    });
  }

  return (
    <div className="nk-outcome-section">
      <div className="nk-outcome-label">
        <span className="nk-text-sm nk-text-secondary font-medium">Reconciliation Outcome</span>
        {currentVerdict && (
          <span className={`nk-outcome-tag nk-outcome-tag--${currentVerdict}`}>
            {currentVerdict.toUpperCase()}
          </span>
        )}
      </div>

      <div className="nk-outcome-btn-group" role="group" aria-label="Alert outcome">
        <Button
          size="sm"
          variant={selectedVerdict === "hit" ? "primary" : "outline"}
          disabled={disabled || !canMark || outcomeMutation.isPending}
          onClick={() => handleSelect("hit")}
          className="nk-btn--outcome-hit"
          aria-pressed={selectedVerdict === "hit"}
        >
          ✓ Intercepted (Hit)
        </Button>
        <Button
          size="sm"
          variant={selectedVerdict === "miss" ? "primary" : "outline"}
          disabled={disabled || !canMark || outcomeMutation.isPending}
          onClick={() => handleSelect("miss")}
          className="nk-btn--outcome-miss"
          aria-pressed={selectedVerdict === "miss"}
        >
          ✗ Cash-Out Occurred (Miss)
        </Button>
        <Button
          size="sm"
          variant={selectedVerdict === "late" ? "primary" : "outline"}
          disabled={disabled || !canMark || outcomeMutation.isPending}
          onClick={() => handleSelect("late")}
          className="nk-btn--outcome-late"
          aria-pressed={selectedVerdict === "late"}
        >
          ⏱ Late Interception
        </Button>
      </div>

      {showConfirm && (
        <div className="nk-outcome-confirm" role="region" aria-label="Outcome details">
          <input
            type="text"
            className="nk-input nk-input--sm"
            placeholder="Optional operator notes / case ref"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            disabled={outcomeMutation.isPending}
          />
          <div className="nk-outcome-confirm-actions">
            <Button
              size="sm"
              variant="primary"
              loading={outcomeMutation.isPending}
              onClick={handleConfirm}
            >
              Confirm {selectedVerdict?.toUpperCase()}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={outcomeMutation.isPending}
              onClick={() => setShowConfirm(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
