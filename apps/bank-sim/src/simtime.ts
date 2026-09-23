/**
 * simtime.ts — SimTimeSource: sim-time provider for bank-sim.
 * DOC 3 Bank Gateway Simulator: "SimTimeSource: polls SIM_STATUS_URL, falls back to
 * last webhook time." NEVER use wall time for lien expiry or domain logic.
 *
 * SimTimeSource is injected into lien and callback logic so tests can
 * supply a fixed sim time without touching the network.
 */

import { config } from "./config.js";

// ---------------------------------------------------------------------------
// SimTimeSource interface — injectable for tests
// ---------------------------------------------------------------------------

/** Provides the current sim time as an ISO-8601 string. */
export interface SimTimeSource {
  /** Returns the latest known sim time. */
  now(): string;
  /** Feed a new sim time from an incoming webhook. */
  updateFromWebhook(simTime: string): void;
  /** Start background polling (no-op in test implementations). */
  startPolling(): void;
  /** Stop background polling (no-op in test implementations). */
  stopPolling(): void;
}

// ---------------------------------------------------------------------------
// Live implementation — polls SIM_STATUS_URL
// ---------------------------------------------------------------------------

/**
 * LiveSimTimeSource polls SIM_STATUS_URL every 10 s.
 * Falls back to the latest webhook sim_time when the poll fails.
 *
 * DOC 3: "Sim time source unavailable: use the latest webhook's sim time;
 * never use wall time for lien expiry."
 */
export class LiveSimTimeSource implements SimTimeSource {
  private latestSimTime: string | null = null;
  private pollInterval: ReturnType<typeof setInterval> | null = null;

  private async poll(): Promise<void> {
    try {
      const res = await fetch(config.simStatusUrl, { signal: AbortSignal.timeout(5000) });
      if (!res.ok) return;
      const data = (await res.json()) as { sim_time?: string };
      if (typeof data.sim_time === "string" && data.sim_time) {
        this.latestSimTime = data.sim_time;
      }
    } catch {
      // Intentionally swallowed — fallback to last webhook time is the design.
    }
  }

  now(): string {
    if (!this.latestSimTime) {
      throw new Error(
        "[bank-sim] SimTimeSource: no sim time available yet. " +
          "Wait for the first webhook or for SIM_STATUS_URL to respond.",
      );
    }
    return this.latestSimTime;
  }

  updateFromWebhook(simTime: string): void {
    // Only update if the webhook time is strictly after the last known time.
    if (!this.latestSimTime || simTime > this.latestSimTime) {
      this.latestSimTime = simTime;
    }
  }

  startPolling(): void {
    // Run one immediate poll, then every 10 s.
    void this.poll();
    this.pollInterval = setInterval(() => void this.poll(), 10_000);
  }

  stopPolling(): void {
    if (this.pollInterval !== null) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }
}

// ---------------------------------------------------------------------------
// Stub implementation for tests
// ---------------------------------------------------------------------------

/** Fixed sim time — use in tests to make time deterministic. */
export class FixedSimTimeSource implements SimTimeSource {
  constructor(private time: string) {}
  now(): string { return this.time; }
  updateFromWebhook(simTime: string): void { this.time = simTime; }
  startPolling(): void { /* no-op */ }
  stopPolling(): void { /* no-op */ }
  /** Advance to a new sim time (test helper). */
  setTime(t: string): void { this.time = t; }
}

// ---------------------------------------------------------------------------
// Module-level singleton (replaced by tests via createApp())
// ---------------------------------------------------------------------------

export const simTimeSource: SimTimeSource = new LiveSimTimeSource();
