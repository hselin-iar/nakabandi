/**
 * CasesPage.tsx — Bundled Cases Management and Dossier Explorer.
 * DOC 3 §S1 & DOC 4 §C6
 */

import React, { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useCases, useCase } from "./api/useCases";
import { CaseDetail } from "./CaseDetail";
import { formatInr, formatSimTime, humanizeStatus } from "../../shared/lib/format";
import { EmptyState } from "../../shared/ui/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState";
import { Select } from "../../shared/ui/Select";
import type { CaseFilter } from "./types";

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

  // List view
  return (
    <div className="nk-cases-page" data-testid="cases-page" style={{ padding: "20px" }}>
      {/* Page Title & Filter Bar */}
      <div
        className="nk-cases-header"
        style={{
          background: "#0f172a",
          border: "1px solid #1e293b",
          borderRadius: 8,
          padding: "16px 20px",
          marginBottom: 20,
        }}
      >
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
            <h2 style={{ margin: 0, fontSize: "20px", color: "#f8fafc" }}>
              Bundled Cases & Investigation Files
            </h2>
            <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "#94a3b8" }}>
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
                background: "#1e293b",
                border: "1px solid #334155",
                color: "#f8fafc",
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
      </div>

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
        <div
          style={{
            background: "#0f172a",
            border: "1px solid #1e293b",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          <table
            data-testid="cases-table"
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "13px",
              textAlign: "left",
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid #334155",
                  background: "#1e293b",
                  color: "#94a3b8",
                }}
              >
                <th style={{ padding: "12px 16px" }}>Case Identifier</th>
                <th style={{ padding: "12px 16px" }}>Linked Cluster</th>
                <th style={{ padding: "12px 16px" }}>Complaints</th>
                <th style={{ padding: "12px 16px" }}>Total Disputed</th>
                <th style={{ padding: "12px 16px" }}>Status</th>
                <th style={{ padding: "12px 16px" }}>First Incident</th>
                <th style={{ padding: "12px 16px", textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr
                  key={c.id}
                  data-testid={`case-row-${c.id}`}
                  style={{
                    borderBottom: "1px solid #1e293b",
                    color: "#f8fafc",
                    transition: "background 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "#131d31";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                  }}
                >
                  <td style={{ padding: "12px 16px", fontWeight: 600 }}>
                    <Link
                      to={`/cases/${c.id}`}
                      style={{ color: "#38bdf8", textDecoration: "none" }}
                    >
                      {c.id}
                    </Link>
                    {c.single_complaint && (
                      <span
                        data-testid="single-complaint-badge"
                        style={{
                          marginLeft: 8,
                          fontSize: "10px",
                          background: "#0369a1",
                          color: "#bae6fd",
                          padding: "2px 6px",
                          borderRadius: 3,
                          textTransform: "uppercase",
                          fontWeight: 700,
                        }}
                      >
                        Single
                      </span>
                    )}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <Link
                      to={`/clusters/${c.cluster_ref}`}
                      style={{ color: "#94a3b8", textDecoration: "none" }}
                    >
                      {c.cluster_ref}
                    </Link>
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    {c.complaint_count} ({c.victim_count} victims)
                  </td>
                  <td style={{ padding: "12px 16px", fontWeight: 700, color: "#38bdf8" }}>
                    {formatInr(c.total_paise)}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        padding: "3px 8px",
                        borderRadius: 4,
                        fontSize: "11px",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        background:
                          c.status === "fir_recommended"
                            ? "#7f1d1d"
                            : c.status === "bundled"
                              ? "#1e3a8a"
                              : "#334155",
                        color:
                          c.status === "fir_recommended"
                            ? "#fca5a5"
                            : c.status === "bundled"
                              ? "#93c5fd"
                              : "#cbd5e1",
                      }}
                    >
                      {humanizeStatus(c.status)}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", color: "#94a3b8" }}>
                    {formatSimTime(c.first_seen)}
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    <button
                      type="button"
                      onClick={() => navigate(`/cases/${c.id}`)}
                      className="nk-btn nk-btn--secondary nk-btn--sm"
                      data-testid={`open-case-btn-${c.id}`}
                    >
                      Open Dossier →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
