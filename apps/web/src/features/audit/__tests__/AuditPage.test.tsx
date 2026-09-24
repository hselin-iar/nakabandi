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
import type { Principal } from "../../../shared/api/schema.d.ts";

// ---------------------------------------------------------------------------
// Import verifyChain so we can spy on it for the tamper test
// ---------------------------------------------------------------------------
import * as auditApi from "../api/useAudit";

const mockAnalyst: Principal = {
  user_id: "USR-ANA-01",
  username: "i4c_analyst_1",
  role: "i4c_analyst",
  scope: {},
  permissions: ["VIEW_AUDIT", "VIEW_ALERTS"],
};

function renderAuditPage() {
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

    // alert.created appears in 3 rows — use getAllByText
    const alertCreatedCells = screen.getAllByText("alert.created");
    expect(alertCreatedCells.length).toBeGreaterThanOrEqual(1);

    const requestHoldCells = screen.getAllByText("action.request_hold");
    expect(requestHoldCells.length).toBeGreaterThanOrEqual(1);

    // SYSTEM actor appears in multiple rows
    const systemActors = screen.getAllByText("SYSTEM");
    expect(systemActors.length).toBeGreaterThanOrEqual(1);
  });

  it("shows the Verify chain button", async () => {
    renderAuditPage();
    await screen.findByTestId("audit-page");
    expect(screen.getByTestId("verify-btn")).toBeTruthy();
  });

  it("shows an OK banner when verify succeeds", async () => {
    // Fixture verifyChain returns ok: true by default
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
    // Spy on verifyChain to simulate a tampered chain at seq 5
    vi.spyOn(auditApi, "verifyChain").mockResolvedValueOnce({
      ok: false,
      first_bad_seq: 5,
      checked_rows: 10,
    });

    renderAuditPage();
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
