/**
 * Hand-maintained convenience layer over the generated schema.d.ts (never hand-edit that file —
 * openapi-typescript regenerates it via `npm run types`, DOC 4 Sync 4). Re-exports the backend's
 * real response shapes under names the rest of the app already used, plus the two types the API
 * never returns as their own JSON schema: `Principal` (assembled client-side from GET /auth/me)
 * and `Scope` (the backend types it as a loose dict; this is its real shape, access/domain/
 * principal.py's Scope dataclass).
 */

import type { components } from "./schema.d.ts";
import type { Permission, Role } from "./enums.ts";

export type Scope = {
  state_id?: string | null;
  district_id?: string | null;
  bank_id?: string | null;
};

/** Assembled from GET /auth/me's MeResponse (role/permissions are typed here, not by the API). */
export interface Principal {
  user_id: string;
  name: string;
  role: Role;
  scope: Scope;
  permissions: Permission[];
}

export type AlertSummary = components["schemas"]["AlertSummaryModel"];
export type AlertDetail = components["schemas"]["AlertDetailModel"];
export type ActionIn = components["schemas"]["ActionInModel"];
export type ActionModel = components["schemas"]["ActionModel"];
export type OutcomeView = components["schemas"]["OutcomeView"];
export type OutcomeIn = components["schemas"]["OutcomeIn"];
export type DeliveryModel = components["schemas"]["DeliveryModel"];
export type ForecastModel = components["schemas"]["ForecastModel"];
export type InterceptAssessmentModel = components["schemas"]["InterceptAssessmentModel"];
export type TimelineEntryModel = components["schemas"]["TimelineEntryModel"];

export type Case = components["schemas"]["CaseModel"];
export type CasePage = components["schemas"]["CasePageModel"];
export type AccountRef = components["schemas"]["AccountRefModel"];
export type LocationHit = components["schemas"]["LocationHitModel"];
export type Cluster = components["schemas"]["ClusterModel"];
export type ClusterNode = components["schemas"]["ClusterNodeModel"];
export type ClusterEdge = components["schemas"]["ClusterEdgeModel"];

export type EvidencePack = components["schemas"]["EvidencePackModel"];

export type AuditEntry = components["schemas"]["AuditEntryResponse"];
export type VerifyResponse = components["schemas"]["VerifyResponse"];

export type OutboxPage = components["schemas"]["OutboxPage"];
export type Delivery = components["schemas"]["DeliveryView"];

export type SystemMetrics = components["schemas"]["MetricsResponse"];
export type LatencyView = components["schemas"]["LatencyView"];

export type MeResponse = components["schemas"]["MeResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type LoginResponse = components["schemas"]["LoginResponse"];
export type DemoUserResponse = components["schemas"]["DemoUserResponse"];
