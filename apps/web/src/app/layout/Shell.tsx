/**
 * Shell.tsx — top bar: sim time, role, connection dot.
 * DOC 3 Web App Shell: layout/ → Shell.tsx
 *
 * C3: sim time from useSimTime() (stream-driven); connection dot from useStream().
 */

import { usePrincipal } from "../auth/usePrincipal";
import { useStream, useSimTime } from "../../shared/stream/useStream";
import { formatSimTime } from "../../shared/lib/format";


// Role display labels (same map as LoginPage)
const ROLE_LABELS: Record<string, string> = {
  i4c_analyst: "I4C Analyst",
  state_investigator: "State Investigator",
  district_officer: "District Officer",
  bank_nodal: "Bank Nodal",
  demo_operator: "Demo Operator",
  admin: "Admin",
};

/**
 * Connection status dot — amber = degraded / polling, green = streaming.
 * At C1 it is always amber (no stream connected yet).
 */
function ConnectionDot({ status }: { status: "streaming" | "polling" | "disconnected" }) {
  const label =
    status === "streaming"
      ? "Live stream"
      : status === "polling"
        ? "Polling — stream degraded"
        : "Disconnected";
  const colorClass =
    status === "streaming"
      ? "nk-dot--green"
      : status === "polling"
        ? "nk-dot--amber"
        : "nk-dot--red";
  return (
    <span
      className={`nk-connection-dot ${colorClass}`}
      role="status"
      aria-label={label}
      title={label}
    />
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { principal, logout } = usePrincipal();
  const { status } = useStream();
  const simTime = useSimTime();

  const simLabel = simTime
    ? `SIM ${formatSimTime(simTime)}`
    : "SIM --:--";

  return (
    <div className="nk-shell">
      <header className="nk-topbar" role="banner">
        <span className="nk-topbar__brand">NAKABANDI</span>

        <span className="nk-topbar__simtime" aria-label="Simulator time">
          {simLabel}
        </span>

        <div className="nk-topbar__right">
          {principal && (
            <>
              <span className="nk-topbar__role">
                {ROLE_LABELS[principal.role] ?? principal.role}
              </span>
              <ConnectionDot status={status} />
              <button
                id="topbar-logout-btn"
                className="nk-topbar__logout"
                onClick={logout}
              >
                Log out
              </button>
            </>
          )}
        </div>
      </header>

      <div className="nk-shell__body">
        <SideNav />
        <main className="nk-main" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SideNav
// ---------------------------------------------------------------------------

import { NavLink } from "react-router-dom";
import { usePrincipal as useP } from "../auth/usePrincipal";

/** Navigation items. Each `require` is a permission from LC-2 Permission enum. */
const NAV_ITEMS = [
  { to: "/alerts", label: "Alerts", id: "nav-alerts", require: "VIEW_ALERTS" },
  { to: "/clusters", label: "Clusters & Cases", id: "nav-clusters", require: "VIEW_CASES" },
  { to: "/map", label: "Map", id: "nav-map", require: "VIEW_ALERTS" },
  { to: "/evaluation", label: "Evaluation", id: "nav-evaluation", require: "VIEW_EVALUATION" },
  { to: "/ops", label: "Ops", id: "nav-ops", require: "SIM_CONTROL" },
  { to: "/outbox", label: "Outbox", id: "nav-outbox", require: "VIEW_AUDIT" },
  { to: "/audit", label: "Audit", id: "nav-audit", require: "VIEW_AUDIT" },
  { to: "/demo", label: "Demo", id: "nav-demo", require: "SIM_CONTROL" },
] as const;

export function SideNav() {
  const { can } = useP();

  return (
    <nav className="nk-sidenav" aria-label="Main navigation">
      <ul className="nk-sidenav__list">
        {NAV_ITEMS.filter((item) => can(item.require as Parameters<typeof can>[0])).map((item) => (
          <li key={item.to}>
            <NavLink
              id={item.id}
              to={item.to}
              className={({ isActive }) =>
                `nk-sidenav__link${isActive ? " nk-sidenav__link--active" : ""}`
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
