/**
 * providers.tsx — wraps the app in QueryClient, Router, Toast, Auth and Stream providers.
 * DOC 3 Web App Shell: app/providers.tsx (QueryClient, router, toast, stream provider)
 *
 * C3: StreamProviderPlaceholder replaced with the real SSE StreamProvider.
 * Overhaul Phase 2: sonner replaces react-hot-toast; TimeProvider (one rAF loop) sits under StreamProvider.
 */

import React from "react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { AuthProvider } from "./auth/AuthContext";
import { StreamProvider } from "../shared/stream/useStream";
import { TimeProvider } from "../shared/time/TimeProvider";
import { TooltipProvider } from "../shared/ui/Tooltip";

/** TanStack Query client with sensible defaults for the app. */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: 30 s — most data is invalidated by SSE events, not polling.
      staleTime: 30_000,
      // Retry once on failure before surfacing the error to the UI.
      retry: 1,
      // Show errors in ErrorBoundary, not as toast by default.
      throwOnError: false,
    },
    mutations: {
      // Mutations surface errors via the calling component (toast).
      throwOnError: false,
    },
  },
});

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StreamProvider>
            {/* One rAF loop, anchored to sim.time ticks; depends on StreamProvider. */}
            <TimeProvider>
              <TooltipProvider delayDuration={200}>
                {children}
                {/* Toast container: stacked, top-right, themed to the tactical tokens. */}
                <Toaster
                  position="top-right"
                  theme="dark"
                  duration={5000}
                  toastOptions={{
                    style: {
                      background: "var(--nk-surface-elevated)",
                      color: "var(--nk-text-primary)",
                      border: "1px solid var(--nk-border-strong)",
                      borderRadius: "var(--nk-radius-lg)",
                      fontFamily: "var(--nk-font-sans)",
                    },
                  }}
                />
              </TooltipProvider>
            </TimeProvider>
          </StreamProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
}

