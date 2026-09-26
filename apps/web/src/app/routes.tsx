/**
 * routes.tsx — route table with RoleGuard.
 * DOC 3 Web App Shell: app/routes.tsx
 *
 * Base routes defined in DOC 3 Interfaces & Contracts:
 *   /login, /, /alerts, /alerts/:id, /clusters/:id, /cases, /cases/:id,
 *   /evaluation, /ops, /outbox, /audit, /demo (demo_operator and admin only)
 *
 * Restructured per the Frontend Strategy doc's 5-destination IA (§3): /clusters (bare) and
 * /evaluation, /ops, /audit now redirect to /cases and /system respectively — /system tabs
 * Evaluation/Ops/Audit under one "can I trust this system?" destination. Every original path
 * above still resolves (redirect, not removed), so bookmarks/deep links keep working.
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
const DashboardPage = lazy(() => import("../features/dashboard/DashboardPage"));
const MapPage = lazy(() => import("../features/map/MapPage"));
const ClustersPage = lazy(() => import("../features/clusters/ClustersPage"));
const CasesPage = lazy(() => import("../features/cases/CasesPage"));
const SystemIntegrityPage = lazy(() => import("../features/system/SystemIntegrityPage"));
const OutboxPage = lazy(() => import("../features/outbox/OutboxPage"));
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
        path="/*"
        element={
          <RoleGuard>
            <Shell>
              <Suspense fallback={<PageLoading />}>
                <Routes>
                  <Route index element={<DashboardPage />} />

                  <Route path="alerts" element={<AlertsInbox />} />
                  <Route path="alerts/:id" element={<AlertsInbox />} />

                  <Route path="map" element={<MapPage />} />

                  {/* Investigate (§4.4): Cases is the primary list; a bare /clusters list
                      duplicated it, so it now redirects there. /clusters/:id remains a deep
                      link (e.g. from an alert's cluster_ref) and still renders ClustersPage. */}
                  <Route path="clusters" element={<Navigate to="/cases" replace />} />
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

                  {/* System Integrity (§4.5): Evaluation/Ops/Audit as tabs under one
                      destination; the old routes redirect, preserving deep links/bookmarks.
                      Permission gating happens per-tab inside the page itself. */}
                  <Route path="system" element={<SystemIntegrityPage />} />
                  <Route
                    path="evaluation"
                    element={<Navigate to="/system?tab=evaluation" replace />}
                  />
                  <Route path="ops" element={<Navigate to="/system?tab=ops" replace />} />
                  <Route path="audit" element={<Navigate to="/system?tab=audit" replace />} />

                  {/* Outbox (§4.6): demoted from primary nav to an admin-only debugging
                      route; per-alert delivery status now lives inline in Alert Focus. */}
                  <Route
                    path="outbox"
                    element={
                      <RoleGuard require="VIEW_AUDIT">
                        <OutboxPage />
                      </RoleGuard>
                    }
                  />

                  <Route
                    path="demo"
                    element={
                      <RoleGuard allowedRoles={["demo_operator", "admin"]}>
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
