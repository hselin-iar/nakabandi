/**
 * format.test.ts — unit tests for shared/lib/format.ts
 * DOC 3 C3 Done When: format helpers tested.
 */

import { describe, it, expect } from "vitest";
import {
  paiseToInr,
  formatInr,
  formatSimTime,
  formatDuration,
} from "../format";

describe("paiseToInr", () => {
  it("converts 100 paise to 1 INR", () => {
    expect(paiseToInr(100)).toBe(1);
  });
  it("converts 150050 paise to 1500.5 INR", () => {
    expect(paiseToInr(150050)).toBe(1500.5);
  });
  it("handles 0", () => {
    expect(paiseToInr(0)).toBe(0);
  });
});

describe("formatInr", () => {
  it("formats small amount", () => {
    expect(formatInr(100)).toBe("₹1.00");
  });
  it("formats thousands with Indian grouping", () => {
    expect(formatInr(100000)).toBe("₹1,000.00");
  });
  it("formats lakhs with Indian grouping", () => {
    expect(formatInr(10000000)).toBe("₹1,00,000.00");
  });
  it("formats crores with Indian grouping", () => {
    expect(formatInr(1000000000)).toBe("₹1,00,00,000.00");
  });
  it("compact: lakh", () => {
    expect(formatInr(150_000_000, { compact: true })).toBe("₹15.0L");
  });
  it("compact: crore", () => {
    expect(formatInr(2_000_000_000, { compact: true })).toBe("₹2.00Cr");
  });
  it("handles negative", () => {
    const result = formatInr(-10000);
    expect(result).toContain("-₹");
  });
});

describe("formatSimTime", () => {
  it("formats ISO datetime to readable string", () => {
    expect(formatSimTime("2026-01-15T10:30:00Z")).toBe("15 Jan 2026, 10:30");
  });
  it("includes seconds when requested", () => {
    expect(formatSimTime("2026-01-15T10:30:45Z", { includeSeconds: true })).toBe(
      "15 Jan 2026, 10:30:45",
    );
  });
  it("returns input unchanged for invalid ISO", () => {
    expect(formatSimTime("not-a-date")).toBe("not-a-date");
  });
});

describe("formatDuration", () => {
  it("formats 0 seconds", () => {
    expect(formatDuration(0)).toBe("0s");
  });
  it("formats seconds only", () => {
    expect(formatDuration(45)).toBe("0m 45s");
  });
  it("formats minutes and seconds", () => {
    expect(formatDuration(90)).toBe("1m 30s");
  });
  it("formats hours and minutes", () => {
    expect(formatDuration(3661)).toBe("1h 1m");
  });
  it("formats negative duration", () => {
    expect(formatDuration(-60)).toBe("-1m 0s");
  });
});
