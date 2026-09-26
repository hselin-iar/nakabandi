/**
 * useCases.ts — TanStack Query hooks for Cases.
 * DOC 3 §S1 & DOC 4 §C6
 *
 * Real backend only: GET /cases, GET /cases/{id}. DOC 3's Case has no workflow `status`, no
 * per-account `role`/`volume_paise`, no named locations, and always an empty `timeline` (DOC 4
 * A12 Learnings) — those are set to safe constants/fallbacks below, not fabricated. The cluster
 * topology comes from a separate GET /clusters/{cluster_ref} call (useCluster), composed by
 * CaseDetail, not embedded here.
 *
 * Invariant: The brief states facts and ends with:
 * "Whether to register an FIR is the investigating officer's decision."
 * It never asserts guilt or names real persons.
 */

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../../shared/api/client";
import type { Case, CaseAccount, CaseFilter, CaseLocation } from "../types";
import type { Case as ApiCase } from "../../../shared/api/types.ts";

export const REQUIRED_FIR_DISCLAIMER =
  "Whether to register an FIR is the investigating officer's decision.";

function toAccount(a: ApiCase["accounts"][number]): CaseAccount {
  return {
    account_ref: a.masked_ref,
    masked_ref: a.masked_ref,
    bank: a.bank,
    complaint_count: a.complaint_count,
  };
}

function toLocation(l: ApiCase["top_locations"][number]): CaseLocation {
  return { id: l.location_id, name: l.location_id, count: l.count, last_at: l.last_at };
}

function toCase(c: ApiCase): Case {
  return {
    id: c.id,
    cluster_ref: c.cluster_ref,
    complaint_count: c.complaint_count,
    victim_count: c.victim_count,
    total_paise: c.total_paise,
    first_seen: c.first_seen,
    last_seen: c.last_seen,
    status: "bundled",
    accounts: c.accounts.map(toAccount),
    top_locations: c.top_locations.map(toLocation),
    sub_communities: c.sub_communities.map((group, i) => ({
      id: `sub-${i}`,
      label: `Sub-community ${i + 1}`,
      account_count: group.length,
    })),
    timeline: [],
    brief_md: c.brief_md,
    single_complaint: c.single_complaint,
  };
}

export function useCases(filter?: CaseFilter) {
  return useQuery<Case[]>({
    queryKey: ["cases", filter],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/cases", { params: { query: {} } });
      if (error) throw new Error("Failed to load cases");
      let result = data.items.map(toCase);

      if (filter?.singleComplaintOnly) {
        result = result.filter((c) => c.single_complaint);
      }
      if (filter?.search) {
        const q = filter.search.toLowerCase();
        result = result.filter(
          (c) => c.id.toLowerCase().includes(q) || c.cluster_ref.toLowerCase().includes(q),
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
      const { data, error } = await apiClient.GET("/cases/{case_id}", {
        params: { path: { case_id: caseId } },
      });
      if (error) throw new Error("Failed to load case");
      return toCase(data);
    },
    enabled: Boolean(caseId),
    staleTime: 60_000,
  });
}

export interface CaseExplanation {
  available: boolean;
  text: string | null;
  model: string | null;
  reason: string | null;
}

/**
 * Optional plain-language reading of a case (server-side NVIDIA NIM call over anonymised
 * aggregate facts; the browser never sees the key). `available: false` means keep showing the
 * deterministic brief only. Cached long: the server caches per unchanged cluster too.
 */
export function useCaseExplanation(caseId: string | undefined) {
  return useQuery<CaseExplanation>({
    queryKey: ["case-explanation", caseId],
    enabled: Boolean(caseId),
    staleTime: 5 * 60_000,
    retry: false,
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/cases/{case_id}/explanation", {
        params: { path: { case_id: caseId! } },
      });
      if (error || !data) return { available: false, text: null, model: null, reason: "model_error" };
      return data;
    },
  });
}
