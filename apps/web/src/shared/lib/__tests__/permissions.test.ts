/**
 * permissions.test.ts — table-driven permission matrix tests.
 * DOC 3 C3 Done When: permissions helpers tested.
 */

import { describe, it, expect } from "vitest";
import { can, permissionsForRole, scopeContains } from "../permissions";
import type { Principal } from "../../api/schema.d.ts";

function makePrincipal(
  role: Principal["role"],
  scope: Principal["scope"] = {},
): Principal {
  return {
    user_id: "test",
    username: "test",
    role,
    scope,
    permissions: permissionsForRole(role) as Principal["permissions"],
  };
}

describe("permissionsForRole", () => {
  it("i4c_analyst has all permissions including SIM_CONTROL", () => {
    const perms = permissionsForRole("i4c_analyst");
    expect(perms).toContain("SIM_CONTROL");
    expect(perms).toContain("REQUEST_HOLD");
    expect(perms).toContain("VIEW_AUDIT");
  });
  it("bank_nodal only has VIEW_ALERTS and ACKNOWLEDGE", () => {
    const perms = permissionsForRole("bank_nodal");
    expect(perms).toContain("VIEW_ALERTS");
    expect(perms).toContain("ACKNOWLEDGE");
    expect(perms).not.toContain("REQUEST_HOLD");
    expect(perms).not.toContain("SIM_CONTROL");
  });
  it("demo_operator cannot REQUEST_HOLD", () => {
    expect(permissionsForRole("demo_operator")).not.toContain("REQUEST_HOLD");
  });
  it("district_officer cannot VIEW_AUDIT", () => {
    expect(permissionsForRole("district_officer")).not.toContain("VIEW_AUDIT");
  });
});

describe("can()", () => {
  it("returns false for null principal", () => {
    expect(can(null, "VIEW_ALERTS")).toBe(false);
  });
  it("returns true when principal has the permission", () => {
    const p = makePrincipal("i4c_analyst");
    expect(can(p, "REQUEST_HOLD")).toBe(true);
  });
  it("returns false when principal lacks the permission", () => {
    const p = makePrincipal("bank_nodal");
    expect(can(p, "REQUEST_HOLD")).toBe(false);
  });
  it("returns false when resource scope is outside principal scope", () => {
    const p = makePrincipal("state_investigator", { state_id: "UP" });
    expect(can(p, "VIEW_ALERTS", { state_id: "MH" })).toBe(false);
  });
  it("returns true when resource scope matches principal scope", () => {
    const p = makePrincipal("state_investigator", { state_id: "UP" });
    expect(can(p, "VIEW_ALERTS", { state_id: "UP" })).toBe(true);
  });
});

describe("scopeContains()", () => {
  it("empty principal scope contains any resource scope", () => {
    expect(scopeContains({}, { state_id: "UP" })).toBe(true);
  });
  it("state scope does not contain different state resource", () => {
    expect(scopeContains({ state_id: "UP" }, { state_id: "MH" })).toBe(false);
  });
  it("state scope contains same state resource", () => {
    expect(scopeContains({ state_id: "UP" }, { state_id: "UP" })).toBe(true);
  });
  it("district scope does not contain different district", () => {
    expect(
      scopeContains(
        { state_id: "UP", district_id: "LKO" },
        { state_id: "UP", district_id: "AGR" },
      ),
    ).toBe(false);
  });
});
