/**
 * types.ts — Type definitions for Clusters & Graph visualization.
 * DOC 3 §S1 (Cluster Case Bundling) & DOC 4 §C6
 */

/** "account" is the real backend's only kind today (DOC 4 A12: no per-node role
 * classification yet); the others are UI-only categories a future step may add. */
export type NodeKind = "account" | "mule" | "victim" | "aggregator" | "exit" | "summary";

export interface ClusterNode {
  id: string;
  kind: NodeKind;
  /** Server-masked account or entity reference (e.g. "•••• 4821") */
  masked_ref?: string;
  /** Full account reference (only visible to LEA roles) */
  account_ref?: string;
  bank?: string;
  label?: string;
  amount_paise?: number;
  /** True if this node was synthesized to represent capped nodes (>200) */
  isSummary?: boolean;
}

export interface ClusterEdge {
  id?: string;
  from: string;
  to: string;
  amount_paise?: number;
  label?: string;
}

export interface ClusterGraphData {
  nodes: ClusterNode[];
  edges: ClusterEdge[];
}

export type ClusterStatus = "active" | "reviewing" | "merged" | "closed";

export interface ClusterSummary {
  cluster_ref: string;
  size: number;
  /** The real backend only ever returns "active" today (not wired to cluster-absorption
   * state) — DOC 4 A12 Learnings. */
  status?: ClusterStatus;
  /** Not wired to the forecast facade yet — always 0 from the real API (DOC 4 A12 Learnings). */
  novelty?: number;
  total_paise?: number;
  first_seen?: string;
  last_seen?: string;
  single_complaint?: boolean;
}

export interface ClusterView extends ClusterSummary, ClusterGraphData {
  sub_communities?: Array<{
    id: string;
    label: string;
    account_count: number;
  }>;
}
