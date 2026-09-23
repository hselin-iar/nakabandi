/**
 * ErrorState.tsx — error display with server message and retry.
 * DOC 3 Web App Shell: shared/ui — ErrorState
 *
 * Works with apiError() output — message is already user text from the server.
 */

import React from "react";
import type { UiError } from "../api/apiError";

interface ErrorStateProps {
  error: UiError;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ error, onRetry, className = "" }: ErrorStateProps) {
  return (
    <div className={`nk-error-state ${className}`} role="alert">
      <span className="nk-error-state__icon" aria-hidden="true">⚠</span>
      <p className="nk-error-state__message">{error.message}</p>
      {error.code && error.code !== "error" && (
        <p className="nk-error-state__code">Error: {error.code}</p>
      )}
      {onRetry && (
        <button className="nk-btn nk-btn--secondary nk-btn--sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
