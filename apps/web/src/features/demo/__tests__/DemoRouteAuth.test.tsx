/**
 * DemoRouteAuth.test.tsx — Route Authorization tests for /demo route.
 * DOC 4 Step C8 — Done When:
 *   "The demo_operator role sees the console; any other role gets a 403 page
 *   (the route itself denies, it is not merely hidden)"
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppRoutes } from "../../../app/routes";
import { AuthContext } from "../../../app/auth/AuthContext";
import { permissionsForRole } from "../../../shared/lib/permissions";
import type { Role } from "../../../shared/api/enums.ts";
import type { Principal } from "../../../shared/api/types.ts";

function createPrincipal(role: Role): Principal {
  return {
    user_id: `user-${role}`,
    name: `${role}_1`,
    role,
    scope: {},
    permissions: [...permissionsForRole(role)],
  };
}

function renderRouteAtDemo(principal: Principal | null = createPrincipal("demo_operator")) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <AuthContext.Provider
      value={{
        principal,
        isAuthenticated: principal !== null,
        can: (p) => principal?.permissions.includes(p) ?? false,
        isReady: true,
        login: vi.fn(),
        logout: vi.fn(),
      }}
    >
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/demo"]}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  globalThis.fetch = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/auth/demo-users")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve([]),
      });
    }
    if (url.includes("/sim-control")) {
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

describe("Demo Route Authorization (Step C8 Done When)", () => {
  it(
    "allows demo_operator to access /demo and renders the Demo Console",
    async () => {
      renderRouteAtDemo(createPrincipal("demo_operator"));
      expect(await screen.findByTestId("demo-console", {}, { timeout: 15000 })).toBeTruthy();
      expect(screen.queryByTestId("access-denied")).toBeNull();
    },
    20000,
  );

  it(
    "allows admin to access /demo and renders the Demo Console",
    async () => {
      renderRouteAtDemo(createPrincipal("admin"));
      expect(await screen.findByTestId("demo-console", {}, { timeout: 15000 })).toBeTruthy();
      expect(screen.queryByTestId("access-denied")).toBeNull();
    },
    20000,
  );

  it("denies state_investigator and renders 403 Access Denied page", async () => {
    renderRouteAtDemo(createPrincipal("state_investigator"));
    expect(await screen.findByTestId("access-denied")).toBeTruthy();
    expect(screen.getByText("Access Denied")).toBeTruthy();
    expect(screen.getByText("You do not have permission to view this page.")).toBeTruthy();
    expect(screen.queryByTestId("demo-console")).toBeNull();
  });

  it("denies district_officer and renders 403 Access Denied page", async () => {
    renderRouteAtDemo(createPrincipal("district_officer"));
    expect(await screen.findByTestId("access-denied")).toBeTruthy();
    expect(screen.getByText("Access Denied")).toBeTruthy();
    expect(screen.queryByTestId("demo-console")).toBeNull();
  });

  it("denies bank_nodal and renders 403 Access Denied page", async () => {
    renderRouteAtDemo(createPrincipal("bank_nodal"));
    expect(await screen.findByTestId("access-denied")).toBeTruthy();
    expect(screen.getByText("Access Denied")).toBeTruthy();
    expect(screen.queryByTestId("demo-console")).toBeNull();
  });

  it("denies i4c_analyst and renders 403 Access Denied page", async () => {
    renderRouteAtDemo(createPrincipal("i4c_analyst"));
    expect(await screen.findByTestId("access-denied")).toBeTruthy();
    expect(screen.getByText("Access Denied")).toBeTruthy();
    expect(screen.queryByTestId("demo-console")).toBeNull();
  });

  it("redirects unauthenticated visitor to /login", async () => {
    renderRouteAtDemo(null);
    expect(await screen.findByText("NAKABANDI")).toBeTruthy();
    expect(screen.getByText("Quick-login (demo mode)")).toBeTruthy();
    expect(screen.queryByTestId("demo-console")).toBeNull();
    expect(screen.queryByTestId("access-denied")).toBeNull();
  });
});
