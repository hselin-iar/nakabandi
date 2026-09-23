/**
 * console.test.ts — the bank nodal console (DOC 3 Bank Gateway Simulator: console.ts).
 *
 * webhook.test.ts covers the webhook and lien services; nothing exercised the console routes, and
 * GET /console returned 500 on SQLite (`SELECT DISTINCT ON` is PostgreSQL-only), which only showed
 * up when the API and the simulator were run together (Sync 5).
 */

import { describe, it, expect, beforeAll, afterAll } from "vitest";
import request from "supertest";
import crypto from "node:crypto";
import type { Application } from "express";

import { createApp } from "../server.js";
import { closeDb, getDb } from "../store.js";
import { FixedSimTimeSource } from "../simtime.js";

const SECRET = process.env["WEBHOOK_SECRET"]!;
const SIM_TIME = "2026-01-15T08:00:00Z";
const simTime = new FixedSimTimeSource(SIM_TIME);

let app: Application;

function signed(body: unknown): Record<string, string> {
  const timestamp = String(Math.floor(Date.now() / 1000));
  const raw = JSON.stringify(body);
  const signature = crypto.createHmac("sha256", SECRET).update(`${timestamp}.${raw}`).digest("hex");
  return {
    "Content-Type": "application/json",
    "X-Nakabandi-Timestamp": timestamp,
    "X-Nakabandi-Signature": signature,
  };
}

async function login(): Promise<ReturnType<typeof request.agent>> {
  const agent = request.agent(app);
  const res = await agent
    .post("/console/login")
    .type("form")
    .send({ username: process.env["CONSOLE_USER"] ?? "bank_nodal", password: process.env["CONSOLE_PASS"] ?? "change-me" });
  expect(res.status).toBe(302);
  return agent;
}

beforeAll(() => {
  app = createApp({ simTime, dbPath: ":memory:", disableAutoRelease: true });
});

afterAll(() => {
  closeDb();
});

describe("bank console", () => {
  it("requires a login", async () => {
    const res = await request(app).get("/console");
    expect([301, 302, 401]).toContain(res.status);
  });

  it("lists a hold request received over the webhook, and a callback row does not break the list", async () => {
    const body = {
      kind: "hold_request",
      request_id: "console-req-1",
      alert_ref: "A-1",
      bank_id: "SBI",
      account_ref: "ACCT-0001",
      complaint_ref: "C-1",
      sim_time: SIM_TIME,
      disputed_amount_paise: 50000,
      proposed_lien_paise: 40000,
      expires_at_sim: "2026-01-15T10:00:00Z",
      review_at_sim: "2026-01-15T09:00:00Z",
      requested_by_role: "i4c_analyst",
    };
    const hook = await request(app).post("/webhooks/nakabandi").set(signed(body)).send(body);
    expect(hook.status).toBe(200);

    // two callbacks for one request (applied, then released): the list must show the latest
    const db = getDb();
    const insert = db.prepare(
      `INSERT INTO callbacks (request_id, status, payload_json, sent_at, success, attempts)
       VALUES (?, ?, '{}', ?, 1, 1)`,
    );
    insert.run("console-req-1", "applied", SIM_TIME);
    insert.run("console-req-1", "released", SIM_TIME);

    const agent = await login();
    const list = await agent.get("/console");

    expect(list.status).toBe(200);
    expect(list.text).toContain("console-req-1");
    const detail = await agent.get("/console/requests/console-req-1");
    expect(detail.status).toBe(200);
  });
});
