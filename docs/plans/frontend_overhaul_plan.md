# NAKABANDI Frontend Overhaul — Implementation Plan

**Status:** Draft for review
**Scope:** `apps/web` only. No backend contract changes (LC-1..LC-10 untouched). Optional, additive backend suggestions are flagged in §5 but none is required to execute Phases 1–5.
**Inputs synthesized:** `docs/research/{chatgpt,claude,gemini,grok}_frontend_operational_command_patterns.md`, `apps/web/src/shared/api/schema.d.ts` (2,723 lines, cross-checked against the Python routers), a full read of the current `apps/web` implementation, and a second pass over Claude's report plus its OSIRIS follow-up (`simplifaisoul/osiris`, MIT; supplied as a pasted note, not yet saved under `docs/research/`).
**Sequencing principle:** phases are ordered by **demo visibility**, not by architectural tidiness (§3.0). Anything an audience sees in the first minutes of a demo lands before anything they would only see if they dug for it.

---

## 0. Corrections to source material (read this before the rest of the plan)

The four research reports and the original task brief both contain a few claims that a verification pass against the real backend and the real frontend did **not** confirm. Every downstream section below is written against the corrected facts, not the original assumptions. Flagging them once, up front, so nothing in the plan silently contradicts them later:

| Claim | Reality | Impact |
|---|---|---|
| "Command palette fuzzy search across alerts, cases, **IFSC codes**, and account numbers" | There is **no `ifsc` field anywhere** in the backend contracts (`schema.d.ts`, `ClusterNodeModel`, `CaseModel`, `AccountRefModel`). Identity is only `bank` (a bank code string) + `masked_ref`/`account_ref`. | Command palette (§2.5) indexes **bank codes + masked account refs**, not IFSC. Do not build an `ifsc` field into any component. |
| "`EvaluationPage.tsx` is an unadorned HTML `<table>`" | False. It already has an animated SVG ring gauge, uses shared `nk-table` classes (styled, not bare), and tokens.css has several *orphaned* classes (`.nk-eval-run-pill`, `.nk-cold-start-chart`, `.nk-feedback-plot`) suggesting a half-built comparison/chart feature that was cut. | Phase 5 work here is "finish and richen an existing page," not "build a table from scratch." |
| Task assumes a live `/evaluation` REST API backs "interactive Brier score curves, hit-rate@k rings, latency sparklines" | **There is no evaluation router mounted in the FastAPI app at all.** `Permission.VIEW_EVALUATION` exists in the enum with zero call sites. The only producer is the offline `scripts/evaluate.py`, which writes `apps/web/public/eval-results.json` containing scalar `hit_rate_at_{1,3,5}`, `precision_at_{1,3,5}`, `brier_score` — no calibration curve, no lead-time distribution, no time series. **The script also emits bare, non-JSON-spec `NaN` tokens** (Python's `json.dumps(..., allow_nan=True)`) whenever a metric's sample size is below `_MIN_N = 30`. A plain `res.json()` / `JSON.parse` will throw `SyntaxError` on that file the first time any metric is under-sampled. | System HUD (§2.4) is scoped to what this file + the real `/system/metrics`, `/audit/verify`, `/analytics/live-metrics` endpoints actually provide. "Brier score curve" (a reliability/calibration diagram) is **not buildable today** — see §5 for the one optional, additive backend change that would unlock it. The NaN-parsing landmine must be fixed client-side regardless (§2.4, §3 Phase 5). |
| Task's permitted-stack list omits Framer Motion / Tremor / Turf.js, but the research reports lean on them | Followed literally: **no Motion, no Tremor, no Turf.js are added.** Rolling counters, hold-to-actuate fill, and the map's pulsating radar are all built with plain CSS transitions/keyframes + `requestAnimationFrame` + Canvas2D, which the research itself shows is sufficient (Gemini's own code samples for the timer ring and radar marker use no animation library). | Dependency list in §3 stays exactly to what the task body names explicitly, plus two small, justified additions (`postcss`, `autoprefixer` — required to make Tailwind function at all, see below). |
| Countdown timers can be driven by `performance.now()` per the research's `TimeProvider` pattern | This app's timers are **not wall-clock**. Every countdown (`Countdown.tsx`, `LadderDecisionPath.tsx`, `TimeSlider.tsx`) is deliberately driven off `useSimTime()`, which reads the `sim.time` SSE event — a documented, enforced convention ("no `Date.now()` for sim purposes"). | The single-RAF `TimeProvider` (§2.1) must interpolate forward from the last known `sim.time` tick using `requestAnimationFrame`, not from `performance.now()` in isolation. This preserves the existing sim-clock invariant while still fixing the N-independent-`setInterval` problem the research identifies. |
| Cytoscape graph work starts from a blank slate | `ClusterGraph.tsx` already renders the mule graph with raw `cytoscape` (no React wrapper), a hand-computed `preset` layout ordered by `ClusterEdgeModel.layer` (left→right hop order), a 200-node cap with a synthetic "+N more" summary node, and kind-based styling (victim/mule/aggregator/exit/summary). This is a **real, working, well-engineered component**, not a stub. | Phase 4b (§3) is a migration (raw Cytoscape → `react-cytoscapejs`, hand-rolled `preset` positions → `cytoscape-dagre`) plus additive features (`cytoscape-expand-collapse`, Sankey), not a rewrite from zero. Its 200-node cap logic should be preserved/ported, not discarded. |
| `ClusterGraph.tsx`'s node styling differentiates victim/mule/aggregator/exit accounts (this is why the graph currently looks like it renders "one shape for everything") | **Root cause traced and confirmed**: `apps/api/src/nakabandi/casework/__init__.py`, `cluster_graph()` (lines 106–131), builds every single `ClusterNode` with `kind="account"` **hardcoded literally** — there is no victim/mule/aggregator/exit classification anywhere in the backend data model. `ClusterNode`/`AccountFact` (`casework/domain/case.py`) carry no role field at all. The raw signal exists *upstream* (`ComplaintFact.touched_account_ids` names the victim's account but is only consumed by `bundle.py` for headcounts; `CashOutFact.account_id` in `graph/application/apply_cashouts.py` records a cash-out but is written only into aggregate `cluster_location_stats`, never persisted per-account) but neither is threaded through to the graph endpoint. So every real node's `kind` is the literal string `"account"`, which matches none of `ClusterGraph.tsx`'s four kind-specific Cytoscape selectors (`node[kind="victim"]` etc.) — every node silently falls through to the generic default style (`#475569` gray circle, no shape). The frontend code isn't buggy in isolation; it was built against a classification the backend never actually populates. | This is a distinct, verified defect from the raw-Cytoscape→`react-cytoscapejs` migration above and is fixed as its own item, ahead of the migration, in Phase 4a (§2.2, §3) — a frontend-only topology-inferred fix now, with an optional backend follow-up for real ground-truth classification listed alongside the evaluation NaN fix in §5. |
| Tailwind CSS is part of the stack | Tailwind is a `devDependency` (`tailwindcss@^3.4.19`) but **is not wired into the build at all**: no `tailwind.config.*`, no `postcss.config.*`, no `@tailwind` directive anywhere, no `autoprefixer`. `tailwind.preset.ts` exists but nothing consumes it. Every current screen is styled via bespoke `nk-*` BEM classes and inline `style={{}}`. | Phase 1 (§3) must first **stand up Tailwind from zero** (config + PostCSS + directives) before any Tailwind utility class named in this plan (e.g. `border-white/[0.08]`) will actually apply. This is called out explicitly because it's easy to assume "Tailwind's already there" and skip it, and every later screen depends on it working. |
| `react-hot-toast` is in active use | It is mounted (`<Toaster />` in `app/providers.tsx`) but **zero components call `toast.*()` anywhere in the codebase.** | Swapping to `sonner` (task-mandated, and the research's 3-of-4 convergence pick over `react-toastify`) is a one-file change with no call-site migration risk. |
| OSIRIS's always-visible "ZULU" (UTC) clock is a cheap HUD element to copy | A wall-clock UTC readout would contradict this app's sim-clock convention (§0 timers row) and confuse a demo where sim time and wall time differ. | The HUD clock reads `useSimTime()` and is labelled **"SIM ⟨time⟩Z"**, never `new Date()`. |
| OSIRIS's "viewport-aware fetching" and "lazy-load a layer on first toggle" are worth copying | The map's data hooks (`useHeatmap`, `useLocations`, alerts) pass filters, not a bounding box, and the whole dataset is four demo states. Viewport-scoped fetching would need a new backend query param for no measurable gain at this data size. `MapAdapter.setLayerVisibility()` **already exists**, so layer toggling is a UI job, not an adapter job. | Adopt the *toggle + live count* pattern (§2.3). Do **not** build viewport-scoped fetching. Optionally gate each layer's query with `enabled: layerOn`; skip if it complicates the existing debounced-invalidate flow. |
| The current `request_hold` UI works against the real backend | It sends `params.lien_amount_paise`, but `RecordAction._validate_hold` requires `params.account_id` and integer `params.proposed_paise` and otherwise returns `LIEN_INVALID`. The UI could never complete a hold; its test only passed because the API was mocked. Also: a `request_hold`/`dispatch` moves the alert to `actioned`, after which no further action (so no "undo") is accepted. | Phase 2 fixes the request (account picker sourced from `GET /clusters/{cluster_id}` nodes, amount defaulted from the proportionality proposal) and drops the planned UNDO toast (§2.1). A role without cluster access sees "no traced accounts available" instead of a broken request. |
| `DataTable`'s column sort is functional | `sortKey`/`sortDir` state toggles in the UI, but the `visible` memo that feeds the table **never applies the sort** — it is currently cosmetic/non-functional. | Fixed opportunistically in Phase 2 while `DataTable` is already being extended for virtualization (§3 Phase 2) — small, in-scope fix, not a new work item. |

---

## 1. Architectural Synthesis & Design System Overhaul

### 1.1 Why a token *replacement*, not a token *edit*

`tokens.css` is 4,081 lines; `neo-utils.css` is another 136. Only the first ~216 lines are actual design tokens (`:root` custom properties) — the rest is ~3,800 lines of per-page, per-component classes accumulated phase-by-phase ("C3", "C4", "PHASE 3", "PHASE 4", …), a meaningful fraction of which hardcode raw hex instead of `var()` (Demo Console, Map overlay panels, `NoveltyBanner`, `CasesPage`/`CaseDetail`/`ClusterGraph`'s inline dark-slate styling). Patching values in place would leave the escape-hatch hex sprinkled throughout untouched and still fighting the new palette.

**Decision:** full replacement of the *token layer* (`:root` variables + Tailwind preset), executed component-by-component against the new tokens rather than by find/replacing hex codes. `tokens.css` is split during Phase 1 into:
- `shared/tokens/tokens.css` — pure `:root` custom properties only (~150 lines after the cut).
- Per-feature CSS files colocated with their feature (`features/cases/cases.css`, etc.) for anything that genuinely needs a raw stylesheet instead of Tailwind utilities (mostly: the map's always-dark overlay panels, which are a deliberate micro-theme and should stay CSS, not Tailwind).
- Everything else migrates to Tailwind utility classes reading the new preset, consistent with the task's mandated stack.

### 1.2 Unified Tactical Command Theme — token values

Per the task brief's explicit instruction, these are the literal values (not "pick one of four research options" — the brief already resolved that decision):

```css
:root {
  /* Canvas / surface tiers */
  --nk-canvas-bg:        #090D12; /* near-black floor, not pure #000 */
  --nk-surface:          #0F151F; /* cards, panels, table rows */
  --nk-surface-elevated: #161F2E; /* dropdowns, drawers, inspectors, modals */

  /* Borders — hairline, not shadows (dark-on-dark shadows are invisible) */
  --nk-border-subtle:  rgba(255,255,255,0.08);   /* border-white/[0.08] */
  --nk-border-strong:  rgba(255,255,255,0.14);   /* border-white/[0.14] */

  /* Text */
  --nk-text-primary:   #E7EAEE;
  --nk-text-secondary: #98A2B3;
  --nk-text-tertiary:  #5D6673;

  /* Severity — the ONLY place color carries meaning (§1.3) */
  --nk-severity-low:      #10B981; /* emerald-500 */
  --nk-severity-medium:   #F59E0B; /* amber-500  */
  --nk-severity-high:     #F97316; /* orange-500 */
  --nk-severity-critical: #EF4444; /* red-500 (crimson) */

  /* Tactical glow (severity-tinted box-shadow, used sparingly on critical rows/nodes) */
  --nk-glow-critical: 0 0 12px rgba(239,68,68,0.25);
  --nk-glow-high:     0 0 12px rgba(249,115,22,0.20);
  --nk-glow-live:     0 0 10px rgba(16,185,129,0.20); /* "healthy"/streaming state, not severity */

  /* Single non-severity interactive accent (focus rings, links, active nav — never reused for severity) */
  --nk-accent: #38BDF8; /* sky-400 — distinct hue from all four severity colors */
}
```

Rationale for the accent choice: the research (Claude's report, §1) explicitly warns against reusing a severity hue for interactive/focus affordances — it collides with the Golden Color Rule (§1.3). Sky-blue is far enough from amber/orange/red/emerald to never be misread as a severity signal, and it's close to the existing `--nk-brand-primary: #38B6FF` the app already uses in its sidebar accent, minimizing brand disruption.

**Verdict/status/ladder colors are explicitly *not* given new hues** — per the Golden Color Rule below, they render via glyph + weight + position on the neutral surface palette, never their own color channel.

### 1.3 The Golden Color Rule (enforced, not just stated)

Color is reserved exclusively for **(a)** severity (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL` → emerald/amber/orange/crimson) and **(b)** live telemetry state (streaming=emerald glow, polling=amber, disconnected=neutral/red text — reusing severity red only for "disconnected," which is itself a severity-adjacent signal, not a competing channel).

Enforcement mechanism (not just a style-guide sentence): extend `shared/ui/Badge.tsx`'s existing pattern — it already never renders color-only (icon + label + color together, per its own doc comment, confirmed in the audit). Codify this as a lint-time-checkable rule of thumb during Phase 1: any new `Verdict`/`AlertStatus`/`LadderLevel`/`ActionType`/`Role` badge must render on the neutral surface tiers (`--nk-surface`/`--nk-surface-elevated`) with a glyph + font-weight distinction, and is **not permitted** to introduce a new named color token. `VerdictBadge`, `StatusBadge`, `LadderBadge`, `DeliveryStatusBadge` (all already exist) are audited in Phase 1 to confirm none of them currently borrow a severity hue for non-severity meaning — the audit found `CasesPage.tsx`'s hand-rolled status pills doing exactly this violation (`#7f1d1d`/`#fca5a5` for `fir_recommended`, i.e. a red very close to `--nk-severity-critical`) and Phase 4a fixes it by routing status through `StatusBadge` instead.

### 1.4 Offline Typography

- **New dependency:** `@fontsource-variable/jetbrains-mono` (OFL-1.1 license, self-hosts the variable woff2, zero runtime Google Fonts fetch — satisfies the 100%-offline requirement).
- Import once in `main.tsx`: `import "@fontsource-variable/jetbrains-mono";`
- Tailwind preset adds `fontFamily.mono = ['"JetBrains Mono Variable"', 'ui-monospace', 'monospace']` and keeps `fontFamily.sans` as the existing system-UI stack for chrome/labels — **sans for UI text, mono for data**, per the research's converged recommendation (§ research digest, "Typography" contradiction resolution: 3 of 4 reports land here once ChatGPT's self-contradicting citation is discounted).
- New utility class `.data-digit` (or Tailwind's built-in `tabular-nums` + a custom `slashed-zero` utility, since Tailwind core doesn't ship `slashed-zero` — add via `theme.extend` plugin or a two-line CSS rule `font-variant-numeric: tabular-nums slashed-zero;`) applied to **every** rendering of: timestamps (`formatSimTime`), rupee amounts (`formatInr` — already exists and is reused as-is, only the CSS treatment is new), countdown digits, alert/case/account IDs, and evaluation metric values.
- The System Integrity HUD (§2.4) gets the most aggressive application of this treatment, per the research's own framing (it's the one screen where every research report that touched typography singled this out).

### 1.4a Weight scale, density and HUD chrome (Linear + OSIRIS, second-pass additions)

- **Three-tier weight scale as tokens** (Claude's report §3.1, Linear): `--nk-weight-read: 400`, `--nk-weight-ui: 510`, `--nk-weight-strong: 590`; no heavier weights anywhere. The system-UI sans stack cannot render 510/590 reliably, so either bundle a variable sans via `@fontsource-variable/inter` (OFL-1.1, offline) for chrome text, or fall back to 400/500/600 on the system stack. **Decide at Phase 1 start** by looking at both on the real shell; default to the bundled Inter if there is any doubt (a wrong weight ladder is visible on every screen).
- **Density, not decoration:** secondary chrome (tab strips, panel headers, table column headers) is dimmed (`--nk-text-tertiary`) and compacted so working content carries the visual weight (Linear's own stated principle). Add a **comfortable / compact density toggle** for the triage queue (row height 64px / 48px; the virtualizer reads one constant, §2.1), remembered in `localStorage`.
- **Persistent HUD chrome** (OSIRIS's deployed UI; no new dependency), pinned in `Shell.tsx`'s topbar/footer:
  - **`SIM ⟨time⟩Z` clock** driven by `useSimTime()` (not wall-clock, §0).
  - Live **stream status** pill (streaming / polling / disconnected) reading the existing `useStream` state, styled with `--nk-glow-live` when streaming.
  - A small **"Press ? for shortcuts"** hint bottom-corner, opening a keyboard cheat-sheet overlay (`shared/ui/ShortcutSheet.tsx`) that lists the active scope's bindings. Because bindings are scoped (§2.1, §2.3), the sheet reads whichever `react-hotkeys-hook` scope is active instead of a hand-maintained list that would drift.
  - Map-only readouts (cursor lat/lon, zoom, layer/entity counters) are specified in §2.3.

### 1.5 shadcn/ui — scoping the decision

The task permits "Tailwind CSS + shadcn/ui (Radix primitives)." The existing `shared/ui/` library already wraps Radix directly (`@radix-ui/react-select`, `@radix-ui/react-tooltip`) with hand-written styling, has a working focus-trapped `Drawer`, and a documented "features import from the barrel only" convention. Wholesale-adopting shadcn's CLI generator would mean maintaining two parallel component systems.

**Decision:** do not migrate the existing library to shadcn. Use shadcn/Radix only for the **one new primitive the research unanimously converges on and that doesn't already exist**: a `Command` component (shared/ui/CommandPalette.tsx) built directly on `cmdk` (shadcn's own `<Command>` is itself just a styled wrapper over `cmdk` — building it in-house against the existing token system is equivalent work and keeps one design system, not two). Everything else (buttons, badges, tables, drawers) stays on the existing hand-rolled primitives, restyled against the new tokens.

---

## 2. Screen-by-Screen Redesign Specifications

### 2.1 Screen 1 — Triage Inbox & Operations Cockpit (`/alerts`)

**Backend contract this screen is built against** (`AlertSummaryModel`/`AlertDetailModel`, `apps/api/.../alerting/interfaces/alerts.py`):
```
severity: "LOW"|"MEDIUM"|"HIGH"|"CRITICAL"   // ordinal band names only — thresholds are policy-configured server-side, never hardcode a confidence cutoff client-side
status: "open"|"acknowledged"|"actioned"|"escalated"|"expired"|"closed"
ladder_level: "NONE"|"L1"|"L2"|"L3"
expires_at, window_start, window_end: ISO datetime   // the countdown ring's data source
allowed_actions: string[]                              // gates which action buttons render — server is the source of truth for permission, not client role logic
forecast.timing: { weights[], medians_min[], sigmas[], elapsed_min, residual_mass, p30, p60, p120 }
forecast.confidence, forecast.novelty
```
SSE events consumed: `alert.created`, `alert.updated` (via existing `useStream`/`streamKeys`), `sim.time` (drives the countdown clock), `:heartbeat` (already handled — 20s-no-event fallback to 5s polling already exists in `useStream.tsx`, unchanged).

**Layout:** two-pane — virtualized triage list (left, ~60%) + `AlertDetail` as an in-place panel rather than a full-width `Drawer` overlay when viewport ≥ 1280px (keeps the list visible during triage; falls back to today's overlay `Drawer` below that width). `ReviewQueue`'s existing one-at-a-time rapid-triage mode is preserved as an explicit toggle, not replaced — it already implements the uncertainty-first ordering (`view=review` query param, tie-broken by severity per the backend's documented ordering) that several research reports independently recommend building from scratch; here it already exists.

**Virtualization:** extend `shared/ui/DataTable.tsx` with an opt-in `virtualized?: boolean` prop backed by `@tanstack/react-virtual`'s `useVirtualizer`, fixed **64px row height** (per Gemini's spec, matched to the countdown ring's needs below). Enabled only for `AlertsInbox`'s live queue; other `DataTable` consumers (Outbox, Cases interim table) keep today's slice-based windowing until/unless they also need true windowing. Fix the dormant sort bug (§0) while this prop is added, since both touch the same `visible` memo.

New-alert insertion (avoiding scroll-jump on SSE bursts): a sticky "▲ N new critical alerts" pill appears above the viewport instead of prepending rows into an active scroll position; clicking it scrolls-to-top and reveals them. `contain: strict` on the list container isolates layout/paint.

**Single-RAF `TimeProvider` (new: `shared/time/TimeProvider.tsx`):**
```tsx
// One requestAnimationFrame loop for the whole app. Interpolates smoothly between
// sparse sim.time SSE ticks — NOT wall-clock time. Countdown, LadderDecisionPath,
// and TimeSlider all read from this instead of running their own timers/intervals.
type TimeCtx = { simTimeMs: number | null };
const TimeContext = createContext<TimeCtx>({ simTimeMs: null });

export function TimeProvider({ children }: { children: React.ReactNode }) {
  const simTimeIso = useSimTime(); // existing hook, SSE-driven, unchanged
  const anchorRef = useRef<{ simMs: number; wallMs: number } | null>(null);
  const [simTimeMs, setSimTimeMs] = useState<number | null>(null);

  useEffect(() => {
    if (!simTimeIso) return;
    anchorRef.current = { simMs: new Date(simTimeIso).getTime(), wallMs: performance.now() };
  }, [simTimeIso]);

  useEffect(() => {
    let raf: number;
    const tick = () => {
      if (anchorRef.current) {
        const elapsed = performance.now() - anchorRef.current.wallMs;
        setSimTimeMs(anchorRef.current.simMs + elapsed);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <TimeContext.Provider value={{ simTimeMs }}>{children}</TimeContext.Provider>;
}
export const useTactileTime = () => useContext(TimeContext);
```
This is Gemini's `TimeProvider` concept corrected per §0: it anchors to the last real `sim.time` SSE tick and interpolates forward via RAF between ticks (sim clock can run faster/slower than wall clock in the simulator — interpolation must scale by whatever rate the last two ticks imply, refined during implementation once actual tick cadence is measured; a fixed 1:1 fallback is acceptable if the simulator always ticks at real-time rate, to confirm during Phase 2 build).

**Countdown ring** (`shared/ui/CountdownRing.tsx`, new — replaces ad-hoc text `Countdown` inside table rows only; `Countdown.tsx` itself stays for non-ring contexts like `AlertDetail`'s metrics row):
- Reads `useTactileTime()` + the alert's `expires_at`/`window_end`, computes `pct` remaining.
- SVG `viewBox="0 0 36 36"`, `r=14`, `circumference = 2πr`, `-rotate-90` start-at-12-o'clock, `stroke-linecap="round"`, track ring `stroke="var(--nk-border-subtle)"`.
- Color bands: `pct > 50` → `--nk-severity-low`, `pct > 20` → `--nk-severity-medium`, else `--nk-severity-critical`, with a `transition-[stroke-dashoffset] duration-75 ease-linear` for smoothing between RAF ticks.
- Wires up the already-defined-but-orphaned `.nk-countdown--urgent` blink CSS (§0 audit finding) as the `pct ≤ 20` state — a real bug fix folded into new work, not a separate task.
- Fixed 64px×64px footprint to match the virtualized row height exactly (no layout shift as it animates).

**Scoped keyboard navigation** (new dependency: `react-hotkeys-hook`):
- Scope `"triage-inbox"`, active only while `AlertsInbox` is mounted/focused (prevents leakage into `/map` or `/cases` per the research's explicit warning about this).
- `j`/`k` — move selection down/up the virtualized list (scrolls the virtualizer to the selected index).
- `f` — freeze (opens/confirms the `request_hold` hold-to-actuate control, §2.1 below) — **only if `"request_hold"` is present in the selected alert's `allowed_actions`**, otherwise no-op (server permission is authoritative, per §0).
- `d` — dispatch (same gating against `allowed_actions` for `"dispatch"`).
- `x` / `Escape` — close the detail pane (there is no dismiss action in the backend, so this only closes the view).
- `Space` — quick-peek (opens the in-place detail panel without navigating away from the list).
- `enableOnFormTags: false` so these never fire while the search/filter inputs have focus (Gemini's specific config finding).

**Offline auditory cue** (new: `shared/audio/tacticalPing.ts`, adapted from Gemini's oscillator recipe, corrected for the app's actual severity taxonomy which is 4 bands not 3):
```ts
export function playTacticalPing(severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW") {
  try {
    const ctx = new (window.AudioContext ?? (window as any).webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    const freq = { CRITICAL: 880, HIGH: 659.25, MEDIUM: 587.33, LOW: 440 }[severity];
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    if (severity === "CRITICAL") osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
    osc.start(); osc.stop(ctx.currentTime + 0.15);
  } catch { /* AudioContext blocked by autoplay policy — silently degrade, no error UI */ }
}
```
Triggered from `useStream.tsx`'s existing `alert.created` handler, gated to `severity === "CRITICAL"` only (avoid ping fatigue), and behind a user-toggleable "Sound" preference stored in `localStorage` (not sessionStorage, since it's a genuine per-device setting the user should not have to re-set every tab).

**Hold-to-actuate for consequential actions** (new: `shared/ui/HoldToActuateButton.tsx`; no new dependency, plain CSS + RAF):
- Applied to `request_hold` (fund freeze / lien proposal, ties into `ProportionalityModel`'s `disputed_paise`/`proposed_paise`) and `dispatch` — the two action types the research and the task brief both single out as "irreversible-feeling."
- `acknowledge`, `notify_station`, and `OutcomeButtons` (hit/miss/late) stay simple click buttons with a `toast.promise()`-driven success/error toast (see below) — hold-to-actuate on every action would dull the signal (research explicitly warns against this: friction should be reserved for genuinely consequential actions).
- `override` is a **reconsidered case, not bucketed with the other plain buttons**: an officer overriding the platform's automated recommendation is arguably the single most consequential action type in the system — it's a human deliberately superseding the model. It doesn't get the hold gesture (the research's hold-to-actuate pattern is specifically framed around funds-freeze/dispatch physical urgency, not deliberation), but per Claude's own tiering (its finding 5.3: a non-dismissible toast — `dismissible: false` — reserved for actions where premature dismissal would cause confusion), the click still fires the mutation optimistically like `acknowledge`/`notify_station`, but the resulting toast is **non-dismissible** (no auto-timeout, must be explicitly clicked closed) rather than the plain auto-dismissing success toast the softer actions get — forcing the officer to consciously register "an override was recorded" rather than letting it scroll past unread.
- **600ms** hold duration (task-specified; note Gemini's own code used 650ms against its stated 600ms — we use exactly 600ms per the task brief, no ambiguity).
- Mechanic: `pointerdown`/`f`-or-`d`-keydown starts a RAF loop computing `pct = min(100, (performance.now() - start) / 600 * 100)`, painted as an inset `<span>` fill (`width: ${pct}%`); release before 100% cancels instantly (RAF cancelled, fill resets — no fake "recoil" animation, matching what Gemini's actual code does rather than its more elaborate prose).
- On reaching 100%: fires the TanStack Query mutation and a **`sonner`** `toast.promise` — reaching 100% is the actuation, and the hold gesture itself is the confirmation (no second dialog). **Correction (found while implementing Phase 2, verified in `alerting/application/record_action.py`): there is no undo.** A `request_hold`/`dispatch` moves the alert to `actioned`, and `actioned` is not in `ACTIONABLE_STATUSES`, so any follow-up action (including `override`) is rejected with `INVALID_TRANSITION` (409); an `override` also would not release a lien even if it were accepted, because it enqueues no delivery. The bank already received the hold request. The original draft's 5-second UNDO toast would have told the operator a freeze was reversed when it was not, so it is **not built**. A hold is released only by the bank/timer path (`released` callback, or the lien's `expires_at`).

**Consequence toast + optimistic cache** (new dependency: `sonner`, replaces the currently-unused `react-hot-toast` `<Toaster/>` mount — one-line swap, zero call-site migration per §0):
- `useMutation`'s `onMutate`: `queryClient.cancelQueries(streamKeys.alerts())`, snapshot previous cache, optimistically patch the alert's `status`, return the snapshot as mutation context.
- **`acknowledge`/`notify_station`/outcomes use `toast.promise(mutation, { loading, success, error })`** (Claude's specific finding 5.2/5.4 — one call that auto-transitions loading→success/error tied to the real mutation, rather than manually calling `.success()`/`.error()` in separate `onSuccess`/`onError` callbacks) — the single-call form is what's actually idiomatic here and is what the plan now specifies, correcting the earlier draft's more generic phrasing.
- For `request_hold`/`dispatch`: the success toast states what is actually true and no more — "Hold requested — waiting for the bank to confirm (₹X)" (the action is `pending` until the bank's callback makes it `applied`/`rejected`). No UNDO button. The consequence tally (below) shows the hold as pending and reconciles when the bank answers.
- `override` gets its own non-dismissible variant per the bullet above, not the plain `toast.promise()` treatment.
- On error (any action): roll back the optimistic cache patch to the snapshot; `toast.promise()`'s own error branch surfaces this without a separate manual call.

**Consequence tally (second-pass addition, Claude report §5.2/5.4 — "stat counters increment immediately and roll back on failure"):** a compact **"Held ₹X · N actions"** readout in the Triage header (`shared/ui/ConsequenceTally.tsx`, rendered with `RollingCounter`, §3 Phase 2, moved up from the original Phase 5).
- On `request_hold` reaching 100%, the tally ticks up immediately by the alert's `proposed_paise` (optimistic), `N` by 1.
- When the bank callback lands, the amount reconciles to the real `applied_amount_paise` (the number may go *down* if the bank applied less — show it truthfully, never round back up); on mutation error it rolls back with the snapshot.
- It is session-scoped derived state fed by the mutation lifecycle, not a new endpoint. It is the piece that makes a freeze feel "immediate and tangible" in a demo, so it lives next to the action, not on a distant dashboard.

**Additional queue interactions (all frontend-only):**
- `1`–`9` jump-select the Nth visible row (Claude report §1.1), in the same `triage-inbox` scope as `j`/`k`. `Escape` closes the in-place detail panel and returns focus to the row.
- **Row exit transition:** when an alert becomes `actioned`/`expired`/`closed` and leaves the visible filter, fade the row out over ~150ms (CSS opacity/`grid-template-rows`, or `view-transition-name` where supported) before the virtualizer drops it, so the list doesn't jump. Arrivals are already handled by the "▲ N new" pill; this covers departures. Low priority within Phase 2 — cut first if time is short.
- **Hotkey hints on the controls:** each hotkey-bound button renders a small `<kbd>` chip (`F`, `D`, `X`) so the shortcut is visible in the demo without opening the cheat-sheet.

### 2.2 Screen 2 — Forensic Dossier & Mule Cascade (`/cases`)

**Backend contract:**
```
ClusterModel: { cluster_ref, size, status, novelty, nodes: ClusterNodeModel[], edges: ClusterEdgeModel[] }
ClusterNodeModel: { id, kind, masked_ref, bank }              // NOTE: no ifsc field — see §0
ClusterEdgeModel: { from, to, amount_paise, layer, event_at }  // "layer" is the hop depth — already the LR-ordering key
CaseModel: { ..., total_paise, accounts: AccountRefModel[], top_locations, sub_communities: string[][], brief_md, ... }
EvidencePackModel: { ..., sha256, audit_head_hash, download_url }  // download_url serves a raw PDF, not JSON
```

**Rewrite CasesPage.tsx and CaseDetail.tsx onto the design system.** Per §0, these two files are ~90% inline `style={{}}` with a hardcoded dark-slate palette (`#0f172a`/`#1e293b`/`#334155`/`#f8fafc`) that is disconnected from the rest of the (currently light, post-overhaul near-black) app — the single biggest visual-consistency gap in the codebase. Rewrite onto `Panel` (already exists, exactly the header/body/footer card the hand-rolled divs are reinventing), `DataTable` (replacing the native `<table>`, restoring sorting/keyboard-row-activation/empty-state for free), and `StatusBadge` (replacing the hand-rolled status pills that currently collide with the severity-red hue, per §1.3). `SafeBriefRenderer`'s markdown-ish hand-parsing of `brief_md` is preserved as-is (it's a legitimate mini-parser, not a design problem) but re-themed onto tokens instead of inline hex.

**Multi-hop graph — migrate `ClusterGraph.tsx`:**
- New dependencies: `react-cytoscapejs` (official Plotly React binding — the research's 3-of-4 convergence pick over the wrapper the fourth report cited), `cytoscape-dagre` + its peer dep `dagre`, `cytoscape-expand-collapse` (i-Vis/Bilkent, MIT, the strongest single cross-report agreement in the whole research digest).
- Replace the current hand-computed `preset` layout with `cytoscape-dagre`: `{ name: "dagre", rankDir: "LR", nodeSep: 50, rankSep: 100, animate: false }`, ranking directly off `ClusterEdgeModel.layer` (already the exact hop-depth field dagre needs — no data transform required, just stop hand-computing x/y and let dagre consume `layer` as its rank source via a thin adapter that seeds dagre's rank hint from `layer`).
- **Cyclic mule rings — a real risk with dagre, not just a nice-to-have alternative.** Dagre is fundamentally a DAG-layout algorithm (Claude's report flags this class of layout as one option among several, not a universal fit); a genuine laundering *ring* — money cycling back through an earlier account, which the product's own domain concept of a "cluster" explicitly allows for — will contain a cycle in `ClusterEdgeModel.from`/`to`, which dagre's internal cycle-breaking heuristic will silently resolve by reversing an edge's rank direction, producing a layout that no longer reads as "money flows left-to-right" for that ring. Detect cycles client-side (a cheap DFS over `cappedEdges`, done once alongside the existing `nodeColumn` pass) and fall back to **`cose-bilkent`** (i-Vis/Bilkent, MIT — explicitly named in Claude's report as "a safe fallback... widely used" when `cytoscape-cola`'s license/stability can't be confirmed, which applies equally well here as the fallback for non-hierarchical/cyclic graph shapes) instead of forcing dagre on data it isn't suited for.
- Preserve the existing 200-node cap + synthetic "+N more accounts" summary node logic verbatim for now — it already does what the research (Claude's hop-limiting finding) recommends building from scratch elsewhere. Note the one respect in which it falls short of Claude's fuller recommendation: the cap is applied entirely **client-side**, after the full node/edge payload for the cluster has already been fetched — for a cluster far larger than 200 nodes, that means transferring and discarding most of the payload before the cap even runs. Claude's report specifically recommends the pruning happen server-side with pruning metadata returned alongside the (already-capped) nodes/edges. Flagged as an additive backend option in §5.3 rather than required here, since it isn't a correctness bug — just a payload-size inefficiency on very large clusters.
- Edge width mapped continuously to `amount_paise`: `'width': 'mapData(amount_paise, 0, maxAmountInThisGraph, 1.5, 8)'` (compute `maxAmountInThisGraph` client-side per render, since the backend gives raw paise with no fixed scale).
- Add `cytoscape-expand-collapse`: compound-collapse nodes sharing the same `bank` field (the real field available, in place of the research's IFSC-based grouping example which doesn't apply here per §0) into a single node labeled e.g. `"HDFC — 14 accounts"`, with the aggregate edge weight summed. Secondary, user-toggleable grouping by `sub_communities` membership (the backend already computes these community clusters — no client-side graph-community-detection needed).
- Node styling stays kind-based (victim/mule/aggregator/exit + summary — the existing scheme), re-themed onto the new severity-free neutral palette with a `--nk-accent`-tinted border for the currently-selected node, and a `--nk-glow-critical` box-shadow-equivalent (Cytoscape `border-width`+`border-color` pulse, since Cytoscape styles don't consume CSS `box-shadow`) reserved for nodes flagged on an active alert.
- Keep the graph canvas on its own deliberate dark micro-theme (`--nk-canvas-bg`) — this is now consistent with the rest of the app by construction, since the whole app is moving to a near-black palette (§1.2), removing what was previously a Cases-vs-rest-of-app inconsistency without the graph itself needing to change its visual language.
- **Click-to-isolate-ring focus mode** (new, no dependency — plain Cytoscape API): a toolbar toggle that, on selecting a node, dims (not hides) every node/edge not in that node's connected component via `cy.elements().difference(selected.closedNeighborhood()).style('opacity', 0.15)`, with a one-click "Show all" to pop back to the full graph. This is a distinct interaction from the `cytoscape-expand-collapse` grouping above — expand-collapse *merges* nodes into a summary, isolate-ring *dims everything else* while keeping the full graph in the DOM and one click away — and is the concrete mechanism behind an investigator focusing on one mule ring without losing surrounding context, which the current `ClusterGraph.tsx` has no equivalent for today (only a node/edge inspector panel, no isolate/dim affordance).
- **On the backend-vs-frontend graph-shaping question:** the current architecture has `ClusterGraph.tsx` transform raw `ClusterNodeModel[]`/`ClusterEdgeModel[]` into Cytoscape's `{group, data}` element format itself (visible today at the `cyNodes`/`cyEdges` `.map()` calls). Claude's report recommends the backend return pre-shaped Cytoscape elements directly instead, to keep the rendering layer "dumb." That specific recommendation can't be adopted literally without changing `/clusters/{cluster_id}`'s response shape, which the task forbids touching. The practical middle ground: keep the transform, but isolate it into one small, exported, unit-tested pure function (`toCytoscapeElements(cluster: ClusterModel): ElementDefinition[]`) rather than inlining it in the component — this achieves the same "dumb, fast rendering layer" goal the recommendation is actually after, without an API change. A genuinely pre-shaped backend endpoint is listed as an optional future addition in §5.3.

**Fix the node-kind classification bug (§0 — the "every node is the same gray circle" defect):** `ClusterGraph.tsx`'s existing kind-based Cytoscape selectors (victim=sky ellipse, mule=amber rounded-rect, aggregator=red diamond, exit=purple hexagon) never fire today because the backend hardcodes `kind="account"` for every node — verified at `apps/api/src/nakabandi/casework/__init__.py:106-131`. There is no real per-account role data anywhere in the backend to classify against (confirmed: `AccountFact`/`ClusterNode` domain entities carry no role field; the closest raw signals — `ComplaintFact.touched_account_ids` and `CashOutFact.account_id` — are each consumed for a different purpose upstream and never persisted per-account or exposed on this endpoint). Two-tier fix, mirroring the evaluation-metrics gap in §5 (ship an honest frontend fix now, flag an optional backend enhancement for later):

- **Frontend now, no backend dependency (required, Phase 4a):** replace the dead `kind`-based selectors with a `role` computed client-side from the *topology already being fetched* — the same edge list already walked once per render for `nodeColumn`/`edgeSpeed` (§2.2 above), so this is one more cheap pass over `cappedEdges`, not a new data dependency:
  - in-degree 0, out-degree > 0 → **`origin`** (the node money is first traced flowing out of — reuses the existing sky-blue ellipse style)
  - out-degree 0, in-degree > 0 → **`terminal`** (the last traced hop before the trail ends — reuses the existing purple hexagon style)
  - in-degree ≥ 3 (configurable threshold, tune against real seeded cluster sizes during implementation) → **`pooling`** (a funnel point many accounts feed into — reuses the existing red diamond style)
  - has both incoming and outgoing edges, in-degree < 3 → **`pass-through`** (reuses the existing amber rounded-rectangle "mule" style)
  - in-degree 0 AND out-degree 0 (an isolated singleton account with no traced hops to/from it — an edge case the current code doesn't explicitly style at all) → falls to the plain default gray circle, which is now the *correct*, honest rendering for "no relational data," not a bug
  - The legend (already present at the bottom-left of the canvas) is relabeled to match: "Origin (no inbound hops)" / "Pass-through" / "Pooling point (≥3 inbound)" / "Terminal (no outbound hops)" — deliberately **not** relabeled "Victim"/"Mule"/"Aggregator"/"Exit ATM," because those are semantic claims this data cannot actually support (a topological origin node is not necessarily the fraud victim — it is only the earliest point the trace happens to start from within the currently-fetched, possibly-200-node-capped subgraph). Overclaiming certainty here in a forensic tool is worse than an honest topological label.
  - This computation piggybacks on the same `nodeColumn`/`edgeSpeed` `useMemo` (or a sibling one keyed the same way) so it doesn't add a second full pass over `cappedEdges`.
- **Optional backend follow-up (not required to ship Phase 4a, tracked alongside §5):** if genuine ground-truth roles are wanted instead of a topological proxy, `casework/__init__.py`'s `cluster_graph()` would need to (a) mark the account(s) named in the originating `ComplaintFact.touched_account_ids` as `kind="victim"`, and (b) persist `CashOutFact.account_id` observations in a queryable per-account form (today `apply_cashouts.py` writes only into aggregate `cluster_location_stats`, confirmed by reading the use case) so they can be joined and emitted as `kind="cashout"`. This is a larger lift than the eval-metrics fix in §5 — it needs a new persisted fact, not just wiring an already-existing pure function — so it's flagged as a genuine enhancement ticket, not a blocking prerequisite.

**Paired Sankey view:** new `CaseFundFlowSankey.tsx` using **Recharts' `<Sankey>`** (already in the permitted stack and already a project dependency — no new package). Data is derived client-side from the same `ClusterModel.edges`/`nodes` already fetched for the graph (aggregate `amount_paise` by destination `bank`) — no new backend endpoint needed. Rendered as a tab alongside the Cytoscape view, not a replacement for it.

**Temporal playback:** a slider scrubbing `ClusterEdgeModel.event_at` timestamps, filtering which edges are drawn/highlighted at a given point in the case timeline, driven by the same `useTactileTime`-style RAF discipline (though here it's investigator-scrubbed time, not sim time — a local `useState` position is fine, no `TimeProvider` dependency). No OSS reference exists for this (confirmed by 3 of 4 research reports) — implemented via Cytoscape's own `cy.style().selector(...).update()` API against edge opacity, not a new library.

**Graph noise controls (second-pass addition, Claude report §2.4 `crypto-tracer` pattern):** the fixed 200-node cap plus "+N more" node gives the investigator no control. Add a small toolbar, all computed client-side from fields already in `ClusterEdgeModel`:
- **Hop-depth limiter** — a 1…max slider over `layer`; edges/nodes deeper than N are hidden.
- **Minimum-amount slider** — hides edges under a threshold of `amount_paise` (the "micro-dust" edges laundering networks inject to bloat visual tools); its default is the smallest value that still keeps the graph connected, not a magic constant.
- **"N edges hidden · show all"** affordance whenever either filter (or the 200-node cap) is hiding something, with the hidden count and hidden `₹` sum. Never hide silently: in a forensic view an unlabeled omission reads as absence of evidence.
- These are the client-side version of what §5.3's `max_hops`/`hidden_*` additions would compute exactly server-side at scale.

**Entity inspector panel (second-pass addition, Claude report §2.4 `fraud-graph` pattern):** replace the bare node/edge inspector with a panel on node select, all derived from the edges already fetched:
- masked ref, bank, and the topological role badge from the classification fix above (with the honest label, not "victim"/"mule");
- in-degree / out-degree, total inbound and outbound `₹` (`formatInr`), first and last edge `event_at`;
- **connection chain:** the shortest hop path from an origin node to this node, click-to-highlight on the canvas;
- "Isolate ring" button (the dim/focus mode above) lives here as well as in the toolbar.
- No risk *score* is shown, because no per-account score exists in the data (§0 policy on overclaiming); a dossier-level `novelty` value from `ClusterModel` may be shown as context only.

**Working-copy export (second-pass addition, lowest priority in this screen):** "Export view" for the current filtered graph as PNG (`cy.png()`) and its visible edges as CSV. Both are labelled **"Working copy — not the evidence pack"** in the file name and UI, because the server-generated `EvidencePackModel` PDF is the only sha256/audit-anchored artifact (DOC1 §1.5 wording rules apply to any caption). Node annotations are deliberately **not** in this plan (they need a persisted, audited, `Principal`-gated backend feature; see §5.4).

### 2.3 Screen 3 — Tactical GIS Map (`/map`)

**No new mapping dependency** — `maplibre-gl` is already installed and the current `MapLibreAdapter.ts` is a genuinely sophisticated implementation (native heatmap layer, boundary/bank/alert layers, a hand-rolled marching-dashes interception-radar line animation, offline bundled boundary GeoJSON, graceful WebGL-unsupported fallback). This screen is additive, not a rewrite.

**Backend contract feeding this screen:**
```
HeatmapResponse: { layer, level, generated_at, version, cells: HeatCellView[], suppressed_count, legend }
HeatCellView: { id, kind, name, lat, lon, value, alert_count }
LiveMetricsResponse: { generated_at, version, window_hours, alert_count, expected_mass, active_locations }
```
SSE `heat.version` (already consumed, debounced 1s invalidation of the heatmap query — unchanged) carries the same `version` number as `HeatmapResponse.version`, confirming cache freshness without a payload diff.

**Pulsating threat radar (new: `features/map/layers/radarIconLayer.ts`):** implements MapLibre's `StyleImageInterface` (Gemini's approach, the only research report with working code, and the more visually distinctive of the two candidate techniques) — an offscreen canvas `render()` draws an expanding, fading outer ring (`rgba(239,68,68,${1-t})`, `t = (performance.now() % 1500) / 1500`) plus a solid inner dot, calls `map.triggerRepaint()` each frame, registered via `map.addImage(id, styleImage)` and consumed by a `symbol` layer (`icon-image: "pulsing-radar"`). **Capped to the top 1–3 highest-`value` `HeatCellView` entries only** (per Claude's performance caution — MapLibre's own maintainers warn against many simultaneously-animating custom-canvas icons); every other elevated cell renders as a static circle with a MapLibre `circle-radius` paint-property *transition* (cheap, GPU-native, no per-frame JS) instead of a second animating icon. This directly resolves the research's Gemini-vs-ChatGPT contradiction on radar technique by using the heavier technique only where it earns its cost.

**Open scope question, not resolved by this plan (Claude's finding 4.4):** the pulsating radar in this phase visualizes *where* a heat cell is, not *how far a mule could physically have travelled by cash-out time* — a true drive-time isochrone ring is a materially different (and more accurate) shape than a simple radius circle, but no client-only isochrone library exists; it would require a self-hosted routing engine (OSRM/Valhalla) against an offline OSM extract, which is an infrastructure decision, not a frontend library choice. This plan does not build either a radius circle or an isochrone for "how far could they have gone" — it only ships the radar *marker* (§ above). Note `InterceptAssessmentModel.best_unit.eta_min` already gives a real, backend-computed ETA for one specific responding unit, which may make a general-purpose isochrone overlay redundant for the interception-feasibility use case specifically — worth a product decision before anyone builds either a Turf.js radius circle or an OSRM isochrone, rather than defaulting to one silently.

**Linked selection:** a small shared selection store (`shared/state/selectionStore.ts`, a plain Zustand-free `useSyncExternalStore`-based module — no new state library needed for one shared "selected entity" value) that `MapPage`, `CaseDetail`'s graph, and `AlertsInbox` all read/write. Clicking a cluster node or an alert row sets `{ kind: "location" | "alert" | "account", id }`; `MapPage` observes it and calls `map.flyTo()`/highlights the matching layer feature. This is the concrete mechanism behind the task's "linked selection" requirement — implemented as a shared primitive under `shared/` (satisfying the `eslint-plugin-boundaries` rule that cross-feature reuse must go through `shared/*`), not a direct `features/map` → `features/cases` import.

**Toggleable layers with live counts (OSIRIS pattern, second-pass addition):** a compact layer panel (`features/map/LayerPanel.tsx`) over the map, one row per existing layer, each with an on/off switch, a hotkey `<kbd>` chip and a live count badge:

| Layer | Hotkey | Count shown | Backing layer id(s) |
|---|---|---|---|
| Risk heat (density + points) | `H` | visible `cells.length` (plus `suppressed_count` as a muted "+N suppressed") | `HEATMAP_LAYER_ID` and its point layer |
| Locations | `L` | `locations.length` | `LOCATIONS_CIRCLE_LAYER_ID` |
| Active alerts | `A` | `alerts.length` | `ALERTS_POINT_LAYER_ID` |
| Interception route | `I` | 1 / 0 (a route is shown or not) | `RADAR_LINE_LAYER_ID` |
| Boundaries | `B` | — | `BOUNDARIES_FILL_LAYER_ID` |

- Toggling calls the existing `MapAdapter.setLayerVisibility(layerId, visible)`; no adapter work beyond confirming a multi-id layer (heat density + points) toggles as one unit. Counts come from data the page already holds, so there is no new fetch.
- The **top-1–3 animated radar markers** (above) are governed by the Alerts/Heat toggles, not a separate switch, so turning a layer off also stops its `triggerRepaint()` loop.
- Persist toggle state in `localStorage` (per-viewer convenience, wrapped in try/catch).
- **Map hotkeys** are a separate `"map"` scope in `react-hotkeys-hook` (single letters above; `Escape` closes `HotspotDrawer`). `MapPage` is only mounted on `/map`, so these can never collide with the `triage-inbox` bindings that mean something else by `f`/`d`.

**Map HUD readouts (OSIRIS pattern, second-pass addition; no dependency):** a bottom strip over the canvas showing **cursor lat/lon** (updates on `mousemove`), **zoom level** as a number, and **"N layers · N entities"** totals. Implementation note: write cursor coordinates straight into a ref'd DOM node from the map's `mousemove` handler, not into React state, or every mouse move re-renders `MapPage`. This needs one small addition to the `MapAdapter` interface (`onPointerMove(cb)`, `onViewChange(cb)`) alongside its MapLibre implementation; it is an internal front-end interface, not an API contract.

### 2.4 Screen 4 — System Trust & Integrity HUD (`/system`)

Scoped strictly to what real data exists (§0) — this is the screen most affected by the evaluation-API gap.

**Data sources, all real and live today:**
```
GET /system/metrics  → MetricsResponse { uptime_s, events_per_second, stages: {[name]: LatencyView}, http: LatencyView, outbox, delivery_failures, streams }
                        (SIM_CONTROL permission — demo_operator/admin only; page must gracefully hide this section for other roles, matching existing RoleGuard usage)
GET /audit/verify    → VerifyResponse { ok, first_bad_seq, head_hash }   // the SHA-256 hash-chain integrity check — a strong, authentic "Trust HUD" signal
GET /analytics/live-metrics → LiveMetricsResponse { alert_count, expected_mass, active_locations, window_hours }
GET /eval-results.json (static file, scripts/evaluate.py output) → { metrics: { hit_rate_at_{1,3,5}, precision_at_{1,3,5}, brier_score } }
```

**Landmine fix (required, not optional):** fetch `eval-results.json` as `text()`, not `.json()`; sanitize bare `NaN` tokens (`text.replace(/:\s*NaN\b/g, ": null")`) before `JSON.parse`. Every metric field becomes `{ value: number | null, n: number }` client-side; render `null` values as an explicit "insufficient sample (n<30)" state, never as `0` or a blank chart point.

**What ships in this plan:**
- `hit_rate@{1,3,5}` and `precision@{1,3,5}` as donut/ring gauges (reusing the existing `ProgressRing` SVG component already in `EvaluationPage.tsx` — restyle, don't rebuild) — real data, real feature.
- `brier_score` as a single labeled stat tile with a trend arrow (comparing this run's `generated_at` against the previous fetched run cached in `localStorage` — a rolling "last N runs" client-side history, since the backend keeps no run history itself) — **not** a reliability/calibration curve (that data doesn't exist — see §5).
- Latency: `MetricsResponse.stages`/`http` `LatencyView { p50_ms, p95_ms, max_ms }` rendered as sparklines built from a **client-side rolling buffer** (poll `/system/metrics` every 10s while the page is open, keep the last ~30 samples in component state) — genuinely "real-time" in the sense of live-polled, but explicitly not a backend-provided time series, since none exists.
- Audit chain integrity: a prominent `VerifyResponse.ok` indicator (green check / red break glyph, `first_bad_seq` shown if broken) — this maps directly onto the platform's actual headline "SHA-256 audit hash chain" capability mentioned in the product brief and was previously not surfaced in any screen at all; a genuinely new, authentic addition rather than a cosmetic one.
- `LiveMetricsResponse.expected_mass`/`active_locations` as supporting exposure tiles.

Aggressive JetBrains Mono + `tabular-nums slashed-zero` treatment throughout, per §1.4 — every research report that addressed this screen singled it out for the heaviest numeric-typography treatment.

### 2.5 Global — Command Palette (`Cmd+K`)

New dependency: `cmdk` (MIT, the unanimous pick over `kbar` per the research — shares Radix primitives with the rest of the stack). Built as `shared/ui/CommandPalette.tsx` (§1.5) and mounted once in `Shell.tsx`, replacing the currently-decorative, non-functional topbar search input (confirmed in the audit to have no `onChange` handler at all today — this is a real gap being filled, not a duplicate feature).

Indexes, in-memory, fuzzy-matched via `cmdk`'s built-in `command-score`:
- Open alerts (by masked target ref / cluster ref / id)
- Cases (by `cluster_ref` / case id)
- **Bank codes and masked account references** (corrected scope per §0 — not IFSC, which doesn't exist in this data model)
- Static navigation targets (Triage, Deployment, Investigate, System Integrity, Demo)

**Context-aware commands (second-pass addition, Claude report §1, kbar scoped-action model + "jump to evidence item N"):** the palette also shows a **contextual group** that depends on the current route and `selectionStore` value, so it is more than a search box:
- With an alert selected: *Freeze selected alert*, *Dispatch*, *Open its cluster*, *Show on map* — each listed **only if** the alert's `allowed_actions` includes it (server permission stays authoritative, §4). Destructive ones (freeze/dispatch) route through the same `HoldToActuateButton` confirmation, never a one-keystroke fire from the palette.
- In a case dossier: *Jump to hop N*, *Jump to evidence item N*, *Isolate ring around selected node*, *Export view (working copy)*.
- Anywhere: *Toggle sound*, *Toggle compact density*, *Show shortcuts*.

`react-hotkeys-hook` binds the global `Cmd+K`/`Ctrl+K` open shortcut at the `Shell` level (outside any feature scope, so it's always available), separate from the `triage-inbox`-scoped bindings in §2.1 — exactly the two-library division of labor (`cmdk` for palette UI/filtering, `react-hotkeys-hook` for the shortcut key itself and all row-level bindings) that the research's two most detailed reports both converge on.

---

## 3. Step-by-Step Implementation Phases

Every phase's verification baseline is `npm run ci:web` (root `package.json`: lint + typecheck + test + build for `apps/web`), run from the repo root. Phase-specific additional checks are listed per phase.

### 3.0 Ordering by demo visibility

Phases are ordered by how much of a live demo they change, subject to hard dependencies. Each phase ends in a **demo-ready state**: if time runs out after any phase, everything up to it is coherent and presentable, and nothing later is half-wired.

| Order | Phase | What the audience sees | Why here |
|---|---|---|---|
| 1 | **Foundation & Reskin** | The whole app flips to the near-black tactical look, with a live `SIM …Z` clock, stream status and monospaced tabular numbers on every screen | Every later screen is styled against these tokens, and it is the only phase that changes *every* screen at once. Also unblocks Tailwind, which is currently not wired at all (§0) |
| 2 | **Triage Cockpit + live KPIs** | Countdown rings ticking, a CRITICAL ping, hold-to-freeze with a fill, a "Held ₹X" tally that jumps the instant you act, Dashboard numbers that roll instead of snap | The demo's core story ("alert arrives → officer acts in seconds") and the most animated screen |
| 3 | **Command Palette + Tactical Map** | `Cmd+K` jumps to anything; the map gains toggleable layers with live counts, single-key hotkeys, cursor/zoom HUD and a pulsing radar on the hottest cell | Palette is cheap, flashy and cross-screen; the map is the second thing any audience looks at. Mostly additive to a strong existing map, so low risk |
| 4a | **Case Dossier quick wins** | The mule graph stops rendering as uniform gray circles (real role shapes and legend), and Cases/CaseDetail match the new theme | The single most visibly *broken* thing today (§0 node-kind defect), fixable in the existing component in about a day, without waiting for the library migration |
| 4b | **Case Dossier forensic depth** | Left-to-right dagre cascade, bank grouping, hop/amount filters with "N hidden", entity inspector, isolate-ring, Sankey, timeline playback | The largest and riskiest work (three new graph packages, layout swap), so it goes after everything cheaper has landed |
| 5 | **System Integrity HUD + consistency pass** | Live audit-chain verification, latency sparklines, eval gauges; every mutation on every screen behaves consistently | Real value, but the least "wow per hour" and the most data plumbing (NaN landmine, rolling buffers). Runs last, so a slip here costs the demo the least |

**Cut order if time is short** (cut from the tail, never from the middle of a screen; this is the frontend-overhaul cut order only and does not replace DOC4 §4.1c, which still governs any descope of the main build): Phase 5's sparklines → 4b's Sankey and export → 4b's timeline playback → 2's row-exit transition → 3's HUD readouts. Never cut Phase 1, the Phase 2 hold-to-actuate + tally, or the 4a role fix.

### Phase 1 — Foundation, Reskin & HUD Chrome

**Target files:**
- New: `apps/web/tailwind.config.ts` (content globs `["./index.html", "./src/**/*.{ts,tsx}"]`, `presets: [nkPreset]`)
- New: `apps/web/postcss.config.js` (`tailwindcss`, `autoprefixer`)
- Modify: `apps/web/src/shared/tokens/tailwind.preset.ts` — expand to the full token set in §1.2 (colors, glows, `fontFamily.mono`, weight tokens from §1.4a)
- Modify: `apps/web/src/shared/tokens/tokens.css` — cut down to `:root` variables only (§1.2 values); everything else either deleted (confirmed orphaned classes, §0) or migrated in later phases
- New: a root stylesheet with `@tailwind base; @tailwind components; @tailwind utilities;` (e.g. `apps/web/src/shared/tokens/tailwind.css`), imported in `main.tsx` alongside the existing `tokens.css`/`neo-utils.css` imports
- Modify: `apps/web/src/main.tsx` — add `@fontsource-variable/jetbrains-mono` (and, if chosen per §1.4a, `@fontsource-variable/inter`) import, add the new Tailwind stylesheet import
- Modify: `apps/web/src/app/layout/Shell.tsx` — restyle onto new tokens; remove the decorative search input (the Command Palette trigger arrives in Phase 3); **add HUD chrome (§1.4a): `SIM ⟨time⟩Z` clock, stream-status pill, "Press ? for shortcuts" hint**
- New: `apps/web/src/shared/ui/ShortcutSheet.tsx` — renders empty-but-wired now (`?` opens it), filled by each later phase's scope
- Modify: `apps/web/src/shared/ui/*.tsx` — restyle `Button`, `Badge`, `Panel`, `DataTable`, `Drawer`, `ConfidenceBar`, `Timeline`, `Countdown` onto new tokens (no behavior changes in this phase); apply `.data-digit` (tabular-nums slashed-zero) to every numeric render
- Audit pass: remove confirmed-orphaned CSS (`.nk-eval-run-pill`, `.nk-cold-start-chart`, `.nk-feedback-plot` if still unused after Phase 5 confirms they stay unused — otherwise wire them up when their owning screen is touched)

**New packages:** `postcss` (MIT), `autoprefixer` (MIT), `@fontsource-variable/jetbrains-mono` (OFL-1.1), optionally `@fontsource-variable/inter` (OFL-1.1) — all license-compatible, all offline/self-hosted.

**Demo-ready when:** every existing screen renders on the new palette with no console errors, and the HUD clock ticks with the simulator.

**Verification:**
```
npm run ci:web
```
Manual/visual: `npm run dev`, confirm a Tailwind arbitrary-value class (e.g. `border-white/[0.08]` on a test element) actually applies — the concrete proof the previously-dormant Tailwind pipeline (§0) now works; confirm the clock advances only when `sim.time` events arrive (pause the simulator: it must stop).

### Phase 2 — Triage Cockpit & Live KPIs

**Target files:**
- New: `apps/web/src/shared/time/TimeProvider.tsx` (§2.1)
- New: `apps/web/src/shared/ui/CountdownRing.tsx`
- New: `apps/web/src/shared/audio/tacticalPing.ts`
- New: `apps/web/src/shared/ui/HoldToActuateButton.tsx`
- New: `apps/web/src/shared/ui/RollingCounter.tsx` (plain CSS `transition` on a `<span>`; no Motion dependency, §0) — **moved up from the old Phase 5** because the tally and Dashboard KPIs are among the first things a demo shows
- New: `apps/web/src/shared/ui/ConsequenceTally.tsx` (§2.1 "Held ₹X · N actions")
- New: `apps/web/src/shared/state/selectionStore.ts` (linked-selection primitive, §2.3) — created here because the Phase 3 palette needs it; map/graph wiring follows in Phases 3 and 4
- Modify: `apps/web/src/shared/ui/DataTable.tsx` — add `virtualized?: boolean` (via `@tanstack/react-virtual`), row height read from one constant (64px / 48px for the density toggle), fix the dormant sort bug (§0)
- Modify: `apps/web/src/features/alerts/AlertsInbox.tsx` — virtualization, `CountdownRing`, `triage-inbox` hotkey scope (`j`/`k`/`1`–`9`/`f`/`d`/`x`/`Space`/`Escape`), `<kbd>` hints, sticky "▲ N new" pill, `ConsequenceTally` in the header, row-exit fade (cut first if short on time)
- Modify: `apps/web/src/features/alerts/AlertDetail.tsx` — `request_hold`/`dispatch` → `HoldToActuateButton`; `acknowledge`/`notify_station`/`OutcomeButtons` stay plain buttons with `toast.promise()`; `override` gets the non-dismissible-toast treatment (§2.1)
- Modify: `apps/web/src/shared/stream/useStream.tsx` — `playTacticalPing("CRITICAL")` on `alert.created` when `severity === "CRITICAL"`, gated by a `localStorage` sound-preference flag
- Modify: `apps/web/src/app/providers.tsx` — replace `react-hot-toast`'s `<Toaster/>` with `sonner`'s `<Toaster/>`
- Modify: `apps/web/src/app/App` root — wrap in `TimeProvider` (above `AlertsInbox`, below `StreamProvider` since it depends on `useSimTime()`)
- Modify: `apps/web/src/features/dashboard/DashboardPage.tsx` — KPI strip uses `RollingCounter`; replace hardcoded-hex accent props (`#ef4444`, `#38bdf8`, `#f59e0b`, `#a78bfa`) with token references, checking each against the Golden Color Rule (§1.3): only the "critical alert" tile may use `--nk-severity-critical`, the others go to neutral + glyph or the single `--nk-accent`
- Modify: `apps/web/src/shared/ui/ShortcutSheet.tsx` — list the `triage-inbox` scope
- New tests: `apps/web/src/shared/ui/__tests__/CountdownRing.test.tsx`, `apps/web/src/features/alerts/__tests__/HoldToActuate.test.tsx` (release-before-600ms cancels; hold-to-completion fires the mutation exactly once; `enableOnFormTags:false` doesn't fire while a filter input has focus), `apps/web/src/shared/ui/__tests__/ConsequenceTally.test.tsx` (optimistic tick, reconcile to a *lower* `applied_amount_paise`, rollback on error)

**New packages:** `react-hotkeys-hook` (MIT), `@tanstack/react-virtual` (MIT), `sonner` (MIT). Remove `react-hot-toast` from `dependencies` (zero call sites to migrate, per §0).

**Demo-ready when:** an alert can be seen arriving, pinged, acted on by hold, and reflected in the tally (pending, then reconciled to what the bank applied) — end to end, with the Dashboard KPIs rolling.

**Verification:**
```
npx vitest run src/shared/ui/__tests__/CountdownRing.test.tsx src/features/alerts/__tests__/HoldToActuate.test.tsx src/shared/ui/__tests__/ConsequenceTally.test.tsx
npm run ci:web
```
Manual: open `/alerts` with the demo simulator running, confirm `j`/`k` traversal, confirm a CRITICAL alert plays the ping once (not per-render), confirm holding `f`, then holding the button for <600ms on a `request_hold`-eligible alert cancels with no mutation fired (Network tab), and a full hold sends `params.account_id` + `params.proposed_paise` and the tally reconciles once the bank-sim callback lands.

### Phase 3 — Command Palette & Tactical Map

**Target files:**
- New: `apps/web/src/shared/ui/CommandPalette.tsx` (`cmdk`, §2.5), including the context-aware group
- Modify: `apps/web/src/app/layout/Shell.tsx` — mount `CommandPalette`, bind global `Cmd/Ctrl+K` via `react-hotkeys-hook` (already a dependency from Phase 2), show the palette trigger in the topbar
- New: `apps/web/src/features/map/LayerPanel.tsx` — toggle switches with `<kbd>` hints and live count badges (§2.3); persists to `localStorage`
- New: `apps/web/src/features/map/MapHud.tsx` — cursor lat/lon, zoom, "N layers · N entities" strip (§2.3); coordinates written via ref, not state
- Modify: `apps/web/src/features/map/MapAdapter.ts` and `maplibre/MapLibreAdapter.ts` — add `onPointerMove(cb)` / `onViewChange(cb)` (internal interface); confirm `setLayerVisibility` toggles the heat density + point layers as one unit
- New: `apps/web/src/features/map/layers/radarIconLayer.ts` (`StyleImageInterface`, §2.3)
- Modify: `apps/web/src/features/map/maplibre/MapLibreAdapter.ts` — register the radar icon layer, cap to top 1–3 hottest cells, downgrade the rest to static `circle-radius`-transition cells; stop the repaint loop when the owning layer is toggled off
- Modify: `apps/web/src/features/map/MapPage.tsx` — `"map"` hotkey scope (`H`/`L`/`A`/`I`/`B`/`Escape`); wire `selectionStore` (`flyTo` + highlight)
- Modify: `apps/web/src/features/alerts/AlertsInbox.tsx` (row click) — write to `selectionStore`; `apps/web/src/shared/ui/ShortcutSheet.tsx` — list the `map` scope

**New packages:** `cmdk` (MIT). No new map dependency (`maplibre-gl` already present; `StyleImageInterface` is native MapLibre API).

**Demo-ready when:** `Cmd+K` → an alert → *Show on map* flies to the location with the radar pulsing, and toggling layers with the keyboard visibly changes the counts.

**Verification:**
```
npx vitest run src/shared/ui/__tests__/CommandPalette.test.tsx src/features/map/__tests__
npm run ci:web
```
Manual: `Cmd+K` opens from any screen; fuzzy-search a masked account ref and a bank code both resolve; with an alert selected the palette offers only actions present in its `allowed_actions`; layer hotkeys don't fire while a filter input has focus; only the top 1–3 heat cells show the animated radar (DevTools performance panel — frame time stays stable with many static cells present); cursor readout doesn't re-render `MapPage` (React DevTools profiler).

### Phase 4a — Case Dossier Quick Wins

Goal: the most visible defect fixed cheaply, before any library migration.

**Target files:**
- Modify: `apps/web/src/features/clusters/ClusterGraph.tsx` — **on the existing raw-Cytoscape component**, replace the dead `kind`-based selectors with the client-computed `role` (`origin`/`pass-through`/`pooling`/`terminal`, derived from in/out-degree over `cappedEdges`, §2.2) and relabel the legend; extract the `cyNodes`/`cyEdges` mapping into an exported, unit-tested `toCytoscapeElements()` pure function (also becomes the seam for the 4b migration); edge width mapped to `amount_paise`
- Rewrite/restyle: `CasesPage.tsx` moves onto `Panel` + `DataTable` (with a neutral `CaseStatusChip` built on the hue-free badge classes: `StatusBadge` itself takes *alert* statuses, which case statuses are not); `CaseDetail.tsx` and `ClustersPage.tsx` keep their structure and are re-themed by replacing every hardcoded hex with tokens (a full Panel rewrite of a 500-line inline-styled file was not worth the regression risk). `SafeBriefRenderer` logic preserved. Statuses and roles stop borrowing severity/hue colours (§1.3)
- Modify: `apps/web/src/features/clusters/ClustersPage.tsx` — restyle onto tokens
- Modify: `apps/web/src/features/cases/CaseDetail.tsx` — graph node click writes to `selectionStore` (map already listens, from Phase 3)

**New packages:** none.

**Demo-ready when:** a seeded cluster visibly renders more than one node shape/colour with an honest legend, and the Cases screens no longer look like a different product.

**Verification:**
```
npx vitest run src/features/clusters/__tests__ src/features/cases/__tests__
npm run ci:web
```
Manual: the specific regression test for the node-kind fix — open a real multi-hop seeded cluster and confirm origin ellipses, pooling diamonds, terminal hexagons and pass-through rounded-rects all appear (not the uniform gray circles rendered today); confirm the 200-node cap still triggers on a large seeded cluster; unit-test `toCytoscapeElements()` and the role classifier including the singleton (in=0, out=0) and pooling (in≥3) cases.

### Phase 4b — Case Dossier Forensic Depth

**Target files:**
- Modify: `apps/web/src/features/clusters/ClusterGraph.tsx` — migrate raw `cytoscape` → `react-cytoscapejs`; `preset` layout → `cytoscape-dagre` (left to right, edge `minLen` seeded from the hop layer) with a cycle-detection pass falling back to `cytoscape-cose-bilkent` for rings (§2.2); hop-depth limiter, minimum-amount slider and "N edges hidden · show all" (§2.2); entity inspector (§2.2); click-to-isolate trail; group-by-bank; PNG/CSV working-copy export; timeline-playback dimming. **`cytoscape-expand-collapse` was NOT used** (see below). Pure logic lives in `graphModel.ts` (filters, grouping, cap, cycle check, chain, stats, CSV) and is unit-tested.
- **Deviation — bank grouping without `cytoscape-expand-collapse`:** grouping is a pure transform (`groupByBank`): same-bank accounts fold into one "HDFC — 14 accounts" node, edges between groups are summed (a test asserts the total is conserved), and clicking a group expands it. Compound-node layout with dagre across hop columns reads badly, and a pure transform is testable and adds no dependency. The package was installed, found MIT, and then removed unused. Secondary grouping by `sub_communities` was dropped: the cluster endpoint does not return them.
- **Finding — grouping can create false rings:** folding same-bank accounts together can make the graph loop (SBIN group → AXIS → PUNB → SBIN group) even though no money actually cycled. The graph therefore distinguishes a real ring (checked on the ungrouped trail) from a grouping artifact and labels each differently.
- New: `apps/web/src/features/cases/CaseFundFlowSankey.tsx` (Recharts `<Sankey>`, client-aggregated from existing `ClusterModel` data — no new API call)
- New: `apps/web/src/features/cases/CaseTimelineScrubber.tsx` (edge-timeline playback, §2.2)
- New: `apps/web/src/features/cases/exportGraphView.ts` — PNG + visible-edges CSV, labelled "Working copy — not the evidence pack" (§2.2); lowest priority in this phase
- Modify: `apps/web/src/shared/ui/CommandPalette.tsx` — register the dossier context commands (jump to hop N / evidence item N, isolate ring, export view)

**New packages:** `react-cytoscapejs` (MIT), `cytoscape-dagre` (MIT) + `dagre` (MIT, peer dep), `cytoscape-expand-collapse` (MIT), `cytoscape-cose-bilkent` (i-Vis/Bilkent, MIT — the cyclic-graph fallback for dagre, §2.2). Add a local `apps/web/src/shared/types/cytoscape-plugins.d.ts` declaring module types for any of these lacking maintained `@types/*` packages (verify at install time).

**Verification:**
```
npx vitest run src/features/clusters/__tests__ src/features/cases/__tests__
npm run ci:web
```
Manual: dagre renders left-to-right in hop order matching the previous hand-computed layout's ordering; a seeded cyclic ring falls back to `cose-bilkent` instead of laying out with a reversed edge; bank-grouping collapse/expand doesn't drop edges (aggregate weight sums correctly); the min-amount slider changes the "N hidden" count and the hidden `₹` sum consistently with the edge list; the connection-chain highlight follows real edges; the entity inspector's totals equal the sum of that node's edges.

### Phase 5 — System Integrity HUD & Consistency Pass

**Target files:**
- New: `apps/web/src/shared/api/fetchEvalResults.ts` — NaN-sanitizing fetch helper (§2.4): fetch as text, sanitize bare `NaN` tokens, `{ value: number | null, n: number }` per metric
- Rewrite: `apps/web/src/features/evaluation/EvaluationPage.tsx` (or a new `features/system/SystemIntegrityPage.tsx` composition, matching the existing `feature:system → feature:[evaluation, ops, audit]` boundaries rule) — wire `/system/metrics`, `/audit/verify`, `/analytics/live-metrics`, sanitized `eval-results.json` per §2.4; `RollingCounter` on the exposure tiles; latency sparklines from a 10s client-side rolling buffer
- Audit pass: every mutation across `alerts`, `casework`-adjacent actions (`EvidencePackPanel`'s generate action, `OutcomeButtons`), and `ops`/`audit` pages gets the consistent optimistic-update + `sonner` treatment of the tiered model in §2.1 (evidence-pack generation gets plain success/error toasts)
- Modify: `apps/web/src/shared/ui/ShortcutSheet.tsx` — final pass so every scope is listed and matches the real bindings

**New packages:** none.

**Verification:**
```
npm run ci:web
npm run test:e2e --workspace apps/web   # if Playwright specs exist/are extended for the triage + case flows touched across phases
```
Manual: full click-through of the demo flow (`npm run dev:sim` + `npm run dev`) — Dashboard → alert → hold-to-freeze → `Cmd+K` to map → case dossier → System HUD; confirm the audit-chain indicator shows `ok`, and that an `eval-results.json` containing bare `NaN` renders "insufficient sample (n<30)" instead of throwing.

---

## 4. Cross-cutting engineering notes (apply throughout, not phase-specific)

- **Paise, always:** every amount field from the backend is integer paise (`amount_paise`, `total_paise`, `disputed_paise`, `proposed_paise`, `applied_amount_paise`). The existing `formatInr()`/`paiseToInr()` in `shared/lib/format.ts` already handles this correctly (Indian digit grouping, compact ₹L/₹Cr notation) — reuse as-is; only the CSS treatment (`tabular-nums slashed-zero`, §1.4) is new. Do not introduce a second formatting path.
- **`severity`/`verdict`/`ladder_level`/`status` are typed `string` in `schema.d.ts`**, not literal-union enums (the Pydantic models type them as `str`, so `openapi-typescript` can't narrow them) — widen these to the actual enum unions manually in a shared `shared/api/enums.ts` addition (the file already exists; extend it) rather than trusting the generated types to constrain them.
- **`ForecastModel.levels` and `MetricsResponse.stages`/`.outbox` are dynamic-key maps**, not fixed-shape objects — index by key defensively (`Object.entries`), don't destructure assuming `district`/`cell`/`location` or any specific stage name will always be present.
- **`eslint-plugin-boundaries` compliance:** any new shared primitive (`TimeProvider`, `CountdownRing`, `HoldToActuateButton`, `RollingCounter`, `ConsequenceTally`, `ShortcutSheet`, `CommandPalette`, `selectionStore`, `tacticalPing`); map-only pieces (`LayerPanel`, `MapHud`) stay inside `features/map` must live under `shared/*` — confirmed importable from every feature by the existing boundaries config. The only two feature→feature import exceptions (`cases→clusters`, `system→{evaluation,ops,audit}`) already cover this plan's cross-feature needs (Case Dossier reusing the Cluster graph, System HUD composing Evaluation/Ops/Audit); no new boundary exception should be needed.
- **Role/permission gating stays server-driven:** every action button's visibility is already gated by `allowed_actions` (alerts) or route-level `RoleGuard`/`can()` (System `/metrics` requiring `SIM_CONTROL`) — new components (hold-to-actuate, command palette action items) must check these same existing gates rather than re-deriving permission logic from `Role` client-side.

---

## 5. Open decisions requiring a (small, additive, non-breaking) backend follow-up

Five items are listed below (5.1–5.5). None blocks Phases 1–5 — each is scoped around in the frontend plan above — but each is worth a backend ticket where the honest, currently-shippable frontend behavior is a deliberate downgrade from what real data would enable. If only one is picked up, pick **5.3**: it is the smallest, and it makes the Phase 4b "N hidden" figures exact at scale.

**5.1 — Evaluation calibration data.** The System Trust HUD's "Brier score curve"/calibration diagram cannot be built today because `evaluation/metrics.py`'s `reliability_curve()` (→ `BinStat[]`) and `lead_time_minutes()` (→ `LeadTimeStats`) exist as pure functions but are never invoked by anything that writes output the frontend can read (`scripts/evaluate.py` only calls the scalar metrics). This is **not** a contract break — it would be a new, additive field in the same JSON artifact (or a new tiny script), touching no locked contract (LC-1..LC-10) and no existing endpoint shape.

Recommendation: extend `scripts/evaluate.py` to also call `reliability_curve()`/`lead_time_minutes()` and include their output under new keys in `eval-results.json`, and fix the script's `json.dumps(..., allow_nan=True)` call to match `evaluation/report.py`'s existing NaN-to-`null` scrubbing (that correct pattern already exists in the codebase, just not applied here). Until it lands, §2.4 ships with the scalar-metrics scope described there, plus the client-side NaN-sanitizing workaround (needed regardless, since even the scalar metrics can independently hit the same `NaN` bug below `n=30`).

**5.2 — Mule-graph node role classification.** `casework/__init__.py`'s `cluster_graph()` hardcodes `kind="account"` for every node (verified, §0/§2.2) — there is currently no way for the backend to tell the frontend which account is the victim's, which is a cash-out point, or which is a pooling/aggregator account. The raw signal exists upstream but isn't persisted per-account: `ComplaintFact.touched_account_ids` is consumed once for headcounts (`bundle.py`) and discarded; `CashOutFact.account_id` (`graph/application/apply_cashouts.py`) is folded into aggregate `cluster_location_stats` and never retained as a per-account fact.

Recommendation: (a) thread the account(s) in `ComplaintFact.touched_account_ids` through to `cluster_graph()` and emit `kind="victim"` for them instead of `"account"`; (b) persist `CashOutFact.account_id` observations in a queryable per-account table (a genuinely new, small table — this is the bigger half of the two asks here) so `cluster_graph()` can join against it and emit `kind="cashout"`. Both are additive changes to a field that is already a free-form `str` — no shape change, no locked-contract risk. Until this lands, §2.2's Phase 4a fix (topology-inferred `origin`/`pass-through`/`pooling`/`terminal` roles, computed entirely client-side from the edge list already being fetched) is what ships, and is an honest, defensible interim state precisely because it never claims more certainty than the data supports.

**5.3 — Server-side graph shaping and pruning (Claude's report, executive-summary point 4 and its #3 recommended reference project).** Claude's report's own headline recommendation — the backend's graph endpoint should return pre-shaped Cytoscape.js elements with hop-limiting/edge-pruning already applied server-side, rather than the frontend fetching raw rows and both transforming and capping them itself — is only partially reflected in this plan (§2.2) because doing it exactly as described would change `/clusters/{cluster_id}`'s response shape (`ClusterNodeModel[]`/`ClusterEdgeModel[]` → literal `{group, data}` Cytoscape element JSON), which the task's "no contract-shape changes" constraint forbids. Two genuinely additive alternatives that don't touch the existing shape:

- Add an optional `max_nodes` (default matching the frontend's current 200) query parameter to `GET /clusters/{cluster_id}` that applies the same priority-scored cap `ClusterGraph.tsx` currently computes client-side, and return a `truncated_count` alongside the existing `nodes`/`edges` fields — this is additive (new optional field, new optional query param, old callers unaffected) and fixes the real inefficiency noted in §2.2 (fetching a possibly-much-larger-than-200-node payload just to discard most of it client-side).
- A separate, net-new `GET /clusters/{cluster_id}/graph-elements` endpoint that wraps the existing data in literal Cytoscape element shape would satisfy Claude's recommendation exactly, without touching `/clusters/{cluster_id}` at all — but given the frontend-side thin-adapter mitigation already described in §2.2 achieves most of the same benefit (an isolated, testable transform function) at no backend cost, this is the lower-priority of the two asks here and is listed mainly for completeness.

**5.3a — Hop limiting and pruning metadata (second-pass extension of 5.3, small and additive).** On the same `GET /clusters/{cluster_id}`, add an optional `max_hops` query parameter alongside `max_nodes`, and return `hidden_edge_count` and `hidden_amount_paise` next to `truncated_count`. Old callers are unaffected (new optional param, new optional fields). This lets Phase 4b's "N edges hidden · show all" and hop-depth limiter report exact figures for clusters far larger than the payload the client would otherwise download, which is the pattern Claude's report cites from `crypto-tracer` (hop limit with pruning metadata returned alongside nodes/edges). Until it lands, the client computes the same numbers over whatever payload it received and labels them as "in loaded data".

**5.4 — Graph annotations (not small; recommend deferring).** Claude's report describes Chainalysis Reactor's workflow as graph-centric with annotation and export. Export is covered client-side (§2.2, "working copy"). Annotation is not: it needs a persisted, audited note attached to a cluster node, gated by an authenticated `Principal`, with wording rules from DOC1 §1.5 applied to free-text notes (no guilt assertions, no real names). That is a new table, endpoint and audit action, i.e. a feature, not a tweak. Listed so the option is on record; not needed for the demo.

**5.5 — "Why flagged" chip on queue rows (unverified, likely tiny).** `ForecastModel.evidence[]` (`code`, `params`, `text_en`) already exists and `AlertDetail` already renders it. If `AlertSummaryModel` (the list-row shape) does not carry it, adding the top evidence `code` there would be one additive field and would let the queue show a short "why" chip without opening the detail panel. **Not checked against the summary model in this pass**; verify before scoping.
