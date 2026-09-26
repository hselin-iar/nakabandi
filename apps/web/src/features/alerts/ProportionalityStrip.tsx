/**
 * ProportionalityStrip.tsx — makes the lien proportionality safeguard load-bearing, not a
 * compliance footnote. DOC1 §1.2 M6 acceptance: "An L1 recommendation always shows a
 * PROPORTIONALITY PANEL: traced disputed amount, proposed lien amount (never above the
 * disputed amount), expiry/review time, and a reminder that the seizure must be reported
 * to the Magistrate. No whole-account freeze option exists in the UI."
 */

import React from "react";
import { ConfidenceBar } from "../../shared/ui/ConfidenceBar";
import { formatInr, formatSimTime } from "../../shared/lib/format";
import type { ProportionalityModel } from "../../shared/api/types.ts";
import { Icon } from "../../shared/ui/Icon";

interface ProportionalityStripProps {
  proportionality: ProportionalityModel;
}

export function ProportionalityStrip({ proportionality }: ProportionalityStripProps) {
  const pct = Math.round(Math.min(1, Math.max(0, proportionality.ratio)) * 100);

  return (
    <div className="nk-proportionality-strip" aria-label="Proportionality safeguard">
      <span className="nk-text-xs font-semibold uppercase tracking-wider text-muted">
        Proportionality Safeguard
      </span>

      <div className="nk-proportionality-strip__amounts">
        <div>
          <span className="nk-text-xs text-muted">Disputed Amount</span>
          <div className="font-mono font-semibold">{formatInr(proportionality.disputed_paise)}</div>
        </div>
        <div>
          <span className="nk-text-xs text-muted">Proposed Lien (capped)</span>
          <div className="font-mono font-semibold">{formatInr(proportionality.proposed_paise)}</div>
        </div>
      </div>

      <ConfidenceBar value={proportionality.ratio} label={`${pct}% of disputed amount`} />

      <div className="nk-proportionality-strip__meta">
        <span>Review by {formatSimTime(proportionality.review_at)}</span>
        <span>Expires {formatSimTime(proportionality.expires_at)}</span>
      </div>

      {proportionality.magistrate_report_reminder && (
        <div className="nk-proportionality-strip__reminder" role="note">
          <Icon name="scale" /> This lien must be reported to the Magistrate. It is capped, time-boxed, and
          anchored to this complaint — there is no whole-account freeze option in this system.
        </div>
      )}
    </div>
  );
}
