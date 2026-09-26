/**
 * AttentionBudgetStrip.tsx — surfaces the alert budget/triage-tier split as a trust
 * signal, not an invisible backend policy. Frontend Strategy §4.2/§7.6: "we are
 * deliberately not showing you everything, on purpose, so you don't rubber-stamp."
 *
 * Uses only real counts from GET /alerts?view=queue|backlog — no fabricated total
 * (the configured shift budget, config/policy.yaml alerting.budget_per_shift, is not
 * exposed by any endpoint, so it is not hardcoded here — AP-10).
 */

import React from "react";

interface AttentionBudgetStripProps {
  shownCount: number;
  backlogCount: number;
}

export function AttentionBudgetStrip({ shownCount, backlogCount }: AttentionBudgetStripProps) {
  const total = shownCount + backlogCount;

  return (
    <div className="nk-attention-budget-strip" role="note" aria-label="Attention budget">
      <span className="nk-attention-budget-strip__text">
        Showing <strong>{shownCount}</strong> alert{shownCount === 1 ? "" : "s"}
        {backlogCount > 0 && (
          <>
            {" "}
            · <strong>{backlogCount}</strong> deferred to protect your attention
          </>
        )}
        {total > 0 && ` · ${total} raised this shift`}
      </span>
      {backlogCount > 0 && (
        <span className="nk-attention-budget-strip__note nk-text-xs text-muted">
          Deferred alerts are lower-priority right now, not dropped — they stay reachable in
          the backlog.
        </span>
      )}
    </div>
  );
}
