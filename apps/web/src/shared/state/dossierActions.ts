/**
 * dossierActions.ts — what the currently open case dossier's graph can do, published for the
 * command palette. The graph registers its handlers while mounted; the palette shows the
 * dossier commands only when something is registered. (shared/ so the palette in app/ and the
 * graph in features/ never import each other.)
 */

import { useSyncExternalStore } from "react";

export interface DossierActions {
  /** Highest hop layer in the loaded graph. */
  maxHop: number;
  showHopsUpTo(hop: number): void;
  isolateSelected(): void;
  hasSelection(): boolean;
  exportPng(): void;
  exportCsv(): void;
}

let current: DossierActions | null = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function registerDossierActions(actions: DossierActions): () => void {
  current = actions;
  emit();
  return () => {
    if (current === actions) {
      current = null;
      emit();
    }
  };
}

export function useDossierActions(): DossierActions | null {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => {
        listeners.delete(cb);
      };
    },
    () => current,
    () => null,
  );
}
