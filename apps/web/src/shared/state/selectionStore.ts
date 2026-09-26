/**
 * selectionStore.ts — the one "selected entity" shared across screens.
 *
 * Clicking an alert row, a graph node or a palette result writes here; the map reads it and
 * flies to / highlights the match (overhaul plan §2.3 "linked selection"). A plain
 * useSyncExternalStore module: one shared value does not justify a state library, and living
 * under shared/ is what lets features reach each other without importing each other.
 *
 * It also carries a one-shot "pending action" so the command palette can ask the alerts
 * screen to open a hold/dispatch dialog for the selected alert once that screen is mounted.
 */

import { useSyncExternalStore } from "react";

export type SelectionKind = "alert" | "location" | "account" | "cluster";

export interface Selection {
  kind: SelectionKind;
  id: string;
}

export interface PendingAction {
  type: "request_hold" | "dispatch";
  nonce: number;
}

let selection: Selection | null = null;
let pending: PendingAction | null = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export const selectionStore = {
  get: (): Selection | null => selection,
  set(next: Selection | null): void {
    if (selection?.kind === next?.kind && selection?.id === next?.id) return;
    selection = next;
    emit();
  },
  clear(): void {
    selection = null;
    pending = null;
    emit();
  },
  requestAction(type: PendingAction["type"]): void {
    pending = { type, nonce: Date.now() };
    emit();
  },
  /** Take the pending action (one-shot): the alerts screen calls this once it has acted on it. */
  consumePendingAction(): PendingAction | null {
    const p = pending;
    if (p) {
      pending = null;
      emit();
    }
    return p;
  },
  getPendingAction: (): PendingAction | null => pending,
};

export function useSelection(): Selection | null {
  return useSyncExternalStore(subscribe, selectionStore.get, () => null);
}

export function usePendingAction(): PendingAction | null {
  return useSyncExternalStore(subscribe, selectionStore.getPendingAction, () => null);
}
