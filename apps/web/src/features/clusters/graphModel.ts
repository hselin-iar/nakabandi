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

/**
 * Pure: merge parallel hops between the same ordered pair into one edge (sum of amounts, earliest
 * time, lowest layer, `hop_count` of raw hops). Dozens of hops between a handful of mule accounts
 * otherwise draw as an unreadable ball; the count and total stay visible on the merged edge.
 */
export function aggregateEdges(edges: readonly ClusterEdge[]): ClusterEdge[] {
  const agg = new Map<string, ClusterEdge>();
  for (const e of edges) {
    const key = `${e.from}=>${e.to}`;
    const prev = agg.get(key);
    if (!prev) {
      agg.set(key, { ...e, id: `a:${key}`, hop_count: e.hop_count ?? 1 });
    } else {
      prev.amount_paise = (prev.amount_paise ?? 0) + (e.amount_paise ?? 0);
      prev.hop_count = (prev.hop_count ?? 1) + (e.hop_count ?? 1);
      prev.layer = Math.min(prev.layer, e.layer);
      if (e.event_at < prev.event_at) prev.event_at = e.event_at;
    }
  }
  return [...agg.values()];
}

/** A merged graph with more edges than this many per account is a hairball, not a trail. */
export const DENSE_EDGES_PER_NODE = 3;

/**
 * Pure: keep each account's `perNode` largest outgoing flows and its largest incoming one. The
 * strongest flows carry the money; the rest is reachable again with "show all". Never used
 * silently: the caller reports how many flows (and how much money) were set aside.
 */
export function strongestEdges(edges: readonly ClusterEdge[], perNode = 2): ClusterEdge[] {
  const keep = new Set<ClusterEdge>();
  const byOut = new Map<string, ClusterEdge[]>();
  const byIn = new Map<string, ClusterEdge[]>();
  for (const e of edges) {
    byOut.set(e.from, [...(byOut.get(e.from) ?? []), e]);
    byIn.set(e.to, [...(byIn.get(e.to) ?? []), e]);
  }
  const top = (list: ClusterEdge[], k: number) =>
    [...list].sort((a, b) => (b.amount_paise ?? 0) - (a.amount_paise ?? 0)).slice(0, k);
  for (const list of byOut.values()) for (const e of top(list, perNode)) keep.add(e);
  for (const list of byIn.values()) for (const e of top(list, 1)) keep.add(e);
  return edges.filter((e) => keep.has(e));
}

/**
 * Pure: breadth-first depth of every node from the trace's origins (nodes nobody pays; if the
 * trail is one big ring, the payer of the earliest hop). An edge whose target is not deeper than
 * its source is a BACK edge: money returning to an earlier or same-level account. Layout uses only
 * the forward edges, so the picture reads left to right and the back edges are drawn honestly on top.
 */
export function computeDepths(
  nodes: readonly ClusterNode[],
  edges: readonly ClusterEdge[],
): Map<string, number> {
  const adj = new Map<string, string[]>();
  const hasIn = new Set<string>();
  for (const e of edges) {
    if (e.from === e.to) continue;
    adj.set(e.from, [...(adj.get(e.from) ?? []), e.to]);
    hasIn.add(e.to);
  }
  const depth = new Map<string, number>();
  const bfs = (start: string) => {
    if (depth.has(start)) return;
    depth.set(start, 0);
    const queue = [start];
    while (queue.length) {
      const cur = queue.shift()!;
      for (const next of adj.get(cur) ?? []) {
        if (!depth.has(next)) {
          depth.set(next, depth.get(cur)! + 1);
          queue.push(next);
        }
      }
    }
  };
  const byTime = [...edges].sort((a, b) => (a.event_at < b.event_at ? -1 : a.event_at > b.event_at ? 1 : a.layer - b.layer));
  for (const n of nodes) if (adj.has(n.id) && !hasIn.has(n.id)) bfs(n.id);
  for (const e of byTime) bfs(e.from); // rings / components with no pure origin
  for (const n of nodes) if (!depth.has(n.id)) depth.set(n.id, 0);
  return depth;
}

/** Shorten long account references for on-canvas labels; the inspector keeps the full text. */
export function shortRef(label: string | undefined): string {
  if (!label) return "";
  return label.length > 14 ? `${label.slice(0, 4)}…${label.slice(-6)}` : label;
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
  const depth = computeDepths(nodes, edges);
  const flow = new Map<string, number>();
  for (const e of edges) {
    flow.set(e.from, (flow.get(e.from) ?? 0) + (e.amount_paise ?? 0));
    flow.set(e.to, (flow.get(e.to) ?? 0) + (e.amount_paise ?? 0));
  }
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
        short: n.isSummary ? label : shortRef(label),
        flow: flow.get(n.id) ?? 0,
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
      label: e.label || ((e.hop_count ?? 1) > 1 ? `×${e.hop_count}` : ""),
      hops: e.hop_count ?? 1,
      back: e.from !== e.to && (depth.get(e.to) ?? 0) <= (depth.get(e.from) ?? 0),
      amount: e.amount_paise ?? 0,
      speedT: edgeSpeed.get(e.id || `${e.from}-${e.to}`) ?? 0,
    },
  }));

  return [...cyNodes, ...cyEdges];
}

// ---------------------------------------------------------------------------
// View derivation: filters, bank grouping and the 200-node cap (all pure)
// ---------------------------------------------------------------------------

export const MAX_NODES = 200;
export const CAPPED_SUMMARY_ID = "node-capped-summary";
export const BANK_GROUP_PREFIX = "bank-group:";

export interface ViewOptions {
  /** Show only hops with layer <= maxHops (Infinity = all). */
  maxHops: number;
  /** Hide edges moving less than this many paise (0 = show all). */
  minAmountPaise: number;
  /** Collapse accounts sharing a bank into one node per bank ("HDFC — 14 accounts"). */
  groupByBank: boolean;
  /** Banks the operator has expanded again while grouping is on. */
  expandedBanks?: ReadonlySet<string>;
  /** Thin a dense graph to its strongest flows (default true; ignored for sparse graphs). */
  strongestOnly?: boolean;
}

export interface GraphView {
  nodes: ClusterNode[];
  edges: ClusterEdge[];
  /** Edges hidden by the hop/amount filters (NOT the 200-node cap), with their summed amount. */
  hidden: { edges: number; paise: number };
  /** Flows set aside by the "strongest flows" thinning (merged edges), with their summed amount. */
  thinned: { edges: number; paise: number };
  isCapped: boolean;
  /** Accounts summarised by the cap. */
  cappedCount: number;
  maxLayer: number;
  maxAmount: number;
  /** Largest money in+out of any one drawn node (paise), for node sizing. */
  maxFlow: number;
}

export function maxLayerOf(edges: readonly ClusterEdge[]): number {
  let m = 0;
  for (const e of edges) if (e.layer > m) m = e.layer;
  return m;
}

/** Pure: apply the 200-node cap (kept from the original component, moved verbatim in behaviour). */
export function capGraph(
  nodes: readonly ClusterNode[],
  edges: readonly ClusterEdge[],
): { nodes: ClusterNode[]; edges: ClusterEdge[]; isCapped: boolean; hiddenCount: number } {
  if (nodes.length <= MAX_NODES) {
    return { nodes: [...nodes], edges: [...edges], isCapped: false, hiddenCount: 0 };
  }
  const priorityScore = (n: ClusterNode) => {
    let score = n.amount_paise ?? 0;
    if (n.kind === "aggregator") score += 10_000_000_00;
    if (n.kind === "exit") score += 5_000_000_00;
    if (n.kind === "victim") score += 2_000_000_00;
    return score;
  };
  const sorted = [...nodes].sort((a, b) => priorityScore(b) - priorityScore(a));
  const top = sorted.slice(0, MAX_NODES);
  const hidden = nodes.length - MAX_NODES;
  const kept = new Set(top.map((n) => n.id));
  const label = `+${hidden} more accounts`;
  const summary: ClusterNode = {
    id: CAPPED_SUMMARY_ID,
    kind: "summary",
    label,
    masked_ref: label,
    account_ref: label,
    bank: "VARIOUS",
    isSummary: true,
  };
  const out: ClusterEdge[] = [];
  const seen = new Set<string>();
  for (const e of edges) {
    const f = kept.has(e.from);
    const t = kept.has(e.to);
    if (f && t) out.push(e);
    else if (f && !t) {
      const k = `${e.from}->summary`;
      if (!seen.has(k)) {
        seen.add(k);
        out.push({ id: `summary-edge-${k}`, from: e.from, to: CAPPED_SUMMARY_ID, label: "Aggregated flow", layer: e.layer, event_at: e.event_at });
      }
    } else if (!f && t) {
      const k = `summary->${e.to}`;
      if (!seen.has(k)) {
        seen.add(k);
        out.push({ id: `summary-edge-${k}`, from: CAPPED_SUMMARY_ID, to: e.to, label: "Aggregated flow", layer: e.layer, event_at: e.event_at });
      }
    }
  }
  return { nodes: [...top, summary], edges: out, isCapped: true, hiddenCount: hidden };
}

/**
 * Pure: collapse accounts of the same bank into one node per bank, summing the amounts of the
 * edges between groups. Banks with a single visible account, and banks in `expanded`, stay as
 * individual accounts. Every edge survives (self-edges inside a group are folded into the
 * group's own count so no money silently disappears from the totals).
 */
export function groupByBank(
  nodes: readonly ClusterNode[],
  edges: readonly ClusterEdge[],
  expanded: ReadonlySet<string> = new Set(),
): { nodes: ClusterNode[]; edges: ClusterEdge[] } {
  const byBank = new Map<string, ClusterNode[]>();
  for (const n of nodes) {
    if (n.isSummary) continue;
    const bank = n.bank || "UNKNOWN";
    byBank.set(bank, [...(byBank.get(bank) ?? []), n]);
  }
  const groupOf = new Map<string, string>(); // node id -> group id
  const outNodes: ClusterNode[] = [];
  for (const n of nodes) {
    const bank = n.bank || "UNKNOWN";
    const members = byBank.get(bank) ?? [];
    if (n.isSummary || members.length < 2 || expanded.has(bank)) {
      outNodes.push(n);
      continue;
    }
    const gid = `${BANK_GROUP_PREFIX}${bank}`;
    groupOf.set(n.id, gid);
    if (!outNodes.some((x) => x.id === gid)) {
      const label = `${bank} — ${members.length} accounts`;
      outNodes.push({ id: gid, kind: "account", label, masked_ref: label, account_ref: label, bank, isSummary: false });
    }
  }
  const agg = new Map<string, ClusterEdge>();
  for (const e of edges) {
    const from = groupOf.get(e.from) ?? e.from;
    const to = groupOf.get(e.to) ?? e.to;
    const key = `${from}=>${to}`;
    const prev = agg.get(key);
    if (!prev) {
      agg.set(key, { ...e, id: `g-${key}`, from, to, amount_paise: e.amount_paise ?? 0 });
    } else {
      prev.amount_paise = (prev.amount_paise ?? 0) + (e.amount_paise ?? 0);
      prev.hop_count = (prev.hop_count ?? 1) + (e.hop_count ?? 1);
      prev.layer = Math.min(prev.layer, e.layer);
      if (e.event_at < prev.event_at) prev.event_at = e.event_at;
    }
  }
  return { nodes: outNodes, edges: [...agg.values()] };
}

/** Pure: the whole derivation, in the order filters -> grouping -> cap. */
export function buildGraphView(
  data: { nodes: readonly ClusterNode[]; edges: readonly ClusterEdge[] },
  opts: ViewOptions,
): GraphView {
  const allEdges = data.edges ?? [];
  const kept = allEdges.filter(
    (e) => e.layer <= opts.maxHops && (e.amount_paise ?? 0) >= opts.minAmountPaise,
  );
  const keptSet = new Set(kept);
  const hidden = allEdges.length - kept.length;
  const hiddenPaise = allEdges.reduce((s, e) => s + (keptSet.has(e) ? 0 : e.amount_paise ?? 0), 0);

  // A node that only lost its edges to a filter disappears with them; a node that never had
  // any edge (a genuinely untraced account) stays visible as "isolated".
  const hadEdge = new Set<string>();
  for (const e of allEdges) {
    hadEdge.add(e.from);
    hadEdge.add(e.to);
  }
  const touched = new Set<string>();
  for (const e of kept) {
    touched.add(e.from);
    touched.add(e.to);
  }
  const visibleNodes = (data.nodes ?? []).filter((n) => touched.has(n.id) || !hadEdge.has(n.id));

  let merged = aggregateEdges(kept);
  const thinned = { edges: 0, paise: 0 };
  if ((opts.strongestOnly ?? true) && merged.length > DENSE_EDGES_PER_NODE * Math.max(1, touched.size)) {
    const strong = strongestEdges(merged);
    const strongSet = new Set(strong);
    for (const e of merged) {
      if (!strongSet.has(e)) {
        thinned.edges += 1;
        thinned.paise += e.amount_paise ?? 0;
      }
    }
    merged = strong;
  }
  const grouped = opts.groupByBank
    ? groupByBank(visibleNodes, merged, opts.expandedBanks ?? new Set())
    : { nodes: visibleNodes, edges: merged };
  const capped = capGraph(grouped.nodes, grouped.edges);

  const flow = new Map<string, number>();
  for (const e of capped.edges) {
    flow.set(e.from, (flow.get(e.from) ?? 0) + (e.amount_paise ?? 0));
    flow.set(e.to, (flow.get(e.to) ?? 0) + (e.amount_paise ?? 0));
  }
  return {
    nodes: capped.nodes,
    edges: capped.edges,
    maxFlow: Math.max(0, ...flow.values()),
    hidden: { edges: hidden, paise: hiddenPaise },
    thinned,
    isCapped: capped.isCapped,
    cappedCount: capped.hiddenCount,
    maxLayer: maxLayerOf(allEdges),
    maxAmount: maxAmountPaise(aggregateEdges(allEdges)),
  };
}

/** Pure: does the directed graph contain a cycle? (money cycling back through an earlier account) */
export function hasCycle(edges: readonly ClusterEdge[]): boolean {
  const adj = new Map<string, string[]>();
  for (const e of edges) adj.set(e.from, [...(adj.get(e.from) ?? []), e.to]);
  const state = new Map<string, 0 | 1 | 2>(); // 1 = on stack, 2 = done
  const visit = (id: string): boolean => {
    state.set(id, 1);
    for (const next of adj.get(id) ?? []) {
      const s = state.get(next);
      if (s === 1) return true;
      if (s === undefined && visit(next)) return true;
    }
    state.set(id, 2);
    return false;
  };
  for (const id of adj.keys()) if (state.get(id) === undefined && visit(id)) return true;
  return false;
}

/** Pure: shortest directed hop path from any origin node to `target` (inclusive), or null. */
export function chainFromOrigin(
  edges: readonly ClusterEdge[],
  roles: ReadonlyMap<string, NodeRole>,
  target: string,
): string[] | null {
  const adj = new Map<string, string[]>();
  for (const e of edges) adj.set(e.from, [...(adj.get(e.from) ?? []), e.to]);
  const prev = new Map<string, string | null>();
  const queue: string[] = [];
  for (const [id, r] of roles) {
    if (r === "origin") {
      prev.set(id, null);
      queue.push(id);
    }
  }
  while (queue.length) {
    const cur = queue.shift()!;
    if (cur === target) break;
    for (const next of adj.get(cur) ?? []) {
      if (!prev.has(next)) {
        prev.set(next, cur);
        queue.push(next);
      }
    }
  }
  if (!prev.has(target)) return null;
  const path: string[] = [];
  for (let at: string | null | undefined = target; at; at = prev.get(at)) path.unshift(at);
  return path;
}

export interface NodeStats {
  inDegree: number;
  outDegree: number;
  inPaise: number;
  outPaise: number;
  firstAt: string | null;
  lastAt: string | null;
}

/** Pure: per-account totals for the entity inspector, from the edges already loaded. */
export function nodeStats(edges: readonly ClusterEdge[], id: string): NodeStats {
  const s: NodeStats = { inDegree: 0, outDegree: 0, inPaise: 0, outPaise: 0, firstAt: null, lastAt: null };
  for (const e of edges) {
    if (e.to !== id && e.from !== id) continue;
    if (e.to === id) {
      s.inDegree += 1;
      s.inPaise += e.amount_paise ?? 0;
    }
    if (e.from === id) {
      s.outDegree += 1;
      s.outPaise += e.amount_paise ?? 0;
    }
    if (!s.firstAt || e.event_at < s.firstAt) s.firstAt = e.event_at;
    if (!s.lastAt || e.event_at > s.lastAt) s.lastAt = e.event_at;
  }
  return s;
}

const CSV_HEADERS = ["from", "from_bank", "to", "to_bank", "amount_paise", "hop_layer", "event_at"];

/** Guard against spreadsheet formula injection: a cell that starts with = + - @ is prefixed. */
function csvCell(v: string | number): string {
  let s = String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Pure: the currently visible edges as CSV (labels follow the same masking as the graph). */
export function edgesToCsv(
  nodes: readonly ClusterNode[],
  edges: readonly ClusterEdge[],
  isLea: boolean,
): string {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const ref = (id: string) => {
    const n = byId.get(id);
    if (!n) return id;
    return (isLea ? (n.label ?? n.account_ref ?? n.masked_ref) : (n.label ?? n.masked_ref)) ?? id;
  };
  const rows = edges.map((e) =>
    [
      ref(e.from),
      byId.get(e.from)?.bank ?? "",
      ref(e.to),
      byId.get(e.to)?.bank ?? "",
      e.amount_paise ?? 0,
      e.layer,
      e.event_at,
    ]
      .map(csvCell)
      .join(","),
  );
  return [CSV_HEADERS.join(","), ...rows].join("\n");
}
