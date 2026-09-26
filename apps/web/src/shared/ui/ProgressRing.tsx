/**
 * ProgressRing.tsx — a 0–1 score drawn as a ring, with an honest state for "cannot be computed".
 *
 * `value === null` means the metric had too few samples: the ring renders empty with an
 * "insufficient sample" caption (and the sample size), never as 0% and never as a blank.
 */

interface ProgressRingProps {
  value: number | null;
  label: string;
  /** Sample size behind the value; shown when the value is missing. */
  n?: number;
  size?: number;
  strokeWidth?: number;
}

export function ProgressRing({ value, label, n, size = 96, strokeWidth = 8 }: ProgressRingProps) {
  const r = (size - strokeWidth) / 2;
  const circ = 2 * Math.PI * r;
  const known = value !== null && Number.isFinite(value);
  const offset = circ * (1 - (known ? Math.max(0, Math.min(1, value)) : 0));
  return (
    <div className="nk-ring-gauge" data-testid={`gauge-${label}`} role="img" aria-label={known ? `${label}: ${(value * 100).toFixed(1)}%` : `${label}: insufficient sample`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--nk-border-subtle)" strokeWidth={strokeWidth} />
        {known && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--nk-accent)"
            strokeWidth={strokeWidth}
            strokeDasharray={circ}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: "stroke-dashoffset 0.8s ease" }}
          />
        )}
        <text
          x="50%"
          y="50%"
          dominantBaseline="middle"
          textAnchor="middle"
          fill={known ? "var(--nk-text-primary)" : "var(--nk-text-tertiary)"}
          fontSize={known ? size * 0.22 : size * 0.16}
          fontWeight={590}
          className="data-digit"
        >
          {known ? `${(value * 100).toFixed(1)}%` : "n/a"}
        </text>
      </svg>
      <span className="nk-ring-gauge__label">{label}</span>
      {!known && <span className="nk-ring-gauge__note">insufficient sample{n !== undefined ? ` (n=${n})` : ""}</span>}
    </div>
  );
}
