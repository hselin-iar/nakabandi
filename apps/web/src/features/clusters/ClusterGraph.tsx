/**
 * ClusterGraph.tsx — Shared Cytoscape.js wrapper for cluster topologies.
 * DOC 3 §S1 & DOC 4 §C6
 *
 * Invariants:
 * - Shared between clusters and cases (imported by CaseDetail, never duplicated).
 * - Caps graph nodes at 200 with a visible "+N more" summary node and alert badge.
 * - Non-LEA principals see only masked account references in node labels.
 * - Node shape encodes TOPOLOGICAL role (see graphModel.ts), because the backend gives every
 *   node kind="account"; colour is not used for it (colour is reserved for severity).
 * - Anything hidden (hop / amount filters, the cap) is announced with its count and amount,
 *   never omitted silently: in a forensic view an unlabeled omission reads as absence of evidence.
 *
 * Layout: dagre, left to right, over the forward edges only; back edges (money returning to an
 * earlier account) are drawn as dashed pink arcs. Parallel hops are merged into one edge (×N).
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import type { Core, EventObject, StylesheetJson } from "cytoscape";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { formatInr } from "../../shared/lib/format";
import { selectionStore } from "../../shared/state/selectionStore";
import { registerDossierActions } from "../../shared/state/dossierActions";
import { ensureCytoscapeExtensions } from "./cytoscapeSetup";
import { TrailScrubber } from "./TrailScrubber";
import { EdgeInspector, NodeInspector } from "./EntityInspector";
import {
  BANK_GROUP_PREFIX,
  ROLE_LABEL,
  buildGraphView,
  chainFromOrigin,
  classifyRoles,
  edgeKey,
  edgesToCsv,
  hasCycle,
  nodeStats,
  toCytoscapeElements,
  type NodeRole,
} from "./graphModel";
import type { ClusterGraphData, ClusterNode, ClusterEdge } from "./types";

interface ClusterGraphProps {
  data: ClusterGraphData;
  onNodeSelect?: (node: ClusterNode | null) => void;
  onEdgeSelect?: (edge: ClusterEdge | null) => void;
  selectedNodeId?: string | null;
  className?: string;
  height?: string | number;
  /** Cluster reference, used only to name exported files. */
  clusterRef?: string;
  /**
   * Timeline playback: edges that happened after this instant (epoch ms) are faded out, so an
   * investigator can scrub the money trail in time. null/undefined shows everything.
   */
  playbackUntilMs?: number | null;
}

export function isLeaRole(role?: string): boolean {
  if (!role) return false;
  return ["state_investigator", "district_officer", "i4c_analyst", "admin"].includes(role);
}

/** Cytoscape needs a canvas; if it cannot start (jsdom, blocked WebGL/canvas) the rest of the view still works. */
class CanvasBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    /* degrade to the accessible node list below */
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

let canvasOk: boolean | null = null;
/** Feature-detect a 2D canvas once (absent in jsdom and some locked-down browsers). */
function canvasAvailable(): boolean {
  if (canvasOk === null) {
    try {
      const c = document.createElement("canvas");
      canvasOk = Boolean(c.getContext && c.getContext("2d"));
    } catch {
      canvasOk = false;
    }
  }
  return canvasOk;
}

// Cytoscape cannot read CSS variables: these hexes mirror the design tokens
// (--nk-surface-elevated, --nk-text-primary/secondary/tertiary, --nk-accent, --nk-canvas-bg).
// Role colours (also used by the legend swatches in tokens.css): green = where the trace starts,
// blue = money passing through, amber = accounts many others feed, red = money stops here.
const ROLE_COLOR = { origin: "#34D399", pass: "#60A5FA", pool: "#F59E0B", term: "#F87171" };
const EDGE_EARLY = "#F97316"; // earliest hops
const EDGE_LATE = "#38BDF8"; // latest hops
const BACK_EDGE = "#F472B6"; // money returning to an earlier account

const STYLE: StylesheetJson = [
  {
    selector: "node",
    style: {
      "background-color": "#161F2E",
      label: "data(short)",
      color: "#E7EAEE",
      "font-size": "10px",
      "font-family": "Inter Variable, system-ui, sans-serif",
      "text-valign": "bottom",
      "text-margin-y": 6,
      "text-background-opacity": 1,
      "text-background-color": "#090D12",
      "text-background-padding": "2px",
      width: 30,
      height: 30,
      "border-width": 3,
      "border-color": "#5D6673",
      shape: "ellipse",
    },
  },
  { selector: 'node[role = "origin"]', style: { shape: "ellipse", "border-color": ROLE_COLOR.origin, "background-color": "#12362B" } },
  { selector: 'node[role = "pass-through"]', style: { shape: "round-rectangle", "border-color": ROLE_COLOR.pass, "background-color": "#14294A" } },
  {
    selector: 'node[role = "pooling"]',
    style: { shape: "diamond", "border-color": ROLE_COLOR.pool, "background-color": "#3A2A0E", width: 42, height: 42 },
  },
  { selector: 'node[role = "terminal"]', style: { shape: "hexagon", "border-color": ROLE_COLOR.term, "background-color": "#3A1A1E", width: 36, height: 36 } },
  {
    selector: "node[?isSummary]",
    style: { "border-color": "#98A2B3", "border-style": "dashed", "border-width": 3, shape: "barrel", width: 44, height: 44, "font-weight": "bold" },
  },
  {
    // a bank group: click it to expand back into its accounts
    selector: `node[id ^= "${BANK_GROUP_PREFIX}"]`,
    style: { "border-style": "double", "border-width": 5, width: 46, height: 46, "font-weight": "bold" },
  },
  { selector: "node:selected", style: { "border-width": 5, "border-color": "#FFFFFF" } },
  {
    selector: "edge",
    style: {
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      "arrow-scale": 1,
      label: "data(label)",
      "font-size": "9px",
      color: "#C7CDD6",
      "text-rotation": "autorotate",
      "text-background-opacity": 1,
      "text-background-color": "#090D12",
      "text-background-padding": "2px",
    },
  },
  {
    // return flow: money coming back to an earlier account. Dashed, pink, and drawn as an arc
    selector: "edge[?back]",
    style: {
      "line-style": "dashed",
      "line-color": BACK_EDGE,
      "target-arrow-color": BACK_EDGE,
      "curve-style": "unbundled-bezier",
      "control-point-distances": [-60],
      "control-point-weights": [0.5],
    },
  },
  { selector: "edge[source = target]", style: { "curve-style": "bezier", "loop-direction": "-45deg", "loop-sweep": "30deg" } },
  { selector: "edge:selected", style: { width: 4, "line-color": "#FFFFFF", "target-arrow-color": "#FFFFFF", opacity: 1 } },
  { selector: ".dim", style: { opacity: 0.15 } },
  { selector: ".future", style: { opacity: 0.08 } },
  {
    selector: ".chain",
    style: { "line-color": "#FFFFFF", "target-arrow-color": "#FFFFFF", "border-color": "#FFFFFF", "border-width": 5, opacity: 1 },
  },
];

export function ClusterGraph({
  data,
  onNodeSelect,
  onEdgeSelect,
  selectedNodeId,
  className = "",
  height = 500,
  clusterRef,
  playbackUntilMs: playbackFromProps,
}: ClusterGraphProps) {
  // The trail scrubber lives inside the graph, so it is present on every page that shows it and
  // in full screen. A caller may still drive playback from outside via `playbackUntilMs`.
  const [playbackState, setPlaybackState] = useState<number | null>(null);
  const playbackUntilMs = playbackFromProps !== undefined ? playbackFromProps : playbackState;
  const cyRef = useRef<Core | null>(null);
  const canvasBoxRef = useRef<HTMLDivElement | null>(null);
  const [selectedNode, setSelectedNode] = useState<ClusterNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<ClusterEdge | null>(null);

  // Noise controls (all client-side, from fields already in the edges)
  const [hopLimit, setHopLimit] = useState<number | null>(null); // null = all hops
  const [minAmount, setMinAmount] = useState(0);
  const [groupBanks, setGroupBanks] = useState(false);
  const [expandedBanks, setExpandedBanks] = useState<ReadonlySet<string>>(new Set());
  const [isolated, setIsolated] = useState(false);
  const [chainIds, setChainIds] = useState<string[] | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [showAllFlows, setShowAllFlows] = useState(false);

  const { principal } = usePrincipal();
  const isLea = isLeaRole(principal?.role);

  ensureCytoscapeExtensions();

  const view = useMemo(
    () =>
      buildGraphView(data, {
        maxHops: hopLimit ?? Infinity,
        minAmountPaise: minAmount,
        groupByBank: groupBanks,
        expandedBanks,
        strongestOnly: !showAllFlows,
      }),
    [data, hopLimit, minAmount, groupBanks, expandedBanks, showAllFlows],
  );
  const { nodes: cappedNodes, edges: cappedEdges, isCapped, cappedCount: hiddenCount } = view;

  const nodeMap = useMemo(() => new Map(cappedNodes.map((n) => [n.id, n])), [cappedNodes]);
  const edgeMap = useMemo(() => new Map(cappedEdges.map((e, i) => [edgeKey(e, i), e])), [cappedEdges]);
  const roles = useMemo(() => classifyRoles(cappedNodes, cappedEdges), [cappedNodes, cappedEdges]);
  const cyclic = useMemo(() => hasCycle(cappedEdges), [cappedEdges]);
  // A ring in the REAL trail (money returning to an earlier account) is a finding worth naming;
  // a loop that only appears because same-bank accounts were folded together is an artifact.
  const realRing = useMemo(
    () =>
      cyclic &&
      (!groupBanks ||
        hasCycle(
          buildGraphView(data, { maxHops: hopLimit ?? Infinity, minAmountPaise: minAmount, groupByBank: false, strongestOnly: !showAllFlows }).edges,
        )),
    [cyclic, groupBanks, data, hopLimit, minAmount, showAllFlows],
  );

  // Where each edge sits in the traced timeline (0 = earliest hop, 1 = latest)
  const { edgeSpeed, timelineSpan } = useMemo(() => {
    let minAt = Infinity;
    let maxAt = -Infinity;
    for (const e of cappedEdges) {
      const t = new Date(e.event_at).getTime();
      if (!Number.isNaN(t)) {
        minAt = Math.min(minAt, t);
        maxAt = Math.max(maxAt, t);
      }
    }
    const span = maxAt > minAt ? maxAt - minAt : 0;
    const speed = new Map<string, number>();
    for (const e of cappedEdges) {
      const t = new Date(e.event_at).getTime();
      speed.set(e.id || `${e.from}-${e.to}`, span > 0 && !Number.isNaN(t) ? (t - minAt) / span : 0);
    }
    return { edgeSpeed: speed, timelineSpan: span };
  }, [cappedEdges]);

  const elements = useMemo(
    () => toCytoscapeElements({ nodes: cappedNodes, edges: cappedEdges, roles, edgeSpeed, isLea }),
    [cappedNodes, cappedEdges, roles, edgeSpeed, isLea],
  );

  // Edge width by amount and brightness by tempo, in the same stylesheet as the static rules
  const stylesheet = useMemo<StylesheetJson>(
    () => [
      ...STYLE,
      {
        selector: "edge",
        style: {
          width: view.maxAmount > 0 ? `mapData(amount, 0, ${view.maxAmount}, 1.5, 8)` : 2,
          "line-color": `mapData(speedT, 0, 1, ${EDGE_EARLY}, ${EDGE_LATE})`,
          "target-arrow-color": `mapData(speedT, 0, 1, ${EDGE_EARLY}, ${EDGE_LATE})`,
        },
      },
      // back edges keep their own colour (declared after the tempo ramp so it wins)
      { selector: "edge[?back]", style: { "line-color": BACK_EDGE, "target-arrow-color": BACK_EDGE } },
      ...(view.maxFlow > 0
        ? ([
            {
              selector: "node[role != 'pooling'][role != 'terminal'][!isSummary]",
              style: { width: `mapData(flow, 0, ${view.maxFlow}, 26, 44)`, height: `mapData(flow, 0, ${view.maxFlow}, 26, 44)` },
            },
          ] as StylesheetJson)
        : []),
    ],
    [view.maxAmount, view.maxFlow],
  );

  // Layered left-to-right layout over the FORWARD edges only (see computeDepths): back edges are
  // drawn on top as dashed arcs, so a ring never makes dagre reverse an edge behind our back.
  const layoutKey = useMemo(() => elements.map((el) => el.data.id).join("|"), [elements]);
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || cy.destroyed()) return;
    const timer = window.setTimeout(() => {
      if (cy.destroyed()) return;
      cy.nodes().union(cy.edges("[!back]")).layout({
        name: "dagre",
        rankDir: "LR",
        nodeSep: 36,
        rankSep: 110,
        edgeSep: 20,
        ranker: "network-simplex",
        animate: false,
        fit: true,
        padding: 40,
      } as never).run();
      cy.fit(undefined, 40);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [layoutKey]);

  // Selected-node derived facts
  const selectedRole = (selectedNode ? roles.get(selectedNode.id) : undefined) ?? "isolated";
  const selectedStats = useMemo(
    () => (selectedNode ? nodeStats(cappedEdges, selectedNode.id) : null),
    [selectedNode, cappedEdges],
  );
  const selectedChain = useMemo(
    () => (selectedNode ? chainFromOrigin(cappedEdges, roles, selectedNode.id) : null),
    [selectedNode, cappedEdges, roles],
  );

  const clearSelection = useCallback(() => {
    setSelectedNode(null);
    setSelectedEdge(null);
    setIsolated(false);
    setChainIds(null);
    onNodeSelect?.(null);
    onEdgeSelect?.(null);
  }, [onNodeSelect, onEdgeSelect]);

  // Wire events once per Cytoscape instance
  const handleCy = useCallback(
    (cy: Core) => {
      if (cyRef.current === cy) return;
      cyRef.current = cy;
      cy.on("tap", "node", (evt: EventObject) => {
        const id = evt.target.id() as string;
        if (id.startsWith(BANK_GROUP_PREFIX)) {
          // expand this bank back into its individual accounts
          setExpandedBanks((prev) => new Set(prev).add(id.slice(BANK_GROUP_PREFIX.length)));
          return;
        }
        const node = nodeMapRef.current.get(id) || null;
        setSelectedNode(node);
        setSelectedEdge(null);
        setChainIds(null);
        onNodeSelectRef.current?.(node);
        if (node && !node.isSummary) selectionStore.set({ kind: "account", id: node.id });
      });
      cy.on("tap", "edge", (evt: EventObject) => {
        const edge = edgeMapRef.current.get(evt.target.id() as string) || null;
        setSelectedEdge(edge);
        setSelectedNode(null);
        onEdgeSelectRef.current?.(edge);
      });
      cy.on("tap", (evt: EventObject) => {
        if (evt.target === cy) clearSelectionRef.current();
      });
    },
    [],
  );

  // Latest callbacks/maps for the once-bound handlers (avoids stale closures)
  const nodeMapRef = useRef(nodeMap);
  const edgeMapRef = useRef(edgeMap);
  const onNodeSelectRef = useRef(onNodeSelect);
  const onEdgeSelectRef = useRef(onEdgeSelect);
  const clearSelectionRef = useRef(clearSelection);
  nodeMapRef.current = nodeMap;
  edgeMapRef.current = edgeMap;
  onNodeSelectRef.current = onNodeSelect;
  onEdgeSelectRef.current = onEdgeSelect;
  clearSelectionRef.current = clearSelection;

  // Full screen: a fixed overlay (works everywhere, unlike the Fullscreen API on some embeds);
  // Escape leaves it, and the canvas is resized and refitted whenever the size changes.
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [fullscreen]);
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || cy.destroyed()) return;
    const t = window.setTimeout(() => {
      cy.resize();
      cy.fit(undefined, 40);
    }, 50);
    return () => window.clearTimeout(t);
  }, [fullscreen]);

  // Keep Cytoscape's canvas in step with its box (window resize, leaving full screen, side panels)
  useEffect(() => {
    const box = canvasBoxRef.current;
    if (!box || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      const cy = cyRef.current;
      if (cy && !cy.destroyed()) cy.resize();
    });
    ro.observe(box);
    return () => ro.disconnect();
  }, []);

  // Isolate the trail: dim everything that is neither upstream nor downstream of the selection
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("dim");
      if (isolated && selectedNode) {
        const n = cy.getElementById(selectedNode.id);
        if (n.nonempty()) {
          const keep = n.union(n.predecessors()).union(n.successors());
          cy.elements().difference(keep).addClass("dim");
        }
      }
    });
  }, [isolated, selectedNode, elements]);

  // Highlight the hop chain from an origin
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("chain");
      if (chainIds && chainIds.length > 1) {
        for (let i = 0; i < chainIds.length; i++) {
          cy.getElementById(chainIds[i]!).addClass("chain");
          if (i > 0) cy.edges(`[source = "${chainIds[i - 1]}"][target = "${chainIds[i]}"]`).addClass("chain");
        }
      }
    });
  }, [chainIds, elements]);

  // Timeline playback: fade out what has not happened yet
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("future");
      if (playbackUntilMs == null) return;
      cy.edges().forEach((e) => {
        const at = edgeMapRef.current.get(e.id())?.event_at;
        if (at && new Date(at).getTime() > playbackUntilMs) e.addClass("future");
      });
      // a node is "not yet reached" when every edge touching it is still in the future
      cy.nodes().forEach((n) => {
        const touching = n.connectedEdges();
        if (touching.nonempty() && touching.not(".future").empty()) n.addClass("future");
      });
    });
  }, [playbackUntilMs, elements]);

  // External selection
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    if (selectedNodeId) cy.getElementById(selectedNodeId).select();
    else cy.nodes().unselect();
  }, [selectedNodeId]);

  // ---- export (a working copy, never the evidence pack) ----
  const stamp = () => new Date().toISOString().replace(/[:.]/g, "-");
  const download = (href: string, name: string) => {
    const a = document.createElement("a");
    a.href = href;
    a.download = name;
    a.click();
  };
  const exportPng = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    download(cy.png({ full: true, bg: "#090D12", scale: 2 }), `working-copy-${clusterRef ?? "cluster"}-${stamp()}.png`);
  }, [clusterRef]);
  const exportCsv = useCallback(() => {
    const url = URL.createObjectURL(new Blob([edgesToCsv(cappedNodes, cappedEdges, isLea)], { type: "text/csv" }));
    download(url, `working-copy-${clusterRef ?? "cluster"}-${stamp()}.csv`);
    URL.revokeObjectURL(url);
  }, [cappedNodes, cappedEdges, isLea, clusterRef]);

  // Publish dossier commands for the command palette while this graph is mounted
  const actionsRef = useRef({ exportPng, exportCsv, selected: selectedNode });
  actionsRef.current = { exportPng, exportCsv, selected: selectedNode };
  useEffect(
    () =>
      registerDossierActions({
        maxHop: view.maxLayer,
        showHopsUpTo: (hop) => setHopLimit(hop >= view.maxLayer ? null : Math.max(1, hop)),
        isolateSelected: () => setIsolated((v) => !v),
        hasSelection: () => actionsRef.current.selected !== null,
        exportPng: () => actionsRef.current.exportPng(),
        exportCsv: () => actionsRef.current.exportCsv(),
      }),
    [view.maxLayer],
  );

  const resetFilters = () => {
    setHopLimit(null);
    setMinAmount(0);
  };
  const anyHidden = view.hidden.edges > 0;
  const amountStep = Math.max(1, Math.floor(view.maxAmount / 100));

  return (
    <div
      className={`nk-cluster-graph ${className}`}
      data-testid="cluster-graph-container"
      style={
        fullscreen
          ? { position: "fixed", inset: 0, zIndex: 1000, width: "100vw", height: "100vh", background: "var(--nk-canvas-bg)", padding: 12 }
          : { position: "relative", width: "100%", height }
      }
      data-fullscreen={fullscreen || undefined}
    >
      {/* Noise controls: what is shown, and an explicit count of what is not */}
      <div className="nk-graph-toolbar nk-graph-toolbar--flow" role="toolbar" aria-label="Graph controls">
        {view.maxLayer > 1 && (
          <label className="nk-graph-toolbar__item">
            <span>Hops ≤ <b className="data-digit">{hopLimit ?? view.maxLayer}</b></span>
            <input
              type="range"
              min={1}
              max={view.maxLayer}
              value={hopLimit ?? view.maxLayer}
              aria-label="Hop depth limit"
              onChange={(e) => {
                const n = Number(e.target.value);
                setHopLimit(n >= view.maxLayer ? null : n);
              }}
            />
          </label>
        )}
        {view.maxAmount > 0 && (
          <label className="nk-graph-toolbar__item">
            <span>Min amount <b className="data-digit">{formatInr(minAmount, { compact: true })}</b></span>
            <input
              type="range"
              min={0}
              max={view.maxAmount}
              step={amountStep}
              value={minAmount}
              aria-label="Minimum amount"
              onChange={(e) => setMinAmount(Number(e.target.value))}
            />
          </label>
        )}
        <button
          type="button"
          className="nk-btn nk-btn--ghost nk-btn--sm"
          aria-pressed={groupBanks}
          onClick={() => {
            setGroupBanks((g) => !g);
            setExpandedBanks(new Set());
          }}
        >
          Group by bank
        </button>
        <span className="nk-graph-toolbar__sep" />
        <button type="button" className="nk-btn nk-btn--ghost nk-btn--sm" onClick={exportPng} title="Working copy — not the evidence pack">
          PNG
        </button>
        <button type="button" className="nk-btn nk-btn--ghost nk-btn--sm" onClick={exportCsv} title="Working copy — not the evidence pack">
          CSV
        </button>
        <button type="button" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 1.25)} title="Zoom In" aria-label="Zoom in" className="nk-btn nk-btn--secondary nk-btn--sm">+</button>
        <button type="button" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() * 0.8)} title="Zoom Out" aria-label="Zoom out" className="nk-btn nk-btn--secondary nk-btn--sm">-</button>
        <button
          type="button"
          onClick={() => setFullscreen((f) => !f)}
          aria-pressed={fullscreen}
          title={fullscreen ? "Exit full screen (Esc)" : "Full screen"}
          aria-label={fullscreen ? "Exit full screen" : "View graph full screen"}
          className="nk-btn nk-btn--secondary nk-btn--sm"
        >
          {fullscreen ? "Exit full screen" : "Full screen"}
        </button>
        <button type="button" onClick={() => cyRef.current?.fit(undefined, 30)} title="Fit to View" aria-label="Fit graph to view" className="nk-btn nk-btn--secondary nk-btn--sm">Fit</button>
      </div>

      {playbackFromProps === undefined && (
        <TrailScrubber edges={data.edges ?? []} value={playbackState} onChange={setPlaybackState} />
      )}

      <div className="nk-graph-notices">
      {isCapped && (
        <div className="nk-graph-notice" data-testid="node-capped-badge" role="status">
          <span>Graph capped: Showing top 200 nodes (+{hiddenCount} more accounts summarized)</span>
        </div>
      )}

      {view.thinned.edges > 0 && (
        <button
          type="button"
          className="nk-graph-hidden"
          data-testid="thinned-edges-notice"
          onClick={() => setShowAllFlows(true)}
        >
          Showing the strongest flows · {view.thinned.edges} weaker {view.thinned.edges === 1 ? "flow" : "flows"} ({formatInr(view.thinned.paise, { compact: true })}) set aside · show all
        </button>
      )}
      {showAllFlows && cappedEdges.length > 3 * Math.max(1, cappedNodes.length) && (
        <button type="button" className="nk-graph-hidden" data-testid="thin-again" onClick={() => setShowAllFlows(false)}>
          Showing every flow · thin to strongest
        </button>
      )}

      {anyHidden && (
        <button type="button" className="nk-graph-hidden" data-testid="hidden-edges-notice" onClick={resetFilters}>
          {view.hidden.edges} {view.hidden.edges === 1 ? "edge" : "edges"} hidden ({formatInr(view.hidden.paise, { compact: true })}) in loaded data · show all
        </button>
      )}

      </div>

      {/* Main Cytoscape canvas */}
      <div
        ref={canvasBoxRef}
        data-testid="cytoscape-canvas"
        style={{ position: "relative", width: "100%", flex: "1 1 0", minHeight: 0, minWidth: 0, background: "var(--nk-canvas-bg)", borderRadius: 8, overflow: "hidden" }}
      >
        <CanvasBoundary>
          {canvasAvailable() && (
          <CytoscapeComponent
            elements={elements}
            stylesheet={stylesheet}
            cy={handleCy}
            // absolutely positioned: the canvas' own pixel size must never widen its parent
            // (it used to keep the full-screen width after leaving full screen)
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
            minZoom={0.2}
            maxZoom={3}
          />
          )}
        </CanvasBoundary>
      </div>

      {/* Hidden semantic representation for accessibility & testing in JSDOM environments */}
      <div className="sr-only" data-testid="graph-nodes-list" aria-label="Graph nodes listing">
        {cappedNodes.map((n) => (
          <div
            key={n.id}
            data-testid={`graph-node-${n.id}`}
            data-kind={n.kind}
            data-role={roles.get(n.id)}
            data-is-summary={n.isSummary ? "true" : "false"}
            data-ref={isLea ? (n.account_ref || n.masked_ref) : n.masked_ref}
          >
            {n.isSummary ? n.label : isLea ? (n.label || n.account_ref || n.masked_ref) : (n.label || n.masked_ref)}
          </div>
        ))}
      </div>

      {/* Legends stack bottom-left in one container so they can never overlap */}
      <div className="nk-graph-legends">
        <div className="nk-graph-legend">
          <span><i className="nk-shape nk-shape--origin" />{ROLE_LABEL.origin}</span>
          <span><i className="nk-shape nk-shape--pass" />{ROLE_LABEL["pass-through"]}</span>
          <span><i className="nk-shape nk-shape--pool" />{ROLE_LABEL.pooling}</span>
          <span><i className="nk-shape nk-shape--term" />{ROLE_LABEL.terminal}</span>
          {isCapped && <span><i className="nk-shape nk-shape--cap" />+N More</span>}
          {cyclic && realRing && <span><i className="nk-shape nk-shape--back" />Ring: money returns to an earlier account</span>}
          {cyclic && !realRing && <span><i className="nk-shape nk-shape--back" />Bank grouping folds accounts together, so arrows can loop back</span>}
        </div>
        {timelineSpan > 0 && (
          <div className="nk-graph-legend">
            <span>Money flows →</span>
            <span className="nk-graph-legend__ramp" />
            <span>earliest hop → latest · thickness = amount · ×N = merged transfers</span>
          </div>
        )}
      </div>

      {selectedNode && selectedStats && (
        <NodeInspector
          node={selectedNode}
          role={selectedRole as NodeRole}
          stats={selectedStats}
          chain={selectedChain}
          isLea={isLea}
          hiddenCount={hiddenCount}
          isolated={isolated}
          onIsolate={() => setIsolated((v) => !v)}
          onHighlightChain={() => setChainIds((c) => (c ? null : selectedChain))}
          onClose={clearSelection}
        />
      )}
      {selectedEdge && <EdgeInspector edge={selectedEdge} onClose={() => setSelectedEdge(null)} />}
    </div>
  );
}
