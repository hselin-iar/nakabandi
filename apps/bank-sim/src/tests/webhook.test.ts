/**
 * webhook.test.ts — supertest suite for bank-sim.
 *
 * Covers all DOC 4 Step C2 Done When conditions:
 *   ✓ Valid signed webhook → 200 { ack: true }
 *   ✓ Bad signature → 401
 *   ✓ Stale timestamp → 401
 *   ✓ Duplicate Idempotency-Key → same body, DB row count unchanged
 *   ✓ proposed > disputed → 422
 *   ✓ applyLien: applied > proposed → throws
 *   ✓ autoReleaseDue: releases overdue liens
 *   ✓ sendCallback: retries on first-failure stub (mock fetch)
 *
 * Uses an in-memory SQLite DB and FixedSimTimeSource for full isolation.
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach, vi } from "vitest";
import request from "supertest";
import crypto from "node:crypto";
import type { Application } from "express";

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

import { createApp } from "../server.js";
import { closeDb, getDb } from "../store.js";
import { FixedSimTimeSource } from "../simtime.js";
import { idempotencyStore } from "../verify.js";
import { applyLien } from "../services/liens.js";
import { autoReleaseDue } from "../services/liens.js";
import type { HoldRequestBody, AlertNoticeBody } from "../types.js";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const SECRET = process.env["WEBHOOK_SECRET"]!;
const SIM_TIME = "2026-01-15T08:00:00Z";
const simTime = new FixedSimTimeSource(SIM_TIME);

function makeHeaders(
  body: unknown,
  opts: { badSig?: boolean; staleTs?: boolean; idempotencyKey?: string } = {},
): Record<string, string> {
  const now = Math.floor(Date.now() / 1000);
  const timestampSec = opts.staleTs ? now - 400 : now;
  const timestamp = String(timestampSec);
  const rawBody = JSON.stringify(body);
  const message = `${timestamp}.${rawBody}`;
  const realSig = crypto.createHmac("sha256", SECRET).update(message).digest("hex");
  const sig = opts.badSig ? "deadbeef".repeat(8) : realSig;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Nakabandi-Timestamp": timestamp,
    "X-Nakabandi-Signature": sig,
  };
  if (opts.idempotencyKey) {
    headers["Idempotency-Key"] = opts.idempotencyKey;
  }
  return headers;
}

function makeHoldRequest(overrides: Partial<HoldRequestBody> = {}): HoldRequestBody {
  return {
    kind: "hold_request",
    request_id: `test-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    alert_ref: "ALERT-001",
    bank_id: "SBI",
    account_ref: "ACCT-001",
    complaint_ref: "COMP-001",
    sim_time: SIM_TIME,
    disputed_amount_paise: 50000,
    proposed_lien_paise: 40000,
    expires_at_sim: "2026-01-15T10:00:00Z",
    review_at_sim: "2026-01-15T09:00:00Z",
    requested_by_role: "i4c_analyst",
    ...overrides,
  };
}

function makeAlertNotice(
  overrides: Partial<AlertNoticeBody> = {},
): AlertNoticeBody {
  return {
    kind: "alert_notice",
    request_id: `test-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    alert_ref: "ALERT-002",
    bank_id: "SBI",
    account_ref: "XXXX1234",
    complaint_ref: "COMP-002",
    sim_time: SIM_TIME,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let app: Application;

beforeAll(() => {
  app = createApp({ simTime, dbPath: ":memory:", disableAutoRelease: true });
  // Seed sim time so auto-release checks don't fail.
  simTime.updateFromWebhook(SIM_TIME);
});

afterAll(() => {
  closeDb();
});

beforeEach(() => {
  // Clear idempotency store between tests.
  (idempotencyStore as unknown as { store: Map<string, unknown> }).store.clear();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("POST /webhooks/nakabandi — Done When checks", () => {

  it("C2-DW-1: valid signed hold_request → 200 { ack: true }", async () => {
    const body = makeHoldRequest();
    const headers = makeHeaders(body, { idempotencyKey: `idem-${Date.now()}` });

    const res = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(JSON.stringify(body));

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ ack: true });
  });

  it("C2-DW-2: bad signature → 401", async () => {
    const body = makeHoldRequest();
    const headers = makeHeaders(body, { badSig: true });

    const res = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(JSON.stringify(body));

    expect(res.status).toBe(401);
    expect(res.body).toMatchObject({ error: "invalid signature" });
  });

  it("C2-DW-3: stale timestamp → 401", async () => {
    const body = makeHoldRequest();
    const headers = makeHeaders(body, { staleTs: true });

    const res = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(JSON.stringify(body));

    expect(res.status).toBe(401);
    expect(res.body).toMatchObject({ error: "invalid signature" });
  });

  it("C2-DW-4: duplicate Idempotency-Key → same response, no second DB record", async () => {
    const body = makeHoldRequest();
    const idemKey = `idem-dup-${Date.now()}`;
    const headers = makeHeaders(body, { idempotencyKey: idemKey });
    const bodyStr = JSON.stringify(body);

    // First request.
    const r1 = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(bodyStr);
    expect(r1.status).toBe(200);
    expect(r1.body).toEqual({ ack: true });

    const db = getDb();
    const countBefore = (
      db
        .prepare("SELECT COUNT(*) as n FROM requests WHERE request_id = ?")
        .get(body.request_id) as { n: number }
    ).n;
    expect(countBefore).toBe(1);

    // Second request — same idempotency key.
    const r2 = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(bodyStr);
    expect(r2.status).toBe(200);
    expect(r2.body).toEqual({ ack: true });

    const countAfter = (
      db
        .prepare("SELECT COUNT(*) as n FROM requests WHERE request_id = ?")
        .get(body.request_id) as { n: number }
    ).n;
    expect(countAfter).toBe(1); // No second record.
  });

  it("C2-DW-5: proposed > disputed → 422", async () => {
    const body = makeHoldRequest({
      disputed_amount_paise: 10000,
      proposed_lien_paise: 20000, // exceeds disputed
    });
    const headers = makeHeaders(body);

    const res = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(JSON.stringify(body));

    expect(res.status).toBe(422);
    expect(res.body).toMatchObject({ error: "contract violation" });
  });

  it("C2-EXTRA: alert_notice is acknowledged", async () => {
    const body = makeAlertNotice();
    const headers = makeHeaders(body);

    const res = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(JSON.stringify(body));

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ ack: true });
  });

  it("C2-EXTRA: proposed = disputed (boundary) → 200", async () => {
    const body = makeHoldRequest({
      disputed_amount_paise: 30000,
      proposed_lien_paise: 30000,
    });
    const headers = makeHeaders(body);

    const res = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(JSON.stringify(body));

    expect(res.status).toBe(200);
  });

  it("C2-EXTRA: proposed = 0 → 422", async () => {
    const body = makeHoldRequest({ proposed_lien_paise: 0 });
    const headers = makeHeaders(body);

    const res = await request(app)
      .post("/webhooks/nakabandi")
      .set(headers)
      .send(JSON.stringify(body));

    expect(res.status).toBe(422);
  });
});

// ---------------------------------------------------------------------------
// Unit tests for applyLien
// ---------------------------------------------------------------------------

describe("applyLien — unit", () => {
  it("C2-DW-6: applied > proposed → throws", async () => {
    // Insert a hold_request into the DB.
    const body = makeHoldRequest({ proposed_lien_paise: 5000 });
    const db = getDb();
    db.prepare(
      `INSERT INTO requests (request_id, kind, body_json, status, received_at)
       VALUES (?, ?, ?, 'pending', ?)`,
    ).run(body.request_id, body.kind, JSON.stringify(body), new Date().toISOString());

    await expect(
      applyLien(body.request_id, "tester", 6000 /* > 5000 */, simTime),
    ).rejects.toThrow(/exceeds proposed_lien_paise/);
  });

  it("applied = 0 → throws", async () => {
    const body = makeHoldRequest({ proposed_lien_paise: 5000 });
    const db = getDb();
    db.prepare(
      `INSERT INTO requests (request_id, kind, body_json, status, received_at)
       VALUES (?, ?, ?, 'pending', ?)`,
    ).run(body.request_id, body.kind, JSON.stringify(body), new Date().toISOString());

    await expect(
      applyLien(body.request_id, "tester", 0, simTime),
    ).rejects.toThrow(/must be > 0/);
  });
});

// ---------------------------------------------------------------------------
// Unit tests for autoReleaseDue
// ---------------------------------------------------------------------------

describe("autoReleaseDue — unit", () => {
  it("C2-DW-7: releases liens past expires_at_sim", async () => {
    // Set sim time to "now".
    const fixedTime = new FixedSimTimeSource("2026-01-15T12:00:00Z");

    // Insert a hold_request + an already-expired lien.
    const db = getDb();
    const reqId = `auto-rel-${Date.now()}`;
    const holdBody = makeHoldRequest({
      request_id: reqId,
      expires_at_sim: "2026-01-15T11:00:00Z", // in the past relative to fixedTime
    });
    db.prepare(
      `INSERT INTO requests (request_id, kind, body_json, status, received_at)
       VALUES (?, ?, ?, 'applied', ?)`,
    ).run(reqId, holdBody.kind, JSON.stringify(holdBody), new Date().toISOString());
    db.prepare(
      `INSERT INTO liens (request_id, applied_paise, expires_at_sim, applied_at_sim, released)
       VALUES (?, ?, ?, ?, 0)`,
    ).run(reqId, 3000, holdBody.expires_at_sim, "2026-01-15T08:30:00Z");

    // Mock sendCallback so it doesn't try a real HTTP request.
    vi.stubGlobal("fetch", async () => ({ ok: true, status: 200 }));

    await autoReleaseDue(fixedTime);

    const lien = db
      .prepare("SELECT released FROM liens WHERE request_id = ?")
      .get(reqId) as { released: number };
    expect(lien.released).toBe(1);

    vi.unstubAllGlobals();
  });
});

// ---------------------------------------------------------------------------
// Unit tests for sendCallback retry
// ---------------------------------------------------------------------------

describe("sendCallback — retry behaviour", () => {
  it("C2-DW-8: retries after first failure and succeeds on second attempt", async () => {
    // We need a fresh DB row to trigger sendCallback.
    // Use applyLien flow, which calls sendCallback internally.
    const db = getDb();
    const reqId = `cb-retry-${Date.now()}`;
    const holdBody = makeHoldRequest({ request_id: reqId, proposed_lien_paise: 1000 });
    db.prepare(
      `INSERT INTO requests (request_id, kind, body_json, status, received_at)
       VALUES (?, ?, ?, 'pending', ?)`,
    ).run(reqId, holdBody.kind, JSON.stringify(holdBody), new Date().toISOString());

    let callCount = 0;
    vi.stubGlobal("fetch", async () => {
      callCount++;
      if (callCount === 1) {
        // First attempt fails.
        return { ok: false, status: 503 };
      }
      return { ok: true, status: 200 };
    });

    await applyLien(reqId, "tester", 500, simTime);

    // Should have been called at least twice (1 fail + 1 success).
    expect(callCount).toBeGreaterThanOrEqual(2);

    // Callback row should be success=1 ultimately.
    const cbRow = db
      .prepare("SELECT success FROM callbacks WHERE request_id = ? AND status = 'applied'")
      .get(reqId) as { success: number } | undefined;
    expect(cbRow?.success).toBe(1);

    vi.unstubAllGlobals();
  });
});
