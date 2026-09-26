/**
 * CommandPaletteHost.tsx — feeds the shared CommandPalette with what the operator can reach.
 *
 * Lives in app/ (not shared/) because it composes several features' data hooks. It is only
 * mounted while the palette is open, so it adds no polling of its own. Everything shown is
 * gated the same way the rest of the UI is (route permissions here; the server's
 * allowed_actions for anything that changes state, checked again by the alerts screen).
 *
 * Bank codes and masked account refs are what this data model actually has: there is no
 * IFSC field anywhere in the contracts (overhaul plan §0).
 */

import { useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { CommandPalette, type PaletteGroup } from "../../shared/ui";
import { setShortcutSheetOpen } from "../../shared/ui/shortcutRegistry";
import { selectionStore, useSelection } from "../../shared/state/selectionStore";
import { useDossierActions } from "../../shared/state/dossierActions";
import { isSoundEnabled, setSoundEnabled } from "../../shared/audio/soundPreference";
import { useAlerts } from "../../features/alerts/api/useAlerts";
import { useCases } from "../../features/cases/api/useCases";
import { usePrincipal } from "../auth/usePrincipal";
import type { Permission, Role } from "../../shared/api/enums.ts";

interface NavTarget {
  to: string;
  label: string;
  hint: string;
  require?: Permission;
  allowedRoles?: Role[];
}

// Mirrors NAV_ITEMS in Shell.tsx (labels and gates); keep the two in step.
const NAV_TARGETS: readonly NavTarget[] = [
  { to: "/", label: "Command", hint: "overview" },
  { to: "/alerts", label: "Triage", hint: "alerts", require: "VIEW_ALERTS" },
  { to: "/map", label: "Deployment", hint: "map", require: "VIEW_ALERTS" },
  { to: "/cases", label: "Investigate", hint: "cases", require: "VIEW_CASES" },
  { to: "/system", label: "System Integrity", hint: "trust", require: "VIEW_EVALUATION" },
  { to: "/demo", label: "Demo", hint: "simulator", allowedRoles: ["demo_operator", "admin"] },
];

const MAX_ENTITY_ITEMS = 200;

export function CommandPaletteHost({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { principal, can } = usePrincipal();
  const selection = useSelection();
  const dossier = useDossierActions();

  const { data: alerts = [] } = useAlerts({ view: "all" });
  const { data: cases = [] } = useCases();

  const groups = useMemo<PaletteGroup[]>(() => {
    const out: PaletteGroup[] = [];

    // ---- Context: what can be done with what is selected right now ----
    const selectedAlert = selection?.kind === "alert" ? alerts.find((a) => a.id === selection.id) : undefined;
    const context: PaletteGroup = { heading: "Selected alert", items: [] };
    if (selectedAlert) {
      const name = String(selectedAlert.target.name ?? selectedAlert.target.id ?? selectedAlert.id);
      context.items.push({
        id: "ctx-open-alert",
        label: `Open ${selectedAlert.cluster_ref} · ${name}`,
        hint: selectedAlert.severity,
        onSelect: () => navigate(`/alerts/${selectedAlert.id}`),
      });
      context.items.push({
        id: "ctx-show-map",
        label: "Show selected alert on the map",
        hint: "Deployment",
        onSelect: () => navigate("/map"),
      });
      const relatedCase = cases.find((c) => c.cluster_ref === selectedAlert.cluster_ref);
      if (relatedCase) {
        context.items.push({
          id: "ctx-open-case",
          label: `Open the case for ${relatedCase.cluster_ref}`,
          hint: "Investigate",
          onSelect: () => navigate(`/cases/${relatedCase.id}`),
        });
      }
      // Consequential actions still go through press-and-hold on the alerts screen, and the
      // server's allowed_actions decides whether the dialog opens at all.
      if (can("REQUEST_HOLD")) {
        context.items.push({
          id: "ctx-freeze",
          label: "Freeze: request a hold on the selected alert",
          hint: "hold to confirm",
          onSelect: () => {
            selectionStore.requestAction("request_hold");
            navigate(`/alerts/${selectedAlert.id}`);
          },
        });
      }
      if (can("DISPATCH")) {
        context.items.push({
          id: "ctx-dispatch",
          label: "Dispatch a unit to the selected alert",
          hint: "hold to confirm",
          onSelect: () => {
            selectionStore.requestAction("dispatch");
            navigate(`/alerts/${selectedAlert.id}`);
          },
        });
      }
    }
    out.push(context);

    // ---- Open case dossier: graph commands (registered by the mounted graph) ----
    if (dossier) {
      const items: PaletteGroup["items"] = [];
      for (let hop = 1; hop <= dossier.maxHop; hop++) {
        items.push({
          id: `dossier-hop-${hop}`,
          label: hop === dossier.maxHop ? `Show all hops (1–${hop})` : `Show hops 1–${hop} only`,
          hint: "graph",
          keywords: ["jump", "hop", `hop ${hop}`],
          onSelect: () => dossier.showHopsUpTo(hop),
        });
      }
      if (dossier.hasSelection()) {
        items.push({ id: "dossier-isolate", label: "Isolate the trail around the selected account", hint: "graph", onSelect: dossier.isolateSelected });
      }
      items.push(
        { id: "dossier-export-png", label: "Export graph view as PNG (working copy)", hint: "not the evidence pack", onSelect: dossier.exportPng },
        { id: "dossier-export-csv", label: "Export visible hops as CSV (working copy)", hint: "not the evidence pack", onSelect: dossier.exportCsv },
      );
      out.push({ heading: "Case dossier", items });
    }

    // ---- Go to ----
    out.push({
      heading: "Go to",
      items: NAV_TARGETS.filter((t) => {
        if (t.allowedRoles) return principal !== null && t.allowedRoles.includes(principal.role);
        if (t.require) return can(t.require);
        return true;
      })
        .filter((t) => t.to !== pathname)
        .map((t) => ({ id: `nav-${t.to}`, label: t.label, hint: t.hint, onSelect: () => navigate(t.to) })),
    });

    // ---- Alerts ----
    out.push({
      heading: "Alerts",
      items: alerts.slice(0, MAX_ENTITY_ITEMS).map((a) => ({
        id: `alert-${a.id}`,
        label: `${a.cluster_ref} · ${String(a.target.name ?? a.target.id ?? "")}`,
        hint: `${a.severity} · ${a.status}`,
        keywords: [a.id, a.severity, a.status],
        onSelect: () => {
          selectionStore.set({ kind: "alert", id: a.id });
          navigate(`/alerts/${a.id}`);
        },
      })),
    });

    // ---- Cases ----
    out.push({
      heading: "Cases",
      items: cases.slice(0, MAX_ENTITY_ITEMS).map((c) => ({
        id: `case-${c.id}`,
        label: `Case ${c.cluster_ref}`,
        hint: `${c.complaint_count} complaints`,
        keywords: [c.id],
        onSelect: () => {
          selectionStore.set({ kind: "cluster", id: c.cluster_ref });
          navigate(`/cases/${c.id}`);
        },
      })),
    });

    // ---- Accounts (masked refs) and banks: the identity fields this data model has ----
    const accountItems: PaletteGroup["items"] = [];
    const bankCases = new Map<string, { caseId: string; accounts: number }>();
    for (const c of cases) {
      for (const acct of c.accounts) {
        if (accountItems.length < MAX_ENTITY_ITEMS) {
          accountItems.push({
            id: `acct-${c.id}-${acct.masked_ref}`,
            label: acct.masked_ref,
            hint: acct.bank,
            keywords: [acct.bank, c.cluster_ref],
            onSelect: () => navigate(`/cases/${c.id}`),
          });
        }
        const seen = bankCases.get(acct.bank);
        bankCases.set(acct.bank, { caseId: seen?.caseId ?? c.id, accounts: (seen?.accounts ?? 0) + 1 });
      }
    }
    out.push({ heading: "Accounts", items: accountItems });
    out.push({
      heading: "Banks",
      items: [...bankCases.entries()].map(([bank, v]) => ({
        id: `bank-${bank}`,
        label: `Bank ${bank}`,
        hint: `${v.accounts} accounts`,
        onSelect: () => navigate(`/cases/${v.caseId}`),
      })),
    });

    // ---- Anywhere ----
    out.push({
      heading: "Commands",
      items: [
        {
          id: "cmd-sound",
          label: isSoundEnabled() ? "Turn alert sounds off" : "Turn alert sounds on",
          onSelect: () => setSoundEnabled(!isSoundEnabled()),
        },
        { id: "cmd-shortcuts", label: "Show keyboard shortcuts", hint: "?", onSelect: () => setShortcutSheetOpen(true) },
      ],
    });

    return out;
  }, [alerts, cases, selection, dossier, pathname, principal, can, navigate]);

  return <CommandPalette open={open} onOpenChange={onOpenChange} groups={groups} />;
}
