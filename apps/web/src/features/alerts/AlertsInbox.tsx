/**
 * AlertsInbox.tsx — Live Alerts Inbox & Operations Cockpit.
 * DOC 3 Web App Shell: features/alerts/AlertsInbox.tsx
 *
 * Implements DataTable, filters (status, severity, search), real-time SSE stream
 * updates without full reload, rapid triage queue, and slide-over AlertDetail.
 */

import React, { useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAlerts, type AlertFilters } from "./api/useAlerts";
import { AlertDetail } from "./AlertDetail";
import { ReviewQueue } from "./ReviewQueue";
import { DataTable, type Column } from "../../shared/ui/DataTable";
import { Select } from "../../shared/ui/Select";
import { shouldShowKindBadge } from "../../shared/lib/format";
import {
  SeverityBadge,
  StatusBadge,
  LadderBadge,
} from "../../shared/ui/Badge";
import { ConfidenceBar } from "../../shared/ui/ConfidenceBar";
import { Countdown } from "../../shared/ui/Countdown";
import { MaskedRef } from "../../shared/ui/MaskedRef";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Button } from "../../shared/ui/Button";
import type { AlertStatus, LadderLevel, Severity } from "../../shared/api/enums.ts";
import type { AlertSummary } from "../../shared/api/types.ts";

export default function AlertsInbox() {
  const { id: urlAlertId } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  // Filters state
  const [statusFilter, setStatusFilter] = useState<AlertStatus | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showReviewQueue, setShowReviewQueue] = useState(false);

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
    }),
    [statusFilter, severityFilter, searchQuery],
  );

  const { data: alerts = [], isLoading, error, refetch } = useAlerts(queryFilters);

  function handleRowClick(alert: AlertSummary) {
    setSelectedAlertId(alert.id);
    navigate(`/alerts/${alert.id}`);
  }

  function handleCloseDetail() {
    setSelectedAlertId(null);
    navigate("/alerts");
  }

  // DataTable column definitions
  const columns: Column<AlertSummary>[] = useMemo(
    () => [
      {
        key: "severity",
        header: "Severity",
        sortable: true,
        width: "9rem",
        cell: (row) => <SeverityBadge severity={row.severity as Severity} />,
      },
      {
        key: "id",
        header: "Alert / Cluster",
        sortable: true,
        width: "14rem",
        cell: (row) => (
          <div className="nk-alert-id-cell">
            <span className="font-mono font-bold">{row.id}</span>
            <span className="nk-text-xs text-muted">
              <MaskedRef value={row.cluster_ref} masked={row.masked} />
            </span>
          </div>
        ),
      },
      {
        key: "target",
        header: "Target Facility",
        sortable: true,
        cell: (row) => {
          const name = String(row.target.name ?? row.target.id ?? "");
          const kind = String(row.target.kind ?? "");
          return (
            <div className="nk-alert-target-cell">
              <span className="font-medium text-primary">{name}</span>
              {shouldShowKindBadge(name, kind) && <span className="nk-text-xs nk-tag">{kind}</span>}
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
        width: "9rem",
        cell: (row) => <LadderBadge level={row.ladder_level as LadderLevel} />,
      },
      {
        key: "expires_at",
        header: "Expires In",
        sortable: true,
        width: "9rem",
        cell: (row) => (
          <Countdown target={row.expires_at} warnThreshold={900} />
        ),
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
    [],
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
          <Button
            variant={showReviewQueue ? "primary" : "outline"}
            onClick={() => setShowReviewQueue((prev) => !prev)}
            aria-pressed={showReviewQueue}
          >
            ⚡ {showReviewQueue ? "Close Triage Queue" : "Rapid Triage Mode"}
          </Button>
        </div>
      </header>

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

      {/* Main Alerts Table */}
      <main className="nk-inbox-table-area">
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
            columns={columns}
            data={alerts}
            getRowKey={(row) => row.id}
            onRowClick={handleRowClick}
            caption="Active fraud interception alerts"
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

      {/* Slide-over Alert Detail Drawer */}
      {selectedAlertId && (
        <AlertDetail alertId={selectedAlertId} onClose={handleCloseDetail} />
      )}
    </div>
  );
}
