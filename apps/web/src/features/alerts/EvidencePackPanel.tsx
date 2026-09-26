/**
 * EvidencePackPanel.tsx — one-click evidence pack generation, wired directly into the alert
 * focus panel. Frontend Strategy §4.2: "Show the SHA-256 and the audit-head-hash it's anchored
 * to, not just a download link — that hash is the actual point (tamper evidence)."
 *
 * Wires three previously-unused endpoints: POST /alerts/{id}/evidence-pack,
 * GET /evidence-packs/{id}, GET /evidence-packs/{id}/download.
 */

import React from "react";
import { toast } from "sonner";
import { Button } from "../../shared/ui/Button";
import { formatSimTime } from "../../shared/lib/format";
import { useBuildEvidencePack } from "./api/useAlerts";

interface EvidencePackPanelProps {
  alertId: string;
}

export function EvidencePackPanel({ alertId }: EvidencePackPanelProps) {
  const buildPack = useBuildEvidencePack();

  return (
    <div className="nk-evidence-pack-panel" aria-label="Evidence pack">
      <div className="nk-evidence-pack-panel__header">
        <span className="nk-text-xs text-muted">
          A court-ready evidence pack (PDF, SHA-256, s.63 draft certificate) anchored to this
          alert's position in the audit hash chain.
        </span>
        <Button
          size="sm"
          variant="outline"
          loading={buildPack.isPending}
          onClick={() =>
            // Not undoable (a sealed, hash-anchored artifact), so a plain outcome toast: no undo window.
            toast.promise(buildPack.mutateAsync({ alertId }), {
              loading: "Building evidence pack…",
              success: (pack) => `Evidence pack v${pack.version} built`,
              error: (err: unknown) => (err instanceof Error ? err.message : "Could not build the evidence pack"),
            })
          }
        >
          📄 Generate Evidence Pack
        </Button>
      </div>

      {buildPack.isError && (
        <p className="nk-text-xs" style={{ color: "var(--nk-verdict-bad)" }}>
          Could not build the evidence pack: {buildPack.error.message}
        </p>
      )}

      {buildPack.data && (
        <div className="nk-evidence-pack-panel__result">
          <dl className="nk-evidence-pack-panel__hashes">
            <div>
              <dt className="nk-text-xs text-muted">SHA-256 (this pack)</dt>
              <dd className="font-mono nk-text-xs" style={{ wordBreak: "break-all" }}>
                {buildPack.data.sha256}
              </dd>
            </div>
            <div>
              <dt className="nk-text-xs text-muted">Audit Head Hash (anchor)</dt>
              <dd className="font-mono nk-text-xs" style={{ wordBreak: "break-all" }}>
                {buildPack.data.audit_head_hash}
              </dd>
            </div>
          </dl>
          <div className="nk-evidence-pack-panel__meta">
            <span className="nk-text-xs text-muted">
              Version {buildPack.data.version} · built {formatSimTime(buildPack.data.created_at)} ·{" "}
              {(buildPack.data.size_bytes / 1024).toFixed(1)} KB
            </span>
            <a
              className="nk-btn nk-btn--primary nk-btn--sm"
              href={buildPack.data.download_url}
              target="_blank"
              rel="noreferrer"
            >
              ⬇ Download PDF
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
