/**
 * AlertsInbox.tsx — Live Alerts Inbox & Operations Cockpit.
 * DOC 3 Web App Shell: features/alerts/AlertsInbox.tsx
 *
 * Implements DataTable, filters (status, severity, search), real-time SSE stream
 * updates without full reload, rapid triage queue, and slide-over AlertDetail.
 */

import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useHotkeys } from "react-hotkeys-hook";
import { useAlerts, type AlertFilters } from "./api/useAlerts";
import { AlertDetail } from "./AlertDetail";
import { ReviewQueue } from "./ReviewQueue";
import { AttentionBudgetStrip } from "./AttentionBudgetStrip";
import { DataTable, type Column, type DataTableHandle } from "../../shared/ui/DataTable";
import { CountdownRing } from "../../shared/ui/CountdownRing";
import { RollingCounter } from "../../shared/ui/RollingCounter";
import { ConsequenceTally } from "../../shared/ui/ConsequenceTally";
import { useRegisterShortcuts, type ShortcutScope } from "../../shared/ui/shortcutRegistry";
import { useMediaQuery } from "../../shared/lib/useMediaQuery";
import { selectionStore, usePendingAction } from "../../shared/state/selectionStore";
import { armAudio, playTacticalPing } from "../../shared/audio/tacticalPing";
import { setSoundEnabled, useSoundEnabled } from "../../shared/audio/soundPreference";
import { useHoldTally } from "./holdTally";
import { Select } from "../../shared/ui/Select";
import { shouldShowKindBadge } from "../../shared/lib/format";
import {
  SeverityBadge,
  StatusBadge,
  LadderBadge,
} from "../../shared/ui/Badge";
import { ConfidenceBar } from "../../shared/ui/ConfidenceBar";
import { MaskedRef } from "../../shared/ui/MaskedRef";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Button } from "../../shared/ui/Button";
import type { ActionType, AlertStatus, LadderLevel, Severity } from "../../shared/api/enums.ts";
import type { AlertSummary } from "../../shared/api/types.ts";

const EMPTY_ALERTS: AlertSummary[] = [];
const SEVERITY_RANK: Record<string, number> = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 };
const LADDER_RANK: Record<string, number> = { NONE: 0, L1: 1, L2: 2, L3: 3 };

type Density = "comfortable" | "compact";
const ROW_HEIGHT: Record<Density, number> = { comfortable: 64, compact: 48 };

function readDensity(): Density {
  try {
    return window.localStorage.getItem("nk.density") === "compact" ? "compact" : "comfortable";
  } catch {
    return "comfortable";
  }
}

/** Is an action dialog (hold / dispatch / override) currently open? Hotkeys must not steal its keys. */
function actionDialogOpen(): boolean {
  return document.querySelector(".nk-action-dialog") !== null;
}

const TRIAGE_SHORTCUTS: ShortcutScope = {
  scope: "triage-inbox",
  title: "Triage inbox",
  entries: [
    { keys: "J / K", description: "Next / previous alert" },
    { keys: "1 – 9", description: "Jump to the Nth alert" },
    { keys: "Space", description: "Peek at the selected alert" },
    { keys: "F", description: "Freeze: request a hold (hold the button to confirm)" },
    { keys: "D", description: "Dispatch a unit (hold the button to confirm)" },
    { keys: "X / Esc", description: "Close the detail panel" },
  ],
};

/**
 * Hold back alerts that arrive while the operator is scrolled down, so the list never jumps
 * under their eyes. They appear on demand (the "▲ N new" pill) or once the list is back at the top.
 */
function useHeldNewRows(alerts: AlertSummary[], scrolled: boolean, resetKey: unknown) {
  const [seen, setSeen] = useState<Set<string> | null>(null);

  useEffect(() => setSeen(null), [resetKey]);

  useEffect(() => {
    setSeen((prev) => {
      if (prev === null) return new Set(alerts.map((a) => a.id));
      if (scrolled) return prev;
      let next: Set<string> | null = null;
      for (const a of alerts) {
        if (!prev.has(a.id)) {
          next ??= new Set(prev);
          next.add(a.id);
        }
      }
      return next ?? prev;
    });
  }, [alerts, scrolled]);

  const visible = useMemo(() => (seen ? alerts.filter((a) => seen.has(a.id)) : alerts), [alerts, seen]);
  const held = useMemo(() => (seen ? alerts.filter((a) => !seen.has(a.id)) : []), [alerts, seen]);
  const release = useCallback(() => setSeen(new Set(alerts.map((a) => a.id))), [alerts]);
  return { visible, held, release };
}

export default function AlertsInbox() {
  const { id: urlAlertId } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  // Filters state
  const [statusFilter, setStatusFilter] = useState<AlertStatus | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showReviewQueue, setShowReviewQueue] = useState(false);

  // Cockpit state: keyboard-active row, density, list scroll state, requested action dialog
  const tableRef = useRef<DataTableHandle>(null);
  const [activeAlert, setActiveAlert] = useState<AlertSummary | null>(null);
  const [density, setDensity] = useState<Density>(readDensity);
  const [scrolled, setScrolled] = useState(false);
  const [requestedAction, setRequestedAction] = useState<{ type: ActionType; nonce: number } | null>(null);
  const soundOn = useSoundEnabled();
  const wide = useMediaQuery("(min-width: 1100px)");
  const tally = useHoldTally();

  useRegisterShortcuts(TRIAGE_SHORTCUTS);

  // Share the keyboard-active alert with the rest of the app (the map flies to it; the
  // command palette offers actions on it).
  useEffect(() => {
    if (activeAlert) selectionStore.set({ kind: "alert", id: activeAlert.id });
  }, [activeAlert]);

  // The command palette can ask for a hold/dispatch dialog on the selected alert.
  const pendingAction = usePendingAction();
  useEffect(() => {
    if (!pendingAction) return;
    const sel = selectionStore.get();
    if (sel?.kind !== "alert") return;
    const p = selectionStore.consumePendingAction();
    if (!p) return;
    setSelectedAlertId(sel.id);
    setRequestedAction({ type: p.type, nonce: p.nonce });
  }, [pendingAction]);

  // Selected alert ID for drawer (defaults to URL param if provided)
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(urlAlertId ?? null);

  // Synchronise state with URL param changes
  React.useEffect(() => {
    if (urlAlertId) {
      setSelectedAlertId(urlAlertId);
    }
  }, [urlAlertId]);

  const queryFilters: AlertFilters = useMemo(
    () => ({
      status: statusFilter,
      severity: severityFilter,
      search: searchQuery,
      view: "queue",
    }),
    [statusFilter, severityFilter, searchQuery],
  );

  const { data: alertsData, isLoading, error, refetch } = useAlerts(queryFilters);
  const allAlerts = alertsData ?? EMPTY_ALERTS;
  const { visible: alerts, held: heldAlerts, release: releaseHeld } = useHeldNewRows(
    allAlerts,
    scrolled,
    queryFilters,
  );

  // Attention-budget strip (§4.2/§7.6): the same filters, against the deferred backlog —
  // makes the alert-budget policy visible as a trust signal, not an invisible server split.
  const { data: backlogAlerts = [] } = useAlerts(
    useMemo(() => ({ ...queryFilters, view: "backlog" }), [queryFilters]),
  );

  function handleRowClick(alert: AlertSummary) {
    selectionStore.set({ kind: "alert", id: alert.id });
    setSelectedAlertId(alert.id);
    navigate(`/alerts/${alert.id}`);
  }

  function handleCloseDetail() {
    setSelectedAlertId(null);
    navigate("/alerts");
  }

  function showHeld() {
    releaseHeld();
    tableRef.current?.scrollToTop();
  }

  function toggleDensity() {
    const next: Density = density === "compact" ? "comfortable" : "compact";
    setDensity(next);
    try {
      window.localStorage.setItem("nk.density", next);
    } catch {
      /* preference just isn't remembered */
    }
  }

  function toggleSound() {
    const next = !soundOn;
    setSoundEnabled(next);
    if (next) {
      // Enabling is a user gesture: unlock audio and give an audible confirmation.
      armAudio();
      window.setTimeout(() => playTacticalPing("MEDIUM"), 60);
    }
  }

  // ---- Keyboard triage (react-hotkeys-hook; single-key, off while typing in a form field) ----
  const hotkeysOn = !(selectedAlertId && !wide); // the modal drawer owns the keyboard when open
  const guarded = (fn: () => void) => () => {
    if (!actionDialogOpen()) fn();
  };
  const requestAction = (type: ActionType) => {
    if (!activeAlert) return;
    setSelectedAlertId(activeAlert.id);
    navigate(`/alerts/${activeAlert.id}`);
    setRequestedAction({ type, nonce: Date.now() });
  };
  useHotkeys("j", guarded(() => tableRef.current?.step(1)), { enabled: hotkeysOn }, [hotkeysOn]);
  useHotkeys("k", guarded(() => tableRef.current?.step(-1)), { enabled: hotkeysOn }, [hotkeysOn]);
  useHotkeys(
    "1,2,3,4,5,6,7,8,9",
    (e) => {
      if (!actionDialogOpen()) tableRef.current?.activate(Number(e.key) - 1);
    },
    { enabled: hotkeysOn },
    [hotkeysOn],
  );
  useHotkeys(
    "space",
    guarded(() => {
      if (!activeAlert) return;
      setSelectedAlertId(activeAlert.id);
      navigate(`/alerts/${activeAlert.id}`);
    }),
    { enabled: hotkeysOn, preventDefault: true },
    [hotkeysOn, activeAlert],
  );
  useHotkeys("f", guarded(() => requestAction("request_hold")), { enabled: hotkeysOn }, [hotkeysOn, activeAlert]);
  useHotkeys("d", guarded(() => requestAction("dispatch")), { enabled: hotkeysOn }, [hotkeysOn, activeAlert]);
  useHotkeys(
    "x,escape",
    guarded(() => {
      if (selectedAlertId) handleCloseDetail();
    }),
    { enabled: Boolean(selectedAlertId) && wide },
    [selectedAlertId, wide],
  );

  // DataTable column definitions
  const columns: Column<AlertSummary>[] = useMemo(
    () => [
      {
        key: "severity",
        header: "Severity",
        sortable: true,
        sortValue: (row) => SEVERITY_RANK[row.severity] ?? -1,
        width: "9rem",
        cell: (row) => <SeverityBadge severity={row.severity as Severity} />,
      },
      {
        key: "id",
        header: "Cluster",
        sortable: true,
        sortValue: (row) => row.cluster_ref,
        width: "14rem",
        cell: (row) => (
          <div className="nk-alert-id-cell">
            <MaskedRef value={row.cluster_ref} masked={row.masked} className="font-bold" />
            <span className="nk-text-xs text-muted font-mono">{row.id}</span>
          </div>
        ),
      },
      {
        key: "target",
        header: "Target Facility",
        sortable: true,
        sortValue: (row) => String(row.target.name ?? row.target.id ?? ""),
        cell: (row) => {
          const name = String(row.target.name ?? row.target.id ?? "");
          const kind = String(row.target.kind ?? "");
          // Extract district code from cluster_ref (e.g. "MH-MUM" from "CLU-MH-MUM-0042")
          const districtMatch = String(row.cluster_ref ?? "").match(/([A-Z]{2}-[A-Z]{2,3})/i);
          const district = districtMatch ? districtMatch[1].toUpperCase() : null;
          return (
            <div className="nk-alert-target-cell">
              <span className="font-medium text-primary">{name}</span>
              {shouldShowKindBadge(name, kind) && <span className="nk-text-xs nk-tag">{kind}</span>}
              {district && <span className="nk-geo-badge">📍 {district}</span>}
            </div>
          );
        },
      },
      {
        key: "confidence",
        header: "Confidence",
        sortable: true,
        width: "11rem",
        cell: (row) => <ConfidenceBar value={row.confidence} />,
      },
      {
        key: "status",
        header: "Status",
        sortable: true,
        width: "8rem",
        cell: (row) => <StatusBadge status={row.status as AlertStatus} />,
      },
      {
        key: "ladder_level",
        header: "Ladder",
        sortable: true,
        sortValue: (row) => LADDER_RANK[row.ladder_level] ?? -1,
        width: "9rem",
        cell: (row) => <LadderBadge level={row.ladder_level as LadderLevel} />,
      },
      {
        key: "expires_at",
        header: "Window",
        sortable: true,
        sortValue: (row) => new Date(row.expires_at).getTime(),
        width: "5rem",
        cell: (row) => <CountdownRing expiresAt={row.expires_at} createdAt={row.created_at} />,
      },
      {
        key: "actions",
        header: "",
        width: "6rem",
        cell: (row) => (
          <Button
            size="sm"
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation();
              handleRowClick(row);
            }}
            aria-label={`Inspect alert ${row.id}`}
          >
            Inspect →
          </Button>
        ),
      },
    ],
    // handleRowClick only touches setState/navigate, which are stable
    [],
  );

  // With the detail pane open the list is narrower: drop the lowest-value columns.
  const splitOpen = wide && Boolean(selectedAlertId);
  const visibleColumns = useMemo(
    () => (splitOpen ? columns.filter((c) => c.key !== "ladder_level" && c.key !== "actions" && c.key !== "confidence") : columns),
    [columns, splitOpen],
  );

  const statusOptions: { label: string; value: AlertStatus | "all" }[] = [
    { label: "All Alerts", value: "all" },
    { label: "Open", value: "open" },
    { label: "Acknowledged", value: "acknowledged" },
    { label: "Actioned", value: "actioned" },
    { label: "Escalated", value: "escalated" },
    { label: "Expired", value: "expired" },
  ];

  const severityOptions: { label: string; value: Severity | "all" }[] = [
    { label: "All Severities", value: "all" },
    { label: "Critical", value: "CRITICAL" },
    { label: "High", value: "HIGH" },
    { label: "Medium", value: "MEDIUM" },
    { label: "Low", value: "LOW" },
  ];

  // KPI summary counts derived from loaded alerts (no extra API call)
  const kpiCounts = useMemo(() => {
    const open = alerts.filter((a) => a.status === "open").length;
    const critical = alerts.filter((a) => a.severity === "CRITICAL").length;
    const high = alerts.filter((a) => a.severity === "HIGH").length;
    const clusters = new Set(alerts.map((a) => a.cluster_ref).filter(Boolean)).size;
    return { open, critical, high, clusters };
  }, [alerts]);

  return (
    <div className="nk-inbox-page">
      {/* Top Header & Triage Mode Toggle */}
      <header className="nk-inbox-header">
        <div>
          <h1 className="nk-inbox-title">Alert Operations Inbox</h1>
          <p className="nk-inbox-subtitle">
            Live fraud trajectory alerts delivered via SSE stream. Acknowledge and dispatch before window expiry.
          </p>
        </div>

        <div className="nk-inbox-top-actions">
          <div className="nk-inbox-tools">
            <ConsequenceTally
              heldPaise={tally.heldPaise}
              actionCount={tally.actionCount}
              pendingCount={tally.pendingCount}
            />
            <Button
              size="sm"
              variant="ghost"
              onClick={toggleSound}
              aria-pressed={soundOn}
              title="Play a cue when a CRITICAL alert arrives"
            >
              {soundOn ? "🔔 Sound on" : "🔕 Sound off"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={toggleDensity}
              aria-pressed={density === "compact"}
              title="Row density"
            >
              {density === "compact" ? "Compact" : "Comfortable"}
            </Button>
          </div>
          <Button
            variant={showReviewQueue ? "primary" : "outline"}
            onClick={() => setShowReviewQueue((prev) => !prev)}
            aria-pressed={showReviewQueue}
          >
            ⚡ {showReviewQueue ? "Close Triage Queue" : "Rapid Triage Mode"}
          </Button>
        </div>
      </header>

      {/* One compact row: attention-budget note on the left, live counts as chips on the right */}
      <div className="nk-inbox-summary">
        <AttentionBudgetStrip shownCount={alerts.length} backlogCount={backlogAlerts.length} />
        <div className="nk-kpi-chips" aria-label="Alert summary statistics">
          <span className="nk-kpi-chip">
            <span className="nk-live-dot" aria-hidden="true" />
            <b className="nk-kpi-chip__n"><RollingCounter value={alerts.length} /></b> live
            <span className="nk-kpi-chip__sub">{kpiCounts.open} open</span>
          </span>
          <span className={`nk-kpi-chip${kpiCounts.critical > 0 ? " nk-kpi-chip--critical" : ""}`}>
            <b className="nk-kpi-chip__n"><RollingCounter value={kpiCounts.critical} /></b> critical
          </span>
          <span className={`nk-kpi-chip${kpiCounts.high > 0 ? " nk-kpi-chip--high" : ""}`}>
            <b className="nk-kpi-chip__n"><RollingCounter value={kpiCounts.high} /></b> high
          </span>
          <span className="nk-kpi-chip">
            <b className="nk-kpi-chip__n"><RollingCounter value={kpiCounts.clusters} /></b> clusters
          </span>
        </div>
      </div>

      {/* Review Queue Triage Drawer / Panel */}
      {showReviewQueue && (
        <div className="nk-inbox-review-container">
          <ReviewQueue
            alerts={alerts}
            onSelectAlert={(alertId) => {
              setSelectedAlertId(alertId);
              setShowReviewQueue(false);
            }}
            onClose={() => setShowReviewQueue(false)}
          />
        </div>
      )}

      {/* Filters Toolbar */}
      <div className="nk-filter-bar" role="search" aria-label="Alert filters">
        <div className="nk-status-tabs" role="tablist" aria-label="Filter by status">
          {statusOptions.map((opt) => (
            <button
              key={opt.value}
              role="tab"
              aria-selected={statusFilter === opt.value}
              className={`nk-tab-btn${statusFilter === opt.value ? " nk-tab-btn--active" : ""}`}
              onClick={() => setStatusFilter(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="nk-filter-controls">
          <Select
            size="sm"
            value={severityFilter}
            ariaLabel="Filter by severity"
            onValueChange={(v) => setSeverityFilter(v as Severity | "all")}
            options={severityOptions}
          />

          <input
            type="search"
            className="nk-input nk-input--sm nk-inbox-search"
            placeholder="Search by ID, cluster, target..."
            value={searchQuery}
            aria-label="Search alerts"
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Main Alerts Table (+ in-place detail pane on wide screens) */}
      <div className={splitOpen ? "nk-triage-split" : undefined}>
        <main className="nk-inbox-table-area">
          {heldAlerts.length > 0 && (
            <button type="button" className="nk-new-pill" onClick={showHeld}>
              ▲ {heldAlerts.length} new {heldAlerts.length === 1 ? "alert" : "alerts"}
              {heldAlerts.some((a) => a.severity === "CRITICAL")
                ? ` (${heldAlerts.filter((a) => a.severity === "CRITICAL").length} critical)`
                : ""}
            </button>
          )}
          {isLoading ? (
            <div className="nk-inbox-loading" aria-live="polite">
              Streaming live alerts…
            </div>
          ) : error ? (
            <ErrorState
              error={{ code: "error", message: error.message }}
              onRetry={() => void refetch()}
            />
          ) : (
            <DataTable
              ref={tableRef}
              columns={visibleColumns}
              data={alerts}
              getRowKey={(row) => row.id}
              onRowClick={handleRowClick}
              onActiveChange={setActiveAlert}
              onScrolledChange={setScrolled}
              virtualized
              rowHeight={ROW_HEIGHT[density]}
              height="clamp(20rem, calc(100dvh - 25rem), 60rem)"
              caption="Active fraud interception alerts"
              rowClassName={(row) => {
                const s = String(row.severity ?? "").toUpperCase();
                if (s === "CRITICAL") return "nk-table__row--critical";
                if (s === "HIGH") return "nk-table__row--high";
                if (s === "MEDIUM") return "nk-table__row--medium";
                return "nk-table__row--low";
              }}
              emptyState={
                <EmptyState
                  title="No alerts matching criteria"
                  message="No alerts found for the selected status and severity filters."
                  action={
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setStatusFilter("all");
                        setSeverityFilter("all");
                        setSearchQuery("");
                      }}
                    >
                      Reset Filters
                    </Button>
                  }
                />
              }
            />
          )}
        </main>

        {/* Alert detail: inline pane beside the queue on wide screens, slide-over drawer otherwise */}
        {selectedAlertId && (
          <AlertDetail
            alertId={selectedAlertId}
            onClose={handleCloseDetail}
            variant={wide ? "panel" : "drawer"}
            requestedAction={requestedAction}
          />
        )}
      </div>
    </div>
  );
}
