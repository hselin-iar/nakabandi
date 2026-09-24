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

// ---------------------------------------------------------------------------
// LC-4 Alert shapes & API contracts (DOC 2 §2.4, DOC 3 §M4)
// ---------------------------------------------------------------------------

export interface AlertTarget {
  kind: LocationKind;
  id: string;
  name?: string;
}

export interface AlertSummary {
  id: string;
  cluster_ref: string;
  target: AlertTarget;
  severity: Severity;
  confidence: number;
  status: AlertStatus;
  is_deferred: boolean;
  is_probe: boolean;
  window_start: SimTime;
  window_end: SimTime;
  expires_at: SimTime;
  ladder_level: LadderLevel;
  created_at: SimTime;
  masked: boolean;
}

export interface TimelineEntry {
  at: SimTime;
  kind: string;
  actor_id: string | null;
  text_code: string;
  text_params: Record<string, unknown>;
}

export interface AlertDetail extends AlertSummary {
  timeline: TimelineEntry[];
}

export interface AlertPage {
  items: AlertSummary[];
  next_cursor: string | null;
}

export interface AlertActionIn {
  type: ActionType;
  reason?: string;
  params?: {
    lien_amount_paise?: number;
    unit_id?: string;
    notes?: string;
    [key: string]: unknown;
  };
}

export interface AlertOutcomeIn {
  verdict: "hit" | "miss" | "late";
  notes?: string;
}

// ---------------------------------------------------------------------------
// Stream SSE event schema (DOC 2 §2.4, DOC 3 §M4)
// ---------------------------------------------------------------------------

export interface StreamEventBase {
  sim_time?: SimTime;
}

export interface AlertCreatedStreamEvent extends StreamEventBase {
  event: "alert.created";
  data: { alert_id: string; severity: Severity };
}

export interface AlertUpdatedStreamEvent extends StreamEventBase {
  event: "alert.updated";
  data: { alert_id: string; status: AlertStatus; ladder_level?: LadderLevel };
}

export interface DeliveryUpdatedStreamEvent extends StreamEventBase {
  event: "delivery.updated";
  data: { alert_id: string; delivery_id: string; status: string };
}

export interface HeatVersionStreamEvent extends StreamEventBase {
  event: "heat.version";
  data: { version: string };
}

export interface SimTimeStreamEvent extends StreamEventBase {
  event: "sim.time";
  data: { sim_time: SimTime };
}

export type StreamEvent =
  | AlertCreatedStreamEvent
  | AlertUpdatedStreamEvent
  | DeliveryUpdatedStreamEvent
  | HeatVersionStreamEvent
  | SimTimeStreamEvent;

// ---------------------------------------------------------------------------
// Geo & Analytics Heatmap shapes (DOC 2 §2.4, DOC 3 §M3)
// ---------------------------------------------------------------------------

export interface GeoRegion {
  id: string;
  name: string;
  state_id?: string;
  kind: "state" | "district";
  geojson?: Record<string, unknown>;
}

export interface GeoLocation {
  id: string;
  kind: LocationKind;
  bank_id: string;
  display_name: string;
  lat: number;
  lon: number;
  district_id: string;
  cell_id: string;
}

export interface HeatmapCell {
  id: string;
  kind: "district" | "cell" | "location";
  name?: string;
  lat: number;
  lon: number;
  score: number;
  event_count: number;
  amount_paise: Paise;
  suppressed?: boolean;
}

export interface HeatmapResponse {
  layer: "live" | "potential";
  level: Resolution;
  generated_at: SimTime;
  version: string;
  cells: HeatmapCell[];
}

// ---------------------------------------------------------------------------
// API Paths contract (openapi-fetch)
// ---------------------------------------------------------------------------

export interface paths {
  "/alerts": {
    get: {
      parameters?: {
        query?: {
          status?: AlertStatus;
          severity?: Severity;
          district_id?: string;
          cursor?: string;
          limit?: number;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": AlertPage;
          };
        };
      };
    };
  };
  "/alerts/{alert_id}": {
    get: {
      parameters: {
        path: { alert_id: string };
      };
      responses: {
        200: {
          content: {
            "application/json": AlertDetail;
          };
        };
      };
    };
  };
  "/alerts/{alert_id}/actions": {
    post: {
      parameters: {
        path: { alert_id: string };
      };
      requestBody: {
        content: {
          "application/json": AlertActionIn;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": { ok: boolean; action_id: string };
          };
        };
      };
    };
  };
  "/alerts/{alert_id}/outcome": {
    post: {
      parameters: {
        path: { alert_id: string };
      };
      requestBody: {
        content: {
          "application/json": AlertOutcomeIn;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": { ok: boolean };
          };
        };
      };
    };
  };
  "/stream": {
    get: {
      responses: {
        200: {
          content: {
            "text/event-stream": string;
          };
        };
      };
    };
  };
  "/geo/regions": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": GeoRegion[];
          };
        };
      };
    };
  };
  "/geo/locations": {
    get: {
      parameters?: {
        query?: {
          bbox?: string;
          kind?: LocationKind;
          bank_id?: string;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": GeoLocation[];
          };
        };
      };
    };
  };
  "/analytics/heatmap": {
    get: {
      parameters?: {
        query?: {
          layer?: "live" | "potential";
          level?: Resolution;
          from?: string;
          to?: string;
          category?: ComplaintCategory;
          amount_band?: string;
          min_confidence?: number;
          bbox?: string;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": HeatmapResponse;
          };
        };
      };
    };
  };
  "/ingest/complaints": {
    post: {
      requestBody: {
        content: {
          "application/json": ComplaintBatch;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": IngestResponse;
          };
        };
      };
    };
  };
  "/ingest/hops": {
    post: {
      requestBody: {
        content: {
          "application/json": HopBatch;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": IngestResponse;
          };
        };
      };
    };
  };
  "/ingest/cashout-observations": {
    post: {
      requestBody: {
        content: {
          "application/json": CashOutObservationBatch;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": IngestResponse;
          };
        };
      };
    };
  };
  "/ingest/registry": {
    post: {
      requestBody: {
        content: {
          "application/json": RegistryUpdate;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": IngestResponse;
          };
        };
      };
    };
  };
  "/ingest/tick": {
    post: {
      requestBody: {
        content: {
          "application/json": Tick;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": { ok: boolean; sim_time: SimTime };
          };
        };
      };
    };
  };
}

