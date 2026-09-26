/**
 * CaseDetail.tsx — Comprehensive Case Brief and Evidence Pack View.
 * DOC 3 §S1 & DOC 4 §C6
 *
 * Invariants:
 * - Brief states facts and ends with: "Whether to register an FIR is the investigating officer's decision."
 * - No unmasked account references displayed for non-LEA fixture principals.
 * - Cytoscape ClusterGraph is imported from ../clusters/ClusterGraph (never duplicated).
 */

import React from "react";
import { Link } from "react-router-dom";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { isLeaRole, ClusterGraph } from "../clusters/ClusterGraph";
import { useCluster } from "../clusters/api/useClusters";
import { formatInr, formatSimTime, humanizeStatus } from "../../shared/lib/format";
import { Timeline } from "../../shared/ui/Timeline";
import { MaskedRef } from "../../shared/ui/MaskedRef";
import { REQUIRED_FIR_DISCLAIMER } from "./api/useCases";
import type { Case } from "./types";

interface CaseDetailProps {
  caseData: Case;
  onBack?: () => void;
}

/**
 * Safe markdown renderer: converts headings, bullets, paragraphs,
 * and ensures the FIR statutory disclaimer is rendered securely without XSS.
 */
function SafeBriefRenderer({ markdown }: { markdown: string }) {
  // Normalize lines
  const lines = markdown.split("\n");
  const elements: React.ReactNode[] = [];
  let currentList: string[] = [];

  const flushList = (key: number) => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`ul-${key}`} style={{ paddingLeft: 20, margin: "8px 0" }}>
          {currentList.map((item, idx) => (
            <li key={`li-${idx}`} style={{ marginBottom: 4, color: "#cbd5e1" }}>
              {item}
            </li>
          ))}
        </ul>,
      );
      currentList = [];
    }
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    if (trimmed.startsWith("- ")) {
      currentList.push(trimmed.slice(2));
      return;
    }

    flushList(idx);

    if (trimmed.startsWith("### ")) {
      elements.push(
        <h3 key={idx} style={{ color: "#f8fafc", fontSize: "16px", marginTop: 16, marginBottom: 8 }}>
          {trimmed.slice(4)}
        </h3>,
      );
    } else if (trimmed.startsWith("#### ")) {
      elements.push(
        <h4 key={idx} style={{ color: "#38bdf8", fontSize: "14px", marginTop: 12, marginBottom: 6 }}>
          {trimmed.slice(5)}
        </h4>,
      );
    } else if (trimmed.length > 0) {
      elements.push(
        <p key={idx} style={{ color: "#cbd5e1", lineHeight: 1.6, margin: "6px 0" }}>
          {trimmed}
        </p>,
      );
    }
  });

  flushList(lines.length);

  return <div className="nk-case-brief__content">{elements}</div>;
}

export function CaseDetail({ caseData, onBack }: CaseDetailProps) {
  const { principal } = usePrincipal();
  const isLea = isLeaRole(principal?.role);
  // The cluster topology lives behind its own endpoint (DOC 3 S1); compose it in here rather
  // than embedding it in the Case response.
  const { data: cluster } = useCluster(caseData.cluster_ref);
  const graphData = caseData.graph_data ?? (cluster ? { nodes: cluster.nodes, edges: cluster.edges } : undefined);

  // Guarantee that the disclaimer is always present at the end
  const briefText = caseData.brief_md.includes(REQUIRED_FIR_DISCLAIMER)
    ? caseData.brief_md
    : `${caseData.brief_md}\n\n${REQUIRED_FIR_DISCLAIMER}`;

  return (
    <div className="nk-case-detail" data-testid="case-detail" style={{ padding: "4px" }}>
      {/* Back button & Action Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="nk-btn nk-btn--secondary nk-btn--sm"
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              ← Back to Cases
            </button>
          )}
          <h2 style={{ margin: 0, fontSize: "20px", color: "#f8fafc" }}>
            Case Dossier: {caseData.cluster_ref}
          </h2>
          <span
            className={`nk-badge ${
              caseData.status === "fir_recommended"
                ? "nk-badge--danger"
                : caseData.status === "bundled"
                  ? "nk-badge--info"
                  : "nk-badge--neutral"
            }`}
            style={{
              textTransform: "uppercase",
              fontSize: "11px",
              fontWeight: 700,
              padding: "4px 8px",
              borderRadius: 4,
            }}
          >
            {humanizeStatus(caseData.status)}
          </span>
          {caseData.single_complaint && (
            <span
              className="nk-badge"
              style={{
                fontSize: "11px",
                fontWeight: 600,
                padding: "4px 8px",
                borderRadius: 4,
                background: "#0369a1",
                color: "#bae6fd",
              }}
            >
              Single complaint
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <Link
            to={`/clusters/${caseData.cluster_ref}`}
            className="nk-btn nk-btn--secondary nk-btn--sm"
            style={{ textDecoration: "none" }}
          >
            Explore Cluster ({caseData.cluster_ref}) →
          </Link>
        </div>
      </div>

      {/* Summary KPI Grid */}
      <div
        className="nk-kpi-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 16,
          marginBottom: 20,
        }}
      >
        <div
          style={{
            background: "#0f172a",
            border: "1px solid #1e293b",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8" }}>Total Disputed Amount</div>
          <div style={{ fontSize: "20px", fontWeight: 700, color: "#38bdf8", marginTop: 4 }}>
            {formatInr(caseData.total_paise)}
          </div>
        </div>

        <div
          style={{
            background: "#0f172a",
            border: "1px solid #1e293b",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8" }}>Complaints / Victims</div>
          <div style={{ fontSize: "20px", fontWeight: 700, color: "#f8fafc", marginTop: 4 }}>
            {caseData.complaint_count} Complaints ({caseData.victim_count} Victims)
          </div>
        </div>

        <div
          style={{
            background: "#0f172a",
            border: "1px solid #1e293b",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8" }}>First Incident</div>
          <div style={{ fontSize: "14px", fontWeight: 600, color: "#e2e8f0", marginTop: 8 }}>
            {formatSimTime(caseData.first_seen)}
          </div>
        </div>

        <div
          style={{
            background: "#0f172a",
            border: "1px solid #1e293b",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div style={{ fontSize: "11px", color: "#94a3b8" }}>Latest Activity</div>
          <div style={{ fontSize: "14px", fontWeight: 600, color: "#e2e8f0", marginTop: 8 }}>
            {formatSimTime(caseData.last_seen)}
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 20,
        }}
      >
        {/* Left Column: Consolidated Case Brief & Accounts */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Executive Brief Box */}
          <div
            className="nk-panel"
            style={{
              background: "#0f172a",
              border: "1px solid #1e293b",
              borderRadius: 8,
              padding: 20,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderBottom: "1px solid #1e293b",
                paddingBottom: 10,
                marginBottom: 12,
              }}
            >
              <h3 style={{ margin: 0, fontSize: "16px", color: "#f8fafc" }}>
                Consolidated Case Brief
              </h3>
              <span style={{ fontSize: "11px", color: "#64748b" }}>
                Factual Synthesis
              </span>
            </div>

            <SafeBriefRenderer markdown={briefText} />

            {/* Statutory Disclaimer Invariant */}
            <div
              className="nk-case-brief__disclaimer"
              data-testid="fir-disclaimer"
              role="note"
              style={{
                marginTop: 16,
                padding: "12px 16px",
                background: "rgba(2, 132, 199, 0.1)",
                border: "1px solid #0284c7",
                borderRadius: 6,
                color: "#e0f2fe",
                fontSize: "13px",
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span aria-hidden="true" style={{ fontSize: "16px" }}>⚖️</span>
              <span>{REQUIRED_FIR_DISCLAIMER}</span>
            </div>
          </div>

          {/* Accounts Table with Role-Gated Masking */}
          <div
            className="nk-panel"
            style={{
              background: "#0f172a",
              border: "1px solid #1e293b",
              borderRadius: 8,
              padding: 20,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <h3 style={{ margin: 0, fontSize: "16px", color: "#f8fafc" }}>
                Identified Accounts ({caseData.accounts.length})
              </h3>
              {!isLea && (
                <span
                  style={{
                    fontSize: "11px",
                    color: "#f59e0b",
                    background: "rgba(245, 158, 11, 0.1)",
                    padding: "2px 8px",
                    borderRadius: 4,
                  }}
                  data-testid="masking-indicator"
                >
                  Masked (Non-LEA Session)
                </span>
              )}
            </div>

            <table
              data-testid="accounts-table"
              style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}
            >
              <thead>
                <tr style={{ borderBottom: "1px solid #334155", color: "#94a3b8", textAlign: "left" }}>
                  <th style={{ padding: "8px 6px" }}>Account Identifier</th>
                  <th style={{ padding: "8px 6px" }}>Bank</th>
                  <th style={{ padding: "8px 6px" }}>Role</th>
                  <th style={{ padding: "8px 6px" }}>Linked Complaints</th>
                  <th style={{ padding: "8px 6px", textAlign: "right" }}>Volume</th>
                </tr>
              </thead>
              <tbody>
                {caseData.accounts.map((acc, idx) => (
                  <tr
                    key={idx}
                    data-testid={`account-row-${idx}`}
                    style={{ borderBottom: "1px solid #1e293b", color: "#e2e8f0" }}
                  >
                    <td style={{ padding: "8px 6px" }}>
                      {isLea ? (
                        <span data-testid="unmasked-account-ref">
                          <code>{acc.account_ref}</code>
                        </span>
                      ) : (
                        <MaskedRef value={acc.masked_ref} masked={true} />
                      )}
                    </td>
                    <td style={{ padding: "8px 6px" }}>{acc.bank}</td>
                    <td style={{ padding: "8px 6px", textTransform: "capitalize" }}>
                      <span
                        style={{
                          padding: "2px 6px",
                          borderRadius: 3,
                          background:
                            acc.role === "aggregator"
                              ? "#7f1d1d"
                              : acc.role === "mule"
                                ? "#78350f"
                                : "#0c4a6e",
                          color: "#f8fafc",
                          fontSize: "10px",
                          fontWeight: 600,
                        }}
                      >
                        {acc.role || "Node"}
                      </span>
                    </td>
                    <td style={{ padding: "8px 6px" }}>{acc.complaint_count}</td>
                    <td style={{ padding: "8px 6px", textAlign: "right" }}>
                      {acc.volume_paise ? formatInr(acc.volume_paise) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Cluster Graph, Locations & Timeline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Embedded Cytoscape Cluster Graph (Shared Component) */}
          {graphData && (
            <div
              className="nk-panel"
              style={{
                background: "#0f172a",
                border: "1px solid #1e293b",
                borderRadius: 8,
                padding: 16,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 10,
                }}
              >
                <h3 style={{ margin: 0, fontSize: "15px", color: "#f8fafc" }}>
                  Syndicate Graph Topology
                </h3>
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                  {graphData.nodes.length} nodes
                </span>
              </div>
              <div
                style={{
                  border: "1px solid #334155",
                  borderRadius: 6,
                  overflow: "hidden",
                }}
              >
                <ClusterGraph data={graphData} height={360} />
              </div>
            </div>
          )}

          {/* Top Disbursal / Activity Locations */}
          {caseData.top_locations.length > 0 && (
            <div
              className="nk-panel"
              style={{
                background: "#0f172a",
                border: "1px solid #1e293b",
                borderRadius: 8,
                padding: 16,
              }}
            >
              <h3 style={{ margin: "0 0 12px 0", fontSize: "15px", color: "#f8fafc" }}>
                Top Disbursal Locations
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {caseData.top_locations.map((loc) => (
                  <div
                    key={loc.id}
                    style={{
                      background: "#1e293b",
                      padding: "8px 12px",
                      borderRadius: 6,
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: "12px",
                    }}
                  >
                    <div>
                      <strong style={{ color: "#f8fafc" }}>{loc.name}</strong>
                      <div style={{ color: "#94a3b8", fontSize: "11px" }}>
                        Last incident: {formatSimTime(loc.last_at)}
                      </div>
                    </div>
                    <span
                      style={{
                        background: "#334155",
                        color: "#38bdf8",
                        fontWeight: 700,
                        padding: "2px 8px",
                        borderRadius: 4,
                      }}
                    >
                      {loc.count} hits
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence Timeline */}
          <div
            className="nk-panel"
            style={{
              background: "#0f172a",
              border: "1px solid #1e293b",
              borderRadius: 8,
              padding: 16,
            }}
          >
            <h3 style={{ margin: "0 0 12px 0", fontSize: "15px", color: "#f8fafc" }}>
              Case Telemetry Timeline
            </h3>
            <Timeline entries={caseData.timeline} />
          </div>
        </div>
      </div>
    </div>
  );
}
