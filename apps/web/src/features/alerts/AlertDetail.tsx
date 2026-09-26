/**
 * AlertDetail.tsx — slide-over detail drawer & action cockpit for an alert.
 * DOC 3 Web App Shell: features/alerts — AlertDetail (M4/LC-4/M5)
 *
 * Implements permission-gated action buttons (Hold, Dispatch, Notify, Acknowledge, Override)
 * and reconciliation outcome marking.
 */

import React, { useState } from "react";
import { Drawer } from "../../shared/ui/Drawer";
import { SeverityBadge, StatusBadge, LadderBadge } from "../../shared/ui/Badge";
import { ConfidenceBar } from "../../shared/ui/ConfidenceBar";
import { Countdown } from "../../shared/ui/Countdown";
import { MaskedRef } from "../../shared/ui/MaskedRef";
import { KeyValue } from "../../shared/ui/KeyValue";
import { Timeline, type TimelineEntry as UITimelineEntry } from "../../shared/ui/Timeline";
import { Button } from "../../shared/ui/Button";
import { Select } from "../../shared/ui/Select";
import { OutcomeButtons } from "./OutcomeButtons";
import { NoveltyBanner } from "./NoveltyBanner";
import { FeedbackPanel } from "./FeedbackPanel";
import { LadderDecisionPath } from "./LadderDecisionPath";
import { ProportionalityStrip } from "./ProportionalityStrip";
import { TimingDecayCurve } from "./TimingDecayCurve";
import { EvidencePackPanel } from "./EvidencePackPanel";
import { DeliveryLog } from "./DeliveryLog";
import { useAlert, useAlertAction } from "./api/useAlerts";
import { formatSimTime, humanizeStatus } from "../../shared/lib/format";
import type { ActionType, AlertStatus, LadderLevel, Severity } from "../../shared/api/enums.ts";

interface AlertDetailProps {
  alertId: string | null;
  onClose: () => void;
}

export function AlertDetail({ alertId, onClose }: AlertDetailProps) {
  const { data: alert, isLoading } = useAlert(alertId);
  const actionMutation = useAlertAction();

  // Action dialog states
  const [activeActionModal, setActiveActionModal] = useState<ActionType | null>(null);
  const [holdAmount, setHoldAmount] = useState("50000");
  const [actionReason, setActionReason] = useState("");
  const [unitId, setUnitId] = useState("UNIT-CRIME-04");

  if (!alertId) return null;

  if (isLoading || !alert) {
    return (
      <Drawer open={Boolean(alertId)} onClose={onClose} title="Alert Detail" width="lg">
        <div className="nk-drawer-loading" aria-live="polite">
          Loading alert details…
        </div>
      </Drawer>
    );
  }

  // Action bar is driven by the server's own per-alert allowed_actions (LC-4), not a
  // client-side role table — this is the source of truth for what this principal may
  // record on THIS alert right now (DOC2 §2.4 / invariant 7).
  const allowedActions = new Set(alert.allowed_actions);
  const canAck = allowedActions.has("acknowledge");
  const canHold = allowedActions.has("request_hold");
  const canDispatch = allowedActions.has("dispatch");
  const canNotify = allowedActions.has("notify_station");
  const canOverride = allowedActions.has("override");

  // Latest interception assessment — the ladder recommendation reflects the most recent one.
  const latestAssessment = alert.interception.at(-1) ?? null;

  const targetName = String(alert.target.name ?? alert.target.id ?? "Target");

  function handleActionSubmit(type: ActionType) {
    if (!alert) return;

    const params: Record<string, unknown> = {};
    if (type === "request_hold") {
      params.lien_amount_paise = parseInt(holdAmount, 10) * 100;
    } else if (type === "dispatch") {
      params.unit_id = unitId;
    }

    actionMutation.mutate(
      {
        alertId: alert.id,
        action: {
          type,
          reason: actionReason || undefined,
          params,
        },
      },
      {
        onSuccess: () => {
          setActiveActionModal(null);
          setActionReason("");
        },
      },
    );
  }

  // Convert alert timeline to UITimelineEntry[]
  const timelineItems: UITimelineEntry[] =
    alert.timeline.map((entry, idx) => ({
      id: `${entry.at}-${idx}`,
      timestamp: entry.at,
      title: humanizeStatus(entry.text_code.replace(/^alert\./, "")),
      description: Object.entries(entry.text_params)
        .map(([k, v]) => `${k}: ${v}`)
        .join(" | "),
      dotClass:
        entry.kind === "created"
          ? "nk-timeline__dot--info"
          : entry.kind === "actioned" || entry.kind === "request_hold"
            ? "nk-timeline__dot--warning"
            : entry.kind === "outcome"
              ? "nk-timeline__dot--success"
              : undefined,
    }));

  return (
    <Drawer
      open={Boolean(alertId)}
      onClose={onClose}
      title={`${alert.cluster_ref} · ${targetName}`}
      width="lg"
    >
      <div className="nk-alert-detail">
          {/* Subtitle */}
          <div className="nk-text-xs font-mono text-muted mb-2">
            Alert Ref: {alert.id}
          </div>

          {/* Novelty / Exploration Banner */}
          <NoveltyBanner isProbe={alert.is_probe} />

          {/* Badges & Scores */}
          <div className="nk-detail-top-card">
            <div className="nk-detail-badges">
              <SeverityBadge severity={alert.severity as Severity} />
              <StatusBadge status={alert.status as AlertStatus} />
              <LadderBadge level={alert.ladder_level as LadderLevel} />
            </div>

            <div className="nk-detail-metrics-row">
              <div className="nk-detail-metric">
                <span className="nk-text-xs text-muted">Confidence Score</span>
                <ConfidenceBar value={alert.confidence} />
              </div>
              <div className="nk-detail-metric">
                <span className="nk-text-xs text-muted">Window Expiry</span>
                <Countdown target={alert.expires_at} warnThreshold={900} />
              </div>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="nk-action-toolbar" role="toolbar" aria-label="Alert actions">
            <span className="nk-text-xs font-semibold uppercase tracking-wider text-muted">
              Response Actions
            </span>
            <div className="nk-action-btn-row">
              {canAck && alert.status === "open" && (
                <Button
                  size="sm"
                  variant="primary"
                  loading={actionMutation.isPending}
                  onClick={() => handleActionSubmit("acknowledge")}
                >
                  ✓ Acknowledge
                </Button>
              )}

              {canHold && (
                <Button
                  size="sm"
                  variant="danger"
                  disabled={alert.status === "actioned" || alert.status === "expired"}
                  onClick={() => setActiveActionModal("request_hold")}
                >
                  🔒 Request Hold
                </Button>
              )}

              {canDispatch && (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={alert.status === "actioned" || alert.status === "expired"}
                  onClick={() => setActiveActionModal("dispatch")}
                >
                  🚓 Dispatch Patrol
                </Button>
              )}

              {canNotify && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleActionSubmit("notify_station")}
                >
                  📢 Notify Station
                </Button>
              )}

              {canOverride && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setActiveActionModal("override")}
                >
                  ⚡ Override
                </Button>
              )}
            </div>
          </div>

          {/* Modal Action Forms */}
          {activeActionModal && (
            <div className="nk-action-dialog" role="dialog" aria-modal="true">
              <div className="nk-action-dialog-header">
                <span className="font-semibold">
                  {activeActionModal === "request_hold" && "Request Inter-Bank Lien Hold"}
                  {activeActionModal === "dispatch" && "Dispatch LEA Field Unit"}
                  {activeActionModal === "override" && "Operator Override Escalation"}
                </span>
                <button
                  className="nk-drawer__close"
                  onClick={() => setActiveActionModal(null)}
                >
                  ✕
                </button>
              </div>

              <div className="nk-action-dialog-body">
                {activeActionModal === "request_hold" && (
                  <div className="nk-form-group">
                    <label htmlFor="hold-amount-input" className="nk-label">
                      Proposed Lien Amount (₹)
                    </label>
                    <input
                      id="hold-amount-input"
                      type="number"
                      className="nk-input"
                      value={holdAmount}
                      onChange={(e) => setHoldAmount(e.target.value)}
                    />
                    <span className="nk-text-xs nk-text-secondary">
                      Must be at or below the disputed amount.
                    </span>
                  </div>
                )}

                {activeActionModal === "dispatch" && (
                  <div className="nk-form-group">
                    <label htmlFor="dispatch-unit-select" className="nk-label">
                      Select Interception Patrol Unit
                    </label>
                    <Select
                      id="dispatch-unit-select"
                      value={unitId}
                      onValueChange={setUnitId}
                      options={[
                        { value: "UNIT-CRIME-04", label: "Cyber Cell Delhi — Unit 04" },
                        { value: "UNIT-PCR-12", label: "PCR Van Connaught Place — Unit 12" },
                        { value: "UNIT-MUMBAI-09", label: "Bandra Beat Patrol — Unit 09" },
                      ]}
                    />
                  </div>
                )}

                <div className="nk-form-group">
                  <label htmlFor="action-reason-input" className="nk-label">
                    Action Justification / Operational Log
                    {activeActionModal === "override" && " (Mandatory)"}
                  </label>
                  <textarea
                    id="action-reason-input"
                    className="nk-textarea"
                    rows={2}
                    placeholder="Enter reason for audit record..."
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                  />
                </div>

                <div className="nk-action-dialog-footer">
                  <Button
                    size="sm"
                    variant="primary"
                    loading={actionMutation.isPending}
                    disabled={activeActionModal === "override" && !actionReason.trim()}
                    onClick={() => handleActionSubmit(activeActionModal)}
                  >
                    Confirm & Execute
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setActiveActionModal(null)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Target & Metadata Details */}
          <div className="nk-detail-section">
            <span className="nk-detail-section-title">Target Location & Network Anchor</span>
            <KeyValue
              items={[
                {
                  key: "Target Facility",
                  value: String(alert.target.name ?? alert.target.id ?? ""),
                },
                {
                  key: "Facility Kind",
                  value: String(alert.target.kind ?? ""),
                },
                {
                  key: "Cluster Association",
                  value: <MaskedRef value={alert.cluster_ref} masked={alert.masked} />,
                },
                {
                  key: "Trajectory Window",
                  value: `${formatSimTime(alert.window_start)} → ${formatSimTime(alert.window_end)}`,
                },
                {
                  key: "First Detected",
                  value: formatSimTime(alert.created_at),
                },
              ]}
            />
          </div>

          {/* Timing-Decay Curve */}
          {alert.forecast?.timing && (
            <div className="nk-detail-section">
              <span className="nk-detail-section-title">Cash-Out Timing Forecast</span>
              <TimingDecayCurve timing={alert.forecast.timing} />
            </div>
          )}

          {/* Interception Assessment — ladder-as-decision-path + proportionality safeguard */}
          {latestAssessment && (
            <div className="nk-detail-section">
              <span className="nk-detail-section-title">Interception Assessment</span>
              <LadderDecisionPath assessment={latestAssessment} expiresAt={alert.expires_at} />
              {latestAssessment.proportionality && (
                <ProportionalityStrip proportionality={latestAssessment.proportionality} />
              )}
            </div>
          )}

          {/* Evidence Timeline — horizontal, so the ingest -> ... -> alert -> action chain
              reads as the fast, single-request pipeline it actually is (DOC2 §2.1). */}
          <div className="nk-detail-section">
            <span className="nk-detail-section-title">Evidence & Audit Trail</span>
            <Timeline entries={timelineItems} orientation="horizontal" />
          </div>

          {/* Model Feedback Loop */}
          <div className="nk-detail-section">
            <FeedbackPanel
              alertId={alert.id}
              confidence={alert.confidence}
              evidence={alert.forecast?.evidence ?? []}
            />
          </div>

          {/* Post-Interception Outcome Logging */}
          <div className="nk-detail-section">
            <OutcomeButtons alertId={alert.id} />
          </div>

          {/* Court-Ready Evidence Pack */}
          <div className="nk-detail-section">
            <span className="nk-detail-section-title">Evidence Pack</span>
            <EvidencePackPanel alertId={alert.id} />
          </div>

          {/* Delivery Log — did the bank/station/email actually get notified? (§4.6) */}
          <div className="nk-detail-section">
            <span className="nk-detail-section-title">Delivery Log</span>
            <DeliveryLog deliveries={alert.deliveries} />
          </div>
      </div>
    </Drawer>
  );
}
