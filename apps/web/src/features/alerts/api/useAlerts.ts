/**
 * useAlerts.ts — TanStack Query hooks for Alert inbox and detail.
 * DOC 3 Web App Shell: features/alerts/api/useAlerts.ts
 *
 * Real backend only: GET /alerts, GET /alerts/{id}, POST /alerts/{id}/actions,
 * POST /alerts/{id}/outcome. Errors surface through TanStack Query's own error state
 * (isError/error) rather than being swallowed by a fixture fallback — a broken or
 * mismatched backend must be visible, not silently masked.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "../../../shared/api/client";
import { streamKeys } from "../../../shared/stream/streamKeys";
import type { AlertStatus, Severity } from "../../../shared/api/enums.ts";
import type { ActionIn, ActionModel, AlertDetail, AlertSummary, OutcomeIn, OutcomeView } from "../../../shared/api/types.ts";

// ---------------------------------------------------------------------------
// Query Filters
// ---------------------------------------------------------------------------

export interface AlertFilters {
  status?: AlertStatus | "all";
  severity?: Severity | "all";
  district_id?: string;
  search?: string;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * useAlerts — queries list of alerts matching filters.
 * Automatically invalidated when SSE stream receives `alert.created` or `alert.updated`.
 */
export function useAlerts(filters: AlertFilters = {}) {
  return useQuery<AlertSummary[]>({
    queryKey: [...streamKeys.alerts(), filters],
    queryFn: async () => {
      const queryParams: Record<string, string> = {};
      if (filters.status && filters.status !== "all") queryParams.status = filters.status;
      if (filters.district_id) queryParams.district_id = filters.district_id;

      const { data, error } = await apiClient.GET("/alerts", {
        params: { query: queryParams },
      });
      if (error) throw new Error("Failed to load alerts");

      let list = data.items;
      if (filters.severity && filters.severity !== "all") {
        list = list.filter((a) => a.severity === filters.severity);
      }
      if (filters.search) {
        const q = filters.search.toLowerCase();
        list = list.filter(
          (a) =>
            a.id.toLowerCase().includes(q) ||
            a.cluster_ref.toLowerCase().includes(q) ||
            String(a.target.name ?? "")
              .toLowerCase()
              .includes(q),
        );
      }
      return list;
    },
    staleTime: 5_000,
  });
}

/**
 * useAlert — queries single alert detail by ID.
 */
export function useAlert(alertId: string | undefined | null) {
  return useQuery<AlertDetail | null>({
    queryKey: alertId ? streamKeys.alert(alertId) : ["alerts", "null"],
    enabled: Boolean(alertId),
    queryFn: async () => {
      if (!alertId) return null;
      const { data, error } = await apiClient.GET("/alerts/{alert_id}", {
        params: { path: { alert_id: alertId } },
      });
      if (error) throw new Error("Failed to load alert");
      return data;
    },
    staleTime: 5_000,
  });
}

/**
 * useAlertAction — executes an action on an alert (hold, notify, dispatch, acknowledge, override).
 */
export function useAlertAction() {
  const qc = useQueryClient();

  return useMutation<ActionModel, Error, { alertId: string; action: ActionIn }>({
    mutationFn: async ({ alertId, action }) => {
      const { data, error } = await apiClient.POST("/alerts/{alert_id}/actions", {
        params: { path: { alert_id: alertId } },
        body: action,
      });
      if (error) throw new Error("Failed to record action");
      return data;
    },
    onSuccess: (_, { alertId }) => {
      void qc.invalidateQueries({ queryKey: streamKeys.alerts() });
      void qc.invalidateQueries({ queryKey: streamKeys.alert(alertId) });
    },
  });
}

/**
 * useAlertOutcome — records the outcome of an alert (hit, miss, late; DOC 3 S3).
 */
export function useAlertOutcome() {
  const qc = useQueryClient();

  return useMutation<OutcomeView, Error, { alertId: string; outcome: OutcomeIn }>({
    mutationFn: async ({ alertId, outcome }) => {
      const { data, error } = await apiClient.POST("/alerts/{alert_id}/outcome", {
        params: { path: { alert_id: alertId } },
        body: outcome,
      });
      if (error) throw new Error("Failed to record outcome");
      return data;
    },
    onSuccess: (_, { alertId }) => {
      void qc.invalidateQueries({ queryKey: streamKeys.alerts() });
      void qc.invalidateQueries({ queryKey: streamKeys.alert(alertId) });
    },
  });
}
