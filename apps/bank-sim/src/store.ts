/**
 * store.ts — SQLite persistence layer (better-sqlite3).
 * DOC 3 Bank Gateway Simulator: store.ts (better-sqlite3: requests, liens, callbacks).
 *
 * Tables:
 *   requests   — every received webhook (one row per request_id)
 *   liens      — applied liens (one row per request_id that had a lien applied)
 *   callbacks  — outbound callback log (one row per attempt; updated on retry)
 *
 * SRP: this file owns only schema initialisation and raw DB access.
 * Business rules live in services/.
 */

import Database from "better-sqlite3";
import { config } from "./config.js";

// ---------------------------------------------------------------------------
// DB singleton
// ---------------------------------------------------------------------------

let _db: Database.Database | null = null;

/**
 * Initialise the SQLite database and create tables if they do not exist.
 * Call once at startup (server.ts). Safe to call multiple times.
 */
export function initDb(dbPath?: string): Database.Database {
  if (_db) return _db;

  _db = new Database(dbPath ?? config.dbPath);
  // WAL for concurrent reads (though volume is tiny at demo scale).
  _db.pragma("journal_mode = WAL");
  _db.pragma("foreign_keys = ON");

  _db.exec(`
    CREATE TABLE IF NOT EXISTS requests (
      request_id   TEXT PRIMARY KEY,
      kind         TEXT NOT NULL CHECK (kind IN ('alert_notice','hold_request')),
      body_json    TEXT NOT NULL,
      status       TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','applied','rejected','released')),
      received_at  TEXT NOT NULL   -- ISO-8601 wall-clock (record only; never used for domain logic)
    );

    CREATE TABLE IF NOT EXISTS liens (
      request_id      TEXT PRIMARY KEY REFERENCES requests(request_id),
      applied_paise   INTEGER NOT NULL CHECK (applied_paise > 0),
      expires_at_sim  TEXT NOT NULL,    -- ISO-8601 sim time
      applied_at_sim  TEXT NOT NULL,    -- ISO-8601 sim time of application
      released        INTEGER NOT NULL DEFAULT 0 CHECK (released IN (0,1))
    );

    CREATE TABLE IF NOT EXISTS callbacks (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      request_id   TEXT NOT NULL,
      status       TEXT NOT NULL CHECK (status IN ('applied','rejected','released')),
      payload_json TEXT NOT NULL,
      sent_at      TEXT NOT NULL,
      success      INTEGER NOT NULL DEFAULT 0 CHECK (success IN (0,1)),
      attempts     INTEGER NOT NULL DEFAULT 1
    );
  `);

  return _db;
}

/**
 * Return the live DB handle.
 * Throws if initDb() has not been called — keeps startup order explicit.
 */
export function getDb(): Database.Database {
  if (!_db) {
    throw new Error(
      "[bank-sim] DB not initialised. Call initDb() during startup.",
    );
  }
  return _db;
}

/**
 * Close and destroy the singleton — used in tests to get a clean state
 * between test files.
 */
export function closeDb(): void {
  if (_db) {
    _db.close();
    _db = null;
  }
}
