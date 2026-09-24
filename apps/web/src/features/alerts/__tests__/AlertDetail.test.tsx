/**
 * AlertDetail.test.tsx — Unit & component tests for AlertDetail & actions.
 * DOC 3 / DOC 4 C4 Done When:
 *   Clicking an alert opens AlertDetail with evidence timeline, Countdown,
 *   ConfidenceBar; action buttons (Hold, Dispatch, Notify, Acknowledge)
 *   respect user role permissions and fire mutations.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AlertDetail } from "../AlertDetail";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal, Permission } from "../../../shared/api/schema.d.ts";
import { resetAlertsFixtureStore } from "../api/useAlerts";

function makePrincipal(permissions: Permission[]): Principal {
  return {
    user_id: "USR-TEST-01",
    username: "test_officer",
    role: "district_officer",
    scope: { state_id: "DL" },
    permissions,
  };
}

function renderAlertDetail(
  alertId: string | null,
  permissions: Permission[] = [
    "VIEW_ALERTS",
    "ACKNOWLEDGE",
    "REQUEST_HOLD",
    "DISPATCH",
    "NOTIFY_STATION",
    "OVERRIDE",
    "MARK_OUTCOME",
  ],
  onClose = vi.fn(),
) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <AuthContext.Provider
      value={{
        principal: makePrincipal(permissions),
        isAuthenticated: true,
        can: (p) => permissions.includes(p),
        loginAs: () => {},
        logout: () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <AlertDetail alertId={alertId} onClose={onClose} />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  resetAlertsFixtureStore();
  vi.unstubAllGlobals();
});

describe("AlertDetail", () => {
  it("renders detail with timeline, target, confidence, and countdown", async () => {
    renderAlertDetail("ALT-2026-001");

    expect(await screen.findByText("Alert ALT-2026-001")).toBeTruthy();
    expect(screen.getByText("CLS-DL-8821")).toBeTruthy();
    expect(screen.getByText(/SBI ATM — Connaught Place/i)).toBeTruthy();
    expect(screen.getByText("Evidence & Audit Trail")).toBeTruthy();
    expect(screen.getByText("Confidence Score")).toBeTruthy();
    expect(screen.getByText("Window Expiry")).toBeTruthy();
  });

  it("renders permission-gated action buttons for authorized officer", async () => {
    renderAlertDetail("ALT-2026-001", [
      "VIEW_ALERTS",
      "ACKNOWLEDGE",
      "REQUEST_HOLD",
      "DISPATCH",
      "NOTIFY_STATION",
      "OVERRIDE",
    ]);

    expect(await screen.findByRole("button", { name: /Acknowledge/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Request Hold/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Dispatch Patrol/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Notify Station/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Override/i })).toBeTruthy();
  });

  it("hides action buttons when user lacks permissions", async () => {
    // Only has VIEW_ALERTS (e.g. read-only auditor or restricted role)
    renderAlertDetail("ALT-2026-001", ["VIEW_ALERTS"]);

    await screen.findByText("Alert ALT-2026-001");

    expect(screen.queryByRole("button", { name: /Acknowledge/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Request Hold/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Dispatch Patrol/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Notify Station/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Override/i })).toBeNull();
  });

  it("executes Acknowledge action and fires mutation", async () => {
    renderAlertDetail("ALT-2026-001", ["VIEW_ALERTS", "ACKNOWLEDGE"]);

    const ackBtn = await screen.findByRole("button", { name: /Acknowledge/i });
    fireEvent.click(ackBtn);

    // After acknowledgment, alert status becomes acknowledged (ACK button disappears for acknowledged alerts)
    expect(await screen.findByText(/acknowledged/i)).toBeTruthy();
  });

  it("opens modal and submits Request Hold action", async () => {
    renderAlertDetail("ALT-2026-001", ["VIEW_ALERTS", "REQUEST_HOLD"]);

    const holdBtn = await screen.findByRole("button", { name: /Request Hold/i });
    fireEvent.click(holdBtn);

    expect(screen.getByText("Request Inter-Bank Lien Hold")).toBeTruthy();
    expect(screen.getByLabelText(/Proposed Lien Amount/i)).toBeTruthy();

    const confirmBtn = screen.getByRole("button", { name: /Confirm & Execute/i });
    fireEvent.click(confirmBtn);

    // Action updates status to ACTIONED
    expect(await screen.findByText(/actioned/i)).toBeTruthy();
  });

  it("renders OutcomeButtons and allows marking Hit outcome", async () => {
    renderAlertDetail("ALT-2026-001", ["VIEW_ALERTS", "MARK_OUTCOME"]);

    const hitBtn = await screen.findByRole("button", { name: /Intercepted \(Hit\)/i });
    fireEvent.click(hitBtn);

    const confirmBtn = screen.getByRole("button", { name: /Confirm HIT/i });
    fireEvent.click(confirmBtn);

    // Timeline receives outcome entry
    expect(await screen.findByText(/outcome/i)).toBeTruthy();
  });
});
