/**
 * CaseDetail.test.tsx — Component tests for CaseDetail, Brief Disclaimer, and Role-Gated Masking.
 * DOC 3 §S1 & DOC 4 §C6 Done When:
 *   - CaseDetail shows the brief text ending with the required disclaimer line:
 *     "Whether to register an FIR is the investigating officer's decision."
 *   - No unmasked refs for a non-LEA fixture principal.
 *   - Unmasked refs for an LEA fixture principal.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CaseDetail } from "../CaseDetail";
import { FIXTURE_CASE_1, REQUIRED_FIR_DISCLAIMER } from "../api/useCases";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/schema.d.ts";

const mockLeaPrincipal: Principal = {
  user_id: "USR-INV-UP",
  username: "investigator_up",
  role: "state_investigator",
  scope: { state_id: "UP" },
  permissions: ["VIEW_CASES", "VIEW_ALERTS"],
};

const mockNonLeaPrincipal: Principal = {
  user_id: "USR-BANK-NODAL",
  username: "bank_nodal_hdfc",
  role: "bank_nodal",
  scope: {},
  permissions: ["VIEW_ALERTS", "VIEW_CASES"],
};

function renderCaseDetail(principal: Principal = mockNonLeaPrincipal) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <AuthContext.Provider
      value={{
        principal,
        isAuthenticated: true,
        can: (p) => principal.permissions.includes(p),
        loginAs: () => {},
        logout: () => {},
      }}
    >
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <CaseDetail caseData={FIXTURE_CASE_1} />
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
    renderCaseDetail(mockLeaPrincipal);

    expect(screen.getByTestId("case-detail")).toBeTruthy();

    // Check header info
    expect(screen.getByText("Case Dossier: CASE-2026-001")).toBeTruthy();
    expect(screen.getByText("Consolidated Case Brief")).toBeTruthy();

    // Check mandatory FIR disclaimer
    const disclaimerEl = screen.getByTestId("fir-disclaimer");
    expect(disclaimerEl).toBeTruthy();
    expect(disclaimerEl.textContent).toContain(REQUIRED_FIR_DISCLAIMER);
    expect(disclaimerEl.textContent).toContain(
      "Whether to register an FIR is the investigating officer's decision.",
    );
  });

  it("strictly masks all account references for a non-LEA principal (DOC 4 §C6 invariant)", () => {
    // Render as non-LEA principal (bank_nodal)
    renderCaseDetail(mockNonLeaPrincipal);

    // Non-LEA masking session indicator is present
    expect(screen.getByTestId("masking-indicator")).toBeTruthy();

    // Accounts table is rendered
    expect(screen.getByTestId("accounts-table")).toBeTruthy();

    // Unmasked account references from fixture 1:
    // ICIC-10293847561, PUNB-55443322110, AXIS-77889900112, KKBK-33221144556
    const rawRefs = [
      "ICIC-10293847561",
      "PUNB-55443322110",
      "AXIS-77889900112",
      "KKBK-33221144556",
    ];

    for (const rawRef of rawRefs) {
      expect(screen.queryByText(rawRef)).toBeNull();
    }

    // Masked references MUST be present
    expect(screen.getByText("ICIC-••••-7561")).toBeTruthy();
    expect(screen.getByText("PUNB-••••-2110")).toBeTruthy();
    expect(screen.getByText("AXIS-••••-0112")).toBeTruthy();
    expect(screen.getByText("KKBK-••••-4556")).toBeTruthy();
  });

  it("reveals unmasked account references for an LEA principal", () => {
    // Render as LEA principal (state_investigator)
    renderCaseDetail(mockLeaPrincipal);

    // Non-LEA masking indicator is NOT present
    expect(screen.queryByTestId("masking-indicator")).toBeNull();

    // Full unmasked account references ARE present
    expect(screen.getByText("ICIC-10293847561")).toBeTruthy();
    expect(screen.getByText("PUNB-55443322110")).toBeTruthy();
    expect(screen.getByText("AXIS-77889900112")).toBeTruthy();
    expect(screen.getByText("KKBK-33221144556")).toBeTruthy();
  });

  it("renders top disbursal locations and evidence telemetry timeline", () => {
    renderCaseDetail(mockLeaPrincipal);

    // Top locations
    expect(screen.getByText("Top Disbursal Locations")).toBeTruthy();
    expect(screen.getByText("Sector 18 ATM Cluster, Noida")).toBeTruthy();
    expect(screen.getByText("4 hits")).toBeTruthy();

    // Timeline
    expect(screen.getByText("Case Telemetry Timeline")).toBeTruthy();
    expect(
      screen.getByText("Initial Complaint Registered (NCRB Portal)"),
    ).toBeTruthy();
    expect(
      screen.getByText("Automated Case Bundling Completed"),
    ).toBeTruthy();

    // Embedded Cytoscape ClusterGraph is present
    expect(screen.getByTestId("cluster-graph-container")).toBeTruthy();
  });
});
