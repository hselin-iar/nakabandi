/**
 * CaseDetail.tsx — Comprehensive Case Brief and Evidence Pack View.
 * DOC 3 §S1 & DOC 4 §C6
 *
 * Invariants:
 * - Brief states facts and ends with: "Whether to register an FIR is the investigating officer's decision."
 * - No unmasked account references displayed for non-LEA fixture principals.
 * - Cytoscape ClusterGraph is imported from ../clusters/ClusterGraph (never duplicated).
 */

import React, { useState } from "react";
import { Link } from "react-router-dom";
import { usePrincipal } from "../../app/auth/usePrincipal";
import { isLeaRole, ClusterGraph } from "../clusters/ClusterGraph";
import { useCluster } from "../clusters/api/useClusters";
import { formatInr, formatSimTime, humanizeStatus } from "../../shared/lib/format";
import { Timeline } from "../../shared/ui/Timeline";
import { MaskedRef } from "../../shared/ui/MaskedRef";
import { CaseFundFlowSankey } from "./CaseFundFlowSankey";
import { CaseTimelineScrubber } from "./CaseTimelineScrubber";
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
            <li key={`li-${idx}`} style={{ marginBottom: 4, color: "var(--nk-text-primary)" }}>
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
        <h3 key={idx} style={{ color: "var(--nk-text-primary)", fontSize: "16px", marginTop: 16, marginBottom: 8 }}>
          {trimmed.slice(4)}
        </h3>,
      );
    } else if (trimmed.startsWith("#### ")) {
      elements.push(
        <h4 key={idx} style={{ color: "var(--nk-accent)", fontSize: "14px", marginTop: 12, marginBottom: 6 }}>
          {trimmed.slice(5)}
        </h4>,
      );
    } else if (trimmed.length > 0) {
      elements.push(
        <p key={idx} style={{ color: "var(--nk-text-primary)", lineHeight: 1.6, margin: "6px 0" }}>
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
  const [graphTab, setGraphTab] = useState<"network" | "flow">("network");
  const [playbackMs, setPlaybackMs] = useState<number | null>(null);
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
          <h2 style={{ margin: 0, fontSize: "20px", color: "var(--nk-text-primary)" }}>
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
                background: "rgba(255,255,255,0.08)",
                color: "var(--nk-text-primary)",
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
            background: "var(--nk-surface-raised)",
            border: "1px solid var(--nk-border-subtle)",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div style={{ fontSize: "11px", color: "var(--nk-text-secondary)" }}>Total Disputed Amount</div>
          <div style={{ fontSize: "20px", fontWeight: 700, color: "var(--nk-accent)", marginTop: 4 }}>
            {formatInr(caseData.total_paise)}
          </div>
        </div>

        <div
          style={{
            background: "var(--nk-surface-raised)",
            border: "1px solid var(--nk-border-subtle)",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div style={{ fontSize: "11px", color: "var(--nk-text-secondary)" }}>Complaints / Victims</div>
          <div style={{ fontSize: "20px", fontWeight: 700, color: "var(--nk-text-primary)", marginTop: 4 }}>
            {caseData.complaint_count} Complaints ({caseData.victim_count} Victims)
          </div>
        </div>

        <div
          style={{
            background: "var(--nk-surface-raised)",
            border: "1px solid var(--nk-border-subtle)",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div style={{ fontSize: "11px", color: "var(--nk-text-secondary)" }}>First Incident</div>
          <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--nk-text-primary)", marginTop: 8 }}>
            {formatSimTime(caseData.first_seen)}
          </div>
        </div>

        <div
          style={{
            background: "var(--nk-surface-raised)",
            border: "1px solid var(--nk-border-subtle)",
            borderRadius: 8,
            padding: "12px 16px",
          }}
        >
          <div style={{ fontSize: "11px", color: "var(--nk-text-secondary)" }}>Latest Activity</div>
          <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--nk-text-primary)", marginTop: 8 }}>
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
              background: "var(--nk-surface-raised)",
              border: "1px solid var(--nk-border-subtle)",
              borderRadius: 8,
              padding: 20,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderBottom: "1px solid var(--nk-border-subtle)",
                paddingBottom: 10,
                marginBottom: 12,
              }}
            >
              <h3 style={{ margin: 0, fontSize: "16px", color: "var(--nk-text-primary)" }}>
                Consolidated Case Brief
              </h3>
              <span style={{ fontSize: "11px", color: "var(--nk-text-tertiary)" }}>
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
                background: "rgba(255,255,255,0.04)",
                border: "1px solid var(--nk-border-strong)",
                borderRadius: 6,
                color: "var(--nk-text-primary)",
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
              background: "var(--nk-surface-raised)",
              border: "1px solid var(--nk-border-subtle)",
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
              <h3 style={{ margin: 0, fontSize: "16px", color: "var(--nk-text-primary)" }}>
                Identified Accounts ({caseData.accounts.length})
              </h3>
              {!isLea && (
                <span
                  style={{
                    fontSize: "11px",
                    color: "var(--nk-text-secondary)",
                    background: "rgba(255,255,255,0.06)",
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
                <tr style={{ borderBottom: "1px solid var(--nk-border-strong)", color: "var(--nk-text-secondary)", textAlign: "left" }}>
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
                    style={{ borderBottom: "1px solid var(--nk-border-subtle)", color: "var(--nk-text-primary)" }}
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
                          background: "rgba(255,255,255,0.08)",
                          color: "var(--nk-text-primary)",
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
                background: "var(--nk-surface-raised)",
                border: "1px solid var(--nk-border-subtle)",
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
                <h3 style={{ margin: 0, fontSize: "15px", color: "var(--nk-text-primary)" }}>
                  Syndicate Graph Topology
                </h3>
                <span style={{ fontSize: "11px", color: "var(--nk-text-secondary)" }}>
                  {graphData.nodes.length} nodes
                </span>
              </div>
              <div role="tablist" aria-label="Graph view" style={{ display: "flex", gap: 6, marginBottom: 10 }}>
                <button
                  type="button"
                  role="tab"
                  aria-selected={graphTab === "network"}
                  className={`nk-tab-btn${graphTab === "network" ? " nk-tab-btn--active" : ""}`}
                  onClick={() => setGraphTab("network")}
                >
                  Network
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={graphTab === "flow"}
                  className={`nk-tab-btn${graphTab === "flow" ? " nk-tab-btn--active" : ""}`}
                  onClick={() => setGraphTab("flow")}
                >
                  Fund flow
                </button>
              </div>
              {graphTab === "network" && (
                <CaseTimelineScrubber edges={graphData.edges} value={playbackMs} onChange={setPlaybackMs} />
              )}
              <div
                style={{
                  border: "1px solid var(--nk-border-strong)",
                  borderRadius: 6,
                  overflow: "hidden",
                }}
              >
                {graphTab === "network" ? (
                  <ClusterGraph
                    data={graphData}
                    height={480}
                    clusterRef={caseData.cluster_ref}
                    playbackUntilMs={playbackMs}
                  />
                ) : (
                  <CaseFundFlowSankey data={graphData} height={480} />
                )}
              </div>
            </div>
          )}

          {/* Top Disbursal / Activity Locations */}
          {caseData.top_locations.length > 0 && (
            <div
              className="nk-panel"
              style={{
                background: "var(--nk-surface-raised)",
                border: "1px solid var(--nk-border-subtle)",
                borderRadius: 8,
                padding: 16,
              }}
            >
              <h3 style={{ margin: "0 0 12px 0", fontSize: "15px", color: "var(--nk-text-primary)" }}>
                Top Disbursal Locations
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {caseData.top_locations.map((loc) => (
                  <div
                    key={loc.id}
                    style={{
                      background: "var(--nk-surface-elevated)",
                      padding: "8px 12px",
                      borderRadius: 6,
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: "12px",
                    }}
                  >
                    <div>
                      <strong style={{ color: "var(--nk-text-primary)" }}>{loc.name}</strong>
                      <div style={{ color: "var(--nk-text-secondary)", fontSize: "11px" }}>
                        Last incident: {formatSimTime(loc.last_at)}
                      </div>
                    </div>
                    <span
                      style={{
                        background: "var(--nk-border-strong)",
                        color: "var(--nk-accent)",
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
              background: "var(--nk-surface-raised)",
              border: "1px solid var(--nk-border-subtle)",
              borderRadius: 8,
              padding: 16,
            }}
          >
            <h3 style={{ margin: "0 0 12px 0", fontSize: "15px", color: "var(--nk-text-primary)" }}>
              Case Telemetry Timeline
            </h3>
            <Timeline entries={caseData.timeline} />
          </div>
        </div>
      </div>
    </div>
  );
}
