/**
 * OpsPage.test.tsx — Component tests for the Operations Console.
 * DOC 4 Step C7 — Evidence required: component test output.
 *
 * The real GET /system/metrics has no channel breakdown, sim-speed, or auto-pause state (DOC 4
 * A11/A12 Learnings) — OpsPage hides those sections rather than showing fabricated numbers, so
 * this test checks for their absence, not fixture values that no longer exist.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import OpsPage from "../OpsPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import { apiClient } from "../../../shared/api/client";
import type { Principal } from "../../../shared/api/types.ts";

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

const mockAdmin: Principal = {
  user_id: "USR-ADM-01",
  name: "admin_1",
  role: "admin",
  scope: {},
  permissions: ["SIM_CONTROL", "VIEW_ALERTS", "VIEW_EVALUATION"],
};

function renderOpsPage() {
  vi.mocked(apiClient.GET).mockResolvedValue({
    data: {
      generated_at: "2026-09-24T03:00:00Z",
      uptime_s: 120,
      events_per_second: 47.3,
      complaints_per_second: 12.1,
      stages: {
        ingest: { count: 10, p50_ms: 3, p95_ms: 12, max_ms: 20 },
        forecast: { count: 10, p50_ms: 38, p95_ms: 110, max_ms: 200 },
      },
      http: { count: 10, p50_ms: 5, p95_ms: 15, max_ms: 30 },
      outbox: { pending: 12, sent: 80, failed: 2, dead: 0 },
      delivery_failures: 2,
      streams: { open: 0, max: 0 },
    },
    error: undefined,
  } as unknown as never);

  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <AuthContext.Provider
      value={{
        principal: mockAdmin,
        isAuthenticated: true,
        can: (p) => mockAdmin.permissions.includes(p),
        isReady: true,
        login: async () => {},
        logout: async () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <OpsPage />
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("OpsPage (Step C7)", () => {
  it("renders the ops console page", async () => {
    renderOpsPage();
    expect(await screen.findByTestId("ops-page")).toBeTruthy();
    expect(screen.getByText("Operations Console")).toBeTruthy();
  });

  it("shows the stat cards with real metrics values", async () => {
    renderOpsPage();
    await screen.findByTestId("ops-page");

    expect(screen.getByTestId("ops-stat-eps")).toBeTruthy();
    expect(screen.getByTestId("ops-stat-outbox-depth")).toBeTruthy();
    expect(screen.getByTestId("ops-stat-failures")).toBeTruthy();
    // Sim speed isn't in the real metrics response — the card is hidden, not fabricated.
    expect(screen.queryByTestId("ops-stat-sim-speed")).toBeNull();

    expect(screen.getByText("47.3")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
  });

  it("shows the stats grid", async () => {
    renderOpsPage();
    expect(await screen.findByTestId("ops-stats-grid")).toBeTruthy();
  });

  it("hides the channel health table (no per-channel breakdown on the real backend)", async () => {
    renderOpsPage();
    await screen.findByTestId("ops-page");
    expect(screen.queryByTestId("ops-channel-table")).toBeNull();
  });

  it("does not show the auto-pause banner (no sim-control state on the real backend)", async () => {
    renderOpsPage();
    await screen.findByTestId("ops-page");
    expect(screen.queryByTestId("ops-auto-pause-banner")).toBeNull();
  });
});
