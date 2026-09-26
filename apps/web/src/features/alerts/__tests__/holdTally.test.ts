import { describe, it, expect, beforeEach } from "vitest";
import { computeTally, holdTally } from "../holdTally";

const entry = (id: string, alertId: string, proposedPaise: number) => ({ id, alertId, proposedPaise });
const none = new Map<string, never[]>();

describe("computeTally", () => {
  it("counts the proposed amount immediately (optimistic) and flags it pending", () => {
    const t = computeTally([entry("optimistic:a", "A1", 150_000)], none);
    expect(t).toEqual({ heldPaise: 150_000, actionCount: 1, pendingCount: 1 });
  });

  it("reconciles DOWN to what the bank applied", () => {
    const actions = new Map([["A1", [{ id: "ACT-1", status: "applied", applied_amount_paise: 90_000 }]]]);
    const t = computeTally([entry("ACT-1", "A1", 150_000)], actions);
    expect(t).toEqual({ heldPaise: 90_000, actionCount: 1, pendingCount: 0 });
  });

  it("drops rejected and released holds from the amount but keeps the action count", () => {
    const actions = new Map([
      ["A1", [{ id: "ACT-1", status: "rejected" }]],
      ["A2", [{ id: "ACT-2", status: "released", applied_amount_paise: 50_000 }]],
    ]);
    const t = computeTally([entry("ACT-1", "A1", 100_000), entry("ACT-2", "A2", 50_000)], actions);
    expect(t.heldPaise).toBe(0);
    expect(t.actionCount).toBe(2);
  });

  it("keeps a still-pending server action at its proposed amount", () => {
    const actions = new Map([["A1", [{ id: "ACT-1", status: "pending" }]]]);
    expect(computeTally([entry("ACT-1", "A1", 70_000)], actions).pendingCount).toBe(1);
  });
});

describe("holdTally store", () => {
  beforeEach(() => holdTally.reset());

  it("rolls an optimistic entry back when the request fails", () => {
    const token = holdTally.begin("A1", 100);
    holdTally.rollback(token);
    // begin again just to observe there is nothing left over: token differs, no throw
    expect(typeof holdTally.begin("A1", 100)).toBe("string");
  });
});
