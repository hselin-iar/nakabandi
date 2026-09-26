/**
 * server.ts — Express application factory and startup.
 * DOC 3 Bank Gateway Simulator: server.ts (Express app, routes wiring, startup).
 *
 * createApp() is exported for tests (they pass a FixedSimTimeSource and an in-memory DB).
 * main() is the production entry point.
 */

import express, { type Application, type Request, type Response, type NextFunction } from "express";
import session from "express-session";
import path from "node:path";
import { initDb } from "./store.js";
import { simTimeSource, type SimTimeSource, LiveSimTimeSource } from "./simtime.js";
import { autoReleaseDue } from "./services/liens.js";
import { createWebhookRouter } from "./routes/webhook.js";
import { createConsoleRouter } from "./routes/console.js";
import { config } from "./config.js";

// ---------------------------------------------------------------------------
// App factory — used by server startup and tests
// ---------------------------------------------------------------------------

export interface AppOptions {
  simTime?: SimTimeSource;
  /** Override DB path (for tests — use ":memory:"). */
  dbPath?: string;
  /** Disable auto-release polling (for tests). */
  disableAutoRelease?: boolean;
}

export function createApp(opts: AppOptions = {}): Application {
  const app = express();

  // Initialise DB (idempotent).
  initDb(opts.dbPath);

  const simTime = opts.simTime ?? simTimeSource;

  // ---------------------------------------------------------------------------
  // JSON body parser with raw body capture.
  // The HMAC is computed over the raw request bytes.
  // ---------------------------------------------------------------------------
  app.use(
    express.json({
      verify: (req, _res, buf) => {
        (req as Request & { rawBody?: Buffer }).rawBody = buf;
      },
    }),
  );

  // URL-encoded bodies for console forms.
  app.use(express.urlencoded({ extended: false }));

  // Session middleware for the console login.
  app.use(
    session({
      secret: config.sessionSecret,
      resave: false,
      saveUninitialized: false,
      cookie: { sameSite: "lax", httpOnly: true },
    }),
  );

  // EJS templates.
  app.set("view engine", "ejs");
  app.set("views", path.join(__dirname, "views"));

  // ---------------------------------------------------------------------------
  // Routes
  // ---------------------------------------------------------------------------

  app.use(createWebhookRouter(simTime));
  app.use(createConsoleRouter(simTime));

  // Redirect / to /console.
  app.get("/", (_req, res) => res.redirect("/console"));

  // ---------------------------------------------------------------------------
  // Error handlers
  // ---------------------------------------------------------------------------

  // 404
  app.use((_req: Request, res: Response) => {
    res.status(404).json({ error: "not found" });
  });

  // 500 — never leaks stack traces (DOC 3).
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
    console.error("[bank-sim] Unhandled error:", err);
    res.status(500).json({ error: "internal server error" });
  });

  return app;
}

// ---------------------------------------------------------------------------
// Production startup
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const app = createApp();

  // Start sim time polling.
  if (simTimeSource instanceof LiveSimTimeSource) {
    simTimeSource.startPolling();
  }

  // Auto-release overdue liens every 60 s (using sim time, not wall time).
  setInterval(() => void autoReleaseDue(simTimeSource), 60_000);

  app.listen(config.port, () => {
    console.log(
      `[bank-sim] Running on http://localhost:${config.port}\n` +
        `  Webhook endpoint: POST http://localhost:${config.port}/webhooks/nakabandi\n` +
        `  Console:          http://localhost:${config.port}/console`,
    );
  });
}

// Start listening only when run as the program (`tsx src/server.ts`), never when a test imports
// createApp(): otherwise every test file that imports this module tries to bind the same port.
if (require.main === module) {
  main().catch((err: unknown) => {
    console.error("[bank-sim] Startup failed:", err);
    process.exit(1);
  });
}
