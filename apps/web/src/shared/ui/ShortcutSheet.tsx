/**
 * ShortcutSheet.tsx — keyboard cheat-sheet overlay, opened with "?".
 *
 * Lists whatever scopes are registered through shortcutRegistry, so it always matches
 * the bindings of the screen the operator is on. The "?" key is ignored while a form
 * field has focus.
 */

import { useEffect, useRef, useState } from "react";
import { useActiveShortcuts } from "./shortcutRegistry";

const GLOBAL_SCOPE_TITLE = "Everywhere";

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

export function ShortcutSheet() {
  const [open, setOpen] = useState(false);
  const scopes = useActiveShortcuts();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        return;
      }
      if (e.key === "?" && !e.metaKey && !e.ctrlKey && !e.altKey && !isTypingTarget(e.target)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="nk-shortcuts__backdrop"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) setOpen(false);
      }}
    >
      <div className="nk-shortcuts" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
        <div className="nk-shortcuts__header">
          <h2 className="nk-shortcuts__title">Keyboard shortcuts</h2>
          <button
            ref={closeRef}
            type="button"
            className="nk-shortcuts__close"
            onClick={() => setOpen(false)}
            aria-label="Close shortcuts"
          >
            Esc
          </button>
        </div>
        <section className="nk-shortcuts__group">
          <h3 className="nk-shortcuts__group-title">{GLOBAL_SCOPE_TITLE}</h3>
          <dl className="nk-shortcuts__list">
            <div className="nk-shortcuts__row">
              <dt><kbd className="nk-kbd">?</kbd></dt>
              <dd>Show or hide this sheet</dd>
            </div>
          </dl>
        </section>
        {scopes.map((s) => (
          <section key={s.scope} className="nk-shortcuts__group">
            <h3 className="nk-shortcuts__group-title">{s.title}</h3>
            <dl className="nk-shortcuts__list">
              {s.entries.map((e) => (
                <div key={e.keys + e.description} className="nk-shortcuts__row">
                  <dt><kbd className="nk-kbd">{e.keys}</kbd></dt>
                  <dd>{e.description}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </div>
  );
}
