/**
 * vitest.config.ts — test environment for bank-sim.
 *
 * Injects required env vars BEFORE any module is evaluated, so config.ts
 * does not throw when imported by store.ts, server.ts etc. during test
 * collection. The values here are test-only placeholders; they do not
 * need to match any real service.
 */

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    env: {
      NODE_ENV: "test",
      WEBHOOK_SECRET: "test-secret-32-chars-long-for-hmac",
      SESSION_SECRET: "test-session-secret-32-chars-long",
      API_BASE_URL: "http://api.test",
      API_SERVICE_KEY: "test-service-key",
      SIM_STATUS_URL: "http://sim.test/status",
      PORT: "3099",
      CONSOLE_USER: "testuser",
      CONSOLE_PASS: "testpass",
      BANK_SIM_DB_PATH: ":memory:",
    },
    // Run test files sequentially — they share a module-level DB singleton.
    sequence: { concurrent: false },
  },
});
