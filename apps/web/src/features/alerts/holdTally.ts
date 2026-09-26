/**
 * holdTally.ts — session tally of funds held ("Held ₹X · N actions").
 *
 * The number ticks up the instant a hold is requested (optimistic, at the proposed amount),
 * then reconciles to what the bank actually did, read from the alert's own actions:
 *   pending  -> counts the proposed amount, flagged as awaiting the bank
 *   applied  -> counts applied_amount_paise (which may be LESS than proposed)
 *   rejected / released -> counts nothing
 * A failed request removes its optimistic entry. Nothing here is a new endpoint: the store is
 * fed by the mutation lifecycle and reconciled from GET /alerts/{id}.
 */

import { useMemo, useSyncExternalStore } from "react";
import { useQueries } from "@tanstack/react-query";
import { streamKeys } from "../../shared/stream/streamKeys";
import { fetchAlertDetail } from "./api/useAlerts";

interface TallyEntry {
  /** Optimistic id until the server's action id is known. */
  id: string;
  alertId: string;
  proposedPaise: number;
}

let entries: readonly TallyEntry[] = [];
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export const holdTally = {
  /** Called the moment a hold actuates; returns a token to settle or roll back. */
  begin(alertId: string, proposedPaise: number): string {
    const id = `optimistic:${alertId}:${entries.length}:${Date.now()}`;
    entries = [...entries, { id, alertId, proposedPaise }];
    emit();
    return id;
  },
  /** The server accepted the request: swap the optimistic id for the real action id. */
  confirm(token: string, actionId: string): void {
    entries = entries.map((e) => (e.id === token ? { ...e, id: actionId } : e));
    emit();
  },
  /** The request failed: take the optimistic amount back out. */
  rollback(token: string): void {
    entries = entries.filter((e) => e.id !== token);
    emit();
  },
  /** Test helper. */
  reset(): void {
    entries = [];
    emit();
  },
};

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export interface HoldTallyState {
  heldPaise: number;
  actionCount: number;
  pendingCount: number;
}

interface ActionLike {
  id: string;
  status: string;
  applied_amount_paise?: number | null;
}

/** Pure: fold entries + the latest known actions per alert into the displayed tally. */
export function computeTally(
  list: readonly TallyEntry[],
  actionsByAlert: ReadonlyMap<string, readonly ActionLike[]>,
): HoldTallyState {
  let heldPaise = 0;
  let pendingCount = 0;
  for (const e of list) {
    const action = actionsByAlert.get(e.alertId)?.find((a) => a.id === e.id);
    if (!action || action.status === "pending") {
      heldPaise += e.proposedPaise;
      pendingCount += 1;
    } else if (action.status === "applied") {
      heldPaise += action.applied_amount_paise ?? e.proposedPaise;
    }
    // rejected / released contribute nothing
  }
  return { heldPaise, actionCount: list.length, pendingCount };
}

export function useHoldTally(): HoldTallyState {
  const list = useSyncExternalStore(subscribe, () => entries);
  const alertIds = useMemo(() => [...new Set(list.map((e) => e.alertId))], [list]);

  const results = useQueries({
    queries: alertIds.map((id) => ({
      queryKey: streamKeys.alert(id),
      queryFn: () => fetchAlertDetail(id),
      staleTime: 5_000,
    })),
  });

  const actionsByAlert = useMemo(() => {
    const m = new Map<string, readonly ActionLike[]>();
    results.forEach((r, i) => {
      if (r.data) m.set(alertIds[i]!, r.data.actions);
    });
    return m;
  }, [results, alertIds]);

  return useMemo(() => computeTally(list, actionsByAlert), [list, actionsByAlert]);
}
