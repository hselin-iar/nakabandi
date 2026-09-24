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

  if (!cluster) {
    return (
      <EmptyState
        title="Cluster Not Found"
        message={
          selectedRef
            ? `No cluster matching reference "${selectedRef}".`
            : "No clusters are currently available."
        }
      />
    );
  }

  const handleSelectCluster = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextRef = e.target.value;
    navigate(`/clusters/${nextRef}`);
  };

  return (
    <div className="nk-clusters-page" data-testid="clusters-page" style={{ padding: "20px" }}>
      {/* Header bar with Cluster selector & key metrics */}
      <div
        className="nk-clusters-header"
        style={{
          background: "#0f172a",
          border: "1px solid #1e293b",
          borderRadius: 8,
          padding: "16px 20px",
          marginBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div>
            <label
              htmlFor="cluster-select"
              style={{
                display: "block",
                fontSize: "11px",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "#94a3b8",
                marginBottom: 4,
              }}
            >
              Select Cluster
            </label>
            <select
              id="cluster-select"
              data-testid="cluster-select"
              value={cluster.cluster_ref}
              onChange={handleSelectCluster}
              className="nk-input"
              style={{
                background: "#1e293b",
                color: "#f8fafc",
                border: "1px solid #334155",
                borderRadius: 4,
                padding: "6px 12px",
                fontWeight: 600,
                fontSize: "14px",
              }}
            >
              {clusters.map((c) => (
                <option key={c.cluster_ref} value={c.cluster_ref}>
                  {c.cluster_ref} ({c.size} nodes — {c.status})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 14 }}>
            <span
              className={`nk-badge ${
                cluster.status === "active" ? "nk-badge--danger" : "nk-badge--neutral"
              }`}
              style={{
                textTransform: "uppercase",
                fontSize: "11px",
                fontWeight: 700,
                padding: "3px 8px",
                borderRadius: 4,
                background: cluster.status === "active" ? "#7f1d1d" : "#334155",
                color: cluster.status === "active" ? "#fca5a5" : "#cbd5e1",
              }}
            >
              {cluster.status}
            </span>

            {cluster.single_complaint && (
              <span
                className="nk-badge nk-badge--info"
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  padding: "3px 8px",
                  borderRadius: 4,
                  background: "#0369a1",
                  color: "#bae6fd",
                }}
              >
                Single complaint
              </span>
            )}

            <span
              style={{
                fontSize: "12px",
                color: "#fbbf24",
                background: "rgba(245, 158, 11, 0.1)",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                padding: "3px 8px",
                borderRadius: 4,
              }}
            >
              Novelty: {((cluster.novelty ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        {/* Aggregate Stats */}
        <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
          <div>
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>Total Disputed</div>
            <div style={{ fontSize: "18px", fontWeight: 700, color: "#38bdf8" }}>
              {formatInr(cluster.total_paise ?? 0)}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>Cluster Size</div>
            <div style={{ fontSize: "18px", fontWeight: 700, color: "#f8fafc" }}>
              {cluster.size} Accounts
            </div>
          </div>

          <div>
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>First / Last Activity</div>
            <div style={{ fontSize: "12px", color: "#cbd5e1" }}>
              {cluster.first_seen ? formatSimTime(cluster.first_seen) : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Sub-communities tags if any */}
      {cluster.sub_communities && cluster.sub_communities.length > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 12,
            fontSize: "12px",
            color: "#94a3b8",
          }}
        >
          <span>Sub-communities:</span>
          {cluster.sub_communities.map((sub) => (
            <span
              key={sub.id}
              style={{
                background: "#1e293b",
                border: "1px solid #334155",
                borderRadius: 4,
                padding: "2px 8px",
                color: "#e2e8f0",
              }}
            >
              {sub.label} ({sub.account_count})
            </span>
          ))}
        </div>
      )}

      {/* Inspected Node Bar */}
      {inspectedNode && (
        <div
          data-testid="selected-node-panel"
          style={{
            marginBottom: 12,
            background: "#1e293b",
            border: "1px solid #38bdf8",
            borderRadius: 6,
            padding: "8px 14px",
            fontSize: "12px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ color: "#e2e8f0" }}>
            Inspected Entity: <strong style={{ color: "#f8fafc" }}>{inspectedNode.label || inspectedNode.masked_ref}</strong>{" "}
            ({inspectedNode.kind}, {inspectedNode.bank || "N/A"})
          </span>
          <button
            type="button"
            onClick={() => setInspectedNode(null)}
            className="nk-btn nk-btn--secondary nk-btn--sm"
            style={{ padding: "2px 8px", fontSize: "11px" }}
          >
            Clear Selection
          </button>
        </div>
      )}

      {/* Interactive Cluster Graph Component */}
      <div
        style={{
          border: "1px solid #1e293b",
          borderRadius: 8,
          overflow: "hidden",
          background: "#090d16",
        }}
      >
        <ClusterGraph
          data={{ nodes: cluster.nodes, edges: cluster.edges }}
          height={600}
          onNodeSelect={setInspectedNode}
          selectedNodeId={inspectedNode?.id}
        />
      </div>
    </div>
  );
}
