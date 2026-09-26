/**
 * DeliveryLog.tsx — this alert's own delivery log, inline in its focus panel.
 * Frontend Strategy §4.6: "the delivery log for a specific alert (already returned inline in
 * GET /alerts/{id} as deliveries[]) should render inside that alert's focus panel — an officer
 * checking 'did the bank actually get notified' shouldn't have to leave the alert to find out."
 */

import React from "react";
import { DeliveryStatusBadge } from "../../shared/ui/Badge";
import { formatSimTime } from "../../shared/lib/format";
import type { DeliveryStatus } from "../../shared/api/enums.ts";
import type { DeliveryModel } from "../../shared/api/types.ts";

interface DeliveryLogProps {
  deliveries: DeliveryModel[];
}

export function DeliveryLog({ deliveries }: DeliveryLogProps) {
  if (deliveries.length === 0) {
    return <p className="nk-text-xs text-muted italic">No deliveries queued for this alert.</p>;
  }

  return (
    <div className="nk-delivery-log">
      {deliveries.map((d, idx) => (
        <div className="nk-delivery-log__row" key={`${d.channel}-${idx}`}>
          <span className="nk-delivery-log__channel">{d.channel}</span>
          <DeliveryStatusBadge status={d.status as DeliveryStatus} />
          <span className="nk-text-xs text-muted">
            {d.attempts} attempt{d.attempts === 1 ? "" : "s"}
            {d.sent_at && ` · sent ${formatSimTime(d.sent_at)}`}
          </span>
        </div>
      ))}
    </div>
  );
}
