/**
 * AuthContext.tsx — React context for the authenticated principal.
 * DOC 3 Web App Shell: auth/ (usePrincipal, RoleGuard, LoginPage)
 *
 * Real session: POST /auth/login sets an HttpOnly cookie (access/interfaces/routers.py); this
 * provider never sees the cookie itself, only GET /auth/me's response. On mount it checks for an
 * existing session so a page reload doesn't bounce a logged-in user back to /login.
 */

import React, { createContext, useCallback, useEffect, useState } from "react";

import { apiClient } from "../../shared/api/client";
import type { Permission } from "../../shared/api/enums.ts";
import type { MeResponse, Principal } from "../../shared/api/types.ts";

function toPrincipal(me: MeResponse): Principal {
  return {
    user_id: me.user_id,
    name: me.name,
    role: me.role as Principal["role"],
    scope: me.scope as Principal["scope"],
    permissions: me.permissions as Permission[],
  };
}

// ---------------------------------------------------------------------------
// Context type
// ---------------------------------------------------------------------------

export interface AuthContextValue {
  principal: Principal | null;
  /** True once the initial GET /auth/me check has finished (either way). */
  isReady: boolean;
  isAuthenticated: boolean;
  can(permission: Permission): boolean;
  /** Real login: POST /auth/login, then GET /auth/me for scope + permissions. */
  login(username: string, password: string): Promise<void>;
  logout(): Promise<void>;
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
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .GET("/auth/me")
      .then(({ data }) => {
        if (!cancelled && data) setPrincipal(toPrincipal(data));
      })
      .finally(() => {
        if (!cancelled) setIsReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const { error } = await apiClient.POST("/auth/login", {
      body: { username, password },
    });
    if (error) throw new Error("Login failed");
    const { data: me, error: meError } = await apiClient.GET("/auth/me");
    if (meError || !me) throw new Error("Login succeeded but /auth/me failed");
    setPrincipal(toPrincipal(me));
  }, []);

  const logout = useCallback(async () => {
    await apiClient.POST("/auth/logout");
    setPrincipal(null);
  }, []);

  const can = useCallback(
    (permission: Permission) => principal?.permissions.includes(permission) ?? false,
    [principal],
  );

  return (
    <AuthContext.Provider
      value={{
        principal,
        isReady,
        isAuthenticated: principal !== null,
        can,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
