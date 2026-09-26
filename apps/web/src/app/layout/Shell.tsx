/**
 * Shell.tsx — top bar: sim time, role, connection dot.
 * DOC 3 Web App Shell: layout/ → Shell.tsx
 *
 * C3: sim time from useSimTime() (stream-driven); connection dot from useStream().
 * UI: Neomorphic Hybrid Fintech design — design.md
 */

import { usePrincipal } from "../auth/usePrincipal";
import { useStream, useSimTime } from "../../shared/stream/useStream";
import { formatSimTime } from "../../shared/lib/format";
import { roleLabel } from "../../shared/lib/roles";

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
      {/* Dark Sidebar */}
      <SideNav simLabel={simLabel} connectionStatus={status} />

      {/* Right side: topbar + main */}
      <div className="nk-shell__body">
        <header className="nk-topbar" role="banner">
          {/* Greeting / page context */}
          <div className="nk-topbar__greeting">
            <span className="nk-topbar__title">NAKABANDI</span>
            <span className="nk-topbar__subtitle">Financial Crime Detection Platform</span>
          </div>

          {/* Center pill search */}
          <div className="nk-topbar__search">
            <svg
              className="nk-topbar__search-icon"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              aria-hidden="true"
            >
              <circle cx="9" cy="9" r="6" />
              <path d="M15 15l-3.5-3.5" strokeLinecap="round" />
            </svg>
            <input
              className="nk-topbar__search-input"
              type="search"
              placeholder="Search alerts, cases, refs…"
              aria-label="Search"
              id="topbar-search"
            />
          </div>

          {/* Right: role pill, connection, logout */}
          <div className="nk-topbar__right">
            {principal && (
              <>
                <span className="nk-topbar__role" id="principal-role">
                  {roleLabel(principal.role)}
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
import type { Permission, Role } from "../../shared/api/enums.ts";

interface NavItem {
  to: string;
  label: string;
  description: string;
  id: string;
  icon: React.ReactNode;
  require?: Permission;
  allowedRoles?: Role[];
}

/** SVG icon components — inline for zero-dependency icons */
const Icons = {
  Alerts: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 2a6 6 0 0 1 6 6c0 3.5 1.5 5 1.5 5H2.5S4 11.5 4 8a6 6 0 0 1 6-6Z" />
      <path d="M8.5 17a1.5 1.5 0 0 0 3 0" />
    </svg>
  ),
  Clusters: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="10" r="2.5" />
      <circle cx="4" cy="5" r="1.75" />
      <circle cx="16" cy="5" r="1.75" />
      <circle cx="4" cy="15" r="1.75" />
      <circle cx="16" cy="15" r="1.75" />
      <path d="M7.5 8.5 5.5 6.5M12.5 8.5l2-2M7.5 11.5l-2 2M12.5 11.5l2 2" />
    </svg>
  ),
  Map: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="1,3 7,1 13,3 19,1 19,17 13,19 7,17 1,19" />
      <line x1="7" y1="1" x2="7" y2="17" />
      <line x1="13" y1="3" x2="13" y2="19" />
    </svg>
  ),
  Evaluation: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="14" height="14" rx="2.5" />
      <path d="M7 10l2 2 4-4" />
    </svg>
  ),
  Ops: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="10" r="2.5" />
      <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.42 1.42M14.36 14.36l1.42 1.42M4.22 15.78l1.42-1.42M14.36 5.64l1.42-1.42" />
    </svg>
  ),
  Outbox: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 13V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3" />
      <path d="M3 13H7l1.5 2h3L13 13h4" />
      <path d="M10 3v8M7 8l3 3 3-3" />
    </svg>
  ),
  Audit: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H6a1 1 0 0 0-1 1v13l5-3 5 3V4a1 1 0 0 0-1-1Z" />
    </svg>
  ),
  Demo: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4l12 6-12 6V4Z" />
    </svg>
  ),
  Clock: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="10" r="7.5" />
      <path d="M10 6v4l2.5 2.5" />
    </svg>
  ),
};

/**
 * Navigation items — 5 task-shaped destinations (Frontend Strategy §3.1), not 8
 * resource-shaped ones: Triage, Deployment and Investigate answer "what do I do", System
 * Integrity answers "can I trust this" as one destination (tabs inside), Command is the
 * thin ambient landing (reached via the brand mark, not its own sidebar item) and Outbox
 * is demoted to a secondary admin route (its per-alert data now lives in Alert Focus).
 * Each item is gated by permission or specific roles.
 */
const NAV_ITEMS: readonly NavItem[] = [
  { to: "/alerts", label: "Triage", description: "Live fraud alerts awaiting action", id: "nav-alerts", icon: Icons.Alerts, require: "VIEW_ALERTS" },
  { to: "/map", label: "Deployment", description: "Where fraud risk is concentrated right now", id: "nav-map", icon: Icons.Map, require: "VIEW_ALERTS" },
  { to: "/cases", label: "Investigate", description: "Mule networks bundled into investigation cases", id: "nav-cases", icon: Icons.Clusters, require: "VIEW_CASES" },
  { to: "/system", label: "System Integrity", description: "Can this system be trusted — statistically, operationally, tamper-evidently", id: "nav-system", icon: Icons.Evaluation, require: "VIEW_EVALUATION" },
  { to: "/demo", label: "Demo", description: "Simulator controls for demonstrations", id: "nav-demo", icon: Icons.Demo, allowedRoles: ["demo_operator", "admin"] },
];

interface SideNavProps {
  simLabel: string;
  connectionStatus: "streaming" | "polling" | "disconnected";
}

export function SideNav({ simLabel, connectionStatus }: SideNavProps) {
  const { can, principal } = useP();

  return (
    <nav className="nk-sidenav" aria-label="Main navigation">
      {/* Brand mark — links to Command (§3.2/§4.1): thin ambient landing, not its own nav item */}
      <NavLink to="/" end className="nk-sidenav__brand" title="Command">
        <div className="nk-sidenav__logo" aria-hidden="true">NK</div>
        <span className="nk-sidenav__wordmark">Nakabandi</span>
      </NavLink>

      {/* Nav links */}
      <ul className="nk-sidenav__list">
        {NAV_ITEMS.filter((item) => {
          if (item.allowedRoles) {
            return principal && item.allowedRoles.includes(principal.role);
          }
          if (item.require) {
            return can(item.require);
          }
          return true;
        }).map((item) => (
          <li key={item.to}>
            <NavLink
              id={item.id}
              to={item.to}
              title={item.description}
              className={({ isActive }) =>
                `nk-sidenav__link${isActive ? " nk-sidenav__link--active" : ""}`
              }
            >
              <span className="nk-sidenav__icon">{item.icon}</span>
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>

      {/* Footer: sim time + connection status */}
      <div className="nk-sidenav__footer">
        <div className="nk-sidenav__simtime">
          <span className="nk-sidenav__icon" style={{ opacity: 0.6 }}>{Icons.Clock}</span>
          <span>{simLabel}</span>
          <ConnectionDot status={connectionStatus} />
        </div>
        <p className="nk-sidenav__attribution">
          ATM &amp; bank branch locations © OpenStreetMap contributors, ODbL.
        </p>
      </div>
    </nav>
  );
}
