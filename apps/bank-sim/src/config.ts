/**
 * config.ts — environment configuration for bank-sim.
 * DOC 3 Bank Gateway Simulator: config.ts env: WEBHOOK_SECRET, API_BASE_URL,
 * API_SERVICE_KEY, SIM_STATUS_URL.
 *
 * Loads .env.bank-sim in development (not in test/production; managed externally).
 * Fails fast if any required variable is missing.
 */

import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Load .env.bank-sim for local development (best-effort)
// ---------------------------------------------------------------------------

function loadDotEnv(): void {
  const envPath = path.resolve(process.cwd(), ".env.bank-sim");
  if (!fs.existsSync(envPath)) return;
  const lines = fs.readFileSync(envPath, "utf8").split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIdx = trimmed.indexOf("=");
    if (eqIdx < 1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim();
    if (!(key in process.env)) {
      process.env[key] = val;
    }
  }
}

if (process.env["NODE_ENV"] !== "test") {
  loadDotEnv();
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function required(name: string): string {
  const val = process.env[name];
  if (!val) {
    throw new Error(
      `[bank-sim] Missing required environment variable: ${name}. ` +
        `Copy infra/.env.example to apps/bank-sim/.env.bank-sim and fill in values.`,
    );
  }
  return val;
}

function optional(name: string, defaultVal: string): string {
  return process.env[name] ?? defaultVal;
}

// ---------------------------------------------------------------------------
// Exported config — consumed throughout the service
// ---------------------------------------------------------------------------

export const config = {
  /** HMAC-SHA256 shared secret with the NAKABANDI API. Agreed before Sync 5. */
  webhookSecret: required("WEBHOOK_SECRET"),

  /**
   * Signs the console's session cookie. Independent of webhookSecret (which authenticates
   * INBOUND webhooks) so a leak of either key doesn't weaken the other — they protect two
   * different trust boundaries.
   */
  sessionSecret: required("SESSION_SECRET"),

  /** Base URL of the NAKABANDI API (no trailing slash). */
  apiBaseUrl: required("API_BASE_URL"),

  /** Service key for POST /api/v1/integrations/bank/callbacks. */
  apiServiceKey: required("API_SERVICE_KEY"),

  /**
   * URL of the world-sim status endpoint for sim-time polling.
   * Falls back to the latest webhook sim_time when unavailable (DOC 3).
   */
  simStatusUrl: required("SIM_STATUS_URL"),

  /** Express server port. Defaults to 3001. */
  port: Number(optional("PORT", "3001")),

  /**
   * Console login username/password (the bank nodal console that approves/rejects real lien
   * amounts). Required, not optional-with-a-default like the rest of this file's `optional()`
   * fields: a well-known public default here (previously "bank_nodal"/"change-me") means a
   * deployment that forgets to set these boots reachable with a public login instead of
   * refusing to start, unlike every other secret in this file.
   */
  consoleUser: required("CONSOLE_USER"),

  /** Console login password. See consoleUser. */
  consolePass: required("CONSOLE_PASS"),

  /** SQLite database path. Overridable for tests. */
  dbPath: optional("BANK_SIM_DB_PATH", "bank-sim.db"),
} as const;
