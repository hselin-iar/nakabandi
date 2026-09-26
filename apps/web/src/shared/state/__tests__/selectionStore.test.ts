import { describe, it, expect, beforeEach } from "vitest";
import { selectionStore } from "../selectionStore";

beforeEach(() => selectionStore.clear());

describe("selectionStore", () => {
  it("holds one shared selection and clears it", () => {
    expect(selectionStore.get()).toBeNull();
    selectionStore.set({ kind: "alert", id: "ALT-1" });
    expect(selectionStore.get()).toEqual({ kind: "alert", id: "ALT-1" });
    selectionStore.clear();
    expect(selectionStore.get()).toBeNull();
  });

  it("hands a requested action over exactly once", () => {
    selectionStore.set({ kind: "alert", id: "ALT-1" });
    selectionStore.requestAction("request_hold");
    const first = selectionStore.consumePendingAction();
    expect(first?.type).toBe("request_hold");
    expect(selectionStore.consumePendingAction()).toBeNull();
  });
});
