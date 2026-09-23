/**
 * OpsPage.test.tsx — Component tests for the Operations Console.
 * DOC 4 Step C7 — Evidence required: component test output.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import OpsPage from "../OpsPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/schema.d.ts";

const mockAdmin: Principal = {
  user_id: "USR-ADM-01",
  username: "admin_1",
  role: "admin",
  scope: {},
  permissions: ["SIM_CONTROL", "VIEW_ALERTS", "VIEW_EVALUATION"],
};

function renderOpsPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <AuthContext.Provider
      value={{
        principal: mockAdmin,
        isAuthenticated: true,
        can: (p) => mockAdmin.permissions.includes(p),
        loginAs: () => {},
        logout: () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <OpsPage />
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

  it("shows the four stat cards with fixture values", async () => {
    renderOpsPage();
    await screen.findByTestId("ops-page");

    expect(screen.getByTestId("ops-stat-eps")).toBeTruthy();
    expect(screen.getByTestId("ops-stat-outbox-depth")).toBeTruthy();
    expect(screen.getByTestId("ops-stat-failures")).toBeTruthy();
    expect(screen.getByTestId("ops-stat-sim-speed")).toBeTruthy();

    // Events/s from fixture: 47.3
    expect(screen.getByText("47.3")).toBeTruthy();
    // Outbox depth from fixture: 12
    expect(screen.getByText("12")).toBeTruthy();
  });

  it("shows the stats grid", async () => {
    renderOpsPage();
    expect(await screen.findByTestId("ops-stats-grid")).toBeTruthy();
  });

  it("shows the channel health table with all four channels", async () => {
    renderOpsPage();
    await screen.findByTestId("ops-page");
    expect(screen.getByTestId("ops-channel-table")).toBeTruthy();
    expect(screen.getByTestId("ops-channel-bank_webhook")).toBeTruthy();
    expect(screen.getByTestId("ops-channel-sms")).toBeTruthy();
    expect(screen.getByTestId("ops-channel-email")).toBeTruthy();
    expect(screen.getByTestId("ops-channel-outbox_sms")).toBeTruthy();
  });

  it("does not show auto-pause banner when auto_paused is false", async () => {
    renderOpsPage();
    await screen.findByTestId("ops-page");
    expect(screen.queryByTestId("ops-auto-pause-banner")).toBeNull();
  });
});
