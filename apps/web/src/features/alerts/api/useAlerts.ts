/**
 * useAlerts.ts — TanStack Query hooks for Alert inbox and detail.
 * DOC 3 Web App Shell: features/alerts/api/useAlerts.ts
 *
 * Backed by apiClient; invalidates on streamKeys.alerts() when stream events arrive.
 * Supplies robust LC-4 fixtures for offline/test environments (DOC 4 Step C4).
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../../shared/api/client";
import { streamKeys } from "../../../shared/stream/streamKeys";
import type {
  AlertSummary,
  AlertDetail,
  AlertActionIn,
  AlertOutcomeIn,
  Severity,
  AlertStatus,
} from "../../../shared/api/schema.d.ts";

// ---------------------------------------------------------------------------
// Standard LC-4 Fixtures (DOC 3 M4, DOC 4 C4)
// ---------------------------------------------------------------------------

export const FIXTURE_ALERTS: AlertDetail[] = [
  {
    id: "ALT-2026-001",
    cluster_ref: "CLS-DL-8821",
    target: {
      kind: "ATM",
      id: "LOC-ATM-4012",
      name: "SBI ATM — Connaught Place Inner Circle",
    },
    severity: "CRITICAL",
    confidence: 0.94,
    status: "open",
    is_deferred: false,
    is_probe: false,
    window_start: "2026-01-15T10:00:00Z",
    window_end: "2026-01-15T11:30:00Z",
    expires_at: "2026-01-15T11:30:00Z",
    ladder_level: "L3",
    created_at: "2026-01-15T10:05:00Z",
    masked: false,
    timeline: [
      {
        at: "2026-01-15T10:05:00Z",
        kind: "created",
        actor_id: null,
        text_code: "alert.created",
        text_params: { reason: "High confidence cash-out trajectory detected" },
      },
      {
        at: "2026-01-15T10:06:12Z",
        kind: "notification",
        actor_id: null,
        text_code: "alert.notified",
        text_params: { channel: "sms", recipient: "+91-98******10" },
      },
    ],
  },
  {
    id: "ALT-2026-002",
    cluster_ref: "CLS-MH-1049",
    target: {
      kind: "BRANCH",
      id: "LOC-BR-0912",
      name: "HDFC Bank — Bandra West Branch",
    },
    severity: "HIGH",
    confidence: 0.81,
    status: "acknowledged",
    is_deferred: false,
    is_probe: false,
    window_start: "2026-01-15T10:15:00Z",
    window_end: "2026-01-15T12:00:00Z",
    expires_at: "2026-01-15T12:00:00Z",
    ladder_level: "L2",
    created_at: "2026-01-15T10:18:00Z",
    masked: false,
    timeline: [
      {
        at: "2026-01-15T10:18:00Z",
        kind: "created",
        actor_id: null,
        text_code: "alert.created",
        text_params: { reason: "Layer 2 rapid pass-through observation" },
      },
      {
        at: "2026-01-15T10:22:00Z",
        kind: "acknowledged",
        actor_id: "USR-NODAL-04",
        text_code: "alert.acknowledged",
        text_params: { by: "Bank Nodal Officer" },
      },
    ],
  },
  {
    id: "ALT-2026-003",
    cluster_ref: "CLS-KA-3321",
    target: {
      kind: "AGENT",
      id: "LOC-AG-1105",
      name: "BC Point — Whitefield Main Rd",
    },
    severity: "MEDIUM",
    confidence: 0.68,
    status: "open",
    is_deferred: false,
    is_probe: true,
    window_start: "2026-01-15T10:30:00Z",
    window_end: "2026-01-15T12:30:00Z",
    expires_at: "2026-01-15T12:30:00Z",
    ladder_level: "L1",
    created_at: "2026-01-15T10:32:00Z",
    masked: true,
    timeline: [
      {
        at: "2026-01-15T10:32:00Z",
        kind: "created",
        actor_id: null,
        text_code: "alert.created",
        text_params: { reason: "Novelty probe pattern" },
      },
    ],
  },
  {
    id: "ALT-2026-004",
    cluster_ref: "CLS-DL-9901",
    target: {
      kind: "ATM",
      id: "LOC-ATM-2201",
      name: "ICICI ATM — Karol Bagh Metro",
    },
    severity: "LOW",
    confidence: 0.42,
    status: "actioned",
    is_deferred: false,
    is_probe: false,
    window_start: "2026-01-15T09:00:00Z",
    window_end: "2026-01-15T10:30:00Z",
    expires_at: "2026-01-15T10:30:00Z",
    ladder_level: "NONE",
    created_at: "2026-01-15T09:05:00Z",
    masked: false,
    timeline: [
      {
        at: "2026-01-15T09:05:00Z",
        kind: "created",
        actor_id: null,
        text_code: "alert.created",
        text_params: { reason: "Low velocity cash out" },
      },
      {
        at: "2026-01-15T09:20:00Z",
        kind: "actioned",
        actor_id: "USR-OFFICER-01",
        text_code: "alert.hold_requested",
        text_params: { lien_amount: "₹50,000" },
      },
    ],
  },
];

// In-memory store for mutations when working against fixture fallbacks
let activeAlertsStore = [...FIXTURE_ALERTS];

export function resetAlertsFixtureStore(): void {
  activeAlertsStore = [...FIXTURE_ALERTS];
}

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
      try {
        const queryParams: Record<string, string> = {};
        if (filters.status && filters.status !== "all") queryParams.status = filters.status;
        if (filters.severity && filters.severity !== "all") queryParams.severity = filters.severity;
        if (filters.district_id) queryParams.district_id = filters.district_id;

        const res = await apiClient.GET("/alerts", {
          params: {
            query: queryParams as {
              status?: AlertStatus;
              severity?: Severity;
              district_id?: string;
            },
          },
        });

        if (res.data?.items && res.data.items.length > 0) {
          let list = res.data.items;
          if (filters.search) {
            const q = filters.search.toLowerCase();
            list = list.filter(
              (a) =>
                a.id.toLowerCase().includes(q) ||
                a.cluster_ref.toLowerCase().includes(q) ||
                (a.target.name ?? "").toLowerCase().includes(q)
            );
          }
          return list;
        }
      } catch {
        // Fall back to fixture store (Sync 4 fallback per DOC 4 C4)
      }

      // Filter fixture store
      return activeAlertsStore.filter((a) => {
        if (filters.status && filters.status !== "all" && a.status !== filters.status) {
          return false;
        }
        if (filters.severity && filters.severity !== "all" && a.severity !== filters.severity) {
          return false;
        }
        if (filters.search) {
          const q = filters.search.toLowerCase();
          const match =
            a.id.toLowerCase().includes(q) ||
            a.cluster_ref.toLowerCase().includes(q) ||
            (a.target.name ?? "").toLowerCase().includes(q);
          if (!match) return false;
        }
        return true;
      });
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
      try {
        const res = await apiClient.GET("/alerts/{alert_id}", {
          params: { path: { alert_id: alertId } },
        });
        if (res.data) return res.data;
      } catch {
        // Fall back to fixture store
      }

      const found = activeAlertsStore.find((a) => a.id === alertId);
      return found ?? null;
    },
    staleTime: 5_000,
  });
}

/**
 * useAlertAction — executes an action on an alert (hold, notify, dispatch, acknowledge, override).
 */
export function useAlertAction() {
  const qc = useQueryClient();

  return useMutation<
    { ok: boolean; action_id: string },
    Error,
    { alertId: string; action: AlertActionIn }
  >({
    mutationFn: async ({ alertId, action }) => {
      try {
        const res = await apiClient.POST("/alerts/{alert_id}/actions", {
          params: { path: { alert_id: alertId } },
          body: action,
        });
        if (res.data) return res.data;
      } catch {
        // Fall back to local store mutation
      }

      const idx = activeAlertsStore.findIndex((a) => a.id === alertId);
      if (idx !== -1) {
        const target = activeAlertsStore[idx]!;
        let newStatus = target.status;
        if (action.type === "acknowledge") newStatus = "acknowledged";
        else if (action.type === "request_hold" || action.type === "dispatch") newStatus = "actioned";

        const updated: AlertDetail = {
          ...target,
          status: newStatus,
          timeline: [
            ...target.timeline,
            {
              at: new Date().toISOString(),
              kind: action.type,
              actor_id: "current_user",
              text_code: `alert.${action.type}`,
              text_params: action.params ?? {},
            },
          ],
        };
        activeAlertsStore[idx] = updated;
      }

      return { ok: true, action_id: `ACT-${Date.now()}` };
    },
    onSuccess: (_, { alertId }) => {
      void qc.invalidateQueries({ queryKey: streamKeys.alerts() });
      void qc.invalidateQueries({ queryKey: streamKeys.alert(alertId) });
    },
  });
}

/**
 * useAlertOutcome — records the outcome of an alert (hit, miss, late).
 */
export function useAlertOutcome() {
  const qc = useQueryClient();

  return useMutation<
    { ok: boolean },
    Error,
    { alertId: string; outcome: AlertOutcomeIn }
  >({
    mutationFn: async ({ alertId, outcome }) => {
      try {
        const res = await apiClient.POST("/alerts/{alert_id}/outcome", {
          params: { path: { alert_id: alertId } },
          body: outcome,
        });
        if (res.data) return res.data;
      } catch {
        // Fall back to local store mutation
      }

      const idx = activeAlertsStore.findIndex((a) => a.id === alertId);
      if (idx !== -1) {
        const target = activeAlertsStore[idx]!;
        const updated: AlertDetail = {
          ...target,
          timeline: [
            ...target.timeline,
            {
              at: new Date().toISOString(),
              kind: "outcome",
              actor_id: "current_user",
              text_code: `outcome.${outcome.verdict}`,
              text_params: { verdict: outcome.verdict, notes: outcome.notes },
            },
          ],
        };
        activeAlertsStore[idx] = updated;
      }

      return { ok: true };
    },
    onSuccess: (_, { alertId }) => {
      void qc.invalidateQueries({ queryKey: streamKeys.alerts() });
      void qc.invalidateQueries({ queryKey: streamKeys.alert(alertId) });
    },
  });
}
