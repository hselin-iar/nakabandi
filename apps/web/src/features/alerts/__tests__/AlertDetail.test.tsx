/**
 * AlertDetail.test.tsx — Unit & component tests for AlertDetail & actions.
 * DOC 3 / DOC 4 C4 Done When:
 *   Clicking an alert opens AlertDetail with evidence timeline, Countdown,
 *   ConfidenceBar; action buttons (Hold, Dispatch, Notify, Acknowledge)
 *   respect user role permissions and fire mutations.
 */

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AlertDetail } from "../AlertDetail";
import { AuthContext } from "../../../app/auth/AuthContext";
import { apiClient } from "../../../shared/api/client";
import type { ActionType, Permission } from "../../../shared/api/enums.ts";
import type { AlertDetail as AlertDetailModel, Principal } from "../../../shared/api/types.ts";

// Mirrors apps/api/src/nakabandi/interception/... alerting/domain/action.py's _PERMISSION_FOR:
// the action bar is gated by AlertDetailModel.allowed_actions (server-computed from this same
// permission mapping), not by client-side permission checks (§10.1 essential fix).
const PERMISSION_TO_ACTION: Partial<Record<Permission, ActionType>> = {
  ACKNOWLEDGE: "acknowledge",
  REQUEST_HOLD: "request_hold",
  NOTIFY_STATION: "notify_station",
  DISPATCH: "dispatch",
  OVERRIDE: "override",
};

function allowedActionsFor(permissions: Permission[]): ActionType[] {
  return permissions
    .map((p) => PERMISSION_TO_ACTION[p])
    .filter((a): a is ActionType => a !== undefined);
}

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

function fixtureDetail(): AlertDetailModel {
  return {
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
    forecast: null,
    interception: [],
    timeline: [
      { at: "2026-01-15T10:05:00Z", kind: "created", actor_id: null, text_code: "alert.created", text_params: {} },
    ],
    deliveries: [],
    actions: [],
    outcomes: [],
    allowed_actions: [],
  };
}

let alertState: AlertDetailModel;

function installStatefulMock(): void {
  alertState = fixtureDetail();
  vi.mocked(apiClient.GET).mockImplementation(((path: string) =>
    Promise.resolve(
      path === "/clusters/{cluster_id}"
        ? { data: { nodes: [{ id: "ACC-7", kind: "account", masked_ref: "XXXX-4471", bank: "SBIN" }] }, error: undefined }
        : { data: alertState, error: undefined },
    )) as unknown as typeof apiClient.GET);
  vi.mocked(apiClient.POST).mockImplementation(((path: string, opts?: { body?: Record<string, unknown> }) => {
    if (path === "/alerts/{alert_id}/actions") {
      const body = opts?.body as { type: string; reason?: string; params?: Record<string, unknown> };
      if (body.type === "acknowledge") alertState = { ...alertState, status: "acknowledged" };
      else if (body.type === "request_hold") alertState = { ...alertState, status: "actioned" };
      alertState = {
        ...alertState,
        timeline: [
          ...alertState.timeline,
          { at: new Date().toISOString(), kind: body.type, actor_id: "test", text_code: `alert.${body.type}`, text_params: {} },
        ],
      };
      return Promise.resolve({
        data: { id: "ACT-1", alert_id: alertState.id, type: body.type, status: "done", actor_role: "district_officer", at: new Date().toISOString(), params: body.params ?? {} },
        error: undefined,
      });
    }
    if (path === "/alerts/{alert_id}/outcome") {
      const body = opts?.body as { result: string; reason?: string };
      alertState = {
        ...alertState,
        timeline: [
          ...alertState.timeline,
          { at: new Date().toISOString(), kind: "outcome", actor_id: "test", text_code: `outcome.${body.result}`, text_params: {} },
        ],
      };
      return Promise.resolve({
        data: { id: "OUT-1", alert_id: alertState.id, result: body.result, source: "officer", at: new Date().toISOString() },
        error: undefined,
      });
    }
    return Promise.resolve({ data: undefined, error: new Error("unmocked path") });
  }) as unknown as typeof apiClient.POST);
}

beforeEach(() => {
  installStatefulMock();
});

function makePrincipal(permissions: Permission[]): Principal {
  return {
    user_id: "USR-TEST-01",
    name: "test_officer",
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

  // The server (not the client) decides allowed_actions; drive it from the same
  // permission list the test already passes in, so existing test intent still holds.
  alertState = { ...alertState, allowed_actions: allowedActionsFor(permissions) };

  return render(
    <AuthContext.Provider
      value={{
        principal: makePrincipal(permissions),
        isAuthenticated: true,
        can: (p) => permissions.includes(p),
        isReady: true,
        login: async () => {},
        logout: async () => {},
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
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("AlertDetail", () => {
  it("renders detail with timeline, target, confidence, and countdown", async () => {
    renderAlertDetail("ALT-2026-001");

    expect(
      await screen.findByText("CLS-DL-8821 · SBI ATM — Connaught Place Inner Circle"),
    ).toBeTruthy();
    expect(screen.getByText(/ALT-2026-001/)).toBeTruthy();
    expect(screen.getAllByText(/SBI ATM — Connaught Place/i).length).toBeGreaterThan(0);
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

    await screen.findByText("Evidence & Audit Trail");

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

  it("Request Hold needs a press-and-hold: an early release sends nothing, a full hold sends the account and amount", async () => {
    alertState = { ...alertState, forecast: { cluster_id: "CLU-1" } as never };
    renderAlertDetail("ALT-2026-001", ["VIEW_ALERTS", "REQUEST_HOLD"]);

    fireEvent.click(await screen.findByRole("button", { name: /Request Hold/i }));

    expect(screen.getByText("Request Inter-Bank Lien Hold")).toBeTruthy();
    // The traced account from the cluster is offered and preselected.
    expect(await screen.findByText(/XXXX-4471/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Proposed Lien Amount/i), { target: { value: "1500" } });

    const holdBtn = screen.getByRole("button", { name: /Hold to request lien/i });
    const actions = () =>
      vi.mocked(apiClient.POST).mock.calls.filter((c) => c[0] === "/alerts/{alert_id}/actions");

    // Let go well before 600 ms: nothing is sent.
    fireEvent.pointerDown(holdBtn, { button: 0, pointerType: "mouse" });
    await new Promise((r) => setTimeout(r, 150));
    fireEvent.pointerUp(holdBtn);
    await new Promise((r) => setTimeout(r, 700));
    expect(actions()).toHaveLength(0);

    // Hold through 600 ms: one request, carrying the account and integer paise.
    fireEvent.pointerDown(holdBtn, { button: 0, pointerType: "mouse" });
    await waitFor(() => expect(actions()).toHaveLength(1), { timeout: 2000 });
    const [, opts] = actions()[0] as unknown as [string, { body: { type: string; params: Record<string, unknown> } }];
    const body = opts.body;
    expect(body.type).toBe("request_hold");
    expect(body.params).toEqual({ account_id: "ACC-7", proposed_paise: 150000 });

    // Optimistic status flip: the alert reads as actioned.
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
