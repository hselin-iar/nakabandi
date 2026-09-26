/**
 * index.ts — barrel export for shared/ui components.
 * DOC 3 Web App Shell: shared/ui
 *
 * Features import from here only — never from individual component files directly.
 */

export { Button } from "./Button";
export type { ButtonProps, ButtonVariant, ButtonSize } from "./Button";

export { SeverityBadge, VerdictBadge, LadderBadge, StatusBadge } from "./Badge";

export { ConfidenceBar } from "./ConfidenceBar";

export { Countdown } from "./Countdown";

export { MaskedRef } from "./MaskedRef";

export { DataTable } from "./DataTable";
export type { Column } from "./DataTable";

export { KeyValue } from "./KeyValue";

export { Timeline } from "./Timeline";
export type { TimelineEntry } from "./Timeline";

export { Drawer } from "./Drawer";

export { Panel } from "./Panel";

export { EmptyState } from "./EmptyState";

export { ErrorState } from "./ErrorState";

export { ShortcutSheet } from "./ShortcutSheet";
export { registerShortcuts, useRegisterShortcuts } from "./shortcutRegistry";
export type { ShortcutEntry, ShortcutScope } from "./shortcutRegistry";
