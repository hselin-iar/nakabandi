/**
 * CasesPage.test.tsx — Component tests for Bundled Cases list and filtering.
 * DOC 3 §S1 & DOC 4 §C6
 *
 * The real Case has no workflow `status` (DOC 4 A12 Learnings) — every bundled case is
 * "bundled" — so the status dropdown has nothing to distinguish; that gap is documented, not
 * faked here with values the backend can't produce.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CasesPage from "../CasesPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import { apiClient } from "../../../shared/api/client";
import type { Principal } from "../../../shared/api/types.ts";
import type { Case as ApiCase } from "../../../shared/api/types.ts";

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

function apiCase(overrides: Partial<ApiCase>): ApiCase {
  return {
    id: "CASE-2026-001",
    cluster_ref: "CLUSTER-2026-081",
    complaint_count: 5,
    victim_count: 2,
    total_paise: 45_00_000_00,
    first_seen: "2026-01-14T09:30:00Z",
    last_seen: "2026-01-15T11:45:00Z",
    accounts: [],
    top_locations: [],
    sub_communities: [],
    brief_md: "brief",
    single_complaint: false,
    built_at: null,
    ...overrides,
  };
}

const FIXTURE_CASES: ApiCase[] = [
  apiCase({ id: "CASE-2026-001", cluster_ref: "CLUSTER-2026-081", total_paise: 45_00_000_00 }),
  apiCase({
    id: "CASE-2026-002",
    cluster_ref: "CLUSTER-2026-SINGLE",
    total_paise: 1_25_000_00,
    single_complaint: true,
    complaint_count: 1,
    victim_count: 1,
  }),
  apiCase({ id: "CASE-2026-003", cluster_ref: "CLUSTER-2026-BIG", total_paise: 580_00_000_00 }),
];

const mockOfficerPrincipal: Principal = {
  user_id: "USR-INV-01",
  name: "investigator_1",
  role: "state_investigator",
  scope: { state_id: "UP" },
  permissions: ["VIEW_CASES", "VIEW_ALERTS"],
};

function renderCasesPage(route = "/cases") {
  vi.mocked(apiClient.GET).mockResolvedValue({
    data: { items: FIXTURE_CASES, next_cursor: null },
    error: undefined,
  } as unknown as never);

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
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/cases" element={<CasesPage />} />
            <Route path="/cases/:id" element={<CasesPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("CasesPage & Bundled Cases Explorer (Step C6)", () => {
  it("renders the cases table with bundled cases and single complaint badges", async () => {
    renderCasesPage();

    expect(await screen.findByTestId("cases-table")).toBeTruthy();

    expect(screen.getByTestId("case-row-CASE-2026-001")).toBeTruthy();
    expect(screen.getByTestId("case-row-CASE-2026-002")).toBeTruthy();
    expect(screen.getByTestId("case-row-CASE-2026-003")).toBeTruthy();

    expect(screen.getByTestId("single-complaint-badge")).toBeTruthy();
    expect(screen.getByText("Single")).toBeTruthy();

    expect(screen.getByText("₹45,00,000.00")).toBeTruthy();
    expect(screen.getByText("₹1,25,000.00")).toBeTruthy();
  });

  it("filters cases by text search query", async () => {
    renderCasesPage();

    expect(await screen.findByTestId("cases-table")).toBeTruthy();

    const searchInput = screen.getByTestId("cases-search-input");
    fireEvent.change(searchInput, { target: { value: "SINGLE" } });

    await waitFor(() => {
      expect(screen.getByTestId("case-row-CASE-2026-002")).toBeTruthy();
      expect(screen.queryByTestId("case-row-CASE-2026-001")).toBeNull();
      expect(screen.queryByTestId("case-row-CASE-2026-003")).toBeNull();
    });
  });

  it("filters cases using 'single complaint only' checkbox", async () => {
    renderCasesPage();

    expect(await screen.findByTestId("cases-table")).toBeTruthy();

    const checkbox = screen.getByTestId("single-complaint-checkbox");
    fireEvent.click(checkbox);

    await waitFor(() => {
      expect(screen.getByTestId("case-row-CASE-2026-002")).toBeTruthy();
      expect(screen.queryByTestId("case-row-CASE-2026-001")).toBeNull();
      expect(screen.queryByTestId("case-row-CASE-2026-003")).toBeNull();
    });
  });
});
