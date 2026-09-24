/**
 * CasesPage.test.tsx — Component tests for Bundled Cases list and filtering.
 * DOC 3 §S1 & DOC 4 §C6
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CasesPage from "../CasesPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/schema.d.ts";

const mockOfficerPrincipal: Principal = {
  user_id: "USR-INV-01",
  username: "investigator_1",
  role: "state_investigator",
  scope: { state_id: "UP" },
  permissions: ["VIEW_CASES", "VIEW_ALERTS"],
};

function renderCasesPage(route = "/cases") {
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

    // Check case rows
    expect(screen.getByTestId("case-row-CASE-2026-001")).toBeTruthy();
    expect(screen.getByTestId("case-row-CASE-2026-002")).toBeTruthy();
    expect(screen.getByTestId("case-row-CASE-2026-003")).toBeTruthy();

    // CASE-2026-002 has a single complaint badge
    expect(screen.getByTestId("single-complaint-badge")).toBeTruthy();
    expect(screen.getByText("Single")).toBeTruthy();

    // Total amounts formatted in INR
    expect(screen.getByText("₹45,00,000.00")).toBeTruthy();
    expect(screen.getByText("₹1,25,000.00")).toBeTruthy();
  });

  it("filters cases by text search query", async () => {
    renderCasesPage();

    expect(await screen.findByTestId("cases-table")).toBeTruthy();

    const searchInput = screen.getByTestId("cases-search-input");
    fireEvent.change(searchInput, { target: { value: "SINGLE" } });

    await waitFor(() => {
      // Only CASE-2026-002 (linked to CLUSTER-2026-SINGLE) should match
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

  it("filters cases using the status dropdown", async () => {
    renderCasesPage();

    expect(await screen.findByTestId("cases-table")).toBeTruthy();

    const statusFilter = screen.getByTestId("cases-status-filter");
    fireEvent.change(statusFilter, { target: { value: "fir_recommended" } });

    await waitFor(() => {
      expect(screen.getByTestId("case-row-CASE-2026-003")).toBeTruthy();
      expect(screen.queryByTestId("case-row-CASE-2026-001")).toBeNull();
      expect(screen.queryByTestId("case-row-CASE-2026-002")).toBeNull();
    });
  });
});
