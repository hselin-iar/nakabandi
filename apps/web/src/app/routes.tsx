/**
 * routes.tsx — route table with RoleGuard.
 * DOC 3 Web App Shell: app/routes.tsx
 *
 * Routes defined in DOC 3 Interfaces & Contracts:
 *   /login, /, /alerts, /alerts/:id, /clusters/:id, /cases, /cases/:id,
 *   /evaluation, /ops, /outbox, /audit, /demo (demo_operator and admin only)
 *
 * Feature page components are stubs at C1 — they will be replaced as
 * each step (C4, C5, C6, C7, C8) lands.
 */

import { Routes, Route, Navigate } from "react-router-dom";
import { Shell } from "./layout/Shell";
import { LoginPage } from "./auth/LoginPage";
import { RoleGuard } from "./auth/RoleGuard";
import { Suspense, lazy } from "react";

// ---------------------------------------------------------------------------
// Lazy-loaded feature page stubs (route-level code splitting, DOC 3)
// Each feature folder provides its own stub; replaced per step.
// ---------------------------------------------------------------------------

const AlertsInbox = lazy(() => import("../features/alerts/AlertsInbox"));
const MapPage = lazy(() => import("../features/map/MapPage"));
const ClustersPage = lazy(() => import("../features/clusters/ClustersPage"));
const CasesPage = lazy(() => import("../features/cases/CasesPage"));
const EvaluationPage = lazy(() => import("../features/evaluation/EvaluationPage"));
const OpsPage = lazy(() => import("../features/ops/OpsPage"));
const DemoPage = lazy(() => import("../features/demo/DemoPage"));

/** Generic page-level loading fallback. */
function PageLoading() {
  return (
    <div className="nk-page-loading" aria-live="polite" aria-label="Loading page">
      Loading…
    </div>
  );
}

/** Generic not-found page. */
function NotFound() {
  return (
    <div className="nk-not-found">
      <h2>Page Not Found</h2>
      <p>The page you requested does not exist.</p>
      <Navigate to="/" replace />
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected: require authentication (and optionally a permission) */}
      <Route
        path="/"
        element={
          <RoleGuard>
            <Shell>
              <Suspense fallback={<PageLoading />}>
                <Routes>
                  <Route index element={<Navigate to="/alerts" replace />} />

                  <Route path="alerts" element={<AlertsInbox />} />
                  <Route path="alerts/:id" element={<AlertsInbox />} />

                  <Route path="map" element={<MapPage />} />

                  <Route
                    path="clusters"
                    element={
                      <RoleGuard require="VIEW_CASES">
                        <ClustersPage />
                      </RoleGuard>
                    }
                  />
                  <Route
                    path="clusters/:id"
                    element={
                      <RoleGuard require="VIEW_CASES">
                        <ClustersPage />
                      </RoleGuard>
                    }
                  />

                  <Route
                    path="cases"
                    element={
                      <RoleGuard require="VIEW_CASES">
                        <CasesPage />
                      </RoleGuard>
                    }
                  />
                  <Route
                    path="cases/:id"
                    element={
                      <RoleGuard require="VIEW_CASES">
                        <CasesPage />
                      </RoleGuard>
                    }
                  />

                  <Route
                    path="evaluation"
                    element={
                      <RoleGuard require="VIEW_EVALUATION">
                        <EvaluationPage />
                      </RoleGuard>
                    }
                  />

                  <Route
                    path="ops"
                    element={
                      <RoleGuard require="SIM_CONTROL">
                        <OpsPage />
                      </RoleGuard>
                    }
                  />

                  <Route
                    path="outbox"
                    element={
                      <RoleGuard require="VIEW_AUDIT">
                        <EvaluationPage />
                      </RoleGuard>
                    }
                  />

                  <Route
                    path="audit"
                    element={
                      <RoleGuard require="VIEW_AUDIT">
                        <EvaluationPage />
                      </RoleGuard>
                    }
                  />

                  <Route
                    path="demo"
                    element={
                      <RoleGuard require="SIM_CONTROL">
                        <DemoPage />
                      </RoleGuard>
                    }
                  />

                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </Shell>
          </RoleGuard>
        }
      />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
