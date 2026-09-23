/**
 * verify.ts — signature verification, timestamp window check, idempotency store.
 * DOC 3 Bank Gateway Simulator: verifySignature(), withinWindow(), IdempotencyStore.
 *
 * SRP: this file owns only cryptographic verification and deduplication.
 * No I/O, no DB calls.
 */

import crypto from "node:crypto";

// ---------------------------------------------------------------------------
// Signature verification (LC-6)
// ---------------------------------------------------------------------------

/**
 * Verify the HMAC-SHA256 signature sent by the NAKABANDI API.
 *
 * The API computes: hex(HMAC-SHA256(secret, timestamp + "." + rawBody))
 * where rawBody is the exact bytes of the POST body.
 *
 * Uses a constant-time comparison to prevent timing attacks.
 */
export function verifySignature(
  secret: string,
  /** The value of X-Nakabandi-Timestamp (epoch seconds string). */
  timestamp: string,
  /** Raw request body bytes. Must be captured before JSON parsing. */
  rawBody: Buffer,
  /** The value of X-Nakabandi-Signature (hex string). */
  signatureHex: string,
): boolean {
  const message = `${timestamp}.${rawBody.toString("utf8")}`;
  const expected = crypto
    .createHmac("sha256", secret)
    .update(message)
    .digest("hex");

  // Constant-time comparison — both strings must be the same length for
  // timingSafeEqual; pad both to 64 hex chars (SHA-256 output).
  const expectedBuf = Buffer.from(expected, "hex");
  const actualBuf = Buffer.from(signatureHex, "hex");

  if (expectedBuf.length !== actualBuf.length) {
    // Different lengths → definitely not equal; avoid leaking which side
    // is shorter via short-circuit. Compare against itself to keep
    // constant-time semantics.
    return !crypto.timingSafeEqual(expectedBuf, expectedBuf) /* always false */;
  }

  return crypto.timingSafeEqual(expectedBuf, actualBuf);
}

// ---------------------------------------------------------------------------
// Timestamp window check (LC-6: window 300 s)
// ---------------------------------------------------------------------------

/**
 * Check whether the request timestamp is within the allowed window.
 *
 * @param timestampSec  X-Nakabandi-Timestamp value (epoch seconds, integer).
 * @param nowSec        Current wall-clock epoch seconds (only used here; never
 *                      used for lien expiry or any domain logic).
 * @param windowSec     Allowed skew in seconds (default 300 = 5 minutes, LC-6).
 */
export function withinWindow(
  timestampSec: number,
  nowSec: number,
  windowSec = 300,
): boolean {
  const delta = Math.abs(nowSec - timestampSec);
  return delta <= windowSec;
}

// ---------------------------------------------------------------------------
// Idempotency store (in-process, per-restart)
// ---------------------------------------------------------------------------

/** Stored response for a previously seen idempotency key. */
export interface StoredResponse {
  statusCode: number;
  body: unknown;
}

/**
 * In-memory idempotency store.
 *
 * Keyed on the value of the `Idempotency-Key` request header.
 * Per DOC 3: "Duplicate delivery with the same key: same response, no second record."
 *
 * This is intentionally in-process (not persisted). A restart clears the map,
 * which means a duplicate delivered after a restart will be stored again —
 * acceptable for the demo scenario.
 */
export class IdempotencyStore {
  private readonly store = new Map<string, StoredResponse>();

  /** Returns the stored response if the key was seen before, otherwise undefined. */
  seen(key: string): StoredResponse | undefined {
    return this.store.get(key);
  }

  /** Records the response for a given key. Call after successfully processing. */
  remember(key: string, response: StoredResponse): void {
    this.store.set(key, response);
  }

  /** Size — for tests. */
  get size(): number {
    return this.store.size;
  }
}

/** Module-level singleton shared across the Express app. */
export const idempotencyStore = new IdempotencyStore();
