/**
 * ClusterGraph.test.tsx — Unit & component tests for Cytoscape ClusterGraph and ClustersPage.
 * DOC 3 §S1 & DOC 4 §C6 Done When:
 *   - ClusterGraph renders a fixture graph and caps at 200 nodes with a "+N more" node;
 *   - Warning badge indicates node capping;
 *   - Role-gated display masks account references for non-LEA principals.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClusterGraph, isLeaRole } from "../ClusterGraph";
import ClustersPage from "../ClustersPage";
import {
  FIXTURE_CLUSTER_STANDARD,
  FIXTURE_CLUSTER_BIG,
} from "../api/useClusters";
import { AuthContext } from "../../../app/auth/AuthContext";
import type { Principal } from "../../../shared/api/schema.d.ts";

const mockLeaPrincipal: Principal = {
  user_id: "USR-LEA-01",
  username: "officer_up",
  role: "state_investigator",
  scope: { state_id: "UP" },
  permissions: ["VIEW_CASES", "VIEW_ALERTS"],
};

const mockNonLeaPrincipal: Principal = {
  user_id: "USR-BANK-01",
  username: "bank_officer",
  role: "bank_nodal",
  scope: {},
  permissions: ["VIEW_ALERTS", "VIEW_CASES"],
};

function renderWithProviders(
  ui: React.ReactNode,
  principal: Principal = mockLeaPrincipal,
  route = "/clusters",
) {
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
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ClusterGraph & Node Capping Invariant (Step C6)", () => {
  it("renders a standard cluster graph without capping when nodes <= 200", () => {
    renderWithProviders(
      <ClusterGraph
        data={{
          nodes: FIXTURE_CLUSTER_STANDARD.nodes,
          edges: FIXTURE_CLUSTER_STANDARD.edges,
        }}
      />,
    );

    // Canvas container renders
    expect(screen.getByTestId("cluster-graph-container")).toBeTruthy();
    expect(screen.getByTestId("cytoscape-canvas")).toBeTruthy();

    // No capping alert should appear
    expect(screen.queryByTestId("node-capped-badge")).toBeNull();

    // All 8 nodes are present in semantic list
    const nodesList = screen.getByTestId("graph-nodes-list");
    expect(nodesList.children.length).toBe(8);
    expect(screen.getByTestId("graph-node-node-vic-1")).toBeTruthy();
    expect(screen.getByTestId("graph-node-node-agg-1")).toBeTruthy();
  });

  it("caps graph at 200 nodes and renders '+N more' summary node when total nodes > 200", () => {
    // FIXTURE_CLUSTER_BIG has 245 nodes
    expect(FIXTURE_CLUSTER_BIG.nodes.length).toBe(245);

    renderWithProviders(
      <ClusterGraph
        data={{
          nodes: FIXTURE_CLUSTER_BIG.nodes,
          edges: FIXTURE_CLUSTER_BIG.edges,
        }}
      />,
    );

    // Capping alert badge is displayed
    const capBadge = screen.getByTestId("node-capped-badge");
    expect(capBadge).toBeTruthy();
    expect(capBadge.textContent).toContain(
      "Graph capped: Showing top 200 nodes (+45 more accounts summarized)",
    );

    // Total rendered nodes: 200 top nodes + 1 summary node = 201 nodes
    const nodesList = screen.getByTestId("graph-nodes-list");
    expect(nodesList.children.length).toBe(201);

    // The summary node "+45 more accounts" is rendered with summary attributes
    const summaryNodeEl = screen.getByTestId("graph-node-node-capped-summary");
    expect(summaryNodeEl).toBeTruthy();
    expect(summaryNodeEl.getAttribute("data-is-summary")).toBe("true");
    expect(summaryNodeEl.textContent).toContain("+45 more accounts");
  });

  it("masks account references in graph nodes for non-LEA principals", () => {
    // Render with non-LEA principal (bank_nodal)
    renderWithProviders(
      <ClusterGraph
        data={{
          nodes: FIXTURE_CLUSTER_STANDARD.nodes,
          edges: FIXTURE_CLUSTER_STANDARD.edges,
        }}
      />,
      mockNonLeaPrincipal,
    );

    const nodesList = screen.getByTestId("graph-nodes-list");
    // Verify that NO child element has an unmasked raw account ref
    for (const child of Array.from(nodesList.children)) {
      const ref = child.getAttribute("data-ref") || "";
      // Unmasked ICICI raw account is ICIC-10293847561; masked is ICIC-••••-7561
      expect(ref).not.toBe("ICIC-10293847561");
      expect(ref).not.toBe("PUNB-55443322110");
    }

    // Node 1 should display masked ref
    const mule1Node = screen.getByTestId("graph-node-node-mule-1");
    expect(mule1Node.getAttribute("data-ref")).toBe("ICIC-••••-7561");
  });

  it("provides full account references in graph nodes for LEA principals", () => {
    // Render with LEA principal (state_investigator)
    renderWithProviders(
      <ClusterGraph
        data={{
          nodes: FIXTURE_CLUSTER_STANDARD.nodes,
          edges: FIXTURE_CLUSTER_STANDARD.edges,
        }}
      />,
      mockLeaPrincipal,
    );

    const mule1Node = screen.getByTestId("graph-node-node-mule-1");
    expect(mule1Node.getAttribute("data-ref")).toBe("ICIC-10293847561");
  });

  it("isLeaRole accurately identifies investigator and officer roles", () => {
    expect(isLeaRole("state_investigator")).toBe(true);
    expect(isLeaRole("district_officer")).toBe(true);
    expect(isLeaRole("i4c_analyst")).toBe(true);
    expect(isLeaRole("admin")).toBe(true);
    expect(isLeaRole("bank_nodal")).toBe(false);
    expect(isLeaRole("demo_operator")).toBe(false);
    expect(isLeaRole(undefined)).toBe(false);
  });
});

describe("ClustersPage Component (Step C6)", () => {
  it("renders clusters page with cluster stats and selector", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/clusters" element={<ClustersPage />} />
        <Route path="/clusters/:id" element={<ClustersPage />} />
      </Routes>,
      mockLeaPrincipal,
      "/clusters",
    );

    // Expect page to render
    expect(await screen.findByTestId("clusters-page")).toBeTruthy();

    // Default selected cluster is CLUSTER-2026-081
    expect(screen.getByText("CLUSTER-2026-081 (8 nodes — active)")).toBeTruthy();
    expect(screen.getByText("₹45,00,000.00")).toBeTruthy();
    expect(screen.getByText("8 Accounts")).toBeTruthy();
    expect(screen.getByText("Novelty: 88%")).toBeTruthy();
  });
});
