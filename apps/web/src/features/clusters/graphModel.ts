/**
 * graphModel.ts — pure graph logic for the cluster topology view.
 *
 * Two things live here so they can be unit-tested away from Cytoscape and the DOM:
 *
 * 1. Topological role classification. The backend gives every node kind="account" (verified:
 *    casework.cluster_graph hardcodes it), so the old victim/mule/aggregator/exit styling never
 *    matched real data and every node rendered as the same grey circle. Roles are therefore
 *    derived from the edges already fetched. They are deliberately named for what the topology
 *    shows, NOT for what an account "is": a node with no inbound hops is only where the trace
 *    begins inside the loaded (possibly capped) subgraph, not necessarily the victim.
 *
 * 2. toCytoscapeElements(): the one place API nodes/edges become Cytoscape elements. Keeping it
 *    a pure exported function is how the rendering layer stays dumb without changing the API shape.
 */

import type { ElementDefinition } from "cytoscape";
import type { ClusterEdge, ClusterNode } from "./types";

export type NodeRole = "origin" | "pass-through" | "pooling" | "terminal" | "isolated" | "summary";

/** In-degree at or above which a node reads as a pooling point (a funnel many accounts feed). */
export const POOLING_MIN_IN_DEGREE = 3;

export const ROLE_LABEL: Record<NodeRole, string> = {
  origin: "Origin (no inbound hops)",
  "pass-through": "Pass-through",
  pooling: `Pooling point (≥${POOLING_MIN_IN_DEGREE} inbound)`,
  terminal: "Terminal (no outbound hops)",
  isolated: "No traced hops",
  summary: "Summarised accounts",
};

export function edgeKey(e: ClusterEdge, idx: number): string {
  return e.id || `e-${idx}-${e.from}-${e.to}`;
}

/**
 * Pure: classify each node from in/out degree over the given edges.
 * Precedence: summary, then pooling (>= POOLING_MIN_IN_DEGREE inbound, whatever its outbound),
 * then origin (no inbound), terminal (no outbound), pass-through. A node with no edges at all
 * is "isolated": nothing relational to say about it.
 */
export function classifyRoles(
  nodes: readonly ClusterNode[],
  edges: readonly ClusterEdge[],
): Map<string, NodeRole> {
  const inDeg = new Map<string, number>();
  const outDeg = new Map<string, number>();
  for (const e of edges) {
    outDeg.set(e.from, (outDeg.get(e.from) ?? 0) + 1);
    inDeg.set(e.to, (inDeg.get(e.to) ?? 0) + 1);
  }
  const roles = new Map<string, NodeRole>();
  for (const n of nodes) {
    const i = inDeg.get(n.id) ?? 0;
    const o = outDeg.get(n.id) ?? 0;
    let role: NodeRole;
    if (n.isSummary) role = "summary";
    else if (i === 0 && o === 0) role = "isolated";
    else if (i >= POOLING_MIN_IN_DEGREE) role = "pooling";
    else if (i === 0) role = "origin";
    else if (o === 0) role = "terminal";
    else role = "pass-through";
    roles.set(n.id, role);
  }
  return roles;
}

export function maxAmountPaise(edges: readonly ClusterEdge[]): number {
  let max = 0;
  for (const e of edges) if ((e.amount_paise ?? 0) > max) max = e.amount_paise ?? 0;
  return max;
}

export interface ElementsInput {
  nodes: readonly ClusterNode[];
  edges: readonly ClusterEdge[];
  roles: ReadonlyMap<string, NodeRole>;
  /** 0..1 position of each edge within the cluster's traced timeline (edge key -> t). */
  edgeSpeed: ReadonlyMap<string, number>;
  /** Non-LEA principals never see unmasked account references in labels. */
  isLea: boolean;
}

/** Pure: API nodes/edges -> Cytoscape element definitions. */
export function toCytoscapeElements({ nodes, edges, roles, edgeSpeed, isLea }: ElementsInput): ElementDefinition[] {
  const cyNodes: ElementDefinition[] = nodes.map((n) => {
    const label = n.isSummary
      ? n.label
      : isLea
        ? (n.label ?? n.account_ref ?? n.masked_ref ?? n.id)
        : (n.label ?? n.masked_ref ?? n.id);
    return {
      group: "nodes",
      data: {
        id: n.id,
        label,
        kind: n.kind,
        role: roles.get(n.id) ?? "isolated",
        bank: n.bank || "",
        isSummary: Boolean(n.isSummary),
      },
    };
  });

  const cyEdges: ElementDefinition[] = edges.map((e, idx) => ({
    group: "edges",
    data: {
      id: edgeKey(e, idx),
      source: e.from,
      target: e.to,
      label: e.label || "",
      amount: e.amount_paise ?? 0,
      speedT: edgeSpeed.get(e.id || `${e.from}-${e.to}`) ?? 0,
    },
  }));

  return [...cyNodes, ...cyEdges];
}
