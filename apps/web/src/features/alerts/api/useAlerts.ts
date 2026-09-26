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
import type { ActionIn, ActionModel, AlertDetail, AlertSummary, EvidencePack, OutcomeIn, OutcomeView } from "../../../shared/api/types.ts";

// ---------------------------------------------------------------------------
// Query Filters
// ---------------------------------------------------------------------------

export interface AlertFilters {
  status?: AlertStatus | "all";
  severity?: Severity | "all";
  district_id?: string;
  search?: string;
  /** "queue" (default, the alert budget) | "backlog" (deferred) | "all" | "review". */
  view?: "queue" | "backlog" | "all" | "review";
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
      if (filters.view) queryParams.view = filters.view;

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
/** The API's error envelope is { error: { code, message } }; surface its user-facing text. */
export function errorMessage(error: unknown, fallback: string): string {
  const msg = (error as { error?: { message?: unknown } } | null)?.error?.message;
  return typeof msg === "string" && msg ? msg : fallback;
}

export async function fetchAlertDetail(alertId: string): Promise<AlertDetail> {
  const { data, error } = await apiClient.GET("/alerts/{alert_id}", {
    params: { path: { alert_id: alertId } },
  });
  if (error) throw new Error("Failed to load alert");
  return data;
}

export function useAlert(alertId: string | undefined | null) {
  return useQuery<AlertDetail | null>({
    queryKey: alertId ? streamKeys.alert(alertId) : ["alerts", "null"],
    enabled: Boolean(alertId),
    queryFn: async () => (alertId ? fetchAlertDetail(alertId) : null),
    staleTime: 5_000,
  });
}

/** Status an alert moves to once this action type is recorded (mirrors RecordAction on the server). */
function optimisticStatus(type: string): AlertStatus {
  return type === "acknowledge" ? "acknowledged" : "actioned";
}

/** Patch one alert's status inside any cached list ([]) or detail ({id}) under the alerts key. */
function patchAlertStatus(data: unknown, alertId: string, status: AlertStatus): unknown {
  if (Array.isArray(data)) {
    return data.map((a) => (a && a.id === alertId ? { ...a, status } : a));
  }
  if (data && typeof data === "object" && (data as { id?: string }).id === alertId) {
    return { ...(data as object), status };
  }
  return data;
}

/**
 * useAlertAction — executes an action on an alert (hold, notify, dispatch, acknowledge, override).
 */
export function useAlertAction() {
  const qc = useQueryClient();

  return useMutation<
    ActionModel,
    Error,
    { alertId: string; action: ActionIn },
    { snapshot: [readonly unknown[], unknown][] }
  >({
    // Optimistic: flip the alert's status in every cached list and detail at once, so the
    // queue reacts the instant the operator acts. Rolled back on error; the server's
    // answer (via invalidation below and the SSE alert.updated event) is what finally stands.
    onMutate: async ({ alertId, action }) => {
      await qc.cancelQueries({ queryKey: streamKeys.alerts() });
      const snapshot = qc.getQueriesData({ queryKey: streamKeys.alerts() }) as [
        readonly unknown[],
        unknown,
      ][];
      const status = optimisticStatus(action.type);
      qc.setQueriesData({ queryKey: streamKeys.alerts() }, (old: unknown) =>
        patchAlertStatus(old, alertId, status),
      );
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => {
      for (const [key, data] of ctx?.snapshot ?? []) qc.setQueryData(key, data);
    },
    mutationFn: async ({ alertId, action }) => {
      const { data, error } = await apiClient.POST("/alerts/{alert_id}/actions", {
        params: { path: { alert_id: alertId } },
        body: action,
      });
      if (error) throw new Error(errorMessage(error, "Failed to record action"));
      return data;
    },
    onSettled: (_data, _err, { alertId }) => {
      void qc.invalidateQueries({ queryKey: streamKeys.alerts() });
      void qc.invalidateQueries({ queryKey: streamKeys.alert(alertId) });
    },
  });
}

/**
 * useAlertHoldAccounts — the accounts traced in the alert's cluster, i.e. the candidates a
 * lien can be requested against. request_hold needs a concrete account_id (the server
 * re-validates that it was traced from this alert's complaint), so the operator picks one.
 */
export function useAlertHoldAccounts(clusterId: string | null | undefined, enabled: boolean) {
  return useQuery<{ id: string; label: string }[]>({
    queryKey: ["clusters", "hold-accounts", clusterId],
    enabled: enabled && Boolean(clusterId),
    queryFn: async () => {
      if (!clusterId) return [];
      const { data, error } = await apiClient.GET("/clusters/{cluster_id}", {
        params: { path: { cluster_id: clusterId } },
      });
      if (error) throw new Error(errorMessage(error, "Failed to load cluster accounts"));
      return (data?.nodes ?? []).map((n) => ({ id: n.id, label: `${n.masked_ref} · ${n.bank}` }));
    },
    staleTime: 30_000,
  });
}

/**
 * useBuildEvidencePack — POST /alerts/{id}/evidence-pack: builds a court-ready evidence pack
 * (PDF, SHA-256, s.63 draft certificate) anchored to the audit hash chain's current head.
 * Fully implemented on the backend, unwired on the frontend until now (Frontend Strategy §4.2).
 */
export function useBuildEvidencePack() {
  return useMutation<EvidencePack, Error, { alertId: string }>({
    mutationFn: async ({ alertId }) => {
      const { data, error } = await apiClient.POST("/alerts/{alert_id}/evidence-pack", {
        params: { path: { alert_id: alertId } },
      });
      if (error) throw new Error("Failed to build evidence pack");
      return data;
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
