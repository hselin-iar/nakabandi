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
  // maplibre-gl uses a Web Worker internally. Vite's dependency pre-bundling inlines
  // the worker as a blob: URL that MapLibre cannot resolve at runtime, causing
  // "Worker failed to load" and a blank canvas.
  // Excluding it from optimizeDeps lets MapLibre use its own bundled worker URL.
  optimizeDeps: {
    exclude: ["maplibre-gl"],
  },
  server: {
    // Proxy /api, /sim-control and /bank to the backend processes when running locally.
    // Ports avoid conflicts with other projects: API on 8001 (not 8000), etc.
    // docker-compose.yml maps container:8000 → host:8001 for exactly this reason.
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/sim-control": {
        target: "http://localhost:8101",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/sim-control/, "/control"),
      },
      "/bank": {
        target: "http://localhost:4001",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Disable CSS minification: esbuild's native binary is unavailable in some Alpine/Docker
    // environments; lightningcss fails the same way. For a demo build this is acceptable —
    // CSS is still bundled, just not minified. Flip to "esbuild" locally if needed.
    cssMinify: false,
    // Route-level code splitting (DOC 3 performance)
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
});
