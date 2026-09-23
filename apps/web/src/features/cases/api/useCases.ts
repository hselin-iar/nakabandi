/**
 * useCases.ts — TanStack Query hooks and hand-written fixtures for Cases.
 * DOC 3 §S1 & DOC 4 §C6
 *
 * Invariant: The brief states facts and ends with:
 * "Whether to register an FIR is the investigating officer's decision."
 * It never asserts guilt or names real persons.
 */

import { useQuery } from "@tanstack/react-query";
import type { Case, CaseFilter } from "../types";
import {
  FIXTURE_CLUSTER_STANDARD,
  FIXTURE_CLUSTER_BIG,
  FIXTURE_CLUSTER_SINGLE,
} from "../../clusters/api/useClusters";

export const REQUIRED_FIR_DISCLAIMER =
  "Whether to register an FIR is the investigating officer's decision.";

// ---------------------------------------------------------------------------
// Fixture 1: Multi-Complaint Digital Arrest Bundle (CASE-2026-001)
// ---------------------------------------------------------------------------
export const FIXTURE_CASE_1: Case = {
  id: "CASE-2026-001",
  cluster_ref: "CLUSTER-2026-081",
  complaint_count: 5,
  victim_count: 2,
  total_paise: 45_00_000_00, // ₹45,00,000
  first_seen: "2026-01-14T09:30:00Z",
  last_seen: "2026-01-15T11:45:00Z",
  status: "bundled",
  single_complaint: false,
  accounts: [
    {
      account_ref: "ICIC-10293847561",
      masked_ref: "ICIC-••••-7561",
      bank: "ICICI",
      complaint_count: 3,
      role: "mule",
      volume_paise: 18_00_000_00,
    },
    {
      account_ref: "PUNB-55443322110",
      masked_ref: "PUNB-••••-2110",
      bank: "PNB",
      complaint_count: 2,
      role: "mule",
      volume_paise: 27_00_000_00,
    },
    {
      account_ref: "AXIS-77889900112",
      masked_ref: "AXIS-••••-0112",
      bank: "AXIS",
      complaint_count: 0,
      role: "mule",
      volume_paise: 35_00_000_00,
    },
    {
      account_ref: "KKBK-33221144556",
      masked_ref: "KKBK-••••-4556",
      bank: "KOTAK",
      complaint_count: 0,
      role: "aggregator",
      volume_paise: 42_00_000_00,
    },
  ],
  top_locations: [
    {
      id: "LOC-NOIDA-SEC18",
      name: "Sector 18 ATM Cluster, Noida",
      count: 4,
      last_at: "2026-01-15T11:30:00Z",
      state: "UP",
      district: "GBN",
    },
    {
      id: "LOC-NOIDA-SEC62",
      name: "Sector 62 Commercial Hub, Noida",
      count: 2,
      last_at: "2026-01-15T10:15:00Z",
      state: "UP",
      district: "GBN",
    },
    {
      id: "LOC-LKO-HAZRATGANJ",
      name: "Hazratganj Branch Terminal, Lucknow",
      count: 1,
      last_at: "2026-01-14T09:30:00Z",
      state: "UP",
      district: "LKO",
    },
  ],
  sub_communities: [
    { id: "sub-1", label: "Mule Layer 1 (UP East)", account_count: 3 },
    { id: "sub-2", label: "Aggregator / Exit (NCR)", account_count: 2 },
  ],
  timeline: [
    {
      id: "tl-1",
      timestamp: "2026-01-14T09:30:00Z",
      title: "Initial Complaint Registered (NCRB Portal)",
      description: "Victim from Lucknow reported fraudulent video call extortion of ₹15,00,000 via IMPS.",
      dotClass: "nk-timeline__dot--info",
    },
    {
      id: "tl-2",
      timestamp: "2026-01-14T10:10:00Z",
      title: "Second Linked Complaint Received",
      description: "Victim from Varanasi transferred ₹30,00,000 across PNB and ICICI mule accounts.",
      dotClass: "nk-timeline__dot--info",
    },
    {
      id: "tl-3",
      timestamp: "2026-01-15T08:00:00Z",
      title: "Rapid Layering Detected",
      description: "Funds moved to Axis layering node within 40 minutes of ingestion.",
      dotClass: "nk-timeline__dot--warning",
    },
    {
      id: "tl-4",
      timestamp: "2026-01-15T11:15:00Z",
      title: "Automated Case Bundling Completed",
      description: "Synthesized 5 distinct complaint references into consolidated syndication file.",
      dotClass: "nk-timeline__dot--success",
    },
  ],
  brief_md: `### Executive Case Summary: Digital Arrest Syndication File

#### 1. Factual Overview
Between 14 January 2026 and 15 January 2026, 5 distinct citizen complaints were received involving fraudulent impersonation of law enforcement officials. Analysis indicates financial transfers totaling ₹45,00,000 routed through two primary recipient accounts in Lucknow and Varanasi before rapid aggregation in the National Capital Region.

#### 2. Flow of Funds
- Inflow Layer: ₹15,00,000 transferred via IMPS to ICICI recipient account and ₹30,00,000 via RTGS to PNB recipient account.
- Consolidation Layer: ₹40,00,000 concentrated into Kotak Mahindra Bank terminal within 4 sim hours.
- Disbursal Targets: ATM terminals in Noida Sector 18 and Sector 62 recorded attempted cashout withdrawals.

#### 3. Interception Status
Lien hold requests have been dispatched to intermediary institutions. Coordinated station notifications sent to Gautam Buddha Nagar and Lucknow commissionerates.

#### 4. Statutory Notice
This case bundle compiles automated technical indicators, transaction logs, and complaint telemetry for operational review. Whether to register an FIR is the investigating officer's decision.`,
  graph_data: {
    nodes: FIXTURE_CLUSTER_STANDARD.nodes,
    edges: FIXTURE_CLUSTER_STANDARD.edges,
  },
};

// ---------------------------------------------------------------------------
// Fixture 2: Single-Complaint Case (CASE-2026-002)
// ---------------------------------------------------------------------------
export const FIXTURE_CASE_2: Case = {
  id: "CASE-2026-002",
  cluster_ref: "CLUSTER-2026-SINGLE",
  complaint_count: 1,
  victim_count: 1,
  total_paise: 1_25_000_00, // ₹1,25,000
  first_seen: "2026-01-15T08:15:00Z",
  last_seen: "2026-01-15T08:45:00Z",
  status: "under_investigation",
  single_complaint: true,
  accounts: [
    {
      account_ref: "PAYTM-99887766554",
      masked_ref: "PAYTM-••••-6554",
      bank: "PAYTM",
      complaint_count: 1,
      role: "mule",
      volume_paise: 1_25_000_00,
    },
  ],
  top_locations: [
    {
      id: "LOC-DELHI-CP",
      name: "Connaught Place ATM Terminal",
      count: 1,
      last_at: "2026-01-15T08:45:00Z",
      state: "DL",
      district: "NDLS",
    },
  ],
  timeline: [
    {
      id: "tl-201",
      timestamp: "2026-01-15T08:15:00Z",
      title: "UPI Phishing Report Filed",
      description: "Citizen reported unauthorized UPI withdrawal of ₹1,25,000 to Paytm wallet.",
      dotClass: "nk-timeline__dot--info",
    },
  ],
  brief_md: `### Case Summary: Single Complaint UPI Phishing Incident

#### 1. Factual Overview
A single citizen complaint was recorded on 15 January 2026 detailing an unauthorized UPI debit of ₹1,25,000. Funds were credited to a digital wallet service provider before an attempted ATM withdrawal in Central Delhi.

#### 2. Technical Findings
- Transaction Hash: verified against bank sim gateway.
- Associated cluster currently exhibits no secondary branching.

#### 3. Statutory Notice
Technical telemetry provided for assessment. Whether to register an FIR is the investigating officer's decision.`,
  graph_data: {
    nodes: FIXTURE_CLUSTER_SINGLE.nodes,
    edges: FIXTURE_CLUSTER_SINGLE.edges,
  },
};

// ---------------------------------------------------------------------------
// Fixture 3: Large Multi-District Syndicate (CASE-2026-003)
// ---------------------------------------------------------------------------
export const FIXTURE_CASE_3: Case = {
  id: "CASE-2026-003",
  cluster_ref: "CLUSTER-2026-BIG",
  complaint_count: 38,
  victim_count: 20,
  total_paise: 580_00_000_00, // ₹5,80,00,000
  first_seen: "2026-01-01T00:00:00Z",
  last_seen: "2026-01-15T12:00:00Z",
  status: "fir_recommended",
  single_complaint: false,
  accounts: [
    {
      account_ref: "SBIN-99000000001",
      masked_ref: "SBIN-••••-0001",
      bank: "SBI",
      complaint_count: 12,
      role: "aggregator",
      volume_paise: 250_00_000_00,
    },
    {
      account_ref: "HDFC-40000004",
      masked_ref: "HDFC-••••-0004",
      bank: "HDFC",
      complaint_count: 8,
      role: "mule",
      volume_paise: 45_00_000_00,
    },
  ],
  top_locations: [
    {
      id: "LOC-LKO-CENTRAL",
      name: "Lucknow Central Disbursal Zone",
      count: 18,
      last_at: "2026-01-15T12:00:00Z",
      state: "UP",
      district: "LKO",
    },
  ],
  timeline: [
    {
      id: "tl-301",
      timestamp: "2026-01-01T00:00:00Z",
      title: "First Syndicate Activity Recorded",
      description: "Initial investment scam complaint linked to central SBI hub.",
    },
    {
      id: "tl-302",
      timestamp: "2026-01-15T12:00:00Z",
      title: "Threshold Cross: Multi-District Escalation",
      description: "38 linked complaints exceeded aggregation criteria.",
      dotClass: "nk-timeline__dot--danger",
    },
  ],
  brief_md: `### Executive Case Summary: Multi-District Syndicate Grid

#### 1. Factual Overview
A multi-state cybercrime network comprising 38 consolidated citizen complaints with aggregate losses exceeding ₹5.8 Crore. The pattern exhibits high-degree pooling into a central hub followed by automated multi-channel cashouts.

#### 2. Syndicate Topology
Network analysis identified over 200 interconnected accounts across four commercial banking institutions.

#### 3. Statutory Notice
All metrics and account associations derived from systemic telemetry. Whether to register an FIR is the investigating officer's decision.`,
  graph_data: {
    nodes: FIXTURE_CLUSTER_BIG.nodes,
    edges: FIXTURE_CLUSTER_BIG.edges,
  },
};

const ALL_CASES: Case[] = [FIXTURE_CASE_1, FIXTURE_CASE_2, FIXTURE_CASE_3];

// ---------------------------------------------------------------------------
// React Query Hooks
// ---------------------------------------------------------------------------

export function useCases(filter?: CaseFilter) {
  return useQuery<Case[]>({
    queryKey: ["cases", filter],
    queryFn: async () => {
      let result = [...ALL_CASES];

      if (filter?.status) {
        result = result.filter((c) => c.status === filter.status);
      }

      if (filter?.singleComplaintOnly) {
        result = result.filter((c) => c.single_complaint);
      }

      if (filter?.search) {
        const q = filter.search.toLowerCase();
        result = result.filter(
          (c) =>
            c.id.toLowerCase().includes(q) ||
            c.cluster_ref.toLowerCase().includes(q),
        );
      }

      return result;
    },
    staleTime: 60_000,
  });
}

export function useCase(caseId: string | undefined) {
  return useQuery<Case | null>({
    queryKey: ["case", caseId],
    queryFn: async () => {
      if (!caseId) return null;
      const match = ALL_CASES.find(
        (c) => c.id.toLowerCase() === caseId.toLowerCase(),
      );
      return match ?? null;
    },
    enabled: Boolean(caseId),
    staleTime: 60_000,
  });
}
