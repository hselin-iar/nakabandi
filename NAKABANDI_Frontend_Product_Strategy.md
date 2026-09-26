# NAKABANDI — Frontend & Product Strategy

*A critical redesign brief, grounded in DOC1 (product spec), DOC2 (architecture), the API/Data Catalog audit, and the current-website audit + screenshots. Written for a team that already has a real backend and a working but generic frontend — this is about closing that gap, not starting over.*

---

## 0. The verdict, up front

Your backend is more honest and more sophisticated than your frontend lets on. You built abstention, calibrated probabilities, ETA-vs-window interceptability, proportionality-capped liens, a hash-chained audit log, and a tamper-evident evidence pack pipeline — and then wrapped it in the same eight-item sidebar, KPI-card-grid, generic-data-table shell that every hackathon "AI dashboard" ships. Worse, in at least one place the frontend actively **contradicts** the architecture's own stated principle (the alert detail's "Prediction Assessment" panel shows feature-attribution-style percentages — exactly the causal-looking explanation format DOC1 §1.5 and DOC2's risk register (T12) tell you not to build), and in another place the frontend's flagship credibility screen (`/evaluation`) is **entirely fake** — hardcoded fixtures, not wired to any real endpoint, because the real endpoint was specified in DOC2 but never built.

That's the actual gap: not "make it prettier," but **make the interface tell the truth the backend already knows, and stop it from telling truths the backend doesn't back up.**

The redesign below does three things:
1. Kills the flat, resource-mirrored navigation and replaces it with a structure organized around the six questions a real investigator needs answered (what / where / when / why / can-we / what-do-I-do), which is what you were asked to design for and what the current IA does not do.
2. Surfaces roughly a dozen backend capabilities that are fully built and completely invisible in the UI today (evidence-pack generation, timing-decay probabilities, proportionality safeguards, live metrics, dynamic action eligibility) — this is the highest-value, lowest-risk work available to you, because it requires **zero new backend logic**.
3. Proposes a small number of genuinely new interaction patterns (an "interception radar," a hierarchical drill-map tied to zoom, a directed fund-flow timeline) that are assembled entirely from primitives you already compute, using libraries you've already committed to (MapLibre, Cytoscape.js, Recharts) — no new dependencies, no schedule risk.

Everything below is tagged with a feasibility marker so you know exactly what's free and what costs something:

| Tag | Meaning |
|---|---|
| 🟢 **AVAILABLE** | Buildable today. The API already returns this data to a wired frontend. |
| 🟡 **UNLOCK** | Backend already computes and stores this. Nobody calls the endpoint yet — it's a wiring job, not an engineering job. |
| 🟠 **SMALL EXTENSION** | A small, additive backend change (a new field, a thin new router reading an existing table). Doesn't touch domain logic or violate an architectural invariant. |
| 🔴 **NEW CAPABILITY** | Genuine new backend work. Scope it deliberately. |
| ⛔ **DON'T BUILD** | Scope creep. Skip it, even if it sounds cool. |

---

## 1. Product diagnosis

### 1.1 What actually works — keep these, don't relitigate them

- **The countdown-to-expiry pattern on alerts** (red at ≤15 min) is the single most correct piece of UX in the product. It's the whole point of the system — cash-out is a race against a clock — and it's already built. Don't touch it; propagate it further (see §3, §7).
- **Role-based scoping and masking** is real, not decorative: bank roles see only their own bank, district officers see masked refs, `Scope` is enforced at the repository level. This is worth being visibly proud of in the demo, not hiding behind a role pill in the topbar.
- **The map's honest suppression of low-count cells** (k-threshold, shown in the current UI as "8 cells suppressed below k-threshold") is a genuinely rare thing to see in a hackathon GIS dashboard — most teams would rather show a denser, more impressive-looking heatmap. Keep this and make it *more* visible, not less; it's a credibility asset (§9).
- **Graceful degradation** (WebGL fallback to table view, SSE fallback to polling) is real engineering discipline. Fine as-is.
- **The audit page's live cryptographic verification** (`/audit/verify` actually recomputes the hash chain against the live backend, not a canned response) is correctly built and correctly wired. Leave it alone.

### 1.2 What's actively wrong — fix these, they're not cosmetic

1. **The evidence panel violates your own architecture's stated principle.** DOC2 §2.8 (risk T12) says explicitly: "Evidence statements may be read as causal explanations… Labelled as 'evidence from features', not 'why the model decided'." The current Alert Detail screen (page 3 of the site audit) shows a "Prediction Assessment" block with **"Velocity & Hop Cadence +38%", "Geographic Proximity to Hotspot +29%", "Mule Account Co-occurrence +18%"** — percentage deltas that read exactly like model feature-importance/SHAP output. That is precisely the format your own risk register warned you against. The backend already returns something better and already-narrative: `forecast.evidence[]` with `text_en` statements like *"Target location matches 4 prior cash-outs associated with this mule cluster."* You built the honest version and shipped the dishonest-looking one. Fix: replace the percentage bars with the narrative evidence cards the API already returns. 🟡 UNLOCK — no backend change, this is purely a frontend rewrite.

2. **The flagship credibility screen is fake.** `/evaluation` renders entirely from hardcoded fixtures (`FIXTURE_EVAL_FEEDBACK_OFF/ON`) in the frontend code. There is no REST route for it — DOC2 §2.4 *specifies* `GET /evaluation/runs` and `GET /evaluation/runs/{id}`, but they were never implemented, because `main.py` is architecturally forbidden from importing the `evaluation` module directly (the hidden-truth firewall, invariant 1). That firewall is about not letting the live API import the oracle client — it does **not** forbid a thin router reading the already-existing `experiment_runs` / `experiment_metrics` tables that the offline harness writes to. This is fixable without touching the firewall. If a judge asks "how do you know your model is any good," right now you show them a fixture. That's the worst possible screen to be caught faking. 🟠 SMALL EXTENSION.

3. **Raw ULIDs are shown to human officers as primary identifiers.** The alerts table and alert detail drawer show `01M3BE7T1T4XENZYFN5Q3VTM8W` as the headline identifier for both the alert and its cluster. A cyber-cell investigator glancing at a table under time pressure cannot parse that, and it doesn't need to be there — `cluster_ref` (`CLU-UP-0012`) is already a human-legible identifier returned by the same endpoint. This is a five-minute fix with an outsized trust payoff: nothing says "half-finished hackathon project" like a raw database key on screen.

4. **The command dashboard computes things the backend already computed better.** `GET /analytics/timeseries` and `GET /analytics/live-metrics` exist, are implemented, and are unused — the dashboard instead scans cached `/alerts` results client-side to fake a sparkline and KPI numbers (confirmed in the catalog: "Mock sparkline," "Derived from alert cache"). This isn't just wasted backend work; it means the two numbers most likely to be quoted in a judge Q&A (current alert-count, mass) are computed by a different method than the one your own analytics module considers canonical. 🟡 UNLOCK.

5. **The demo console — the screen you will be operating live in front of judges — was captured mid-failure.** The screenshot shows `Sim Time: 01 Jan 1970, 00:00:00`, `Speed: 60x`, state `STALLED`, and a raw `Engine Error: HTTP 500` banner. Whatever the actual bug is, fix it before anything else in this document — a broken demo console is not a UX problem, it's a "you lose before you open your mouth" problem. Separately, once it's fixed: the error banner gives the operator zero next step. A demo console's entire job is to fail *legibly* — "world-sim unreachable, retry / check logs," not a raw HTTP status. This is the one screen where "boring and bulletproof" beats "impressive."

6. **Two backend documents disagree with each other, and the UI has silently picked a side you should confirm on purpose.** These aren't nitpicks — each one changes what a real UI component should look like:
   - **Ladder rungs.** DOC1 §1.2 (M6) defines a **3-rung** ladder: L1 (bank-side lien), L2 (branch/ATM/agent alert), L3 (field dispatch). The API catalog's own example payload returns `"ladder_level": "L4"` for a dispatch case, and documents the field as accepting `NONE, L1, L2, L3` **or** "domain levels L0–L5." The current UI shows `L3 · Dispatch`. Before you build a "ladder visualization" (recommended below), get your backend teammate to state definitively: is this three rungs or six? A ladder widget designed for three positions and fed six values will look broken on stage.
   - **Bank-nodal permissions.** DOC2 §2.4 states plainly: *"bank_nodal may only acknowledge."* The audit's own `GET /auth/me` example response for `bank_nodal` lists permissions `["ACKNOWLEDGE", "MARK_OUTCOME", "REQUEST_HOLD", "VIEW_ALERTS"]` — including `REQUEST_HOLD`, which DOC1's whole legal framing treats as an LEA→bank *ask*, not something a bank grants itself. If a bank_nodal principal can call `request_hold`, that's either a documentation error or a real permission bug with human-in-the-loop implications (invariant 7 exists specifically so that only an authenticated officer role can request an external effect). Resolve this before you build the action bar around `allowed_actions` — it decides what buttons a bank_nodal user should ever see.
   - **Cell resolution.** DOC2 §2.3 defines the default grid cell as 5 km (`grid_km`, configurable). The current Map page labels the option "Equirectangular Cell (**~27km**)". Either the config was changed for the demo world and DOC2 is stale, or the label is wrong. Minor on its own, but it's exactly the kind of inconsistency a technically literate judge will probe ("why 27, not 5?") — have an answer ready either way.

### 1.3 What's missing — built and invisible

The API/Data Catalog's own "Frontend Data Opportunity Map" already caught most of this; it's worth taking seriously precisely *because* it came from an audit of your actual code, not from a wishlist. The single highest-leverage fact in the entire project is this: **every item below requires no new backend work.**

| Capability | Where it lives | Currently | Cost to expose |
|---|---|---|---|
| Timing decay (`p30`/`p60`/`p120`, `residual_mass`) | `GET /alerts/{id}` → `forecast.timing` | Not displayed at all | 🟢 AVAILABLE |
| Narrative evidence (`evidence[].text_en`) | `GET /alerts/{id}` → `forecast.evidence` | Replaced by the mis-framed percentage bars (§1.2.1) | 🟢 AVAILABLE |
| Proportionality safeguard (`disputed_paise`, `proposed_paise`, `ratio`, `magistrate_report_reminder`) | `GET /alerts/{id}` → `interception[].proportionality` | Hidden entirely | 🟢 AVAILABLE |
| Dynamic `allowed_actions` | `GET /alerts/{id}` | Action bar is hardcoded per role, not per this field | 🟢 AVAILABLE |
| Court-ready evidence pack (PDF, SHA-256, s.63 draft certificate) | `POST /alerts/{id}/evidence-pack`, `GET /evidence-packs/{id}/download` | Zero buttons; fully unused | 🟢 AVAILABLE |
| Historical risk time series | `GET /analytics/timeseries` | Dashboard fakes a sparkline instead | 🟡 UNLOCK |
| Live operational metrics (`expected_mass`, `active_locations`) | `GET /analytics/live-metrics` | Dashboard computes an approximation from cached alerts | 🟡 UNLOCK |
| Best-response-unit + ETA | `GET /alerts/{id}` → `interception[].best_unit` | Rendered as a plain text badge | 🟢 AVAILABLE (mapping it needs 🟠, see §6) |
| ETag-based heatmap caching | `GET /analytics/heatmap` | Not leveraged; risk of flicker on refresh | 🟢 AVAILABLE |
| Evaluation sweep results | Offline harness, tables exist | No REST route; frontend uses fixtures (§1.2.2) | 🟠 SMALL EXTENSION |

### 1.4 What's unnecessarily complicated

- **Eight top-level nav items** (Alerts, Clusters & Cases, Map, Evaluation, Ops, Outbox, Audit, Demo) mirror API resources, not investigator tasks. A resource-per-nav-item IA is what you get when the frontend is built by walking the OpenAPI spec top to bottom rather than by asking what an officer does in a shift.
- **Clusters and Cases are already the same object at two zoom levels, but you've built two top-level surfaces for them.** Look at your own Case Detail page: its right column *embeds* the ClusterGraph component. A case **is** a cluster once it has a brief attached (`casework` module literally wraps `graph`'s cluster). Maintaining `/clusters` and `/cases` as two separate primary nav items, each with its own list-and-detail pattern, duplicates UI for no product reason (§3).
- **Outbox is plumbing wearing a nav item's clothes.** It's a delivery log for a mechanism (webhook/SMS/email retries) that officers don't act on — it's useful for debugging and for a bank nodal officer checking their own delivery, not as a peer of Alerts and Map in the primary sidebar.
- **Evaluation, Ops, and Audit are three separate top-level destinations answering one underlying question — "can I trust this system?" — from three different angles** (statistical trust, operational health, tamper-evidence). They don't need to be three sidebar items with three different visual languages; they can be three tabs under one destination.

---

## 2. Product concept

### 2.1 The mental model to design around

The current product's implicit mental model is: *"a set of admin panels over a database."* Alerts is a table over the `alerts` table. Clusters is a viewer over the `clusters` table. Cases is a viewer over `cases`. That's a defensible way to build an MVP fast — it is not a product concept, and it's why the interface reads as generic.

The actual product, per DOC1's own root insight, is much sharper than its current shell: **digital layering is instant and unbounded; cash-out is physical and constrained.** The entire system exists to exploit the one moment where an infinitely fast, infinitely branching digital process has to collapse into a single person standing at a single machine at a single time. Everything NAKABANDI computes — cluster resolution, hierarchical location forecast, timing mixture, interceptability, the ladder — is in service of **naming that moment before it happens** and **deciding, in the time available, what the cheapest lawful way to be there is.**

That's not a dashboard. That's a **checkpoint** — which is what the product is already named after, and which the current UI never once evokes. "Naka" (checkpoint) is invisible in a product whose subtitle is the generic "Financial Crime Detection Platform."

**Proposed mental model for the interface: NAKABANDI is a live race with two runners and one clock.** Runner one is the money, whose position is a probability distribution over places and a probability curve over time. Runner two is your nearest lawful hand — a lien, an alert, a patrol — whose position is an ETA. The interface's only job, at every level of zoom (a single alert, a district heatmap, a whole state), is to make that race visible and make the officer's decision about which lever to pull obvious. Every screen should be answerable against the six questions you were asked to design for:

| Question | Where it should be answered |
|---|---|
| What is happening | Alert focus panel: target, severity, cluster, category |
| Where the risk is | Map (live + potential layers), alert's ranked location list |
| When it's likely | Timing-decay curve (p30/p60/p120), window countdown |
| Why the system believes it | Narrative evidence cards (not attribution bars) |
| Whether intervention is possible | ETA vs. window verdict, ladder recommendation |
| What the human can do | `allowed_actions`-driven action bar, proportionality panel |

If any screen in the redesign can't be mapped to at least one of these six, cut it or fold it into another screen.

### 2.2 Design consequences of the concept

- **Abstention must be visible, not hidden.** DOC1's whole differentiator (D1) is predicting hierarchically and *abstaining honestly* at the finest resolution when evidence is thin. A UI that always shows a confident-looking pin for every alert is lying about a system that was specifically built not to. Abstained forecasts should visibly look different (greyed, widened, labeled "district-level only — insufficient confidence for a specific location") rather than being silently rounded up to the nearest resolution.
- **The ladder is a recommendation with a reason, not a badge.** "L3 · Dispatch" as a colored pill hides the actual product: the system chose the *least intrusive sufficient action*, and it chose it because of a specific comparison (ETA vs. window, channel, unit availability). Show the reasoning path, not just the conclusion (§7.5).
- **Proportionality is not a compliance footnote, it's a headline feature.** A system that can *only* propose amount-capped, time-boxed, complaint-anchored liens — and structurally cannot construct a whole-account freeze — is a genuine differentiator against every "just freeze the account" instinct a real deployment would otherwise have. Currently this is completely invisible in the UI. Make it load-bearing, visually.

---

## 3. Information architecture

### 3.1 From eight resources to five destinations

| Current nav (8 items, resource-shaped) | Proposed (5 destinations, task-shaped) |
|---|---|
| Dashboard (`/`) | **Command** — ambient, mostly folded into a persistent header ticker (§3.2), not a full page most roles need to visit |
| Alerts (`/alerts`, `/alerts/:id`) | **Triage** — the hero surface, unchanged in scope, redesigned in depth (§4.2) |
| Map (`/map`) | **Deployment** — strategic heatmap, same scope, adds unit layer + hierarchical drill |
| Clusters & Cases (`/clusters`, `/cases`) | **Investigate** — merged. Case is primary; cluster graph is an embedded panel, not a sibling top-level page |
| Evaluation (`/evaluation`) | Tab inside **System Integrity** |
| Ops (`/ops`) | Tab inside **System Integrity** |
| Audit (`/audit`) | Tab inside **System Integrity** |
| Outbox (`/outbox`) | Demoted: a panel inside Alert Detail (per-alert delivery log, which is the data an officer actually needs) + a secondary admin route, not a primary nav item |
| Demo (`/demo`) | Unchanged in placement (already correctly gated and compiled out of prod builds). Fix reliability (§1.2.5) before anything else |

This is not "hide things to look minimal" — every existing screen still exists and every permission gate still applies. It's collapsing three questions that are really one question (System Integrity), and demoting two screens that are plumbing, not officer workflow (Outbox, and the standalone Dashboard).

### 3.2 Make the dashboard's real value ambient, not a destination

Look at what the current Command Centre dashboard actually contains: five KPI cards and eight navigation tiles. The KPI cards (open alerts, critical count, disputed total, hotspot count, peak intensity) are exactly the numbers an officer needs to see *before deciding whether to even open the app further* — which means they belong in a **persistent header strip visible from every screen**, not gated behind a "go to the dashboard first" click. The eight navigation tiles are just the sidebar, restated as cards; once the nav itself is task-shaped (§3.1), that page has nothing left to justify a dedicated route for most roles.

Keep a landing destination — but make it thin: the live-metrics ticker (wire `/analytics/live-metrics` and `/analytics/timeseries`, 🟡 UNLOCK) plus the single soonest-expiring critical alert as a call to action, and nothing else. The eight-tile launcher grid can go.

### 3.3 Alert focus as shared state, not a page you navigate to

The current build already has two different "look at this alert" components that don't talk to each other: `AlertDetail` (a slide-over drawer, opened from the Alerts table) and `HotspotDrawer` (a slide-out on the Map, listing "contributing active alerts" with links back to `/alerts/:id`). That's redundant UI for the same underlying idea. Unify it: a single **Alert Focus panel** component, addressable from Triage, Deployment (map), and Investigate (case/cluster) alike, that opens *in place* without a full route transition. Clicking a hotspot on the map, a row in the alerts table, or a top-location entry in a case brief should all open the exact same component with the exact same content. This is both a UX win (no jarring page-to-page navigation for what is conceptually "look closer at this one thing") and an engineering win (one component instead of two divergent ones).

---

## 4. Screen-by-screen experience

### 4.1 Command (ambient header, thin landing page)
- **Purpose:** orient in under two seconds — is anything on fire right now.
- **Must understand immediately:** count and severity of open alerts in scope; time to the soonest critical window closing.
- **Data:** `/analytics/live-metrics` (🟡 UNLOCK), `/analytics/timeseries` (🟡 UNLOCK) for the trend, `/alerts?view=queue` for the soonest-expiring critical.
- **Interaction:** click the ticker → Triage, filtered to critical/open. That's the only interaction it needs.
- **Do NOT show:** the eight-tile module launcher (redundant with nav), per-cluster financial totals (that's Investigate's job), anything requiring a second click to become actionable.

### 4.2 Triage (Alerts inbox + Alert Focus) — the hero surface
- **Purpose:** this is where 90% of officer time lives; DOC1 calls it the hero use case for a reason.
- **Must understand immediately, per alert:** target facility (human name, not ULID), severity, time remaining, and — new — the ladder recommendation *with its reason*, not just its label.
- **Table changes:** drop the raw ULID as the primary label; lead with `cluster_ref` + target name. Keep the queue/backlog split already implemented (`view=queue|backlog`, catalog finding #15) but make it visible as a UI concept — "N alerts deferred to protect your attention" is a genuinely good, ethically-grounded UI idea that's currently just a query parameter, not a surfaced feature. Surface it as an **attention-budget strip**: alerts shown / alert budget for this shift / deferred count, sourced directly from the budget policy already enforced server-side (DOC1 §1.5 principle 6). This turns an internal safety mechanism into a visible trust signal: *"we are deliberately not showing you everything, on purpose, so you don't rubber-stamp."*
- **Alert Focus panel — rebuild these four blocks specifically:**
  1. **Timing-decay curve**, not a static countdown alone: plot `p30/p60/p120` against `residual_mass` as a curve that visually depletes as `elapsed_min` grows (Recharts area/line chart — no new library). This turns three numbers into one legible shape: "chance of cash-out climbs to ~80% by the hour mark, and we're already 12 minutes in."
  2. **Evidence, as narrative cards**, one per `evidence[]` item, `text_en` verbatim, no percentages, no bars. Delete the current "Velocity & Hop Cadence +38%" panel outright (§1.2.1).
  3. **Ladder-as-decision-path**, not a colored pill: show the comparison that produced the recommendation — predicted window vs. best unit's ETA, with the margin, and the `reason_code`/`reason_params` already returned by the API rendered in plain language ("Dispatch is feasible: patrol UNT-UP-LKO-03 is 14.5 min out against a 45 min window — 30.5 min of margin"). If the verdict is NOT_INTERCEPTABLE, say why (no unit in reach) rather than just greying the dispatch button.
  4. **Proportionality strip**, always visible when a lien is proposed, not tucked away: disputed amount, proposed amount, ratio as a bounded bar (never able to visually exceed 100%), review/expiry timestamps, and the magistrate-report reminder as an explicit line, not a tooltip. This is your legal safety mechanism *and* your best "we are not a blanket-freeze tool" talking point — put it where a judge glances, not where they have to dig.
- **Action bar:** render buttons strictly from `allowed_actions` returned by the API (🟢 AVAILABLE), not a role-based hardcoded set. This is a correctness fix, not just a UX one — see the bank_nodal/`REQUEST_HOLD` discrepancy in §1.2.6.
- **New, one-click: "Generate Evidence Pack."** Wire the three unused endpoints (`POST /alerts/{id}/evidence-pack`, `GET /evidence-packs/{id}`, `GET /evidence-packs/{id}/download`) directly into the alert focus panel. Show the SHA-256 and the audit-head-hash it's anchored to, not just a download link — that hash is the actual point (tamper evidence), and hiding it behind a plain "download PDF" button wastes the best piece of forensic theatre you have. 🟢 AVAILABLE.
- **What NOT to show here:** the cluster's full account-level graph (that belongs to Investigate — link out, don't inline a second graph viewer); anything from Evaluation/Ops (system health has nothing to do with this one alert).

### 4.3 Deployment (Map)
- **Purpose:** the strategic view — where should attention and units be positioned over the next hours, not this one alert.
- **Must understand immediately:** which few cells actually matter right now, at whatever zoom level is open.
- **Change 1 — resolution should follow zoom, not a disconnected dropdown.** Currently "Live/Potential" and "District/Cell/Location" are separate dropdown controls, decoupled from the map's own zoom/pan. Bind them: zoomed out shows district rollups, zooming in smoothly reveals cell-level, then individual points — this is a standard, officially documented MapLibre pattern (data-driven layer visibility by zoom expression), not a new library. This directly *dramatizes* D1's hierarchical-forecast-with-abstention design decision instead of hiding it behind a menu.
- **Change 2 — abstained/low-confidence cells should look abstained.** Don't render every returned cell at full saturation; fade cells whose confidence sits below the abstention threshold, and label them "insufficient evidence" rather than coloring them like every other data point. Honesty about uncertainty is a stated design principle (§2.2) — make the map say so.
- **Change 3 — put response units on the map.** This is the one item in this whole document that needs a small backend extension: `interception[].best_unit` returns `unit_id`, `unit_kind`, `eta_min` but no coordinates. The `geo.Unit` entity already stores `lat`/`lon` (DOC2 §2.3) — it's modeled, just not exposed. Add either a `GET /geo/units` endpoint (mirrors the existing `/geo/locations` pattern exactly) or include lat/lon inline on `best_unit`. 🟠 SMALL EXTENSION — this is the single backend ask in the whole document, and it's a one-afternoon addition, not a redesign.
- **Change 4 — the Interception Radar** (see §7.1 for the visualization spec): once units have coordinates, render the assigned unit, the target, and an animated ETA vector between them directly on the map for any alert opened from here — using MapLibre's own documented "animate a point along a route" + gradient-dasharray-line patterns. This is assembled entirely from data you already compute (best_unit + eta_min + target lat/lon) plus one small extension; it is not a new subsystem.
- **What NOT to show:** individual alert action buttons (this is a planning view, not a triage view — clicking a hotspot should open the same Alert Focus panel as everywhere else, read-only-by-default, with a link to act in Triage).

### 4.4 Investigate (merged Clusters + Cases)
- **Purpose:** the forensic view — how big is this network, who's in it, where has it cashed out before, and is it ready for a brief.
- **Structure:** a case-first list (search, single-complaint filter — keep as-is, it works), and a detail view that is the current Case Detail page, unchanged in content, with the cluster graph as an embedded, expandable panel rather than a separately-navigable top-level page. `/clusters/:id` still exists as a deep link (e.g., from an alert's `cluster_ref`) but is no longer a parallel primary destination with its own list view.
- **New: fund-flow timeline, not just a topology graph.** The existing Cytoscape graph shows *who* is connected to *whom* — it does not show *when* or *how fast*. `FundHop` already carries `layer` (1–12) and both `event_at`/`observed_at`. Re-render the same graph data with Cytoscape's built-in `breadthfirst` layout, `directed: true`, ordered left-to-right by hop layer instead of force-directed — this is a configuration change to a library you've already chosen, not a new dependency (Cytoscape's breadthfirst layout is documented and designed for exactly this: ordering a DAG by traversal depth). Color or animate edges by hop speed (fast hops vs. slow, from the same timing-mixture concept M2 already models) and you've turned a static "who's connected" diagram into a visualization of DOC1's actual root insight: *layering is instant, cash-out is the physical bottleneck.* This is the "why isn't this just a normal dashboard" moment for the network view specifically.
- **What NOT to show:** live countdown timers (that's Triage's job — a case is retrospective/aggregate, not a live-window object).

### 4.5 System Integrity (Evaluation + Ops + Audit, as tabs)
- **Purpose:** answer "can I trust this system" from three angles that share an audience (analysts, admins) but not a workflow with Triage/Deployment — hence tabs under one destination, not three peers of Alerts in the primary nav.
- **Evaluation tab:** fix the fake-data problem first (§1.2.2) — wire real `experiment_runs`/`experiment_metrics` via a thin new router. Once real, keep the existing hero-score-ring + metrics table + cold-start chart layout; it's a reasonable design, it's just currently connected to nothing.
- **Ops tab:** already correctly wired to `/system/metrics`; keep the stage-latency waterfall as-is, it's a genuinely good use of the data (pipeline stage p50/p95/max is exactly what the catalog itself flags as an underused "Live Pipeline Telemetry HUD" opportunity, and the current Ops page already does most of this — don't rebuild what isn't broken).
- **Audit tab:** already correctly wired and already does the right thing (live chain verification, not a canned banner). Leave it functionally as-is; only change is its location in the nav.
- **What NOT to do:** don't try to unify these into one shared visual widget — a Brier score, a p95 latency, and a hash-chain status are different enough claims that forcing them into one "trust score" would be exactly the kind of dishonest compression this whole document argues against. Tabs, not a single meter.

### 4.6 Outbox (demoted)
- **Purpose:** debugging and per-alert delivery confirmation, not officer workflow.
- **Change:** the delivery log for a *specific* alert (already returned inline in `GET /alerts/{id}` as `deliveries[]`) should render inside that alert's focus panel — an officer checking "did the bank actually get notified" shouldn't have to leave the alert to find out. Keep a thin, permission-gated `/outbox` route for admins doing cross-alert debugging, but remove it from the primary sidebar.

### 4.7 Demo Console
- **Priority zero: fix the reliability bug shown in your own screenshot** (§1.2.5) before any of the rest of this document matters.
- Once stable, the console itself is well-scoped and correctly gated (`VITE_DEMO_CONSOLE=false` compiles it out of production, forward-auth gates the proxy) — resist the urge to add anything to it beyond error legibility. This is infrastructure, not product; time spent polishing it is time not spent on §4.2–4.4.

---

## 5. Core operational workflow

### 5.1 The actual pipeline, traced

This is the real, synchronous chain (DOC2 §2.1, confirmed against the API catalog's pipeline description):

```
complaint ingested → intake.ingest
   → graph.resolve(account) → cluster_id (or novel)
   → forecast.generate(cluster, complaint, as_of=now) → ranked locations (3 resolutions) + timing mixture + evidence
   → interception.assess(forecast) → ETA vs window → verdict → ladder level + lien proposal (capped)
   → alerting.raise_or_merge → alert row + outbox rows (same transaction)
   → outbox worker → SSE / email / SMS / signed bank webhook (async, retried)
   → officer acts (Principal required) → request_hold / notify_station / dispatch / override
   → (if hold) bank-sim verifies signature → applies lien → callback → action status updates
   → lagged CashOutObservation arrives → outcome reconciled (hit/miss/late) → ClusterLocationStat updated (feedback)
```

Every arrow above except the *very last* one (bank-sim → callback → status update, and outcome reconciliation) happens **inside a single request path** with a documented p95 budget (under 2s to alert-visible, excluding delivery). That's a strong claim you should make explicitly in the demo narrative (§9) — the frontend currently doesn't communicate that this is one continuous, fast, causal chain at all; it presents each stage as a separate screen with no visual sense that they're seconds apart.

### 5.2 Where the frontend should help decide, not just display

- **At forecast time:** the resolution-and-abstention decision is *already made* by the backend (D1). The frontend's job is to represent that decision honestly (§4.3, §2.2) — this is display, correctly, because the decision isn't the officer's to make.
- **At interception time:** the ladder *recommendation* is computed, but the ladder rung the officer actually authorizes is a human decision (invariant 7). This is the one point in the whole flow where the UI should visibly slow down and ask for a reason on override (already partially built — `override` requires a mandatory justification) — keep that friction, it's correct, don't streamline it away for a smoother demo.
- **At hold-request time:** the proportionality panel (§4.2.4) exists specifically so a human can *see* the constraint before confirming, not discover it after. This is decision support, not display — make the proposed amount field visually incapable of exceeding the disputed amount (disable the input past that value, don't just validate on submit).

### 5.3 A more powerful representation than a page sequence

The workflow above is fundamentally a **single object's timeline** — one complaint, one cluster resolution, one forecast, one interception assessment, one alert, N actions, one outcome — currently scattered across Alerts, Clusters, and Outbox as if they were unrelated resources. Consider a **single scrubbable timeline view per complaint/alert** (reachable from the Alert Focus panel as an expandable section, not a new top-level screen) that shows this exact chain as a horizontal sequence of timestamped events — ingest → cluster resolve → forecast → assess → alert → each delivery → each action → outcome — using the `timeline[]` array the API *already returns* inline on `GET /alerts/{id}` (🟢 AVAILABLE, currently rendered as a plain bulleted "Evidence & Audit Trail" list per the screenshot). Re-rendering that same array as a horizontal timeline rather than a vertical bullet list is a small change with a real payoff: it makes the "seconds, not hours" speed claim visible instead of asserted.

---

## 6. Data → UI mapping

This extends the catalog's own opportunity map with the additional items this document proposes. Nothing here invents a field that doesn't exist; where a small extension is genuinely needed, it's marked and justified.

| UI element | Backend data | Endpoint(s) | Feasibility |
|---|---|---|---|
| Attention-budget strip | `view=queue\|backlog`, `is_deferred`, `is_probe` | `GET /alerts` | 🟢 AVAILABLE |
| Timing-decay curve | `timing.p30/p60/p120`, `residual_mass`, `elapsed_min` | `GET /alerts/{id}` | 🟢 AVAILABLE |
| Narrative evidence cards | `forecast.evidence[].text_en` | `GET /alerts/{id}` | 🟢 AVAILABLE |
| Ladder-as-decision-path | `interception[].reason_code/params`, `window_min`, `best_unit.eta_min` | `GET /alerts/{id}` | 🟢 AVAILABLE (pending the L1–L3 vs L0–L5 resolution, §1.2.6) |
| Proportionality strip | `interception[].proportionality.*` | `GET /alerts/{id}` | 🟢 AVAILABLE |
| Dynamic action bar | `allowed_actions[]` | `GET /alerts/{id}` | 🟢 AVAILABLE |
| Evidence pack + hash | `sha256`, `audit_head_hash`, `download_url` | `POST /alerts/{id}/evidence-pack`, `GET /evidence-packs/{id}/download` | 🟢 AVAILABLE |
| Command ticker | `expected_mass`, `alert_count`, `active_locations`; hourly `points[]` | `GET /analytics/live-metrics`, `GET /analytics/timeseries` | 🟡 UNLOCK |
| Zoom-bound resolution switching | `level=district\|cell\|location` cells | `GET /analytics/heatmap` | 🟢 AVAILABLE (frontend logic change) |
| Abstention-aware map styling | forecast `abstained` flag, per-level `confidence` | `GET /alerts/{id}` (per-alert), heatmap `legend`/`suppressed_count` (aggregate) | 🟢 AVAILABLE |
| Interception Radar (unit + ETA vector on map) | `best_unit.unit_id/kind/eta_min` + target lat/lon (`geo.locations`) | `GET /alerts/{id}`, `GET /geo/locations` | 🟠 needs unit lat/lon exposed — **the one backend ask** |
| Fund-flow directed timeline | `FundHop.layer`, `event_at` (via cluster graph nodes/edges) | `GET /clusters/{id}` | 🟢 AVAILABLE (Cytoscape config change only) |
| Evaluation tab (real data) | `experiment_runs`, `experiment_metrics` | none exists yet — DOC2 specifies `GET /evaluation/runs[/{id}]` | 🟠 SMALL EXTENSION |
| Per-alert delivery log inline | `deliveries[]` | `GET /alerts/{id}` (already inline!) | 🟢 AVAILABLE — literally already in the payload, just not rendered there |
| Horizontal event timeline | `timeline[]` | `GET /alerts/{id}` | 🟢 AVAILABLE |
| Human-legible identifiers | `cluster_ref`, `target.name` | already returned everywhere | 🟢 AVAILABLE |
| ETag-based heatmap refresh | `ETag` header, `heat.version` SSE event | `GET /analytics/heatmap`, `GET /stream` | 🟢 AVAILABLE |

**What this table does not contain, on purpose:** any field that isn't already in the schema, and any endpoint that doesn't already exist except the two explicitly marked extensions (unit coordinates; evaluation runs). That's deliberate — the instruction was not to invent backend capability, and it turns out you don't need to. Almost the entire redesign is a wiring and framing exercise, not an engineering one.

---

## 7. Visualization & interaction strategy

Each item below states its analytical purpose first — visualization for its own sake is exactly what you were told to avoid, and it's what a lot of hackathon GIS/AI dashboards default to.

### 7.1 Interception Radar (map-embedded)
**Purpose:** answer "can we get there in time" as a single glance, not a mental subtraction of two numbers.
**Data:** target location (lat/lon, already available), `best_unit` + `eta_min` (needs coordinates, §4.3), `window_min`.
**Pattern:** MapLibre GL JS supports both a documented "animate a point along a route" example and a documented gradient-dasharray line technique — combine them: draw the unit-to-target line with a dash pattern that visually "fills in" proportional to elapsed time against the ETA, so the officer sees the unit's progress toward the target the way a delivery-tracking map shows a courier, without needing a live GPS feed (it's a computed animation driven by `eta_min`, not a real telemetry stream — say this plainly in the demo, don't imply live GPS tracking that doesn't exist).
**Feasibility:** 🟠 — blocked only on exposing unit coordinates (§4.3, one small extension). Everything else is your existing map stack.

### 7.2 Timing-decay curve
**Purpose:** turn three point-probabilities (p30/p60/p120) into a shape, because a shape communicates "climbing fast" or "already flat" in a way three numbers in a row do not.
**Pattern:** Recharts area chart, x-axis = minutes elapsed, y-axis = cumulative cash-out probability, with a vertical marker at "now" (driven by `elapsed_min`) and the window boundary shaded. No new library.
**Feasibility:** 🟢 AVAILABLE.

### 7.3 Hierarchical drill-map bound to zoom
**Purpose:** make D1's three-resolution, abstain-when-thin design decision *felt*, not just configurable via a dropdown a user might never touch.
**Pattern:** MapLibre zoom-expression-driven layer visibility (a standard, documented pattern — swap `district` polygons for `cell` heat for `location` points at defined zoom breakpoints), plus opacity/fade tied to each cell's own confidence value so low-confidence areas visibly recede rather than looking as certain as high-confidence ones.
**Feasibility:** 🟢 AVAILABLE.

### 7.4 Fund-flow directed timeline
**Purpose:** show tempo, not just topology — the actual differentiator claim in DOC1 is about speed of layering vs. physicality of cash-out, and a force-directed graph shows neither.
**Pattern:** Cytoscape.js `breadthfirst` layout, `directed: true`, nodes ordered by `FundHop.layer`; edge color/width or a subtle animated dash keyed to hop latency (`event_at` deltas). Same library, same data source (`GET /clusters/{id}`), different layout config.
**Feasibility:** 🟢 AVAILABLE.

### 7.5 Ladder-as-decision-path
**Purpose:** show a recommendation as a reasoned comparison, not a colored label — this is the difference between "the system said L3" and "the system compared a 45-minute window against a 14.5-minute ETA and had 30 minutes of margin, so it recommended dispatch instead of a bank-side hold."
**Pattern:** a small horizontal comparison widget (two bars on a shared time axis: window vs. ETA, with the margin called out), plus the `reason_code` rendered as a plain-language sentence. No charting library needed — this is closer to a custom, purpose-built component than a generic chart.
**Feasibility:** 🟢 AVAILABLE, pending the rung-count question (§1.2.6).

### 7.6 Attention-budget strip
**Purpose:** make an ethical safeguard (DOC1 §1.5 principle 6, alert budget/triage tiers) visible as a trust feature rather than an invisible backend policy.
**Pattern:** a simple bounded strip — shown / deferred / budget-for-shift — directly above the alerts table.
**Feasibility:** 🟢 AVAILABLE.

### 7.7 What should stay boring, on purpose
- **Audit log:** a plain table is correct here. Tamper-evidence is a credibility feature precisely because it looks like a boring, auditable ledger — don't visualize it into something that looks designed to impress rather than to be checked.
- **Outbox:** a table with expandable rows (current pattern) is right for a debugging surface. Don't add charts to it.
- **Cases list:** a searchable table is right; cases are compared and scanned, not explored spatially.

### 7.8 What NOT to add
⛔ A new charting/mapping/graph library. You already have MapLibre, Cytoscape.js, and Recharts, and every recommendation above is built from them. Introducing D3 directly, deck.gl, or a Sankey library for one screen buys a visual novelty at the cost of a dependency DOC2 explicitly decided against ("Not used: … D3 directly"). ⛔ A generic BI-style "explore your data" screen with pivotable filters — that's a different product (retrospective analytics) than the one you're building (proactive interception).

---

## 8. Current website redesign — verdict by page

| Page | Verdict | Why |
|---|---|---|
| Login | Keep, minor polish | Quick-login grid for demo is fine and appropriate; not worth redesign time |
| Command Centre Dashboard | **Demote to thin ambient header + minimal landing** | Its real content (KPIs) belongs in a persistent strip; its module grid is redundant with a task-shaped nav (§3.2) |
| Alerts Inbox + Alert Detail | **Keep structure, rebuild detail panel contents** | The list/queue/detail pattern is sound; the detail panel's evidence, timing, ladder, and proportionality treatment all need rework (§4.2) |
| Map | **Keep, extend** | Correctly built (live/potential layers, k-threshold suppression, time slider); add zoom-bound resolution, abstention-aware styling, and the unit/ETA layer (§4.3) |
| Clusters | **Merge into Investigate, remove as top-level page** | Duplicates Case Detail's embedded graph; keep `/clusters/:id` as a deep link only (§4.4) |
| Cases | **Keep as the primary surface of Investigate** | Statutory disclaimer, brief, accounts table are all correct and load-bearing — don't touch the legal-compliance content, only its position in the nav and its relationship to Clusters |
| Evaluation | **Keep layout, fix the data underneath** | The hero-ring + metrics-table + cold-start-chart design is fine; it is currently connected to nothing real (§1.2.2) |
| Ops | **Keep as-is** | Correctly wired, genuinely useful stage-latency breakdown; move under System Integrity tabs, don't redesign |
| Outbox | **Demote from primary nav to per-alert panel + admin route** | Debugging surface, not officer workflow (§4.6) |
| Audit | **Keep functionally, move under System Integrity tabs** | Already does the right thing; don't touch the verification logic or its presentation |
| Demo Console | **Fix reliability first, then leave alone** | Correctly scoped and gated; the only real problem is the HTTP 500/stalled state caught in your own screenshot (§1.2.5) |

---

## 9. Hackathon demonstration

### 9.1 Priority zero
Fix the demo console reliability issue (§1.2.5) before rehearsing anything else. A single visible `HTTP 500` during a live run undoes every other improvement in this document.

### 9.2 The narrative arc
1. **Open on the Command ticker, not a KPI grid.** One sentence: "Right now, across four states, this many rupees are moving toward cash-out." This sets the "race" framing from the first ten seconds (§2.1).
2. **Inject a cluster live** (`/sim-control/inject-cluster`, already built and already the right demo mechanism — don't change it). Narrate what's about to happen before it happens, so the audience is watching *for* something.
3. **Let the alert arrive on screen via SSE** — no refresh, no manual navigation. Open Triage already sitting there; the new critical alert should visibly appear.
4. **Open the Alert Focus panel and walk the six questions in order** (what/where/when/why/can-we/what-do-I-do), using exactly the four rebuilt blocks in §4.2: timing-decay curve, narrative evidence, ladder-as-decision-path, proportionality strip. This is the entire redesign's thesis performed in sixty seconds.
5. **Switch to Deployment and show the Interception Radar** for the same alert — same data, spatial framing, the ETA vector "closing the gap." This is the moment most likely to make a judge say "why isn't this just a normal dashboard" (§9.3).
6. **Take the action** (request hold or dispatch) and show the proportionality cap visually preventing over-reach — this is your strongest "we thought about the law, not just the ML" beat, and it currently doesn't exist on screen at all.
7. **Close on the evidence pack**: generate it live, show the SHA-256 and audit-head-hash, download it. "From a complaint to a court-admissible artifact, live, in one click" is a genuinely strong closing line, and it's wiring three unused endpoints, not new engineering.
8. **If asked about model quality**, go to System Integrity → Evaluation and show real sweep numbers — which only works if §1.2.2 is fixed first. If it isn't fixed in time, do not show that screen live; a caught fixture is worse than an admitted gap.

### 9.3 The signature moment
Make it the **Interception Radar** (§7.1, §9.2 step 5), not the heatmap. Heatmaps are what every predictive-policing-adjacent hackathon project shows, and yours already has one that works — it's not the differentiator. The differentiator is the thing DOC1 states as the actual insight: cash-out is physical, and physical things can be raced against. A visible unit closing a visible gap on a map, backed by a real ETA computation, is memorable in a way a colored blob is not, and it costs one small backend extension.

### 9.4 What to say out loud that the current UI doesn't say for you
- "Every prediction here comes with an abstention option — the system says 'I don't know at that resolution' rather than guessing." (Currently invisible; make it visible per §4.3, and say it anyway even before that ships.)
- "This lien proposal is capped by construction — the type it's built from cannot exceed the amount actually in dispute." (Proportionality panel, §4.2.4 — a real, structural claim, not a policy promise.)
- "Nothing here executes automatically. Every external effect required an authenticated officer." (True today, per invariant 7 — say it plainly, it's a genuine strength.)

---

## 10. Implementation priorities

### 10.1 Essential — do these regardless of time remaining
1. Fix the demo console reliability bug (§1.2.5).
2. Replace the percentage-based evidence panel with narrative `evidence[].text_en` cards (§1.2.1) — this is actively contradicting your own architecture; leaving it is worse than not having built evidence display at all.
3. Wire `allowed_actions` to the action bar instead of hardcoded role checks (§4.2) — closes the bank_nodal/`REQUEST_HOLD` correctness question regardless of how it's resolved.
4. Surface the proportionality panel (§4.2.4) — highest ratio of (legal/ethical credibility) to (engineering effort) in this entire document.
5. Replace raw ULIDs with `cluster_ref`/target name as primary identifiers everywhere they currently appear.

### 10.2 High value, cheap — do these next
6. Wire `/analytics/live-metrics` and `/analytics/timeseries` to the dashboard/ticker (§1.2.4).
7. Add the timing-decay curve (§7.2).
8. Wire the evidence-pack generation/download flow into Alert Focus (§4.2).
9. Re-render `timeline[]` as a horizontal event sequence instead of a bullet list (§5.3).
10. Human-legible labels pass across every table (small, unglamorous, very visible payoff).

### 10.3 Small backend extension, worth the ask
11. Expose unit coordinates (`GET /geo/units` or inline on `best_unit`) — unlocks the Interception Radar (§4.3, §7.1). One afternoon of backend work for the demo's signature moment.
12. Thin `GET /evaluation/runs[/{id}]` router over existing `experiment_runs`/`experiment_metrics` tables (§1.2.2). Stops your credibility screen from being a lie.

### 10.4 Larger, real new work — only if the essentials are already done
13. IA restructuring itself (§3): merging Clusters/Cases, tabifying System Integrity, demoting Outbox and the standalone Dashboard. This is routing and layout work, not algorithm work, but it touches every screen — budget real time for it, and do it *after* item 10.1–10.2 are done on the existing IA, so you're not redesigning navigation and rewiring data at the same time.
14. Fund-flow directed timeline via Cytoscape breadthfirst reconfiguration (§7.4) and the hierarchical zoom-bound map (§7.3) — genuinely valuable, genuinely low-dependency-risk, but each is a real multi-hour build, not a wiring job. Sequence after the map's unit layer (item 11), since that's the higher-impact map change.

### 10.5 Explicitly avoid — this is where hackathon teams bleed time for no judge-visible payoff
- ⛔ Any new mapping/graphing library (D3, deck.gl, a Sankey package). Everything proposed here runs on MapLibre + Cytoscape + Recharts, which you already chose and which your teammates already know.
- ⛔ Deduplicating the `acknowledge` endpoint (dedicated route exists, frontend calls the generic `/actions` route instead). It's real tech debt, it is invisible to a judge and irrelevant to the demo — don't touch it this cycle.
- ⛔ A generic "explore the data" analytics screen with arbitrary pivots/filters. Wrong product; you're building proactive interception, not retrospective BI.
- ⛔ Building a "trust score" that merges Evaluation + Ops + Audit into one number (§4.5). Actively dishonest compression of three different claims.
- ⛔ Real GPS/live-telemetry for units. The Interception Radar's ETA vector is a computed animation from `eta_min`, and that's fine — don't imply live tracking that doesn't exist; say plainly it's a computed estimate.
- ⛔ Polishing the Demo Console beyond error-legibility (§4.7). It's infrastructure; every hour spent there is an hour not spent on Triage/Deployment, which is what judges actually watch.

---

## 11. Final product direction

NAKABANDI's frontend should stop behaving like an admin panel generated from an OpenAPI spec and start behaving like what the backend actually is: a system that watches a race between money moving toward cash and lawful hands moving toward that same point in space and time, and that is disciplined enough to say "I don't know" when the evidence is thin and "no more than this" when the law says so.

**Information hierarchy:** five task-shaped destinations (Command, Triage, Deployment, Investigate, System Integrity), not eight resource-shaped ones. Alert focus is a shared, persistent concept reachable identically from all of them, not a page you navigate to and away from.

**Interaction philosophy:** every number the backend already qualifies with a confidence, a cap, or an abstention should be *visually* qualified the same way, not flattened into a clean-looking badge. Every recommendation should show the comparison that produced it, not just its conclusion. Every irreversible-feeling action (a lien, a dispatch) should visibly show the structural constraint that bounds it, because the constraint — not the model — is what makes the intervention defensible.

**Design philosophy:** boring where boring is correct (audit log, outbox, cases list), and genuinely novel exactly where the backend's own primitives — hierarchical forecast, timing mixture, ETA, ladder, proportionality — combine into something a plain chart-per-endpoint dashboard cannot represent (the Interception Radar, the timing-decay curve, the directed fund-flow timeline, the ladder-as-decision-path). Every one of those novel pieces is buildable this cycle from data you already compute and libraries you've already chosen. That's the whole opportunity here: you already did the hard part. The frontend just hasn't been telling anyone.
