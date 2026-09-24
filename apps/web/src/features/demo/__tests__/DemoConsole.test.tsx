/**
 * DemoConsole.test.tsx — Component tests for the Demo Console.
 * DOC 4 Step C8 — Evidence required: Component test output; request log showing proxied call path.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DemoConsole } from "../DemoConsole";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/types.ts";

const mockDemoOperator: Principal = {
  user_id: "demo-operator",
  name: "demo_operator_1",
  role: "demo_operator",
  scope: {},
  permissions: ["VIEW_ALERTS", "VIEW_CASES", "VIEW_EVALUATION", "SIM_CONTROL"],
};

const mockAdmin: Principal = {
  user_id: "demo-admin",
  name: "admin_1",
  role: "admin",
  scope: {},
  permissions: ["VIEW_ALERTS", "VIEW_CASES", "VIEW_EVALUATION", "SIM_CONTROL"],
};

function renderDemoConsole(principal = mockDemoOperator) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <AuthContext.Provider
      value={{
        principal,
        isAuthenticated: true,
        can: (p) => principal.permissions.includes(p),
        isReady: true,
        login: vi.fn(),
        logout: vi.fn(),
      }}
    >
      <QueryClientProvider client={qc}>
        <DemoConsole />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

describe("DemoConsole (Step C8)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    // Mock global fetch to handle /sim-control and /auth/demo-users
    globalThis.fetch = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);

      if (url.includes("/auth/demo-users")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () =>
            Promise.resolve([
              { username: "demo_operator_1", role: "demo_operator", display_name: "Demo Operator" },
              { username: "admin_1", role: "admin", display_name: "System Admin" },
              { username: "state_investigator_1", role: "state_investigator", display_name: "State Investigator (UP)" },
              { username: "bank_nodal_1", role: "bank_nodal", display_name: "Bank Nodal (HDFC)" },
            ]),
        });
      }

      if (url === "/sim-control/status") {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () =>
            Promise.resolve({
              state: "running",
              sim_time: 1718000000,
              speed: 1.0,
              seed: 42,
              scenario: "free",
              counts: { complaints: 140, cashouts: 42, ticks: 950 },
              last_error: null,
            }),
        });
      }

      if (url === "/sim-control/start") {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () => Promise.resolve({ status: "started", run_id: "run-test-123" }),
        });
      }

      if (url === "/sim-control/pause") {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () => Promise.resolve({ status: "paused" }),
        });
      }

      if (url === "/sim-control/resume") {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () => Promise.resolve({ status: "resumed" }),
        });
      }

      if (url === "/sim-control/speed") {
        const body = JSON.parse(String(init?.body || "{}"));
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () => Promise.resolve({ status: "ok", speed: body.factor }),
        });
      }

      if (url === "/sim-control/reset") {
        const body = JSON.parse(String(init?.body || "{}"));
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () => Promise.resolve({ status: "reset", seed: body.seed ?? 42 }),
        });
      }

      if (url === "/sim-control/inject-cluster") {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () => Promise.resolve({ status: "injected", cluster_id: "cls-injected-999" }),
        });
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({}),
      });
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders the demo console with visible DEMO MODE banner", async () => {
    renderDemoConsole();
    expect(await screen.findByTestId("demo-console")).toBeTruthy();

    // Check DEMO MODE banner is prominently visible
    const banner = screen.getByTestId("demo-mode-banner");
    expect(banner).toBeTruthy();
    expect(banner.textContent).toContain("DEMO MODE ACTIVE");
    expect(banner.textContent).toContain("Hosted Simulator Protections Enforced");
    expect(banner.textContent).toContain("Speed Capped at 60x");
    expect(banner.textContent).toContain("Reset/Seed Restricted to Admin");
  });

  it("displays simulator status information correctly", async () => {
    renderDemoConsole();
    await screen.findByTestId("demo-console");

    expect(screen.getByTestId("sim-status-card")).toBeTruthy();
    expect(screen.getByTestId("sim-status-state").textContent).toBe("RUNNING");
    expect(screen.getByTestId("sim-status-speed").textContent).toBe("1x");
    expect(screen.getByTestId("sim-status-seed").textContent).toBe("42");
    expect(screen.getByTestId("sim-status-scenario").textContent).toBe("free");
  });

  it("disables reset and seed control for demo_operator in hosted mode", async () => {
    renderDemoConsole(mockDemoOperator);
    await screen.findByTestId("demo-console");

    const resetBtn = screen.getByTestId("sim-btn-reset") as HTMLButtonElement;
    expect(resetBtn.disabled).toBe(true);

    const seedInput = screen.getByTestId("sim-seed-input") as HTMLInputElement;
    expect(seedInput.disabled).toBe(true);

    expect(
      screen.getByText(/In hosted demo mode, reset and re-seeding are restricted to the/i),
    ).toBeTruthy();
  });

  it("enables reset and seed control when principal is admin", async () => {
    renderDemoConsole(mockAdmin);
    await screen.findByTestId("demo-console");

    const resetBtn = screen.getByTestId("sim-btn-reset") as HTMLButtonElement;
    expect(resetBtn.disabled).toBe(false);

    const seedInput = screen.getByTestId("sim-seed-input") as HTMLInputElement;
    expect(seedInput.disabled).toBe(false);
  });

  it("calls POST /sim-control/inject-cluster with correct payload and records it in request log", async () => {
    renderDemoConsole();
    await screen.findByTestId("demo-console");

    // Change district, size, and locality
    const districtInput = screen.getByTestId("inject-district-input");
    fireEvent.change(districtInput, { target: { value: "MH-MUM" } });

    const sizeInput = screen.getByTestId("inject-size-input");
    fireEvent.change(sizeInput, { target: { value: "45" } });

    const user = userEvent.setup();
    await user.click(screen.getByTestId("inject-locality-select"));
    await user.click(await screen.findByRole("option", { name: /multi_district \(neighbouring\)/i }));

    // Submit inject cluster form
    const injectBtn = screen.getByTestId("inject-cluster-btn");
    fireEvent.click(injectBtn);

    // Verify feedback message
    expect(await screen.findByTestId("inject-result-msg")).toBeTruthy();
    expect(screen.getByTestId("inject-result-msg").textContent).toContain("cls-injected-999");

    // Verify fetch was called with the proxied path /sim-control/inject-cluster
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/sim-control/inject-cluster",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          district_id: "MH-MUM",
          size: 45,
          fast_weight: 0.6,
          locality: "multi_district",
        }),
      }),
    );

    // Verify request log table shows the proxied call
    await waitFor(() => {
      const logRows = screen.getAllByTestId("request-log-row");
      const injectRow = logRows.find((row) =>
        row.textContent?.includes("/sim-control/inject-cluster"),
      );
      expect(injectRow).toBeTruthy();
      expect(injectRow?.textContent).toContain("POST");
      expect(injectRow?.textContent).toContain("200");
    });
  });

  it("handles speed adjustment up to 60x cap and calls /sim-control/speed", async () => {
    renderDemoConsole();
    await screen.findByTestId("demo-console");

    const speedInput = screen.getByTestId("sim-speed-input");
    fireEvent.change(speedInput, { target: { value: "30" } });

    const speedBtn = screen.getByTestId("sim-btn-speed");
    fireEvent.click(speedBtn);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/sim-control/speed",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ factor: 30 }),
        }),
      );
    });
  });

  it("renders quick-login buttons loaded from /auth/demo-users without hardcoded credentials", async () => {
    renderDemoConsole();
    await screen.findByTestId("demo-console");

    // Verify quick-login panel rendered
    expect(screen.getByTestId("demo-quick-login-panel")).toBeTruthy();

    // Verify fetched users from mock /auth/demo-users are present
    expect(await screen.findByTestId("quick-switch-state_investigator")).toBeTruthy();
    expect(screen.getByTestId("quick-switch-bank_nodal")).toBeTruthy();
    expect(screen.getByTestId("quick-switch-admin")).toBeTruthy();
  });
});
