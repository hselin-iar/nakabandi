/**
 * AlertsInbox.test.tsx — Unit & component tests for AlertsInbox.
 * DOC 3 / DOC 4 C4 Done When:
 *   AlertsInbox renders the live list, sorts, filters by severity/status, and updates;
 *   clicking an alert opens AlertDetail.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AlertsInbox from "../AlertsInbox";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/types.ts";
import type { AlertSummary } from "../../../shared/api/types.ts";
import { apiClient } from "../../../shared/api/client";

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

const FIXTURE_ALERTS: AlertSummary[] = [
  {
    id: "ALT-2026-001",
    cluster_ref: "CLS-DL-8821",
    target: { kind: "ATM", id: "LOC-ATM-4012", name: "SBI ATM — Connaught Place Inner Circle" },
    severity: "CRITICAL",
    confidence: 0.94,
    status: "open",
    is_deferred: false,
    is_probe: false,
    window_start: "2026-01-15T10:00:00Z",
    window_end: "2026-01-15T11:30:00Z",
    expires_at: "2026-01-15T11:30:00Z",
    ladder_level: "L3",
    created_at: "2026-01-15T10:05:00Z",
    masked: false,
  },
  {
    id: "ALT-2026-002",
    cluster_ref: "CLS-MH-1049",
    target: { kind: "BRANCH", id: "LOC-BR-0912", name: "HDFC Bank — Bandra West Branch" },
    severity: "HIGH",
    confidence: 0.81,
    status: "acknowledged",
    is_deferred: false,
    is_probe: false,
    window_start: "2026-01-15T10:15:00Z",
    window_end: "2026-01-15T12:00:00Z",
    expires_at: "2026-01-15T12:00:00Z",
    ladder_level: "L2",
    created_at: "2026-01-15T10:18:00Z",
    masked: false,
  },
  {
    id: "ALT-2026-003",
    cluster_ref: "CLS-KA-3321",
    target: { kind: "AGENT", id: "LOC-AG-1105", name: "BC Point — Whitefield Main Rd" },
    severity: "MEDIUM",
    confidence: 0.68,
    status: "open",
    is_deferred: false,
    is_probe: true,
    window_start: "2026-01-15T10:30:00Z",
    window_end: "2026-01-15T12:30:00Z",
    expires_at: "2026-01-15T12:30:00Z",
    ladder_level: "L1",
    created_at: "2026-01-15T10:32:00Z",
    masked: true,
  },
  {
    id: "ALT-2026-004",
    cluster_ref: "CLS-DL-9901",
    target: { kind: "ATM", id: "LOC-ATM-2201", name: "ICICI ATM — Karol Bagh Metro" },
    severity: "LOW",
    confidence: 0.42,
    status: "actioned",
    is_deferred: false,
    is_probe: false,
    window_start: "2026-01-15T09:00:00Z",
    window_end: "2026-01-15T10:30:00Z",
    expires_at: "2026-01-15T10:30:00Z",
    ladder_level: "NONE",
    created_at: "2026-01-15T09:05:00Z",
    masked: false,
  },
];

const FIXTURE_DETAIL_BY_ID: Record<string, unknown> = Object.fromEntries(
  FIXTURE_ALERTS.map((a) => [
    a.id,
    { ...a, forecast: null, interception: [], timeline: [], deliveries: [], actions: [], outcomes: [], allowed_actions: [] },
  ]),
);

const mockOfficerPrincipal: Principal = {
  user_id: "USR-001",
  name: "officer_sharma",
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
        isReady: true,
        login: async () => {},
        logout: async () => {},
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

function mockGet(): void {
  vi.mocked(apiClient.GET).mockImplementation(((
    path: string,
    opts?: { params?: { path?: { alert_id?: string }; query?: { status?: string; district_id?: string } } },
  ) => {
    if (path === "/alerts") {
      const status = opts?.params?.query?.status;
      const items = status ? FIXTURE_ALERTS.filter((a) => a.status === status) : FIXTURE_ALERTS;
      return Promise.resolve({ data: { items, next_cursor: null }, error: undefined });
    }
    if (path === "/alerts/{alert_id}") {
      const id = opts?.params?.path?.alert_id;
      return Promise.resolve({ data: id ? FIXTURE_DETAIL_BY_ID[id] : null, error: undefined });
    }
    return Promise.resolve({ data: undefined, error: new Error("unmocked path") });
  }) as unknown as typeof apiClient.GET);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("AlertsInbox", () => {
  it("renders the table headers and live fixture alerts", async () => {
    mockGet();
    renderWithProviders(<AlertsInbox />);

    expect(screen.getByText("Alert Operations Inbox")).toBeTruthy();
    expect(await screen.findByText("ALT-2026-001")).toBeTruthy();
    expect(screen.getByText("ALT-2026-002")).toBeTruthy();
    expect(screen.getByText("ALT-2026-003")).toBeTruthy();
    expect(screen.getByText("ALT-2026-004")).toBeTruthy();
  });

  it("filters alerts by status tabs", async () => {
    mockGet();
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
    mockGet();
    renderWithProviders(<AlertsInbox />);
    await screen.findByText("ALT-2026-001");

    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Filter by severity"));
    await user.click(await screen.findByRole("option", { name: "Critical" }));

    // ALT-2026-001 is CRITICAL
    expect(await screen.findByText("ALT-2026-001")).toBeTruthy();
    // ALT-2026-002 is HIGH, should not be visible
    expect(screen.queryByText("ALT-2026-002")).toBeNull();
  });

  it("filters alerts by search query", async () => {
    mockGet();
    renderWithProviders(<AlertsInbox />);
    await screen.findByText("ALT-2026-001");

    const searchInput = screen.getByLabelText("Search alerts");
    fireEvent.change(searchInput, { target: { value: "Bandra" } });

    // ALT-2026-002 target contains Bandra
    expect(await screen.findByText("ALT-2026-002")).toBeTruthy();
    expect(screen.queryByText("ALT-2026-001")).toBeNull();
  });

  it("opens AlertDetail drawer when an alert inspect button or row is clicked", async () => {
    mockGet();
    renderWithProviders(<AlertsInbox />);

    const inspectBtn = await screen.findByLabelText("Inspect alert ALT-2026-001");
    fireEvent.click(inspectBtn);

    // Drawer should open and show target location and response actions
    expect(await screen.findByText("Target Location & Network Anchor")).toBeTruthy();
    expect(screen.getByText("Response Actions")).toBeTruthy();
  });

  it("toggles rapid triage review queue", async () => {
    mockGet();
    renderWithProviders(<AlertsInbox />);
    await screen.findByText("ALT-2026-001");

    const triageBtn = screen.getByRole("button", { name: /Rapid Triage Mode/i });
    fireEvent.click(triageBtn);

    expect(screen.getByLabelText("Rapid triage queue")).toBeTruthy();
    expect(screen.getByText(/Alert 1 of/i)).toBeTruthy();
  });
});
