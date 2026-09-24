/**
 * types.ts — Type definitions for Cases & Case Bundling.
 * DOC 3 §S1 & DOC 4 §C6
 */

import type { ClusterGraphData } from "../clusters/types";

export type CaseStatus =
  | "bundled"
  | "under_investigation"
  | "fir_recommended"
  | "closed";

export interface CaseAccount {
  /** Full account reference (only visible to LEA roles) */
  account_ref: string;
  /** Server-masked reference (e.g. "•••• 4821") */
  masked_ref: string;
  bank: string;
  complaint_count: number;
  role?: "mule" | "victim" | "aggregator" | "exit";
  volume_paise?: number;
}

export interface CaseLocation {
  id: string;
  name: string;
  count: number;
  last_at: string;
  state?: string;
  district?: string;
}

export interface CaseTimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  description?: string;
  dotClass?: string;
}

export interface Case {
  id: string;
  cluster_ref: string;
  complaint_count: number;
  victim_count: number;
  total_paise: number;
  first_seen: string;
  last_seen: string;
  status: CaseStatus;
  accounts: CaseAccount[];
  top_locations: CaseLocation[];
  sub_communities?: Array<{
    id: string;
    label: string;
    account_count: number;
  }>;
  timeline: CaseTimelineEvent[];
  /** Consolidated factual case brief in markdown */
  brief_md: string;
  /** Topology of the linked cluster for visualization */
  graph_data?: ClusterGraphData;
  single_complaint?: boolean;
}

export interface CaseFilter {
  status?: string;
  search?: string;
  singleComplaintOnly?: boolean;
}
