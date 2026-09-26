/**
 * CommandPalette.tsx — Cmd/Ctrl+K "go to anything" palette, built on cmdk.
 *
 * Presentational only: the caller (app shell) supplies grouped, already-permission-filtered
 * items, so this file imports no feature. Fuzzy matching is cmdk's own; each item can carry
 * extra `keywords` (e.g. the bank code of a masked account) that match without being shown.
 */

import { Command } from "cmdk";

export interface PaletteItem {
  id: string;
  label: string;
  /** Right-aligned secondary text. */
  hint?: string;
  /** Extra searchable terms that are not displayed. */
  keywords?: string[];
  onSelect: () => void;
}

export interface PaletteGroup {
  heading: string;
  items: PaletteItem[];
}

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groups: PaletteGroup[];
}

export function CommandPalette({ open, onOpenChange, groups }: CommandPaletteProps) {
  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command palette"
      overlayClassName="nk-palette__overlay"
      contentClassName="nk-palette"
      loop
    >
      <Command.Input className="nk-palette__input" placeholder="Search alerts, cases, accounts, banks, or run a command…" />
      <Command.List className="nk-palette__list">
        <Command.Empty className="nk-palette__empty">Nothing matches.</Command.Empty>
        {groups
          .filter((g) => g.items.length > 0)
          .map((g) => (
            <Command.Group key={g.heading} heading={g.heading} className="nk-palette__group">
              {g.items.map((item) => (
                <Command.Item
                  key={item.id}
                  value={`${item.id} ${item.label}`}
                  keywords={item.keywords}
                  className="nk-palette__item"
                  onSelect={() => {
                    onOpenChange(false);
                    item.onSelect();
                  }}
                >
                  <span className="nk-palette__label">{item.label}</span>
                  {item.hint && <span className="nk-palette__hint">{item.hint}</span>}
                </Command.Item>
              ))}
            </Command.Group>
          ))}
      </Command.List>
    </Command.Dialog>
  );
}
