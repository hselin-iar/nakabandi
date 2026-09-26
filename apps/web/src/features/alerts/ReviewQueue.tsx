/**
 * ReviewQueue.tsx — Rapid triage queue for nodal and district officers.
 * DOC 3 Web App Shell: features/alerts — ReviewQueue
 */

import { toast } from "sonner";
import React, { useState } from "react";
import type { AlertSummary } from "../../shared/api/types.ts";
import type { AlertStatus, Severity } from "../../shared/api/enums.ts";
import { SeverityBadge, StatusBadge } from "../../shared/ui/Badge";
import { Countdown } from "../../shared/ui/Countdown";
import { Button } from "../../shared/ui/Button";
import { useAlertAction } from "./api/useAlerts";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { can } from "../../shared/lib/permissions";

interface ReviewQueueProps {
  alerts: AlertSummary[];
  onSelectAlert: (alertId: string) => void;
  onClose: () => void;
}

export function ReviewQueue({
  alerts,
  onSelectAlert,
  onClose,
}: ReviewQueueProps) {
  const { principal } = usePrincipal();
  const [currentIndex, setCurrentIndex] = useState(0);
  const actionMutation = useAlertAction();

  const pendingAlerts = alerts.filter(
    (a) => a.status === "open" || a.status === "acknowledged",
  );

  const current = pendingAlerts[currentIndex];
  const canAck = can(principal, "ACKNOWLEDGE");

  if (!current || pendingAlerts.length === 0) {
    return (
      <div className="nk-review-queue nk-review-queue--empty">
        <div className="nk-text-sm font-semibold">Triage Queue Clear</div>
        <p className="nk-text-xs nk-text-secondary">All open alerts have been processed.</p>
        <Button size="sm" variant="outline" onClick={onClose}>
          Return to Inbox
        </Button>
      </div>
    );
  }

  function handleNext() {
    if (currentIndex < pendingAlerts.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    }
  }

  function handlePrev() {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  }

  function handleAckAndNext() {
    if (!current) return;
    // Optimistic (the mutation flips the status in every cached list) with a toast that
    // reports the real outcome; the queue advances only once the server accepted it.
    const request = actionMutation.mutateAsync({ alertId: current.id, action: { type: "acknowledge" } });
    toast.promise(request, {
      loading: "Acknowledging…",
      success: "Acknowledged",
      error: (err: unknown) => (err instanceof Error ? err.message : "Acknowledge failed"),
    });
    request.then(handleNext, () => undefined);
  }

  return (
    <aside className="nk-review-queue" aria-label="Rapid triage queue">
      <div className="nk-review-queue-header">
        <div>
          <span className="nk-text-xs font-semibold uppercase tracking-wider text-muted">
            Triage Queue
          </span>
          <div className="nk-text-xs nk-text-secondary">
            Alert {currentIndex + 1} of {pendingAlerts.length}
          </div>
        </div>
        <button
          className="nk-drawer__close"
          onClick={onClose}
          aria-label="Close review queue"
        >
          ✕
        </button>
      </div>

      <div className="nk-review-queue-body">
        <div className="nk-review-item-main">
          <div className="nk-review-badges">
            <SeverityBadge severity={current.severity as Severity} />
            <StatusBadge status={current.status as AlertStatus} />
          </div>

          <div className="nk-review-target">
            <span className="font-mono font-bold">{current.cluster_ref}</span>
            <div className="text-sm font-medium">
              {String(current.target.name ?? current.target.id ?? "")}
            </div>
            <div className="text-xs text-muted font-mono">{current.id}</div>
          </div>

          <div className="nk-review-countdown">
            <span className="nk-text-xs text-muted">Expires In</span>
            <Countdown target={current.expires_at} warnThreshold={900} />
          </div>
        </div>

        <div className="nk-review-queue-actions">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onSelectAlert(current.id)}
          >
            Inspect Full Evidence →
          </Button>

          {canAck && current.status === "open" && (
            <Button
              size="sm"
              variant="primary"
              loading={actionMutation.isPending}
              onClick={handleAckAndNext}
            >
              ✓ Acknowledge & Next
            </Button>
          )}
        </div>
      </div>

      <div className="nk-review-queue-footer">
        <Button
          size="sm"
          variant="ghost"
          disabled={currentIndex === 0}
          onClick={handlePrev}
        >
          ← Previous
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={currentIndex >= pendingAlerts.length - 1}
          onClick={handleNext}
        >
          Next →
        </Button>
      </div>
    </aside>
  );
}
