import { describe, it, expect } from "vitest";
import { interpolateSimMs, nextAnchor } from "../TimeProvider";

describe("sim-time interpolation", () => {
  it("starts at real-time rate on the first tick", () => {
    const a = nextAnchor(null, 1_000_000, 500);
    expect(a.rate).toBe(1);
    expect(interpolateSimMs(a, 1_000)).toBe(1_000_000 + 500);
  });

  it("derives the rate from the last two ticks (a sim running 60x)", () => {
    const first = nextAnchor(null, 0, 0);
    const second = nextAnchor(first, 60_000, 1_000); // 60 s of sim in 1 s of wall
    expect(second.rate).toBe(60);
    expect(interpolateSimMs(second, 1_500)).toBe(60_000 + 500 * 60);
  });

  it("stops extrapolating when ticks stop (simulator paused), instead of running on", () => {
    const first = nextAnchor(null, 0, 0);
    const second = nextAnchor(first, 1_000, 1_000); // rate 1, 1 s interval -> 2 s grace, min 1.5 s
    const long = interpolateSimMs(second, 60_000);
    expect(long).toBe(1_000 + 2_000);
  });

  it("restarts at real-time rate when the sim clock moves backwards (reset)", () => {
    const first = nextAnchor(null, 5_000, 0);
    const reset = nextAnchor(first, 1_000, 1_000);
    expect(reset.rate).toBe(1);
    expect(reset.simMs).toBe(1_000);
  });

  it("caps an absurd rate", () => {
    const first = nextAnchor(null, 0, 0);
    const wild = nextAnchor(first, 1e12, 10);
    expect(wild.rate).toBeLessThanOrEqual(3_600);
  });
});
