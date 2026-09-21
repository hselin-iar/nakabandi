# DOC 2 — NAKABANDI: System & Technical Architecture

*Status: Confirmed. Builds on DOC 1 (product, features, evidence). Per-module contracts are DOC 3; build order and ownership are DOC 4.*

## Table of Contents
- §2.0 — Constraints
- §2.1 — Architecture Overview
- §2.2 — Technology Stack Decisions
- §2.3 — Data Architecture
- §2.4 — API Design
- §2.5 — Clean Architecture & Engineering Principles
- §2.6 — Repository Layout & Boundary Enforcement
- §2.7 — Non-Functional Requirements & Performance Budget
- §2.8 — Technical Risks & Assumptions
- Appendix A — Simulator Parameter Priors

---

## §2.0 — Constraints

- **Scope.** The architecture fully supports M1-M6 and leaves clean seams for S1-S5 (DOC 1 §1.2). Differentiators: **D1 lean** (hierarchical location forecast with abstention, mixture time-to-cash-out) and **D2 haversine** (reachability); D3 is stretch.
- **Evidence.** Public timing and distance distributions do not exist, so those parameters are priors: swept, never claimed as calibrated (DOC 1 §1.1; Appendix A below).
- **Legal design.** Amount-limited, time-boxed, complaint-anchored liens; an unsigned BSA s.63 certificate draft with a SHA-256 hash report; no compliance claims; human approval on every external action (DOC 1 §1.5).
- **Hosting.** A public hosted link and a public repository are required. The demo must also work fully offline as a backup path. Docker runs on 3 of 4 team machines, so every service must also run natively.
- **Demo geography.** Maharashtra, Uttar Pradesh, Haryana, Jharkhand (public reporting names them as high-risk regions). Cluster identifiers stay synthetic; no real locality is labelled as a criminal hotspot.
- **Two languages only** (Python, TypeScript/JavaScript). No third runtime.
- **A pure algorithmic core** (graph, forecast, interception domain code) with no framework and no I/O, so the algo dev works with plain functions and pytest, not web or database code.
- **Generated API types** for the front end, so the web dev never hand-writes request or response shapes.
- **The external bank system is its own small Node/Express service**: a correct system boundary and a fit for the web dev.
- **Automated guardrails** (architecture tests, CI, one deterministic golden scenario), because agent-assisted coding needs them.

---

## §2.1 — Architecture Overview

```
ARCHITECTURE STYLE: Modular monolith (Python) + two external-system simulators + React SPA
RATIONALE:
  - Monolith-first rule: one small team, unproven domain boundaries. A modular
    monolith keeps deployment trivial while enforcing module boundaries in code, so any
    module can be extracted later.
  - The two simulators are NOT part of the product. They stand in for systems we do not
    own (NCRP/CFCFRMS and bank feeds; the bank's own lien system). Keeping them as separate
    processes with their own stores makes every integration go through a real contract.
  - Everything the product does with the outside world goes through ports (interfaces), so
    a real NCRP adapter or bank API can replace a simulator without touching domain code.
```

**System context**

```
   ┌──────────────────────────────┐            ┌───────────────────────────────┐
   │ WORLD SIMULATOR   (M1)       │            │ BANK GATEWAY SIMULATOR        │
   │ Python · own DB (world.db)   │            │ Node/Express · own store      │
   │ plays: complaint feed,       │            │ plays: bank / CFCFRMS lien    │
   │ lagged cash-out reports,     │            │ side + bank nodal console     │
   │ hidden ground truth          │            └──────▲───────────────┬────────┘
   └──────────┬───────────────────┘        signed     │               │ callbacks
   canonical  │ complaints / observations  webhook     │               ▼ (hold applied/released)
   schema     │ / clock ticks                           │
   ┌──────────▼─────────────────────────────────────────┴───────────────────────────┐
   │ NAKABANDI API — modular monolith (Python / FastAPI)                             │
   │ intake → graph → forecast → interception → alerting → casework                  │
   │ + geo · access · audit · analytics · evaluation (offline only)                  │
   │ SQLite (WAL) · in-process event bus · outbox worker · injectable Clock          │
   └──────▲────────────────────────▲──────────────────────────────┬───────────────┘
          │ REST + SSE             │ REST (control)               │ SMTP / SMS sandbox
   ┌──────┴────────────┐    ┌──────┴──────────┐            ┌──────▼────────────────┐
   │ WEB APP (React)   │    │ DEMO CONSOLE    │            │ Mailpit / SMTP        │
   │ LEA interface,    │    │ (route in web   │            │ SMS sandbox adapter   │
   │ heatmap, inbox    │    │ app, demo-only) │            └───────────────────────┘
   └───────────────────┘    │ → world-sim API │
                            └─────────────────┘
```

**Layer diagram (inside the API)**

```
  [Client Layer]          React 18 + TypeScript SPA (Vite, Tailwind, MapLibre)
        │                 | team skill, dashboard behind login, no SSR needed
        ▼
  [Interface Layer]       FastAPI routers · SSE stream · CLI entry points
        │                 | thin: parse, authenticate, call ONE use case, present
        ▼
  [Application Layer]     Use cases · transactions · authorization (Principal + Scope)
        │                 | orchestrates domain code and ports; owns no algorithms
        ▼
  [Domain Layer]          Entities · value objects · algorithms (pure Python)
        │                 | no I/O, no framework, no wall-clock reads; the DSA seam
        ▼
  [Infrastructure Layer]  SQLAlchemy repositories · channel adapters · model store ·
        │                 file store · Clock implementations | implements ports
        ▼
  [Runtime]               Docker Compose on a laptop (offline) · optional single VM
```

**Dependency rule:** `interfaces → application → domain`; `infrastructure` implements ports declared by `application`/`domain` and is wired at startup. Nothing inner imports anything outer. This is enforced by an automated test (§2.6).

**Modules (bounded contexts) inside the API** *(eleven contexts plus one process manager, `pipeline`, and the shared kernel)*

| Module | Responsibility | Owns (tables) | Publishes events | DOC 1 features |
|---|---|---|---|---|
| `geo` | Registry of banks, ATMs/branches/agents, regions, grid cells, response units; spatial index | regions, banks, locations, cells, units | none | M1, M3, M6 |
| `intake` | Validate and store canonical complaints, accounts, fund hops and cash-out observations; idempotency; time ticks | complaints, accounts, fund_hops, cashout_observations, ingest_batches | ComplaintIngested, ObservationIngested | M1, M2 |
| `graph` | Resolve accounts to mule clusters (incremental union-find plus periodic community refinement); cluster footprints and affinities | clusters, cluster_members, cluster_location_stats | ClusterUpdated | M2, S1 |
| `forecast` | Candidate generation, scoring, hierarchy, abstention, timing mixture, calibration, explanation evidence | forecasts, model_versions | ForecastGenerated | M2 |
| `interception` | Reachability, interceptability verdict, ladder recommendation, lien proposal (proportionality rules) | intercept_assessments | InterceptAssessed | M6 |
| `alerting` | Alert lifecycle, dedup, routing, budget, escalation, outbox delivery, channel adapters, action and outcome recording | alerts, deliveries, actions, outcomes | AlertRaised, AlertUpdated, AlertEscalated, ActionRecorded, OutcomeRecorded | M4, M5, S3 |
| `casework` | Cluster-level case bundling, case brief, evidence pack, s.63 certificate draft | cases, evidence_packs | none | S1, S2 |
| `access` | Authentication, roles, scopes, masking policy | users | none | M5 |
| `audit` | Append-only, hash-chained audit log and verification | audit_entries | none | M5, S2 |
| `analytics` | Read models: heat rollups, time series, live metrics; filters | heat_rollups, metric_snapshots | none | M3 |
| `evaluation` | OFFLINE harness: backtests, baselines, sensitivity sweeps. Only module allowed to read ground truth | experiment_runs, experiment_metrics | none | M2, M6, S4 |
| `pipeline` | Process manager: runs the synchronous complaint chain by calling module facades in order; retries `unprocessed` complaints; refreshes open alerts. The only module allowed to call several facades in sequence | none | none | M2, M4, M6 |
| `shared` | Config, logging, ids, Clock, event bus, unit of work, error types | none | none | all |

**Rules that keep concerns separate (the "architectural invariants")**

```
1. HIDDEN-TRUTH FIREWALL. Ground truth (which cash-outs really belong to which mule
   cluster) lives only in world.db, owned by the world simulator. The API process has no
   credentials to it. Only the offline `evaluation` harness may read it, through an
   "oracle" client. The API learns outcomes only through lagged, observed reports on
   the same ingestion contract a real bank feed would use.
2. TWO CLOCKS. Every record has event_at (when it happened in the world) and observed_at
   (when the system could know). Features and models see only records with
   observed_at <= now.
3. AS-OF BY CONSTRUCTION. Every repository read method REQUIRES an as_of argument (no
   default), so a future-data leak cannot be written by accident.
4. INJECTED TIME. No domain or application code reads the wall clock. A Clock port is
   injected: SimClock (driven by ingested event times and ticks) in the demo,
   SystemClock in a real deployment. Timers (escalation, expiry, lien review) fire on the
   Clock.
5. MODULE OWNERSHIP. Each module owns its tables. No module reads or writes another
   module's tables or imports its internals. Cross-module needs go through the module's
   public facade or through domain events.
6. READ MODELS, NOT CROSS-QUERIES. `analytics` builds its rollups by subscribing to
   events; it never queries other modules' tables.
7. HUMAN GATE IS A TYPE. Any use case that produces an effect on a third party (a hold
   request to a bank, a dispatch instruction) takes an authenticated `Principal` with the
   right role as a parameter; system code cannot call it. Notifications TO officers are
   automated; requests TO other institutions are human-approved.
8. LEGAL INVARIANTS LIVE IN DOMAIN TYPES. A `LienProposal` cannot be constructed with an
   amount above the traced disputed amount, without an expiry, or without a complaint
   anchor. There is no "whole-account freeze" value in the domain at all.
9. ONLY THE APPLICATION LAYER TOUCHES TRANSACTIONS. Domain code is pure; repositories
   never commit; use cases own the unit of work.
```

**Primary runtime flow (hero use case)**

```
world-sim ──complaint (canonical)──▶ intake.ingest          [sync, one transaction]
   intake ──ComplaintIngested──▶ graph.resolve_cluster       [sync]
   graph  ──ClusterUpdated───▶ forecast.generate             [sync, in-memory model]
   forecast ─ForecastGenerated▶ interception.assess          [sync]
   interception ─InterceptAssessed▶ alerting.raise_or_merge  [sync: alert row + outbox rows]
   alerting.outbox worker ──▶ SSE push · email · SMS sandbox · informational webhook
                              (alert_notice) to the affected bank [async, retried, idempotent]
officer (browser) ──ack / request_hold (needs Principal)──▶ alerting.record_action
   record_action ──outbox──▶ signed webhook ──▶ bank-sim ──callback──▶ alerting.update_status
world-sim ──lagged cash-out observation──▶ intake ──▶ alerting.record_outcome (hit/miss/late)
                                                    ──▶ graph affinities (S3 feedback)
```
Orchestration is explicit: `pipeline.ProcessComplaint` calls the module facades in this order, and domain events are published afterwards only for fan-out (read models, casework, the SSE hub), never for control flow. The synchronous chain is deliberate: one complaint produces an alert in a single request path (p95 budget in §2.7). Only delivery is asynchronous, so a slow SMS provider can never delay an alert. If a stage fails, the complaint is stored and flagged `unprocessed`, and a retry job re-runs the chain.

**Evaluation harness (offline, separate entry point)**

```
sweep config (YAML) ─▶ world-sim (seeded, headless) ─▶ history + held-out days
      ─▶ train ─▶ replay held-out period through the SAME application use cases
      ─▶ reconcile predictions against oracle truth
      ─▶ metrics: precision@k per resolution, lead time, calibration (Brier, reliability),
         interceptable share, dispatches per interception, false-hold rate, cold-start curve
      ─▶ stored in experiment_metrics ─▶ shown on the web app's Evaluation page
```
Baselines run through the same harness: historical-frequency hotspot, nearest-ATM-to-victim, issuing-bank footprint only.

**Traceability: DOC 1 feature → architecture**

| Feature | Modules | Primary surface |
|---|---|---|
| M1 Scenario Simulator | world-sim (external), `intake` (contract), `evaluation` (sweeps) | canonical ingest API, Demo Console |
| M2 Predictive Engine | `graph`, `forecast`, `intake` | forecast on alert detail, Evaluation page |
| M3 Risk Heatmap Dashboard | `analytics`, `geo` | Map page, filters, SSE-driven refresh |
| M4 Alert & Notification System | `alerting` (+ channel adapters), bank-sim | Inbox, SSE, email, SMS sandbox, webhook |
| M5 Law Enforcement Interface | `access`, `audit`, `alerting`, web app | Login, inbox, alert detail, actions |
| M6 Interceptability Planner | `interception`, `geo` | Alert detail: ETA vs window, ladder, proportionality panel |
| S1 Cluster Case Bundling | `graph`, `casework` | Cases page |
| S2 Evidence Pack + Audit Chain | `casework`, `audit` | Evidence pack download, verify chain |
| S3 Feedback Loop | `alerting` (outcomes), `graph` (affinities) | Outcome buttons, before/after precision |
| S4 Cold-Start Drill | world-sim scenario injection, `forecast` (novelty, abstention) | Demo Console, Evaluation page |
| S5 Bilingual Templates | `alerting` (Jinja2 templates) | Email/SMS content |
| C1-C4 | seams only: `interception` policy config, `analytics`, PWA route, `access` | not built unless time allows |

---

## §2.2 — Technology Stack Decisions

*Principles applied: boring technology; match the team's skills; avoid native-build dependencies that break on Windows; every external dependency must work offline; keep implementation details behind ports so the choice can change.*

### Client

```
Decision: Frontend framework
  Chosen: React 18 + TypeScript + Vite (single-page app)
  Reason: The MERN teammate already knows React; a dashboard behind a login needs no
    server-side rendering; TypeScript plus generated API types gives coding agents a
    type-checked target, which cuts a whole class of mistakes.
  Not used: Next.js (SSR/SEO irrelevant, a second server concept), Vue, Svelte.

Decision: Styling and components
  Chosen: Tailwind CSS + shadcn/ui (Radix primitives), design tokens as CSS variables
  Reason: Fast for vibecoding; components are copied in, so the designer can change look
    and feel by editing tokens without fighting a library theme.
  Not used: MUI, Chakra, hand-written CSS only.

Decision: Server state and API client
  Chosen: TanStack Query + openapi-typescript / openapi-fetch (types generated from the
    API's OpenAPI document by one script)
  Reason: The API is the single source of truth for shapes; SSE only sends "something
    changed" pings and the client refetches, so there is one data path, not two.
  Not used: Redux Toolkit, hand-written fetch with hand-written types.

Decision: Map
  Chosen: MapLibre GL JS with locally bundled GeoJSON (district boundaries for the four
    demo states, ATM/branch/agent points, grid cells) and MapLibre's native heatmap and
    cluster layers. An online basemap is an optional enhancement, never a requirement.
  Reason: The demo must work offline (DOC 1). Boundaries plus points communicate the
    story without street tiles, and native layers handle tens of thousands of points.
  Not used: Leaflet, Mapbox GL, deck.gl, Google Maps (network, tokens or heavy).

Decision: Cluster graph view and charts
  Chosen: Cytoscape.js (mini graph) and Recharts (charts)
  Reason: Mature, well documented, easy for agents to generate correctly.
  Not used: react-force-graph, vis-network, D3 directly, ECharts.
```

### API and Domain Engine

```
Decision: Backend / API framework
  Chosen: Python 3.11 + FastAPI + Pydantic v2, served by Uvicorn with ONE worker
  Reason: The product is ML- and algorithm-heavy; one language for API, engine and
    simulator avoids a cross-service contract for the hottest path. OpenAPI is generated
    for free (feeds the typed client) and SSE is supported.
  Constraint: single worker; CPU-bound work runs in the threadpool.
  Not used: Express/Node API with a separate Python engine service, Django, Flask.

Decision: Engine, graph and clustering
  Chosen: Custom incremental Union-Find (disjoint-set) for live cluster resolution, plus
    NetworkX (Louvain community refinement, graph queries) run periodically
  Reason: Cluster resolution per complaint must be near-constant time and deterministic
    (a data-structures task that suits the DSA teammate). Community refinement is
    infrequent and NetworkX is adequate at simulator scale (thousands of accounts).
  Not used: GNNs (GraphSAGE via PyTorch Geometric), igraph, graph-tool, Neo4j.

Decision: Engine, location scoring (D1)
  Chosen: scikit-learn HistGradientBoostingClassifier on (cluster, candidate-location)
    pairs, probabilities normalised per cluster, isotonic calibration per resolution;
    coarser resolutions (grid cell, district) obtained by SUMMING location probabilities
    so the three levels are coherent; abstention when calibrated confidence at a level is
    below a configured threshold
  Reason: We need calibrated probabilities (alerts, ladder and abstention all consume
    them). Feature set comes straight from the evidence: issuing-bank footprint match,
    distance from home branch and from the cluster's runner footprint, cluster history
    at the location and cell, channel, time of day, and an amount x distance interaction.
    Abstention answers the literature's known failure modes (offender adaptation, sparse
    series) and the evidence that specific-ATM reuse was NOT supported.
  Constraint: explanations are evidence statements derived from the same features (for example
    "cluster has 6 prior cash-outs in this cell"), never model attributions.
  Not used: conditional / mixed logit as the engine (a possible baseline), LightGBM LambdaRank (uncalibrated
    scores; a drop-in swap only if precision@k needs it), GNNs.

Decision: Engine, time-to-cash-out
  Chosen: Two-component lognormal mixture (fast runners vs delayed handlers) fitted by EM
    with numpy/scipy, per cluster type with empirical-Bayes shrinkage to a global prior;
    predictions are CONDITIONED on the time already elapsed since credit; horizon
    probabilities (30/60/120 min) scored with Brier score and reliability curves
  Reason: The literature review found no validated model for sub-hourly mule cash-out
    timing and flagged multi-modal timing as a gap; a mixture represents both modes
    honestly. Conditioning matters because complaints arrive after some delay.
    Public timing distributions do not exist, so parameters are priors and are swept
    (Appendix A), never presented as calibrated.
  Not used: neural survival models, Cox / accelerated failure time (lifelines), a single lognormal or exponential.

Decision: Interception and reachability (D2)
  Chosen: Haversine distance with configurable speed profiles by area type, and
    scikit-learn BallTree (haversine metric) for nearest units and candidate retrieval
  Reason: Sufficient for the demo, offline, no downloads; speeds and thresholds live in
    configuration.
  Not used: OSMnx / OSRM road-network travel times (stretch, demo states only), online distance-matrix APIs.

Decision: Allocation under displacement (C1, stretch)
  Chosen: Greedy top-k allocation with a displacement discount tuned on the simulator
  Reason: The security-games literature confirms that adaptive adversaries and attempts to
    manipulate learning defenders are real, but formal Stackelberg models need payoff
    assumptions we cannot ground. A transparent heuristic, labelled as such, is honest.
  Not used: Stackelberg security games, game-focused learning.

Decision: World simulator (M1)
  Chosen: Python agent-based simulator (numpy Generator with explicit seeds), a separate
    package and process with its own database and a small control API
  Reason: Needs ATM geography, channels, runner footprints, timing mixtures and
    scenario injection, none of which public generators model. Determinism (same seed,
    same world) enables the golden-scenario test and the sweeps.
  Guard against circular evaluation: the hidden-truth firewall (§2.1 rule 1), three baselines, sweeps,
    reporting matches AND mismatches against public aggregates, and the cold-start drill.
  Not used: public generators (AMLSim / PaySim-style, IBM synthetic AML data) as the core (optional sanity
    check of the graph code only), hand-written static CSVs.
```

### Data, Security and Runtime

```
Decision: Database
  Chosen: SQLite 3 in WAL mode via SQLAlchemy 2.0, behind repository ports
  Reason: Zero infrastructure, one file, works offline and on every laptop; at the
    volumes in §2.7 it is comfortably sufficient. Only the API process writes to the
    product database, so the single-writer limit never bites.
  Constraint: JSON columns only for explanation and config blobs.
  Not used: PostgreSQL + PostGIS, MongoDB, DuckDB.

Decision: Authentication and authorization
  Chosen: Login issues a signed JWT in an HttpOnly, SameSite=Lax cookie; passwords hashed
    with argon2; RBAC via FastAPI dependencies producing a `Principal` (user, role, scope);
    machine clients (simulators) use service API keys; seeded demo user per role
  Reason: No external identity provider, so it works offline; cookies also work with SSE.
    Mutating requests additionally require a custom header (CSRF mitigation).
  Constraint: demo credentials are demo-only and never real. No MFA (C4).
  Not used: Supabase Auth, Clerk, bearer tokens in localStorage, SSO / OAuth.

Decision: Real-time push
  Chosen: Server-Sent Events, one authenticated stream per browser, events filtered by
    the principal's scope; events carry IDs and versions only, and the client refetches
  Reason: Push is one-directional; SSE is simple, works with cookies, reconnects on its own.
  Not used: WebSockets / Socket.io, polling as the primary path (the client falls back to polling only
    when SSE is buffered, §2.8 T13).

Decision: Background processing and scheduling
  Chosen: In-process asyncio tasks: an outbox worker for deliveries and a scheduler for
    escalation, expiry and lien-review timers, both driven by the injected Clock
  Reason: Timers must follow SIMULATED time when replaying at 1x-60x; most schedulers
    assume wall-clock time. The transactional outbox gives at-least-once delivery with
    idempotency keys without a broker.
  Constraint: tasks die with the process; recover them from the outbox table on boot.
  Not used: Celery + Redis, APScheduler, Kafka.

Decision: Notification channels
  Chosen: Adapters behind a `NotificationChannel` port. Dashboard via SSE. Email via SMTP
    when configured (Mailpit locally; a real SMTP account is optional) and ALWAYS recorded
    with its rendered body so an in-app Outbox viewer shows it, which also works on the
    hosted site. SMS via a provider
    sandbox or trial to verified test numbers, with an automatic fallback to an on-screen
    "SMS outbox" adapter. Webhook via HTTPX to the bank simulator, signed with
    HMAC-SHA256 over "timestamp.body", with an Idempotency-Key header
  Reason: Every channel is real on our side and testable offline. Failures are visible in
    the delivery log and never block alert creation.
  Not used: a production telecom gateway, fake console.log channels (they fail the "no mocks on our side" rule).

Decision: Evidence storage and PDF generation
  Chosen: Local filesystem volume for generated packs (path and SHA-256 stored in the
    database); ReportLab (pure Python) for PDFs
  Reason: No network, no native dependencies on Windows.
  Not used: S3 / R2 / Supabase Storage, WeasyPrint, headless Chromium.

Decision: Caching
  Chosen: No external cache. In-process derived structures (union-find, BallTree, loaded
    model, rollups) rebuilt from the database at startup
  Reason: Avoids Redis; startup rebuild is cheap at these volumes.
  Constraint: processes are NOT stateless in the 12-factor sense; the in-process state is a derived,
    disposable view (see §2.5).
  Not used: Redis, Upstash.

Decision: Bank gateway simulator
  Chosen: Node 20 + Express, small server-rendered "bank nodal console", its own SQLite
    or JSON store; verifies the HMAC signature and timestamp window; acknowledges;
    applies an amount-limited lien in its own ledger; calls back on apply and release
  Reason: A separate process is a true system boundary and gives the webhook contract
    real teeth; a natural fit for the MERN teammate.
  Not used: a Python module inside the API, a Python second service.
```

### Delivery, Quality and Operations

```
Decision: Deployment
  Chosen: Docker Compose on ONE small VM (2 vCPU / 4 GB is enough) behind a Caddy reverse
    proxy that gives automatic HTTPS and a single public origin; services: api (also serves
    the built SPA), world-sim, bank-sim. The presenter's laptop runs the same Compose file
    as the offline backup. Every service also runs natively (uvicorn, npm) for the teammate
    without Docker; Compose is used for hosting, the backup demo and CI.
  Reason: The event requires a public link. One origin keeps cookies and SSE simple
    (same-site, no CORS). The same images run everywhere, so what judges see is what we
    tested. A single VM keeps SQLite (one writer, local disk) valid and cost low.
  Constraint: a public endpoint needs the protections in §2.7 (abuse limits, auto-pause, nightly reset).
  Not used: split Vercel front end + separate API host, Kubernetes. A PaaS with several services
    (Railway / Render / Fly) is the FALLBACK if no VM is available: it needs a persistent volume for SQLite,
    and free tiers may sleep or wipe disk.

  Hosted topology
    Internet ─▶ Caddy (HTTPS, one origin)
                 /            → api container (SPA static files)
                 /api/*       → api
                 /bank/*      → bank-sim console (its own login)
                 /sim-control/* → world-sim control API, ONLY after Caddy forward_auth
                               calls api GET /auth/check?role=demo_operator
                 (world-sim oracle API and the world database are never routed or mounted)

Decision: Testing
  Chosen: pytest (unit tests on the pure domain, property tests with Hypothesis for the
    union-find and geo invariants), contract tests for the ingestion API and the webhook,
    ONE deterministic golden-scenario integration test (seeded three-day world, expected
    alerts), Vitest for front-end utilities, ONE Playwright test for the hero flow,
    architecture tests with import-linter
  Reason: A small, high-value pyramid; the golden scenario is the safety net for agents
    that change code they do not fully understand.
  Constraint: coverage is deliberately uneven: domain code heavily, presentation lightly.
  Not used: Jest, broad E2E suites.

Decision: Monitoring and logging
  Chosen: structlog JSON logs to stdout with a request ID; `/health` and a JSON metrics
    endpoint (events per second, stage latencies p50/p95, outbox depth, delivery failures)
    surfaced on an Ops panel in the web app
  Reason: Gives the scalability conversation real numbers from our own prototype.
  Not used: Sentry, Datadog, Prometheus + Grafana.

Decision: CI/CD and tooling
  Chosen: GitHub Actions running ruff, pyright, pytest, import-linter, eslint, tsc, vitest
    and the front-end build; pre-commit hooks locally; Python dependencies via uv with
    pyproject.toml (pip install fallback); Node via npm; root package.json scripts
    (`npm run dev | test | ci | types | seed | sweep`) instead of a Makefile because
    `make` is not standard on Windows
  Reason: One command per task on every operating system; failures caught before merge.
  Constraint: deployment stays manual (Compose).
  Not used: Makefile / just, Nx / Turborepo.
```

---

## §2.3 — Data Architecture

**Three stores, three owners**

```
nakabandi.db  (SQLite, WAL)   owned by the API. The product's data.
world.db      (SQLite)        owned by the world simulator. Ground truth lives here.
                               NEVER mounted into the API container.
bank.db       (SQLite/JSON)   owned by the bank simulator. Its ledger of liens.
```

**Conventions (all tables in nakabandi.db)**
- Surrogate primary key (ULID string, sortable), `created_at`, `updated_at`.
- Time columns are named `event_at` (when it happened in the world) or `observed_at` (when the system could know). Never a bare `timestamp`.
- Money is stored as integer paise (`amount_paise`), never floating point.
- Account identifiers are pseudonymous references (`account_ref`), not real numbers (see SENSITIVE DATA).
- Every index below is a foreign key or serves a named query.

**CORE ENTITIES**

```
── geo ─────────────────────────────────────────────────────────────────────────
Entity: Region        Fields: id, level (state|district), name, parent_id, geojson_ref
  Indexing: (level, parent_id)
Entity: Bank          Fields: id, name, short_code
Entity: Location      Fields: id, kind (ATM|BRANCH|AGENT), bank_id, lat, lon, district_id,
                      cell_id, source (osm|synthetic), display_name, area_type
                      (urban|semi_urban|rural), activity_index (0..1)
  Relationships: belongs to Bank, Region(district), Cell
  Indexing: (district_id), (cell_id), (bank_id, kind); spatial lookup via BallTree in memory
Entity: Cell          Fields: id, grid_km, row, col, district_id, centroid_lat, centroid_lon
  (square grid of configurable size, default 5 km. Mid-level resolution: region → cell → location.)
Entity: Unit          Fields: id, kind (cyber_cell|station|patrol), district_id, lat, lon,
                      status, speed_profile

── intake ───────────────────────────────────────────────────────────────────────
Entity: Account       Fields: id, account_ref, bank_id, home_location_id, home_district_id,
                      first_seen_observed_at
  Indexing: unique (account_ref)
Entity: Complaint     Fields: id, external_ref, category, amount_paise, victim_district_id,
                      credited_at (event_at of layer-1 credit), reported_event_at,
                      observed_at, layer1_account_id, processing_status
                      (processed|unprocessed|failed)
  Indexing: (observed_at), (layer1_account_id), (category, observed_at)
Entity: FundHop       Fields: id, complaint_id, from_account_id, to_account_id,
                      amount_paise, layer, event_at, observed_at
  Indexing: (complaint_id), (from_account_id), (to_account_id)
Entity: CashOutObservation  Fields: id, account_id, location_id, channel
                      (ATM|BRANCH|AGENT), amount_paise, event_at, observed_at,
                      source (bank_report|police_report)
  Indexing: (account_id, event_at), (location_id, event_at), (observed_at)
Entity: IngestBatch   Fields: id, idempotency_key, source, received_at, row_counts
  Indexing: unique (idempotency_key)

── graph ────────────────────────────────────────────────────────────────────────
Entity: Cluster       Fields: id, created_observed_at, size, status (active|dormant),
                      novelty_score, footprint_summary (JSON, small)
Entity: ClusterMember Fields: cluster_id, account_id, joined_observed_at
  Indexing: unique (account_id), (cluster_id)
Entity: ClusterLocationStat  Fields: cluster_id, location_id, cell_id, cashouts, amount_paise,
                      last_event_at, last_observed_at
  Indexing: (cluster_id, cell_id), (cluster_id, location_id)   [the affinity table]

── forecast ─────────────────────────────────────────────────────────────────────
Entity: ModelVersion  Fields: id, kind (scorer|timing), trained_at, train_window,
                      data_hash, params (JSON), artifact_path, metrics (JSON)
Entity: Forecast      Fields: id, complaint_id, cluster_id (nullable), generated_at,
                      model_version_ids, levels (JSON: per resolution, ranked items with
                      calibrated probability and an abstained flag), timing (JSON: mixture
                      weights, parameters, P30/P60/P120 conditional on elapsed time),
                      confidence, evidence (JSON: statements derived from features)
  Indexing: (complaint_id), (cluster_id, generated_at)

── interception ─────────────────────────────────────────────────────────────────
Entity: InterceptAssessment  Fields: id, forecast_id, target_kind, target_id, channel,
                      window_min, best_unit_id, eta_min, verdict (interceptable|marginal|not),
                      ladder_level (L1|L2|L3), reason, lien_proposal (JSON: disputed_amount_paise,
                      proposed_amount_paise ≤ disputed, expires_at, review_at)

── alerting ─────────────────────────────────────────────────────────────────────
Entity: Alert         Fields: id, cluster_id, dedup_key, target_kind, target_id, severity,
                      confidence, window_start, window_end, expires_at, status
                      (open|acknowledged|actioned|escalated|expired|closed), scope_district_id,
                      scope_bank_id, budget_rank, is_probe, latest_forecast_id
  Indexing: unique (dedup_key) where status in open states; (status, severity), (scope_district_id)
Entity: Delivery      Fields: id, alert_id (or action_id), channel (sse|email|sms|webhook),
                      rendered_body (for the Outbox viewer; masked identifiers only),
                      webhook_kind (alert_notice|hold_request), recipient, status
                      (pending|sent|failed|dead), attempts, idempotency_key, last_error, sent_at
  Indexing: (status, next_attempt_at)   [the outbox]
Entity: Action        Fields: id, alert_id, type (acknowledge|request_hold|notify_station|
                      dispatch|override), actor_user_id, reason, params (JSON), status, at
Entity: Outcome       Fields: id, alert_id, result (hit|miss|late), observation_id,
                      reconciled_at

── casework ─────────────────────────────────────────────────────────────────────
Entity: Case          Fields: id, cluster_id, complaint_ids, totals, brief_md, status
Entity: EvidencePack  Fields: id, alert_id or case_id, file_path, sha256, hash_report (JSON),
                      certificate_draft (JSON, unsigned), created_by, created_at

── access · audit · analytics · evaluation ─────────────────────────────────────
Entity: User          Fields: id, name, role (i4c_analyst|state_investigator|district_officer|
                      bank_nodal|demo_operator|admin), scope_state_id, scope_district_id, scope_bank_id,
                      password_hash, locale (en|hi), is_active
Entity: AuditEntry    Fields: seq (monotonic), at, actor_id, action, entity_type, entity_id,
                      reason, payload (canonical JSON), prev_hash, hash
  Indexing: unique (seq); hash = SHA-256(prev_hash || canonical payload)
Entity: HeatRollup    Fields: target_kind (cell|location), target_id, hour_bucket, category,
                      amount_band, confidence_band, layer (live|potential), expected_mass,
                      alert_count, version
  Indexing: (hour_bucket, category), (target_id)   [the read model behind the heatmap]
Entity: ExperimentRun / ExperimentMetric   Fields: run id, config hash, sweep parameters,
                      metric name, resolution, value
```

**DATA FLOW (primary use case)**

```
1. world-sim POSTs a complaint batch (canonical schema, idempotency key) → intake validates,
   upserts accounts, stores complaint and fund hops; observed_at = clock.now().
2. graph.resolve(account) → cluster_id or new/novel cluster (union-find, O(α n)).
3. forecast.generate(cluster, complaint, as_of=now):
     candidates (BallTree around footprint and home branch) → features → scorer →
     per-cluster normalisation → calibration → sum up to cell and district →
     abstain where confidence < threshold; timing mixture conditioned on elapsed time.
4. interception.assess(forecast): ETA of nearest unit vs window → verdict; ladder level
   by channel; lien proposal built via the LienProposal type (capped at disputed amount).
5. alerting.raise_or_merge(dedup_key = cluster + target): create or update alert, rank
   under the officer's alert budget, write Delivery rows to the outbox in the same
   transaction; emit AlertRaised.
6. outbox worker delivers: SSE ping, email, SMS sandbox; retries with backoff; dead-letters.
7. Officer acts (Principal required). request_hold → signed webhook via outbox → bank-sim
   verifies, applies lien in its own ledger, calls back → Action status updates.
8. World-sim later posts a lagged CashOutObservation. intake stores it;
   alerting reconciles to Outcome (hit / miss / late); graph updates
   ClusterLocationStat (S3); analytics updates rollups.
```

**Canonical event schema.** One versioned JSON Schema in the shared `contracts` package defines the ingestion contract: `ComplaintBatch`, `CashOutObservationBatch`, `RegistryUpdate`, `Tick`. The world simulator writes to it; any real NCRP or bank adapter would too. A "calibrate from data" command reads the same schema to refit the timing mixture and footprint parameters from any conforming dataset, so the pipeline is ready for real agency data.

**SENSITIVE DATA**

```
- No real personal data anywhere. Accounts are pseudonymous refs generated by the simulator.
  Any real deployment would store HMAC-SHA256(account number, secret) as account_ref.
- Display masking by role (policy in `access`, applied in presenters only):
    admin/i4c_analyst/state_investigator: full ref to authorised scope
    district_officer: masked except last 4; scope limited to district
    bank_nodal: refs for OWN bank only; other banks' data is never returned
- Notifications (SMS/email) carry masked identifiers and a deep link, never full refs.
- Logs never contain account_ref, tokens or passwords (structlog processor scrubs).
- Secrets (JWT signing key, HMAC webhook secret, service API keys, SMTP/SMS credentials)
  come from environment variables; `.env.example` holds names only.
- Evidence packs: masked for non-LEA roles; the pack's SHA-256 is stored and shown; the s.63
  certificate draft is UNSIGNED and labelled as a drafting aid.
- Audit log is append-only and hash-chained; `GET /audit/verify` recomputes the chain.
- Public repository: only `.env.example` is committed; secret scanning (gitleaks) runs in pre-commit and CI; demo
  credentials are documented as demo-only and the hosted instance uses different secrets.
- Third-party data licences: OpenStreetMap-derived ATM points are under ODbL and need visible
  attribution in the repository and the UI footer; every bundled dataset's source and licence is
  recorded in `data/geo/README`.
- Retention: all data is synthetic and disposable (`npm run reset`).
- Legal posture: design principles only, no compliance claims (DOC 1 §1.5).
```

---

## §2.4 — API Design

```
API STYLE: REST over JSON, versioned under /api/v1, plus one SSE stream.
RATIONALE: Resource-shaped data with role-scoped reads and a few command endpoints; OpenAPI
  is generated from Pydantic models (feeds the typed client and contract tests). GraphQL and
  tRPC add cost without benefit; the only real-time need is one-way notification.
CONVENTIONS:
  - Nouns for resources; commands as POST sub-resources (e.g. /alerts/{id}/actions).
  - Cursor pagination (?cursor=&limit=); filters as query params.
  - Errors: { "error": { "code", "message", "details": [ {field, issue} ] } }; never a stack trace.
  - Status codes: 200/201/204; 400 bad request; 401 unauthenticated; 403 forbidden (also
    for out-of-scope resources); 404; 409 conflict (stale or duplicate); 422 validation.
  - Idempotency-Key header on all ingest POSTs and webhook deliveries.
  - Every response for a principal is filtered by Scope at the repository level, then masked
    in the presenter. Routers never filter or mask.
```

**Core endpoints**

```
AUTH
  POST /auth/login            Auth: none. Sets HttpOnly session cookie. Rate limited.
  POST /auth/logout           Auth: any.
  GET  /auth/me               Auth: any. Returns principal (role, scope).
  GET  /auth/check?role=      Auth: session cookie. 204 if the principal holds the role, else 403.
                              Used ONLY by the reverse proxy (forward_auth) to gate /sim-control.
  GET  /auth/demo-users       Auth: none. Lists quick-login demo accounts (hosted demo mode only).

INGEST  (machine clients only: service API key)
  POST /ingest/registry       Purpose: banks, locations, units, regions (idempotent upsert).
  POST /ingest/complaints     Purpose: batch (<= 500) in canonical schema. Runs the pipeline.
  POST /ingest/hops           Purpose: later-arriving fund-flow tracing from banks (batch <= 500).
  POST /ingest/cashout-observations   Purpose: lagged cash-out reports.
  POST /ingest/tick           Purpose: advance the SimClock; fires due timers.

ALERTS & ACTIONS   (role-based, scoped)
  GET  /alerts                Filters: status, severity, district, bank, cluster, cursor.
  GET  /alerts/{id}           Detail: forecast (per resolution, with abstention), timing,
                              evidence statements, interception verdict, ladder,
                              proportionality panel, deliveries, timeline.
  POST /alerts/{id}/acknowledge
  POST /alerts/{id}/actions   Body: type, reason, params. Types: request_hold (params
                              include lien amount, validated ≤ disputed), notify_station,
                              dispatch, override (reason mandatory). Roles: investigator,
                              i4c_analyst, district_officer as configured; bank_nodal may
                              only acknowledge.
  POST /alerts/{id}/outcome   Body: hit | miss | late. Human-marked (S3); simulator
                              reconciliation is automatic.

CLUSTERS & CASES   (S1)
  GET  /clusters, GET /clusters/{id}     Summary plus small graph (nodes, edges) for the mini graph.
  GET  /cases, GET /cases/{id}           Bundled case and consolidated brief.

MAP & ANALYTICS   (M3)
  GET  /geo/regions           GeoJSON for demo states/districts (static, cacheable).
  GET  /geo/locations         Params: bbox, kind, bank. Points for ATM/branch/agent layers.
  GET  /analytics/heatmap     Params: layer (live|potential), level (district|cell|location),
                              from, to, category, amount_band, min_confidence, bbox.
                              Reads HeatRollup only. Cells under the k-threshold are
                              suppressed above location level.
  GET  /analytics/timeseries  Params: same filters; bucketed counts.
  GET  /analytics/live-metrics  Alert counts, queue depth, latency percentiles.

EVIDENCE & AUDIT   (S2)
  POST /alerts/{id}/evidence-pack     Creates the PDF and hash report; returns metadata.
  GET  /evidence-packs/{id}/download  Streams the PDF. Scoped and masked by role.
  GET  /audit                 Role-limited. GET /audit/verify recomputes the chain.

EVALUATION & OPS
  GET  /evaluation/runs, GET /evaluation/runs/{id}    Sweep results for the Evaluation page.
  GET  /system/health, GET /system/metrics            Throughput and latency (Ops panel).

STREAM
  GET  /stream                SSE. Event types: alert.created, alert.updated, heat.version,
                              delivery.updated, sim.time. Payload: IDs and versions only.

INBOUND FROM BANK SIMULATOR (service key + HMAC)
  POST /integrations/bank/callbacks   Body: request id, status (applied|rejected|released),
                              applied_amount. Updates the Action; writes audit.
```

**Outbound webhook contract (API → bank simulator).** Two message kinds share one signed endpoint:
- `alert_notice`: INFORMATIONAL, sent automatically with an alert to the bank whose accounts or locations are involved. Need-to-know only: that bank's own masked account refs, target location, window. It requests nothing.
- `hold_request`: a REQUEST to another institution. Created only by the `request_hold` use case, which requires an authenticated officer `Principal` (invariant 7).

```
POST {bank-sim}/webhooks/nakabandi
Headers: X-Nakabandi-Timestamp (wall clock, epoch seconds), X-Nakabandi-Signature =
         hex(HMAC-SHA256(secret, timestamp + "." + raw_body)), Idempotency-Key
Body (common):  { kind: alert_notice | hold_request, request_id, alert_ref, bank_id,
                  account_ref (masked for alert_notice), complaint_ref }
Body (hold_request only): { disputed_amount_paise, proposed_lien_paise (must be <=
                  disputed), expires_at_sim, review_at_sim, requested_by_role }
Receiver: reject if timestamp is outside a five-minute window or signature fails;
          dedupe on Idempotency-Key; respond 200 { ack: true }; later POST the callback.
```
Transport-level security uses wall-clock time; domain times inside the payload use simulated time.

**Demo Console (demo-only, separate client).** The web app's `/demo` route, visible only to `demo_operator` and `admin`, talks to the world simulator's control API through the proxy path `/sim-control/*` (`POST start|pause|speed|reset|seed|inject-cluster`, `GET status`). The proxy authorises every call via `GET /auth/check`. Hosted mode caps speed at 60x and restricts `reset` and `seed` to `admin`. It is compiled out of a production build with `VITE_DEMO_CONSOLE=false`, and the product API knows nothing about it beyond the generic role check.

---

## §2.5 — Clean Architecture & Engineering Principles

**Concern map: where each concern lives, and where it must never appear**

| Concern | Lives in | Must never appear in |
|---|---|---|
| Rendering and interaction | `apps/web` features and `shared/ui` | business rules, SQL, secrets |
| HTTP parsing, validation, response shaping | API `interfaces` (routers, presenters) | domain algorithms, transactions |
| Authorization (who may do what, on which scope) | Application use cases, using a `Principal` and `Scope` from `access` | routers, domain algorithms |
| Data masking | Presenters, using the masking policy from `access` | repositories, domain |
| Business rules and algorithms | `domain` (pure Python) | I/O, frameworks, wall clock, config files |
| Persistence and transactions | `infrastructure` repositories; unit of work owned by use cases | domain, routers |
| Time | The `Clock` port | anywhere except `SystemClock` / `SimClock` |
| Policy and thresholds (ladder rules, speed profiles, alert budget, abstention thresholds, k-threshold, exploration share) | `config/policy.yaml`, validated by Pydantic in `shared/config` | hard-coded constants in code |
| Legal and ethical invariants | Domain value objects and use-case guards, plus audit | UI-only checks |
| Integrations (banks, SMS, email) | `infrastructure` adapters behind ports | domain and application |
| Ground truth and simulation | world simulator, `evaluation.oracle` | the API process |
| Observability | logging and metrics middleware | domain |
| Demo tooling | Demo Console and world-sim control API | the product API |

```
MODULARITY & COHESION:
  Eleven bounded contexts plus one process manager (`pipeline`), each with one reason to change and its own tables (§2.1). Modules talk
  only through a public facade (`__init__.py`) or domain events, never through each
  other's tables or internals. `analytics` is a pure read model built from events.

SINGLE RESPONSIBILITY PRINCIPLE:
  Each use case does one thing (`IngestComplaint`, `ResolveCluster`, `GenerateForecast`,
  `AssessInterception`, `RaiseOrMergeAlert`, `RecordAction`, `ReconcileOutcome`).
  Temptation to avoid: putting "just one more rule" in a router or a repository. Guard: the
  architecture tests and the concern map above.

SEPARATION OF CONCERNS:
  Business logic lives only in `domain`; orchestration and authorization only in
  `application`; parsing and masking only in `interfaces`; SQL only in `infrastructure`.
  Presentation, domain and data layers are isolated by ports and DTOs. Policy is data, not
  code. The simulator and the product are separate systems joined only by a contract.

DEPENDENCY INVERSION:
  Application and domain declare ports (`Clock`, `LocationScorer`, `TimingModel`,
  `TravelTimeEstimator`, `NotificationChannel`, `FileStore`, repositories). Infrastructure
  implements them; startup wiring ("composition root") injects them. No upward imports.
  Tests inject fakes (a fixed Clock, an in-memory repository).

OPEN/CLOSED PRINCIPLE:
  New channel = new `NotificationChannel` adapter. New ladder rule = a policy entry. New
  scorer or timing model = a new class behind its port. New crime category = a
  configuration value. No edits to existing modules to add any of these.

INFORMATION HIDING (Ousterhout):
  Deep modules with small interfaces: `graph` exposes `resolve(account) → cluster`;
  `forecast` exposes `forecast(cluster, complaint, as_of) → Forecast`; `interception`
  exposes `assess(forecast) → Assessment`. Union-find internals, feature engineering,
  calibration and EM fitting never leak. Repository methods require `as_of`, which defines
  the leakage error out of existence.

TESTABILITY:
  The domain is pure, so it is unit-tested with no mocks. The Clock is injected, so timers
  are tested by advancing a fake clock. One seeded golden scenario tests the whole chain
  deterministically. Contract tests pin the ingestion API and the webhook.

NAMING & READABILITY (Clean Code):
  Files and modules named for what the system does (`interception`, `alerting`), not for
  frameworks. Python: snake_case modules and functions, PascalCase types, no abbreviations
  beyond domain terms (`cell`, `lien`). TypeScript: PascalCase components, camelCase
  values, kebab-case files. Routes are plural nouns. Money is `*_paise`. Time is
  `event_at` / `observed_at`. Comments explain why (legal rules, evidence sources), never
  what. No magic numbers: thresholds come from policy config with named keys.

12-FACTOR COMPLIANCE (backend / deployment):
  Codebase: one repository, one image per service. Dependencies: declared in
  pyproject.toml and package.json, locked. Config: environment variables plus policy YAML;
  no secrets in the repo. Backing services: SMTP, SMS, bank simulator and SQLite path are
  attached resources set by config. Build/release/run: images built in CI, config injected
  at run. Processes: KNOWN DEVIATION. The API keeps derived in-process state (union-find,
  spatial index, model) rebuilt at boot; this blocks horizontal scale-out until it is
  externalised, and is accepted for the demo. Port binding: each service binds its own
  port. Concurrency: single worker by design. Disposability: fast start, graceful
  shutdown, outbox and retry recover work on restart. Dev/prod parity: Compose is the same
  in both. Logs: JSON to stdout. Admin processes: seed, reset, train, sweep and
  calibrate run as one-off commands in the same image.
```

**Traceability: DOC 1 §1.5 principles → enforcing mechanism**

| DOC 1 principle | Mechanism in this architecture |
|---|---|
| Human in the loop | Invariant 7: external-effect use cases require a `Principal`; override needs a reason; every action audited |
| Score accounts and ATMs, not people | Feature blocklist enforced in `forecast` feature registry; no demographic fields exist in the schema |
| Data minimisation, role-based views | `Scope` at repository level; masking in presenters; bank role sees own bank only |
| Aggregate privacy | k-threshold suppression in the heatmap query above location level (policy key) |
| Time-boxed, reversible interventions | `LienProposal` requires expiry and review time; scheduler fires review; release path via bank callback |
| Alert budget and triage | `alerting` budget policy (per officer, per shift), triage tiers, exploration share |
| Tamper-evident logging | `audit` hash chain and `/audit/verify`; evidence pack embeds the head hash |
| Synthetic-only data | Simulator is the only data source; account refs are pseudonymous; cluster IDs synthetic |
| Alert compartmentalisation | SSE and queries filtered by scope; masked notifications; delivery log access restricted |
| Proportionality of liens | Domain invariant 8; proportionality panel in the UI is a presentation of the same value object |

---

## §2.6 — Repository Layout & Boundary Enforcement

```
nakabandi/
  AGENTS.md  DOC1.md  DOC2.md  DOC3.md  DOC4.md    project spec set, at the repo root
  vibe-antipatterns.md  prompt-patterns.md         agent reference files, loaded on demand by AGENTS.md
  docs/                             state/ (one file per track)  design/  reference/  research/  results/
  apps/
    api/
      src/nakabandi/
        shared/                     config, logging, ids, clock, events, errors
        geo/  intake/  graph/  forecast/  interception/
        alerting/  casework/  access/  audit/  analytics/  evaluation/  pipeline/
        main.py                     composition root: wiring, lifespan tasks
      tests/                        unit/  contract/  golden/  architecture/
    web/
      src/
        features/                   alerts/ map/ clusters/ cases/ evaluation/ ops/ demo/
        shared/                     ui/  api/ (generated client)  lib/  tokens/
    world-sim/
      src/worldsim/                 core/ (pure sim)  control_api/  writer/  oracle_api/
    bank-sim/
      src/                          server, webhook verification, ledger, console
  packages/
    contracts/                      canonical JSON Schemas + Pydantic models (no logic)
  config/                           policy.yaml  sim.default.yaml  sweep.example.yaml
  data/geo/                         bundled GeoJSON, ATM extract, README with sources/licences
  infra/                            docker-compose.yml  Dockerfiles  .env.example
  scripts/                          seed  reset  types  sweep  calibrate
  package.json  pyproject.toml  .python-version  .nvmrc
```

**Inside every API module**
```
<module>/
  __init__.py        PUBLIC FACADE ONLY: what other modules may import
  domain/            pure entities, value objects, algorithms
  application/       use cases and ports (interfaces)
  infrastructure/    repositories and adapters that implement ports
  interfaces/        routers and presenters (only where the module exposes HTTP)
```
Small modules (`geo`, `access`, `audit`) may collapse a layer into one file; the layer names and rules still apply. DOC 3 fixes the exact structure per module.

**Boundary enforcement (automated, runs in CI and pre-commit)**

| Rule | Tool | Effect |
|---|---|---|
| `interfaces → application → domain`; `infrastructure` never imports `interfaces` | import-linter (layers contract) | Fails on an upward import |
| A module may import another module only through its public facade | import-linter (forbidden contracts) | Fails on reaching into `other.domain`, `other.infrastructure` |
| `domain` may not import `sqlalchemy`, `fastapi`, `httpx`, `os`, `requests` | import-linter (forbidden) | Keeps domain pure |
| No wall-clock reads outside the Clock implementations | ruff banned-API rule (`datetime.now`, `time.time`) | Keeps time injectable |
| Only `evaluation` may import the oracle client; `main.py` may not import `evaluation` | import-linter | Enforces the hidden-truth firewall |
| Only `pipeline` and `main.py` may import several module facades in sequence; no module imports `pipeline` | import-linter | Keeps orchestration in one place |
| `packages/contracts` imports nothing from `apps/*` | import-linter | Keeps the shared kernel clean |
| Web features do not import each other; only from `shared/*` | eslint-plugin-boundaries | Prevents front-end tangling |
| Generated API client is never hand-edited | CI check (`npm run types` produces no diff) | Prevents type drift |

**Team seams**
- **Algorithmic seam (DSA):** `graph/domain`, `forecast/domain`, `interception/domain`, `geo/domain`, the pure simulator core. Plain Python, pytest, no framework.
- **Web seam (MERN):** `apps/web` features, `apps/bank-sim`.
- **Integration seam (systems):** `application` and `infrastructure` layers, `intake`, `alerting`, `main.py`, CI, Compose, ingestion contract.
- **Design seam (designer):** `shared/tokens`, `shared/ui`, layouts, copy, evidence-pack layout, demo materials.

Two shared contracts are locked in DOC 3: the **canonical event schema** (`packages/contracts`) and the **OpenAPI document** (generated from the API).

---

## §2.7 — Non-Functional Requirements & Performance Budget

*Design targets to verify, not measured results. The Ops panel reports the measured numbers.*

| Area | Requirement |
|---|---|
| Volume (default world) | 8,000 complaints/day (about 0.09/s average); 30-day history ≈ 240,000 complaints, ≈ 720,000 fund hops, ≈ 240,000 observations; 20,000-50,000 registry points across four states; 300-1,500 clusters. Dev and sweep worlds use 7 days. |
| Users | Up to 10 concurrent (team and judges) |
| Ingest to alert visible | p95 under 2 s (delivery excluded); forecast stage p95 under 300 ms |
| Read latency | Heatmap filter response p95 under 1 s (rollups only); alert detail p95 under 500 ms; SSE to screen under 1 s |
| Stress | 50 complaints/s for 60 s with no loss and no duplicate alerts (stress mode of the simulator) |
| Startup | In-process caches rebuilt in under 30 s at default size; crash recovery replays outbox and `unprocessed` complaints |
| Training and sweeps | Model training on default history under 5 min on a laptop; one sweep run (7-day world) under 3 min |
| Hosting | Public HTTPS link on one origin; same images as the offline backup; no external runtime dependencies (map data, fonts, icons and libraries bundled; no CDN, no telemetry) |
| Offline backup | The whole stack runs from Compose on a laptop with no internet; email and SMS use the in-app Outbox viewer |
| Public exposure | Login and control endpoints rate-limited; at most 25 concurrent SSE streams; simulator speed capped at 60x; world auto-pauses after 15 minutes without a viewer; nightly reset restores the seeded state; database size capped by reset |
| Responsive design | Desktop-first (1280 px and up) for the dashboard; alert inbox and detail usable at 360 px; native mobile app out of scope |
| Accessibility | WCAG AA contrast on design tokens; actions keyboard-operable; severity never conveyed by colour alone |
| Security | Input validation at every boundary; argon2 hashing; HttpOnly cookies plus CSRF header; CORS locked to the app origin; login rate limit; `pip-audit` and `npm audit` in CI; secrets only via environment |
| Reproducibility | Same seed and config give an identical world and identical golden-scenario alerts; training is seeded; artifacts carry a data hash |
| Portability | Compose is the reference environment; configuration only via environment and policy YAML; open-source ready (MIT by default) |

**Scalability claims we make, and do not make.** We report our own prototype's measured throughput and latency. We do NOT claim NPCI-scale performance. The scale-out path is already reflected in the ports: PostgreSQL with PostGIS, Redis or Kafka for the event bus and outbox, stateless API replicas with externalised caches, and partitioning by jurisdiction.

---

## §2.8 — Technical Risks & Assumptions

| # | Assumption or risk | Impact if wrong | Mitigation |
|---|---|---|---|
| T3 | Boundary GeoJSON has a clear licence and depicts boundaries acceptably | Legal or sensitivity problem on stage | Use four demo states only; record source and licence in `data/geo/README`; if a national outline is added, use one consistent with official depiction |
| T4 | OpenStreetMap ATM coverage is incomplete | Sparse points | Fill with synthetic points; mark `source` on every location |
| T5 | SMS provider sandbox or trial works during the demo | SMS channel fails live | Automatic fallback to the on-screen SMS outbox; email and dashboard remain |
| T7 | Single-writer SQLite and in-process state suffice at demo volume | Contention or slow boot | Only the API writes; stress mode verifies; ports allow a swap to PostgreSQL |
| T8 | Simulated-time clock and timers are a bug magnet | Escalations and expiries misfire | Injected Clock, property tests, deterministic golden scenario |
| T11 | EM fitting is unstable on sparse clusters | Bad timing forecasts | Minimum-sample rule, shrinkage to global prior, fallback to global mixture, flagged low confidence |
| T12 | Evidence statements may be read as causal explanations | Misleading UI | Labelled "evidence from features", not "why the model decided" |
| T13 | SSE may be buffered by venue proxies | Live updates stall | Client falls back to polling every 5 s |
| T14 | KAYA requires a public hosted link and a public repository | Wrong packaging | One VM with Compose plus a PaaS fallback; offline laptop backup; README explains all three paths |
| T16 | A public simulator control surface can be abused or exhausted | Demo dies or is defaced | Proxy forward_auth, rate limits, speed cap, auto-pause, nightly reset, no writes to anything but the demo world |
| T17 | The hosting VM's ownership, persistence and uptime | Link dead at judging time | Named owner, uptime check, snapshot of the seeded database, PaaS fallback, laptop backup |
| T18 | OSM-derived data (ODbL) and boundary files carry licence obligations in a public repo | Licence breach | Attribution in UI and repo; source and licence per dataset in `data/geo/README`; use only redistributable boundary data |
| T19 | Secrets or demo credentials leak through the public repo | Compromised hosted instance | `.env.example` only, gitleaks in CI, different secrets on the hosted instance, demo accounts have no real power |
| T15 | Straight-line ETAs understate travel time | Overly optimistic interceptability | Speed profiles configurable and conservative; limitation stated in UI copy |

---

## Appendix A — Simulator Parameter Priors

*Sources: public reporting and official statistics (mostly news-grade). Every value is a PRIOR recorded in the simulator's assumption ledger, not a fact. Unpublished quantities are configurable and swept. Keys refer to `config/sim.default.yaml`.*

| Config key | Prior | Confidence | Note |
|---|---|---|---|
| `load.complaints_per_day` | Default 8,000 (PS figure); range 6,500-8,000 | High for order of magnitude | 2025 official average about 6,600/day (derived) |
| `amounts.mean_paise` | About ₹94,000 (2025); ₹1.19 lakh (2024) | High for the mean; shape assumed | Heavy-tailed shape is our assumption |
| `network.layers` | 2 to 12, median about 4 | Medium-low | Case-based, not a distribution |
| `network.accounts_per_cluster` | 10 to about 20,000, median about 100 | Low-medium | Wide sweep |
| `caps.card_atm_daily_inr` | 20,000 to 1,00,000, median about 50,000 | Medium | Bank-specific; no universal RBI cap |
| `caps.cardless_atm_txn_inr` | About 10,000 per transaction | Medium | Bank-specific daily limits |
| `caps.aeps_txn_inr` / `caps.aeps_daily_inr` | About 10,000 per transaction; daily 10,000 to 50,000 | Medium-low | Bank-specific |
| `timing.mixture` | Fast component median about 15 min (range 1 to 60); slow component hours to a day; weights unknown | **Low** | SWEEP the median: 15 / 60 / 240 min |
| `channels.mix` | **Unpublished.** Three labelled-illustrative mixes: ATM-heavy, branch-heavy, balanced | None | Not estimates |
| `footprint.locality` | **Unpublished.** Sweep from local (one district) to dispersed (multi-state) | None | Same-district pattern not supported |
| `footprint.size_per_cluster` | Sweep from tens to hundreds of locations | Low | One hotspot report cites about 5,000 ATM IDs |
| `mule.lifetime_days` | 1 to 180, median about 30 | Low | Wide sweep |
| `geo.state_weights` | Official state-wise cybercrime counts (MHA Lok Sabha UQ 1906, 11 Mar 2025) | Medium | Weights complaint origin, not cash-out location |
| `kit.cards_per_account` | Reported kits typically hold one ATM card, a cheque book, a SIM, a QR code | Low | Models one card per account, cap-driven repeat visits |
| `noise.innocent_layer1_rate` | Assumed 2% to 5% of complaints land on an innocent holder's account (misdirected or compromised) | None (assumed) | Makes the false-hold metric non-vacuous; swept |
| `network.bridge_rate` | Assumed small share of accounts used by two clusters | None (assumed) | Exercises cluster merging |
| `network.hop_visibility` | Share of deeper hops that banks trace and report later, and their lag | None (assumed) | Drives late merges |
| `lag.observation_hours` | Bank/police confirmation lag; range hours to days | None (assumed) | Drives the observed_at clock; swept in the Evaluation page |
| Time-to-withdrawal and residence-to-cash-out distance distributions | **None public** (fewer than 8 numeric observations found) | None | Sweep; never claim calibration; the calibration adapter ships for real data |
| Interception recovery in fast cases | Not used | n/a | Single anecdote; interception is an outcome we compute |
