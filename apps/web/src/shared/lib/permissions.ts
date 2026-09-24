/**
 * permissions.ts — client-side permission helpers.
 * DOC 3 Web App Shell: shared/lib/permissions.ts
 *
 * Mirrors the server-side permission matrix from DOC 3 §M5 (the API enforces
 * regardless; these helpers drive UI rendering only).
 *
 * SRP: pure functions, no React, no I/O.
 */

import type { Permission, Role } from "../api/enums.ts";
import type { Principal, Scope } from "../api/types.ts";

// ---------------------------------------------------------------------------
// Permission matrix (DOC 3 §M5, policy.yaml — DO NOT add rows not in LC-2)
// ---------------------------------------------------------------------------

const PERMISSION_MATRIX: Record<Role, readonly Permission[]> = {
  i4c_analyst: [
    "VIEW_ALERTS",
    "ACKNOWLEDGE",
    "REQUEST_HOLD",
    "NOTIFY_STATION",
    "DISPATCH",
    "OVERRIDE",
    "MARK_OUTCOME",
    "CREATE_EVIDENCE",
    "VIEW_CASES",
    "VIEW_AUDIT",
    "VIEW_EVALUATION",
    "SIM_CONTROL",
  ],
  state_investigator: [
    "VIEW_ALERTS",
    "ACKNOWLEDGE",
    "REQUEST_HOLD",
    "NOTIFY_STATION",
    "DISPATCH",
    "MARK_OUTCOME",
    "CREATE_EVIDENCE",
    "VIEW_CASES",
    "VIEW_AUDIT",
    "VIEW_EVALUATION",
  ],
  district_officer: [
    "VIEW_ALERTS",
    "ACKNOWLEDGE",
    "NOTIFY_STATION",
    "DISPATCH",
    "MARK_OUTCOME",
    "CREATE_EVIDENCE",
    "VIEW_CASES",
    "VIEW_EVALUATION",
  ],
  bank_nodal: [
    "VIEW_ALERTS",
    "ACKNOWLEDGE",
  ],
  demo_operator: [
    "VIEW_ALERTS",
    "VIEW_CASES",
    "VIEW_EVALUATION",
    "SIM_CONTROL",
  ],
  admin: [
    "VIEW_ALERTS",
    "ACKNOWLEDGE",
    "REQUEST_HOLD",
    "NOTIFY_STATION",
    "DISPATCH",
    "OVERRIDE",
    "MARK_OUTCOME",
    "CREATE_EVIDENCE",
    "VIEW_CASES",
    "VIEW_AUDIT",
    "VIEW_EVALUATION",
    "SIM_CONTROL",
  ],
};

// ---------------------------------------------------------------------------
// Scope containment check
// ---------------------------------------------------------------------------

/**
 * Return true if `principal.scope` contains `resourceScope`.
 *
 * Rules (DOC 3 §M5):
 *   - district within state: principal's state_id must equal resource's state_id
 *   - bank equal: principal's bank_id must equal resource's bank_id
 *   - A scope with no restrictions contains any resource.
 */
export function scopeContains(
  principalScope: Scope,
  resourceScope: Scope,
): boolean {
  if (
    resourceScope.state_id != null &&
    principalScope.state_id != null &&
    principalScope.state_id !== resourceScope.state_id
  ) {
    return false;
  }
  if (
    resourceScope.district_id != null &&
    principalScope.district_id != null &&
    principalScope.district_id !== resourceScope.district_id
  ) {
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// can() — check permission for a principal
// ---------------------------------------------------------------------------

/**
 * Check whether a principal has a given permission.
 *
 * Uses the permissions array carried on the Principal (set by the server).
 * Falls back to the local matrix when the array is absent (e.g. stub fixtures).
 *
 * @param principal     Authenticated principal, or null (unauthenticated).
 * @param permission    The permission to check.
 * @param resourceScope Optional: restrict check to a scope subset.
 */
export function can(
  principal: Principal | null,
  permission: Permission,
  resourceScope?: Scope,
): boolean {
  if (!principal) return false;

  // Prefer the server-provided permissions array.
  const permissions: readonly Permission[] =
    principal.permissions.length > 0
      ? principal.permissions
      : (PERMISSION_MATRIX[principal.role] ?? []);

  if (!permissions.includes(permission)) return false;

  if (resourceScope) {
    return scopeContains(principal.scope, resourceScope);
  }

  return true;
}

/**
 * Get the full permissions list for a role from the local matrix.
 * Used for testing and stubs; real permissions come from the API.
 */
export function permissionsForRole(role: Role): readonly Permission[] {
  return PERMISSION_MATRIX[role] ?? [];
}
