/**
 * shortcutRegistry.ts — tiny store of the keyboard shortcuts currently active.
 *
 * Each screen registers its own scope ("triage-inbox", "map", …) while mounted; the
 * ShortcutSheet renders whatever is registered, so the cheat-sheet can never drift
 * from the real bindings (overhaul plan §1.4a).
 */

import { useEffect, useSyncExternalStore } from "react";

export interface ShortcutEntry {
  /** Human-readable key combo, e.g. "J / K" or "⌘ K". */
  keys: string;
  description: string;
}

export interface ShortcutScope {
  scope: string;
  title: string;
  entries: readonly ShortcutEntry[];
}

let scopes: readonly ShortcutScope[] = [];
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

/** Register (or replace) a scope; returns the unregister function. */
export function registerShortcuts(next: ShortcutScope): () => void {
  scopes = [...scopes.filter((s) => s.scope !== next.scope), next];
  emit();
  return () => {
    scopes = scopes.filter((s) => s !== next);
    emit();
  };
}

/** Register a scope for the lifetime of the calling component. */
export function useRegisterShortcuts(scope: ShortcutScope): void {
  useEffect(() => registerShortcuts(scope), [scope]);
}

export function useActiveShortcuts(): readonly ShortcutScope[] {
  return useSyncExternalStore(subscribe, () => scopes);
}

// ---------------------------------------------------------------------------
// Sheet open state (so the command palette can open the cheat-sheet too)
// ---------------------------------------------------------------------------

let sheetOpen = false;
const sheetListeners = new Set<() => void>();

export function setShortcutSheetOpen(open: boolean): void {
  if (sheetOpen === open) return;
  sheetOpen = open;
  for (const l of sheetListeners) l();
}

export function useShortcutSheetOpen(): boolean {
  return useSyncExternalStore(
    (cb) => {
      sheetListeners.add(cb);
      return () => {
        sheetListeners.delete(cb);
      };
    },
    () => sheetOpen,
    () => false,
  );
}
