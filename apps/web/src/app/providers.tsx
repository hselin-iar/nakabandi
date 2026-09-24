/**
 * providers.tsx — wraps the app in QueryClient, Router, Toast, Auth and Stream providers.
 * DOC 3 Web App Shell: app/providers.tsx (QueryClient, router, toast, stream provider)
 *
 * C3: StreamProviderPlaceholder replaced with the real SSE StreamProvider.
 */

import React from "react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "./auth/AuthContext";
import { StreamProvider } from "../shared/stream/useStream";
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
            <TooltipProvider delayDuration={200}>
              {children}
              {/* Toast container — positioned top-right, accessible */}
              <Toaster
                position="top-right"
                toastOptions={{
                  duration: 5000,
                  style: {
                    background: "var(--nk-surface-raised, #1e2130)",
                    color: "var(--nk-text-primary, #e2e8f0)",
                    border: "1px solid var(--nk-border-subtle, #2d3748)",
                  },
                }}
              />
            </TooltipProvider>
          </StreamProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
}

