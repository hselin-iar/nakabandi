/**
 * SystemIntegrityPage.tsx — "can I trust this system?" from three angles that share an
 * audience but not a workflow with Triage/Deployment: statistical trust (Evaluation),
 * operational health (Ops), tamper-evidence (Audit). Frontend Strategy §4.5: tabs under
 * one destination, not three peers of Alerts in the primary nav — and never merged into
 * a single "trust score," since a Brier score, a p95 latency and a hash-chain status are
 * different enough claims that forcing them into one meter would be a dishonest compression.
 */

import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import EvaluationPage from "../evaluation/EvaluationPage";
import OpsPage from "../ops/OpsPage";
import AuditPage from "../audit/AuditPage";
import SystemHud from "./SystemHud";
import { usePrincipal } from "../../app/auth/usePrincipal";
import type { Permission } from "../../shared/api/enums.ts";

type Tab = "overview" | "evaluation" | "ops" | "audit";

// The overview shows only the sections a role may see, so it needs at least one of these.
const OVERVIEW_PERMISSIONS: Permission[] = ["VIEW_AUDIT", "VIEW_EVALUATION", "SIM_CONTROL", "VIEW_ALERTS"];

const TABS: { id: Tab; label: string; require: Permission | Permission[] }[] = [
  { id: "overview", label: "Overview", require: OVERVIEW_PERMISSIONS },
  { id: "evaluation", label: "Evaluation", require: "VIEW_EVALUATION" },
  { id: "ops", label: "Ops", require: "SIM_CONTROL" },
  { id: "audit", label: "Audit", require: "VIEW_AUDIT" },
];

export default function SystemIntegrityPage() {
  const { can } = usePrincipal();
  const [searchParams] = useSearchParams();
  const availableTabs = TABS.filter((t) => (Array.isArray(t.require) ? t.require.some(can) : can(t.require)));
  const requestedTab = searchParams.get("tab") as Tab | null;
  const [tab, setTab] = useState<Tab | null>(requestedTab ?? availableTabs[0]?.id ?? null);
  const activeTab = tab && availableTabs.some((t) => t.id === tab) ? tab : availableTabs[0]?.id;

  return (
    <div className="nk-system-integrity-page">
      <header className="nk-system-integrity-header">
        <h1 className="nk-system-integrity-title">System Integrity</h1>
        <p className="nk-system-integrity-subtitle">
          Can this system be trusted — statistically, operationally, and tamper-evidently.
        </p>
      </header>

      {availableTabs.length === 0 ? (
        <p className="nk-text-sm text-muted">
          You do not have permission to view any System Integrity report.
        </p>
      ) : (
        <>
          <div className="nk-system-integrity-tabs" role="tablist" aria-label="System integrity reports">
            {availableTabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={activeTab === t.id}
                className={`nk-tab-btn${activeTab === t.id ? " nk-tab-btn--active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="nk-system-integrity-body">
            {activeTab === "overview" && <SystemHud />}
            {activeTab === "evaluation" && <EvaluationPage />}
            {activeTab === "ops" && <OpsPage />}
            {activeTab === "audit" && <AuditPage />}
          </div>
        </>
      )}
    </div>
  );
}
