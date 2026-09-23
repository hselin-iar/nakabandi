import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// DOC 2 §2.2: React 18 + Vite SPA
export default defineConfig({
  plugins: [react()],
  server: {
    // Proxy /api to the FastAPI backend when running locally.
    // The API does not exist yet at C1; the proxy will 502 until A3.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
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
