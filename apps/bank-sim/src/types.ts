/**
 * types.ts — LC-6 Bank webhook and callback shapes.
 * DOC 3 Locked Contract LC-6. DO NOT add fields beyond this contract.
 * Contract Change Process required for any modification (DOC 3, DOC 4 §4.1b).
 */

/** Common fields for all webhook bodies. */
interface WebhookBodyBase {
  kind: "alert_notice" | "hold_request";
  /** ULID — unique per logical event (not per delivery attempt). */
  request_id: string;
  alert_ref: string;
  bank_id: string;
  /** Masked (last-4 only) for alert_notice; full for hold_request. */
  account_ref: string;
  complaint_ref: string;
  /** ISO-8601 sim time at which the event occurred. */
  sim_time: string;
}

/** alert_notice: informs the bank that an alert has been raised. */
export interface AlertNoticeBody extends WebhookBodyBase {
  kind: "alert_notice";
}

/** hold_request: asks the bank to apply a time-boxed lien. */
export interface HoldRequestBody extends WebhookBodyBase {
  kind: "hold_request";
  /** Integer paise. The amount under dispute. */
  disputed_amount_paise: number;
  /** Integer paise. Must be > 0 and <= disputed_amount_paise. */
  proposed_lien_paise: number;
  /** ISO-8601 sim time. Lien auto-releases after this. */
  expires_at_sim: string;
  /** ISO-8601 sim time. Earliest permitted bank review. */
  review_at_sim: string;
  /** Role of the officer who requested the hold. */
  requested_by_role: string;
}

/** Union type — discriminated on `kind`. */
export type WebhookBody = AlertNoticeBody | HoldRequestBody;

/** Callback body sent from bank-sim to the API (LC-6). */
export interface CallbackBody {
  request_id: string;
  status: "applied" | "rejected" | "released";
  /** Set when status is "applied". Integer paise. */
  applied_amount_paise?: number;
  /** ISO-8601 sim time of the decision. */
  at_sim: string;
  note?: string;
}

/** Stored row in the requests table. */
export interface RequestRow {
  request_id: string;
  kind: "alert_notice" | "hold_request";
  body_json: string;
  status: "pending" | "applied" | "rejected" | "released";
  received_at: string;
}

/** Stored row in the liens table. */
export interface LienRow {
  request_id: string;
  applied_paise: number;
  expires_at_sim: string;
  applied_at_sim: string;
  released: 0 | 1;
}

/** Stored row in the callbacks table. */
export interface CallbackRow {
  id: number;
  request_id: string;
  status: "applied" | "rejected" | "released";
  payload_json: string;
  sent_at: string;
  success: 0 | 1;
  attempts: number;
}
