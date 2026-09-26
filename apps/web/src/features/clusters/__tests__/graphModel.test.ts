import { describe, it, expect } from "vitest";
import { classifyRoles, maxAmountPaise, toCytoscapeElements, POOLING_MIN_IN_DEGREE } from "../graphModel";
import type { ClusterEdge, ClusterNode } from "../types";

const node = (id: string, extra: Partial<ClusterNode> = {}): ClusterNode => ({
  id,
  kind: "account", // the backend's only kind today
  masked_ref: `XXXX-${id}`,
  bank: "SBIN",
  ...extra,
});
const edge = (from: string, to: string, layer = 1, amount = 1000): ClusterEdge => ({
  from,
  to,
  layer,
  amount_paise: amount,
  event_at: "2026-01-15T10:00:00Z",
});

describe("classifyRoles", () => {
  it("names roles from topology, so real kind='account' data no longer renders as one shape", () => {
    // v -> m1 -> m2 -> atm
    const nodes = ["v", "m1", "m2", "atm"].map((id) => node(id));
    const roles = classifyRoles(nodes, [edge("v", "m1"), edge("m1", "m2", 2), edge("m2", "atm", 3)]);
    expect(roles.get("v")).toBe("origin");
    expect(roles.get("m1")).toBe("pass-through");
    expect(roles.get("m2")).toBe("pass-through");
    expect(roles.get("atm")).toBe("terminal");
    expect(new Set(roles.values()).size).toBeGreaterThan(1);
  });

  it("marks a funnel (>= 3 inbound) as a pooling point, even if it forwards on", () => {
    const nodes = ["a", "b", "c", "hub", "out"].map((id) => node(id));
    const edges = ["a", "b", "c"].map((s) => edge(s, "hub"));
    expect(POOLING_MIN_IN_DEGREE).toBe(3);
    expect(classifyRoles(nodes, [...edges, edge("hub", "out", 2)]).get("hub")).toBe("pooling");
    expect(classifyRoles(nodes, edges).get("hub")).toBe("pooling");
    expect(classifyRoles(nodes, edges.slice(0, 2)).get("hub")).toBe("terminal");
  });

  it("treats an account with no traced hops as isolated, and the cap summary as summary", () => {
    const summary = node("node-capped-summary", { isSummary: true, kind: "summary" });
    const roles = classifyRoles([node("lonely"), summary], [edge("x", "y")]);
    expect(roles.get("lonely")).toBe("isolated");
    expect(roles.get("node-capped-summary")).toBe("summary");
  });

  it("does not claim victim/mule/exit anywhere in its vocabulary", () => {
    const all = new Set(
      classifyRoles([node("a"), node("b")], [edge("a", "b")]).values(),
    );
    for (const r of all) expect(["victim", "mule", "aggregator", "exit"]).not.toContain(r);
  });
});

describe("toCytoscapeElements", () => {
  const nodes = [node("a", { account_ref: "FULL-A" }), node("b")];
  const edges = [edge("a", "b", 1, 5000)];
  const roles = classifyRoles(nodes, edges);
  const speed = new Map<string, number>();

  it("labels with the full ref for LEA roles and the masked ref otherwise", () => {
    const lea = toCytoscapeElements({ nodes, edges, roles, edgeSpeed: speed, isLea: true });
    const non = toCytoscapeElements({ nodes, edges, roles, edgeSpeed: speed, isLea: false });
    expect(lea.find((e) => e.data.id === "a")!.data.label).toBe("FULL-A");
    expect(non.find((e) => e.data.id === "a")!.data.label).toBe("XXXX-a");
  });

  it("carries role on nodes and amount on edges (the two things styling keys off)", () => {
    const els = toCytoscapeElements({ nodes, edges, roles, edgeSpeed: speed, isLea: false });
    expect(els.find((e) => e.data.id === "a")!.data.role).toBe("origin");
    const e = els.find((x) => x.group === "edges")!;
    expect(e.data.amount).toBe(5000);
    expect(e.data.source).toBe("a");
    expect(e.data.target).toBe("b");
  });

  it("maxAmountPaise ignores missing amounts", () => {
    expect(maxAmountPaise([edge("a", "b", 1, 300), { ...edge("b", "c"), amount_paise: undefined }])).toBe(300);
    expect(maxAmountPaise([])).toBe(0);
  });
});

import {
  BANK_GROUP_PREFIX,
  MAX_NODES,
  buildGraphView,
  chainFromOrigin,
  edgesToCsv,
  groupByBank,
  hasCycle,
  nodeStats,
} from "../graphModel";

const bn = (id: string, bank: string): ClusterNode => ({ id, kind: "account", masked_ref: `XXXX-${id}`, bank });
const NONE = { maxHops: Infinity, minAmountPaise: 0, groupByBank: false } as const;

describe("buildGraphView filters", () => {
  const nodes = [bn("a", "SBIN"), bn("b", "SBIN"), bn("c", "HDFC"), bn("d", "HDFC"), bn("solo", "AXIS")];
  const edges = [edge("a", "b", 1, 900_000), edge("b", "c", 2, 50), edge("c", "d", 3, 40)];

  it("hides deep hops and reports exactly how many edges and how many rupees were hidden", () => {
    const v = buildGraphView({ nodes, edges }, { ...NONE, maxHops: 1 });
    expect(v.edges).toHaveLength(1);
    expect(v.hidden).toEqual({ edges: 2, paise: 90 });
    expect(v.maxLayer).toBe(3);
  });

  it("hides micro-dust edges, drops nodes that only lost their edges, keeps genuinely untraced ones", () => {
    const v = buildGraphView({ nodes, edges }, { ...NONE, minAmountPaise: 100 });
    expect(v.edges.map((e) => `${e.from}>${e.to}`)).toEqual(["a>b"]);
    const ids = v.nodes.map((n) => n.id);
    expect(ids).toContain("solo"); // never had an edge: stays as an isolated account
    expect(ids).not.toContain("d"); // only lost its edge to the filter: goes with it
    expect(v.hidden.edges).toBe(2);
  });

  it("with no filters nothing is hidden", () => {
    const v = buildGraphView({ nodes, edges }, NONE);
    expect(v.hidden).toEqual({ edges: 0, paise: 0 });
    expect(v.nodes).toHaveLength(5);
  });
});

describe("groupByBank", () => {
  const nodes = [bn("a", "SBIN"), bn("b", "SBIN"), bn("c", "SBIN"), bn("h", "HDFC")];
  const edges = [edge("a", "h", 1, 100), edge("b", "h", 1, 250), edge("c", "h", 1, 50)];

  it("collapses same-bank accounts into one node and SUMS the edge amounts (no edge dropped)", () => {
    const g = groupByBank(nodes, edges);
    expect(g.nodes.map((n) => n.id).sort()).toEqual([`${BANK_GROUP_PREFIX}SBIN`, "h"].sort());
    expect(g.nodes.find((n) => n.id === `${BANK_GROUP_PREFIX}SBIN`)!.label).toBe("SBIN — 3 accounts");
    expect(g.edges).toHaveLength(1);
    expect(g.edges[0]!.amount_paise).toBe(400);
    const total = edges.reduce((s, e) => s + (e.amount_paise ?? 0), 0);
    expect(g.edges.reduce((s, e) => s + (e.amount_paise ?? 0), 0)).toBe(total);
  });

  it("leaves single-account banks and expanded banks alone", () => {
    expect(groupByBank(nodes, edges, new Set(["SBIN"])).nodes).toHaveLength(4);
    expect(groupByBank(nodes, edges).nodes.some((n) => n.id === "h")).toBe(true);
  });
});

describe("cap, cycles, chains, stats, csv", () => {
  it("caps at MAX_NODES with a summary node and keeps every kept-to-kept edge", () => {
    const many = Array.from({ length: MAX_NODES + 25 }, (_, i) => bn(`n${i}`, "AXIS"));
    const v = buildGraphView({ nodes: many, edges: [edge("n0", "n1"), edge("n0", `n${MAX_NODES + 5}`)] }, NONE);
    expect(v.isCapped).toBe(true);
    expect(v.cappedCount).toBe(25);
    expect(v.nodes).toHaveLength(MAX_NODES + 1);
    expect(v.nodes.at(-1)!.isSummary).toBe(true);
  });

  it("detects a money ring but not a clean cascade", () => {
    expect(hasCycle([edge("a", "b"), edge("b", "c"), edge("c", "a")])).toBe(true);
    expect(hasCycle([edge("a", "b"), edge("b", "c"), edge("a", "c")])).toBe(false);
  });

  it("finds the shortest chain from an origin to a node", () => {
    const nodes = ["v", "m1", "m2", "atm"].map((id) => bn(id, "SBIN"));
    const edges = [edge("v", "m1"), edge("m1", "m2"), edge("v", "m2"), edge("m2", "atm")];
    const roles = classifyRoles(nodes, edges);
    expect(chainFromOrigin(edges, roles, "atm")).toEqual(["v", "m2", "atm"]);
    expect(chainFromOrigin(edges, roles, "nope")).toBeNull();
  });

  it("nodeStats totals are exactly the sum of that node's edges", () => {
    const edges = [edge("a", "m", 1, 300), edge("b", "m", 1, 200), edge("m", "z", 2, 450)];
    edges[0]!.event_at = "2026-01-15T10:05:00Z";
    edges[2]!.event_at = "2026-01-15T11:00:00Z";
    const s = nodeStats(edges, "m");
    expect(s).toMatchObject({ inDegree: 2, outDegree: 1, inPaise: 500, outPaise: 450 });
    expect(s.firstAt).toBe("2026-01-15T10:00:00Z");
    expect(s.lastAt).toBe("2026-01-15T11:00:00Z");
  });

  it("csv escapes commas/quotes and neutralises spreadsheet formulas", () => {
    const nodes = [bn("a", "S,BIN"), { ...bn("b", "HDFC"), masked_ref: "=HYPERLINK(1)" }];
    const csv = edgesToCsv(nodes, [edge("a", "b", 1, 12345)], false);
    const [head, row] = csv.split("\n");
    expect(head).toBe("from,from_bank,to,to_bank,amount_paise,hop_layer,event_at");
    expect(row).toContain('"S,BIN"');
    expect(row).toContain("'=HYPERLINK(1)");
    expect(row).toContain("12345");
  });
});
