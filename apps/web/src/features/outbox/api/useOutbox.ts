/**
 * useOutbox.ts — Fixture data + TanStack Query hook for Outbox Deliveries.
 * DOC 3 §M4 (outbox, channels) · DOC 4 Step C7
 *
 * STUB STRATEGY: fixture matching the /outbox documented endpoint shape.
 * Swap for a real GET /outbox when Track A Step A8 lands.
 */

import { useQuery } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DeliveryStatus =
  | "pending"
  | "delivered"
  | "failed"
  | "retrying";

export type DeliveryChannel =
  | "bank_webhook"
  | "sms"
  | "outbox_sms"
  | "email";

export interface Delivery {
  delivery_id: string;
  alert_id: string;
  action_id: string;
  channel: DeliveryChannel;
  status: DeliveryStatus;
  /** Rendered notification body (plain text or JSON) */
  rendered_body: string;
  idempotency_key: string;
  attempt_count: number;
  created_at: string;
  delivered_at: string | null;
  last_error: string | null;
}

// ---------------------------------------------------------------------------
// Fixture
// ---------------------------------------------------------------------------

export const FIXTURE_DELIVERIES: Delivery[] = [
  {
    delivery_id: "DLV-0001",
    alert_id:    "ALT-2026-001",
    action_id:   "ACT-2026-001",
    channel:     "bank_webhook",
    status:      "delivered",
    rendered_body: JSON.stringify({
      event:        "hold_requested",
      alert_id:     "ALT-2026-001",
      account_ref:  "ICIC-10293847561",
      amount_paise: 1800000,
      expires_at:   "2026-09-25T12:00:00Z",
    }, null, 2),
    idempotency_key: "ALT-2026-001:ACT-2026-001:bank_webhook",
    attempt_count:   1,
    created_at:      "2026-09-23T11:00:00Z",
    delivered_at:    "2026-09-23T11:00:02Z",
    last_error:      null,
  },
  {
    delivery_id: "DLV-0002",
    alert_id:    "ALT-2026-001",
    action_id:   "ACT-2026-001",
    channel:     "sms",
    status:      "delivered",
    rendered_body:
      "NAKABANDI ALERT: Hold request sent for ALT-2026-001. " +
      "Cluster CLUSTER-2026-081. Target: Sector 18 ATM, Noida. " +
      "Approved by state_investigator_1.",
    idempotency_key: "ALT-2026-001:ACT-2026-001:sms",
    attempt_count:   1,
    created_at:      "2026-09-23T11:00:00Z",
    delivered_at:    "2026-09-23T11:00:04Z",
    last_error:      null,
  },
  {
    delivery_id: "DLV-0003",
    alert_id:    "ALT-2026-002",
    action_id:   "ACT-2026-002",
    channel:     "bank_webhook",
    status:      "failed",
    rendered_body: JSON.stringify({
      event:        "hold_requested",
      alert_id:     "ALT-2026-002",
      account_ref:  "AXIS-77889900112",
      amount_paise: 950000,
      expires_at:   "2026-09-26T08:00:00Z",
    }, null, 2),
    idempotency_key: "ALT-2026-002:ACT-2026-002:bank_webhook",
    attempt_count:   3,
    created_at:      "2026-09-23T14:30:00Z",
    delivered_at:    null,
    last_error:      "Connection refused: bank-sim returned 503",
  },
  {
    delivery_id: "DLV-0004",
    alert_id:    "ALT-2026-003",
    action_id:   "ACT-2026-003",
    channel:     "outbox_sms",
    status:      "retrying",
    rendered_body:
      "NAKABANDI ALERT: Station notification for ALT-2026-003. " +
      "Dispatch unit DU-GBN-07 to Sector 62, Noida.",
    idempotency_key: "ALT-2026-003:ACT-2026-003:outbox_sms",
    attempt_count:   2,
    created_at:      "2026-09-24T00:15:00Z",
    delivered_at:    null,
    last_error:      "SMS provider timeout after 10 s",
  },
  {
    delivery_id: "DLV-0005",
    alert_id:    "ALT-2026-003",
    action_id:   "ACT-2026-003",
    channel:     "email",
    status:      "pending",
    rendered_body:
      "Subject: [NAKABANDI] Alert ALT-2026-003 — action required\n\n" +
      "An interception action has been recorded. Please review the alert " +
      "detail in the Nakabandi dashboard.",
    idempotency_key: "ALT-2026-003:ACT-2026-003:email",
    attempt_count:   0,
    created_at:      "2026-09-24T00:15:00Z",
    delivered_at:    null,
    last_error:      null,
  },
];

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useOutboxDeliveries() {
  return useQuery<Delivery[]>({
    queryKey: ["outbox-deliveries"],
    queryFn: () => Promise.resolve(FIXTURE_DELIVERIES),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
