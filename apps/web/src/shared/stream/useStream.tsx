/**
 * useStream.ts — SSE subscriber with polling fallback and sim-time clock store.
 * DOC 3 Web App Shell:
 *   useStream(): opens GET /api/v1/stream; invalidates TanStack Query keys on
 *   events; falls back to polling every 5 s after 20 s with no event or
 *   heartbeat; shows an amber connection dot when degraded.
 *   useSimTime(): returns current sim time from the stream.
 *
 * Injected-time invariant: sim time is ONLY updated by the stream/poll —
 * no component reads Date.now() for sim purposes.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamKeys, SSE_EVENTS } from "./streamKeys";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ConnectionStatus = "streaming" | "polling" | "disconnected";

interface StreamContextValue {
  status: ConnectionStatus;
  simTime: string | null;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const StreamContext = createContext<StreamContextValue>({
  status: "disconnected",
  simTime: null,
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** After this many ms with no event/heartbeat, fall back to polling. */
const INACTIVITY_MS = 20_000;
/** Polling interval when SSE is degraded. */
const POLL_INTERVAL_MS = 5_000;
/** Max SSE reconnect backoff. */
const MAX_BACKOFF_MS = 30_000;
/** Debounce heat.version query invalidation. */
const HEAT_DEBOUNCE_MS = 1_000;

// ---------------------------------------------------------------------------
// StreamProvider
// ---------------------------------------------------------------------------

export function StreamProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [simTime, setSimTime] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const heatDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(1_000);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);

  const clearInactivity = useCallback(() => {
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = null;
    }
  }, []);

  const clearPoll = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const invalidateHeat = useCallback(() => {
    if (heatDebounceRef.current) clearTimeout(heatDebounceRef.current);
    heatDebounceRef.current = setTimeout(() => {
      void qc.invalidateQueries({ queryKey: streamKeys.heatmap() });
    }, HEAT_DEBOUNCE_MS);
  }, [qc]);

  // Poll mode: hit a lightweight /api/v1/alerts endpoint to keep data fresh.
  const startPolling = useCallback(() => {
    if (pollTimerRef.current) return; // already polling
    setStatus("polling");
    pollTimerRef.current = setInterval(() => {
      void qc.invalidateQueries({ queryKey: streamKeys.alerts() });
      void qc.invalidateQueries({ queryKey: streamKeys.deliveries() });
    }, POLL_INTERVAL_MS);
  }, [qc]);

  const resetInactivityTimer = useCallback(() => {
    clearInactivity();
    inactivityTimerRef.current = setTimeout(() => {
      if (!isMountedRef.current) return;
      // No event for 20 s — degrade to polling.
      startPolling();
    }, INACTIVITY_MS);
  }, [clearInactivity, startPolling]);

  const handleEvent = useCallback(
    (eventType: string, data: string) => {
      resetInactivityTimer();
      clearPoll(); // we're receiving events, so stop poll if it was running
      setStatus("streaming");

      try {
        switch (eventType) {
          case SSE_EVENTS.ALERT_CREATED:
          case SSE_EVENTS.ALERT_UPDATED: {
            const payload = JSON.parse(data) as { alert_id?: string };
            if (payload.alert_id) {
              void qc.invalidateQueries({
                queryKey: streamKeys.alert(payload.alert_id),
              });
            }
            void qc.invalidateQueries({ queryKey: streamKeys.alerts() });
            break;
          }
          case SSE_EVENTS.DELIVERY_UPDATED: {
            void qc.invalidateQueries({ queryKey: streamKeys.deliveries() });
            break;
          }
          case SSE_EVENTS.HEAT_VERSION: {
            invalidateHeat();
            break;
          }
          case SSE_EVENTS.SIM_TIME: {
            const payload = JSON.parse(data) as { sim_time?: string };
            if (payload.sim_time) {
              setSimTime(payload.sim_time);
            }
            break;
          }
          case SSE_EVENTS.HEARTBEAT:
            // Just keeps the inactivity timer alive.
            break;
        }
      } catch {
        // Malformed event data — ignore.
      }
    },
    [qc, resetInactivityTimer, clearPoll, invalidateHeat],
  );

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    // Close any existing connection.
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const es = new EventSource("/api/v1/stream");
    esRef.current = es;

    es.onopen = () => {
      if (!isMountedRef.current) return;
      backoffRef.current = 1_000; // reset backoff on successful connect
      clearPoll();
      setStatus("streaming");
      resetInactivityTimer();
    };

    es.onerror = () => {
      if (!isMountedRef.current) return;
      es.close();
      esRef.current = null;
      clearInactivity();
      startPolling();

      // Exponential backoff reconnect.
      const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS);
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      reconnectTimerRef.current = setTimeout(connect, delay);
    };

    // Listen for all known event types.
    const eventTypes = Object.values(SSE_EVENTS);
    for (const type of eventTypes) {
      es.addEventListener(type, (e) => {
        handleEvent(type, (e as MessageEvent<string>).data ?? "{}");
      });
    }

    // Default message handler for unnamed events.
    es.onmessage = (e) => {
      handleEvent(SSE_EVENTS.HEARTBEAT, e.data ?? "{}");
    };
  }, [
    clearInactivity,
    clearPoll,
    handleEvent,
    resetInactivityTimer,
    startPolling,
  ]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      esRef.current?.close();
      clearInactivity();
      clearPoll();
      if (heatDebounceRef.current) clearTimeout(heatDebounceRef.current);
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [connect, clearInactivity, clearPoll]);

  const value: StreamContextValue = { status, simTime };

  return (
    <StreamContext.Provider value={value}>{children}</StreamContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Returns the current SSE connection status and latest sim time.
 * Must be used inside StreamProvider.
 */
export function useStream(): StreamContextValue {
  return useContext(StreamContext);
}

/**
 * Returns the current simulator time ISO string from the SSE stream.
 * Components MUST use this instead of Date.now() for sim-time display.
 * Returns null when no sim.time event has arrived yet.
 */
export function useSimTime(): string | null {
  return useContext(StreamContext).simTime;
}
