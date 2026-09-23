/**
 * useClusters.ts — TanStack Query hooks and hand-written fixtures for Clusters.
 * DOC 3 §S1 & DOC 4 §C6 (STUB/MOCK STRATEGY: Hand-written ClusterView until Track A Step A12 lands).
 */

import { useQuery } from "@tanstack/react-query";
import type { ClusterSummary, ClusterView, ClusterNode, ClusterEdge } from "../types";

// ---------------------------------------------------------------------------
// Fixture 1: Standard Multi-Hop Syndicate (CLUSTER-2026-081)
// ---------------------------------------------------------------------------
export const FIXTURE_CLUSTER_STANDARD: ClusterView = {
  cluster_ref: "CLUSTER-2026-081",
  size: 8,
  status: "active",
  novelty: 0.88,
  total_paise: 45_00_000_00, // ₹45,00,000
  first_seen: "2026-01-14T09:30:00Z",
  last_seen: "2026-01-15T11:45:00Z",
  single_complaint: false,
  sub_communities: [
    { id: "sub-1", label: "Mule Layer 1 (UP East)", account_count: 3 },
    { id: "sub-2", label: "Aggregator / Exit (NCR)", account_count: 2 },
  ],
  nodes: [
    {
      id: "node-vic-1",
      kind: "victim",
      account_ref: "SBIN-99201481102",
      masked_ref: "SBIN-••••-1102",
      bank: "SBI",
      label: "Victim (LKO)",
      amount_paise: 15_00_000_00,
    },
    {
      id: "node-vic-2",
      kind: "victim",
      account_ref: "HDFC-88192004199",
      masked_ref: "HDFC-••••-4199",
      bank: "HDFC",
      label: "Victim (VNS)",
      amount_paise: 30_00_000_00,
    },
    {
      id: "node-mule-1",
      kind: "mule",
      account_ref: "ICIC-10293847561",
      masked_ref: "ICIC-••••-7561",
      bank: "ICICI",
      label: "Mule L1-A",
      amount_paise: 18_00_000_00,
    },
    {
      id: "node-mule-2",
      kind: "mule",
      account_ref: "PUNB-55443322110",
      masked_ref: "PUNB-••••-2110",
      bank: "PNB",
      label: "Mule L1-B",
      amount_paise: 27_00_000_00,
    },
    {
      id: "node-mule-3",
      kind: "mule",
      account_ref: "AXIS-77889900112",
      masked_ref: "AXIS-••••-0112",
      bank: "AXIS",
      label: "Mule L2 Rapid Layering",
      amount_paise: 35_00_000_00,
    },
    {
      id: "node-agg-1",
      kind: "aggregator",
      account_ref: "KKBK-33221144556",
      masked_ref: "KKBK-••••-4556",
      bank: "KOTAK",
      label: "Aggregator Account",
      amount_paise: 42_00_000_00,
    },
    {
      id: "node-exit-1",
      kind: "exit",
      account_ref: "ATM-NCR-SECTOR-18",
      masked_ref: "ATM-••••-SEC18",
      bank: "SBI",
      label: "Cashout ATM Noida",
      amount_paise: 20_00_000_00,
    },
    {
      id: "node-exit-2",
      kind: "exit",
      account_ref: "ATM-NCR-SECTOR-62",
      masked_ref: "ATM-••••-SEC62",
      bank: "HDFC",
      label: "Cashout ATM Noida 62",
      amount_paise: 22_00_000_00,
    },
  ],
  edges: [
    { id: "e1", from: "node-vic-1", to: "node-mule-1", amount_paise: 15_00_000_00, label: "₹15L IMPS" },
    { id: "e2", from: "node-vic-2", to: "node-mule-2", amount_paise: 27_00_000_00, label: "₹27L RTGS" },
    { id: "e3", from: "node-vic-2", to: "node-mule-1", amount_paise: 3_00_000_00, label: "₹3L UPI" },
    { id: "e4", from: "node-mule-1", to: "node-mule-3", amount_paise: 16_00_000_00, label: "₹16L Layering" },
    { id: "e5", from: "node-mule-2", to: "node-mule-3", amount_paise: 25_00_000_00, label: "₹25L Layering" },
    { id: "e6", from: "node-mule-3", to: "node-agg-1", amount_paise: 40_00_000_00, label: "₹40L Concentration" },
    { id: "e7", from: "node-agg-1", to: "node-exit-1", amount_paise: 20_00_000_00, label: "₹20L ATM Disbursal" },
    { id: "e8", from: "node-agg-1", to: "node-exit-2", amount_paise: 20_00_000_00, label: "₹20L ATM Disbursal" },
  ],
};

// ---------------------------------------------------------------------------
// Fixture 2: Large Scale Syndicate (CLUSTER-2026-BIG) >200 nodes
// Generated to explicitly test 200-node capping behavior (DOC 4 §C6)
// ---------------------------------------------------------------------------
function generateLargeCluster(): ClusterView {
  const totalNodes = 245;
  const nodes: ClusterNode[] = [];
  const edges: ClusterEdge[] = [];

  // Core root hub
  nodes.push({
    id: "big-root",
    kind: "aggregator",
    account_ref: "SBIN-99000000001",
    masked_ref: "SBIN-••••-0001",
    bank: "SBI",
    label: "Syndicate Central Hub",
    amount_paise: 250_00_000_00,
  });

  for (let i = 1; i < totalNodes; i++) {
    const isVictim = i <= 20;
    const isExit = i > 220;
    const kind: ClusterNode["kind"] = isVictim ? "victim" : isExit ? "exit" : "mule";
    const bank = i % 4 === 0 ? "HDFC" : i % 3 === 0 ? "ICICI" : i % 2 === 0 ? "PNB" : "AXIS";
    const refRaw = `${bank}-4000${String(i).padStart(4, "0")}`;
    const refMasked = `${bank}-••••-${String(i).padStart(4, "0")}`;

    nodes.push({
      id: `big-node-${i}`,
      kind,
      account_ref: refRaw,
      masked_ref: refMasked,
      bank,
      label: `${kind.toUpperCase()} #${i}`,
      amount_paise: (1000 + i * 50) * 100_00,
    });

    // Connect node to root or neighbor
    const parentId = i % 5 === 0 ? "big-root" : `big-node-${Math.max(0, i - (i % 7 || 1))}`;
    edges.push({
      id: `big-e-${i}`,
      from: isVictim ? `big-node-${i}` : parentId,
      to: isVictim ? parentId : `big-node-${i}`,
      amount_paise: 50_000_00,
      label: "Tx",
    });
  }

  return {
    cluster_ref: "CLUSTER-2026-BIG",
    size: totalNodes,
    status: "active",
    novelty: 0.94,
    total_paise: 580_00_000_00,
    first_seen: "2026-01-01T00:00:00Z",
    last_seen: "2026-01-15T12:00:00Z",
    single_complaint: false,
    sub_communities: [
      { id: "sub-big-1", label: "Northern Mule Grid", account_count: 140 },
      { id: "sub-big-2", label: "Western ATM Outlets", account_count: 105 },
    ],
    nodes,
    edges,
  };
}

export const FIXTURE_CLUSTER_BIG: ClusterView = generateLargeCluster();

// ---------------------------------------------------------------------------
// Fixture 3: Single-Complaint Cluster (CLUSTER-2026-SINGLE)
// ---------------------------------------------------------------------------
export const FIXTURE_CLUSTER_SINGLE: ClusterView = {
  cluster_ref: "CLUSTER-2026-SINGLE",
  size: 3,
  status: "reviewing",
  novelty: 0.42,
  total_paise: 1_25_000_00, // ₹1,25,000
  first_seen: "2026-01-15T08:15:00Z",
  last_seen: "2026-01-15T08:45:00Z",
  single_complaint: true,
  sub_communities: [{ id: "sub-s1", label: "Isolated P2P Transfer", account_count: 3 }],
  nodes: [
    {
      id: "sc-vic-1",
      kind: "victim",
      account_ref: "SBIN-11223344556",
      masked_ref: "SBIN-••••-4556",
      bank: "SBI",
      label: "Complainant Victim",
      amount_paise: 1_25_000_00,
    },
    {
      id: "sc-mule-1",
      kind: "mule",
      account_ref: "PAYTM-99887766554",
      masked_ref: "PAYTM-••••-6554",
      bank: "PAYTM",
      label: "Mule Wallet",
      amount_paise: 1_25_000_00,
    },
    {
      id: "sc-exit-1",
      kind: "exit",
      account_ref: "ATM-DELHI-CP",
      masked_ref: "ATM-••••-CP",
      bank: "SBI",
      label: "CP ATM Cashout",
      amount_paise: 1_00_000_00,
    },
  ],
  edges: [
    { id: "sc-e1", from: "sc-vic-1", to: "sc-mule-1", amount_paise: 1_25_000_00, label: "₹1.25L UPI" },
    { id: "sc-e2", from: "sc-mule-1", to: "sc-exit-1", amount_paise: 1_00_000_00, label: "₹1.0L ATM" },
  ],
};

const ALL_CLUSTERS: ClusterView[] = [
  FIXTURE_CLUSTER_STANDARD,
  FIXTURE_CLUSTER_BIG,
  FIXTURE_CLUSTER_SINGLE,
];

// ---------------------------------------------------------------------------
// React Query Hooks
// ---------------------------------------------------------------------------

export function useClusters() {
  return useQuery<ClusterSummary[]>({
    queryKey: ["clusters"],
    queryFn: async () => {
      // Hand-written fixture until Track A Step A12 lands
      return ALL_CLUSTERS.map((c) => ({
        cluster_ref: c.cluster_ref,
        size: c.size,
        status: c.status,
        novelty: c.novelty,
        total_paise: c.total_paise,
        first_seen: c.first_seen,
        last_seen: c.last_seen,
        single_complaint: c.single_complaint,
      }));
    },
    staleTime: 60_000,
  });
}

export function useCluster(clusterRef: string | undefined) {
  return useQuery<ClusterView | null>({
    queryKey: ["cluster", clusterRef],
    queryFn: async () => {
      if (!clusterRef) return null;
      const match = ALL_CLUSTERS.find(
        (c) => c.cluster_ref.toLowerCase() === clusterRef.toLowerCase(),
      );
      return match ?? null;
    },
    enabled: Boolean(clusterRef),
    staleTime: 60_000,
  });
}
