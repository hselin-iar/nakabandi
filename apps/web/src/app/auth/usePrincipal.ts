/**
 * usePrincipal.ts — hook to access the authenticated principal and permissions.
 * DOC 3 Web App Shell: usePrincipal(): { principal, permissions, can(permission) }
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
