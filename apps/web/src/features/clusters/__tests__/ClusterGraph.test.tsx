/**
 * ClusterGraph.test.tsx — Unit & component tests for Cytoscape ClusterGraph and ClustersPage.
 * DOC 3 §S1 & DOC 4 §C6 Done When:
 *   - ClusterGraph renders a fixture graph and caps at 200 nodes with a "+N more" node;
 *   - Warning badge indicates node capping;
 *   - Role-gated display masks account references for non-LEA principals.
 *
 * The real backend already masks server-side (access.mask_ref, per the calling principal): a
 * node's `masked_ref` field IS the raw ref for a full-access role and a masked one otherwise.
 * These fixtures simulate what the API returns for each principal, matching real
 * casework.ClusterNode ({id, kind, masked_ref, bank} — no separate unmasked field, no label,
 * no per-node amount; DOC 4 A12).
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ClusterGraph, isLeaRole } from "../ClusterGraph";
import ClustersPage from "../ClustersPage";
import { AuthContext } from "../../../app/auth/AuthContext";
import { apiClient } from "../../../shared/api/client";
import type { Principal } from "../../../shared/api/types.ts";
import type { ClusterEdge, ClusterNode } from "../types";

vi.mock("../../../shared/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

const STANDARD_NODES_RAW: ClusterNode[] = [
  { id: "node-vic-1", kind: "account", account_ref: "SBIN-99201481102", masked_ref: "SBIN-99201481102", bank: "SBI" },
  { id: "node-vic-2", kind: "account", account_ref: "HDFC-88192004199", masked_ref: "HDFC-88192004199", bank: "HDFC" },
  { id: "node-mule-1", kind: "account", account_ref: "ICIC-10293847561", masked_ref: "ICIC-10293847561", bank: "ICICI" },
  { id: "node-mule-2", kind: "account", account_ref: "PUNB-55443322110", masked_ref: "PUNB-55443322110", bank: "PNB" },
  { id: "node-mule-3", kind: "account", account_ref: "AXIS-77889900112", masked_ref: "AXIS-77889900112", bank: "AXIS" },
  { id: "node-agg-1", kind: "account", account_ref: "KKBK-33221144556", masked_ref: "KKBK-33221144556", bank: "KOTAK" },
  { id: "node-exit-1", kind: "account", account_ref: "ATM-NCR-SECTOR-18", masked_ref: "ATM-NCR-SECTOR-18", bank: "SBI" },
  { id: "node-exit-2", kind: "account", account_ref: "ATM-NCR-SECTOR-62", masked_ref: "ATM-NCR-SECTOR-62", bank: "HDFC" },
];

const STANDARD_NODES_MASKED: ClusterNode[] = STANDARD_NODES_RAW.map((n) => ({
  ...n,
  account_ref: n.masked_ref?.replace(/^(\w+)-(\d+)(\d{4})$/, "$1-••••-$3") ?? n.masked_ref,
  masked_ref: n.masked_ref?.replace(/^(\w+)-(\d+)(\d{4})$/, "$1-••••-$3") ?? n.masked_ref,
}));

const STANDARD_EDGES: ClusterEdge[] = [
  { from: "node-vic-1", to: "node-mule-1", amount_paise: 15_00_000_00 },
  { from: "node-vic-2", to: "node-mule-2", amount_paise: 27_00_000_00 },
  { from: "node-mule-1", to: "node-mule-3", amount_paise: 16_00_000_00 },
  { from: "node-mule-2", to: "node-mule-3", amount_paise: 25_00_000_00 },
  { from: "node-mule-3", to: "node-agg-1", amount_paise: 40_00_000_00 },
  { from: "node-agg-1", to: "node-exit-1", amount_paise: 20_00_000_00 },
  { from: "node-agg-1", to: "node-exit-2", amount_paise: 20_00_000_00 },
];

function generateBigCluster(): { nodes: ClusterNode[]; edges: ClusterEdge[] } {
  const totalNodes = 245;
  const nodes: ClusterNode[] = [{ id: "big-root", kind: "account", masked_ref: "SBIN-99000000001", bank: "SBI" }];
  const edges: ClusterEdge[] = [];
  for (let i = 1; i < totalNodes; i++) {
    nodes.push({ id: `big-node-${i}`, kind: "account", masked_ref: `AXIS-4000${String(i).padStart(4, "0")}`, bank: "AXIS" });
    const parentId = i % 5 === 0 ? "big-root" : `big-node-${Math.max(0, i - (i % 7 || 1))}`;
    edges.push({ from: parentId, to: `big-node-${i}`, amount_paise: 50_000_00 });
  }
  return { nodes, edges };
}

const BIG_CLUSTER = generateBigCluster();

const mockLeaPrincipal: Principal = {
  user_id: "USR-LEA-01",
  name: "officer_up",
  role: "state_investigator",
  scope: { state_id: "UP" },
  permissions: ["VIEW_CASES", "VIEW_ALERTS"],
};

const mockNonLeaPrincipal: Principal = {
  user_id: "USR-BANK-01",
  name: "bank_officer",
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
        isReady: true,
        login: async () => {},
        logout: async () => {},
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
    renderWithProviders(<ClusterGraph data={{ nodes: STANDARD_NODES_RAW, edges: STANDARD_EDGES }} />);

    expect(screen.getByTestId("cluster-graph-container")).toBeTruthy();
    expect(screen.getByTestId("cytoscape-canvas")).toBeTruthy();
    expect(screen.queryByTestId("node-capped-badge")).toBeNull();

    const nodesList = screen.getByTestId("graph-nodes-list");
    expect(nodesList.children.length).toBe(8);
    expect(screen.getByTestId("graph-node-node-vic-1")).toBeTruthy();
    expect(screen.getByTestId("graph-node-node-agg-1")).toBeTruthy();
  });

  it("caps graph at 200 nodes and renders '+N more' summary node when total nodes > 200", () => {
    expect(BIG_CLUSTER.nodes.length).toBe(245);

    renderWithProviders(<ClusterGraph data={BIG_CLUSTER} />);

    const capBadge = screen.getByTestId("node-capped-badge");
    expect(capBadge).toBeTruthy();
    expect(capBadge.textContent).toContain("45");

    const nodesList = screen.getByTestId("graph-nodes-list");
    expect(nodesList.children.length).toBe(201);

    const summaryNodeEl = screen.getByTestId("graph-node-node-capped-summary");
    expect(summaryNodeEl).toBeTruthy();
    expect(summaryNodeEl.getAttribute("data-is-summary")).toBe("true");
  });

  it("shows what the server already masked for non-LEA principals", () => {
    renderWithProviders(
      <ClusterGraph data={{ nodes: STANDARD_NODES_MASKED, edges: STANDARD_EDGES }} />,
      mockNonLeaPrincipal,
    );

    const nodesList = screen.getByTestId("graph-nodes-list");
    for (const child of Array.from(nodesList.children)) {
      const ref = child.getAttribute("data-ref") || "";
      expect(ref).not.toBe("ICIC-10293847561");
      expect(ref).not.toBe("PUNB-55443322110");
    }

    const mule1Node = screen.getByTestId("graph-node-node-mule-1");
    expect(mule1Node.getAttribute("data-ref")).toBe("ICIC-••••-7561");
  });

  it("shows unmasked account references the server sent for LEA principals", () => {
    renderWithProviders(
      <ClusterGraph data={{ nodes: STANDARD_NODES_RAW, edges: STANDARD_EDGES }} />,
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
    vi.mocked(apiClient.GET).mockImplementation(((path: string) => {
      if (path === "/clusters") {
        return Promise.resolve({
          data: {
            items: [
              {
                id: "CASE-1",
                cluster_ref: "CLUSTER-2026-081",
                complaint_count: 5,
                victim_count: 2,
                total_paise: 45_00_000_00,
                first_seen: "2026-01-14T09:30:00Z",
                last_seen: "2026-01-15T11:45:00Z",
                accounts: STANDARD_NODES_RAW.map((n) => ({
                  masked_ref: n.masked_ref,
                  bank: n.bank,
                  complaint_count: 1,
                })),
                top_locations: [],
                sub_communities: [],
                brief_md: "",
                single_complaint: false,
                built_at: null,
              },
            ],
            next_cursor: null,
          },
          error: undefined,
        });
      }
      if (path === "/clusters/{cluster_id}") {
        return Promise.resolve({
          data: {
            cluster_ref: "CLUSTER-2026-081",
            size: 8,
            status: "active",
            novelty: 0.88,
            nodes: STANDARD_NODES_RAW.map((n) => ({ id: n.id, kind: "account", masked_ref: n.masked_ref, bank: n.bank })),
            edges: STANDARD_EDGES,
          },
          error: undefined,
        });
      }
      return Promise.resolve({ data: undefined, error: new Error("unmocked path") });
    }) as unknown as typeof apiClient.GET);

    renderWithProviders(
      <Routes>
        <Route path="/clusters" element={<ClustersPage />} />
        <Route path="/clusters/:id" element={<ClustersPage />} />
      </Routes>,
      mockLeaPrincipal,
      "/clusters",
    );

    expect(await screen.findByTestId("clusters-page")).toBeTruthy();

    expect(await screen.findByText("CLUSTER-2026-081 (8 nodes — active)")).toBeTruthy();
    expect(screen.getByText("₹45,00,000.00")).toBeTruthy();
    expect(screen.getByText("8 Accounts")).toBeTruthy();
    expect(screen.getByText("Novelty: 88%")).toBeTruthy();
  });
});
