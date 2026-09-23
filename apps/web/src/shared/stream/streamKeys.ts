/**
 * streamKeys.ts — TanStack Query key factory for SSE-driven invalidation.
 * DOC 3 Web App Shell: shared/stream/streamKeys.ts
 *
 * These constants are the contract between the SSE event types and the Query
 * cache keys. Components use these same keys in useQuery; the stream invalidates
 * them on matching events.
 */

export const streamKeys = {
  /** Base key for all alert-related queries. */
  alerts: () => ["alerts"] as const,
  /** A specific alert by ID. */
  alert: (id: string) => ["alerts", id] as const,
  /** Delivery / outbox entries. */
  deliveries: () => ["deliveries"] as const,
  /** Heatmap data (debounced on heat.version). */
  heatmap: () => ["heatmap"] as const,
} as const;

// ---------------------------------------------------------------------------
// SSE event type names (must match the API's stream protocol — DOC 3 §A7)
// ---------------------------------------------------------------------------

export const SSE_EVENTS = {
  ALERT_CREATED: "alert.created",
  ALERT_UPDATED: "alert.updated",
  DELIVERY_UPDATED: "delivery.updated",
  HEAT_VERSION: "heat.version",
  SIM_TIME: "sim.time",
  /** A7 stream.py sends this as an SSE comment event (`:heartbeat`). */
  HEARTBEAT: ":heartbeat",
} as const;

export type SseEventType = (typeof SSE_EVENTS)[keyof typeof SSE_EVENTS];
