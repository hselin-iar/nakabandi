/**
 * roles.ts — human-readable labels for backend role codes.
 * Single source of truth: previously duplicated separately in Shell.tsx and LoginPage.tsx.
 */

import type { Role } from "../api/enums.ts";

export const ROLE_LABELS: Record<Role, string> = {
  i4c_analyst: "I4C Analyst",
  state_investigator: "State Investigator",
  district_officer: "District Officer",
  bank_nodal: "Bank Nodal",
  demo_operator: "Demo Operator",
  admin: "Admin",
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role as Role] ?? role;
}
