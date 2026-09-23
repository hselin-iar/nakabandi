/**
 * Panel.tsx — container card with header, body, and optional footer.
 * DOC 3 Web App Shell: shared/ui — Panel
 */

import React from "react";

interface PanelProps {
  title?: string;
  /** Right-side header actions. */
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function Panel({ title, actions, footer, children, className = "" }: PanelProps) {
  return (
    <section className={`nk-panel ${className}`}>
      {(title || actions) && (
        <div className="nk-panel__header">
          {title && <h3 className="nk-panel__title">{title}</h3>}
          {actions && <div className="nk-panel__actions">{actions}</div>}
        </div>
      )}
      <div className="nk-panel__body">{children}</div>
      {footer && <div className="nk-panel__footer">{footer}</div>}
    </section>
  );
}
