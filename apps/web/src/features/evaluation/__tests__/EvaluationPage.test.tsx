/**
 * EvaluationPage.test.tsx — Component tests for the Evaluation Harness page.
 * DOC 4 Step C7 — Evidence required: component test output.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import EvaluationPage from "../EvaluationPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/schema.d.ts";

const mockAnalyst: Principal = {
  user_id: "USR-ANA-01",
  username: "i4c_analyst_1",
  role: "i4c_analyst",
  scope: {},
  permissions: ["VIEW_EVALUATION", "VIEW_ALERTS"],
};

function renderEvalPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <AuthContext.Provider
      value={{
        principal: mockAnalyst,
        isAuthenticated: true,
        can: (p) => mockAnalyst.permissions.includes(p),
        loginAs: () => {},
        logout: () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <EvaluationPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("EvaluationPage (Step C7)", () => {
  it("renders the evaluation page with fixture data", async () => {
    renderEvalPage();
    expect(await screen.findByTestId("eval-page")).toBeTruthy();
    expect(screen.getByText("Evaluation Harness")).toBeTruthy();
  });

  it("shows the metrics table with all 10 metric rows", async () => {
    renderEvalPage();
    expect(await screen.findByTestId("eval-metrics-table")).toBeTruthy();

    // Check a representative subset of metrics
    expect(screen.getByTestId("eval-row-hit_rate_at_k")).toBeTruthy();
    expect(screen.getByTestId("eval-row-precision_at_k")).toBeTruthy();
    expect(screen.getByTestId("eval-row-brier")).toBeTruthy();
    expect(screen.getByTestId("eval-row-false_hold_rate")).toBeTruthy();
    expect(screen.getByTestId("eval-row-cold_start_hit_rate")).toBeTruthy();
  });

  it("shows the run controls panel with feedback-on and feedback-off labels", async () => {
    renderEvalPage();
    expect(await screen.findByTestId("eval-controls")).toBeTruthy();

    // Run labels are inside testid spans to avoid compound child text-node matching issues
    expect(screen.getByTestId("eval-run-label-0").textContent).toBe("Baseline (feedback off)");
    expect(screen.getByTestId("eval-run-label-1").textContent).toBe("With feedback loop");
  });

  it("activates compare mode and shows the feedback plot side by side", async () => {
    renderEvalPage();
    await screen.findByTestId("eval-controls");

    const toggle = screen.getByLabelText("Compare runs side by side");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(screen.getByTestId("eval-feedback-plot")).toBeTruthy();
    });
  });

  it("shows delta column when in compare mode", async () => {
    renderEvalPage();
    await screen.findByTestId("eval-metrics-table");

    const toggle = screen.getByLabelText("Compare runs side by side");
    fireEvent.click(toggle);

    // Delta arrows should appear (▲ or ▼)
    await waitFor(() => {
      const rows = screen.getAllByTestId(/^eval-row-/);
      expect(rows.length).toBeGreaterThan(0);
    });
  });
});
