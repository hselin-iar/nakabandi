/**
 * EntityInspector.tsx — details for the selected account (or transaction flow) in the graph.
 *
 * Everything shown is derived from the edges already loaded: degrees, totals moved in and out,
 * first/last activity, the hop chain from an origin. It deliberately shows NO risk score: no
 * per-account score exists in the data, and inventing one in a forensic view would overclaim.
 */

import { formatInr, formatSimTime } from "../../shared/lib/format";
import { ROLE_LABEL, type NodeRole, type NodeStats } from "./graphModel";
import type { ClusterEdge, ClusterNode } from "./types";

interface NodeInspectorProps {
  node: ClusterNode;
  role: NodeRole;
  stats: NodeStats;
  chain: string[] | null;
  isLea: boolean;
  hiddenCount: number;
  isolated: boolean;
  onIsolate: () => void;
  onHighlightChain: () => void;
  onClose: () => void;
}

export function NodeInspector({
  node,
  role,
  stats,
  chain,
  isLea,
  hiddenCount,
  isolated,
  onIsolate,
  onHighlightChain,
  onClose,
}: NodeInspectorProps) {
  return (
    <div className="nk-graph-inspector" data-testid="node-inspector">
      <div className="nk-graph-inspector__head">
        <strong>Account details</strong>
        <button type="button" onClick={onClose} aria-label="Close details" className="nk-graph-inspector__close">
          ✕
        </button>
      </div>
      <dl className="nk-graph-inspector__list">
        <div><dt>Role</dt><dd>{ROLE_LABEL[role]}</dd></div>
        <div><dt>Bank</dt><dd>{node.bank || "N/A"}</dd></div>
        <div>
          <dt>Account</dt>
          <dd><code>{isLea ? node.account_ref || node.masked_ref : node.masked_ref}</code></dd>
        </div>
        {node.isSummary ? (
          <div><dt>Summary</dt><dd>Represents {hiddenCount} truncated accounts</dd></div>
        ) : (
          <>
            <div><dt>Inbound</dt><dd className="data-digit">{stats.inDegree} hops · {formatInr(stats.inPaise)}</dd></div>
            <div><dt>Outbound</dt><dd className="data-digit">{stats.outDegree} hops · {formatInr(stats.outPaise)}</dd></div>
            {stats.firstAt && (
              <div><dt>First seen</dt><dd className="data-digit">{formatSimTime(stats.firstAt)}</dd></div>
            )}
            {stats.lastAt && (
              <div><dt>Last seen</dt><dd className="data-digit">{formatSimTime(stats.lastAt)}</dd></div>
            )}
            <div>
              <dt>Trail from origin</dt>
              <dd>{chain ? `${chain.length - 1} hop${chain.length === 2 ? "" : "s"}` : "not reachable from an origin in the loaded graph"}</dd>
            </div>
          </>
        )}
      </dl>
      {!node.isSummary && (
        <div className="nk-graph-inspector__actions">
          <button type="button" className="nk-btn nk-btn--outline nk-btn--sm" onClick={onIsolate} aria-pressed={isolated}>
            {isolated ? "Show all" : "Isolate trail"}
          </button>
          {chain && chain.length > 1 && (
            <button type="button" className="nk-btn nk-btn--ghost nk-btn--sm" onClick={onHighlightChain}>
              Highlight chain
            </button>
          )}
        </div>
      )}
    </div>
  );
}

interface EdgeInspectorProps {
  edge: ClusterEdge;
  onClose: () => void;
}

export function EdgeInspector({ edge, onClose }: EdgeInspectorProps) {
  return (
    <div className="nk-graph-inspector" data-testid="edge-inspector">
      <div className="nk-graph-inspector__head">
        <strong>Transaction flow</strong>
        <button type="button" onClick={onClose} aria-label="Close details" className="nk-graph-inspector__close">
          ✕
        </button>
      </div>
      <dl className="nk-graph-inspector__list">
        <div><dt>From</dt><dd><code>{edge.from}</code></dd></div>
        <div><dt>To</dt><dd><code>{edge.to}</code></dd></div>
        {edge.label && <div><dt>Label</dt><dd>{edge.label}</dd></div>}
        {edge.amount_paise !== undefined && (
          <div><dt>Amount</dt><dd className="data-digit">{formatInr(edge.amount_paise)}</dd></div>
        )}
        <div><dt>Hop</dt><dd className="data-digit">{edge.layer}</dd></div>
        <div><dt>At</dt><dd className="data-digit">{formatSimTime(edge.event_at)}</dd></div>
      </dl>
    </div>
  );
}
