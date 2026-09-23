/**
 * MaskedRef.tsx — display server-masked identifiers.
 * DOC 3 Web App Shell: shared/ui — MaskedRef
 *
 * Shows the value exactly as delivered by the API.
 * Masking is server-side; this component NEVER attempts unmasking.
 */

import React from "react";

interface MaskedRefProps {
  /** The reference value as returned by the server (may be masked). */
  value: string;
  /** If true, renders a visual "masked" indicator. */
  masked?: boolean;
  className?: string;
}

export function MaskedRef({ value, masked = false, className = "" }: MaskedRefProps) {
  return (
    <span className={`nk-masked-ref ${className}`}>
      <code className="nk-masked-ref__value">{value}</code>
      {masked && (
        <span
          className="nk-masked-ref__tag"
          aria-label="Identifier is partially masked"
          title="Masking applied by server"
        >
          masked
        </span>
      )}
    </span>
  );
}
