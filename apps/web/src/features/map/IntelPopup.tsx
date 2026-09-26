/**
 * IntelPopup.tsx — the intelligence dossier that opens when any point on the map is clicked
 * (a facility, an alert marker, or a heat cell).
 *
 * Everything shown is assembled from data the page already holds (locations, alerts, heat rows,
 * regions) plus the tracked alert's own detail (forecast timing, interception assessment); no
 * figure is invented. Styled as a terse operations-centre readout: classification banner,
 * designation, threat assessment, position, facility profile, live trajectories, and a
 * cash-out / interception brief for the most severe linked alert.
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { SeverityBadge, StatusBadge, LadderBadge } from "../../shared/ui/Badge";
import { ConfidenceBar } from "../../shared/ui/ConfidenceBar";
import { Countdown } from "../../shared/ui/Countdown";
import { formatInr, formatSimTime } from "../../shared/lib/format";
import { useAlert } from "../alerts/api/useAlerts";
import type { AlertSummary } from "../../shared/api/types.ts";
import type {
  AlertStatus,
  LadderLevel,
  Severity,
} from "../../shared/api/enums.ts";
import type { HeatCell, HotspotDetail, LocationPoint, Region } from "./types";

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};
const KIND_LABEL: Record<string, string> = {
  ATM: "ATM",
  BRANCH: "BANK BRANCH",
  AGENT: "BC AGENT",
  location: "FACILITY",
  cell: "GRID CELL",
  district: "DISTRICT",
};

export type ThreatLevel = "NEGLIGIBLE" | "ELEVATED" | "HIGH" | "SEVERE";

/** Pure: threat band from a 0..1 risk value. */
export function threatLevel(value: number): ThreatLevel {
  if (value >= 0.75) return "SEVERE";
  if (value >= 0.5) return "HIGH";
  if (value >= 0.2) return "ELEVATED";
  return "NEGLIGIBLE";
}

/** Pure: decimal degrees as degrees-minutes-seconds, e.g. 28°36′40″N. */
export function toDms(value: number, pos: string, neg: string): string {
  const hemi = value >= 0 ? pos : neg;
  const abs = Math.abs(value);
  const d = Math.floor(abs);
  const mFloat = (abs - d) * 60;
  const m = Math.floor(mFloat);
  const s = Math.round((mFloat - m) * 60);
  return `${d}°${String(m).padStart(2, "0")}′${String(s).padStart(2, "0")}″${hemi}`;
}

/** Pure: great-circle distance in km. */
export function distanceKm(
  aLat: number,
  aLon: number,
  bLat: number,
  bLon: number,
): number {
  const rad = Math.PI / 180;
  const dLat = (bLat - aLat) * rad;
  const dLon = (bLon - aLon) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(aLat * rad) * Math.cos(bLat * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

interface Props {
  hotspot: HotspotDetail;
  /** The alert whose marker was clicked, if any: the dossier opens on it. */
  focusAlertId?: string | null;
  locations: readonly LocationPoint[];
  alerts: readonly AlertSummary[];
  regions: readonly Region[];
  heatCells: readonly HeatCell[];
  simNow: string | null;
  onClose: () => void;
  onTrackAlert?: (alertId: string) => void;
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="nk-intel__row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function IntelPopup({
  hotspot,
  focusAlertId,
  locations,
  alerts,
  regions,
  heatCells,
  simNow,
  onClose,
  onTrackAlert,
}: Props) {
  const [copied, setCopied] = useState(false);

  const facility = useMemo(
    () => locations.find((l) => l.id === hotspot.id) ?? null,
    [locations, hotspot.id],
  );
  const district = facility
    ? regions.find((r) => r.id === facility.district_id)
    : undefined;
  const state = district?.parent_id
    ? regions.find((r) => r.id === district.parent_id)
    : undefined;
  const heat = heatCells.find((c) => c.id === hotspot.id);

  // Alerts aimed at this exact target (a facility), most severe then newest first
  const linked = useMemo(
    () =>
      alerts
        .filter((a) => a.target.id === hotspot.id)
        .sort(
          (a, b) =>
            (SEVERITY_ORDER[b.severity] ?? 0) -
              (SEVERITY_ORDER[a.severity] ?? 0) ||
            b.created_at.localeCompare(a.created_at),
        ),
    [alerts, hotspot.id],
  );
  const nowMs = simNow ? new Date(simNow).getTime() : Date.now();
  const live = linked.filter(
    (a) => a.status !== "expired" && new Date(a.expires_at).getTime() > nowMs,
  );

  const focus = linked.find((a) => a.id === focusAlertId) ?? linked[0] ?? null;
  const { data: detail } = useAlert(focus?.id ?? null);
  const assessment = detail?.interception.at(-1) ?? null;
  const timing = detail?.forecast?.timing ?? null;
  const expectedMedian =
    timing && timing.weights.length
      ? timing.weights.reduce(
          (s, w, i) => s + w * (timing.medians_min[i] ?? 0),
          0,
        ) / (timing.weights.reduce((s, w) => s + w, 0) || 1)
      : null;

  const value = Math.min(1, Math.max(0, heat?.value ?? hotspot.value));
  const level = threatLevel(value);

  const nearby = useMemo(() => {
    if (!facility) return null;
    const counts = { ATM: 0, BRANCH: 0, AGENT: 0 };
    let sameBank = 0;
    for (const l of locations) {
      if (l.id === facility.id) continue;
      if (distanceKm(facility.lat, facility.lon, l.lat, l.lon) <= 5) {
        counts[l.kind] += 1;
        if (l.bank_id === facility.bank_id) sameBank += 1;
      }
    }
    return { ...counts, sameBank };
  }, [facility, locations]);

  const designation = facility?.display_name || hotspot.name || hotspot.id;
  const kindKey = facility?.kind ?? hotspot.kind;
  const coords = `${hotspot.lat.toFixed(5)}, ${hotspot.lon.toFixed(5)}`;

  return (
    <aside
      className={`nk-intel nk-intel--${level.toLowerCase()}`}
      data-testid="intel-popup"
      aria-label={`Intelligence dossier: ${designation}`}
    >
      <span
        className="nk-intel__corner nk-intel__corner--tl"
        aria-hidden="true"
      />
      <span
        className="nk-intel__corner nk-intel__corner--tr"
        aria-hidden="true"
      />
      <span
        className="nk-intel__corner nk-intel__corner--bl"
        aria-hidden="true"
      />
      <span
        className="nk-intel__corner nk-intel__corner--br"
        aria-hidden="true"
      />

      <div className="nk-intel__banner">
        <span>RESTRICTED // FININT</span>
        <span>
          {simNow
            ? `DTG ${formatSimTime(simNow, { includeSeconds: true })}Z`
            : "DTG --"}
        </span>
        <button
          type="button"
          className="nk-intel__close"
          onClick={onClose}
          aria-label="Close dossier"
        >
          ✕
        </button>
      </div>

      <div className="nk-intel__scroll">
        <header className="nk-intel__head">
          <span className="nk-intel__kind">
            {KIND_LABEL[kindKey] ?? kindKey.toUpperCase()}
          </span>
          <h3 className="nk-intel__title">{designation}</h3>
          <code className="nk-intel__id">{hotspot.id}</code>
        </header>

        <section className="nk-intel__section" aria-label="Threat assessment">
          <h4>Threat assessment</h4>
          <div className="nk-intel__threat">
            <span
              className={`nk-intel__level nk-intel__level--${level.toLowerCase()}`}
            >
              {level}
            </span>
            <div
              className="nk-intel__meter"
              role="meter"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(value * 100)}
              aria-label="Risk score"
            >
              <span style={{ width: `${Math.max(3, value * 100)}%` }} />
            </div>
            <span className="nk-intel__score data-digit">
              {(value * 100).toFixed(0)}%
            </span>
          </div>
          <dl className="nk-intel__grid">
            <Row label="Alerts on target">
              <b>{hotspot.alert_count || heat?.alert_count || linked.length}</b>{" "}
              raised
              {linked.length > 0 && (
                <>
                  {" "}
                  · <b>{live.length}</b> live
                </>
              )}
            </Row>
            <Row label="Expected cash-out mass">{value.toFixed(2)}</Row>
            {detail?.forecast && (
              <Row label="Forecast confidence">
                {(detail.forecast.confidence * 100).toFixed(0)}%
              </Row>
            )}
          </dl>
        </section>

        <section className="nk-intel__section" aria-label="Position">
          <h4>Position</h4>
          <dl className="nk-intel__grid">
            <Row label="Lat / Lon">
              <span className="data-digit">{coords}</span>
            </Row>
            <Row label="DMS">
              <span className="data-digit">
                {toDms(hotspot.lat, "N", "S")} {toDms(hotspot.lon, "E", "W")}
              </span>
            </Row>
            {facility && (
              <Row label="District">
                {district?.name ?? facility.district_id}
                {state ? `, ${state.name}` : ""}
              </Row>
            )}
            {facility && (
              <Row label="Grid cell">
                <code>{facility.cell_id}</code>
              </Row>
            )}
          </dl>
        </section>

        {facility && (
          <section className="nk-intel__section" aria-label="Facility profile">
            <h4>Facility profile</h4>
            <dl className="nk-intel__grid">
              <Row label="Bank">
                <code>{facility.bank_id}</code>
              </Row>
              <Row label="Area type">
                {facility.area_type.replace(/_/g, " ")}
              </Row>
              {nearby && (
                <Row label="Within 5 km">
                  {nearby.ATM} ATM · {nearby.BRANCH} branch · {nearby.AGENT}{" "}
                  agent
                  {nearby.sameBank > 0 && <> ({nearby.sameBank} same bank)</>}
                </Row>
              )}
            </dl>
          </section>
        )}

        <section className="nk-intel__section" aria-label="Linked trajectories">
          <h4>Linked trajectories ({linked.length})</h4>
          {linked.length === 0 ? (
            <p className="nk-intel__none">
              No alerts have targeted this point in the current window.
            </p>
          ) : (
            <ul className="nk-intel__alerts">
              {linked.slice(0, 5).map((a) => {
                const expired =
                  a.status === "expired" ||
                  new Date(a.expires_at).getTime() <= nowMs;
                return (
                  <li
                    key={a.id}
                    className={a.id === focus?.id ? "is-focus" : undefined}
                  >
                    <div className="nk-intel__alert-top">
                      <SeverityBadge severity={a.severity as Severity} />
                      <StatusBadge status={a.status as AlertStatus} />
                      <LadderBadge level={a.ladder_level as LadderLevel} />
                    </div>
                    <div className="nk-intel__alert-mid">
                      <code>{a.cluster_ref}</code>
                      <ConfidenceBar value={a.confidence} />
                    </div>
                    <div className="nk-intel__alert-foot">
                      <span>
                        {expired ? (
                          "WINDOW CLOSED"
                        ) : (
                          <>
                            CLOSES IN{" "}
                            <Countdown
                              target={a.expires_at}
                              warnThreshold={900}
                            />
                          </>
                        )}
                      </span>
                      <span className="nk-intel__alert-actions">
                        {onTrackAlert && (
                          <button
                            type="button"
                            onClick={() => onTrackAlert(a.id)}
                          >
                            ◎ Track
                          </button>
                        )}
                        <Link to={`/alerts/${a.id}`}>Open →</Link>
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {focus && (
          <section
            className="nk-intel__section"
            aria-label="Cash-out and interception brief"
          >
            <h4>Cash-out &amp; interception brief</h4>
            {!detail ? (
              <p className="nk-intel__none">Retrieving brief…</p>
            ) : (
              <dl className="nk-intel__grid">
                {expectedMedian != null && timing && (
                  <Row label="Expected cash-out">
                    ~{Math.round(expectedMedian)} min after credit ·{" "}
                    {(timing.residual_mass * 100).toFixed(0)}% of mass still
                    open
                  </Row>
                )}
                {timing && (
                  <Row label="Elapsed">
                    {Math.round(timing.elapsed_min)} min
                  </Row>
                )}
                {assessment && (
                  <>
                    <Row label="Verdict">
                      <b
                        className={`nk-intel__verdict nk-intel__verdict--${assessment.verdict.toLowerCase()}`}
                      >
                        {assessment.verdict.replace(/_/g, " ")}
                      </b>{" "}
                      · P(intercept){" "}
                      {(assessment.interception_probability * 100).toFixed(0)}%
                    </Row>
                    <Row label="Window">
                      {assessment.window_min.toFixed(0)} min
                    </Row>
                    {assessment.best_unit && (
                      <Row label="Nearest unit">
                        {assessment.best_unit.unit_kind}{" "}
                        <code>{assessment.best_unit.unit_id}</code> · ETA{" "}
                        {assessment.best_unit.eta_min.toFixed(1)} min
                      </Row>
                    )}
                    {assessment.proportionality && (
                      <Row label="Proposed lien">
                        {formatInr(assessment.proportionality.proposed_paise, {
                          compact: true,
                        })}
                      </Row>
                    )}
                  </>
                )}
                <Row label="Notifications">
                  {detail.deliveries.length === 0
                    ? "none sent"
                    : `${detail.deliveries.filter((d) => d.status === "sent").length}/${detail.deliveries.length} delivered`}
                </Row>
              </dl>
            )}
          </section>
        )}
      </div>

      <footer className="nk-intel__foot">
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard?.writeText(coords).then(() => {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1500);
            });
          }}
        >
          {copied ? "✓ Copied" : "⧉ Copy coordinates"}
        </button>
        {focus && (
          <Link to={`/alerts/${focus.id}`} className="nk-intel__primary">
            Open alert file →
          </Link>
        )}
      </footer>
    </aside>
  );
}
