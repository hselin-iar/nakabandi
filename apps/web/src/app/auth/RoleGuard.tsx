/**
 * RoleGuard.tsx — redirects unauthenticated users to /login.
 * DOC 3 Web App Shell: RoleGuard hides routes and controls, while the API enforces regardless.
 */

import { Navigate, useLocation } from "react-router-dom";
import { usePrincipal } from "./usePrincipal";
import type { Permission } from "../../shared/api/schema.d.ts";

interface RoleGuardProps {
  /** Optional: also require a specific permission. */
  require?: Permission;
  children: React.ReactNode;
}

/**
 * Wrap a route element with RoleGuard.
 * - Unauthenticated → redirect to /login, preserving the intended route.
 * - Authenticated but missing `require` permission → shows a 403 message.
 * - Authenticated and authorised → renders children.
 */
export function RoleGuard({ require: requiredPerm, children }: RoleGuardProps) {
  const location = useLocation();
  const { isAuthenticated, can } = usePrincipal();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredPerm && !can(requiredPerm)) {
    return (
      <div className="nk-not-allowed">
        <h2>Access Denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    );
  }

  return <>{children}</>;
}
