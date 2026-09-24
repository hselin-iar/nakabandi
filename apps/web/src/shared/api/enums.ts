/**
 * String-literal unions mirroring packages/contracts/src/nakabandi_contracts/enums.py (LC-2,
 * normative). The backend's own response models intentionally type these fields as plain `str`
 * (looser API coupling — DOC 2 §2.4), so openapi-typescript never sees them as named schemas;
 * these are hand-kept in sync with enums.py instead of generated. Update both together.
 */

export const ROLES = [
  "i4c_analyst",
  "state_investigator",
  "district_officer",
  "bank_nodal",
  "demo_operator",
  "admin",
] as const;
export type Role = (typeof ROLES)[number];

export const ALERT_STATUSES = [
  "open",
  "acknowledged",
  "actioned",
  "escalated",
  "expired",
  "closed",
] as const;
export type AlertStatus = (typeof ALERT_STATUSES)[number];

export const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
export type Severity = (typeof SEVERITIES)[number];

export const VERDICTS = ["INTERCEPTABLE", "MARGINAL", "NOT_INTERCEPTABLE"] as const;
export type Verdict = (typeof VERDICTS)[number];

export const LADDER_LEVELS = ["NONE", "L1", "L2", "L3"] as const;
export type LadderLevel = (typeof LADDER_LEVELS)[number];

export const ACTION_TYPES = [
  "acknowledge",
  "request_hold",
  "notify_station",
  "dispatch",
  "override",
] as const;
export type ActionType = (typeof ACTION_TYPES)[number];

export const PERMISSIONS = [
  "VIEW_ALERTS",
  "ACKNOWLEDGE",
  "REQUEST_HOLD",
  "NOTIFY_STATION",
  "DISPATCH",
  "OVERRIDE",
  "MARK_OUTCOME",
  "CREATE_EVIDENCE",
  "VIEW_CASES",
  "VIEW_AUDIT",
  "VIEW_EVALUATION",
  "SIM_CONTROL",
] as const;
export type Permission = (typeof PERMISSIONS)[number];

export const CHANNELS = ["ATM", "BRANCH", "AGENT"] as const;
export type Channel = (typeof CHANNELS)[number];

export const COMPLAINT_CATEGORIES = [
  "digital_arrest",
  "investment_scam",
  "upi_phishing",
  "task_job_scam",
] as const;
export type ComplaintCategory = (typeof COMPLAINT_CATEGORIES)[number];

export const METRIC_NAMES = [
  "hit_rate_at_k",
  "precision_at_k",
  "lead_time_median",
  "brier",
  "interceptable_precision",
  "interceptable_recall",
  "dispatches_per_interception",
  "false_hold_rate",
  "cold_start_hit_rate",
  "abstention_rate",
] as const;
export type MetricName = (typeof METRIC_NAMES)[number];
