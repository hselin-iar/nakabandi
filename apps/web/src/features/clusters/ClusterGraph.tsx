/**
 * ClusterGraph.tsx — Shared Cytoscape.js wrapper for cluster topologies.
 * DOC 3 §S1 & DOC 4 §C6
 *
 * Invariants:
 * - Shared between clusters and cases (imported by CaseDetail, never duplicated).
 * - Caps graph nodes at 200 with a visible "+N more" summary node and alert badge.
 * - Non-LEA principals see only masked account references in node labels.
 */

import React, { useEffect, useRef, useState, useMemo } from "react";
import cytoscape from "cytoscape";
import type { Core, EventObject } from "cytoscape";
import { usePrincipal } from "../../app/auth/usePrincipal";
import type { ClusterGraphData, ClusterNode, ClusterEdge } from "./types";

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

  const edgeMap = useMemo(() => {
    const map = new Map<string, ClusterEdge>();
    for (const edge of cappedEdges) {
      const id = edge.id || `${edge.from}-${edge.to}`;
      map.set(id, edge);
    }
    return map;
  }, [cappedEdges]);

  // ---------------------------------------------------------------------------
  // Cytoscape initialization and updates
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current) return;

    // Convert nodes to Cytoscape elements
    const cyNodes = cappedNodes.map((n) => {
      // Role-gated display: non-LEA never sees unmasked account refs
      const displayLabel = n.isSummary
        ? n.label
        : isLea
          ? (n.label ?? n.account_ref ?? n.masked_ref ?? n.id)
          : (n.label ?? n.masked_ref ?? n.id);

      return {
        group: "nodes" as const,
        data: {
          id: n.id,
          label: displayLabel,
          kind: n.kind,
          bank: n.bank || "",
          isSummary: Boolean(n.isSummary),
        },
      };
    });

    const cyEdges = cappedEdges.map((e, idx) => ({
      group: "edges" as const,
      data: {
        id: e.id || `e-${idx}-${e.from}-${e.to}`,
        source: e.from,
        target: e.to,
        label: e.label || "",
      },
    }));

    try {
      if (cyRef.current) {
        cyRef.current.destroy();
      }

      const cy = cytoscape({
        container: containerRef.current,
        elements: [...cyNodes, ...cyEdges],
        style: [
          {
            selector: "node",
            style: {
              "background-color": "#475569",
              label: "data(label)",
              color: "#f8fafc",
              "font-size": "11px",
              "text-valign": "bottom",
              "text-margin-y": 6,
              width: 32,
              height: 32,
              "border-width": 2,
              "border-color": "#334155",
            },
          },
          {
            selector: 'node[kind = "victim"]',
            style: {
              "background-color": "#0284c7", // Sky blue
              "border-color": "#38bdf8",
              shape: "ellipse",
            },
          },
          {
            selector: 'node[kind = "mule"]',
            style: {
              "background-color": "#d97706", // Amber
              "border-color": "#fbbf24",
              shape: "round-rectangle",
            },
          },
          {
            selector: 'node[kind = "aggregator"]',
            style: {
              "background-color": "#dc2626", // Red
              "border-color": "#f87171",
              shape: "diamond",
              width: 38,
              height: 38,
            },
          },
          {
            selector: 'node[kind = "exit"]',
            style: {
              "background-color": "#9333ea", // Purple
              "border-color": "#c084fc",
              shape: "hexagon",
              width: 36,
              height: 36,
            },
          },
          {
            selector: "node[?isSummary]",
            style: {
              "background-color": "#334155",
              "border-color": "#94a3b8",
              "border-style": "dashed",
              "border-width": 3,
              shape: "barrel",
              width: 44,
              height: 44,
              "font-weight": "bold",
              color: "#e2e8f0",
            },
          },
          {
            selector: "node:selected",
            style: {
              "border-width": 4,
              "border-color": "#38bdf8",
            },
          },
          {
            selector: "edge",
            style: {
              width: 2,
              "line-color": "#475569",
              "target-arrow-color": "#64748b",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              "arrow-scale": 1.2,
              label: "data(label)",
              "font-size": "9px",
              color: "#94a3b8",
              "text-rotation": "autorotate",
              "text-background-opacity": 0.8,
              "text-background-color": "#090d16",
              "text-background-padding": "2px",
            },
          },
          {
            selector: "edge:selected",
            style: {
              width: 4,
              "line-color": "#38bdf8",
              "target-arrow-color": "#38bdf8",
            },
          },
        ],
        layout: {
          name: cyNodes.length > 50 ? "concentric" : "breadthfirst",
          directed: true,
          padding: 30,
          spacingFactor: 1.25,
        } as cytoscape.LayoutOptions,
      });

      cy.on("tap", "node", (evt: EventObject) => {
        const id = evt.target.id();
        const node = nodeMap.get(id) || null;
        setSelectedNode(node);
        setSelectedEdge(null);
        onNodeSelect?.(node);
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
  }, [cappedNodes, cappedEdges, isLea, nodeMap, edgeMap, onNodeSelect, onEdgeSelect]);

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
            background: "rgba(15, 23, 42, 0.9)",
            border: "1px solid #f59e0b",
            color: "#fbbf24",
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
          <span aria-hidden="true">⚠️</span>
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
          background: "rgba(15, 23, 42, 0.85)",
          padding: 4,
          borderRadius: 6,
          border: "1px solid #334155",
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
          background: "#090d16",
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

      {/* Node Legend overlay at bottom-left */}
      <div
        className="nk-cluster-graph__legend"
        style={{
          position: "absolute",
          bottom: 12,
          left: 12,
          zIndex: 10,
          background: "rgba(15, 23, 42, 0.85)",
          padding: "6px 12px",
          borderRadius: 6,
          border: "1px solid #334155",
          fontSize: "11px",
          display: "flex",
          gap: 12,
          color: "#94a3b8",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#0284c7" }} />
          Victim
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: "#d97706" }} />
          Mule
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, transform: "rotate(45deg)", background: "#dc2626" }} />
          Aggregator
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, background: "#9333ea" }} />
          Exit ATM
        </span>
        {isCapped && (
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 10, height: 10, border: "1px dashed #94a3b8" }} />
            +N More
          </span>
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
            background: "#0f172a",
            border: "1px solid #38bdf8",
            borderRadius: 8,
            padding: 12,
            width: 260,
            boxShadow: "0 10px 15px -3px rgba(0,0,0,0.5)",
            fontSize: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <strong style={{ color: "#f8fafc" }}>Node Details</strong>
            <button
              type="button"
              onClick={() => setSelectedNode(null)}
              style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer" }}
            >
              ✕
            </button>
          </div>
          <div style={{ color: "#cbd5e1" }}>
            <div>
              <strong>Kind:</strong>{" "}
              <span style={{ textTransform: "capitalize" }}>{selectedNode.kind}</span>
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
                <strong>Amount:</strong> ₹{(selectedNode.amount_paise / 100).toLocaleString("en-IN")}
              </div>
            )}
            {selectedNode.isSummary && (
              <div style={{ marginTop: 4, color: "#f59e0b", fontStyle: "italic" }}>
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
            background: "#0f172a",
            border: "1px solid #38bdf8",
            borderRadius: 8,
            padding: 12,
            width: 260,
            boxShadow: "0 10px 15px -3px rgba(0,0,0,0.5)",
            fontSize: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <strong style={{ color: "#f8fafc" }}>Transaction Flow</strong>
            <button
              type="button"
              onClick={() => setSelectedEdge(null)}
              style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer" }}
            >
              ✕
            </button>
          </div>
          <div style={{ color: "#cbd5e1" }}>
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
                <strong>Amount:</strong> ₹{(selectedEdge.amount_paise / 100).toLocaleString("en-IN")}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
