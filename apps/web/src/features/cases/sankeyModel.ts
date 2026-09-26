/**
 * sankeyModel.ts — fund-flow Sankey data from the cluster edges already loaded (no new API).
 *
 * Nodes are (bank, hop column) pairs so the diagram is acyclic by construction: every link
 * goes from an earlier hop column to a later one. An edge that would go backwards or sideways
 * (money returning to an earlier account: a ring) cannot be drawn in a Sankey; it is counted
 * in `omitted` and reported, never dropped silently. Values are integer paise.
 */

import type { ClusterEdge, ClusterNode } from "../clusters/types";

export interface SankeyData {
  nodes: { name: string; column: number }[];
  links: { source: number; target: number; value: number }[];
  /** Edges left out because they close a ring (cannot be shown in a Sankey). */
  omitted: { edges: number; paise: number };
}

export function buildSankey(nodes: readonly ClusterNode[], edges: readonly ClusterEdge[]): SankeyData {
  const bankOf = new Map(nodes.map((n) => [n.id, n.bank || "UNKNOWN"]));
  const column = new Map<string, number>();
  for (const e of edges) {
    const existing = column.get(e.to);
    if (existing === undefined || e.layer < existing) column.set(e.to, e.layer);
    if (!column.has(e.from)) column.set(e.from, Math.max(0, e.layer - 1));
  }

  const index = new Map<string, number>();
  const outNodes: SankeyData["nodes"] = [];
  const nodeIndex = (id: string) => {
    const col = column.get(id) ?? 0;
    const bank = bankOf.get(id) ?? "UNKNOWN";
    const key = `${bank}@${col}`;
    let i = index.get(key);
    if (i === undefined) {
      i = outNodes.length;
      index.set(key, i);
      outNodes.push({ name: bank, column: col });
    }
    return i;
  };

  const linkValue = new Map<string, number>();
  let omittedEdges = 0;
  let omittedPaise = 0;
  for (const e of edges) {
    const amount = e.amount_paise ?? 0;
    if (amount <= 0) continue;
    if ((column.get(e.from) ?? 0) >= (column.get(e.to) ?? 0)) {
      omittedEdges += 1;
      omittedPaise += amount;
      continue;
    }
    const s = nodeIndex(e.from);
    const t = nodeIndex(e.to);
    const key = `${s}>${t}`;
    linkValue.set(key, (linkValue.get(key) ?? 0) + amount);
  }

  const links = [...linkValue.entries()].map(([key, value]) => {
    const [s, t] = key.split(">").map(Number);
    return { source: s!, target: t!, value };
  });
  return { nodes: outNodes, links, omitted: { edges: omittedEdges, paise: omittedPaise } };
}
