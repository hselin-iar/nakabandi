/**
 * CasesPage.tsx — Bundled Cases Management and Dossier Explorer.
 * DOC 3 §S1 & DOC 4 §C6
 */

import React, { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useCases, useCase } from "./api/useCases";
import { CaseDetail } from "./CaseDetail";
import { formatInr, formatSimTime, humanizeStatus } from "../../shared/lib/format";
import { DataTable, type Column } from "../../shared/ui/DataTable";
import { Panel } from "../../shared/ui/Panel";
import { Button } from "../../shared/ui/Button";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Select } from "../../shared/ui/Select";
import type { Case, CaseFilter } from "./types";

/**
 * Case status chip. Neutral fills and weight/inversion tell states apart: a red pill here would
 * borrow the severity hue for a workflow state (Golden Color Rule).
 */
function CaseStatusChip({ status }: { status: string }) {
  const cls =
    status === "fir_recommended"
      ? "nk-badge--verdict-bad"
      : status === "under_investigation"
        ? "nk-badge--status-open"
        : status === "closed"
          ? "nk-badge--status-expired"
          : "nk-badge--status-ack";
  return <span className={`nk-badge ${cls}`}>{humanizeStatus(status)}</span>;
}

export default function CasesPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [singleOnly, setSingleOnly] = useState(false);

  // If `:id` is provided in URL, load specific case
  const {
    data: selectedCase,
    isLoading: isLoadingCase,
    isError: isCaseError,
  } = useCase(id);

  const filter: CaseFilter = {
    search: search.trim() || undefined,
    status: statusFilter === "all" ? undefined : statusFilter,
    singleComplaintOnly: singleOnly || undefined,
  };

  const {
    data: cases = [],
    isLoading: isLoadingList,
    isError: isListError,
  } = useCases(filter);

  // If looking at a single case detail view
  if (id) {
    if (isLoadingCase) {
      return (
        <div className="nk-page-loading" aria-live="polite">
          Loading case dossier…
        </div>
      );
    }

    if (isCaseError || !selectedCase) {
      return (
        <div style={{ padding: 20 }}>
          <ErrorState
            error={{
              message: `Could not retrieve case with ID "${id}".`,
              code: "CASE_NOT_FOUND",
            }}
          />
          <div style={{ marginTop: 16 }}>
            <button
              type="button"
              onClick={() => navigate("/cases")}
              className="nk-btn nk-btn--secondary"
            >
              ← Back to Case List
            </button>
          </div>
        </div>
      );
    }

    return (
      <div style={{ padding: 20 }}>
        <CaseDetail
          caseData={selectedCase}
          onBack={() => navigate("/cases")}
        />
      </div>
    );
  }

  const columns: Column<Case>[] = [
    {
      key: "id",
      header: "Case Identifier",
      sortable: true,
      cell: (c) => (
        <>
          <Link to={`/cases/${c.id}`} className="nk-link" style={{ fontWeight: "var(--nk-weight-strong)" }}>
            {c.id}
          </Link>
          {c.single_complaint && (
            <span data-testid="single-complaint-badge" className="nk-badge nk-badge--status-ack" style={{ marginLeft: 8 }}>
              Single
            </span>
          )}
        </>
      ),
    },
    {
      key: "cluster_ref",
      header: "Linked Cluster",
      sortable: true,
      cell: (c) => (
        <Link to={`/clusters/${c.cluster_ref}`} className="nk-link nk-link--muted">
          {c.cluster_ref}
        </Link>
      ),
    },
    {
      key: "complaint_count",
      header: "Complaints",
      sortable: true,
      cell: (c) => `${c.complaint_count} (${c.victim_count} victims)`,
    },
    {
      key: "total_paise",
      header: "Total Disputed",
      sortable: true,
      cell: (c) => <span className="data-digit" style={{ fontWeight: "var(--nk-weight-strong)" }}>{formatInr(c.total_paise)}</span>,
    },
    { key: "status", header: "Status", sortable: true, cell: (c) => <CaseStatusChip status={c.status} /> },
    {
      key: "first_seen",
      header: "First Incident",
      sortable: true,
      cell: (c) => <span className="data-digit" style={{ color: "var(--nk-text-secondary)" }}>{formatSimTime(c.first_seen)}</span>,
    },
    {
      key: "actions",
      header: "",
      cell: (c) => (
        <Button
          size="sm"
          variant="secondary"
          data-testid={`open-case-btn-${c.id}`}
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/cases/${c.id}`);
          }}
        >
          Open Dossier →
        </Button>
      ),
    },
  ];

  // List view
  return (
    <div className="nk-cases-page" data-testid="cases-page" style={{ padding: "20px" }}>
      {/* Page Title & Filter Bar */}
      <Panel className="nk-cases-header">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 16,
            marginBottom: 16,
          }}
        >
          <div>
            <h2 className="nk-console-title">
              Bundled Cases & Investigation Files
            </h2>
            <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "var(--nk-text-secondary)" }}>
              Complaints that share a target, cluster, or fund trail, automatically grouped into
              one case file for investigation.
            </p>
          </div>

          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <Link
              to="/clusters"
              className="nk-btn nk-btn--secondary"
              style={{ textDecoration: "none", fontSize: "13px" }}
            >
              View Cluster Topologies →
            </Link>
          </div>
        </div>

        {/* Filter Controls */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 16,
            alignItems: "center",
          }}
        >
          <div style={{ flex: "1 1 240px" }}>
            <input
              type="text"
              placeholder="Search case ID or cluster ref…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="nk-input"
              data-testid="cases-search-input"
              style={{
                width: "100%",
                background: "var(--nk-surface-elevated)",
                border: "1px solid var(--nk-border-strong)",
                color: "var(--nk-text-primary)",
                padding: "8px 12px",
                borderRadius: 4,
                fontSize: "13px",
              }}
            />
          </div>

          <div style={{ minWidth: 200 }}>
            <Select
              testId="cases-status-filter"
              value={statusFilter}
              onValueChange={setStatusFilter}
              options={[
                { value: "all", label: "All Statuses" },
                { value: "bundled", label: "Bundled" },
                { value: "under_investigation", label: "Under Investigation" },
                { value: "fir_recommended", label: "FIR Recommended" },
                { value: "closed", label: "Closed" },
              ]}
            />
          </div>

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: "13px",
              color: "var(--nk-text-secondary)",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              className="nk-checkbox"
              checked={singleOnly}
              onChange={(e) => setSingleOnly(e.target.checked)}
              data-testid="single-complaint-checkbox"
            />
            Single complaint only
          </label>
        </div>
      </Panel>

      {/* Cases List Table */}
      {isLoadingList ? (
        <div className="nk-page-loading" aria-live="polite">
          Loading case files…
        </div>
      ) : isListError ? (
        <ErrorState
          error={{
            message: "Could not load the bundled cases list.",
            code: "CASES_LIST_ERROR",
          }}
        />
      ) : cases.length === 0 ? (
        <EmptyState
          title="No Cases Found"
          message="No bundled cases match your current filter criteria."
          action={
            (search || statusFilter !== "all" || singleOnly) && (
              <button
                type="button"
                className="nk-btn nk-btn--outline nk-btn--sm"
                onClick={() => {
                  setSearch("");
                  setStatusFilter("all");
                  setSingleOnly(false);
                }}
              >
                Reset Filters
              </button>
            )
          }
        />
      ) : (
        <DataTable
          testId="cases-table"
          columns={columns}
          data={cases}
          getRowKey={(c) => c.id}
          getRowTestId={(c) => `case-row-${c.id}`}
          onRowClick={(c) => navigate(`/cases/${c.id}`)}
          caption="Bundled cases"
        />
      )}
    </div>
  );
}
