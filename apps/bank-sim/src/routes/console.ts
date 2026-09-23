/**
 * console.ts — bank nodal operator console routes.
 * DOC 3 Bank Gateway Simulator: GET /console, POST /console/requests/:id/apply|reject|release.
 *
 * Simple session-based login (env CONSOLE_USER / CONSOLE_PASS).
 * Server-rendered via EJS templates (views/).
 * No JavaScript beyond native HTML form submits.
 */

import { Router, type Request, type Response, type NextFunction } from "express";
import { getDb } from "../store.js";
import { config } from "../config.js";
import { applyLien, releaseLien } from "../services/liens.js";
import { sendCallback } from "../services/callback.js";
import type { SimTimeSource } from "../simtime.js";
import type { RequestRow, LienRow, CallbackRow } from "../types.js";

// ---------------------------------------------------------------------------
// Auth middleware
// ---------------------------------------------------------------------------

function requireLogin(req: Request, res: Response, next: NextFunction): void {
  const sess = req.session as { loggedIn?: boolean };
  if (sess.loggedIn) {
    next();
    return;
  }
  res.redirect("/console/login");
}

// ---------------------------------------------------------------------------
// Router factory — simTime injected so tests can provide a fixed time
// ---------------------------------------------------------------------------

export function createConsoleRouter(simTime: SimTimeSource): Router {
  const router = Router();

  // GET /console/login
  router.get("/console/login", (_req: Request, res: Response) => {
    res.render("console-login", { error: null });
  });

  // POST /console/login
  router.post("/console/login", (req: Request, res: Response) => {
    const { username, password } = req.body as { username?: string; password?: string };
    if (username === config.consoleUser && password === config.consolePass) {
      (req.session as { loggedIn?: boolean }).loggedIn = true;
      res.redirect("/console");
    } else {
      res.render("console-login", { error: "Invalid credentials." });
    }
  });

  // POST /console/logout
  router.post("/console/logout", (req: Request, res: Response) => {
    req.session.destroy(() => res.redirect("/console/login"));
  });

  // GET /console — list all requests grouped by status
  router.get("/console", requireLogin, (_req: Request, res: Response) => {
    const db = getDb();
    const requests = db
      .prepare(`SELECT * FROM requests ORDER BY received_at DESC`)
      .all() as RequestRow[];

    const liens = db
      .prepare(`SELECT * FROM liens`)
      .all() as LienRow[];

    const callbacks = db
      .prepare(
        `SELECT DISTINCT ON (request_id, status) * FROM callbacks ORDER BY id DESC`,
      )
      .all() as CallbackRow[];

    // Enrich with lien and callback info for easy template access.
    const lienByReqId = Object.fromEntries(liens.map((l) => [l.request_id, l]));
    const callbackByReqId = Object.fromEntries(
      callbacks.map((c) => [c.request_id, c]),
    );

    res.render("console-list", {
      requests,
      lienByReqId,
      callbackByReqId,
    });
  });

  // GET /console/requests/:id — detail
  router.get(
    "/console/requests/:id",
    requireLogin,
    (req: Request, res: Response) => {
      const db = getDb();
      const request = db
        .prepare(`SELECT * FROM requests WHERE request_id = ?`)
        .get(req.params["id"]) as RequestRow | undefined;

      if (!request) {
        res.status(404).send("Request not found");
        return;
      }

      const lien = db
        .prepare(`SELECT * FROM liens WHERE request_id = ?`)
        .get(req.params["id"]) as LienRow | undefined;

      const callbackHistory = db
        .prepare(`SELECT * FROM callbacks WHERE request_id = ? ORDER BY id DESC`)
        .all(req.params["id"]) as CallbackRow[];

      res.render("console-detail", {
        request,
        body: JSON.parse(request.body_json),
        lien,
        callbackHistory,
      });
    },
  );

  // POST /console/requests/:id/apply
  router.post(
    "/console/requests/:id/apply",
    requireLogin,
    (req: Request, res: Response) => {
      const { applied_amount_paise } = req.body as { applied_amount_paise?: string };
      const applied = Number(applied_amount_paise);

      if (!Number.isInteger(applied) || applied <= 0) {
        res.status(400).send("applied_amount_paise must be a positive integer");
        return;
      }

      applyLien(req.params["id"] as string, "console-operator", applied, simTime)
        .then(() => res.redirect(`/console/requests/${req.params["id"]}`))
        .catch((err: unknown) => {
          const msg = err instanceof Error ? err.message : String(err);
          res.status(400).send(`Apply failed: ${msg}`);
        });
    },
  );

  // POST /console/requests/:id/reject
  router.post(
    "/console/requests/:id/reject",
    requireLogin,
    (req: Request, res: Response) => {
      let simNow: string;
      try {
        simNow = simTime.now();
      } catch {
        res.status(503).send("Sim time not available yet.");
        return;
      }

      // Update status and send "rejected" callback.
      const db = getDb();
      db.prepare(`UPDATE requests SET status = 'rejected' WHERE request_id = ?`)
        .run(req.params["id"]);

      sendCallback({
        request_id: req.params["id"] as string,
        status: "rejected",
        at_sim: simNow,
      })
        .then(() => res.redirect(`/console/requests/${req.params["id"]}`))
        .catch((err: unknown) => {
          const msg = err instanceof Error ? err.message : String(err);
          res.status(500).send(`Callback failed: ${msg}`);
        });
    },
  );

  // POST /console/requests/:id/release
  router.post(
    "/console/requests/:id/release",
    requireLogin,
    (req: Request, res: Response) => {
      releaseLien(req.params["id"] as string, simTime)
        .then(() => res.redirect(`/console/requests/${req.params["id"]}`))
        .catch((err: unknown) => {
          const msg = err instanceof Error ? err.message : String(err);
          res.status(400).send(`Release failed: ${msg}`);
        });
    },
  );

  return router;
}
