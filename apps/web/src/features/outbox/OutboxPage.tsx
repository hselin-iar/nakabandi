/**
 * OutboxPage.tsx — Outbox delivery list with expandable rendered_body.
 * DOC 3 §M4 (outbox, channels, rendered_body) · DOC 4 Step C7
 *
 * Shows all deliveries with status badges and expandable body preview.
 * Stub until Track A Step A8 (/outbox endpoint) lands.
 */

import React, { useState } from "react";
import { useOutboxDeliveries } from "./api/useOutbox";
import type { Delivery, DeliveryStatus } from "./api/useOutbox";
import { EmptyState } from "../../shared/ui/EmptyState";

// ---------------------------------------------------------------------------
// Delivery status badge
// ---------------------------------------------------------------------------

const STATUS_META: Record<
  DeliveryStatus,
  { label: string; colorClass: string; icon: string }
> = {
  delivered: { label: "Delivered", colorClass: "nk-dlv-status--delivered", icon: "✓" },
  pending:   { label: "Pending",   colorClass: "nk-dlv-status--pending",   icon: "◷" },
  retrying:  { label: "Retrying",  colorClass: "nk-dlv-status--retrying",  icon: "↻" },
  failed:    { label: "Failed",    colorClass: "nk-dlv-status--failed",    icon: "✗" },
};

function DeliveryStatusBadge({ status }: { status: DeliveryStatus }) {
  const m = STATUS_META[status];
  return (
    <span className={`nk-badge nk-dlv-status ${m.colorClass}`} aria-label={m.label}>
      <span className="nk-badge__icon" aria-hidden="true">{m.icon}</span>
      <span className="nk-badge__label">{m.label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// DeliveryRow (expandable)
// ---------------------------------------------------------------------------

function DeliveryRow({ d }: { d: Delivery }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className="nk-table__row nk-table__row--clickable"
        onClick={() => setExpanded((v) => !v)}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
        aria-expanded={expanded}
        data-testid={`outbox-row-${d.delivery_id}`}
      >
        <td className="nk-table__td">
          <code className="nk-mono nk-size-12">{d.delivery_id}</code>
        </td>
        <td className="nk-table__td">
          <code className="nk-mono nk-size-12">{d.alert_id}</code>
        </td>
        <td className="nk-table__td">
          <code className="nk-mono nk-size-12">{d.channel}</code>
        </td>
        <td className="nk-table__td">
          <DeliveryStatusBadge status={d.status} />
        </td>
        <td className="nk-table__td nk-table__td--right">
          {d.attempt_count}
        </td>
        <td className="nk-table__td nk-outbox-time">
          {new Date(d.created_at).toLocaleString("en-IN", {
            day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false,
          })}
        </td>
        <td className="nk-table__td nk-outbox-time">
          {d.delivered_at
            ? new Date(d.delivered_at).toLocaleString("en-IN", {
                day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false,
              })
            : <span className="nk-text-secondary">—</span>}
        </td>
        <td className="nk-table__td nk-text-secondary nk-size-12">
          {expanded ? "▲" : "▼"}
        </td>
      </tr>

      {/* Expanded body */}
      {expanded && (
        <tr className="nk-outbox-body-row" data-testid={`outbox-body-${d.delivery_id}`}>
          <td colSpan={8} className="nk-outbox-body-cell">
            <div className="nk-outbox-body-header">
              <span>rendered_body</span>
              {d.last_error && (
                <span className="nk-outbox-last-error" role="alert">
                  ⚠ Last error: {d.last_error}
                </span>
              )}
            </div>
            <pre className="nk-rendered-body">{d.rendered_body}</pre>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// OutboxPage
// ---------------------------------------------------------------------------

export default function OutboxPage() {
  const { data: deliveries, isLoading, error } = useOutboxDeliveries();

  if (isLoading) {
    return (
      <div className="nk-page-loading" aria-live="polite">
        Loading outbox…
      </div>
    );
  }

  if (error) {
    return (
      <div className="nk-error-state" role="alert">
        <span className="nk-error-state__icon" aria-hidden="true">⚠</span>
        <p className="nk-error-state__message">Could not load delivery outbox. Please retry.</p>
      </div>
    );
  }

  if (!deliveries?.length) {
    return (
      <EmptyState
        title="No deliveries"
        message="No outbox deliveries have been recorded yet."
      />
    );
  }

  const failedCount = deliveries.filter((d) => d.status === "failed").length;

  return (
    <main className="nk-outbox-page" data-testid="outbox-page">
      <header className="nk-outbox-page__header">
        <h1 className="nk-outbox-page__title">Delivery Outbox</h1>
        <p className="nk-outbox-page__subtitle">
          {deliveries.length} deliveries · {failedCount > 0
            ? <><span className="nk-text-bad">⚠ {failedCount} failed</span></>
            : "all channels healthy"}
        </p>
      </header>

      <div className="nk-table-wrapper" data-testid="outbox-table">
        <table className="nk-table">
          <caption className="nk-table__caption">Outbox deliveries (click row to expand body)</caption>
          <thead>
            <tr>
              <th className="nk-table__th">Delivery</th>
              <th className="nk-table__th">Alert</th>
              <th className="nk-table__th">Channel</th>
              <th className="nk-table__th">Status</th>
              <th className="nk-table__th nk-table__th--right">Attempts</th>
              <th className="nk-table__th">Created</th>
              <th className="nk-table__th">Delivered</th>
              <th className="nk-table__th" aria-label="Expand" />
            </tr>
          </thead>
          <tbody>
            {deliveries.map((d) => (
              <DeliveryRow key={d.delivery_id} d={d} />
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
