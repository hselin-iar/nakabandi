/**
 * LoginPage.tsx — login screen with quick-login buttons for each demo role.
 * DOC 3 Web App Shell: LoginPage.tsx (with quick-login buttons)
 *
 * Real: GET /auth/demo-users for the button list, POST /auth/login (via usePrincipal().login)
 * on click.
 */

import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { apiClient } from "../../shared/api/client";
import type { DemoUserResponse } from "../../shared/api/types.ts";
import { usePrincipal } from "./usePrincipal";
import { roleLabel } from "../../shared/lib/roles";

export function LoginPage() {
  const { login, isAuthenticated } = usePrincipal();
  const navigate = useNavigate();
  const location = useLocation();
  const from: string = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/";

  const [demoUsers, setDemoUsers] = useState<DemoUserResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .GET("/auth/demo-users")
      .then(({ data }) => setDemoUsers(data ?? []))
      .catch(() => setDemoUsers([]));
  }, []);

  useEffect(() => {
    if (isAuthenticated) navigate(from, { replace: true });
  }, [isAuthenticated, from, navigate]);

  if (isAuthenticated) return null;

  async function handleQuickLogin(user: DemoUserResponse) {
    setError(null);
    try {
      await login(user.username, user.password);
      navigate(from, { replace: true });
    } catch {
      setError("Login failed. The demo credentials may have changed — try again.");
    }
  }

  return (
    <div className="nk-login-page">
      <div className="nk-login-card">
        <div className="nk-login-header">
          <h1>NAKABANDI</h1>
          <p className="nk-login-tagline">Predict. Intercept. Protect.</p>
        </div>

        <div className="nk-login-body">
          <p className="nk-login-label">Quick-login (demo mode)</p>
          {error && <p className="nk-login-error">{error}</p>}
          <div className="nk-quick-login-grid">
            {demoUsers.map((user) => (
              <button
                key={user.role}
                id={`quick-login-${user.role}`}
                className="nk-quick-login-btn"
                onClick={() => handleQuickLogin(user)}
              >
                <span className="nk-btn-role">{roleLabel(user.role)}</span>
                <span className="nk-btn-username">{user.display_name}</span>
              </button>
            ))}
          </div>
        </div>

        <p className="nk-login-footer">Demo credentials only — no real data.</p>
      </div>
    </div>
  );
}
