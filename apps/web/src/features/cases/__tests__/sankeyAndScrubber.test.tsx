import { describe, it, expect, afterEach, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { buildSankey } from "../sankeyModel";
import { CaseTimelineScrubber, timeBounds } from "../CaseTimelineScrubber";
import type { ClusterEdge, ClusterNode } from "../../clusters/types";

afterEach(cleanup);

const n = (id: string, bank: string): ClusterNode => ({ id, kind: "account", masked_ref: id, bank });
const e = (from: string, to: string, layer: number, amount: number, at = "2026-01-15T10:00:00Z"): ClusterEdge => ({
  from,
  to,
  layer,
  amount_paise: amount,
  event_at: at,
});

describe("buildSankey", () => {
  it("aggregates flows by (bank, hop column) and conserves the total drawn amount", () => {
    const nodes = [n("v1", "SBIN"), n("v2", "SBIN"), n("m", "HDFC"), n("atm", "AXIS")];
    const edges = [e("v1", "m", 1, 300), e("v2", "m", 1, 200), e("m", "atm", 2, 450)];
    const s = buildSankey(nodes, edges);
    expect(s.omitted).toEqual({ edges: 0, paise: 0 });
    // the two SBIN victims collapse to one SBIN@0 -> HDFC@1 link carrying 500
    const total = s.links.reduce((sum, l) => sum + l.value, 0);
    expect(total).toBe(300 + 200 + 450);
    expect(s.links).toHaveLength(2);
    expect(s.links.find((l) => l.value === 500)).toBeTruthy();
    // every link runs from an earlier column to a later one (acyclic)
    for (const l of s.links) expect(s.nodes[l.source]!.column).toBeLessThan(s.nodes[l.target]!.column);
  });

  it("reports, rather than drops, an edge that returns money to an earlier account", () => {
    const nodes = [n("a", "SBIN"), n("b", "HDFC"), n("c", "AXIS")];
    const edges = [e("a", "b", 1, 100), e("b", "c", 2, 100), e("c", "a", 3, 70)];
    const s = buildSankey(nodes, edges);
    expect(s.omitted).toEqual({ edges: 1, paise: 70 });
  });

  it("ignores zero-amount edges", () => {
    expect(buildSankey([n("a", "X"), n("b", "Y")], [e("a", "b", 1, 0)]).links).toHaveLength(0);
  });
});

describe("CaseTimelineScrubber", () => {
  const edges = [e("a", "b", 1, 1, "2026-01-15T10:00:00Z"), e("b", "c", 2, 1, "2026-01-15T11:00:00Z")];

  it("computes the bounds of the trail and hides itself when there is no time span", () => {
    expect(timeBounds(edges)).toEqual({ min: Date.parse("2026-01-15T10:00:00Z"), max: Date.parse("2026-01-15T11:00:00Z") });
    const { container } = render(<CaseTimelineScrubber edges={[edges[0]!]} value={null} onChange={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("scrubbing sets a cutoff and 'Show all' clears it", () => {
    const onChange = vi.fn();
    const mid = Date.parse("2026-01-15T10:30:00Z");
    const { rerender } = render(<CaseTimelineScrubber edges={edges} value={null} onChange={onChange} />);
    expect(screen.getByText("All hops")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Trail playback position"), { target: { value: String(mid) } });
    expect(onChange).toHaveBeenLastCalledWith(mid);
    rerender(<CaseTimelineScrubber edges={edges} value={mid} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Show all" }));
    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});
