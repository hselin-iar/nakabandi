/**
 * AuditPage.tsx — Hash-chained audit log table + "Verify chain" button.
 * DOC 3 §M5 (access, audit) · DOC 4 Step C7
 *
 * Done-when evidence: "Verify chain" shows a clear ok/not-ok banner with
 * first_bad_seq when not ok. The tampered fixture state is exercised in
 * AuditPage.test.tsx.
 *
 * Stub until Track A Step A4 (/audit, /audit/verify) lands.
 */

import React, { useState } from "react";
import { useAuditLog, verifyChain } from "./api/useAudit";
import type { VerifyResponse } from "../../shared/api/types.ts";
import { EmptyState } from "../../shared/ui/EmptyState";
import { humanizeAction, formatSimTime } from "../../shared/lib/format";
import { roleLabel } from "../../shared/lib/roles";

// ---------------------------------------------------------------------------
// VerifyBanner
// ---------------------------------------------------------------------------

interface VerifyBannerProps {
  result: VerifyResponse;
  rowCount: number;
}

function VerifyBanner({ result, rowCount }: VerifyBannerProps) {
  if (result.ok) {
    return (
      <div
        className="nk-verify-banner nk-verify-banner--ok"
        role="status"
        aria-live="polite"
        data-testid="verify-banner"
        data-verify-ok="true"
      >
        <span className="nk-verify-banner__icon" aria-hidden="true">✓</span>
        <span>
          Chain verified — {rowCount} rows, head hash {result.head_hash?.slice(0, 12)}…
        </span>
      </div>
    );
  }

  return (
    <div
      className="nk-verify-banner nk-verify-banner--fail"
      role="alert"
      aria-live="assertive"
      data-testid="verify-banner"
      data-verify-ok="false"
    >
      <span className="nk-verify-banner__icon" aria-hidden="true">✗</span>
      <span>
        Chain integrity failure — first bad row at <strong>seq {result.first_bad_seq}</strong>.
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AuditPage
// ---------------------------------------------------------------------------

export default function AuditPage() {
  const { data: entries, isLoading, error } = useAuditLog();
  const [verifyResult, setVerifyResult] = useState<VerifyResponse | null>(null);
  const [verifying, setVerifying] = useState(false);

  async function handleVerify() {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const result = await verifyChain();
      setVerifyResult(result);
    } finally {
      setVerifying(false);
    }
  }

  if (isLoading) {
    return (
      <div className="nk-page-loading" aria-live="polite">
        Loading audit log…
      </div>
    );
  }

  if (error) {
    return (
      <div className="nk-error-state" role="alert">
        <span className="nk-error-state__icon" aria-hidden="true">⚠</span>
        <p className="nk-error-state__message">Could not load the audit log. Please retry.</p>
      </div>
    );
  }

  if (!entries?.length) {
    return (
      <EmptyState
        title="No audit entries"
        message="No audit entries have been recorded yet."
      />
    );
  }

  return (
    <main className="nk-audit-page" data-testid="audit-page">
      <header className="nk-audit-page__header">
        <div className="nk-audit-page__title-row">
          <h1 className="nk-audit-page__title">Audit Log</h1>
          <button
            id="audit-verify-btn"
            className={`nk-btn nk-btn--primary${verifying ? " nk-btn--loading" : ""}`}
            onClick={handleVerify}
            disabled={verifying}
            aria-busy={verifying}
            data-testid="verify-btn"
          >
            {verifying ? "Verifying…" : "Verify chain"}
          </button>
        </div>
        <p className="nk-audit-page__subtitle">
          Hash-chained append-only log. Each row's hash covers the previous hash
          — tamper one row and every subsequent hash breaks.
        </p>
      </header>

      {/* Verify result banner */}
      {verifyResult && <VerifyBanner result={verifyResult} rowCount={entries.length} />}

      {/* Audit table */}
      <div className="nk-table-wrapper" data-testid="audit-table">
        <table className="nk-table">
          <caption className="nk-table__caption">Audit log entries</caption>
          <thead>
            <tr>
              <th className="nk-table__th nk-table__th--right" style={{ width: "4rem" }}>Seq</th>
              <th className="nk-table__th">Event</th>
              <th className="nk-table__th">Actor</th>
              <th className="nk-table__th">Object</th>
              <th className="nk-table__th">Recorded At</th>
              <th className="nk-table__th">Row Hash</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr
                key={entry.seq}
                className="nk-table__row"
                data-testid={`audit-row-${entry.seq}`}
              >
                <td className="nk-table__td nk-table__td--right nk-text-secondary nk-size-12">
                  {entry.seq}
                </td>
                <td className="nk-table__td">
                  {humanizeAction(entry.action)}
                </td>
                <td className="nk-table__td nk-size-14">
                  {entry.actor_id}
                  <span className="nk-text-secondary nk-size-12"> · {roleLabel(entry.actor_role)}</span>
                </td>
                <td className="nk-table__td">
                  <code className="nk-mono nk-size-12">{entry.entity_type}:{entry.entity_id}</code>
                </td>
                <td className="nk-table__td nk-audit-time">
                  {formatSimTime(entry.at, { includeSeconds: true })}
                </td>
                <td className="nk-table__td">
                  <code
                    className="nk-mono nk-size-12 nk-audit-hash"
                    title={entry.hash}
                    aria-label={`Hash prefix: ${entry.hash.slice(0, 12)}…`}
                  >
                    {entry.hash.slice(0, 12)}…
                  </code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
