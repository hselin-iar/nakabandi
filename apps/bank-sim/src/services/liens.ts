/**
 * liens.ts — lien application, release, and auto-release logic.
 * DOC 3 Bank Gateway Simulator: applyLien(), releaseLien(), autoReleaseDue().
 *
 * SRP: this file owns only lien lifecycle rules.
 * It calls sendCallback() after state transitions; it does not know about HTTP.
 */

import { getDb } from "../store.js";
import { sendCallback } from "./callback.js";
import type { SimTimeSource } from "../simtime.js";
import type { HoldRequestBody } from "../types.js";

// ---------------------------------------------------------------------------
// applyLien
// ---------------------------------------------------------------------------

/**
 * Apply a lien to a pending hold_request.
 *
 * Rules (DOC 3):
 *   - requires 0 < appliedPaise <= proposedLienPaise
 *   - writes a lien row with expires_at_sim from the webhook body
 *   - updates requests.status to "applied"
 *   - fires sendCallback("applied")
 *
 * @throws if the request is not found, not a hold_request, not pending, or
 *         if appliedPaise violates the amount rules.
 */
export async function applyLien(
  requestId: string,
  /** Display name of the console operator performing the action. */
  operator: string,
  /** Integer paise — must be > 0 and <= proposed_lien_paise. */
  appliedPaise: number,
  simTime: SimTimeSource,
): Promise<void> {
  const db = getDb();

  const row = db
    .prepare(`SELECT body_json, status, kind FROM requests WHERE request_id = ?`)
    .get(requestId) as
    | { body_json: string; status: string; kind: string }
    | undefined;

  if (!row) throw new Error(`request_id ${requestId} not found`);
  if (row.kind !== "hold_request") throw new Error(`${requestId} is not a hold_request`);
  if (row.status !== "pending") throw new Error(`${requestId} is not in pending status`);

  const body = JSON.parse(row.body_json) as HoldRequestBody;

  if (appliedPaise <= 0) {
    throw new Error(
      `applied_paise must be > 0 (got ${appliedPaise})`,
    );
  }
  if (appliedPaise > body.proposed_lien_paise) {
    throw new Error(
      `applied_paise (${appliedPaise}) exceeds proposed_lien_paise (${body.proposed_lien_paise})`,
    );
  }

  const simNow = simTime.now();

  db.transaction(() => {
    db.prepare(
      `UPDATE requests SET status = 'applied' WHERE request_id = ?`,
    ).run(requestId);

    db.prepare(
      `INSERT INTO liens (request_id, applied_paise, expires_at_sim, applied_at_sim, released)
       VALUES (?, ?, ?, ?, 0)`,
    ).run(requestId, appliedPaise, body.expires_at_sim, simNow);
  })();

  console.log(
    `[bank-sim] applyLien: request=${requestId} operator=${operator} ` +
      `applied=${appliedPaise} paise expires_at_sim=${body.expires_at_sim}`,
  );

  await sendCallback({
    request_id: requestId,
    status: "applied",
    applied_amount_paise: appliedPaise,
    at_sim: simNow,
  });
}

// ---------------------------------------------------------------------------
// releaseLien
// ---------------------------------------------------------------------------

/**
 * Manually release an applied lien (operator action or auto-release).
 *
 * @throws if the request is not found or the lien is already released.
 */
export async function releaseLien(
  requestId: string,
  simTime: SimTimeSource,
): Promise<void> {
  const db = getDb();

  const lien = db
    .prepare(`SELECT released FROM liens WHERE request_id = ?`)
    .get(requestId) as { released: number } | undefined;

  if (!lien) throw new Error(`No lien found for request_id ${requestId}`);
  if (lien.released === 1) throw new Error(`Lien for ${requestId} is already released`);

  const simNow = simTime.now();

  db.transaction(() => {
    db.prepare(
      `UPDATE liens SET released = 1 WHERE request_id = ?`,
    ).run(requestId);
    db.prepare(
      `UPDATE requests SET status = 'released' WHERE request_id = ?`,
    ).run(requestId);
  })();

  console.log(`[bank-sim] releaseLien: request=${requestId} at_sim=${simNow}`);

  await sendCallback({
    request_id: requestId,
    status: "released",
    at_sim: simNow,
  });
}

// ---------------------------------------------------------------------------
// rejectLien
// ---------------------------------------------------------------------------

/**
 * Reject a pending hold_request. Unlike applyLien/releaseLien this has no `liens` row to check
 * (a rejection never creates one), so it validates against `requests` directly instead.
 *
 * @throws if the request is not found, is not a hold_request, or is not in pending status.
 */
export async function rejectLien(requestId: string, simTime: SimTimeSource): Promise<void> {
  const db = getDb();

  const row = db
    .prepare(`SELECT status, kind FROM requests WHERE request_id = ?`)
    .get(requestId) as { status: string; kind: string } | undefined;

  if (!row) throw new Error(`request_id ${requestId} not found`);
  if (row.kind !== "hold_request") throw new Error(`${requestId} is not a hold_request`);
  if (row.status !== "pending") throw new Error(`${requestId} is not in pending status`);

  const simNow = simTime.now();

  db.prepare(`UPDATE requests SET status = 'rejected' WHERE request_id = ?`).run(requestId);

  console.log(`[bank-sim] rejectLien: request=${requestId} at_sim=${simNow}`);

  await sendCallback({
    request_id: requestId,
    status: "rejected",
    at_sim: simNow,
  });
}

// ---------------------------------------------------------------------------
// autoReleaseDue
// ---------------------------------------------------------------------------

/**
 * Release all liens whose expires_at_sim is in the past (relative to simNow).
 *
 * Called on a timer in server.ts (or after each webhook delivery).
 * DOC 3 Edge case: "Restart: pending requests and liens persist; auto-release
 * resumes from the last sim time."
 */
export async function autoReleaseDue(simTime: SimTimeSource): Promise<void> {
  const db = getDb();
  let simNow: string;
  try {
    simNow = simTime.now();
  } catch {
    // No sim time yet — cannot determine which liens are overdue.
    return;
  }

  const due = db
    .prepare(
      `SELECT request_id FROM liens
       WHERE released = 0 AND expires_at_sim <= ?`,
    )
    .all(simNow) as { request_id: string }[];

  for (const { request_id } of due) {
    try {
      await releaseLien(request_id, simTime);
    } catch (err) {
      console.error(`[bank-sim] autoReleaseDue failed for ${request_id}:`, err);
    }
  }
}
