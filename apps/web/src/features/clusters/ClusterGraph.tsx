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
 */

import React, { useEffect, useRef, useState, useMemo } from "react";
import cytoscape from "cytoscape";
import type { Core, EventObject, NodeSingular } from "cytoscape";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { formatInr } from "../../shared/lib/format";
import { selectionStore } from "../../shared/state/selectionStore";
import type { ClusterGraphData, ClusterNode, ClusterEdge } from "./types";
import {
  ROLE_LABEL,
  classifyRoles,
  maxAmountPaise,
  toCytoscapeElements,
  type NodeRole,
} from "./graphModel";

interface ClusterGraphProps {
  data: ClusterGraphData;
  onNodeSelect?: (node: ClusterNode | null) => void;
  onEdgeSelect?: (edge: ClusterEdge | null) => void;
  selectedNodeId?: string | null;
  className?: string;
  height?: string | number;
}

const MAX_NODES = 200;

export function isLeaRole(role?: string): boolean {
  if (!role) return false;
  return [
    "state_investigator",
    "district_officer",
    "i4c_analyst",
    "admin",
  ].includes(role);
}

export function ClusterGraph({
  data,
  onNodeSelect,
  onEdgeSelect,
  selectedNodeId,
  className = "",
  height = 500,
}: ClusterGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<ClusterNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<ClusterEdge | null>(null);

  const { principal } = usePrincipal();
  const isLea = isLeaRole(principal?.role);

  // ---------------------------------------------------------------------------
  // Node Capping Logic (DOC 4 §C6: cap at 200 nodes with a "+N more" node)
  // ---------------------------------------------------------------------------
  const { cappedNodes, cappedEdges, isCapped, hiddenCount } = useMemo(() => {
    if (!data.nodes || data.nodes.length === 0) {
      return { cappedNodes: [], cappedEdges: [], isCapped: false, hiddenCount: 0 };
    }

    if (data.nodes.length <= MAX_NODES) {
      return {
        cappedNodes: data.nodes,
        cappedEdges: data.edges || [],
        isCapped: false,
        hiddenCount: 0,
      };
    }

    // Sort nodes to preserve most significant entities (aggregators, victims, high volume)
    const priorityScore = (n: ClusterNode) => {
      let score = n.amount_paise ?? 0;
      if (n.kind === "aggregator") score += 10_000_000_00;
      if (n.kind === "exit") score += 5_000_000_00;
      if (n.kind === "victim") score += 2_000_000_00;
      return score;
    };

    const sorted = [...data.nodes].sort((a, b) => priorityScore(b) - priorityScore(a));
    const topNodes = sorted.slice(0, MAX_NODES);
    const hidden = data.nodes.length - MAX_NODES;

    const keptIds = new Set(topNodes.map((n) => n.id));

    // Summary node representing capped accounts
    const summaryNode: ClusterNode = {
      id: "node-capped-summary",
      kind: "summary",
      label: `+${hidden} more accounts`,
      masked_ref: `+${hidden} more accounts`,
      account_ref: `+${hidden} more accounts`,
      bank: "VARIOUS",
      isSummary: true,
    };

    const resultNodes = [...topNodes, summaryNode];

    // Filter and remap edges
    const resultEdges: ClusterEdge[] = [];
    const edgeIdSet = new Set<string>();

    for (const edge of data.edges || []) {
      const fromKept = keptIds.has(edge.from);
      const toKept = keptIds.has(edge.to);

      if (fromKept && toKept) {
        resultEdges.push(edge);
      } else if (fromKept && !toKept) {
        const edgeKey = `${edge.from}->summary`;
        if (!edgeIdSet.has(edgeKey)) {
          edgeIdSet.add(edgeKey);
          resultEdges.push({
            id: `summary-edge-${edgeKey}`,
            from: edge.from,
            to: "node-capped-summary",
            label: "Aggregated flow",
            layer: edge.layer,
            event_at: edge.event_at,
          });
        }
      } else if (!fromKept && toKept) {
        const edgeKey = `summary->${edge.to}`;
        if (!edgeIdSet.has(edgeKey)) {
          edgeIdSet.add(edgeKey);
          resultEdges.push({
            id: `summary-edge-${edgeKey}`,
            from: "node-capped-summary",
            to: edge.to,
            label: "Aggregated flow",
            layer: edge.layer,
            event_at: edge.event_at,
          });
        }
      }
    }

    return {
      cappedNodes: resultNodes,
      cappedEdges: resultEdges,
      isCapped: true,
      hiddenCount: hidden,
    };
  }, [data.nodes, data.edges]);

  // Lookup map for fast lookup on click
  const nodeMap = useMemo(() => {
    const map = new Map<string, ClusterNode>();
    for (const node of cappedNodes) {
      map.set(node.id, node);
    }
    return map;
  }, [cappedNodes]);

  const roles = useMemo(() => classifyRoles(cappedNodes, cappedEdges), [cappedNodes, cappedEdges]);
  const maxAmount = useMemo(() => maxAmountPaise(cappedEdges), [cappedEdges]);

  const edgeMap = useMemo(() => {
    const map = new Map<string, ClusterEdge>();
    for (const edge of cappedEdges) {
      const id = edge.id || `${edge.from}-${edge.to}`;
      map.set(id, edge);
    }
    return map;
  }, [cappedEdges]);

  // ---------------------------------------------------------------------------
  // Fund-flow directed timeline (§4.4, §7.4): order nodes left-to-right by
  // FundHop.layer instead of a force-directed blob, and colour/weight edges by
  // how early they happened relative to the cluster's first traced hop — tempo,
  // not just topology, is the actual differentiator (DOC1: layering is instant,
  // cash-out is the physical bottleneck).
  // ---------------------------------------------------------------------------
  const { nodeColumn, edgeSpeed, timelineSpan } = useMemo(() => {
    const column = new Map<string, number>();
    for (const e of cappedEdges) {
      const existing = column.get(e.to);
      if (existing === undefined || e.layer < existing) column.set(e.to, e.layer);
      if (!column.has(e.from)) column.set(e.from, Math.max(0, e.layer - 1));
    }

    let minAt = Infinity;
    let maxAt = -Infinity;
    for (const e of cappedEdges) {
      const t = new Date(e.event_at).getTime();
      if (!Number.isNaN(t)) {
        if (t < minAt) minAt = t;
        if (t > maxAt) maxAt = t;
      }
    }
    const span = maxAt > minAt ? maxAt - minAt : 0;

    const speed = new Map<string, number>();
    for (const e of cappedEdges) {
      const id = e.id || `${e.from}-${e.to}`;
      const t = new Date(e.event_at).getTime();
      speed.set(id, span > 0 && !Number.isNaN(t) ? (t - minAt) / span : 0);
    }

    return { nodeColumn: column, edgeSpeed: speed, timelineSpan: span };
  }, [cappedEdges]);

  // Preset positions: column from nodeColumn (0 for anything untouched by an edge, e.g. a
  // singleton account or the capped-summary node), row = index within that column.
  const nodePositions = useMemo(() => {
    const columnCounts = new Map<number, number>();
    const positions = new Map<string, { x: number; y: number }>();
    const COL_WIDTH = 160;
    const ROW_HEIGHT = 70;

    for (const n of cappedNodes) {
      const col = n.isSummary
        ? (Math.max(0, ...Array.from(nodeColumn.values())) + 1)
        : (nodeColumn.get(n.id) ?? 0);
      const row = columnCounts.get(col) ?? 0;
      columnCounts.set(col, row + 1);
      positions.set(n.id, { x: col * COL_WIDTH, y: row * ROW_HEIGHT });
    }
    return positions;
  }, [cappedNodes, nodeColumn]);

  // ---------------------------------------------------------------------------
  // Cytoscape initialization and updates
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current) return;

    const elements = toCytoscapeElements({
      nodes: cappedNodes,
      edges: cappedEdges,
      roles,
      edgeSpeed,
      isLea,
    });

    try {
      if (cyRef.current) {
        cyRef.current.destroy();
      }

      const cy = cytoscape({
        container: containerRef.current,
        elements: elements,
        style: [
          {
            // Default: an isolated account (no traced hops): plain circle. Cytoscape cannot read
            // CSS variables, so these hexes mirror the tokens (--nk-surface-elevated, --nk-text-*).
            selector: "node",
            style: {
              "background-color": "#161F2E",
              label: "data(label)",
              color: "#E7EAEE",
              "font-size": "11px",
              "font-family": "Inter Variable, system-ui, sans-serif",
              "text-valign": "bottom",
              "text-margin-y": 6,
              width: 32,
              height: 32,
              "border-width": 2,
              "border-color": "#5D6673",
              shape: "ellipse",
            },
          },
          { selector: 'node[role = "origin"]', style: { shape: "ellipse", "border-color": "#E7EAEE", "border-width": 3 } },
          { selector: 'node[role = "pass-through"]', style: { shape: "round-rectangle", "border-color": "#98A2B3" } },
          {
            selector: 'node[role = "pooling"]',
            style: { shape: "diamond", "border-color": "#E7EAEE", "background-color": "#2A3548", width: 40, height: 40 },
          },
          { selector: 'node[role = "terminal"]', style: { shape: "hexagon", "border-color": "#98A2B3", width: 36, height: 36 } },
          {
            selector: "node[?isSummary]",
            style: {
              "border-color": "#98A2B3",
              "border-style": "dashed",
              "border-width": 3,
              shape: "barrel",
              width: 44,
              height: 44,
              "font-weight": "bold",
            },
          },
          { selector: "node:selected", style: { "border-width": 4, "border-color": "#38BDF8" } },
          {
            // Width by amount moved (paise), colour by tempo: earlier hops bright, later hops dim.
            selector: "edge",
            style: {
              width: maxAmount > 0 ? `mapData(amount, 0, ${maxAmount}, 1.5, 8)` : 2,
              "line-color": "mapData(speedT, 0, 1, #E7EAEE, #5D6673)",
              "target-arrow-color": "mapData(speedT, 0, 1, #E7EAEE, #5D6673)",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              "arrow-scale": 1.2,
              label: "data(label)",
              "font-size": "9px",
              color: "#98A2B3",
              "text-rotation": "autorotate",
              "text-background-opacity": 0.8,
              "text-background-color": "#090D12",
              "text-background-padding": "2px",
            },
          },
          {
            selector: "edge:selected",
            style: { width: 4, "line-color": "#38BDF8", "target-arrow-color": "#38BDF8" },
          },
        ],
        layout: {
          // Ordered left-to-right by FundHop.layer (nodePositions), not a force-directed
          // blob or a BFS-computed depth — the domain's own hop depth, directly (§4.4, §7.4).
          name: "preset",
          positions: (node: NodeSingular) =>
            nodePositions.get(node.id()) ?? { x: 0, y: 0 },
          fit: true,
          padding: 30,
        } as cytoscape.LayoutOptions,
      });

      cy.on("tap", "node", (evt: EventObject) => {
        const id = evt.target.id();
        const node = nodeMap.get(id) || null;
        setSelectedNode(node);
        setSelectedEdge(null);
        onNodeSelect?.(node);
        if (node && !node.isSummary) selectionStore.set({ kind: "account", id: node.id });
      });

      cy.on("tap", "edge", (evt: EventObject) => {
        const id = evt.target.id();
        const edge = edgeMap.get(id) || null;
        setSelectedEdge(edge);
        setSelectedNode(null);
        onEdgeSelect?.(edge);
      });

      cy.on("tap", (evt: EventObject) => {
        if (evt.target === cy) {
          setSelectedNode(null);
          setSelectedEdge(null);
          onNodeSelect?.(null);
          onEdgeSelect?.(null);
        }
      });

      cyRef.current = cy;
    } catch {
      // In headless or test environments where canvas is missing, Cytoscape degrades gracefully
    }

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [
    cappedNodes,
    cappedEdges,
    isLea,
    nodeMap,
    edgeMap,
    edgeSpeed,
    nodePositions,
    roles,
    maxAmount,
    onNodeSelect,
    onEdgeSelect,
  ]);

  // Update selection externally if selectedNodeId changes
  useEffect(() => {
    if (!cyRef.current) return;
    if (selectedNodeId) {
      cyRef.current.$(`node#${selectedNodeId}`).select();
    } else {
      cyRef.current.nodes().unselect();
    }
  }, [selectedNodeId]);

  const handleZoomIn = () => {
    cyRef.current?.zoom(cyRef.current.zoom() * 1.25);
  };

  const handleZoomOut = () => {
    cyRef.current?.zoom(cyRef.current.zoom() * 0.8);
  };

  const handleFit = () => {
    cyRef.current?.fit(undefined, 30);
  };

  return (
    <div
      className={`nk-cluster-graph ${className}`}
      data-testid="cluster-graph-container"
      style={{ position: "relative", width: "100%", height }}
    >
      {/* Capping notice banner */}
      {isCapped && (
        <div
          className="nk-cluster-graph__cap-badge"
          data-testid="node-capped-badge"
          role="status"
          style={{
            position: "absolute",
            top: 12,
            left: 12,
            zIndex: 10,
            background: "rgba(9, 13, 18, 0.9)",
            border: "1px solid var(--nk-border-strong)",
            color: "var(--nk-text-primary)",
            padding: "6px 12px",
            borderRadius: 6,
            fontSize: "12px",
            fontWeight: 600,
            boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
                    <span>
            Graph capped: Showing top 200 nodes (+{hiddenCount} more accounts summarized)
          </span>
        </div>
      )}

      {/* Graph Toolbar Controls */}
      <div
        className="nk-cluster-graph__controls"
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          zIndex: 10,
          display: "flex",
          gap: 6,
          background: "rgba(9, 13, 18, 0.88)",
          padding: 4,
          borderRadius: 6,
          border: "1px solid var(--nk-border-strong)",
        }}
      >
        <button
          type="button"
          onClick={handleZoomIn}
          title="Zoom In"
          aria-label="Zoom in"
          className="nk-btn nk-btn--secondary nk-btn--sm"
          style={{ minWidth: 32, padding: "4px 8px" }}
        >
          +
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          title="Zoom Out"
          aria-label="Zoom out"
          className="nk-btn nk-btn--secondary nk-btn--sm"
          style={{ minWidth: 32, padding: "4px 8px" }}
        >
          -
        </button>
        <button
          type="button"
          onClick={handleFit}
          title="Fit to View"
          aria-label="Fit graph to view"
          className="nk-btn nk-btn--secondary nk-btn--sm"
          style={{ padding: "4px 10px", fontSize: "11px" }}
        >
          Fit
        </button>
      </div>

      {/* Main Cytoscape canvas container */}
      <div
        ref={containerRef}
        data-testid="cytoscape-canvas"
        style={{
          width: "100%",
          height: "100%",
          background: "var(--nk-canvas-bg)",
          borderRadius: 8,
          overflow: "hidden",
        }}
      />

      {/* Hidden semantic representation for accessibility & testing in JSDOM environments */}
      <div
        className="sr-only"
        data-testid="graph-nodes-list"
        aria-label="Graph nodes listing"
      >
        {cappedNodes.map((n) => (
          <div
            key={n.id}
            data-testid={`graph-node-${n.id}`}
            data-kind={n.kind}
            data-role={roles.get(n.id)}
            data-is-summary={n.isSummary ? "true" : "false"}
            data-ref={isLea ? (n.account_ref || n.masked_ref) : n.masked_ref}
          >
            {n.isSummary
              ? n.label
              : isLea
                ? (n.label || n.account_ref || n.masked_ref)
                : (n.label || n.masked_ref)}
          </div>
        ))}
      </div>

      {/* Legends stack bottom-left in one container so they can never overlap */}
      <div
        style={{
          position: "absolute",
          bottom: 12,
          left: 12,
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          gap: 6,
          maxWidth: "calc(100% - 24px)",
        }}
      >
      {/* Legend: shape = topological role (colour is reserved for severity). Labels state what
          the topology shows, not what an account "is". */}
      <div
        className="nk-cluster-graph__legend"
        style={{
          background: "rgba(9, 13, 18, 0.88)",
          padding: "6px 12px",
          borderRadius: 6,
          border: "1px solid var(--nk-border-strong)",
          fontSize: "11px",
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          color: "var(--nk-text-secondary)",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", border: "2px solid var(--nk-text-primary)" }} />
          {ROLE_LABEL.origin}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, border: "2px solid var(--nk-text-secondary)" }} />
          {ROLE_LABEL["pass-through"]}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 9, height: 9, transform: "rotate(45deg)", border: "2px solid var(--nk-text-primary)" }} />
          {ROLE_LABEL.pooling}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, clipPath: "polygon(25% 0, 75% 0, 100% 50%, 75% 100%, 25% 100%, 0 50%)", background: "var(--nk-text-secondary)" }} />
          {ROLE_LABEL.terminal}
        </span>
        {isCapped && (
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 10, height: 10, border: "1px dashed var(--nk-text-secondary)" }} />
            +N More
          </span>
        )}
      </div>

      {/* Fund-flow tempo legend — money flows left to right by hop layer; edge colour is
          when that hop happened relative to the cluster's traced timeline, not distance. */}
      {timelineSpan > 0 && (
        <div
          className="nk-cluster-graph__tempo-legend"
          style={{
            background: "rgba(9, 13, 18, 0.88)",
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid var(--nk-border-strong)",
            fontSize: "11px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: "var(--nk-text-secondary)",
          }}
        >
          <span>Money flows →</span>
          <span
            style={{
              width: 60,
              height: 4,
              borderRadius: 2,
              background: "linear-gradient(90deg, #E7EAEE, #5D6673)",
            }}
          />
          <span>earliest hop (bright) → latest (dim) · thickness = amount</span>
        </div>
      )}
      </div>

      {/* Selected Node Details Drawer/Card */}
      {selectedNode && (
        <div
          className="nk-cluster-graph__inspector"
          data-testid="node-inspector"
          style={{
            position: "absolute",
            bottom: 12,
            right: 12,
            zIndex: 10,
            background: "var(--nk-surface-raised)",
            border: "1px solid var(--nk-accent)",
            borderRadius: 8,
            padding: 12,
            width: 260,
            boxShadow: "0 10px 15px -3px rgba(0,0,0,0.5)",
            fontSize: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <strong style={{ color: "var(--nk-text-primary)" }}>Node Details</strong>
            <button
              type="button"
              onClick={() => setSelectedNode(null)}
              style={{ background: "none", border: "none", color: "var(--nk-text-secondary)", cursor: "pointer" }}
            >
              ✕
            </button>
          </div>
          <div style={{ color: "var(--nk-text-primary)" }}>
            <div>
              <strong>Role:</strong> {ROLE_LABEL[(roles.get(selectedNode.id) ?? "isolated") as NodeRole]}
            </div>
            <div>
              <strong>Bank:</strong> {selectedNode.bank || "N/A"}
            </div>
            <div>
              <strong>Account:</strong>{" "}
              <code>
                {isLea
                  ? selectedNode.account_ref || selectedNode.masked_ref
                  : selectedNode.masked_ref}
              </code>
            </div>
            {selectedNode.amount_paise !== undefined && (
              <div>
                <strong>Amount:</strong> {formatInr(selectedNode.amount_paise)}
              </div>
            )}
            {selectedNode.isSummary && (
              <div style={{ marginTop: 4, color: "var(--nk-text-secondary)", fontStyle: "italic" }}>
                Represents {hiddenCount} truncated accounts.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Selected Edge Details Card */}
      {selectedEdge && (
        <div
          className="nk-cluster-graph__inspector"
          data-testid="edge-inspector"
          style={{
            position: "absolute",
            bottom: 12,
            right: 12,
            zIndex: 10,
            background: "var(--nk-surface-raised)",
            border: "1px solid var(--nk-accent)",
            borderRadius: 8,
            padding: 12,
            width: 260,
            boxShadow: "0 10px 15px -3px rgba(0,0,0,0.5)",
            fontSize: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <strong style={{ color: "var(--nk-text-primary)" }}>Transaction Flow</strong>
            <button
              type="button"
              onClick={() => setSelectedEdge(null)}
              style={{ background: "none", border: "none", color: "var(--nk-text-secondary)", cursor: "pointer" }}
            >
              ✕
            </button>
          </div>
          <div style={{ color: "var(--nk-text-primary)" }}>
            <div>
              <strong>From:</strong> <code>{selectedEdge.from}</code>
            </div>
            <div>
              <strong>To:</strong> <code>{selectedEdge.to}</code>
            </div>
            {selectedEdge.label && (
              <div>
                <strong>Label:</strong> {selectedEdge.label}
              </div>
            )}
            {selectedEdge.amount_paise !== undefined && (
              <div>
                <strong>Amount:</strong> {formatInr(selectedEdge.amount_paise)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
