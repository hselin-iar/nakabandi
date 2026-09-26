import { describe, it, expect, afterEach, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { CountdownRing, remainingFraction, ringBand } from "../CountdownRing";

vi.mock("../../time/TimeProvider", () => ({ useTactileTime: vi.fn() }));
import { useTactileTime } from "../../time/TimeProvider";

const CREATED = "2026-01-15T10:00:00Z";
const EXPIRES = "2026-01-15T11:00:00Z"; // a 60-minute window
const at = (iso: string) => new Date(iso).getTime();

afterEach(cleanup);

describe("remainingFraction / ringBand", () => {
  it("is 1 at the start, 0.5 halfway, 0 at expiry, and clamps outside the window", () => {
    expect(remainingFraction(at(CREATED), CREATED, EXPIRES)).toBe(1);
    expect(remainingFraction(at("2026-01-15T10:30:00Z"), CREATED, EXPIRES)).toBe(0.5);
    expect(remainingFraction(at(EXPIRES), CREATED, EXPIRES)).toBe(0);
    expect(remainingFraction(at("2026-01-15T12:00:00Z"), CREATED, EXPIRES)).toBe(0);
    expect(remainingFraction(at("2026-01-15T09:00:00Z"), CREATED, EXPIRES)).toBe(1);
  });

  it("returns null when time or the window is unusable", () => {
    expect(remainingFraction(null, CREATED, EXPIRES)).toBeNull();
    expect(remainingFraction(1, "garbage", EXPIRES)).toBeNull();
    expect(remainingFraction(1, EXPIRES, CREATED)).toBeNull();
  });

  it("steps through the severity bands at 50% and 20%", () => {
    expect(ringBand(0.9, 3000)).toBe("ok");
    expect(ringBand(0.5, 1800)).toBe("warn");
    expect(ringBand(0.21, 700)).toBe("warn");
    expect(ringBand(0.2, 600)).toBe("urgent");
    expect(ringBand(0, 0)).toBe("expired");
  });
});

describe("CountdownRing", () => {
  it("shows an idle placeholder before the first sim.time tick", () => {
    vi.mocked(useTactileTime).mockReturnValue(null);
    render(<CountdownRing createdAt={CREATED} expiresAt={EXPIRES} />);
    expect(screen.getByLabelText("Time remaining unknown")).toBeTruthy();
  });

  it("drains with sim time, changes band, and pulses when urgent", () => {
    vi.mocked(useTactileTime).mockReturnValue(at("2026-01-15T10:15:00Z")); // 75% left
    const { container, rerender } = render(<CountdownRing createdAt={CREATED} expiresAt={EXPIRES} />);
    expect(screen.getByLabelText("Time remaining: 45m 0s")).toBeTruthy();
    expect(container.querySelector(".nk-ring--ok")).toBeTruthy();

    vi.mocked(useTactileTime).mockReturnValue(at("2026-01-15T10:52:00Z")); // ~13% left
    rerender(<CountdownRing createdAt={CREATED} expiresAt={EXPIRES} />);
    expect(container.querySelector(".nk-ring--urgent")).toBeTruthy();
    expect(container.querySelector(".nk-countdown--urgent")).toBeTruthy();

    // dashoffset is the un-remaining share of the circumference
    const arc = container.querySelector(".nk-ring__arc")!;
    const c = 2 * Math.PI * 14;
    expect(Number(arc.getAttribute("stroke-dashoffset"))).toBeCloseTo(c * (1 - 8 / 60), 3);
  });
});
