/**
 * Button.tsx — base button component.
 * DOC 3 Web App Shell: shared/ui — Button
 */

import React from "react";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "danger"
  | "ghost"
  | "outline";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  /** Full-width button. */
  block?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  block = false,
  disabled,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  const cls = [
    "nk-btn",
    `nk-btn--${variant}`,
    `nk-btn--${size}`,
    block ? "nk-btn--block" : "",
    loading ? "nk-btn--loading" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      {...rest}
      className={cls}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading && (
        <span className="nk-btn__spinner" aria-hidden="true" />
      )}
      <span className={loading ? "nk-btn__label--loading" : ""}>{children}</span>
    </button>
  );
}
