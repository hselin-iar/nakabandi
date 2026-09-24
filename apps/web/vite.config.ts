import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// DOC 2 §2.2: React 18 + Vite SPA
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["tests/e2e/**", "node_modules/**"],
    setupFiles: ["src/shared/test/setup.ts"],
  },
  server: {
    // Proxy /api, /sim-control and /bank to the backend processes when running locally
    // (see README "Running the full stack locally"); each must be started separately.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/sim-control": {
        target: "http://localhost:8100",
        changeOrigin: true,
      },
      "/bank": {
        target: "http://localhost:4000",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Route-level code splitting (DOC 3 performance)
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
});
