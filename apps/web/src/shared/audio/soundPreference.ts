/**
 * soundPreference.ts — per-device "play alert sounds" preference.
 * localStorage, not sessionStorage: it is a device setting the operator should not have
 * to re-set in every tab. Every access is wrapped: storage can throw (private windows,
 * blocked site data) and the app must behave with sound simply off.
 */

import { useSyncExternalStore } from "react";

const KEY = "nk.sound";
const listeners = new Set<() => void>();

export function isSoundEnabled(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "on";
  } catch {
    return false;
  }
}

export function setSoundEnabled(on: boolean): void {
  try {
    window.localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    /* unavailable: preference just isn't remembered */
  }
  for (const l of listeners) l();
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function useSoundEnabled(): boolean {
  return useSyncExternalStore(subscribe, isSoundEnabled, () => false);
}
