/**
 * EvaluationPage.test.tsx — Component tests for the Evaluation Harness page.
 * DOC 4 Step C7 — Evidence required: component test output.
 */

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import EvaluationPage from "../EvaluationPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/types.ts";
import type { EvalReport } from "../api/useEvaluation";

const mockAnalyst: Principal = {
  user_id: "USR-ANA-01",
  name: "i4c_analyst_1",
  role: "i4c_analyst",
  scope: {},
  permissions: ["VIEW_EVALUATION", "VIEW_ALERTS"],
};

const SAMPLE_REPORT: EvalReport = {
  generated_at: "2026-09-26T02:33:29.079935+00:00",
  as_of: "2026-01-18T05:30:01.726030+00:00",
  scorer: "hgb_v1",
  metrics: {
    n_complaints: 226,
    hit_rate_at_1: { value: 0.0265, n: 226 },
    hit_rate_at_3: { value: 0.0752, n: 226 },
    hit_rate_at_5: { value: 0.1018, n: 226 },
    precision_at_1: { value: 0.0265, n: 226 },
    precision_at_3: { value: 0.028, n: 226 },
    precision_at_5: { value: 0.0239, n: 226 },
    brier_score: { value: 0.006, n: 37168 },
  },
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
        isReady: true,
        login: async () => {},
        logout: async () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <EvaluationPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("EvaluationPage (Step C7)", () => {
  it("renders the evaluation page and real metrics table when a report exists", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(SAMPLE_REPORT), { status: 200 }),
    );
    renderEvalPage();

    expect(await screen.findByTestId("eval-page")).toBeTruthy();
    expect(screen.getByText("Evaluation Harness")).toBeTruthy();
    expect(await screen.findByTestId("eval-metrics-table")).toBeTruthy();
    expect(screen.getByTestId("eval-row-hit_rate_at_5")).toBeTruthy();
    expect(screen.getByTestId("eval-row-brier_score")).toBeTruthy();
    expect(screen.getByText("hgb_v1")).toBeTruthy();
    expect(screen.getAllByText("226").length).toBeGreaterThan(0);
  });

  it("shows an honest empty state when scripts/evaluate.py has never been run", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("not found", { status: 404 }));
    renderEvalPage();

    const emptyState = await screen.findByTestId("eval-empty-state");
    expect(emptyState.textContent).toMatch(/scripts\/evaluate\.py/);
    expect(screen.queryByTestId("eval-metrics-table")).toBeNull();
  });
});
