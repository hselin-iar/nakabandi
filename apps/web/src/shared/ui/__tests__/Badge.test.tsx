/**
 * Badge.test.tsx — component tests for Badge variants.
 * DOC 3 C3 Done When: Badge variants render label + icon + colour.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { SeverityBadge, VerdictBadge, LadderBadge, StatusBadge } from "../Badge";

describe("SeverityBadge", () => {
  it("renders label for LOW severity", () => {
    render(<SeverityBadge severity="LOW" />);
    expect(screen.getByText("Low")).toBeTruthy();
  });
  it("renders label for CRITICAL severity", () => {
    render(<SeverityBadge severity="CRITICAL" />);
    expect(screen.getByText("Critical")).toBeTruthy();
  });
  it("has a severity-low colour class for LOW", () => {
    const { container } = render(<SeverityBadge severity="LOW" />);
    expect(container.querySelector(".nk-badge--severity-low")).toBeTruthy();
  });
  it("has a severity-critical colour class for CRITICAL", () => {
    const { container } = render(<SeverityBadge severity="CRITICAL" />);
    expect(container.querySelector(".nk-badge--severity-critical")).toBeTruthy();
  });
  it("renders an icon element (aria-hidden)", () => {
    const { container } = render(<SeverityBadge severity="HIGH" />);
    expect(container.querySelector(".nk-badge__icon")).toBeTruthy();
  });
});

describe("VerdictBadge", () => {
  it("renders INTERCEPTABLE label", () => {
    render(<VerdictBadge verdict="INTERCEPTABLE" />);
    expect(screen.getByText("Interceptable")).toBeTruthy();
  });
  it("renders NOT_INTERCEPTABLE with bad colour class", () => {
    const { container } = render(<VerdictBadge verdict="NOT_INTERCEPTABLE" />);
    expect(container.querySelector(".nk-badge--verdict-bad")).toBeTruthy();
  });
});

describe("LadderBadge", () => {
  it("renders L2 label", () => {
    render(<LadderBadge level="L2" />);
    expect(screen.getByText("L2 · Hold")).toBeTruthy();
  });
  it("renders NONE label", () => {
    render(<LadderBadge level="NONE" />);
    expect(screen.getByText("No Action")).toBeTruthy();
  });
});

describe("StatusBadge", () => {
  it("renders open label", () => {
    render(<StatusBadge status="open" />);
    expect(screen.getByText("Open")).toBeTruthy();
  });
  it("renders expired label with expired colour class", () => {
    const { container } = render(<StatusBadge status="expired" />);
    expect(screen.getByText("Expired")).toBeTruthy();
    expect(container.querySelector(".nk-badge--status-expired")).toBeTruthy();
  });
});
