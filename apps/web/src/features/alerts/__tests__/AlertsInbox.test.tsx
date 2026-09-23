/**
 * AlertsInbox.test.tsx — Unit & component tests for AlertsInbox.
 * DOC 3 / DOC 4 C4 Done When:
 *   AlertsInbox renders the live list, sorts, filters by severity/status, and updates;
 *   clicking an alert opens AlertDetail.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AlertsInbox from "../AlertsInbox";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/schema.d.ts";
import { resetAlertsFixtureStore } from "../api/useAlerts";

const mockOfficerPrincipal: Principal = {
  user_id: "USR-001",
  username: "officer_sharma",
  role: "district_officer",
  scope: { state_id: "DL", district_id: "DL-NEW-DELHI" },
  permissions: [
    "VIEW_ALERTS",
    "ACKNOWLEDGE",
    "REQUEST_HOLD",
    "DISPATCH",
    "NOTIFY_STATION",
    "MARK_OUTCOME",
  ],
};

function renderWithProviders(ui: React.ReactNode, initialPath = "/alerts") {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <AuthContext.Provider
      value={{
        principal: mockOfficerPrincipal,
        isAuthenticated: true,
        can: (p) => mockOfficerPrincipal.permissions.includes(p),
        loginAs: () => {},
        logout: () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/alerts" element={ui} />
            <Route path="/alerts/:id" element={ui} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  resetAlertsFixtureStore();
  vi.unstubAllGlobals();
});

describe("AlertsInbox", () => {
  it("renders the table headers and live fixture alerts", async () => {
    renderWithProviders(<AlertsInbox />);

    expect(screen.getByText("Alert Operations Inbox")).toBeTruthy();
    expect(await screen.findByText("ALT-2026-001")).toBeTruthy();
    expect(screen.getByText("ALT-2026-002")).toBeTruthy();
    expect(screen.getByText("ALT-2026-003")).toBeTruthy();
    expect(screen.getByText("ALT-2026-004")).toBeTruthy();
  });

  it("filters alerts by status tabs", async () => {
    renderWithProviders(<AlertsInbox />);
    await screen.findByText("ALT-2026-001");

    // Click 'Acknowledged' tab
    const ackTab = screen.getByRole("tab", { name: "Acknowledged" });
    fireEvent.click(ackTab);

    // ALT-2026-002 is 'acknowledged'
    expect(await screen.findByText("ALT-2026-002")).toBeTruthy();
    // ALT-2026-001 is 'open', should not be visible
    expect(screen.queryByText("ALT-2026-001")).toBeNull();
  });

  it("filters alerts by severity dropdown", async () => {
    renderWithProviders(<AlertsInbox />);
    await screen.findByText("ALT-2026-001");

    const severitySelect = screen.getByLabelText("Filter by severity");
    fireEvent.change(severitySelect, { target: { value: "CRITICAL" } });

    // ALT-2026-001 is CRITICAL
    expect(await screen.findByText("ALT-2026-001")).toBeTruthy();
    // ALT-2026-002 is HIGH, should not be visible
    expect(screen.queryByText("ALT-2026-002")).toBeNull();
  });

  it("filters alerts by search query", async () => {
    renderWithProviders(<AlertsInbox />);
    await screen.findByText("ALT-2026-001");

    const searchInput = screen.getByLabelText("Search alerts");
    fireEvent.change(searchInput, { target: { value: "Bandra" } });

    // ALT-2026-002 target contains Bandra
    expect(await screen.findByText("ALT-2026-002")).toBeTruthy();
    expect(screen.queryByText("ALT-2026-001")).toBeNull();
  });

  it("opens AlertDetail drawer when an alert inspect button or row is clicked", async () => {
    renderWithProviders(<AlertsInbox />);

    const inspectBtn = await screen.findByLabelText("Inspect alert ALT-2026-001");
    fireEvent.click(inspectBtn);

    // Drawer should open and show target location and response actions
    expect(await screen.findByText("Target Location & Network Anchor")).toBeTruthy();
    expect(screen.getByText("Response Actions")).toBeTruthy();
  });

  it("toggles rapid triage review queue", async () => {
    renderWithProviders(<AlertsInbox />);
    await screen.findByText("ALT-2026-001");

    const triageBtn = screen.getByRole("button", { name: /Rapid Triage Mode/i });
    fireEvent.click(triageBtn);

    expect(screen.getByLabelText("Rapid triage queue")).toBeTruthy();
    expect(screen.getByText(/Alert 1 of/i)).toBeTruthy();
  });
});
