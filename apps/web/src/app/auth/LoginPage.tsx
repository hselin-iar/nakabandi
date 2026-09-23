/**
 * LoginPage.tsx — login screen with quick-login buttons for each demo role.
 * DOC 3 Web App Shell: LoginPage.tsx (with quick-login buttons)
 *
 * STUB STRATEGY (C1): no API call — invokes loginAs() with a fixture principal.
 * Swap for POST /auth/login once Track A Step A4 lands.
 */

import { useLocation, useNavigate } from "react-router-dom";
import { DEMO_USERS } from "./AuthContext";
import { usePrincipal } from "./usePrincipal";
import type { Principal } from "../../shared/api/schema.d.ts";

// Role display labels
const ROLE_LABELS: Record<Principal["role"], string> = {
  i4c_analyst: "I4C Analyst",
  state_investigator: "State Investigator",
  district_officer: "District Officer",
  bank_nodal: "Bank Nodal",
  demo_operator: "Demo Operator",
  admin: "Admin",
};

export function LoginPage() {
  const { loginAs, isAuthenticated } = usePrincipal();
  const navigate = useNavigate();
  const location = useLocation();
  const from: string = (location.state as { from?: { pathname: string } })?.from?.pathname ?? "/";

  // If already logged in, redirect immediately
  if (isAuthenticated) {
    navigate(from, { replace: true });
    return null;
  }

  function handleQuickLogin(user: Principal) {
    loginAs(user);
    navigate(from, { replace: true });
  }

  return (
    <div className="nk-login-page">
      <div className="nk-login-card">
        <div className="nk-login-header">
          <h1>NAKABANDI</h1>
          <p className="nk-login-tagline">
            Predict. Intercept. Protect.
          </p>
        </div>

        <div className="nk-login-body">
          <p className="nk-login-label">Quick-login (demo mode)</p>
          <div className="nk-quick-login-grid">
            {DEMO_USERS.map((user) => (
              <button
                key={user.user_id}
                id={`quick-login-${user.role}`}
                className="nk-quick-login-btn"
                onClick={() => handleQuickLogin(user)}
              >
                <span className="nk-btn-role">{ROLE_LABELS[user.role]}</span>
                <span className="nk-btn-username">{user.username}</span>
              </button>
            ))}
          </div>
        </div>

        <p className="nk-login-footer">
          Demo credentials only — no real data. Real /auth endpoints land at Track A Step A4.
        </p>
      </div>
    </div>
  );
}
