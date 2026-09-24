/**
 * useDemoControl.ts — API hooks & client for the World-Sim Control API through /sim-control.
 * DOC 3 M1 · LC-8 · DOC 2 §2.2 / §2.7 · DOC 4 Step C8
 *
 * All control API calls MUST go through the /sim-control/* proxy path (never a direct
 * world-sim URL) since that is the only path enforcing demo_operator authentication
 * via reverse-proxy forward_auth (DOC 2 §2.2).
 */

import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  SimulatorStatus,
  StartRequest,
  SpeedRequest,
  ResetRequest,
  InjectClusterRequest,
  ProxiedRequestLogEntry,
  DemoUser,
} from "../types";

/** Proxied control base path (DOC 3 LC-8). */
export const SIM_CONTROL_PROXY_PATH = "/sim-control";

/** Initial fixture status while waiting for first status poll (DOC 4 C8 stub strategy). */
export const FIXTURE_STATUS: SimulatorStatus = {
  state: "running",
  sim_time: 1718000000,
  speed: 1.0,
  seed: 42,
  scenario: "free",
  counts: {
    complaints: 128,
    cashouts: 34,
    ticks: 890,
  },
  last_error: null,
};

// Global in-memory log buffer so history persists across re-renders
let globalLogCounter = 0;
const globalRequestLog: ProxiedRequestLogEntry[] = [];
const logSubscribers = new Set<(logs: ProxiedRequestLogEntry[]) => void>();

function appendLog(entry: Omit<ProxiedRequestLogEntry, "id" | "timestamp">) {
  globalLogCounter += 1;
  const newEntry: ProxiedRequestLogEntry = {
    ...entry,
    id: `req-${Date.now()}-${globalLogCounter}`,
    timestamp: new Date().toISOString(),
  };
  globalRequestLog.unshift(newEntry);
  if (globalRequestLog.length > 100) {
    globalRequestLog.pop();
  }
  logSubscribers.forEach((cb) => cb([...globalRequestLog]));
  return newEntry;
}

/** Helper that performs fetch through the /sim-control proxy and logs the request. */
async function callProxy<T = unknown>(
  subpath: string,
  options?: RequestInit,
  payload?: unknown,
): Promise<T> {
  const fullPath = `${SIM_CONTROL_PROXY_PATH}${subpath}`;
  const method = (options?.method ?? "GET").toUpperCase() as "GET" | "POST";

  const fetchOptions: RequestInit = {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Nakabandi-CSRF": "1",
      ...(options?.headers ?? {}),
    },
  };

  if (payload !== undefined) {
    fetchOptions.body = JSON.stringify(payload);
  }

  try {
    const res = await fetch(fullPath, fetchOptions);
    let data: unknown = null;
    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      data = await res.json().catch(() => null);
    } else {
      data = await res.text().catch(() => null);
    }

    appendLog({
      method,
      path: fullPath,
      payload,
      status: res.status,
      response: data,
    });

    if (!res.ok) {
      const errDetail =
        typeof data === "object" && data !== null && "detail" in data
          ? String((data as { detail: unknown }).detail)
          : `HTTP ${res.status}`;
      throw new Error(errDetail);
    }

    return data as T;
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    // If not already logged via response error
    if (!options?.signal?.aborted) {
      appendLog({
        method,
        path: fullPath,
        payload,
        status: 0,
        error: errorMsg,
      });
    }
    throw err;
  }
}

/** Hook to monitor the proxied request audit log. */
export function useProxiedRequestLog() {
  const [logs, setLogs] = useState<ProxiedRequestLogEntry[]>([...globalRequestLog]);

  useEffect(() => {
    logSubscribers.add(setLogs);
    return () => {
      logSubscribers.delete(setLogs);
    };
  }, []);

  const clearLog = useCallback(() => {
    globalRequestLog.length = 0;
    setLogs([]);
  }, []);

  return { logs, clearLog };
}

/** Fetch demo users from /api/v1/auth/demo-users (or /auth/demo-users). */
export function useDemoUsers() {
  return useQuery<DemoUser[]>({
    queryKey: ["auth", "demo-users"],
    queryFn: async () => {
      try {
        const res = await fetch("/api/v1/auth/demo-users", {
          headers: { "X-Nakabandi-CSRF": "1" },
        });
        if (res.ok) {
          return (await res.json()) as DemoUser[];
        }
      } catch {
        // Fall back to alternative path
      }

      try {
        const res2 = await fetch("/auth/demo-users");
        if (res2.ok) {
          return (await res2.json()) as DemoUser[];
        }
      } catch {
        // Fallback
      }

      // Default empty list if endpoint is unavailable
      return [];
    },
    staleTime: 60_000,
  });
}

/** Main simulator control hook wired to /sim-control/* proxy. */
export function useDemoControl() {
  const queryClient = useQueryClient();
  const { logs, clearLog } = useProxiedRequestLog();
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Poll simulator status through /sim-control/status
  const statusQuery = useQuery<SimulatorStatus>({
    queryKey: ["sim-control", "status"],
    queryFn: async () => {
      try {
        return await callProxy<SimulatorStatus>("/status", { method: "GET" });
      } catch {
        // Fallback to fixture if server/runner is not yet running
        return FIXTURE_STATUS;
      }
    },
    refetchInterval: import.meta.env.MODE === "test" ? false : 3000,
    refetchOnWindowFocus: import.meta.env.MODE !== "test",
  });

  const invalidateStatus = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["sim-control", "status"] });
  }, [queryClient]);

  // Start
  const startMutation = useMutation({
    mutationFn: (req: StartRequest) =>
      callProxy<{ status: string; run_id: string }>("/start", { method: "POST" }, req),
    onSuccess: invalidateStatus,
  });

  // Pause
  const pauseMutation = useMutation({
    mutationFn: () =>
      callProxy<{ status: string }>("/pause", { method: "POST" }),
    onSuccess: invalidateStatus,
  });

  // Resume
  const resumeMutation = useMutation({
    mutationFn: () =>
      callProxy<{ status: string }>("/resume", { method: "POST" }),
    onSuccess: invalidateStatus,
  });

  // Speed (capped at 60x per DOC 2 §2.7)
  const speedMutation = useMutation({
    mutationFn: (req: SpeedRequest) => {
      const factor = Math.min(Math.max(req.factor, 1), 60);
      return callProxy<{ status: string; speed: number }>("/speed", { method: "POST" }, { factor });
    },
    onSuccess: invalidateStatus,
  });

  // Reset (admin only in hosted mode)
  const resetMutation = useMutation({
    mutationFn: (req: ResetRequest) =>
      callProxy<{ status: string; seed: number }>("/reset", { method: "POST" }, req),
    onSuccess: invalidateStatus,
  });

  // Inject cluster
  const injectClusterMutation = useMutation({
    mutationFn: (req: InjectClusterRequest) =>
      callProxy<{ status: string; cluster_id: string }>(
        "/inject-cluster",
        { method: "POST" },
        req,
      ),
    onSuccess: invalidateStatus,
  });

  return {
    status: statusQuery.data ?? FIXTURE_STATUS,
    isLoading: statusQuery.isLoading,
    isError: statusQuery.isError,
    error: statusQuery.error,
    refetchStatus: statusQuery.refetch,
    // Actions
    startSimulation: startMutation.mutateAsync,
    isStarting: startMutation.isPending,
    pauseSimulation: pauseMutation.mutateAsync,
    isPausing: pauseMutation.isPending,
    resumeSimulation: resumeMutation.mutateAsync,
    isResuming: resumeMutation.isPending,
    setSpeed: speedMutation.mutateAsync,
    isSettingSpeed: speedMutation.isPending,
    resetSimulation: resetMutation.mutateAsync,
    isResetting: resetMutation.isPending,
    injectCluster: injectClusterMutation.mutateAsync,
    isInjecting: injectClusterMutation.isPending,
    injectError: injectClusterMutation.error,
    // Audit log
    requestLog: logs,
    clearRequestLog: clearLog,
  };
}
