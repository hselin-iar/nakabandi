/**
 * OutboxPage.test.tsx — Component tests for the Delivery Outbox page.
 * DOC 4 Step C7 — Evidence required: component test output.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import OutboxPage from "../OutboxPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import { apiClient } from "../../../shared/api/client";
import type { Principal } from "../../../shared/api/types.ts";
import type { Delivery } from "../../../shared/api/types.ts";

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

function delivery(overrides: Partial<Delivery>): Delivery {
  return {
    id: "DLV-0001",
    alert_id: "ALT-2026-001",
    action_id: "ACT-2026-001",
    channel: "bank_webhook",
    provider: "bank-sim",
    webhook_kind: "hold_request",
    recipient: "bank-sim",
    status: "sent",
    attempts: 1,
    next_attempt_at: "2026-09-23T11:00:02Z",
    created_at: "2026-09-23T11:00:00Z",
    sent_at: "2026-09-23T11:00:02Z",
    last_error: null,
    rendered_body: JSON.stringify({ event: "hold_requested", alert_id: "ALT-2026-001" }),
    ...overrides,
  };
}

const FIXTURE_DELIVERIES: Delivery[] = [
  delivery({ id: "DLV-0001", status: "sent" }),
  delivery({ id: "DLV-0002", channel: "sms", status: "sent", rendered_body: "SMS body" }),
  delivery({
    id: "DLV-0003",
    alert_id: "ALT-2026-002",
    status: "dead",
    attempts: 3,
    sent_at: null,
    last_error: "Connection refused: bank-sim returned 503",
  }),
  delivery({ id: "DLV-0004", channel: "outbox_sms", status: "failed", attempts: 2, sent_at: null }),
  delivery({ id: "DLV-0005", channel: "email", status: "pending", attempts: 0, sent_at: null }),
];

const mockAnalyst: Principal = {
  user_id: "USR-ANA-01",
  name: "i4c_analyst_1",
  role: "i4c_analyst",
  scope: {},
  permissions: ["VIEW_AUDIT", "VIEW_ALERTS"],
};

function renderOutboxPage() {
  vi.mocked(apiClient.GET).mockResolvedValue({
    data: { items: FIXTURE_DELIVERIES, next_cursor: null, dead_count: 1 },
    error: undefined,
  } as unknown as never);

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
        <OutboxPage />
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("OutboxPage (Step C7)", () => {
  it("renders the outbox page with fixture deliveries", async () => {
    renderOutboxPage();
    expect(await screen.findByTestId("outbox-page")).toBeTruthy();
    expect(screen.getByText("Delivery Outbox")).toBeTruthy();
    expect(screen.getByTestId("outbox-table")).toBeTruthy();
  });

  it("shows all 5 fixture delivery rows", async () => {
    renderOutboxPage();
    await screen.findByTestId("outbox-table");

    expect(screen.getByTestId("outbox-row-DLV-0001")).toBeTruthy();
    expect(screen.getByTestId("outbox-row-DLV-0002")).toBeTruthy();
    expect(screen.getByTestId("outbox-row-DLV-0003")).toBeTruthy();
    expect(screen.getByTestId("outbox-row-DLV-0004")).toBeTruthy();
    expect(screen.getByTestId("outbox-row-DLV-0005")).toBeTruthy();
  });

  it("shows status badges for all four delivery states", async () => {
    renderOutboxPage();
    await screen.findByTestId("outbox-table");

    // Fixture has: sent (×2 -> "Delivered"), dead (×1 -> "Failed"), failed (×1 -> "Retrying"), pending (×1)
    const allDelivered = screen.getAllByText("Delivered");
    expect(allDelivered.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.getByText("Retrying")).toBeTruthy();
    expect(screen.getByText("Pending")).toBeTruthy();
  });

  it("expands a row to show the rendered_body on click", async () => {
    renderOutboxPage();
    await screen.findByTestId("outbox-table");

    const row = screen.getByTestId("outbox-row-DLV-0001");
    fireEvent.click(row);

    await waitFor(() => {
      expect(screen.getByTestId("outbox-body-DLV-0001")).toBeTruthy();
      expect(screen.getByText(/hold_requested/)).toBeTruthy();
    });
  });

  it("shows the last_error for a dead delivery when expanded", async () => {
    renderOutboxPage();
    await screen.findByTestId("outbox-table");

    const deadRow = screen.getByTestId("outbox-row-DLV-0003");
    fireEvent.click(deadRow);

    await waitFor(() => {
      expect(screen.getByTestId("outbox-body-DLV-0003")).toBeTruthy();
      expect(screen.getByText(/Connection refused/)).toBeTruthy();
    });
  });
});
