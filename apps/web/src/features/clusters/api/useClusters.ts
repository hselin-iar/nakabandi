/**
 * useClusters.ts — TanStack Query hooks for Clusters & Graph visualization.
 * DOC 3 §S1 (Cluster Case Bundling) & DOC 4 §C6.
 *
 * Real backend only: GET /clusters (a page of the same cases the Cases feature lists — DOC 4
 * A12 built no separate "all clusters" listing, since a cluster only appears once it has a
 * bundled case) and GET /clusters/{cluster_ref} (the real node/edge graph, capped at 200 nodes).
 */

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../../shared/api/client";
import type { ClusterEdge, ClusterNode, ClusterSummary, ClusterView, NodeKind } from "./../types";

export function useClusters() {
  return useQuery<ClusterSummary[]>({
    queryKey: ["clusters"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/clusters", { params: { query: {} } });
      if (error) throw new Error("Failed to load clusters");
      return data.items.map((c) => ({
        cluster_ref: c.cluster_ref,
        size: c.accounts.length,
        // Same placeholder the single-cluster endpoint uses today (DOC 4 A12 Learnings: not
        // wired to absorption state / the forecast facade yet) — kept consistent, not fabricated.
        status: "active" as const,
        novelty: 0,
        total_paise: c.total_paise,
        first_seen: c.first_seen,
        last_seen: c.last_seen,
        single_complaint: c.single_complaint,
      }));
    },
    staleTime: 60_000,
  });
}

export function useCluster(clusterRef: string | undefined) {
  return useQuery<ClusterView | null>({
    queryKey: ["cluster", clusterRef],
    queryFn: async () => {
      if (!clusterRef) return null;
      const { data, error } = await apiClient.GET("/clusters/{cluster_id}", {
        params: { path: { cluster_id: clusterRef } },
      });
      if (error) throw new Error("Failed to load cluster");
      const nodes: ClusterNode[] = data.nodes.map((n) => ({
        id: n.id,
        kind: n.kind as NodeKind,
        masked_ref: n.masked_ref,
        account_ref: n.masked_ref,
        bank: n.bank,
      }));
      const edges: ClusterEdge[] = data.edges.map((e) => ({
        from: e.from,
        to: e.to,
        amount_paise: e.amount_paise ?? undefined,
      }));
      return {
        cluster_ref: data.cluster_ref,
        size: data.size,
        status: data.status as ClusterView["status"],
        novelty: data.novelty,
        nodes,
        edges,
      };
    },
    enabled: Boolean(clusterRef),
    staleTime: 60_000,
  });
}
