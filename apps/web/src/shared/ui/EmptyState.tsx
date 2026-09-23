/**
 * EmptyState.tsx — placeholder when no records exist.
 * DOC 3 Web App Shell: shared/ui — EmptyState
 */

import React from "react";

interface EmptyStateProps {
  /** SVG icon or emoji to display. */
  icon?: React.ReactNode;
  title: string;
  message?: string;
  /** Optional call-to-action button. */
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  message,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`nk-empty-state ${className}`} role="status">
      {icon && (
        <div className="nk-empty-state__icon" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="nk-empty-state__title">{title}</h3>
      {message && (
        <p className="nk-empty-state__message">{message}</p>
      )}
      {action && (
        <div className="nk-empty-state__action">{action}</div>
      )}
    </div>
  );
}
