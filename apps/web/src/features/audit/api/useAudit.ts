/**
 * useAudit.ts — Fixture data + TanStack Query hooks for the Audit Log.
 * DOC 3 §M5 (audit, hash-chained AuditLog) · DOC 4 Step C7
 *
 * STUB STRATEGY: fixture matching /audit and /audit/verify endpoint shapes.
 * Swap for real API calls when Track A Step A4 lands.
 *
 * verifyChain() supports an optional `tamperSeq` param that forces the
 * verify response to report a failure at that sequence number — used in
 * component tests to exercise the "verify failed" banner state (Evidence
 * required in DOC4 Step C7).
 */

import { useQuery } from "@tanstack/react-query";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuditEntry {
  seq: number;
  event_type: string;
  actor_id: string;
  object_ref: string;
  recorded_at: string;
  row_hash: string;
}

export interface VerifyResult {
  ok: boolean;
  /** Sequence number of first bad row (only set when ok === false) */
  first_bad_seq?: number;
  checked_rows: number;
}

// ---------------------------------------------------------------------------
// Fixture: ten hash-chained entries
// ---------------------------------------------------------------------------

/** SHA-256-like stub hashes (not real hashes — replaced when A4 lands) */
const HASH: string[] = [
  "a3f9b2c14d7e8f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
  "b4a0c3d2e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
  "c5b1d4e3f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4",
  "d6c2e5f4a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5",
  "e7d3f6a5b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6",
  "f8e4a7b6c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7",
  "a9f5b8c7d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8",
  "b0a6c9d8e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9",
  "c1b7d0e9f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0",
  "d2c8e1f0a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1",
];

export const FIXTURE_AUDIT_ENTRIES: AuditEntry[] = [
  { seq: 1,  event_type: "alert.created",       actor_id: "SYSTEM",              object_ref: "ALT-2026-001", recorded_at: "2026-09-23T09:00:00Z", row_hash: HASH[0] },
  { seq: 2,  event_type: "alert.acknowledged",   actor_id: "state_investigator_1",object_ref: "ALT-2026-001", recorded_at: "2026-09-23T09:05:12Z", row_hash: HASH[1] },
  { seq: 3,  event_type: "action.request_hold",  actor_id: "state_investigator_1",object_ref: "ACT-2026-001", recorded_at: "2026-09-23T09:08:44Z", row_hash: HASH[2] },
  { seq: 4,  event_type: "delivery.dispatched",  actor_id: "SYSTEM",              object_ref: "DLV-0001",     recorded_at: "2026-09-23T09:08:45Z", row_hash: HASH[3] },
  { seq: 5,  event_type: "delivery.dispatched",  actor_id: "SYSTEM",              object_ref: "DLV-0002",     recorded_at: "2026-09-23T09:08:46Z", row_hash: HASH[4] },
  { seq: 6,  event_type: "alert.created",        actor_id: "SYSTEM",              object_ref: "ALT-2026-002", recorded_at: "2026-09-23T14:00:00Z", row_hash: HASH[5] },
  { seq: 7,  event_type: "action.request_hold",  actor_id: "district_officer_1",  object_ref: "ACT-2026-002", recorded_at: "2026-09-23T14:29:00Z", row_hash: HASH[6] },
  { seq: 8,  event_type: "delivery.failed",      actor_id: "SYSTEM",              object_ref: "DLV-0003",     recorded_at: "2026-09-23T14:31:00Z", row_hash: HASH[7] },
  { seq: 9,  event_type: "alert.created",        actor_id: "SYSTEM",              object_ref: "ALT-2026-003", recorded_at: "2026-09-24T00:10:00Z", row_hash: HASH[8] },
  { seq: 10, event_type: "action.notify_station",actor_id: "district_officer_2",  object_ref: "ACT-2026-003", recorded_at: "2026-09-24T00:14:00Z", row_hash: HASH[9] },
];

// ---------------------------------------------------------------------------
// Verify helper
// ---------------------------------------------------------------------------

/**
 * Simulates /audit/verify.
 * Pass `tamperSeq` to force a failure at that sequence number (for tests).
 */
export function verifyChain(tamperSeq?: number): Promise<VerifyResult> {
  if (tamperSeq != null) {
    return Promise.resolve({
      ok: false,
      first_bad_seq: tamperSeq,
      checked_rows: FIXTURE_AUDIT_ENTRIES.length,
    });
  }
  return Promise.resolve({
    ok: true,
    checked_rows: FIXTURE_AUDIT_ENTRIES.length,
  });
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useAuditLog() {
  return useQuery<AuditEntry[]>({
    queryKey: ["audit-log"],
    queryFn: () => Promise.resolve(FIXTURE_AUDIT_ENTRIES),
    staleTime: 60_000,
  });
}
