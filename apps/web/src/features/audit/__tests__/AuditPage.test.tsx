/**
 * AuditPage.test.tsx — Component tests for the Audit Log page.
 * DOC 4 Step C7 — Evidence required: component test output +
 * "Verify chain" ok/not-ok banner state (including tampered fixture).
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AuditPage from "../AuditPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import { apiClient } from "../../../shared/api/client";
import type { Principal } from "../../../shared/api/types.ts";
import type { AuditEntry } from "../../../shared/api/types.ts";

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

import * as auditApi from "../api/useAudit";

function entry(overrides: Partial<AuditEntry>): AuditEntry {
  return {
    seq: 1,
    at: "2026-09-23T09:00:00Z",
    actor_id: "SYSTEM",
    actor_role: "admin",
    action: "alert.created",
    entity_type: "alert",
    entity_id: "ALT-2026-001",
    reason: null,
    payload: {},
    hash: "a3f9b2c14d7e8f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
    ...overrides,
  };
}

const FIXTURE_ENTRIES: AuditEntry[] = Array.from({ length: 10 }, (_, i) =>
  entry({
    seq: i + 1,
    action: i % 3 === 0 ? "alert.created" : i === 2 ? "action.request_hold" : "delivery.dispatched",
    actor_id: i % 3 === 0 ? "SYSTEM" : "state_investigator_1",
    entity_id: `ALT-2026-00${(i % 3) + 1}`,
  }),
);

const mockAnalyst: Principal = {
  user_id: "USR-ANA-01",
  name: "i4c_analyst_1",
  role: "i4c_analyst",
  scope: {},
  permissions: ["VIEW_AUDIT", "VIEW_ALERTS"],
};

function renderAuditPage() {
  vi.mocked(apiClient.GET).mockImplementation(((path: string) => {
    if (path === "/audit") {
      return Promise.resolve({ data: FIXTURE_ENTRIES, error: undefined });
    }
    if (path === "/audit/verify") {
      return Promise.resolve({ data: { ok: true, first_bad_seq: null, head_hash: "deadbeef" }, error: undefined });
    }
    return Promise.resolve({ data: undefined, error: new Error("unmocked path") });
  }) as unknown as typeof apiClient.GET);

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
        <AuditPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AuditPage (Step C7)", () => {
  it("renders the audit log page with fixture entries", async () => {
    renderAuditPage();
    expect(await screen.findByTestId("audit-page")).toBeTruthy();
    expect(screen.getByText("Audit Log")).toBeTruthy();
    expect(screen.getByTestId("audit-table")).toBeTruthy();
  });

  it("shows all 10 fixture audit entries", async () => {
    renderAuditPage();
    await screen.findByTestId("audit-table");

    for (let seq = 1; seq <= 10; seq++) {
      expect(screen.getByTestId(`audit-row-${seq}`)).toBeTruthy();
    }
  });

  it("shows event types and actor ids for fixture entries", async () => {
    renderAuditPage();
    await screen.findByTestId("audit-table");

    const alertCreatedCells = screen.getAllByText("Alert: Created");
    expect(alertCreatedCells.length).toBeGreaterThanOrEqual(1);

    const requestHoldCells = screen.getAllByText("Action: Request hold");
    expect(requestHoldCells.length).toBeGreaterThanOrEqual(1);

    const systemActors = screen.getAllByText("SYSTEM");
    expect(systemActors.length).toBeGreaterThanOrEqual(1);
  });

  it("shows the Verify chain button", async () => {
    renderAuditPage();
    await screen.findByTestId("audit-page");
    expect(screen.getByTestId("verify-btn")).toBeTruthy();
  });

  it("shows an OK banner when verify succeeds", async () => {
    renderAuditPage();
    await screen.findByTestId("audit-page");

    fireEvent.click(screen.getByTestId("verify-btn"));

    await waitFor(() => {
      const banner = screen.getByTestId("verify-banner");
      expect(banner).toBeTruthy();
      expect(banner.getAttribute("data-verify-ok")).toBe("true");
      expect(banner.textContent).toMatch(/Chain verified/);
    });
  });

  it("shows a FAIL banner with first_bad_seq when chain is tampered (C7 evidence)", async () => {
    renderAuditPage();
    vi.spyOn(auditApi, "verifyChain").mockResolvedValueOnce({
      ok: false,
      first_bad_seq: 5,
      head_hash: "stale",
    });

    await screen.findByTestId("audit-page");

    fireEvent.click(screen.getByTestId("verify-btn"));

    await waitFor(() => {
      const banner = screen.getByTestId("verify-banner");
      expect(banner).toBeTruthy();
      expect(banner.getAttribute("data-verify-ok")).toBe("false");
      expect(banner.textContent).toMatch(/seq 5/);
      expect(banner.textContent).toMatch(/Chain integrity failure/);
    });
  });
});
