/**
 * webhook.ts — POST /webhooks/nakabandi route handler.
 * DOC 3 Bank Gateway Simulator: handleWebhook() flow per spec.
 *
 * Flow:
 *   1 verify signature and window (→ 401)
 *   2 dedupe on Idempotency-Key (→ 200 stored response)
 *   3 for alert_notice: store and respond {ack:true}
 *   4 for hold_request: re-validate proposed ≤ disputed and > 0 (→ 422); store; respond {ack:true}
 */

import { Router, type Request, type Response } from "express";
import { verifySignature, withinWindow } from "../verify.js";
import { idempotencyStore } from "../verify.js";
import { getDb } from "../store.js";
import { config } from "../config.js";
import type { SimTimeSource } from "../simtime.js";
import type { WebhookBody, HoldRequestBody } from "../types.js";

export function createWebhookRouter(simTime: SimTimeSource): Router {
  const router = Router();

  router.post(
    "/webhooks/nakabandi",
    (req: Request & { rawBody?: Buffer }, res: Response) => {
      // --- 1. Signature and window check ---
      const timestampHeader = req.headers["x-nakabandi-timestamp"];
      const signatureHeader = req.headers["x-nakabandi-signature"];
      const idempotencyKey = req.headers["idempotency-key"];

      if (
        typeof timestampHeader !== "string" ||
        typeof signatureHeader !== "string"
      ) {
        res.status(401).json({ error: "invalid signature" });
        return;
      }

      const timestampSec = Number(timestampHeader);
      if (!Number.isInteger(timestampSec)) {
        res.status(401).json({ error: "invalid signature" });
        return;
      }

      const nowSec = Math.floor(Date.now() / 1000);
      if (!withinWindow(timestampSec, nowSec)) {
        console.warn(
          `[bank-sim] Webhook rejected: clock skew ${Math.abs(nowSec - timestampSec)}s ` +
            `(limit 300s) from timestamp=${timestampHeader}`,
        );
        res.status(401).json({ error: "invalid signature" });
        return;
      }

      const rawBody: Buffer = req.rawBody ?? Buffer.from(JSON.stringify(req.body));
      if (!verifySignature(config.webhookSecret, timestampHeader, rawBody, signatureHeader)) {
        res.status(401).json({ error: "invalid signature" });
        return;
      }

      // --- 2. Idempotency-Key deduplication ---
      if (typeof idempotencyKey === "string" && idempotencyKey) {
        const stored = idempotencyStore.seen(idempotencyKey);
        if (stored) {
          res.status(stored.statusCode).json(stored.body);
          return;
        }
      }

      // --- 3 & 4. Parse and process ---
      const body = req.body as WebhookBody;

      if (!body.kind || !["alert_notice", "hold_request"].includes(body.kind)) {
        const errBody = { error: "contract violation", fields: ["kind"] };
        if (typeof idempotencyKey === "string" && idempotencyKey) {
          idempotencyStore.remember(idempotencyKey, { statusCode: 422, body: errBody });
        }
        res.status(422).json(errBody);
        return;
      }

      if (body.kind === "hold_request") {
        const hr = body as HoldRequestBody;
        const violations: string[] = [];

        if (
          typeof hr.proposed_lien_paise !== "number" ||
          hr.proposed_lien_paise <= 0
        ) {
          violations.push("proposed_lien_paise (must be > 0)");
        }
        if (
          typeof hr.disputed_amount_paise !== "number" ||
          hr.disputed_amount_paise <= 0
        ) {
          violations.push("disputed_amount_paise (must be > 0)");
        }
        if (
          typeof hr.proposed_lien_paise === "number" &&
          typeof hr.disputed_amount_paise === "number" &&
          hr.proposed_lien_paise > hr.disputed_amount_paise
        ) {
          violations.push(
            `proposed_lien_paise (${hr.proposed_lien_paise}) exceeds ` +
              `disputed_amount_paise (${hr.disputed_amount_paise})`,
          );
        }

        if (violations.length > 0) {
          const errBody = { error: "contract violation", fields: violations };
          if (typeof idempotencyKey === "string" && idempotencyKey) {
            idempotencyStore.remember(idempotencyKey, { statusCode: 422, body: errBody });
          }
          res.status(422).json(errBody);
          return;
        }
      }

      // --- Store the request ---
      const db = getDb();
      db.prepare(
        `INSERT OR IGNORE INTO requests (request_id, kind, body_json, status, received_at)
         VALUES (?, ?, ?, 'pending', ?)`,
      ).run(
        body.request_id,
        body.kind,
        JSON.stringify(body),
        new Date().toISOString(),
      );

      // Update SimTimeSource from the webhook's sim_time.
      if (body.sim_time) {
        simTime.updateFromWebhook(body.sim_time);
      }

      const ackBody = { ack: true };
      if (typeof idempotencyKey === "string" && idempotencyKey) {
        idempotencyStore.remember(idempotencyKey, { statusCode: 200, body: ackBody });
      }
      res.status(200).json(ackBody);
    },
  );

  return router;
}
