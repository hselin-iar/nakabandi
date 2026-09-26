/**
 * ConsequenceTally.tsx — "Held ₹X · N actions" readout.
 *
 * Purely presentational: the alerts feature owns the numbers (they tick up the instant a
 * hold is requested and reconcile to what the bank actually applied). Lives next to the
 * action it reflects so a freeze feels immediate and tangible.
 */

import { RollingCounter } from "./RollingCounter";
import { formatInr } from "../lib/format";

interface ConsequenceTallyProps {
  /** Total held, integer paise (optimistic until reconciled). */
  heldPaise: number;
  /** Holds requested this session. */
  actionCount: number;
  /** Holds still awaiting the bank's confirmation. */
  pendingCount?: number;
}

export function ConsequenceTally({ heldPaise, actionCount, pendingCount = 0 }: ConsequenceTallyProps) {
  return (
    <div className="nk-tally" role="status" aria-label="Funds held this session">
      <span className="nk-tally__label">Held</span>
      <RollingCounter
        className="nk-tally__value"
        value={heldPaise}
        format={(n) => formatInr(Math.round(n), { compact: true })}
      />
      <span className="nk-tally__meta data-digit">
        {actionCount} {actionCount === 1 ? "action" : "actions"}
        {pendingCount > 0 ? ` · ${pendingCount} pending` : ""}
      </span>
    </div>
  );
}
