import { Navigate, useLocation } from "react-router-dom";
import { usePrincipal } from "./usePrincipal";
import type { Permission, Role } from "../../shared/api/enums.ts";

interface RoleGuardProps {
  /** Optional: also require a specific permission. */
  require?: Permission;
  /** Optional: restrict route to specific roles (e.g. demo_operator, admin for /demo). */
  allowedRoles?: Role[];
  children: React.ReactNode;
}

/**
 * Wrap a route element with RoleGuard.
 * - Unauthenticated → redirect to /login, preserving the intended route.
 * - Authenticated but missing `require` permission or not in `allowedRoles` → shows a 403 message.
 * - Authenticated and authorised → renders children.
 */
export function RoleGuard({ require: requiredPerm, allowedRoles, children }: RoleGuardProps) {
  const location = useLocation();
  const { isAuthenticated, isReady, principal, can } = usePrincipal();

  if (!isReady) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredPerm && !can(requiredPerm)) {
    return (
      <div className="nk-not-allowed" data-testid="access-denied">
        <h2>Access Denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    );
  }

  if (allowedRoles && (!principal || !allowedRoles.includes(principal.role))) {
    return (
      <div className="nk-not-allowed" data-testid="access-denied">
        <h2>Access Denied</h2>
        <p>You do not have permission to view this page.</p>
      </div>
    );
  }

  return <>{children}</>;
}
