/**
 * ClustersPage.tsx — Cluster topology explorer.
 * DOC 3 §S1 & DOC 4 §C6
 */

import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useClusters, useCluster } from "./api/useClusters";
import { ClusterGraph } from "./ClusterGraph";
import { formatInr, formatSimTime } from "../../shared/lib/format";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Tooltip } from "../../shared/ui/Tooltip";
import type { ClusterNode } from "./types";

export default function ClustersPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  const { data: clusters = [], isLoading: isLoadingList, isError: isListError } = useClusters();

  // If no ID param, default to the first cluster in the list
  const selectedRef = id || (clusters.length > 0 ? clusters[0]?.cluster_ref : undefined);

  const {
    data: clusterDetail,
    isLoading: isLoadingCluster,
    isError: isClusterError,
  } = useCluster(selectedRef);

  // The list (GET /clusters) and the detail (GET /clusters/{id}) are separate real endpoints
  // with disjoint fields (DOC 4 A12): merge them so the page has both in one object.
  const summary = clusters.find((c) => c.cluster_ref === selectedRef);
  const cluster = clusterDetail ? { ...summary, ...clusterDetail } : null;

  const [inspectedNode, setInspectedNode] = useState<ClusterNode | null>(null);

  if (isLoadingList || (selectedRef && isLoadingCluster)) {
    return (
      <div className="nk-page-loading" aria-live="polite">
        Loading cluster graph…
      </div>
    );
  }

  if (isListError || isClusterError) {
    return (
      <ErrorState
        error={{
          message: "Could not retrieve cluster topology. Please try again.",
          code: "CLUSTER_LOAD_ERROR",
        }}
      />
    );
  }

  if (!cluster && clusters.length === 0) {
    return (
      <EmptyState
        title="No Clusters Available"
        message="The simulator has not generated any mule clusters yet. Start the simulation from the Demo console."
      />
    );
  }

  return (
    <div className="nk-clusters-page" data-testid="clusters-page" style={{ padding: "20px", height: "100%" }}>
      {/* Page Title */}
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: "20px", color: "var(--nk-text-primary)", fontWeight: 700 }}>
          Cluster Topology Explorer
        </h1>
        <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "var(--nk-text-secondary)" }}>
          {clusters.length} mule network{clusters.length !== 1 ? "s" : ""} identified — select one to inspect its transaction graph.
        </p>
      </div>

      <div className="nk-clusters-layout">
        {/* ---- Sidebar: scrollable cluster list ---- */}
        <div className="nk-cluster-sidebar" aria-label="Cluster list">
          {clusters.map((c) => {
            const isActive = c.cluster_ref === selectedRef;
            return (
              <button
                key={c.cluster_ref}
                type="button"
                className={`nk-cluster-sidebar-item${isActive ? " nk-cluster-sidebar-item--active" : ""}`}
                onClick={() => navigate(`/clusters/${c.cluster_ref}`)}
                aria-current={isActive ? "true" : undefined}
              >
                <div className="nk-cluster-sidebar-item__id">{c.cluster_ref}</div>
                <div className="nk-cluster-sidebar-item__district">
                  {((c as unknown) as Record<string, string>).district_ref ?? "Unknown district"}
                </div>
                <div className="nk-cluster-sidebar-item__stats">
                  <span>{c.size ?? "?"} nodes</span>
                  <span>·</span>
                  <span
                    style={{
                      color: c.status === "active" ? "#ef4444" : "var(--nk-text-muted)",
                      fontWeight: 600,
                      textTransform: "uppercase",
                    }}
                  >
                    {c.status}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* ---- Main: health strip + graph + node inspector ---- */}
        {cluster ? (
          <div className="nk-cluster-graph-area">
            {/* Health Strip */}
            <div className="nk-cluster-health-strip" aria-label="Cluster metrics">
              <div className="nk-cluster-metric">
                <span className="nk-cluster-metric__label">Cluster ID</span>
                <span className="nk-cluster-metric__value" style={{ fontFamily: "var(--nk-font-mono)" }}>
                  {cluster.cluster_ref}
                </span>
              </div>

              <div className="nk-cluster-metric__divider" />

              <div className="nk-cluster-metric">
                <span className="nk-cluster-metric__label">Total Disputed</span>
                <span className="nk-cluster-metric__value" style={{ color: "var(--nk-brand-primary)" }}>
                  {formatInr(cluster.total_paise ?? 0)}
                </span>
              </div>

              <div className="nk-cluster-metric__divider" />

              <div className="nk-cluster-metric">
                <span className="nk-cluster-metric__label">Accounts</span>
                <span className="nk-cluster-metric__value">{cluster.size ?? (cluster.nodes?.length ?? "—")}</span>
              </div>

              <div className="nk-cluster-metric__divider" />

              <div className="nk-cluster-metric">
                <span className="nk-cluster-metric__label">Transactions</span>
                <span className="nk-cluster-metric__value">{cluster.edges?.length ?? "—"}</span>
              </div>

              <div className="nk-cluster-metric__divider" />

              <div className="nk-cluster-metric">
                <span className="nk-cluster-metric__label">First Seen</span>
                <span className="nk-cluster-metric__value" style={{ fontSize: "13px" }}>
                  {cluster.first_seen ? formatSimTime(cluster.first_seen) : "—"}
                </span>
              </div>

              <div className="nk-cluster-metric__divider" />

              <div className="nk-cluster-metric">
                <Tooltip content="How different this cluster's behaviour is from previously-seen patterns. Higher novelty = less historical precedent.">
                  <span className="nk-cluster-metric__label" style={{ cursor: "help" }}>Novelty ⓘ</span>
                </Tooltip>
                <span
                  className="nk-cluster-metric__value"
                  style={{ color: (cluster.novelty ?? 0) > 0.7 ? "#f59e0b" : "var(--nk-text-primary)" }}
                >
                  {((cluster.novelty ?? 0) * 100).toFixed(0)}%
                </span>
              </div>

              {/* Status & bridge badges pushed right */}
              <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 700,
                    padding: "3px 10px",
                    borderRadius: 999,
                    textTransform: "uppercase",
                    background: cluster.status === "active" ? "rgba(239,68,68,0.12)" : "rgba(148,163,184,0.12)",
                    color: cluster.status === "active" ? "#ef4444" : "#94a3b8",
                    border: `1px solid ${cluster.status === "active" ? "rgba(239,68,68,0.3)" : "rgba(148,163,184,0.2)"}`,
                  }}
                >
                  {cluster.status}
                </span>
                {cluster.single_complaint && (
                  <span className="nk-geo-badge">Single complaint</span>
                )}
                {/* Sub-communities */}
                {cluster.sub_communities && cluster.sub_communities.length > 0 && (
                  <span className="nk-bridge-badge">
                    🔗 {cluster.sub_communities.length} sub-communities
                  </span>
                )}
              </div>
            </div>

            {/* Cytoscape Graph */}
            <div
              style={{
                border: "1px solid var(--nk-border-subtle)",
                borderRadius: 8,
                overflow: "hidden",
                background: "#090d16",
              }}
            >
              <ClusterGraph
                data={{ nodes: cluster.nodes, edges: cluster.edges }}
                height={520}
                onNodeSelect={setInspectedNode}
                selectedNodeId={inspectedNode?.id}
              />
            </div>

            {/* Node Inspector Panel */}
            {inspectedNode && (
              <div className="nk-node-inspector" data-testid="selected-node-panel">
                <div className="nk-node-inspector__title">
                  Node Inspector
                  <button
                    type="button"
                    onClick={() => setInspectedNode(null)}
                    className="nk-btn nk-btn--ghost nk-btn--sm"
                    style={{ marginLeft: "auto", float: "right", fontSize: "11px" }}
                  >
                    ✕ Clear
                  </button>
                </div>
                <div className="nk-node-inspector__field">
                  <span className="nk-node-inspector__field-label">Kind</span>
                  <span className={`nk-node-inspector__field-value nk-node-kind--${inspectedNode.kind}`}>
                    {inspectedNode.kind}
                  </span>
                </div>
                <div className="nk-node-inspector__field">
                  <span className="nk-node-inspector__field-label">Account Ref</span>
                  <span className="nk-node-inspector__field-value">
                    {inspectedNode.label || inspectedNode.masked_ref || inspectedNode.id}
                  </span>
                </div>
                <div className="nk-node-inspector__field">
                  <span className="nk-node-inspector__field-label">Bank</span>
                  <span className="nk-node-inspector__field-value">{inspectedNode.bank || "—"}</span>
                </div>
                <div className="nk-node-inspector__field">
                  <span className="nk-node-inspector__field-label">Amount</span>
                  <span className="nk-node-inspector__field-value" style={{ color: "var(--nk-brand-primary)" }}>
                    {inspectedNode.amount_paise != null ? formatInr(inspectedNode.amount_paise) : "—"}
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <EmptyState
            title="Select a Cluster"
            message="Choose a mule network from the list on the left to inspect its account graph."
          />
        )}
      </div>
    </div>
  );
}
