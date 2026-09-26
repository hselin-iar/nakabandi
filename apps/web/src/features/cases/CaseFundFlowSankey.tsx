/**
 * CaseFundFlowSankey.tsx — where the money went, by bank and hop, as a Sankey (Recharts).
 * Derived client-side from the cluster edges the dossier already loads; shown as a tab next to
 * the network graph, not instead of it.
 */

import { useMemo } from "react";
import { ResponsiveContainer, Sankey, Tooltip } from "recharts";
import { formatInr } from "../../shared/lib/format";
import { buildSankey } from "./sankeyModel";
import type { ClusterGraphData } from "../clusters/types";

interface NodeProps {
  x: number;
  y: number;
  width: number;
  height: number;
  index: number;
  payload: { name: string; column: number; value?: number };
}

/** Bar + bank label (Recharts' default node has no text). */
function SankeyNode({ x, y, width, height, payload }: NodeProps) {
  // Labels sit to the right of each bar; the chart's right margin leaves room for the last column.
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill="#E7EAEE" stroke="#090D12" />
      <text
        x={x + width + 6}
        y={y + height / 2}
        dy="0.35em"
        textAnchor="start"
        fill="#E7EAEE"
        fontSize={11}
      >
        {payload.name}
        {payload.value ? ` · ${formatInr(payload.value, { compact: true })}` : ""}
      </text>
    </g>
  );
}

export function CaseFundFlowSankey({ data, height = 360 }: { data: ClusterGraphData; height?: number }) {
  const sankey = useMemo(() => buildSankey(data.nodes, data.edges), [data]);

  if (sankey.links.length === 0) {
    return (
      <p className="nk-text-xs text-muted" data-testid="sankey-empty" style={{ padding: 16 }}>
        No traced amounts to draw yet.
      </p>
    );
  }

  return (
    <div data-testid="fund-flow-sankey">
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          <Sankey
            data={{ nodes: sankey.nodes, links: sankey.links }}
            nodePadding={28}
            nodeWidth={10}
            margin={{ top: 8, right: 110, bottom: 8, left: 8 }}
            link={{ stroke: "#98A2B3", strokeOpacity: 0.3 }}
            node={SankeyNode as never}
          >
            <Tooltip formatter={(v) => formatInr(Number(v))} />
          </Sankey>
        </ResponsiveContainer>
      </div>
      {sankey.omitted.edges > 0 && (
        <p className="nk-text-xs text-muted" data-testid="sankey-omitted" style={{ padding: "4px 8px" }}>
          {sankey.omitted.edges} {sankey.omitted.edges === 1 ? "hop" : "hops"} ({formatInr(sankey.omitted.paise)}) return money
          to an earlier account and cannot be drawn in a Sankey; see the network view.
        </p>
      )}
    </div>
  );
}
