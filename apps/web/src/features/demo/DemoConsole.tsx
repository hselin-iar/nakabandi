/**
 * DemoConsole.tsx — World Simulator Control & Guided-Demo Console.
 * DOC 3 M1 · LC-8 · DOC 2 §2.7 · DOC 4 Step C8
 *
 * Controls:
 *   - Start / Pause / Resume / Speed (1..60, capped in hosted mode)
 *   - Reset / Seed (Admin restricted in hosted mode)
 *   - Inject Cluster (district_id, size, fast_weight, locality)
 *   - Dynamic Quick-Login buttons (loaded from /auth/demo-users — NO hardcoded credentials)
 *   - Proxied Request Log (/sim-control/* audit trail)
 *   - Hosted "DEMO MODE" Banner
 */

import React, { useState } from "react";
import { format } from "date-fns";
import { useDemoControl, useDemoUsers } from "./api/useDemoControl";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { formatSimTime } from "../../shared/lib/format";
import { Select } from "../../shared/ui/Select";
import type { DemoUser } from "./types";
import type { InjectClusterRequest } from "./types";
import { Icon } from "../../shared/ui/Icon";

const DISTRICT_PRESETS = [
  { id: "UP-LKO", label: "Lucknow (UP-LKO)" },
  { id: "MH-MUM", label: "Mumbai (MH-MUM)" },
  { id: "JH-RAN", label: "Ranchi (JH-RAN)" },
  { id: "HR-GGN", label: "Gurugram (HR-GGN)" },
];

const SPEED_PRESETS = [1, 5, 10, 30, 60];

export function DemoConsole() {
  const { principal, login } = usePrincipal();
  const isAdmin = principal?.role === "admin";

  const {
    status,
    startSimulation,
    isStarting,
    pauseSimulation,
    isPausing,
    resumeSimulation,
    isResuming,
    setSpeed,
    isSettingSpeed,
    resetSimulation,
    isResetting,
    injectCluster,
    isInjecting,
    requestLog,
    clearRequestLog,
    refetchStatus,
  } = useDemoControl();

  const { data: demoUsers, isLoading: isLoadingUsers } = useDemoUsers();

  // Control form states
  const [scenario, setScenario] = useState<"free" | "guided_demo">("free");
  const [speedFactor, setSpeedFactor] = useState<number>(status.speed || 1);
  const [seedInput, setSeedInput] = useState<string>(String(status.seed || 42));

  // Injection state
  const [injectDistrict, setInjectDistrict] = useState("UP-LKO");
  const [injectSize, setInjectSize] = useState<number>(25);
  const [injectFastWeight, setInjectFastWeight] = useState<number>(0.6);
  const [injectLocality, setInjectLocality] = useState<
    "district" | "multi_district" | "state" | "multi_state"
  >("district");
  const [injectResult, setInjectResult] = useState<string | null>(null);
  const [injectErrorMsg, setInjectErrorMsg] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Status values
  const isRunning = status.state === "running";
  const isPaused = status.state === "paused";

  const formattedSimTime = React.useMemo(() => {
    if (!status.sim_time) return "SIM 00:00:00";
    const iso =
      typeof status.sim_time === "number"
        ? status.sim_time > 1e11
          ? new Date(status.sim_time).toISOString()
          : new Date(status.sim_time * 1000).toISOString()
        : String(status.sim_time);
    return formatSimTime(iso, { includeSeconds: true });
  }, [status.sim_time]);

  // Handlers
  async function handleStart() {
    setActionNotice(null);
    try {
      const res = await startSimulation({ scenario, speed: speedFactor });
      setActionNotice(`Simulation started (${res.status || "OK"})${res.run_id ? ` [${res.run_id}]` : ""}`);
    } catch (err: unknown) {
      setActionNotice(`Start failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function handlePause() {
    setActionNotice(null);
    try {
      await pauseSimulation();
      setActionNotice("Simulation paused");
    } catch (err: unknown) {
      setActionNotice(`Pause failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function handleResume() {
    setActionNotice(null);
    try {
      await resumeSimulation();
      setActionNotice("Simulation resumed");
    } catch (err: unknown) {
      setActionNotice(`Resume failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function handleSetSpeed(factor: number) {
    setActionNotice(null);
    const capped = Math.min(Math.max(factor, 1), 60);
    setSpeedFactor(capped);
    try {
      await setSpeed({ factor: capped });
      setActionNotice(`Simulation speed set to ${capped}x`);
    } catch (err: unknown) {
      setActionNotice(`Speed change failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function handleReset() {
    setActionNotice(null);
    if (!isAdmin) {
      setActionNotice("Hosted mode protection: only admin may reset and re-seed the simulation.");
      return;
    }
    const seed = seedInput.trim() ? parseInt(seedInput, 10) : undefined;
    try {
      await resetSimulation({ seed: isNaN(seed as number) ? undefined : seed });
      setActionNotice(`Simulation reset with seed ${seed ?? status.seed}`);
    } catch (err: unknown) {
      setActionNotice(`Reset failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function handleInjectCluster(e: React.FormEvent) {
    e.preventDefault();
    setInjectResult(null);
    setInjectErrorMsg(null);

    const payload: InjectClusterRequest = {
      district_id: injectDistrict,
      size: Math.min(Math.max(Number(injectSize) || 1, 1), 500),
      fast_weight: Math.min(Math.max(Number(injectFastWeight) || 0, 0), 1),
      locality: injectLocality,
    };

    try {
      const res = await injectCluster(payload);
      setInjectResult(`Cluster injected successfully: ID ${res.cluster_id || "ack"}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setInjectErrorMsg(`Injection failed: ${msg}`);
    }
  }

  async function handleQuickLogin(user: DemoUser) {
    if (!user.password) {
      setActionNotice("Cannot switch: demo credentials unavailable (server list did not load).");
      return;
    }
    try {
      await login(user.username, user.password);
      setActionNotice(`Switched role to ${user.display_name} (${user.role})`);
    } catch {
      setActionNotice(`Failed to switch role to ${user.display_name}.`);
    }
  }

  return (
    <div className="nk-demo-console" data-testid="demo-console">
      {/* ------------------------------------------------------------------- */}
      {/* Top Banner: Hosted DEMO MODE Protections                            */}
      {/* ------------------------------------------------------------------- */}
      <div className="nk-demo-banner" data-testid="demo-mode-banner">
        <div className="nk-demo-banner__top">
          <span className="nk-demo-banner__badge">DEMO MODE ACTIVE</span>
          <span className="nk-demo-banner__title">Hosted Simulator Protections Enforced</span>
        </div>
        <p className="nk-demo-banner__desc">
          Safe demonstration environment. All mutations route strictly through the authenticated{" "}
          <code>/sim-control/*</code> reverse proxy path (DOC 2 §2.2 / §2.7).
        </p>
        <div className="nk-demo-banner__specs">
          <span className="nk-demo-banner__pill"><Icon name="bolt" size={12} /> Speed Capped at 60x</span>
          <span className="nk-demo-banner__pill"><Icon name="lock" size={12} /> Reset/Seed Restricted to Admin</span>
          <span className="nk-demo-banner__pill">⏱ Auto-Pause on Inactivity</span>
          <span className="nk-demo-banner__pill"><Icon name="shield" size={12} /> Reverse Proxy Auth Gated</span>
        </div>
      </div>

      {actionNotice && (
        <div className="nk-demo-alert nk-demo-alert--info" role="status">
          {actionNotice}
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Main Grid: Status & Controls                                        */}
      {/* ------------------------------------------------------------------- */}
      <div className="nk-demo-grid">
        {/* Card 1: Live Status */}
        <section className="nk-demo-card" data-testid="sim-status-card">
          <div className="nk-demo-card__header">
            <h3>Simulator Status</h3>
            <span
              className={`nk-demo-status-pill nk-demo-status-pill--${status.state.toLowerCase()}`}
              data-testid="sim-status-state"
            >
              {status.state.toUpperCase()}
            </span>
          </div>

          <div className="nk-demo-status-items">
            <div className="nk-demo-status-row">
              <span className="nk-demo-label">Sim Time</span>
              <span className="nk-demo-val nk-mono" data-testid="sim-status-time">
                {formattedSimTime}
              </span>
            </div>
            <div className="nk-demo-status-row">
              <span className="nk-demo-label">Speed</span>
              <span className="nk-demo-val" data-testid="sim-status-speed">
                {status.speed}x
              </span>
            </div>
            <div className="nk-demo-status-row">
              <span className="nk-demo-label">RNG Seed</span>
              <span className="nk-demo-val nk-mono" data-testid="sim-status-seed">
                {status.seed}
              </span>
            </div>
            <div className="nk-demo-status-row">
              <span className="nk-demo-label">Scenario</span>
              <span className="nk-demo-val" data-testid="sim-status-scenario">
                {status.scenario}
              </span>
            </div>
          </div>

          <div className="nk-demo-counts-grid">
            <div className="nk-demo-count-box">
              <span className="nk-demo-count-box__label">Complaints</span>
              <span className="nk-demo-count-box__val">{status.counts.complaints.toLocaleString()}</span>
            </div>
            <div className="nk-demo-count-box">
              <span className="nk-demo-count-box__label">Cash-Outs</span>
              <span className="nk-demo-count-box__val">{status.counts.cashouts.toLocaleString()}</span>
            </div>
            <div className="nk-demo-count-box">
              <span className="nk-demo-count-box__label">Engine Ticks</span>
              <span className="nk-demo-count-box__val">{status.counts.ticks.toLocaleString()}</span>
            </div>
          </div>

          {status.last_error && (
            <div className="nk-demo-error-banner" role="alert">
              <div className="nk-demo-error-banner__headline">
                <strong>World-sim isn't responding as expected.</strong>
                <span>
                  The engine may have stalled or the runner process may be down. Retry the
                  status check, or restart the simulation below.
                </span>
              </div>
              <div className="nk-demo-error-banner__actions">
                <button
                  type="button"
                  className="nk-btn nk-btn--outline nk-btn--sm"
                  onClick={() => void refetchStatus()}
                >
                  ↻ Retry Status Check
                </button>
                <details className="nk-demo-error-banner__detail">
                  <summary>Technical detail</summary>
                  <code>{status.last_error}</code>
                </details>
              </div>
            </div>
          )}
        </section>

        {/* Card 2: Runner Execution Controls */}
        <section className="nk-demo-card">
          <div className="nk-demo-card__header">
            <h3>Execution Controls</h3>
            <span className="nk-demo-subtext">Start, pause, or adjust speed</span>
          </div>

          <div className="nk-demo-section">
            <label className="nk-demo-form-label">Scenario</label>
            <div className="nk-demo-scenario-radios">
              <label className="nk-demo-radio">
                <input
                  type="radio"
                  name="scenario"
                  value="free"
                  checked={scenario === "free"}
                  onChange={() => setScenario("free")}
                  disabled={isRunning}
                />
                <span>Free Play</span>
              </label>
              <label className="nk-demo-radio">
                <input
                  type="radio"
                  name="scenario"
                  value="guided_demo"
                  checked={scenario === "guided_demo"}
                  onChange={() => setScenario("guided_demo")}
                  disabled={isRunning}
                />
                <span>Guided Demo</span>
              </label>
            </div>
          </div>

          <div className="nk-demo-btn-row">
            <button
              id="btn-sim-start"
              className="nk-btn nk-btn--primary"
              data-testid="sim-btn-start"
              onClick={handleStart}
              disabled={isStarting || isRunning}
            >
              {isStarting ? "Starting…" : "Start Simulation"}
            </button>
            <button
              id="btn-sim-pause"
              className="nk-btn nk-btn--secondary"
              data-testid="sim-btn-pause"
              onClick={handlePause}
              disabled={isPausing || !isRunning}
            >
              {isPausing ? "Pausing…" : "Pause"}
            </button>
            <button
              id="btn-sim-resume"
              className="nk-btn nk-btn--secondary"
              data-testid="sim-btn-resume"
              onClick={handleResume}
              disabled={isResuming || !isPaused}
            >
              {isResuming ? "Resuming…" : "Resume"}
            </button>
          </div>

          {/* Speed Controls */}
          <div className="nk-demo-section" style={{ marginTop: "var(--nk-space-4)" }}>
            <label className="nk-demo-form-label" htmlFor="sim-speed-input">
              Speed Factor (1x – 60x max)
            </label>
            <div className="nk-demo-speed-row">
              <input
                id="sim-speed-input"
                type="number"
                min="1"
                max="60"
                step="1"
                className="nk-input"
                data-testid="sim-speed-input"
                value={speedFactor}
                onChange={(e) => setSpeedFactor(Number(e.target.value))}
              />
              <button
                className="nk-btn nk-btn--secondary"
                data-testid="sim-btn-speed"
                onClick={() => handleSetSpeed(speedFactor)}
                disabled={isSettingSpeed}
              >
                Set Speed
              </button>
            </div>

            <div className="nk-demo-preset-group">
              <span className="nk-demo-preset-label">Presets:</span>
              {SPEED_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  className={`nk-demo-preset-btn${status.speed === preset ? " nk-demo-preset-btn--active" : ""}`}
                  onClick={() => handleSetSpeed(preset)}
                >
                  {preset}x
                </button>
              ))}
            </div>
          </div>

          {/* Reset & Re-Seed Controls */}
          <div className="nk-demo-section" style={{ marginTop: "var(--nk-space-4)" }}>
            <label className="nk-demo-form-label" htmlFor="sim-seed-input">
              Reset & Seed Control {!isAdmin && <span className="nk-demo-tag--admin">Admin Only</span>}
            </label>
            <div className="nk-demo-reset-row">
              <input
                id="sim-seed-input"
                type="number"
                className="nk-input"
                data-testid="sim-seed-input"
                placeholder="Seed (e.g. 42)"
                value={seedInput}
                onChange={(e) => setSeedInput(e.target.value)}
                disabled={!isAdmin || isResetting}
              />
              <button
                className="nk-btn nk-btn--danger"
                data-testid="sim-btn-reset"
                onClick={handleReset}
                disabled={!isAdmin || isResetting}
                title={!isAdmin ? "Reset restricted to Admin role in hosted demo mode" : "Reset simulation state"}
              >
                {isResetting ? "Resetting…" : "Reset Simulation"}
              </button>
            </div>
            {!isAdmin && (
              <p className="nk-demo-field-hint">
                In hosted demo mode, reset and re-seeding are restricted to the <code>admin</code> role.
              </p>
            )}
          </div>
        </section>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Cluster Injection Panel                                             */}
      {/* ------------------------------------------------------------------- */}
      <section className="nk-demo-card" data-testid="cluster-injection-panel" style={{ marginTop: "var(--nk-space-6)" }}>
        <div className="nk-demo-card__header">
          <h3>Inject Synthetic Cluster</h3>
          <span className="nk-demo-subtext">
            Trigger a live mule cluster via <code>POST /sim-control/inject-cluster</code>
          </span>
        </div>

        <form onSubmit={handleInjectCluster} className="nk-demo-inject-form">
          <div className="nk-demo-form-grid">
            <div className="nk-demo-form-group">
              <label htmlFor="inject-district-input">District ID</label>
              <div className="nk-demo-combo">
                <Select
                  id="inject-district-select"
                  value={injectDistrict}
                  onValueChange={setInjectDistrict}
                  options={DISTRICT_PRESETS.map((d) => ({ value: d.id, label: d.label }))}
                />
                <input
                  id="inject-district-input"
                  className="nk-input"
                  data-testid="inject-district-input"
                  type="text"
                  placeholder="Or custom code (e.g. UP-LKO)"
                  value={injectDistrict}
                  onChange={(e) => setInjectDistrict(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="nk-demo-form-group">
              <label htmlFor="inject-size-input">Cluster Size (1–500)</label>
              <input
                id="inject-size-input"
                className="nk-input"
                data-testid="inject-size-input"
                type="number"
                min="1"
                max="500"
                value={injectSize}
                onChange={(e) => setInjectSize(Number(e.target.value))}
                required
              />
            </div>

            <div className="nk-demo-form-group">
              <label htmlFor="inject-fast-weight-input">Fast Weight (0.0 – 1.0)</label>
              <input
                id="inject-fast-weight-input"
                className="nk-input"
                data-testid="inject-fast-weight-input"
                type="number"
                min="0.0"
                max="1.0"
                step="0.05"
                value={injectFastWeight}
                onChange={(e) => setInjectFastWeight(Number(e.target.value))}
                required
              />
            </div>

            <div className="nk-demo-form-group">
              <label htmlFor="inject-locality-select">Locality Pattern</label>
              <Select
                id="inject-locality-select"
                testId="inject-locality-select"
                value={injectLocality}
                onValueChange={(v) =>
                  setInjectLocality(v as "district" | "multi_district" | "state" | "multi_state")
                }
                options={[
                  { value: "district", label: "district (single district)" },
                  { value: "multi_district", label: "multi_district (neighbouring)" },
                  { value: "state", label: "state (statewide)" },
                  { value: "multi_state", label: "multi_state (cross-border)" },
                ]}
              />
            </div>
          </div>

          <div className="nk-demo-form-actions">
            <button
              type="submit"
              className="nk-btn nk-btn--primary"
              data-testid="inject-cluster-btn"
              disabled={isInjecting}
            >
              {isInjecting ? "Injecting Cluster…" : "Inject Cluster"}
            </button>

            {injectResult && (
              <span className="nk-demo-success-msg" data-testid="inject-result-msg">
                ✓ {injectResult}
              </span>
            )}
            {injectErrorMsg && (
              <span className="nk-demo-error-msg" role="alert">
                ✗ {injectErrorMsg}
              </span>
            )}
          </div>
        </form>
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* Quick-Login Switcher Panel (Loaded from /auth/demo-users)            */}
      {/* ------------------------------------------------------------------- */}
      <section className="nk-demo-card" data-testid="demo-quick-login-panel" style={{ marginTop: "var(--nk-space-6)" }}>
        <div className="nk-demo-card__header">
          <h3>Quick-Login Role Switcher</h3>
          <span className="nk-demo-subtext">
            Loaded from <code>/auth/demo-users</code> — zero hardcoded credentials
          </span>
        </div>

        <p className="nk-demo-field-hint" style={{ marginBottom: "var(--nk-space-4)" }}>
          Switch between persona roles on stage to show scoped views across State Investigator, District Officer,
          Bank Nodal, and Demo Operator.
        </p>

        {isLoadingUsers ? (
          <p className="nk-demo-loading">Loading demo users from server…</p>
        ) : (
          <div className="nk-demo-user-grid">
            {(demoUsers ?? []).length === 0 && (
              <p className="nk-demo-loading">
                No demo users available — GET /auth/demo-users did not return any.
              </p>
            )}
            {(demoUsers ?? []).map((user) => {
              const isCurrent = principal?.role === user.role;
              return (
                <button
                  key={user.username}
                  type="button"
                  id={`quick-switch-${user.role}`}
                  className={`nk-demo-user-btn${isCurrent ? " nk-demo-user-btn--current" : ""}`}
                  data-testid={`quick-switch-${user.role}`}
                  onClick={() => handleQuickLogin(user)}
                >
                  <div className="nk-demo-user-btn__role">{user.display_name}</div>
                  <div className="nk-demo-user-btn__meta">
                    <span className="nk-demo-user-btn__user">{user.username}</span>
                    <span className="nk-demo-user-btn__badge">{user.role}</span>
                  </div>
                  {isCurrent && <span className="nk-demo-user-btn__active-pill">CURRENT ROLE</span>}
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------------- */}
      {/* Proxied Request Log (/sim-control/* audit trail)                    */}
      {/* ------------------------------------------------------------------- */}
      <section className="nk-demo-card" data-testid="sim-request-log" style={{ marginTop: "var(--nk-space-6)" }}>
        <div className="nk-demo-card__header">
          <div>
            <h3>Proxied Request Log</h3>
            <span className="nk-demo-subtext">
              Real-time audit trail confirming all actions hit <code>/sim-control/*</code>
            </span>
          </div>
          <button
            type="button"
            className="nk-btn nk-btn--ghost"
            onClick={clearRequestLog}
            disabled={requestLog.length === 0}
          >
            Clear Log
          </button>
        </div>

        {requestLog.length === 0 ? (
          <p className="nk-demo-empty-log">
            No proxied requests sent yet in this session. Control actions above will be logged here.
          </p>
        ) : (
          <div className="nk-demo-log-table-wrap">
            <table className="nk-table nk-demo-log-table">
              <thead>
                <tr>
                  <th style={{ width: "120px" }}>Time</th>
                  <th style={{ width: "70px" }}>Method</th>
                  <th style={{ width: "240px" }}>Proxied Endpoint</th>
                  <th>Payload</th>
                  <th style={{ width: "90px" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {requestLog.map((log) => (
                  <tr key={log.id} data-testid="request-log-row">
                    <td className="nk-mono nk-demo-log-time">
                      {format(new Date(log.timestamp), "HH:mm:ss")}
                    </td>
                    <td>
                      <span className={`nk-demo-method-tag nk-demo-method-tag--${log.method.toLowerCase()}`}>
                        {log.method}
                      </span>
                    </td>
                    <td className="nk-mono nk-demo-log-path">{log.path}</td>
                    <td className="nk-mono nk-demo-log-payload">
                      {log.payload ? JSON.stringify(log.payload) : "—"}
                    </td>
                    <td>
                      <span
                        className={`nk-demo-status-code ${
                          log.status >= 200 && log.status < 300
                            ? "nk-text-good"
                            : "nk-text-bad"
                        }`}
                      >
                        {log.status ? `${log.status}` : "NET_ERR"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default DemoConsole;
