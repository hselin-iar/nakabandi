/**
 * tacticalPing.ts — short synthesized alert cue. Web Audio oscillator: no audio asset,
 * no network, works on the offline path. Severity picks the pitch; CRITICAL also sweeps down.
 */

import type { Severity } from "../api/enums.ts";

const FREQ: Record<Severity, number> = {
  CRITICAL: 880,
  HIGH: 659.25,
  MEDIUM: 587.33,
  LOW: 440,
};

type AudioCtor = typeof AudioContext;
let ctx: AudioContext | null = null;

function getContext(): AudioContext | null {
  try {
    if (!ctx) {
      const Ctor: AudioCtor | undefined =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext;
      if (!Ctor) return null;
      ctx = new Ctor();
    }
    return ctx;
  } catch {
    return null;
  }
}

/**
 * Browsers keep an AudioContext suspended until a user gesture. Call once early (first
 * click/keypress anywhere) so later pings are allowed to play.
 */
export function armAudio(): void {
  const c = getContext();
  if (c && c.state === "suspended") void c.resume().catch(() => undefined);
}

export function playTacticalPing(severity: Severity): void {
  const c = getContext();
  if (!c || c.state !== "running") return; // autoplay-blocked: degrade silently
  try {
    const now = c.currentTime;
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.connect(gain);
    gain.connect(c.destination);
    osc.frequency.setValueAtTime(FREQ[severity], now);
    if (severity === "CRITICAL") osc.frequency.exponentialRampToValueAtTime(440, now + 0.15);
    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
    osc.start(now);
    osc.stop(now + 0.15);
  } catch {
    /* never let a sound cue break the alert flow */
  }
}
