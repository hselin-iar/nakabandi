/**
 * usePrincipal.ts — hook to access the authenticated principal and permissions.
 * DOC 3 Web App Shell: usePrincipal(): { principal, permissions, can(permission) }
 *
 * STUB STRATEGY (C1): returns a hardcoded principal with a fixture demo-users list
 * (LC-2 shapes). Swap once Track A Step A4's /auth endpoints exist.
 */

import { useContext } from "react";
import { AuthContext } from "./AuthContext";

export function usePrincipal() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("usePrincipal must be used inside AuthProvider");
  }
  return ctx;
}
