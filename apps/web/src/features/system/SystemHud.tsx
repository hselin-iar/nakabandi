/**
 * SystemHud.tsx — the "Trust HUD" overview of System Integrity.
 *
 * Every figure on it comes from something that exists:
 *   - audit hash-chain verification (GET /audit/verify): the system's headline tamper-evidence
 *   - live latency/throughput (GET /system/metrics, polled, rolling client-side buffer)
 *   - model quality (eval-results.json from scripts/evaluate.py; NaN-safe, null = insufficient sample)
 *   - exposure tiles (GET /analytics/live-metrics)
 * There is deliberately NO calibration curve or lead-time distribution: no producer writes that
 * data yet (plan §5.1). Nothing is merged into one "trust score": these are different claims.
 */

import { useEffect, useMemo, useState } from "react";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { useEvalReport } from "../evaluation/api/useEvaluation";
import { ProgressRing } from "../../shared/ui/ProgressRing";
import { RollingCounter } from "../../shared/ui/RollingCounter";
import { Sparkline } from "../../shared/ui/Sparkline";
import { formatDuration } from "../../shared/lib/format";
import {
  brierTrend,
  loadBrierHistory,
  recordRun,
  saveBrierHistory,
  useAuditVerify,
  useHudLiveMetrics,
  useMetricsBuffer,
  type BrierRun,
} from "./api/useSystemHud";

const TREND_GLYPH = { better: "▼ improving", worse: "▲ worsening", same: "■ unchanged" } as const;

export default function SystemHud() {
  const { can } = usePrincipal();
  const canMetrics = can("SIM_CONTROL");
  const canAudit = can("VIEW_AUDIT");
  const canEval = can("VIEW_EVALUATION");
  const canLive = can("VIEW_ALERTS");

  const metrics = useMetricsBuffer(canMetrics);
  const verify = useAuditVerify(canAudit);
  const live = useHudLiveMetrics(canLive);
  const { data: report } = useEvalReport();

  // Remember each run's Brier score locally so a trend arrow is possible at all
  const [history, setHistory] = useState<BrierRun[]>(loadBrierHistory);
  const brier = report?.metrics.brier_score;
  useEffect(() => {
    if (!report || brier?.value == null) return;
    setHistory((h) => {
      const next = recordRun(h, { generated_at: report.generated_at, brier: brier.value! });
      if (next.length !== h.length) saveBrierHistory(next);
      return next.length !== h.length ? next : h;
    });
  }, [report, brier?.value]);
  const trend = brierTrend(history);

  const latest = metrics.buffer.at(-1);
  const stageNames = useMemo(() => Object.keys(latest?.stageP95 ?? {}).sort(), [latest]);

  return (
    <div className="nk-hud" data-testid="system-hud">
      {/* ---- Tamper evidence ---- */}
      {canAudit && (
        <section className="nk-hud-card nk-hud-card--wide" aria-label="Audit chain integrity">
          <h2 className="nk-hud-card__title">Audit chain</h2>
          {verify.isLoading ? (
            <p className="nk-hud-card__note">Verifying the hash chain…</p>
          ) : verify.isError || !verify.data ? (
            <p className="nk-hud-card__note" role="alert">Could not verify the audit chain.</p>
          ) : (
            <div className="nk-hud-chain" data-testid="audit-chain-status" data-ok={verify.data.ok}>
              <span className={`nk-hud-chain__glyph${verify.data.ok ? "" : " nk-hud-chain__glyph--broken"}`} aria-hidden="true">
                {verify.data.ok ? "✓" : "✕"}
              </span>
              <div>
                <div className="nk-hud-chain__state">
                  {verify.data.ok ? "Chain intact" : `Chain broken at entry #${verify.data.first_bad_seq ?? "?"}`}
                </div>
                <div className="nk-hud-card__note">
                  SHA-256 hash chain, re-verified every minute
                  {verify.data.head_hash && (
                    <>
                      {" · head "}
                      <code className="data-digit" title={verify.data.head_hash}>{verify.data.head_hash.slice(0, 16)}…</code>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* ---- Model quality ---- */}
      {canEval && (
        <section className="nk-hud-card nk-hud-card--wide" aria-label="Model quality">
          <h2 className="nk-hud-card__title">Model quality</h2>
          {!report ? (
            <p className="nk-hud-card__note" data-testid="hud-eval-empty">
              No evaluation run yet. Run <code>uv run python scripts/evaluate.py</code>, then reload.
            </p>
          ) : (
            <>
              <div className="nk-hud-gauges">
                <ProgressRing label="Hit rate @1" value={report.metrics.hit_rate_at_1.value} n={report.metrics.hit_rate_at_1.n} size={80} strokeWidth={7} />
                <ProgressRing label="Hit rate @3" value={report.metrics.hit_rate_at_3.value} n={report.metrics.hit_rate_at_3.n} size={80} strokeWidth={7} />
                <ProgressRing label="Hit rate @5" value={report.metrics.hit_rate_at_5.value} n={report.metrics.hit_rate_at_5.n} size={80} strokeWidth={7} />
                <ProgressRing label="Precision @1" value={report.metrics.precision_at_1.value} n={report.metrics.precision_at_1.n} size={80} strokeWidth={7} />
                <ProgressRing label="Precision @3" value={report.metrics.precision_at_3.value} n={report.metrics.precision_at_3.n} size={80} strokeWidth={7} />
                <ProgressRing label="Precision @5" value={report.metrics.precision_at_5.value} n={report.metrics.precision_at_5.n} size={80} strokeWidth={7} />
                <div className="nk-hud-stat" data-testid="hud-brier">
                  <span className="nk-hud-stat__label">Brier score</span>
                  <span className="nk-hud-stat__value data-digit">
                    {brier?.value == null ? "n/a" : brier.value.toFixed(4)}
                  </span>
                  <span className="nk-hud-card__note">
                    {brier?.value == null ? `insufficient sample (n=${brier?.n ?? 0})` : trend ? `${TREND_GLYPH[trend]} vs previous run` : "lower is better"}
                  </span>
                </div>
              </div>
              <p className="nk-hud-card__note">
                {report.scorer} · {report.metrics.n_complaints} complaints scored · generated {new Date(report.generated_at).toLocaleString("en-IN")}
              </p>
            </>
          )}
        </section>
      )}

      {/* ---- Live latency & throughput ---- */}
      {canMetrics && (
        <section className="nk-hud-card nk-hud-card--wide" aria-label="Latency and throughput">
          <h2 className="nk-hud-card__title">Latency &amp; throughput <span className="nk-hud-card__note">(sampled every 10 s since this page opened)</span></h2>
          {metrics.isError && !latest ? (
            <p className="nk-hud-card__note" role="alert">Could not load system metrics.</p>
          ) : !latest ? (
            <p className="nk-hud-card__note">Collecting samples…</p>
          ) : (
            <>
              <div className="nk-hud-tiles">
                <div className="nk-hud-stat"><span className="nk-hud-stat__label">Uptime</span><span className="nk-hud-stat__value data-digit">{formatDuration(latest.uptimeS)}</span></div>
                <div className="nk-hud-stat"><span className="nk-hud-stat__label">Events / s</span><span className="nk-hud-stat__value"><RollingCounter value={latest.eps} format={(n) => n.toFixed(1)} /></span></div>
                <div className="nk-hud-stat"><span className="nk-hud-stat__label">HTTP p50 / p95 / max</span><span className="nk-hud-stat__value data-digit">{latest.httpP50.toFixed(0)} / {latest.httpP95.toFixed(0)} / {latest.httpMax.toFixed(0)} ms</span></div>
                <div className="nk-hud-stat"><span className="nk-hud-stat__label">Complaints / s</span><span className="nk-hud-stat__value"><RollingCounter value={latest.complaintsPerS} format={(n) => n.toFixed(2)} /></span></div>
                <div className="nk-hud-stat"><span className="nk-hud-stat__label">Live streams</span><span className="nk-hud-stat__value data-digit">{latest.streams.open} / {latest.streams.max}</span></div>
                <div className="nk-hud-stat"><span className="nk-hud-stat__label">Outbox pending</span><span className="nk-hud-stat__value"><RollingCounter value={latest.outboxPending} /></span></div>
                <div className="nk-hud-stat"><span className="nk-hud-stat__label">Delivery failures</span><span className="nk-hud-stat__value"><RollingCounter value={latest.deliveryFailures} /></span></div>
              </div>
              <div className="nk-hud-outbox" data-testid="hud-outbox">
                <span className="nk-hud-stat__label">Outbox</span>
                {Object.entries(latest.outbox).map(([state, n]) => (
                  <span key={state} className={`nk-kpi-chip${(state === "failed" || state === "dead") && n > 0 ? " nk-kpi-chip--critical" : ""}`}>
                    <b className="nk-kpi-chip__n">{n}</b> {state}
                  </span>
                ))}
              </div>
              {stageNames.length > 0 && (
                <table className="nk-table nk-hud-stage-table" data-testid="hud-stage-table">
                  <thead>
                    <tr>
                      <th className="nk-table__th">Pipeline stage</th>
                      <th className="nk-table__th nk-table__th--right">Calls</th>
                      <th className="nk-table__th nk-table__th--right">p50</th>
                      <th className="nk-table__th nk-table__th--right">p95</th>
                      <th className="nk-table__th nk-table__th--right">Max</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stageNames.map((name) => {
                      const st = latest.stages[name];
                      return (
                        <tr key={name} className="nk-table__row">
                          <td className="nk-table__td"><code className="nk-mono">{name}</code></td>
                          <td className="nk-table__td nk-table__td--right data-digit">{st?.count ?? 0}</td>
                          <td className="nk-table__td nk-table__td--right data-digit">{(st?.p50 ?? 0).toFixed(0)} ms</td>
                          <td className="nk-table__td nk-table__td--right data-digit">{(st?.p95 ?? 0).toFixed(0)} ms</td>
                          <td className="nk-table__td nk-table__td--right data-digit">{(st?.max ?? 0).toFixed(0)} ms</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
              <div className="nk-hud-spark-grid">
                <div className="nk-hud-spark">
                  <span className="nk-hud-stat__label">HTTP p95</span>
                  <Sparkline label="HTTP p95 latency" values={metrics.buffer.map((s) => s.httpP95)} />
                  <span className="data-digit nk-hud-spark__now">{latest.httpP95.toFixed(0)} ms</span>
                </div>
                {stageNames.map((name) => (
                  <div key={name} className="nk-hud-spark">
                    <span className="nk-hud-stat__label">{name} p95</span>
                    <Sparkline label={`${name} p95 latency`} values={metrics.buffer.map((s) => s.stageP95[name] ?? 0)} />
                    <span className="data-digit nk-hud-spark__now">{(latest.stageP95[name] ?? 0).toFixed(0)} ms</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {/* ---- Exposure ---- */}
      {canLive && live.data && (
        <section className="nk-hud-card" aria-label="Exposure">
          <h2 className="nk-hud-card__title">Exposure <span className="nk-hud-card__note">(last {live.data.window_hours} h)</span></h2>
          <div className="nk-hud-tiles">
            <div className="nk-hud-stat"><span className="nk-hud-stat__label">Alerts</span><span className="nk-hud-stat__value"><RollingCounter value={live.data.alert_count} /></span></div>
            <div className="nk-hud-stat"><span className="nk-hud-stat__label">Expected mass</span><span className="nk-hud-stat__value"><RollingCounter value={live.data.expected_mass} format={(n) => n.toFixed(1)} /></span></div>
            <div className="nk-hud-stat"><span className="nk-hud-stat__label">Active locations</span><span className="nk-hud-stat__value"><RollingCounter value={live.data.active_locations} /></span></div>
          </div>
        </section>
      )}

      {!canAudit && !canEval && !canMetrics && !canLive && (
        <p className="nk-hud-card__note">Nothing in this overview is available to your role.</p>
      )}
    </div>
  );
}
