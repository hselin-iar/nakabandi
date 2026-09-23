/**
 * providers.tsx — wraps the app in QueryClient, Router, Toast and Auth providers.
 * DOC 3 Web App Shell: app/providers.tsx (QueryClient, router, toast, stream provider placeholder)
 *
 * STUB STRATEGY (C1): stream provider is a placeholder (wired in C3).
 */

import React from "react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { AuthProvider } from "./auth/AuthContext";

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

/**
 * StreamProviderPlaceholder — will be replaced by the real SSE provider in C3.
 * For now it is a pass-through so the component tree is already shaped correctly.
 */
function StreamProviderPlaceholder({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <StreamProviderPlaceholder>
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
          </StreamProviderPlaceholder>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
}
