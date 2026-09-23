/**
 * AuthContext.tsx — React context for the authenticated principal.
 * DOC 3 Web App Shell: auth/ (usePrincipal, RoleGuard, LoginPage)
 *
 * STUB STRATEGY (C1): manages a hardcoded demo-users fixture list; the "logged-in"
 * principal is stored in React state (no real session). Swap for the real /auth
 * endpoints once Track A Step A4 lands.
 */

import React, { createContext, useState, useCallback } from "react";
import type { Principal, Permission } from "../../shared/api/schema.d.ts";

// ---------------------------------------------------------------------------
// Fixture demo-users (LC-2 Role shapes — DO NOT add roles or fields beyond LC-2)
// ---------------------------------------------------------------------------

export const DEMO_USERS: Principal[] = [
  {
    user_id: "demo-i4c",
    username: "i4c_analyst_1",
    role: "i4c_analyst",
    scope: {},
    permissions: [
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
  },
  {
    user_id: "demo-state",
    username: "state_investigator_1",
    role: "state_investigator",
    scope: { state_id: "UP" },
    permissions: [
      "VIEW_ALERTS",
      "ACKNOWLEDGE",
      "REQUEST_HOLD",
      "NOTIFY_STATION",
      "VIEW_CASES",
      "MARK_OUTCOME",
    ],
  },
  {
    user_id: "demo-district",
    username: "district_officer_1",
    role: "district_officer",
    scope: { state_id: "UP", district_id: "LKO" },
    permissions: ["VIEW_ALERTS", "ACKNOWLEDGE", "NOTIFY_STATION", "VIEW_CASES"],
  },
  {
    user_id: "demo-bank",
    username: "bank_nodal_1",
    role: "bank_nodal",
    scope: {},
    permissions: ["VIEW_ALERTS"],
  },
  {
    user_id: "demo-operator",
    username: "demo_operator_1",
    role: "demo_operator",
    scope: {},
    permissions: ["VIEW_ALERTS", "VIEW_CASES", "VIEW_EVALUATION", "SIM_CONTROL"],
  },
];

// ---------------------------------------------------------------------------
// Context type
// ---------------------------------------------------------------------------

export interface AuthContextValue {
  principal: Principal | null;
  /** Whether the stub session is considered "authenticated". */
  isAuthenticated: boolean;
  /** Check a permission against the current principal. */
  can(permission: Permission): boolean;
  /** Log in as one of the demo principals (stub). */
  loginAs(user: Principal): void;
  /** Clear the session. */
  logout(): void;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

export const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [principal, setPrincipal] = useState<Principal | null>(null);

  const loginAs = useCallback((user: Principal) => {
    setPrincipal(user);
  }, []);

  const logout = useCallback(() => {
    setPrincipal(null);
  }, []);

  const can = useCallback(
    (permission: Permission) => {
      return principal?.permissions.includes(permission) ?? false;
    },
    [principal],
  );

  return (
    <AuthContext.Provider
      value={{
        principal,
        isAuthenticated: principal !== null,
        can,
        loginAs,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
