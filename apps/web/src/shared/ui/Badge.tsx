/**
 * Badge.tsx — badge variants for severity, verdict, ladder level, and status.
 * DOC 3 Web App Shell: shared/ui — Badge variants
 *
 * Every variant shows: icon + text + colour.
 * Colour is NEVER the only signal (accessibility, DOC 2 §2.7).
 */

import React from "react";
import type { Severity, Verdict, LadderLevel, AlertStatus, DeliveryStatus } from "../api/enums.ts";

// ---------------------------------------------------------------------------
// Base badge
// ---------------------------------------------------------------------------

interface BadgeProps {
  icon: React.ReactNode;
  label: string;
  colorClass: string;
  className?: string;
}

function Badge({ icon, label, colorClass, className = "" }: BadgeProps) {
  return (
    <span className={`nk-badge ${colorClass} ${className}`} aria-label={label}>
      <span className="nk-badge__icon" aria-hidden="true">{icon}</span>
      <span className="nk-badge__label">{label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// SVG icons (inline, no external dep)
// ---------------------------------------------------------------------------

const Icons = {
  /** Severity — low: info circle */
  Low: () => (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <line x1="8" y1="7" x2="8" y2="11" strokeWidth="1.5" stroke="currentColor" />
      <circle cx="8" cy="5" r="0.8" fill="currentColor" />
    </svg>
  ),
  /** Severity — medium: warning triangle */
  Medium: () => (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 2L15 13H1L8 2Z" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinejoin="round" />
      <line x1="8" y1="7" x2="8" y2="10" strokeWidth="1.5" stroke="currentColor" />
      <circle cx="8" cy="11.5" r="0.7" fill="currentColor" />
    </svg>
  ),
  /** Severity — high: exclamation diamond */
  High: () => (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 1L15 8L8 15L1 8Z" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinejoin="round" />
      <line x1="8" y1="5" x2="8" y2="9.5" strokeWidth="1.5" stroke="currentColor" />
      <circle cx="8" cy="11" r="0.7" fill="currentColor" />
    </svg>
  ),
  /** Severity — critical: lightning bolt */
  Critical: () => (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M10 2L4 9h5l-2 5 8-8h-5z" strokeLinejoin="round" />
    </svg>
  ),
  /** Verdict — good: check */
  Check: () => (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <polyline points="3,8 6.5,12 13,4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  /** Verdict — warn: dash */
  Dash: () => (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="4" y1="8" x2="12" y2="8" strokeLinecap="round" />
    </svg>
  ),
  /** Verdict — bad: X */
  X: () => (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <line x1="4" y1="4" x2="12" y2="12" strokeLinecap="round" />
      <line x1="12" y1="4" x2="4" y2="12" strokeLinecap="round" />
    </svg>
  ),
  /** Ladder — escalation stairs */
  Stairs: () => (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <polyline points="2,14 2,10 6,10 6,6 10,6 10,2 14,2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  /** Status — open: circle */
  Circle: () => (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="8" cy="8" r="5" />
    </svg>
  ),
  /** Status — ack: eye */
  Eye: () => (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M1 8s3-5 7-5 7 5 7 5-3 5-7 5-7-5-7-5z" strokeLinejoin="round" />
      <circle cx="8" cy="8" r="2" />
    </svg>
  ),
  /** Status — actioned: check-circle */
  CheckCircle: () => (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="8" cy="8" r="6" />
      <polyline points="5,8 7,10.5 11,5.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  /** Status — expired: clock */
  Clock: () => (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="8" cy="8" r="6" />
      <polyline points="8,5 8,8 10.5,10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};

// ---------------------------------------------------------------------------
// SeverityBadge
// ---------------------------------------------------------------------------

const SEVERITY_CONFIG: Record<
  Severity,
  { label: string; colorClass: string; icon: React.ReactNode }
> = {
  LOW: { label: "Low", colorClass: "nk-badge--severity-low", icon: <Icons.Low /> },
  MEDIUM: { label: "Medium", colorClass: "nk-badge--severity-medium", icon: <Icons.Medium /> },
  HIGH: { label: "High", colorClass: "nk-badge--severity-high", icon: <Icons.High /> },
  CRITICAL: { label: "Critical", colorClass: "nk-badge--severity-critical", icon: <Icons.Critical /> },
};

export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity;
  className?: string;
}) {
  const cfg = SEVERITY_CONFIG[severity];
  return (
    <Badge
      icon={cfg.icon}
      label={cfg.label}
      colorClass={cfg.colorClass}
      className={className}
    />
  );
}

// ---------------------------------------------------------------------------
// VerdictBadge
// ---------------------------------------------------------------------------

const VERDICT_CONFIG: Record<
  Verdict,
  { label: string; colorClass: string; icon: React.ReactNode }
> = {
  INTERCEPTABLE: {
    label: "Interceptable",
    colorClass: "nk-badge--verdict-good",
    icon: <Icons.Check />,
  },
  MARGINAL: {
    label: "Marginal",
    colorClass: "nk-badge--verdict-warn",
    icon: <Icons.Dash />,
  },
  NOT_INTERCEPTABLE: {
    label: "Not Interceptable",
    colorClass: "nk-badge--verdict-bad",
    icon: <Icons.X />,
  },
};

export function VerdictBadge({
  verdict,
  className,
}: {
  verdict: Verdict;
  className?: string;
}) {
  const cfg = VERDICT_CONFIG[verdict];
  return (
    <Badge
      icon={cfg.icon}
      label={cfg.label}
      colorClass={cfg.colorClass}
      className={className}
    />
  );
}

// ---------------------------------------------------------------------------
// LadderBadge
// ---------------------------------------------------------------------------

const LADDER_CONFIG: Record<
  LadderLevel,
  { label: string; colorClass: string }
> = {
  NONE: { label: "No Action", colorClass: "nk-badge--ladder-none" },
  L1: { label: "L1 · Notify", colorClass: "nk-badge--ladder-l1" },
  L2: { label: "L2 · Hold", colorClass: "nk-badge--ladder-l2" },
  L3: { label: "L3 · Dispatch", colorClass: "nk-badge--ladder-l3" },
};

export function LadderBadge({
  level,
  className,
}: {
  level: LadderLevel;
  className?: string;
}) {
  const cfg = LADDER_CONFIG[level];
  return (
    <Badge
      icon={<Icons.Stairs />}
      label={cfg.label}
      colorClass={cfg.colorClass}
      className={className}
    />
  );
}

// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  AlertStatus,
  { label: string; colorClass: string; icon: React.ReactNode }
> = {
  open: { label: "Open", colorClass: "nk-badge--status-open", icon: <Icons.Circle /> },
  acknowledged: { label: "Acknowledged", colorClass: "nk-badge--status-ack", icon: <Icons.Eye /> },
  actioned: { label: "Actioned", colorClass: "nk-badge--status-actioned", icon: <Icons.CheckCircle /> },
  escalated: { label: "Escalated", colorClass: "nk-badge--severity-high", icon: <Icons.High /> },
  expired: { label: "Expired", colorClass: "nk-badge--status-expired", icon: <Icons.Clock /> },
  closed: { label: "Closed", colorClass: "nk-badge--status-expired", icon: <Icons.CheckCircle /> },
};

export function StatusBadge({
  status,
  className,
}: {
  status: AlertStatus;
  className?: string;
}) {
  const cfg = STATUS_CONFIG[status];
  return (
    <Badge
      icon={cfg.icon}
      label={cfg.label}
      colorClass={cfg.colorClass}
      className={className}
    />
  );
}

// ---------------------------------------------------------------------------
// DeliveryStatusBadge
// ---------------------------------------------------------------------------

const DELIVERY_STATUS_CONFIG: Record<
  DeliveryStatus,
  { label: string; colorClass: string; icon: React.ReactNode }
> = {
  sent: { label: "Delivered", colorClass: "nk-badge--status-actioned", icon: <Icons.CheckCircle /> },
  pending: { label: "Pending", colorClass: "nk-badge--status-ack", icon: <Icons.Clock /> },
  failed: { label: "Retrying", colorClass: "nk-badge--severity-high", icon: <Icons.Medium /> },
  dead: { label: "Failed", colorClass: "nk-badge--status-expired", icon: <Icons.X /> },
};

export function DeliveryStatusBadge({
  status,
  className,
}: {
  status: DeliveryStatus;
  className?: string;
}) {
  const cfg = DELIVERY_STATUS_CONFIG[status];
  return (
    <Badge
      icon={cfg.icon}
      label={cfg.label}
      colorClass={cfg.colorClass}
      className={className}
    />
  );
}
