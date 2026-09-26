# Research: High-End Operational Command, Dispatch & Forensic UI Patterns for NAKABANDI

**Scope note up front:** GitHub search for "SOC/fraud/mule triage dashboard" surfaces mostly hackathon and student portfolio repos (many clearly AI-scaffolded, low star counts, thin commit history) — including several 2026 hackathon projects (RIFT, SIH) that are direct functional peers of NAKABANDI. There is **no widely-starred, production-grade, permissively-licensed open-source reference implementation** that is simultaneously a (a) real-time triage cockpit, (b) financial forensic graph tool, and (c) tactical dark UI, all at once. The best available strategy — and what this report recommends — is composing **primitive libraries** (Radix/shadcn, Cytoscape.js, MapLibre, cmdk/kbar, Sonner) using patterns borrowed from **adjacent, better-documented domains**: Linear's design engineering, Chainalysis Reactor's public workflow documentation, and DevOps/observability dashboard conventions. This is stated plainly so the team doesn't spend time hunting for a single "Gotham starter kit" that doesn't exist in OSS.

---

## 1. Tactical Incident & Fast-Decay Triage Cockpits

### Findings

**1.1 — [timc1/kbar](https://github.com/timc1/kbar)**
Publisher/Date: Tim Cheung, actively maintained. Stack & License: React, headless/unstyled, **MIT**. Pattern: <cite index="43-1">a plug-n-play React component for a fast, portable, extensible command+k interface with built-in animations, keyboard navigation (ctrl+n/ctrl+p), and keyboard shortcuts bound to specific actions</cite>. Application to NAKABANDI: use kbar (or cmdk, below) as the backbone for the **Triage Inbox's sub-second keyboard triage** — bind single keys (`f` = freeze, `e` = escalate, `d` = dismiss, `1`-`9` = jump to alert N) scoped only while an alert row has "focus," matching kbar's scope model. **[VERIFIED — README reviewed directly]**

**1.2 — [pacocoursey/cmdk](https://github.com/pacocoursey/cmdk)**
Stack & License: React, **MIT**, unstyled, built on Radix primitives (fits your shadcn/Radix stack directly). Pattern: <cite index="45-1">an unstyled primitive — cmdk handles fuzzy filtering and keyboard navigation via the command-score library, which favors prefix and contiguous matches, and stays smooth into the low thousands of items</cite>; note the same source flags that <cite index="45-1">cmdk renders only the palette and does not run your app's other keyboard shortcuts — that's a separate concern</cite>. Application: cmdk is the better fit than kbar for a shadcn codebase (shares Radix), but you'll still need a second, dedicated hotkey layer for row-level triage actions (see 1.3). **[VERIFIED — README/analysis reviewed directly]**

**1.3 — [JohannesKlauss/react-hotkeys-hook](https://github.com/JohannesKlauss/react-hotkeys-hook)**
Stack & License: React hook, **MIT**, 3.6M+ weekly npm downloads. Pattern: <cite index="79-1">a declarative React hook for keyboard shortcuts with scopes, so hotkeys can be grouped to prevent collisions with each other</cite>. Application: this is the actual engine for NAKABANDI's triage hotkeys layer — define a `triage-inbox` scope active only when that pane has focus, so `f`/`e`/`d`/arrow-keys don't leak into the GIS map or Case Dossier scopes. Pair with cmdk for the global `Cmd+K` search-everything palette. **[VERIFIED — README reviewed directly]**

**1.4 — Purpose-built SOC/alert-triage dashboards on GitHub (multiple, low confidence)**
Repos found: `Barrosleo/soc-alert-triage-dashboard`, `Jagtap100/soc-alert-triage-dashboard`, `winmyataun0007-hue/Triagedesk`, `SiteQ8/secopsdash`, `aboodaslan33/Alert-Triage-Workbench`. Licenses are mostly unstated or MIT; several are Python/FastAPI + vanilla JS or Streamlit, not React/Tailwind — architecturally distant from your stack. One exception worth a closer look: **`aboodaslan33/Alert-Triage-Workbench`** — <cite index="5-1">a working SOC Level 1 triage queue running entirely in the browser</cite>, notable for a real design discipline: <cite index="5-1">colour means severity and nothing else; triage verdicts and workflow status use glyph and weight, never colour</cite>, and it separates "detail" (raw record + matched rule) from "queue" cleanly. This severity-is-color-only / status-is-shape-only convention is directly reusable for NAKABANDI's Triage Inbox to keep 20+ alerts scannable without relying on color alone (accessibility + reduces "everything is red" fatigue). **[UNVERIFIED — reviewed via search snippet, not cloned]**. The rest of this cluster (SecOpsDash, CyberDefenseX, TriageDesk) are **not recommended as architecture references** — they read as generated demo apps rather than production patterns; flagging them mainly so the team doesn't waste time evaluating them further.

**1.5 — Circular SVG countdown timers / severity pulses**
No single dedicated open-source "alert countdown timer" component library was found in this search that matches your exact need (per-alert SVG ring counting down to SLA breach). This is a **gap** — recommend building this as a small custom component: an SVG `<circle>` with `stroke-dasharray`/`stroke-dashoffset` driven by `requestAnimationFrame` or a CSS custom property + `@property` animation, colored via a CSS variable that steps through severity bands. This is a well-known, cheap-to-build pattern (search terms "SVG circular countdown timer React" return many small tutorials/gists, none authoritative enough to cite as *the* reference) — treat it as bespoke, not sourced.

**1.6 — Zero layout shift for a growing/shrinking queue**
No single canonical repo found; the standard, low-risk approach given your stack is CSS Grid with fixed row height + `overflow-y: auto` on the list container (not the page), combined with either CSS `view-transition-name` (if targeting recent Chromium) or a small Framer Motion `AnimatePresence`/`layout` wrapper around each row so removals/reorders animate rather than jump. Framer Motion is MIT and commonly paired with shadcn.

### How this applies to NAKABANDI's screens
- **Triage Inbox**: cmdk (global search) + react-hotkeys-hook (scoped row actions) + custom SVG countdown rings + color-for-severity/shape-for-status convention from Alert-Triage-Workbench.
- **Case Dossier**: cmdk can double as an in-dossier "jump to evidence item N" palette.

---

## 2. Forensic Money-Flow & Mule Network Graph Visualization

### Findings

**2.1 — [plotly/react-cytoscapejs](https://github.com/plotly/react-cytoscapejs)**
Stack & License: React wrapper for Cytoscape.js, **MIT**. Pattern: <cite index="26-1">an MIT-licensed React component for network visualisation where the component renders a Cytoscape graph and most props are Cytoscape JSON</cite>. This is the correct, official binding for your mandated stack — use this rather than hand-rolling a Cytoscape/React integration. **[VERIFIED — README reviewed directly]**

**2.2 — [cytoscape/cytoscape.js](https://github.com/cytoscape/cytoscape.js)**
License: **MIT**. <cite index="28-1">Cytoscape.js is a fully-featured graph theory library for modelling and visualising relational data, designed to make graph theory as easy as possible to use whether server-side in Node or in a rich UI</cite>. Confirmed base dependency, MIT-clear. **[VERIFIED]**

**2.3 — `cytoscape-cola` layout extension (surfaced via peer project mm-backend)**
One peer hackathon project explicitly notes: <cite index="23-1">using cytoscape-cola for force-directed layout, with a fallback to the cose layout because cola can be slow above roughly 1,000 nodes</cite>. Application: for NAKABANDI's mule-cluster graphs, use `cytoscape-cola` for the default force-directed view (it produces more readable, less-overlapping layouts than `cose` for financial flow graphs), but implement the same fallback-to-`cose` threshold for large clusters to protect frame rate. `cytoscape-cola` is MIT. **[UNVERIFIED — surfaced via a peer repo's README, not independently confirmed against the cola repo itself]**

**2.4 — Peer hackathon projects doing near-identical work (architecture references, not code to copy)**
Several 2025–2026 Indian hackathon submissions (RIFT, SIH) independently converged on the same stack pattern you're using — this is a strong signal it's the right shape for this problem class, even though none of these individual repos is polished enough to lift wholesale:
- **`pranavperingeth/SIH-26` (ChainTrace)**: <cite index="22-1">visualizes the complete fund-flow network from victim to exchange using Cytoscape.js, with click-to-inspect risk scores, transaction history, and SHAP explanations, built for law-enforcement officers to submit wallets, track investigations, and receive live alerts</cite>. Directly maps to your Case Dossier + GIS/graph split. **[UNVERIFIED]**
- **`Sagar-S-R/mm-backend` (RIFT 2026)**: <cite index="23-1">a deterministic graph-intelligence engine using NetworkX for detection and React + Cytoscape.js (with cytoscape-cola) for visualisation, exposing a `/graph-data` endpoint that returns Cytoscape-ready elements directly</cite>. The pattern of a backend endpoint that returns **pre-shaped Cytoscape JSON** (not raw rows the frontend has to transform) is worth copying directly into NAKABANDI's API contract — it keeps the graph rendering layer dumb and fast. **[UNVERIFIED]**
- **`prithvi-01x/crypto-tracer`**: notable for a **noise-reduction pattern** relevant to your Layer-1/Layer-2 mule cascades: <cite index="25-1">illicit networks deliberately inject dozens of low-value "micro-dust" transactions to cause exponential branching and exhaust investigator bandwidth in visual graph tools, so the system applies a configurable hop-limit (default 4, range 1–6) and returns pruning metadata alongside the nodes and edges</cite>. Application: build server-side edge-pruning/hop-limiting into your graph API from day one, and expose "N edges hidden" affordances in the UI rather than rendering everything — this is exactly the node-collapsing behavior your spec asks for. **[UNVERIFIED]**
- **`DharshiniManikandan-1203/fraud-graph`**: pattern of <cite index="20-1">a force-directed Cytoscape.js canvas with glowing risk halos and node-type badges, paired with a separate "entity intelligence inspector" panel showing a risk-score gauge, connection chains, and a one-click "isolate this ring" focus mode</cite> — the click-to-isolate-subgraph interaction is a good concrete UX pattern for your Case Dossier when an investigator wants to focus on one mule ring without losing the full graph context (push/pop filter, not navigate-away). **[UNVERIFIED]**

### How this applies to NAKABANDI's screens
- **GIS Map ↔ Case Dossier split**: geography stays in MapLibre; the *relationship* structure (Victim → L1 Mule → L2 Mule → ATM) stays in Cytoscape via `react-cytoscapejs`, linked by shared entity IDs so clicking a node in one highlights the corresponding pin in the other.
- **Case Dossier graph**: `cytoscape-cola` default layout, `cose` fallback above a node-count threshold, server-side hop-limiting/pruning with an explicit "N hidden low-value edges — show all" toggle, and a click-to-isolate-ring focus mode.
- Edge weight → line thickness/opacity mapped to transaction amount; a temporal "playback" affordance (a scrubber that fades in edges by timestamp) is a common ask in this category but no OSS reference for a Cytoscape.js-specific edge-timeline scrubber was found — treat as custom build using Cytoscape's own event/style API (`cy.style().selector(...).update()` driven by a `requestAnimationFrame` loop).

---

## 3. High-Density Tactical UI & Dark Command Aesthetic

### Findings

**3.1 — Linear's design tokens (multiple independently-reconstructed sources agree closely)**
Several independent teardown sites converge on the same core numbers, which is a good confidence signal for a public, unofficial reverse-engineering:
- Canvas: <cite index="16-1">Linear's marketing site floor is #010102 — essentially pure black with a faint blue cast, deliberately not the flat "#000000" true black most dark sites default to</cite>. Accent: <cite index="16-1">a single chromatic accent, lavender-blue #5e6ad2, used scarcely — the brand mark, focus rings, and one primary CTA per section</cite>.
- Typography weight discipline: <cite index="17-1">a three-tier weight system — 400 for reading, 510 for emphasis/UI, and 590 for strong emphasis — deliberately avoiding heavy bold weights</cite>.
- Shadow philosophy on dark: <cite index="17-1">on dark surfaces, traditional dark-on-dark shadows are nearly invisible, so hierarchy is carried by surface lift and hairline borders instead</cite>, confirmed independently: <cite index="19-1">borders are hairline-thin (0.5px) so geometry, not shadow, does the work of separating panels</cite>.
- Density principle stated by Linear itself: <cite index="13-1">in an information-dense product, not every element of the interface should carry equal visual weight — secondary chrome like tabs is dimmed and compacted so the main working content takes precedence</cite>.

**Application to NAKABANDI**: adopt the near-black-not-pure-black canvas (`#0a0a0b`–`#0f1011` range), a single tactical accent color (reserve amber/red purely for severity, pick one separate neutral accent — e.g. cyan or amber — for interactive/focus state so severity color isn't overloaded), hairline borders (`border-white/10`) instead of box-shadows for panel separation, and the 3-weight type scale. **[VERIFIED — multiple independent teardown sources agree; Linear's own blog post confirms the density principle directly]**

**3.2 — Monospace tabular figures — use `font-variant-numeric: tabular-nums`, not a monospace font hack**
<cite index="69-1">If a monospace font is used purely to stop digits from jittering, `font-variant-numeric: tabular-nums` (Tailwind's `tabular-nums` utility calls the same CSS property) is the correct, more portable fix and works in all modern browsers</cite>; the same source recommends <cite index="69-1">pairing `tabular-nums` with `slashed-zero` in financial tables specifically, since it's easier to distinguish 0 from O</cite>. **Given your offline constraint**, this matters: don't runtime-fetch Google Fonts for a monospace face — self-host a variable monospace (e.g. JetBrains Mono, SIL OFL, bundle the `.woff2` in the repo) and apply `tabular-nums slashed-zero` on every numeric cell (amounts, timestamps, counts). **[VERIFIED]**

**3.3 — Reference dark dashboard aesthetic (secondary, lower-confidence source)**
A dashboard-template roundup describes a comparable pattern already in commercial templates: <cite index="70-1">a DevOps-first dashboard with a terminal aesthetic — JetBrains Mono typography, a near-black palette, and neon-green accent semantics that read as "healthy" in monitoring contexts</cite>. This confirms the JetBrains Mono + near-black + single-semantic-accent combination is an established convention for "mission-critical tool" aesthetics generally, beyond just Linear. **[UNVERIFIED — commercial template marketing copy, not inspected directly; template itself not open-source]**

**3.4 — shadcn/ui + Tailwind v4 font registration for offline bundling**
shadcn's own registry format shows the correct mechanism for baking in a variable font without a runtime Google Fonts fetch — a `registry:font` item pinned to a package like `@fontsource-variable/jetbrains-mono`, which ships the font files as an npm dependency rather than a CDN `<link>`. This satisfies your "no Google Fonts runtime fetch" constraint directly. **[VERIFIED — shadcn docs reviewed directly]**

### How this applies to NAKABANDI's screens
- Global: near-black canvas (not `#000`), hairline borders over shadows, 3-tier font-weight scale, one non-severity accent color, `@fontsource-variable/jetbrains-mono` bundled locally + `tabular-nums slashed-zero` on every number.
- **System Integrity** screen (uptime %, queue depth, throughput) is exactly the terminal/monitoring aesthetic described in 3.3 — this is the screen where the JetBrains Mono + tabular-nums treatment should be most aggressive.

---

## 4. Offline MapLibre GL Tactical Operations Mapping

### Findings — this is the weakest-coverage question; state the gap plainly

**4.1 — [maplibre/maplibre-gl-js](https://github.com/maplibre/maplibre-gl-js)**
License: <cite index="33-1">MapLibre GL JS is a fully open-source, GPU-accelerated vector tile map renderer, originally forked from mapbox-gl-js before Mapbox's license change in December 2020, and is not permitted to backport code from the now-non-OSS mapbox-gl-js</cite>. Base license is **BSD-3-Clause** — confirmed permissive, compatible with your constraints. **[VERIFIED]**

**4.2 — No dedicated "tactical/radar-sweep/military-style" MapLibre repository was found.** The closest analog located is Mapbox's own (Mapbox-specific, but conceptually portable) circle-radius pulsing-dot pattern: <cite index="31-1">a point source whose `circle-radius` paint property is incremented each animation frame toward a max radius, then reset — the standard technique for simulating a radar "blip"</cite>. There is also a maintained, MIT rain/radar-image overlay layer, `nagix/mapbox-gl-rain-layer` (<cite index="30-1">an animated rain layer for Mapbox GL JS, MIT-licensed</cite>) but it's built for weather-radar tile imagery and is the wrong shape for a threat-radius overlay — flagging only because it's the nearest "radar" name-match, not a recommendation. **[VERIFIED as a non-fit]**

**4.3 — Community guidance confirms this needs to be built with Canvas, not relied on as off-the-shelf.** MapLibre's own maintainers, in a live discussion thread, describe the real trade-off directly: <cite index="32-1">a canvas layer gives significant control over rendering via the Canvas API, but heavy custom WebGL animation layers cause high resource load</cite>, and elsewhere note teams eventually move such animation needs to a second canvas via deck.gl rather than fighting MapLibre's own render loop for continuous animation. **Since deck.gl is out of scope for you** (not explicitly forbidden, but adds a large dependency for one feature), the practical recommendation is: implement the pulsating alert radius and radar-sweep as a `CanvasSource`/custom style layer with a `requestAnimationFrame`-driven redraw, capped in number (don't animate more than a handful of "live" markers at once — static circle layers with `circle-radius-transition` for the rest), which matches the resource-load warning above.

**4.4 — Isochrones/route vectors offline**: no offline-first, pure-GeoJSON isochrone generator was located in this pass — routing/isochrone tools generally assume a routing-engine backend (OSRM, Valhalla) rather than being pure client-side MapLibre plugins. If NAKABANDI needs true isochrones (drive-time rings around an ATM), this likely means running a small self-hosted OSRM/Valhalla instance against your offline OSM extract rather than finding a client-only library — worth flagging to the team as a scope/infra decision, not a frontend one.

### How this applies to NAKABANDI's screens
- **GIS Map**: MapLibre GL JS + local GeoJSON/vector tiles (already your plan) is confirmed sound and license-clear. The tactical radar-sweep/pulsing-threat-radius visuals are **not available off-the-shelf** — budget them as ~1–2 days of custom `CanvasSource`/canvas-layer work, capped to a small number of simultaneously-animating markers for performance. Static (non-animated) threat radii should just be a styled circle/fill layer, reserving animation for the 1-3 "hottest" active alerts only.

### What could not be confirmed
No open-source, MapLibre-native, offline tactical-ops mapping reference product was found. If one exists it wasn't surfaced by this search pass — worth a narrower follow-up search specifically in defense/GIS OSS communities (e.g. searching GitHub topics `tak`, `cot`, `military-mapping` for TAK-adjacent, ATAK-style web viewers) if the team wants to sink more research time here.

---

## 5. Kinetic Feedback & Consequence UX for High-Stakes Actions

### Findings

**5.1 — [Sonner](https://github.com/emilkowal/sonner) (via its creator's own writeup)**
License: MIT, React. The creator's own account of why it works: <cite index="68-1">the library took off because of its stacking animation, a technique some companies had used internally before but never open-sourced</cite>, and its API deliberately mirrors `react-hot-toast`'s render model because <cite index="68-1">that pattern is simply very good</cite>. **[VERIFIED — creator's own writeup reviewed directly]**

**5.2 — `toast.promise()` for the freeze/dispatch action itself**
A composite skill/reference source lays out the exact pattern needed for "freeze ₹1.5 lakh": <cite index="60-1">use Sonner's `toast.promise()` so a single toast transitions automatically from a loading state to success or error based on how the underlying async call resolves</cite>. Application: fire the freeze action **optimistically** — the case status flips to "Freeze requested" immediately, `toast.promise()` shows a loading→success/error toast wired to the real API call, and the case's stat counters increment immediately (optimistic) and roll back with an error toast + counter decrement if the call fails. This gives the "immediate and tangible" feel your spec asks for without faking the outcome. **[VERIFIED — pattern is standard Sonner usage per its own examples]**

**5.3 — Explicit-confirmation toast variant for irreversible or high-value actions**
Sonner supports a variant purpose-built for this: <cite index="61-1">a toast with a cancel button for confirmations and dismissible warnings that need explicit acknowledgment, for cases where passive dismissal would be ambiguous</cite>, and a stronger variant: <cite index="63-1">a non-dismissible toast — with `dismissible: false` removing the close button — for critical warnings or required acknowledgments where premature dismissal would cause confusion</cite>. Application: for the ₹1.5-lakh-freeze action specifically, use the action+cancel toast (not a blocking modal) so the operator isn't forced to context-switch away from the queue, but the action still requires one explicit click rather than a passive auto-dismiss. Reserve `dismissible: false` only for truly irreversible actions (e.g., confirmed dispatch of a patrol unit, not just "flag for review"). **[VERIFIED]**

**5.4 — React state pattern underlying all of the above: `useOptimistic`**
A working reference implementation shows the exact hook combination: <cite index="67-1">using React's `useOptimistic` for instant UI state changes, wrapped in `startTransition`, together with Sonner for the visible toast feedback</cite>. This is the concrete "stat increment animation" mechanism — the number updates via optimistic state before the network round-trip completes, and Sonner communicates the eventual real outcome. **[VERIFIED]**

### How this applies to NAKABANDI's screens
- **Triage Inbox / Case Dossier "Freeze" and "Dispatch" actions**: `useOptimistic` for instant stat/status change → `toast.promise()` tied to the real mutation → action+cancel (not blocking-modal) confirmation for reversible-but-high-value actions, non-dismissible confirmation only for genuinely irreversible ones. This keeps the operator's flow uninterrupted (your stated constraint) while still making the consequence visible and, on failure, reversible.

---

## Top 3 Recommended Implementation Projects / Boilerplates to Inspect

1. **`plotly/react-cytoscapejs`** (+ `cytoscape.js` core) — the one unambiguous, official, MIT, production-grade dependency in this whole report. Start the Case Dossier graph here; don't hand-roll a Cytoscape/React bridge.
2. **`JohannesKlauss/react-hotkeys-hook`** + **`pacocoursey/cmdk`** together — the correct division of labor is cmdk for the global "search everything" palette and react-hotkeys-hook (with scopes) for the Triage Inbox's row-level single-key actions. Both are MIT and Radix-friendly.
3. **`Sagar-S-R/mm-backend`** (RIFT 2026) — *not* to lift code from (it's an unpolished hackathon repo), but to study its API-contract decision: the backend returns pre-shaped Cytoscape JSON from a dedicated `/graph-data` endpoint rather than making the frontend transform raw rows. Copying that contract shape will save real frontend complexity in NAKABANDI regardless of code quality elsewhere in that repo.

---

## Five-Line Executive Summary

1. Adopt Linear's dark-canvas discipline directly: near-black (`~#0a0a0b`) not pure black, hairline borders instead of shadows for panel separation, a 3-tier font-weight scale, and exactly one non-severity accent color.
2. Use `font-variant-numeric: tabular-nums slashed-zero` (Tailwind's `tabular-nums` utility) on every numeric cell, backed by a self-hosted (not Google-Fonts-runtime) variable JetBrains Mono for the offline constraint.
3. Build the Triage Inbox's keyboard triage on `react-hotkeys-hook` (scoped, row-level single-key actions) plus `cmdk` (global search), not a single all-purpose library — no OSS library covers both needs at once.
4. Have the backend's graph endpoint return pre-shaped Cytoscape.js elements with server-side hop-limiting/edge-pruning built in from day one (mirroring the `crypto-tracer` and `mm-backend` peer-project pattern), rather than shipping raw transaction rows to the frontend.
5. For high-stakes actions (freeze, dispatch), use `useOptimistic` + `toast.promise()` (Sonner) for instant, reversible feedback, reserving non-dismissible confirmation toasts only for genuinely irreversible actions — this satisfies "immediate and tangible" without blocking-modal friction.

---

## What I Could Not Confirm

- **No production-grade, well-starred, MIT/Apache-licensed "SOC/fraud triage cockpit" reference exists in OSS** that matches NAKABANDI's caliber target (Gotham/Reactor-tier). The repos found in Section 1 and 2 are hackathon/student projects — useful for pattern-spotting (severity-is-color-only conventions, pre-shaped graph API contracts, hop-limiting), not for architecture-copying.
- **No dedicated open-source MapLibre "tactical ops mapping" library** (radar sweep, pulsing threat radius as a packaged plugin) was found — this needs custom `CanvasSource`/canvas-layer implementation; budgeted as a small bespoke build, not a library integration.
- **No canonical open-source "SVG circular countdown timer for alert SLAs" component** was found; recommend a small bespoke component rather than a dependency.
- Palantir Gotham and Chainalysis Reactor UI internals are **not publicly documented at the component/code level** (both are closed-source, enterprise products) — everything cited about Reactor above comes from Chainalysis's own public product marketing and workflow documentation, not a design teardown of actual screens or code. Treat those citations as validating the *workflow shape* (graph-centric, hop-tracing, annotation, export-to-report), not as a source of implementable UI code.
- Did not verify `cytoscape-cola`'s license or repository directly (only saw it referenced inside a peer project's README) — confirm this independently before adding it as a dependency; if unavailable/unclear, `cose-bilkent` (also MIT, widely used) is a safe fallback force-directed layout for Cytoscape.js.
- Did not locate an offline-capable, client-only isochrone/routing library — if NAKABANDI's spec truly needs isochrone rings around ATMs, this is likely an infrastructure decision (self-hosted OSRM/Valhalla) rather than a frontend library choice, and should be scoped separately.
