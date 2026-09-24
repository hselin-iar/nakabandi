/**
 * format.ts — formatting helpers for the NAKABANDI UI.
 * DOC 3 Web App Shell: shared/lib/format.ts (INR money, sim-time, durations)
 *
 * SRP: pure functions, no React, no I/O.
 */

// ---------------------------------------------------------------------------
// Currency — Indian Rupee (Paise → INR)
// ---------------------------------------------------------------------------

/**
 * Convert paise (integer) to INR (float).
 *
 * @example paiseToInr(150050) → 1500.50
 */
export function paiseToInr(paise: number): number {
  return paise / 100;
}

/**
 * Format paise as a human-readable INR string using the Indian numbering system.
 *
 * @param paise   Integer paise value (positive or negative).
 * @param options compact: true → abbreviates large values (₹1.5L, ₹3.2Cr).
 *
 * @example
 *   formatInr(150050)              → "₹1,500.50"
 *   formatInr(10_000_00)           → "₹1,00,000.00"
 *   formatInr(15_000_000, { compact: true }) → "₹1.5L"
 */
export function formatInr(
  paise: number,
  options: { compact?: boolean } = {},
): string {
  const inr = paiseToInr(paise);
  const abs = Math.abs(inr);
  const sign = inr < 0 ? "-" : "";

  if (options.compact) {
    if (abs >= 1_00_00_000) {
      return `${sign}₹${(abs / 1_00_00_000).toFixed(2)}Cr`;
    }
    if (abs >= 1_00_000) {
      return `${sign}₹${(abs / 1_00_000).toFixed(1)}L`;
    }
    if (abs >= 1_000) {
      return `${sign}₹${(abs / 1_000).toFixed(1)}K`;
    }
  }

  // Indian numbering: group rightmost 3, then groups of 2.
  const [wholePart, fracPart] = abs.toFixed(2).split(".");
  const whole = wholePart!;
  let formatted: string;

  if (whole.length > 3) {
    // Last 3 digits form the first group from the right.
    let grouped = "," + whole.slice(-3);
    const rest = whole.slice(0, -3);
    // Remaining digits in groups of 2 from the right.
    let i = rest.length;
    while (i > 0) {
      const start = Math.max(0, i - 2);
      grouped = "," + rest.slice(start, i) + grouped;
      i = start;
    }
    // Strip leading comma.
    formatted = grouped.slice(1);
  } else {
    formatted = whole;
  }

  return `${sign}₹${formatted}.${fracPart}`;
}

// ---------------------------------------------------------------------------
// Sim-time formatting
// ---------------------------------------------------------------------------

/**
 * Format an ISO sim-time string to a locale-friendly display string.
 *
 * @param iso            ISO-8601 datetime (e.g. "2026-01-15T10:30:00Z")
 * @param options.includeSeconds  include seconds in output (default: false)
 *
 * @example
 *   formatSimTime("2026-01-15T10:30:00Z")               → "15 Jan 2026, 10:30"
 *   formatSimTime("2026-01-15T10:30:45Z", { includeSeconds: true }) → "15 Jan 2026, 10:30:45"
 */
export function formatSimTime(
  iso: string,
  options: { includeSeconds?: boolean } = {},
): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;

    const day = String(d.getUTCDate()).padStart(2, "0");
    const month = d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" });
    const year = d.getUTCFullYear();
    const hh = String(d.getUTCHours()).padStart(2, "0");
    const mm = String(d.getUTCMinutes()).padStart(2, "0");

    if (options.includeSeconds) {
      const ss = String(d.getUTCSeconds()).padStart(2, "0");
      return `${day} ${month} ${year}, ${hh}:${mm}:${ss}`;
    }

    return `${day} ${month} ${year}, ${hh}:${mm}`;
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Duration formatting
// ---------------------------------------------------------------------------

/**
 * Format a duration in seconds to a compact human-readable string.
 *
 * @example
 *   formatDuration(90)        → "1m 30s"
 *   formatDuration(3661)      → "1h 1m"
 *   formatDuration(-60)       → "-1m 0s"
 *   formatDuration(0)         → "0s"
 */
// ---------------------------------------------------------------------------
// Status / action code humanization
// ---------------------------------------------------------------------------

const ALL_CAPS_WORDS = new Set(["fir", "kyc", "upi", "atm", "sim"]);

/**
 * Turn a snake_case status code into a readable label.
 *
 * @example
 *   humanizeStatus("under_investigation") → "Under Investigation"
 *   humanizeStatus("fir_recommended")      → "FIR Recommended"
 */
export function humanizeStatus(status: string): string {
  return status
    .split("_")
    .filter(Boolean)
    .map((word) =>
      ALL_CAPS_WORDS.has(word.toLowerCase())
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1),
    )
    .join(" ");
}

/**
 * Turn a dotted, snake_case audit/timeline action code into a readable "Namespace: Verb"
 * label instead of shouting the raw code in caps.
 *
 * @example
 *   humanizeAction("alert.acknowledge")   → "Alert: Acknowledge"
 *   humanizeAction("outcome.hit")         → "Outcome: Hit"
 *   humanizeAction("alert.request_hold")  → "Alert: Request hold"
 */
export function humanizeAction(code: string): string {
  const parts = code.split(".").filter(Boolean);
  const verb = (parts.pop() ?? code).replace(/_/g, " ");
  const verbLabel = verb.charAt(0).toUpperCase() + verb.slice(1);
  if (parts.length === 0) return verbLabel;
  const namespace = parts.join(".");
  const namespaceLabel = namespace.charAt(0).toUpperCase() + namespace.slice(1);
  return `${namespaceLabel}: ${verbLabel}`;
}

/**
 * Whether a separate "kind" badge is worth showing next to a target's name — false when the
 * name already spells out the kind (e.g. name "MG Road ATM" with kind "ATM" would otherwise
 * render as "MG Road ATM ATM").
 */
export function shouldShowKindBadge(name: string, kind: string): boolean {
  if (!kind) return false;
  return !name.toLowerCase().includes(kind.toLowerCase());
}

export function formatDuration(seconds: number): string {
  if (seconds === 0) return "0s";

  const sign = seconds < 0 ? "-" : "";
  const abs = Math.abs(Math.round(seconds));

  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const s = abs % 60;

  if (h > 0) {
    return `${sign}${h}h ${m}m`;
  }

  return `${sign}${m}m ${s}s`;
}
