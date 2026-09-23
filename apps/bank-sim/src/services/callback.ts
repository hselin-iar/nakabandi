/**
 * callback.ts — sendCallback: POST the callback to the NAKABANDI API.
 * DOC 3 Bank Gateway Simulator: "sendCallback(payload): POST {API_BASE_URL}/api/v1/
 * integrations/bank/callbacks with the service key; retries with backoff; idempotent
 * by request_id + status."
 *
 * SRP: this file owns only outbound callback delivery. Lien rules live in liens.ts.
 */

import { getDb } from "../store.js";
import { config } from "../config.js";
import type { CallbackBody } from "../types.js";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_ATTEMPTS = 3;
const BACKOFF_MS = [1_000, 3_000, 9_000]; // 1 s, 3 s, 9 s

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function callbackEndpoint(): string {
  return `${config.apiBaseUrl}/api/v1/integrations/bank/callbacks`;
}

// ---------------------------------------------------------------------------
// sendCallback
// ---------------------------------------------------------------------------

/**
 * Post a callback to the NAKABANDI API.
 *
 * Retries up to MAX_ATTEMPTS times with exponential backoff.
 * Records each attempt in the `callbacks` table.
 * Idempotent: skips if a successful row for this request_id + status already exists.
 *
 * @param payload  The callback body (LC-6).
 */
export async function sendCallback(payload: CallbackBody): Promise<void> {
  const db = getDb();

  // Idempotency check — do not re-send a callback that already succeeded.
  const existing = db
    .prepare(
      `SELECT id FROM callbacks WHERE request_id = ? AND status = ? AND success = 1 LIMIT 1`,
    )
    .get(payload.request_id, payload.status) as { id: number } | undefined;

  if (existing) {
    return; // Already delivered successfully.
  }

  const payloadJson = JSON.stringify(payload);
  const sentAt = new Date().toISOString();

  // Insert a pending row; we'll update it on success.
  const insertResult = db
    .prepare(
      `INSERT INTO callbacks (request_id, status, payload_json, sent_at, success, attempts)
       VALUES (?, ?, ?, ?, 0, 0)`,
    )
    .run(payload.request_id, payload.status, payloadJson, sentAt);

  const rowId = insertResult.lastInsertRowid;

  let lastError: unknown;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    if (attempt > 1) {
      await sleep(BACKOFF_MS[attempt - 2] ?? 9_000);
    }

    try {
      const res = await fetch(callbackEndpoint(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${config.apiServiceKey}`,
        },
        body: payloadJson,
        signal: AbortSignal.timeout(10_000),
      });

      db.prepare(
        `UPDATE callbacks SET attempts = ?, sent_at = ?, success = ? WHERE id = ?`,
      ).run(attempt, new Date().toISOString(), res.ok ? 1 : 0, rowId);

      if (res.ok) return; // Delivered.

      lastError = new Error(
        `[bank-sim] Callback POST returned ${res.status} on attempt ${attempt}`,
      );
    } catch (err) {
      lastError = err;
      db.prepare(
        `UPDATE callbacks SET attempts = ?, success = 0 WHERE id = ?`,
      ).run(attempt, rowId);
    }
  }

  // All attempts exhausted — console shows "callback pending".
  console.error(
    `[bank-sim] sendCallback: all ${MAX_ATTEMPTS} attempts failed for ` +
      `request_id=${payload.request_id} status=${payload.status}:`,
    lastError,
  );
}
