/**
 * useAudit.ts — TanStack Query hooks for the Audit Log.
 * DOC 3 §M5 (audit, hash-chained AuditLog) · DOC 4 Step C7
 *
 * Real backend only: GET /audit (list, with each row's own chain hash — added alongside this
 * rewrite so the page can show more than pass/fail), GET /audit/verify.
 */

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../../../shared/api/client";
import type { AuditEntry, VerifyResponse } from "../../../shared/api/types.ts";

export function useAuditLog() {
  return useQuery<AuditEntry[]>({
    queryKey: ["audit-log"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/audit");
      if (error) throw new Error("Failed to load the audit log");
      return data;
    },
    staleTime: 60_000,
  });
}

export async function verifyChain(): Promise<VerifyResponse> {
  const { data, error } = await apiClient.GET("/audit/verify");
  if (error) throw new Error("Failed to verify the audit chain");
  return data;
}
