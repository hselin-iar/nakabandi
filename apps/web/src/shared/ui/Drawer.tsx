/**
 * Drawer.tsx — slide-over detail panel.
 * DOC 3 Web App Shell: shared/ui — Drawer
 *
 * Features:
 *   - Focus trap on open; restores focus on close.
 *   - ESC key dismissal.
 *   - aria-modal, role="dialog".
 *   - Backdrop click to close.
 */

import React, { useEffect, useRef } from "react";

interface DrawerProps {
  /** Whether the drawer is open. */
  open: boolean;
  /** Called when the drawer should close. */
  onClose: () => void;
  /** Drawer title (shown in header). */
  title: string;
  children: React.ReactNode;
  /** Width class override. */
  width?: "sm" | "md" | "lg";
  /** Edge the drawer slides in from (default right). */
  side?: "left" | "right";
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  width = "md",
  side = "right",
}: DrawerProps) {
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Capture previous focus and restore on close.
  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      // Move focus into the drawer after paint.
      requestAnimationFrame(() => {
        drawerRef.current?.focus();
      });
    } else if (previousFocusRef.current) {
      previousFocusRef.current.focus();
      previousFocusRef.current = null;
    }
  }, [open]);

  // ESC to close.
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  // Focus trap within the drawer.
  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key !== "Tab") return;
    const drawer = drawerRef.current;
    if (!drawer) return;
    const focusable = drawer.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) return;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="nk-drawer-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Drawer panel */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`nk-drawer nk-drawer--${width}${side === "left" ? " nk-drawer--left" : ""}`}
        onKeyDown={handleKeyDown}
      >
        <div className="nk-drawer__header">
          <h2 className="nk-drawer__title">{title}</h2>
          <button
            className="nk-drawer__close"
            onClick={onClose}
            aria-label="Close panel"
          >
            ✕
          </button>
        </div>
        <div className="nk-drawer__body">{children}</div>
      </div>
    </>
  );
}
