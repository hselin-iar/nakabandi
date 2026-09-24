/**
 * CaseDetail.test.tsx — Component tests for CaseDetail, Brief Disclaimer, and Role-Gated Masking.
 * DOC 3 §S1 & DOC 4 §C6 Done When:
 *   - CaseDetail shows the brief text ending with the required disclaimer line:
 *     "Whether to register an FIR is the investigating officer's decision."
 *   - No unmasked refs for a non-LEA fixture principal.
 *   - Unmasked refs for an LEA fixture principal.
 *
 * The real backend masks server-side (access.mask_ref, per the calling principal) before the
 * response ever reaches the client — so what CaseDetail renders is just whatever `masked_ref`
 * it was given; these two fixtures simulate what the API would return for each principal, not a
 * client-side masking decision.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CaseDetail } from "../CaseDetail";
import { REQUIRED_FIR_DISCLAIMER } from "../api/useCases";
import { AuthContext } from "../../../app/auth/AuthContext";
import { apiClient } from "../../../shared/api/client";
import type { Principal } from "../../../shared/api/types.ts";
import type { Case } from "../types";

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

const RAW_REFS = ["ICIC-10293847561", "PUNB-55443322110", "AXIS-77889900112", "KKBK-33221144556"];
const MASKED_REFS = ["ICIC-••••-7561", "PUNB-••••-2110", "AXIS-••••-0112", "KKBK-••••-4556"];

function fixtureCase(masked: boolean): Case {
  const refs = masked ? MASKED_REFS : RAW_REFS;
  return {
    id: "CASE-2026-001",
    cluster_ref: "CLUSTER-2026-081",
    complaint_count: 5,
    victim_count: 2,
    total_paise: 45_00_000_00,
    first_seen: "2026-01-14T09:30:00Z",
    last_seen: "2026-01-15T11:45:00Z",
    status: "bundled",
    single_complaint: false,
    accounts: [
      { account_ref: refs[0], masked_ref: refs[0], bank: "ICICI", complaint_count: 3 },
      { account_ref: refs[1], masked_ref: refs[1], bank: "PNB", complaint_count: 2 },
      { account_ref: refs[2], masked_ref: refs[2], bank: "AXIS", complaint_count: 0 },
      { account_ref: refs[3], masked_ref: refs[3], bank: "KOTAK", complaint_count: 0 },
    ],
    top_locations: [
      { id: "LOC-NOIDA-SEC18", name: "Sector 18 ATM Cluster, Noida", count: 4, last_at: "2026-01-15T11:30:00Z" },
    ],
    sub_communities: [],
    timeline: [],
    brief_md: `### Case Summary\n\n${REQUIRED_FIR_DISCLAIMER}`,
  };
}

const mockLeaPrincipal: Principal = {
  user_id: "USR-INV-UP",
  name: "investigator_up",
  role: "state_investigator",
  scope: { state_id: "UP" },
  permissions: ["VIEW_CASES", "VIEW_ALERTS"],
};

const mockNonLeaPrincipal: Principal = {
  user_id: "USR-BANK-NODAL",
  name: "bank_nodal_hdfc",
  role: "bank_nodal",
  scope: {},
  permissions: ["VIEW_ALERTS", "VIEW_CASES"],
};

function renderCaseDetail(principal: Principal, caseData: Case) {
  vi.mocked(apiClient.GET).mockResolvedValue({
    data: { cluster_ref: caseData.cluster_ref, size: 0, status: "active", novelty: 0, nodes: [], edges: [] },
    error: undefined,
  } as unknown as never);

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
        login: async () => {},
        logout: async () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <CaseDetail caseData={caseData} />
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("CaseDetail & Invariants (Step C6)", () => {
  it("renders the case brief concluding with the required FIR statutory disclaimer", () => {
    renderCaseDetail(mockLeaPrincipal, fixtureCase(false));

    expect(screen.getByTestId("case-detail")).toBeTruthy();
    expect(screen.getByText("Case Dossier: CASE-2026-001")).toBeTruthy();
    expect(screen.getByText("Consolidated Case Brief")).toBeTruthy();

    const disclaimerEl = screen.getByTestId("fir-disclaimer");
    expect(disclaimerEl).toBeTruthy();
    expect(disclaimerEl.textContent).toContain(REQUIRED_FIR_DISCLAIMER);
  });

  it("shows what the server already masked for a non-LEA principal", () => {
    renderCaseDetail(mockNonLeaPrincipal, fixtureCase(true));

    expect(screen.getByTestId("masking-indicator")).toBeTruthy();
    expect(screen.getByTestId("accounts-table")).toBeTruthy();

    for (const rawRef of RAW_REFS) {
      expect(screen.queryByText(rawRef)).toBeNull();
    }
    for (const maskedRef of MASKED_REFS) {
      expect(screen.getByText(maskedRef)).toBeTruthy();
    }
  });

  it("shows unmasked account references the server sent for an LEA principal", () => {
    renderCaseDetail(mockLeaPrincipal, fixtureCase(false));

    expect(screen.queryByTestId("masking-indicator")).toBeNull();
    for (const rawRef of RAW_REFS) {
      expect(screen.getByText(rawRef)).toBeTruthy();
    }
  });

  it("renders top disbursal locations", async () => {
    renderCaseDetail(mockLeaPrincipal, fixtureCase(false));

    expect(screen.getByText("Top Disbursal Locations")).toBeTruthy();
    expect(screen.getByText("Sector 18 ATM Cluster, Noida")).toBeTruthy();
    expect(screen.getByText("4 hits")).toBeTruthy();
    expect(await screen.findByTestId("cluster-graph-container")).toBeTruthy();
  });
});
