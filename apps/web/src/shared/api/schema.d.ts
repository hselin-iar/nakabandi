/**
 * GENERATED — do not hand-edit. Regenerate with `npm run types`.
 *
 * Source: packages/contracts/src/nakabandi_contracts/{enums,ingest}.py
 * Until the FastAPI server exposes its OpenAPI document (Track A Step A2),
 * this file is generated from the LC-1 Pydantic models and LC-2 enums.
 * Once the OpenAPI spec exists, `npm run types` will call openapi-typescript.
 */

// ---------------------------------------------------------------------------
// LC-2 Enums (nakabandi_contracts.enums)
// ---------------------------------------------------------------------------

export type Resolution = "district" | "cell" | "location";

export type Channel = "ATM" | "BRANCH" | "AGENT";

export type LocationKind = "ATM" | "BRANCH" | "AGENT";

export type ComplaintCategory =
  | "digital_arrest"
  | "investment_scam"
  | "upi_phishing"
  | "task_job_scam";

export type Role =
  | "i4c_analyst"
  | "state_investigator"
  | "district_officer"
  | "bank_nodal"
  | "demo_operator"
  | "admin";

export type AlertStatus =
  | "open"
  | "acknowledged"
  | "actioned"
  | "escalated"
  | "expired"
  | "closed";

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type Verdict = "INTERCEPTABLE" | "MARGINAL" | "NOT_INTERCEPTABLE";

export type LadderLevel = "NONE" | "L1" | "L2" | "L3";

export type ActionType =
  | "acknowledge"
  | "request_hold"
  | "notify_station"
  | "dispatch"
  | "override";

export type Permission =
  | "VIEW_ALERTS"
  | "ACKNOWLEDGE"
  | "REQUEST_HOLD"
  | "NOTIFY_STATION"
  | "DISPATCH"
  | "OVERRIDE"
  | "MARK_OUTCOME"
  | "CREATE_EVIDENCE"
  | "VIEW_CASES"
  | "VIEW_AUDIT"
  | "VIEW_EVALUATION"
  | "SIM_CONTROL";

export type MetricName =
  | "hit_rate_at_k"
  | "precision_at_k"
  | "lead_time_median"
  | "brier"
  | "interceptable_precision"
  | "interceptable_recall"
  | "dispatches_per_interception"
  | "false_hold_rate"
  | "cold_start_hit_rate"
  | "abstention_rate";

// ---------------------------------------------------------------------------
// LC-2 Principal (DOC 3 Shared Kernel) — shape the auth module produces
// ---------------------------------------------------------------------------

/** Scope restricts a role's visible data to a district or state. */
export interface Scope {
  state_id?: string;
  district_id?: string;
}

/** Authenticated principal produced by the auth dependency. */
export interface Principal {
  user_id: string;
  username: string;
  role: Role;
  scope: Scope;
  permissions: Permission[];
}

// ---------------------------------------------------------------------------
// LC-1 Ingest shapes (nakabandi_contracts.ingest) — used by bank-sim / world-sim
// ---------------------------------------------------------------------------

export type SimTime = string; // ISO-8601 datetime with timezone

export type Id = string;

export type Paise = number; // positive integer

export interface AccountIn {
  account_ref: string;
  bank_id: Id;
  home_location_id?: Id | null;
}

export interface ComplaintIn {
  external_ref: string;
  category: ComplaintCategory;
  amount_paise: Paise;
  victim_district_id: Id;
  credited_at: SimTime;
  reported_event_at: SimTime;
  observed_at: SimTime;
  layer1_account: AccountIn;
}

export interface ComplaintBatch {
  batch_id: string;
  idempotency_key: string;
  sim_time: SimTime;
  items: ComplaintIn[];
}

export interface HopIn {
  complaint_external_ref: string;
  from_account: AccountIn;
  to_account: AccountIn;
  amount_paise: Paise;
  layer: number;
  event_at: SimTime;
  observed_at: SimTime;
}

export interface HopBatch {
  batch_id: string;
  idempotency_key: string;
  sim_time: SimTime;
  items: HopIn[];
}

export interface CashOutObsIn {
  account_ref: string;
  location_id: Id;
  channel: Channel;
  amount_paise: Paise;
  event_at: SimTime;
  observed_at: SimTime;
  source: "bank_report" | "police_report";
}

export interface CashOutObservationBatch {
  batch_id: string;
  idempotency_key: string;
  sim_time: SimTime;
  items: CashOutObsIn[];
}

export interface RegistryLocation {
  id: Id;
  kind: LocationKind;
  bank_id: Id;
  lat: number;
  lon: number;
  district_id: Id;
  cell_id: Id;
  source: "osm" | "synthetic";
  display_name: string;
  area_type: "urban" | "semi_urban" | "rural";
  activity_index: number;
}

export interface RegistryUnit {
  id: Id;
  kind: "cyber_cell" | "station" | "patrol";
  district_id: Id;
  lat: number;
  lon: number;
  status: string;
}

export interface RegistryUpdate {
  version: string;
  banks: Record<string, unknown>[];
  regions: Record<string, unknown>[];
  cells: Record<string, unknown>[];
  locations: RegistryLocation[];
  units: RegistryUnit[];
}

export interface Tick {
  sim_time: SimTime;
}

export interface RejectedItem {
  index: number;
  code: string;
  message: string;
}

export interface IngestResponse {
  accepted: number;
  rejected: RejectedItem[];
  sim_time: SimTime;
}
