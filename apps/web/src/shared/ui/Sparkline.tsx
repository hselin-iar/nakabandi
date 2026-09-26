/**
 * Sparkline.tsx — a tiny inline trend line for a short series (SVG, no dependency).
 * Built from a client-side rolling buffer wherever the backend keeps no history.
 */

interface SparklineProps {
  values: readonly number[];
  width?: number;
  height?: number;
  label: string;
}

export function Sparkline({ values, width = 120, height = 28, label }: SparklineProps) {
  if (values.length < 2) {
    return <span className="nk-sparkline nk-sparkline--empty" aria-label={`${label}: collecting samples`}>collecting…</span>;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 2;
  const pts = values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (width - pad * 2);
      const y = height - pad - ((v - min) / span) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="nk-sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: ${values.length} samples, latest ${values[values.length - 1]}`}>
      <polyline points={pts} fill="none" stroke="var(--nk-accent)" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
