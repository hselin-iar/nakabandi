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
