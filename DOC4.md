# DOC 4 — NAKABANDI: Vibecoding Build Guide

*Status: Confirmed. Synthesises DOC 1 (what), DOC 2 (how), DOC 3 (contracts). This is the executable plan: tracks, steps, sync points, ownership, descope order, rules for agents, checkpoints, deployment.*

## Table of Contents
- §4.0 — Project Context Snapshot
- Track A — Platform & Integration
  - Step A1 — Repo Scaffold & Guardrails
  - Step A2 — Shared Kernel & Contracts
  - Step A3 — Storage, Intake & Registry
  - Step A4 — Access & Audit
  - Step A5 — Skeleton Deployment
  - Step A6 — Pipeline v0 & Golden Test
  - Step A7 — Alerting Core
  - Step A8 — Alerting Delivery, Actions & Webhook
  - Step A9 — Analytics Read Model & Heatmap API
  - Step A10 — Outcomes, Budget & Feedback
  - Step A11 — Demo Mode, Ops & Hardening
  - Step A12 — Case Bundling & Evidence Pack
- Track B — Algorithms & Simulator
  - Step B1 — Simulator v0 Golden Generator
  - Step B2 — Graph & Geo Domain
  - Step B3 — Interception Domain
  - Step B4 — Forecast v0
  - Step B5 — Live Runner & Control API
  - Step B6 — Forecast v1
  - Step B7 — Evaluation Harness
  - Step B8 — Simulator v1 Realism
  - Step B9 — Sweeps & Result Pack
- Track C — Web & Bank Simulator
  - Step C1 — Web Scaffold & Shell
  - Step C2 — Bank Gateway Simulator
  - Step C3 — Shared UI Kit & Stream
  - Step C4 — Alerts Inbox & Detail
  - Step C5 — Map Dashboard
  - Step C6 — Clusters & Cases UI
  - Step C7 — Evaluation, Ops, Outbox & Audit Pages
  - Step C8 — Demo Console
  - Step C9 — Hero-Flow E2E Test
- Track D — Design, Content & Data Curation
  - Step D1 — Design Language & Tokens
  - Step D2 — Core Screens in Figma
  - Step D3 — Copy Pack
  - Step D4 — Evidence Pack & Bank Console Look
  - Step D5 — Geo Data Curation & Attribution
  - Step D6 — Usability Walkthroughs
  - Step D7 — Demo Inputs, README & Architecture Figure
- Track R — Research Agent Tasks
  - Step R1 — Geo Sources & Licences
  - Step R2 — Public Anchors
  - Step R3 — Evidence Law Schedule Text
  - Step R4 — Hosting Options
- §4.1a — Sync Points
- §4.1b — Ownership & Merge Strategy
- §4.1c — Descope Order
- §4.2 — Agentic Coding Rules
- §4.3 — Integration Checkpoints
- §4.4 — Deployment Checklist

---

## §4.0 — Project Context Snapshot

*Copy-paste this block at the start of every agent session.*

```
PROJECT: NAKABANDI
TAGLINE: Predicts where stolen money will turn into cash, and picks the cheapest way to stop it
         before it does, for cyber-cell investigators and I4C analysts.

WHAT WE'RE BUILDING:
  A working prototype for KAYA at IIT (BHU) on the problem "predict likely cash-withdrawal
  locations from cybercrime complaints". Per complaint it resolves the mule cluster, forecasts
  the next cash-out location at three resolutions (with abstention) and its timing, checks
  whether interception is possible in time, and recommends the least intrusive action
  (amount-limited lien, branch/ATM alert, or field team). A human officer approves every
  external action. All data is synthetic, produced by a separate world simulator.

STACK:
  Frontend:   React 18 + TypeScript + Vite, Tailwind + shadcn/ui, TanStack Query, MapLibre GL,
              Cytoscape.js, Recharts
  Backend:    Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, one Uvicorn worker
  Engine:     numpy, scipy, scikit-learn (HistGradientBoosting, BallTree), NetworkX
  Database:   SQLite (WAL) for the product; separate SQLite for the simulator's ground truth
  Auth:       signed JWT in an HttpOnly cookie, argon2, RBAC
  Real-time:  Server-Sent Events
  External systems (separate processes): world simulator (Python), bank gateway simulator (Node 24 LTS + Express)
  Deployment: Docker Compose on one VM behind Caddy (public HTTPS), same Compose offline on a laptop

ARCHITECTURE IN ONE LINE:
  Modular monolith (geo, intake, graph, forecast, interception, alerting, casework, access,
  audit, analytics, evaluation + a pipeline process manager) with layers
  interfaces → application → domain, infrastructure implementing ports, two external simulators,
  React SPA over REST + SSE.

CORE PRINCIPLES TO FOLLOW:
  - Dependencies point inward: interfaces → application → domain. Domain code is pure (no I/O,
    no framework, no wall clock). Infrastructure implements ports.
  - Modules own their tables and talk only through facades (`__init__.py`) or domain events.
  - Every forecasting read takes a required `as_of`; only records with observed_at <= as_of.
  - The API never has access to ground truth; only `evaluation` reads the oracle.
  - Time is injected (Clock). Never call datetime.now() or time.time() outside SystemClock.
  - Human gate: any effect on a third party requires an authenticated Principal.
  - A lien can never exceed the traced disputed amount; there is no whole-account freeze.
  - Money is integer paise; times are event_at / observed_at; ids are ULIDs.
  - Policy values live in config/policy.yaml; no magic numbers in code.
  - Locked contracts (DOC 3 LC-1 to LC-10) change only through the Contract Change Process.

MVP FEATURES (in build order):
  1. M1 Scenario Simulator (golden generator first, then live runner, then realism)
  2. M2 Predictive Engine (heuristic v0, then trained v1)
  3. M6 Interceptability Planner and Intervention Ladder
  4. M4 Alert & Notification System (core, then delivery and actions)
  5. M5 Law Enforcement Interface (access, audit, alerts UI)
  6. M3 Risk Heatmap Dashboard
  Then SHOULD: S1 case bundling, S2 evidence pack, S3 feedback, S4 cold-start drill, S5 Hindi templates.
```

**Team and roles**

| Role | Skills | Owns |
|---|---|---|
| **Systems lead** (Integration Owner) | Experienced vibecoder, systems understanding | Track A |
| **Algo dev** | DSA, limited agent experience | Track B |
| **Web dev** | MERN, limited agent experience | Track C |
| **Designer** | Design, content | Track D; pastes Track R prompts into the research agent |

**Build strategy.** Walking skeleton first: every module gets a simple **v0** that closes the loop end to end (heuristic forecast, basic alert flow, cell-level map), and named **v1 upgrades** (trained scorer, EM timing, realism, filters, budget) follow. If the MUST tier is at risk, v1 upgrades slip first and MUST features stay; §4.1c says exactly in what order. Descope decisions are triggered by build state, never by the calendar.

---

## Track A — Platform & Integration

```
TRACK A: API platform, pipeline, alerting, access, audit, analytics, casework, hosting, CI
  OWNER:       Systems lead, working with a coding agent (Integration Owner for the whole project)
  DEPENDS ON:  None to start. Steps A6 and A9 consume Track B outputs (stubs until Sync 3).
  STEPS:       A1 → A12, ordered by value and dependency; A12 is SHOULD-tier.
```

### Step A1 — Repo Scaffold & Guardrails

```
BUILD STEP A1: Repo Scaffold & Guardrails
  Reference:    DOC 2 → §2.6 (layout and boundary enforcement), §2.2 (CI/CD and tooling)
                DOC 3 → Shared Kernel (structure)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    The monorepo skeleton exactly as DOC 2 §2.6: pyproject.toml (uv workspace: api, world-sim,
    contracts), root package.json with scripts (dev, test, ci, types, seed, reset, sweep),
    .python-version and .nvmrc, ruff, pyright, pytest config, import-linter contracts from the
    §2.6 table, eslint + eslint-plugin-boundaries (empty web app), pre-commit (ruff, gitleaks),
    GitHub Actions ci.yml, .gitignore, .env.example (names only), LICENSE (MIT by
    default), README stub, DOC1 to DOC4, AGENTS.md, vibe-antipatterns.md and prompt-patterns.md at the repo
    root, and an empty docs/ tree (design/, reference/, research/, results/) beside the provided
    docs/state/ files. Empty packages with `__init__.py`
    facades for every module in DOC 2 §2.1. No application code.

  Folder/file targets:
    /pyproject.toml, /package.json, /.github/workflows/ci.yml, /.pre-commit-config.yaml,
    /.importlinter, /apps/{api,web,world-sim,bank-sim}/ (empty), /packages/contracts/,
    /config/, /data/geo/, /infra/, /scripts/, /docs/state/, /DOC1.md … /DOC4.md, /AGENTS.md,
    /vibe-antipatterns.md, /prompt-patterns.md

  Agent prompt hint:
    "Create the monorepo skeleton exactly per DOC 2 §2.6. Tooling and empty packages only, no
    feature code, no extra dependencies. CI must pass on the empty tree and import-linter must
    encode every rule in the §2.6 table."

  YOUR JOB — ALONGSIDE:
    Create the public GitHub repo and protect main; confirm the licence (default MIT); the other
    three clone and run `npm run ci` locally to prove every machine works (Python 3.11, Node 24 LTS).

  Done when:
    `npm run ci` passes locally and in GitHub Actions on the empty tree. On a throwaway branch,
    adding `import sqlalchemy` inside any `domain/` package makes import-linter fail.

  Evidence required:
    Green CI run link; the failing import-linter output from the throwaway branch; one line
    confirming all four machines ran `npm run ci`.

  Common drift to watch for:
    The agent adds a sample app, extra libraries, Poetry or a Makefile (stack substitution, AP-07).
    Keep tooling exactly as DOC 2 §2.2.
```

### Step A2 — Shared Kernel & Contracts

```
BUILD STEP A2: Shared Kernel & Contracts
  Reference:    DOC 3 → Shared Kernel; Locked Contracts LC-1, LC-2, LC-3, LC-7, LC-9
                DOC 2 → §2.5 (principles)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    packages/contracts: enums.py (LC-2), ingest.py (LC-1 Pydantic models), generated JSON Schemas
    committed under schemas/. nakabandi/shared: types, ids, clock (Clock, SystemClock, SimClock),
    scheduler, events (DomainEvent, EventBus and the LC-3 payloads), errors and messages,
    config (Settings), policy (typed model that loads config/policy.yaml), uow (protocol),
    logging (structlog with scrubbing). config/policy.yaml with EVERY LC-7 key and the starting
    values written in DOC 3. Unit tests for kernel behaviour.

  Folder/file targets:
    /packages/contracts/src/nakabandi_contracts/, /apps/api/src/nakabandi/shared/,
    /config/policy.yaml, /config/sim.default.yaml (skeleton keys only)

  Agent prompt hint:
    "Implement DOC 3 Shared Kernel and LC-1/LC-2/LC-3/LC-7 exactly as written. Do not add enum
    members, fields or events that are not in the contracts. No business logic."

  YOUR JOB — ALONGSIDE:
    Read the generated JSON Schemas once against DOC 3 LC-1; send the schema folder link to the
    other three (this is Sync 1).

  Done when:
    Kernel tests pass (SimClock monotonic, Scheduler order/replace/cancel/exception isolation,
    EventBus order, Policy rejects a file with a missing or mistyped key); schemas regenerate
    with no diff; a hand-written sample payload validates against each ingest schema.

  Evidence required:
    pytest output; `git diff --stat` limited to the targets above; the list of generated schema
    files.

  Common drift to watch for:
    "Helpful" extra fields or enum members (interface invention, AP-09); reading the wall clock
    outside SystemClock; putting constants in code instead of policy.yaml (AP-10).
```

### Step A3 — Storage, Intake & Registry

```
BUILD STEP A3: Storage, Intake & Registry
  Reference:    DOC 3 → M2 (intake); LC-1, LC-10
                DOC 2 → §2.3 (entities), §2.4 (ingest endpoints)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    SQLAlchemy models and create_all for the geo and intake tables (DOC 2 §2.3, SQLite WAL);
    repositories (every forecasting read has a required `as_of`); application use cases
    IngestRegistry, IngestComplaints, IngestHops, IngestObservations, AdvanceClock; the
    UnitOfWork implementation; routers POST /ingest/{registry,complaints,hops,cashout-observations,tick}
    behind a service API key; per-item `rejected[]` reporting; idempotency by key; SimClock
    advances from batch sim_time and Tick; `npm run seed` CLI that loads a JSONL file through the
    SAME use cases (no bypass).

  Folder/file targets:
    /apps/api/src/nakabandi/{intake,geo}/, /apps/api/src/nakabandi/shared/infrastructure/uow.py,
    /apps/api/src/nakabandi/main.py (composition root), /scripts/seed

  Agent prompt hint:
    "Implement the intake module per DOC 3 M2 (intake) and geo registry application per DOC 3 M3.
    Repositories only in infrastructure; routers only parse and call one use case. Every read
    takes as_of. No forecasting logic."

  YOUR JOB — ALONGSIDE:
    Write a 20-row hand fixture (`tests/fixtures/mini_ingest.json`) from LC-1 as an independent
    check on the schemas.

  STUB/MOCK STRATEGY:
    Until Step B1 produces the golden stream, use the hand fixture. Swap when Sync 2 confirms.

  Done when:
    Posting the fixture returns accepted counts; resending with the same idempotency key is a
    no-op; a malformed item is returned in `rejected[]` with index and code; a record with
    observed_at later than the clock is invisible to as_of reads (test).

  Evidence required:
    Test output for the four checks above; the table list (matches DOC 3 LC-10 ownership).

  Common drift to watch for:
    Cross-module table access; business rules in routers; repositories that commit; a default
    value for `as_of` (must be required).
```

### Step A4 — Access & Audit

```
BUILD STEP A4: Access & Audit
  Reference:    DOC 3 → M5 (API side); LC-2 (roles and permissions)
                DOC 2 → §2.3 (sensitive data), §2.2 (auth decision)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    Module access: users table (with locale), argon2 hashing, JWT cookie (HttpOnly, SameSite=Lax,
    Secure in hosted mode), Principal and Scope, permission matrix loaded from policy.yaml,
    masking policy, routes /auth/{login,logout,me,check,demo-users}, login rate limit, seeded
    demo users (one per role, demo-only passwords). Module audit: hash-chained AuditLog whose
    append participates in the caller's unit of work, /audit and /audit/verify, plus dependency
    `get_principal`.

  Folder/file targets:
    /apps/api/src/nakabandi/{access,audit}/

  Agent prompt hint:
    "Implement access and audit per DOC 3 M5 (API side). Authentication, authorization and masking
    are three separate files. The audit repository exposes INSERT and SELECT only."

  YOUR JOB — ALONGSIDE:
    Pick personas and names for the demo users (with the Designer) so the UI reads naturally.

  Done when:
    Table-driven tests cover every role x permission; the bank_nodal principal never receives
    another bank's identifiers (property test); a tampered audit row makes /audit/verify fail;
    /auth/check returns 204 or 403 as expected; login is rate limited.

  Evidence required:
    pytest output; a curl transcript of login, /auth/me and /auth/check for two roles.

  Common drift to watch for:
    Ad hoc role checks in routers; storing tokens in localStorage; adding update/delete methods
    to the audit repository.
```

### Step A5 — Skeleton Deployment

```
BUILD STEP A5: Skeleton Deployment
  Reference:    DOC 2 → §2.2 (Deployment decision and hosted topology), §2.7 (hosting rows)
                DOC 4 → §4.4 (deployment checklist)
  EXECUTOR:     Coding agent (Systems lead) plus Human for provisioning
  REASON:       Deploy a walking skeleton early so hosting risk shows up early, not at the end.

  What to build:
    Dockerfiles for api (serving a placeholder SPA), world-sim (placeholder), bank-sim
    (placeholder); docker-compose.yml; Caddyfile for one HTTPS origin with /, /api, /bank and
    /sim-control (the last via forward_auth to /api/v1/auth/check?role=demo_operator); env wiring;
    GET /api/v1/system/health; uptime check.

  Folder/file targets:
    /infra/{docker-compose.yml,Caddyfile,Dockerfile.api,Dockerfile.worldsim,Dockerfile.banksim,.env.example}

  Agent prompt hint:
    "Write Compose and Caddy exactly as DOC 2 §2.2 hosted topology. No Kubernetes, no PaaS-specific
    files, no secrets in images. Same Compose must run on a laptop with no internet."

  YOUR JOB — ALONGSIDE:
    Provision the VM and DNS (use the Track R4 hosting-options output), install Docker, put
    secrets on the VM only, and enable an external uptime check.

  Done when:
    A public HTTPS URL serves the placeholder page and /api/v1/system/health; /sim-control returns
    401 or 403 without a demo_operator login; the same Compose starts on a laptop with the
    network off.

  Evidence required:
    The public URL; a curl of health and of the gated path; a log of the offline laptop start.

  Common drift to watch for:
    Adding a PaaS config or Kubernetes; baking .env into an image; exposing world-sim's oracle or
    world.db.
```

### Step A6 — Pipeline v0 & Golden Test

```
BUILD STEP A6: Pipeline v0 & Golden Test
  Reference:    DOC 3 → M2 (pipeline), Evaluation Harness (golden run)
                DOC 2 → §2.1 (primary runtime flow, invariants 4 and 9)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    `pipeline` module: ProcessComplaint (graph.resolve → graph.context_for → forecast.generate →
    interception.assess → alerting.raise_or_merge), marking complaints processed or unprocessed
    with the failing stage; RetryUnprocessed; RefreshOpenAlerts. Stub facades under tests/stubs
    return deterministic canned outputs matching the LC-4 shapes. A golden-scenario test harness
    that ingests the golden stream with a SimClock and snapshots the resulting alerts.

  Folder/file targets:
    /apps/api/src/nakabandi/pipeline/, /apps/api/tests/{stubs,golden}/

  Agent prompt hint:
    "Implement the pipeline process manager per DOC 3 M2. It is the only place that calls several
    module facades. Use stub facades that match the LC-4 shapes until real ones exist."

  YOUR JOB — ALONGSIDE:
    Review the canned outputs with the Algo dev so stubs match real shapes (prevents Sync 3 surprises).

  STUB/MOCK STRATEGY:
    Stubs stand in for graph, forecast, interception and alerting until Sync 3. Replace one facade
    at a time and rerun the golden test.

  Done when:
    The pipeline processes the fixture end to end with stubs; a forced stage failure leaves the
    complaint `unprocessed` and RetryUnprocessed recovers it; import-linter confirms only
    `pipeline` and `main.py` call several facades.

  Evidence required:
    Golden test output; the forced-failure test; the import-linter run.

  Common drift to watch for:
    Modules calling each other directly to "save time" (layer violation, AP-06); events used for
    control flow instead of explicit calls.
```

### Step A7 — Alerting Core

```
BUILD STEP A7: Alerting Core
  Reference:    DOC 3 → M4 (domain, application, read API); LC-4, LC-5
                DOC 2 → §2.1 invariants 4 and 7
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    alerting domain: Alert entity and state machine, dedup_key, severity, routing, outcome
    classification skeleton. Application: RaiseOrMergeAlert, AcknowledgeAlert, EscalateAlert,
    ExpireAlert, RebuildTimers, ClusterMerged re-keying. Infrastructure: repositories, SseHub.
    Interfaces: GET /alerts, GET /alerts/{id}, POST /alerts/{id}/acknowledge, GET /stream
    (alert.created, alert.updated, sim.time; heartbeat). All thresholds from policy.

  Folder/file targets:
    /apps/api/src/nakabandi/alerting/{domain,application,infrastructure,interfaces}/ (no channels
    other than SSE yet)

  Agent prompt hint:
    "Implement alerting core per DOC 3 M4 up to but excluding outbox channels, actions and budget.
    State machine is a transition table; timers use Scheduler and the injected Clock."

  YOUR JOB — ALONGSIDE:
    When the endpoints exist, tell the Web dev; they regenerate types and swap fixtures for the
    API (Sync 4).

  Done when:
    Every legal and illegal transition is tested; duplicate complaints merge into one alert;
    escalation and expiry fire on a fake clock; GET /alerts respects scope; SSE emits alert.created
    on raise; OpenAPI shows AlertSummary and AlertDetail exactly as LC-4.

  Evidence required:
    pytest output; the OpenAPI excerpt for alerts; an SSE capture of one alert.created.

  Common drift to watch for:
    Business rules inside routers; wall-clock timers; adding statuses not in LC-2.
```

### Step A8 — Alerting Delivery, Actions & Webhook

```
BUILD STEP A8: Alerting Delivery, Actions & Webhook
  Reference:    DOC 3 → M4 (RecordAction, outbox, channels, callback); LC-6
                DOC 2 → §2.1 invariant 7 (human gate), §2.2 (notifications, background)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    Outbox and DeliverOutbox worker; channels: SmtpEmail (optional), ProviderSms with automatic
    fallback to OutboxSms, BankWebhook (HMAC, timestamp, Idempotency-Key); rendered_body stored
    per delivery; /outbox view endpoint; RecordAction (needs a Principal, authorises, validates
    request_hold through interception.validate_lien, audits in the same unit of work, enqueues the
    hold_request webhook); HandleBankCallback; English templates (S5 adds Hindi).

  Folder/file targets:
    /apps/api/src/nakabandi/alerting/{application/{outbox,record_action,bank_callback}.py,
    infrastructure/channels/, interfaces/{actions,integrations,outbox_view}.py, templates/en/}

  Agent prompt hint:
    "Implement delivery and actions per DOC 3 M4. Nothing but RecordAction may create a
    hold_request delivery. Channel adapters only send; failures become Delivery rows."

  YOUR JOB — ALONGSIDE:
    Run the bank simulator (Step C2) against the API together with the Web dev at Sync 5.

  STUB/MOCK STRATEGY:
    Point BankWebhook at a local echo server until C2 is ready; keep the signature code identical.

  Done when:
    request_hold by an investigator creates an Action, an audit entry and a hold_request delivery;
    a bank_nodal principal is denied; a failing channel retries with backoff then dead-letters and
    shows in the outbox view; the callback updates the action status; signature verification
    passes against the bank simulator.

  Evidence required:
    Test output for each of those; one outbox-viewer JSON sample; the webhook round-trip log.

  Common drift to watch for:
    A second code path that can send a hold request; skipping the lien re-validation; unmasked
    account refs in rendered bodies.
```

### Step A9 — Analytics Read Model & Heatmap API

```
BUILD STEP A9: Analytics Read Model & Heatmap API
  Reference:    DOC 3 → M3 (geo and analytics); LC-4 (HeatmapResponse), LC-5
                DOC 2 → §2.3 (HeatRollup)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    Geo application endpoints /geo/regions and /geo/locations (uses the geo domain from B2);
    analytics: projectors on AlertRaised/AlertUpdated/ForecastGenerated writing HeatRollup and
    bumping version; QueryHeatmap (scope-restricted, window sum, k-threshold suppression, district
    roll-up, ETag), QueryTimeseries, QueryLiveMetrics; heat.version SSE event.

  Folder/file targets:
    /apps/api/src/nakabandi/analytics/, /apps/api/src/nakabandi/geo/{application,infrastructure,interfaces}/

  Agent prompt hint:
    "Implement analytics per DOC 3 M3 API side. Read models come from events only; never query
    another module's tables. The potential layer is a decayed persistence estimate."

  YOUR JOB — ALONGSIDE:
    Hand-compute one rollup from the golden run for the test fixture.

  Done when:
    Rollups from the golden run match the hand-computed fixture; filters change results; a
    district_officer sees only their district; small-count cells are suppressed above location
    level; repeated identical queries return 304.

  Evidence required:
    Test output; two sample HeatmapResponse bodies with different filters.

  Common drift to watch for:
    Reading forecasts or alerts tables directly; hard-coded amount bands (they come from policy).
```

### Step A10 — Outcomes, Budget & Feedback

```
BUILD STEP A10: Outcomes, Budget & Feedback
  Reference:    DOC 3 → M4 (outcome, budget), S3
                DOC 2 → §2.1 (feedback path)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    ReconcileOutcome with hit/late/miss windows and grace; alert budget per role and jurisdiction
    per shift with seeded exploration probes and deferred alerts; review queue ordering by
    uncertainty; MarkOutcome (officer) and ApplyConfirmedCashOut via the graph facade;
    POST /alerts/{id}/outcome.

  Folder/file targets:
    /apps/api/src/nakabandi/alerting/{domain/{budget,outcome,uncertainty}.py,application/{reconcile,feedback}.py}

  Agent prompt hint:
    "Implement outcomes, budget and feedback per DOC 3 M4 and S3. Misses are decided by timers,
    not by data arrival. Exploration draws are seeded by alert id."

  YOUR JOB — ALONGSIDE:
    None: pure codegen, watch and verify.

  STUB/MOCK STRATEGY:
    If B2's apply_confirmed is not ready, stub it with a recording fake and swap at the next merge.

  Done when:
    Outcome classification is correct at window and grace edges; the same seed gives the same
    exploration picks; deferred alerts remain reachable under Backlog; a confirmed hit changes the
    next forecast on a fixture.

  Evidence required:
    Test output; a before/after forecast diff on the fixture.

  Common drift to watch for:
    Random choices from an unseeded generator; deleting deferred alerts instead of ranking them.
```

### Step A11 — Demo Mode, Ops & Hardening

```
BUILD STEP A11: Demo Mode, Ops & Hardening
  Reference:    DOC 2 → §2.7 (public exposure, stress, startup), §2.8 (T7, T8, T16, T17)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    Hosted-demo settings: login and control rate limits, cap of 25 SSE streams, simulator speed
    cap, auto-pause after 15 minutes without a viewer, nightly reset job restoring the seeded
    database, /auth/demo-users flag; /system/metrics (events per second, stage latencies p50 and
    p95, outbox depth, delivery failures); a stress script (50 complaints/s for 60 s); a
    kill-and-restart recovery test.

  Folder/file targets:
    /apps/api/src/nakabandi/shared/{ratelimit,metrics}.py, /apps/api/src/nakabandi/main.py,
    /scripts/{stress,reset}, /infra/ (cron or scheduler for the nightly reset)

  Agent prompt hint:
    "Add hosted-demo protections and ops metrics per DOC 2 §2.7. Configuration only through
    environment and policy; nothing product-specific may depend on demo mode being on."

  YOUR JOB — ALONGSIDE:
    Run the stress script and the restart test on the VM yourself and read the numbers.

  Done when:
    Stress run: no lost complaints, no duplicate alerts; after `kill -9` and restart, timers and
    outbox resume; auto-pause and the nightly reset are observed on the VM; measured p95 numbers
    are on the Ops page.

  Evidence required:
    Stress and restart logs; the metrics output; a screenshot of the Ops page with real numbers.

  Common drift to watch for:
    Demo protections that leak into product code paths; disabling limits "temporarily" and forgetting.
```

### Step A12 — Case Bundling & Evidence Pack

```
BUILD STEP A12: Case Bundling & Evidence Pack   (SHOULD tier)
  Reference:    DOC 3 → S1, S2
                Track R output → docs/reference/bsa_s63_schedule.md (R3)
  EXECUTOR:     Coding agent (Systems lead)

  What to build:
    casework: build_case, render_brief, BundleCluster (debounced on ClusterUpdated), /clusters and
    /cases endpoints; evidence: EvidenceBundle, hash_report, Section63Draft (labelled DRAFT and laid
    out from the R3 Schedule text), ReportLab PDF with a Devanagari-capable font, LocalFileStore,
    POST /alerts/{id}/evidence-pack and download; audit head hash embedded.

  Folder/file targets:
    /apps/api/src/nakabandi/casework/

  Agent prompt hint:
    "Implement S1 and S2 per DOC 3. The certificate is an unsigned drafting aid labelled DRAFT. The
    PDF's own SHA-256 is stored outside the PDF."

  YOUR JOB — ALONGSIDE:
    Check the certificate layout against R3's transcription of the official Schedule form.

  Done when:
    Two complaints on one cluster give one case with both; hash reports reproduce; a tampered audit
    row breaks verify and mismatches the pack's head hash; non-LEA roles get masked refs.

  Evidence required:
    Test output; one generated PDF attached to the review.

  Common drift to watch for:
    The brief asserting guilt or naming real persons; presenting the certificate as compliant.
```

---

## Track B — Algorithms & Simulator

```
TRACK B: world simulator, graph and geo domain, interception, forecast, evaluation
  OWNER:       Algo dev, working with a coding agent (the pure-code seam)
  DEPENDS ON:  Track A Step A2 (contracts merged) for anything that imports contracts; B3 can
               start as soon as A2 lands. B4 needs B2. Integration into the pipeline is Sync 3.
  STEPS:       B1 → B9. B1 and B3 are the critical early wins.
```

### Step B1 — Simulator v0 Golden Generator

```
BUILD STEP B1: Simulator v0 Golden Generator
  Reference:    DOC 3 → M1 (core, writer, golden config); LC-1
                DOC 2 → §2.2 (simulator decision), Appendix A (priors)
  EXECUTOR:     Coding agent (Algo dev)

  What to build:
    worldsim core minimal: rng_for (SeedSequence keyed by names), config loading, a small registry
    (synthetic points over the four states), clusters with a fixed two-component timing mixture,
    complaint → hop → cash-out generation, observe() with lag, JsonlEmitter and ApiEmitter (no
    live loop yet), the `golden` config (3 days, about 600 complaints/day, 6 clusters, seed 42) and
    a stream-hash test, CLI `history`.

  Folder/file targets:
    /apps/world-sim/src/worldsim/{core,writer}/, /apps/world-sim/tests/, /config/sim.default.yaml

  Agent prompt hint:
    "Implement the v0 golden generator per DOC 3 M1. Pure core, no I/O. Determinism first: same
    seed gives an identical event stream. No live runner, no realism features yet."

  YOUR JOB — ALONGSIDE:
    Read DOC 2 Appendix A and confirm the golden config's parameters sit inside the priors.

  Done when:
    Same seed gives the same stream hash; observed_at >= event_at for every event (property test);
    the output validates against the contracts JSON Schemas; the API ingest accepts the stream
    (Sync 2).

  Evidence required:
    Stream hash printed twice; property-test output; the ingest response counts.

  Common drift to watch for:
    A global numpy RNG; starting the live loop or scenarios early (scope drift, AP-01); importing
    nakabandi.* (forbidden).
```

### Step B2 — Graph & Geo Domain

```
BUILD STEP B2: Graph & Geo Domain
  Reference:    DOC 3 → M2 (graph), M3 (geo domain)
  EXECUTOR:     Coding agent (Algo dev)

  What to build:
    DisjointSet (path compression, union by size, deterministic tie-break), ClusterIndex.resolve,
    footprint and PointInTimeStats, ClusterService facade (resolve, context_for, rebuild),
    ResolveCluster/RebuildIndex use cases and repositories; RefineCommunities (annotate only);
    geo domain: cell_id_for, SpatialIndex (BallTree, haversine).

  Folder/file targets:
    /apps/api/src/nakabandi/graph/, /apps/api/src/nakabandi/geo/domain/

  Agent prompt hint:
    "Implement graph and geo domain per DOC 3. Domain code is pure Python and numpy; every read
    takes as_of. Merges emit ClusterMerged and never split."

  YOUR JOB — ALONGSIDE:
    Write the DisjointSet property tests yourself first (this is your strongest seam); let the
    agent make them pass.

  Done when:
    Property tests pass (union commutative and idempotent, find stable, merge yields one
    component); accounts sharing a truth cluster in the golden stream resolve to one cluster except
    where the config planted bridge accounts; a leakage test passes (a future observation does not
    change context_for).

  Evidence required:
    Test output; a small table of golden clusters vs resolved clusters.

  Common drift to watch for:
    Splitting clusters (post-MVP); reading data without as_of; importing infrastructure into domain.
```

### Step B3 — Interception Domain

```
BUILD STEP B3: Interception Domain
  Reference:    DOC 3 → M6
  EXECUTOR:     Coding agent (Algo dev)
  REASON:       Small, pure, and independent, so it can start right after A2.

  What to build:
    UnitIndex, HaversineEstimator, interception_probability, verdict_from, ladder_level,
    LienProposal (frozen, validated), build_lien, AssessInterception use case, facade,
    repositories, policy-driven thresholds and ladder table.

  Folder/file targets:
    /apps/api/src/nakabandi/interception/

  Agent prompt hint:
    "Implement M6 per DOC 3. LienProposal must be impossible to construct with proposed above
    disputed, without expiry, or without a complaint anchor. No field for a whole-account freeze."

  YOUR JOB — ALONGSIDE:
    None: pure codegen, watch and verify (the invariants are the point; read those tests).

  Done when:
    Property test: no valid LienProposal has proposed > disputed; the ladder table has a rule for
    every channel x verdict pair (exhaustive test); ETA is monotone in distance; probability is
    monotone non-increasing in ETA; the no-units case returns NOT_INTERCEPTABLE with NO_UNITS.

  Evidence required:
    Test output; the ladder table as loaded from policy.

  Common drift to watch for:
    Adding a "freeze_account" option; hard-coding thresholds; using the wall clock for expiry.
```

### Step B4 — Forecast v0

```
BUILD STEP B4: Forecast v0
  Reference:    DOC 3 → M2 (forecast)
                DOC 2 → §2.2 (location scoring, timing decisions)
  EXECUTOR:     Coding agent (Algo dev)

  What to build:
    forecast types; generate_candidates; build_features with FEATURE_REGISTRY and BLOCKLIST;
    HeuristicScorer implementing LocationScorer (hand weights from policy: bank match, distance
    decay, cluster history, channel); normalise and aggregate_levels; apply_abstention;
    MixtureTimingModel with FIXED mixture parameters and conditioning on elapsed time; explain();
    Forecaster facade; GenerateForecast use case; repository.

  Folder/file targets:
    /apps/api/src/nakabandi/forecast/

  Agent prompt hint:
    "Implement the v0 forecast per DOC 3 M2 with a heuristic scorer behind the LocationScorer
    port and a fixed-parameter timing model behind TimingModel. Same output shapes as LC-4."

  YOUR JOB — ALONGSIDE:
    Sanity-check three explain() outputs by eye for wording and correctness with the Designer.

  Done when:
    Probabilities sum to 1 within 1e-6 at every level; cell probability equals the sum of its
    locations; abstention is monotone in the threshold; the leakage test passes; the golden pipeline
    produces forecasts (Sync 3).

  Evidence required:
    Test output; one Forecast JSON for a golden complaint.

  Common drift to watch for:
    Training a model early (that is B6); fetching data inside domain functions; demographic-style
    features (BLOCKLIST test must stay green).
```

### Step B5 — Live Runner & Control API

```
BUILD STEP B5: Live Runner & Control API
  Reference:    DOC 3 → M1 (runner, control API, oracle API, guided demo); LC-8
  EXECUTOR:     Coding agent (Algo dev)

  What to build:
    LiveRunner (speed loop, batching, ticks, pause/resume, speed change), truth_store (world.db),
    control API (start, pause, resume, speed 1..60, reset, seed, inject-cluster, status), oracle API
    (never routed), guided_demo script and inject_cluster, ApiEmitter retry with the same
    idempotency key and a stalled state.

  Folder/file targets:
    /apps/world-sim/src/worldsim/{runner.py,control_api/,oracle_api/,truth_store.py,core/scenarios.py}

  Agent prompt hint:
    "Implement the live runner and control API per DOC 3 M1 and LC-8. Speed changes must never
    duplicate or skip simulated time. The oracle API is internal only."

  YOUR JOB — ALONGSIDE:
    Run it against the skeleton deployment on the VM for ten unattended minutes.

  Done when:
    start, pause, resume, speed and inject change the status endpoint as specified; a stubbed API
    failure triggers retries with the same key and a `stalled` status; a ten-minute unattended run
    ends with no errors.

  Evidence required:
    Status transitions log; the retry test; the ten-minute run log.

  Common drift to watch for:
    Exposing oracle endpoints through any route; letting ticks depend on wall time drift.
```

### Step B6 — Forecast v1

```
BUILD STEP B6: Forecast v1
  Reference:    DOC 3 → M2 (training), S4 (novelty)
                DOC 2 → §2.2 (scorer and timing decisions)
  EXECUTOR:     Coding agent (Algo dev)

  What to build:
    PointInTimeStats replay, TrainingSetBuilder (time-based split), HistGradientBoostingScorer with
    isotonic calibration before normalisation, MixtureTimingModel with EM and per-cluster shrinkage,
    Trainer and model store (joblib plus metadata and data hash), tuned abstention thresholds,
    novelty() and DistrictPrior fallback, fallback to the v0 scorer when model files are missing.

  Folder/file targets:
    /apps/api/src/nakabandi/forecast/{domain/{training,scorers,timing,priors}.py,application/train.py,infrastructure/model_store.py}, /apps/api/src/nakabandi/graph/domain/novelty.py

  Agent prompt hint:
    "Upgrade the forecast to v1 per DOC 3 without changing any output shape or port. Point-in-time
    features only; calibrate before normalising; keep the v0 scorer as the fallback."

  YOUR JOB — ALONGSIDE:
    Read the calibration plot and the abstention rate, and decide the thresholds with the Systems
    lead (a judgment call the agent cannot make).

  Done when:
    Training on a 7-day simulated world takes under 5 minutes; the EM step recovers a planted
    mixture within tolerance; the leakage test passes; a calibration curve is produced; the model
    loads at API boot and a missing file falls back to v0 with a visible banner.

  Evidence required:
    Training log with timings; the calibration plot; the leakage test output.

  Common drift to watch for:
    Random train/validation splits (leakage); changing LC-4 shapes; adding GNNs or SHAP.
```

### Step B7 — Evaluation Harness

```
BUILD STEP B7: Evaluation Harness
  Reference:    DOC 3 → Evaluation Harness
                DOC 2 → §2.1 (evaluation harness)
  EXECUTOR:     Coding agent (Algo dev)

  What to build:
    metrics.py (hit_rate_at_k, precision_at_k, lead_time, brier, reliability_curve,
    interceptable_share, dispatches_per_interception, false_hold_rate, cold_start_curve, abstention
    rate), baselines (hotspot, nearest-to-victim, bank-footprint) implementing LocationScorer,
    run_experiment through the SAME ingest and pipeline use cases, OracleClient, expand_grid,
    store and /evaluation/runs endpoints, first golden run.

  Folder/file targets:
    /apps/api/src/nakabandi/evaluation/

  Agent prompt hint:
    "Implement the evaluation harness per DOC 3. Metrics are pure functions tested on hand-computed
    fixtures. Replay uses the real application use cases, never a shortcut. Only this module may
    import the oracle client."

  YOUR JOB — ALONGSIDE:
    Hand-compute two metric fixtures yourself (small tables) before the agent writes the tests.

  Done when:
    Every metric matches its hand fixture; run_experiment on the golden config is deterministic
    (same config hash, same rows); results appear at /evaluation/runs; abstained items are excluded
    from precision but counted in the abstention rate.

  Evidence required:
    Test output; the JSON of a golden run.

  Common drift to watch for:
    Importing the oracle from anywhere else; computing metrics on data the pipeline could not have
    seen at the time.
```

### Step B8 — Simulator v1 Realism

```
BUILD STEP B8: Simulator v1 Realism
  Reference:    DOC 3 → M1 (behaviour, caps, ledger, checks); DOC 2 → Appendix A
                Track R output → data/anchors/public_anchors.json (R2)
  EXECUTOR:     Coding agent (Algo dev)

  What to build:
    split_under_caps, pick_channel, footprint locality and size, bridge accounts, hop visibility and
    lag, innocent-layer-1 noise, state-weighted complaint geography, mixture timing per cluster
    type, AssumptionLedger (Markdown and JSON per run), compare_to_public (reports matches and
    mismatches), sweep-world headless mode, real ATM and branch registry from the curated geo data.

  Folder/file targets:
    /apps/world-sim/src/worldsim/core/{behaviour,timing,ledger,checks,clusters,registry}.py, /data/anchors/

  Agent prompt hint:
    "Add the realism features listed in DOC 3 M1 without changing any emitted contract. Every
    parameter is read from sim.default.yaml and appears in the ledger. Do not tune to look good."

  YOUR JOB — ALONGSIDE:
    Read the compare_to_public report and record mismatches honestly in the README notes.

  STUB/MOCK STRATEGY:
    If the curated geo data (D5) or anchors (R2) are late, use synthetic points and DOC 1's verified
    figures; swap on arrival.

  Done when:
    Caps are never exceeded (property test); ledger lists every config key once; the check report
    compares complaints/day, mean amount and state weights and shows matches AND mismatches; the
    golden stream hash is unchanged when realism flags are off.

  Evidence required:
    Test output; the ledger file; the check report.

  Common drift to watch for:
    Tuning parameters until the model looks good (circularity); dropping mismatches from the report.
```

### Step B9 — Sweeps & Result Pack

```
BUILD STEP B9: Sweeps & Result Pack
  Reference:    DOC 3 → Evaluation Harness (sweeps), S3 (feedback on/off), S4 (cold-start curve)
  EXECUTOR:     Human (Algo dev) running the harness, with a coding agent for scripting
  REASON:       Running experiments and reading results is judgment work; the agent scripts the runs.

  What to build:
    Run the default sweep (timing median 15/60/240 x three channel mixes x locality local/dispersed),
    feedback on/off, and the cold-start curve on 7-day worlds; export JSON and Markdown to
    docs/results/, including the three baselines side by side and every mismatch or failure.

  Folder/file targets:
    /docs/results/, /scripts/sweep

  Agent prompt hint:
    "Script the sweep runs per DOC 3 and write results to docs/results as JSON and Markdown. Report
    n and refuse rates when n < 30."

  YOUR JOB — ALONGSIDE:
    Read the results critically with the Systems lead: where do we beat the baselines, where not,
    and what to say honestly on the slide.

  Done when:
    docs/results contains the full sweep with baselines and abstention rates; the Evaluation page
    displays it; failures are listed, not hidden.

  Evidence required:
    The results Markdown; the run ids.

  Common drift to watch for:
    Cherry-picking cells; reporting a single accuracy number.
```

---

## Track C — Web & Bank Simulator

```
TRACK C: web app shell, alerts/map/clusters/cases/evaluation/ops/outbox/audit/demo UI, bank
         gateway simulator, the hero-flow E2E test
  OWNER:       Web dev, working with a coding agent
  DEPENDS ON:  Track A Step A2 (contracts, for generated types) to start C1 for real; Track A
               Step A5 (skeleton deployment) before the app is wired to the same Compose origin.
               C4/C5/C7 build against fixtures until their backing Track A steps land (Sync 4).
               C2 depends on A2 for LC-6 shapes only, otherwise independent.
  STEPS:       C1 → C9, ordered by value and dependency; C9 is the whole track's integration proof.
```

### Step C1 — Web Scaffold & Shell

```
BUILD STEP C1: Web Scaffold & Shell
  Reference:    DOC 3 → Web App Shell & Design System
                DOC 2 → §2.2 (client stack), §2.6 (repo layout, eslint boundaries)
  EXECUTOR:     Coding agent (Web dev)

  What to build:
    apps/web Vite + React 18 + TypeScript scaffold; app/{main.tsx, providers.tsx} (QueryClient,
    router, toast, a stream provider placeholder), app/routes.tsx with RoleGuard, app/layout/
    (Shell.tsx top bar with sim time/role/connection dot, SideNav.tsx), app/auth/ (LoginPage.tsx
    with quick-login buttons, usePrincipal.ts, RoleGuard.tsx); shared/api/{client.ts, apiError.ts}
    against a placeholder schema.d.ts; shared/tokens/ placeholder tokens.css and tailwind.preset.ts;
    empty shared/ui/ folder; eslint-plugin-boundaries configured so a feature folder can never
    import another feature folder.

  Folder/file targets:
    /apps/web/src/{app,shared}/

  Agent prompt hint:
    "Scaffold apps/web exactly per DOC 3 Web App Shell. Providers, routes, layout and login only —
    no feature pages yet. Configure eslint-plugin-boundaries so a feature folder cannot import
    another feature folder."

  YOUR JOB — ALONGSIDE:
    None — pure codegen, watch and verify.

  STUB/MOCK STRATEGY:
    Use a hardcoded principal object and a fixture demo-users list matching the LC-2 shapes until
    Track A Step A4's /auth endpoints exist; swap once available.

  Done when:
    `npm run dev` boots to a login screen; RoleGuard redirects an unauthenticated user to /login and
    preserves the intended route; on a throwaway branch, a feature importing another feature makes
    eslint fail.

  Evidence required:
    A dev-server screenshot or log; the failing eslint-boundaries output; the diff limited to the
    listed targets.

  Common drift to watch for:
    Building alert/map feature pages early (scope drift, AP-01); reaching for a UI library outside
    Tailwind/shadcn-ui (stack substitution, AP-07).
```

### Step C2 — Bank Gateway Simulator

```
BUILD STEP C2: Bank Gateway Simulator
  Reference:    DOC 3 → Bank Gateway Simulator; Locked Contract LC-6
  EXECUTOR:     Coding agent (Web dev)
  REASON:       A separate Node/Express service is both a true system boundary (DOC 2 §2.2) and a
                natural fit for the MERN teammate; independent of the rest of the web app.

  What to build:
    apps/bank-sim exactly per DOC 3's module structure: server.ts, config.ts, verify.ts
    (verifySignature, withinWindow, IdempotencyStore), store.ts (better-sqlite3: requests, liens,
    callbacks), routes/{webhook.ts, console.ts}, services/{liens.ts, callback.ts}, simtime.ts,
    types.ts (from the contracts JSON Schema), views/ (EJS console templates), tests/ (supertest).

  Folder/file targets:
    /apps/bank-sim/src/

  Agent prompt hint:
    "Implement the bank gateway simulator per DOC 3 exactly, including the LC-6 shapes.
    Verification, storage, lien rules and callbacks stay in separate files. Use better-sqlite3, not
    an ORM."

  YOUR JOB — ALONGSIDE:
    Agree the WEBHOOK_SECRET and env wiring with the Systems lead before Sync 5, so both sides use
    the same secret from the start.

  STUB/MOCK STRATEGY:
    Point SIM_STATUS_URL at a canned JSON file until Track B Step B5's live runner exists; the
    fallback to the last webhook's sim time is already the design's answer for this, so no separate
    stub is needed beyond that.

  Done when:
    A hand-crafted signed webhook is acknowledged; a bad signature returns 401; a duplicate
    Idempotency-Key returns the same stored response and no second record; applying a lien over the
    proposed amount is rejected; the supertest suite passes.

  Evidence required:
    supertest output; one signed request/response transcript.

  Common drift to watch for:
    Reaching for an ORM instead of better-sqlite3 (stack substitution, AP-07); trusting wall time
    instead of SimTimeSource for lien expiry.
```

### Step C3 — Shared UI Kit & Stream

```
BUILD STEP C3: Shared UI Kit & Stream
  Reference:    DOC 3 → Web App Shell & Design System (shared/ui, useStream, format helpers)
  EXECUTOR:     Coding agent (Web dev)

  What to build:
    shared/ui components (Button, Badge variants — SeverityBadge, VerdictBadge, LadderBadge,
    StatusBadge — ConfidenceBar, Countdown, MaskedRef, DataTable, KeyValue, Timeline, Drawer,
    Panel, EmptyState, ErrorState); shared/stream/useStream.ts (SSE with polling fallback and the
    sim-time clock store); shared/lib/format.ts (INR money, sim-time, durations) and
    shared/lib/permissions.ts.

  Folder/file targets:
    /apps/web/src/shared/{ui,stream,lib}/

  Agent prompt hint:
    "Implement shared/ui and useStream per DOC 3. useStream falls back to 5 s polling after 20 s
    with no event or heartbeat and shows an amber connection dot. Badge variants never use colour
    as the only signal."

  YOUR JOB — ALONGSIDE:
    Import Track D Step D1's real token values as soon as they land (Sync 6) and swap the
    placeholder tokens.css; build against placeholder values until then.

  STUB/MOCK STRATEGY:
    Test useStream against a fake EventSource; point it at Track A Step A7's real /stream endpoint
    once it exists (Sync 4).

  Done when:
    Vitest passes for apiError mapping, the useStream fallback with a fake EventSource, permissions
    helpers, and format helpers; Badge variants render label + icon + colour; Countdown renders
    using the sim clock, never the browser clock.

  Evidence required:
    Vitest output; one DOM snapshot or screenshot of the Badge variants.

  Common drift to watch for:
    A component that calls fetch directly instead of going through the generated client and query
    hooks (layer violation, AP-06); premature memoisation.
```

### Step C4 — Alerts Inbox & Detail

```
BUILD STEP C4: Alerts Inbox & Detail
  Reference:    DOC 3 → Web App Shell (routes), M4 (alert shapes, LC-4), M5 (permissions), S3
                (outcome buttons)
  EXECUTOR:     Coding agent (Web dev)

  What to build:
    features/alerts: AlertsInbox (DataTable, filters, live stream updates), AlertDetail (evidence
    explain, ConfidenceBar, Countdown, action buttons gated by permissions), OutcomeButtons.tsx,
    ReviewQueue.tsx, FeedbackPanel.tsx (stub until A10 lands), NoveltyBanner.tsx (stub until B4/S4).

  Folder/file targets:
    /apps/web/src/features/alerts/

  Agent prompt hint:
    "Build the alerts inbox and detail per DOC 3 Web App Shell and M4/M5. Every action button
    checks usePrincipal().can(...) before rendering, but never relies on that alone — the API
    enforces regardless."

  YOUR JOB — ALONGSIDE:
    Check the action buttons against the M5 permission matrix role by role, with the Systems lead.

  STUB/MOCK STRATEGY:
    Build against a hand-written fixture matching AlertSummary/AlertDetail (LC-4) until Track A
    Step A7 lands (Sync 4); then swap only the data source, not the components.

  Done when:
    The inbox lists fixture alerts; opening detail shows evidence and a countdown on sim time; a
    bank_nodal fixture principal sees only notice-level fields; acknowledging updates optimistically
    then reconciles on the next stream event.

  Evidence required:
    Component test output; screenshots of the inbox and detail for two roles.

  Common drift to watch for:
    Business rules (who can request a hold) implemented in the component instead of read from
    permissions; polling instead of using useStream.
```

### Step C5 — Map Dashboard

```
BUILD STEP C5: Map Dashboard
  Reference:    DOC 3 → M3 (Risk Heatmap Dashboard, MapAdapter contract)
  EXECUTOR:     Coding agent (Web dev)

  What to build:
    features/map: MapPage, HotspotDrawer, FilterPanel, TimeSlider, Legend; MapAdapter.ts interface;
    maplibre/MapLibreAdapter.ts (the only file importing maplibre-gl); layers/{cellsLayer,
    locationsLayer, alertsLayer}.ts; useHeatmap.ts, useRegions.ts; a table-view fallback for a
    WebGL failure.

  Folder/file targets:
    /apps/web/src/features/map/

  Agent prompt hint:
    "Implement the map dashboard per DOC 3 M3. All maplibre-gl imports stay inside
    MapLibreAdapter.ts — every other file talks to the MapAdapter interface only, so a fallback
    renderer is a drop-in swap."

  YOUR JOB — ALONGSIDE:
    Confirm the bundled GeoJSON (Track D Step D5 / Track R Step R1) actually renders the four demo
    states before wiring live data.

  STUB/MOCK STRATEGY:
    Build against the hand-computed HeatmapResponse fixture shared from Track A Step A9's test
    suite until A9 lands (Sync 3); swap only the data source.

  Done when:
    MapPage renders the four states from bundled GeoJSON with no network request; filter changes
    debounce and refetch; forcing a WebGL failure falls back to the table view with the same data;
    moving the time slider pauses live updates and shows "return to live".

  Evidence required:
    Component test output; a screenshot with the table-view fallback triggered.

  Common drift to watch for:
    Importing maplibre-gl outside the adapter file (breaks the fallback contract); fetching map
    tiles from a CDN (violates the offline/no-CDN NFR in DOC 2 §2.7).
```

### Step C6 — Clusters & Cases UI

```
BUILD STEP C6: Clusters & Cases UI   (SHOULD tier — depends on Track A Step A12)
  Reference:    DOC 3 → S1 (Cluster Case Bundling)
  EXECUTOR:     Coding agent (Web dev)

  What to build:
    features/clusters/ClusterGraph.tsx (Cytoscape wrapper, capped at 200 nodes with a "+N more"
    node), features/cases/CasesPage.tsx and CaseDetail.tsx (renders brief_md, masked refs).

  Folder/file targets:
    /apps/web/src/features/{clusters,cases}/

  Agent prompt hint:
    "Implement the clusters and cases UI per DOC 3 S1. The Cytoscape wrapper is shared between both
    features — build it once in clusters and import it from cases, never duplicate it."

  YOUR JOB — ALONGSIDE:
    None — pure codegen, watch and verify.

  STUB/MOCK STRATEGY:
    Use a hand-written ClusterView/Case fixture until Track A Step A12 lands. A12 is SHOULD-tier and
    may be cut per §4.1c; if so, this step is cut with it, and the route degrades to an EmptyState
    rather than a dead link.

  Done when:
    ClusterGraph renders a fixture graph and caps at 200 nodes; CaseDetail shows the brief text
    ending with the required disclaimer line and no unmasked refs for a non-LEA fixture principal.

  Evidence required:
    Component test output; one screenshot of a capped graph.

  Common drift to watch for:
    Rendering the brief as raw Markdown with unescaped HTML (XSS risk); guilt-sounding placeholder
    copy creeping in — flag to Track D Step D3 immediately if seen.
```

### Step C7 — Evaluation, Ops, Outbox & Audit Pages

```
BUILD STEP C7: Evaluation, Ops, Outbox & Audit Pages
  Reference:    DOC 3 → Evaluation Harness (results shape), M4 (outbox), M5 (audit)
                DOC 2 → §2.7 (metrics)
  EXECUTOR:     Coding agent (Web dev)

  What to build:
    features/evaluation (results table and plots, ColdStartChart.tsx from S4, the before/after
    feedback plot from S3), features/ops (events/s, stage latencies p50/p95, outbox depth, delivery
    failures), features/outbox (delivery list with rendered_body), features/audit (AuditLog table,
    a "Verify chain" button and result banner).

  Folder/file targets:
    /apps/web/src/features/{evaluation,ops,outbox,audit}/

  Agent prompt hint:
    "Build these four read-heavy pages per DOC 3 and DOC 2 §2.7. Each is a table or plot over one
    existing endpoint — no new business logic, and never recompute a number the API already
    computes."

  YOUR JOB — ALONGSIDE:
    None — pure codegen, watch and verify.

  STUB/MOCK STRATEGY:
    Fixture JSON matching each endpoint's documented shape until Track B Step B7 (evaluation),
    Track A Step A11 (ops), Step A8 (outbox) and Step A4 (audit) land respectively; swap each
    endpoint's data source as it individually becomes ready, not all four at once.

  Done when:
    Each page renders its fixture data; "Verify chain" shows a clear ok/not-ok state with the first
    bad seq when not ok; the evaluation page can display a feedback-off and a feedback-on run side
    by side.

  Evidence required:
    Component test output; one screenshot of the audit page in the "verify failed" state (force it
    with a tampered fixture).

  Common drift to watch for:
    Computing p95 or hit-rate numbers in the browser instead of trusting the API's numbers
    (duplicated logic that will drift from the source of truth).
```

### Step C8 — Demo Console

```
BUILD STEP C8: Demo Console
  Reference:    DOC 3 → M1 (control API, LC-8)
                DOC 2 → §2.7 (public exposure)
  EXECUTOR:     Coding agent (Web dev)

  What to build:
    features/demo/DemoConsole.tsx: start/pause/resume/speed/reset/seed/inject-cluster controls
    wired to Track B Step B5's control API through the /sim-control proxy path; quick-login buttons
    from /auth/demo-users; a visible "DEMO MODE" banner when hosted-demo protections are active.

  Folder/file targets:
    /apps/web/src/features/demo/

  Agent prompt hint:
    "Build the demo console per DOC 3 M1/LC-8. It calls the control API only through the proxied
    /sim-control path — never a direct world-sim URL — since that is the only path enforcing
    demo_operator auth (DOC 2 §2.2)."

  YOUR JOB — ALONGSIDE:
    Rehearse the guided-demo script with the Systems lead once Track B Step B5 is live (Sync 7);
    note any control that is confusing under stage pressure.

  STUB/MOCK STRATEGY:
    Build the controls against a fake status object until Track B Step B5 lands (Sync 3); swap only
    the polling/stream source.

  Done when:
    The demo_operator role sees the console; any other role gets a 403 page (the route itself
    denies, it is not merely hidden); the inject-cluster control is verified, via a request log, to
    call the right endpoint through the proxy.

  Evidence required:
    Component test output; a request log showing the proxied call path.

  Common drift to watch for:
    Hardcoding demo credentials in the frontend bundle instead of reading them from
    /auth/demo-users (secret-leak risk, DOC 2 §2.8 T19).
```

### Step C9 — Hero-Flow E2E Test

```
BUILD STEP C9: Hero-Flow E2E Test
  Reference:    DOC 3 → Web App Shell (E2E plan), Bank Gateway Simulator (E2E note), and the
                hero-flow references throughout M3/M4/M5
  EXECUTOR:     Coding agent (Web dev), reviewed by the Systems lead
  REASON:       This is the single test that proves the whole system integrates end to end, so it
                is named as its own step rather than folded into C4.

  What to build:
    One Playwright test: quick-login as investigator → an alert appears live (via a real or
    scripted simulator tick) → open detail → request a hold → the bank console applies it → status
    returns to the alert → log in as bank_nodal and confirm scope (no other bank's identifiers
    visible).

  Folder/file targets:
    /apps/web/tests/e2e/hero-flow.spec.ts

  Agent prompt hint:
    "Write the hero-flow E2E test per DOC 3's E2E notes across M3/M4/M5/Bank Gateway Simulator. It
    must run against the real Compose stack (api + web + world-sim + bank-sim), not mocks — this is
    the integration proof, not a fast unit test."

  YOUR JOB — ALONGSIDE:
    Run it live on the VM once, not only in CI, before Checkpoints 4/5 — a CI-only green run has
    hidden a demo-day surprise before.

  Done when:
    The test passes against Compose end to end, and fails clearly (not a timeout) when any one
    service is stopped.

  Evidence required:
    A green Playwright run against Compose; a deliberately-broken run (one service stopped) showing
    a clear failure, not a hang.

  Common drift to watch for:
    Mocking any part of the stack "to make it faster" — that defeats the purpose of this specific
    test; every other test should be fast, this one should be real.
```

---

## Track D — Design, Content & Data Curation

```
TRACK D: design tokens, screen mockups, product and legal copy, evidence-pack and bank-console
         look, geo data curation, usability review, demo inputs and README
  OWNER:       Designer
  DEPENDS ON:  None to start D1-D3. D4 can start from DOC 3's spec directly but its certificate
               layout is only confirmed after Track R Step R3 lands (Sync 8). D5 depends on Track R
               Step R1's sourced material. D6 needs Track C's core screens running (after C4/C5).
               D7 is last, after Checkpoint 8.
  STEPS:       D1 → D7.
```

### Step D1 — Design Language & Tokens

```
BUILD STEP D1: Design Language & Tokens
  Reference:    DOC 3 → Web App Shell & Design System (token names are the contract)
                DOC 2 → §2.7 (accessibility: WCAG AA, colour never the only signal)
  EXECUTOR:     Human (Designer)

  What to build:
    The full token set under the exact names DOC 3 fixes: color.surface.{base,raised,sunken},
    text.{primary,secondary,inverse}, border.{subtle,strong}, brand.{primary,accent},
    severity.{low,medium,high,critical}, verdict.{good,warn,bad}, status.{open,ack,actioned,
    expired}, focus.ring; type.font.{sans,mono}, size scale 12/14/16/20/24/32, weight
    400/500/600; space 4-point scale; radius.{sm,md,lg}; shadow.{sm,md}; both light and dark
    theme values; written into tokens.css.

  Folder/file targets:
    /apps/web/src/shared/tokens/tokens.css (hands off into Track C Step C3)

  YOUR JOB — ALONGSIDE:
    Contrast-check every severity/verdict/status colour pair against its background at WCAG AA
    before handing off — DOC 2 §2.7 names this as a requirement, and it is design judgment, not
    something to leave to an agent.

  Done when:
    Every token name in DOC 3's Web App Shell contract exists with a light and dark value; every
    severity/verdict/status colour pair passes WCAG AA contrast against both theme backgrounds; no
    severity or status relies on colour alone once checked against Step C3's Badge variants.

  Evidence required:
    The tokens.css file; a contrast-check table for every colour pair.

  Common drift to watch for:
    Renaming a token to something that "reads better" — the names are the contract Step C3 codes
    against, and a silent rename breaks the handoff instead of erroring loudly.
```

### Step D2 — Core Screens in Figma

```
BUILD STEP D2: Core Screens in Figma
  Reference:    DOC 1 → §1.3 (user flow overview)
                DOC 3 → Web App Shell (routes list), M4/M5/M3 (alert detail, map, login)
  EXECUTOR:     Human (Designer)

  What to build:
    Figma mockups for login, alerts inbox, alert detail (evidence/explain plus action buttons), map
    dashboard, and case detail, covering DOC 1 §1.3's primary user flow end to end, in both light
    and dark theme, using Step D1's tokens.

  Folder/file targets:
    External (Figma); link recorded at docs/design/figma-link.md

  YOUR JOB — ALONGSIDE:
    Walk the Systems lead through the flow once before Track C Steps C4/C5 start building, so
    layout assumptions (where the countdown sits, what the drawer contains) are shared before code,
    not discovered after.

  Done when:
    All five screens exist for both themes; DOC 1 §1.3's primary flow is walkable in Figma end to
    end with no dead-end screen.

  Evidence required:
    The Figma link; a short walkthrough (recorded or live) with the Systems lead.

  Common drift to watch for:
    Designing screens DOC 3 does not list as routes (scope creep) instead of sticking to the fixed
    route list.
```

### Step D3 — Copy Pack

```
BUILD STEP D3: Copy Pack
  Reference:    DOC 1 → §1.5 (legal framing and ethics: no guilt-asserting language, "not legal
                advice")
                DOC 3 → S1 (case-brief disclaimer), S2 (DRAFT label), S5 (bilingual templates), M4
                (alert wording), M3 (heatmap legend note)
  EXECUTOR:     Human (Designer)

  What to build:
    All user-facing product copy: empty states, error messages, the English alert/SMS/email
    templates' actual wording (S5's Jinja files get real text, not placeholders), the case-brief
    disclaimer line, the evidence-pack DRAFT label and certificate section headings, login/
    onboarding copy, and the map legend's "decayed persistence estimate" note per DOC 3 M3.

  Folder/file targets:
    docs/design/copy-pack.md, feeding into /apps/api/src/nakabandi/alerting/templates/en/*.j2 and
    UI strings across apps/web

  YOUR JOB — ALONGSIDE:
    Re-check every alert/case/evidence string against DOC 1's ethics list (no guilt assertion, no
    naming real persons, "not legal advice" framing) before handoff — this is a compliance-adjacent
    check, not a style preference.

  Done when:
    Every string DOC 3 requires (S1's disclaimer, S2's DRAFT label, M3's legend note, M4's template
    wording) has final copy; none of it asserts guilt or claims legal compliance.

  Evidence required:
    The copy-pack doc; a line-by-line note confirming the three required disclaimer strings are
    present verbatim.

  Common drift to watch for:
    Copy that reads as an accusation ("suspect" instead of "flagged account") — catch and fix it
    here, not after a judge notices it on stage.
```

### Step D4 — Evidence Pack & Bank Console Look

```
BUILD STEP D4: Evidence Pack & Bank Console Look   (SHOULD tier — feeds Track A Step A12)
  Reference:    DOC 3 → S2 (Section63Draft, PDF sections), Bank Gateway Simulator (console pages)
                Track R output → docs/reference/bsa_s63_schedule.md (R3)
  EXECUTOR:     Human (Designer)

  What to build:
    A print-ready layout for the evidence-pack PDF (summary, forecast/evidence statements,
    interception/proportionality, timeline, audit excerpt, hash report, certificate draft) matching
    R3's transcription of the official Schedule form once available; a simple, credible look for
    the bank console (request list, request detail, apply/reject).

  Folder/file targets:
    docs/design/evidence-pack-layout.md, docs/design/bank-console-look.md — feed Step A12's
    ReportLab template and Step C2's EJS views

  YOUR JOB — ALONGSIDE:
    Check the certificate section order and required fields against R3's transcription line by
    line before signing off — this is the check DOC 3 S2 itself calls for.

  STUB/MOCK STRATEGY:
    Draft the layout against DOC 3's own section list before R3 lands; revise once R3's Schedule-
    form text arrives (Sync 8) rather than blocking.

  Done when:
    The evidence-pack layout has every DOC 3 S2 section in a sensible order and is checked against
    R3's transcription; the bank console look covers list, detail and the apply/reject actions.

  Evidence required:
    The two layout docs; the line-by-line check note against R3.

  Common drift to watch for:
    Designing the certificate to look "officially signed" — per DOC 3 S2 it must visibly read as an
    unsigned DRAFT.
```

### Step D5 — Geo Data Curation & Attribution

```
BUILD STEP D5: Geo Data Curation & Attribution
  Reference:    DOC 2 → §2.2 (bundled GeoJSON decision), §2.8 T3/T4/T18 (licence and coverage risks)
                DOC 3 → M3 (geo module, bundled GeoJSON loader)
                Track R output → docs/research/geo-sources.md (R1)
  EXECUTOR:     Human (Designer), consuming Track R Step R1's output

  What to build:
    Curated district-boundary GeoJSON for the four approved demo states (Maharashtra, Uttar
    Pradesh, Haryana, Jharkhand) and a synthetic-or-OSM-derived ATM/branch point extract, trimmed
    and simplified for bundle size; data/geo/README.md recording every source, licence, and
    coverage gap (T4); a `source` field on every location record per DOC 2 §2.8.

  Folder/file targets:
    /data/geo/*.geojson, /data/geo/README.md — consumed by Track C Step C5 and Track B Step B8

  YOUR JOB — ALONGSIDE:
    This step IS the human work — curating, trimming, and writing honest licence notes for a
    public repo is a judgment task (T18's licence-breach risk) that should not be delegated
    unsupervised.

  STUB/MOCK STRATEGY:
    If Track R Step R1's sourced boundaries are late, use a coarse public-domain state-outline
    placeholder so Step C5 is not blocked, and swap once the curated files land.

  Done when:
    GeoJSON for all four states loads in Step C5's MapPage; data/geo/README.md names a source and
    licence for every file; every location has a `source` field; total bundle size is checked
    against the offline/bundled NFR in DOC 2 §2.7.

  Evidence required:
    The README; a file-size listing; a screenshot of the four states rendering.

  Common drift to watch for:
    Bundling a boundary or point dataset with an unclear or non-redistributable licence (T18) —
    when in doubt, leave it out and note the gap honestly rather than guessing.
```

### Step D6 — Usability Walkthroughs

```
BUILD STEP D6: Usability Walkthroughs
  Reference:    DOC 1 → §1.2 (acceptance criteria for MUST features)
                DOC 2 → §2.7 (accessibility: WCAG AA, keyboard operability)
  EXECUTOR:     Human (Designer)

  What to build:
    A usability pass once Track C's core screens (Steps C4, C5) are live against real or fixture
    data: walk the login → alert → map → hold flow as each role, check keyboard reachability and
    reduced-motion behaviour, and file concrete UI issues back to the Web dev.

  Folder/file targets:
    docs/design/usability-notes.md

  YOUR JOB — ALONGSIDE:
    This step IS the human work — a fresh pair of eyes on the running app catches what the builder
    has stopped seeing.

  Done when:
    The primary flow has been walked as at least two roles; every action DOC 2 §2.7 requires to be
    keyboard-reachable has been tried by keyboard only; issues are filed with enough detail (screen,
    role, expected vs. actual) for the Web dev to act without a follow-up question.

  Evidence required:
    The usability-notes doc; an issue list with severities.

  Common drift to watch for:
    Filing vague issues ("map feels off") instead of specific, actionable ones — vague notes will
    not get acted on.
```

### Step D7 — Demo Inputs, README & Architecture Figure

```
BUILD STEP D7: Demo Inputs, README & Architecture Figure
  Reference:    DOC 4 → §4.4 (deployment checklist), and this whole document as the README's source
  EXECUTOR:     Human (Designer), with a coding agent for the architecture figure only

  What to build:
    The top-level README (what this is, how to run it locally and offline, the three deployment
    paths from DOC 2 §2.8, screenshots); a one-page architecture figure redrawing DOC 2 §2.1's
    layer diagram cleanly; the exact guided-demo inputs (seed value, which demo users to log in as,
    in what order) written down so nobody has to remember it live.

  Folder/file targets:
    /README.md, /docs/architecture-figure.(svg|png), /docs/demo-script.md

  Agent prompt hint:
    "Redraw the DOC 2 §2.1 layer diagram as a clean SVG or PNG figure — same boxes and arrows, no
    new content." (for the architecture figure only; the README and demo script are the Designer's
    own writing.)

  YOUR JOB — ALONGSIDE:
    Write the demo script and README copy yourself — this is the last thing judges and future-you
    will read, and it should read like it, not like agent output.

  Done when:
    The README lets someone with none of this context clone, run offline, and run hosted; the
    architecture figure matches DOC 2 §2.1 exactly; the demo script names the exact seed, users and
    order used in the actual rehearsed run.

  Evidence required:
    The README; the figure file; the demo script; one clean run following the README from scratch
    (ideally by someone who was not in the room).

  Common drift to watch for:
    A README that describes the aspirational plan instead of what actually ships — write it last,
    after Checkpoint 8, and correct anything that drifted from the original plan.
```

---

## Track R — Research Agent Tasks

```
TRACK R: open-web research and verification handed to a research/web agent, pasted in and
         retrieved by the Designer
  OWNER:       Research agent, operated by the Designer
  DEPENDS ON:  None — can start immediately, in parallel with everything else.
  STEPS:       R1 → R4, no fixed internal order; run in parallel.
  AD-HOC RESEARCH: when any step of any track needs heavy research beyond these four (several sources, or
               facts a decision, licence or public claim rests on), the coding agent hands it off: it writes a
               Research Handoff prompt (AGENTS.md), a human pastes it into the research agent, and the output
               lands in docs/research/<topic>.md. Quick lookups and debugging searches stay with the coding agent.
```

### Step R1 — Geo Sources & Licences

```
BUILD STEP R1: Geo Sources & Licences
  Reference:    DOC 2 → §2.8 T3/T4/T18
                DOC 3 → M3 (bundled GeoJSON)
  EXECUTOR:     Research agent
  REASON:       Finding and checking licence terms across several boundary/POI datasets is
                open-web lookup work, better suited to a research agent than burning coding-agent
                context on it.

  RESEARCH AGENT PROMPT:
    "Find publicly redistributable district-boundary GeoJSON or shapefile sources for
    Maharashtra, Uttar Pradesh, Haryana and Jharkhand, India, and a source of bank ATM/branch
    point locations for those four states (an OpenStreetMap Overpass extract or another
    redistributable source). For each source, report: exact download URL, licence (name and key
    terms — especially attribution and redistribution requirements), last-updated date, and any
    known coverage gaps. Flag anything with an unclear or non-commercial-only licence."

  OUTPUT LANDS AT:    docs/research/geo-sources.md
  CONSUMED BY:        Track D Step D5 (geo data curation)
```

### Step R2 — Public Anchors

```
BUILD STEP R2: Public Anchors
  Reference:    DOC 2 → Appendix A (simulator priors)
                DOC 1 → §1.1 (verified-figures block)
  EXECUTOR:     Research agent
  REASON:       Corroborating or extending the public anchor figures already in DOC 1/DOC 2 with
                fresher or additional official sources is open-source lookup work.

  RESEARCH AGENT PROMPT:
    "Find current official Indian government sources (PIB releases, MHA Lok Sabha/Rajya Sabha
    parliamentary replies, RBI publications) on: (1) the most recent state-wise cybercrime
    complaint distribution, (2) any published figures on ATM cash-withdrawal caps or daily
    transaction limits by major Indian banks, (3) any public reporting naming approximate numbers
    of mule/suspect ATM IDs associated with a single fraud ring or cluster. For each figure, give
    the exact number, the source name, URL, and the date of the figure. Do not use unofficial
    aggregator sites — prefer PIB, MHA, RBI, or a bank's own published policy page."

  OUTPUT LANDS AT:    docs/research/public-anchors.md
  CONSUMED BY:        Track B Step B8 (simulator v1 realism, compare_to_public); corroborates and
                       extends (never replaces) the priors already fixed in DOC 2 Appendix A
```

### Step R3 — Evidence Law Schedule Text

```
BUILD STEP R3: Evidence Law Schedule Text
  Reference:    DOC 1 → §1.5 (legal framing, BSA 2023 s.63)
                DOC 3 → S2 (Section63Draft, Schedule form layout)
  EXECUTOR:     Research agent
  REASON:       Transcribing an official statutory schedule form accurately is a lookup-and-verify
                task, not a coding task, and gates Step D4's certificate layout.

  RESEARCH AGENT PROMPT:
    "Find the official text of the Bharatiya Sakshya Adhiniyam 2023, Section 63, and its
    accompanying Schedule (the certificate form for electronic evidence), from an official Indian
    government legal source (India Code, e-Gazette, or a Ministry of Law and Justice publication —
    not a law-firm blog). Transcribe the Schedule's required fields and structure exactly (Part A /
    Part B, signatory roles, required statements about the device/record and hash values). Note
    the source URL and publication date."

  OUTPUT LANDS AT:    docs/reference/bsa_s63_schedule.md
  CONSUMED BY:        Track A Step A12 (Section63Draft), Track D Step D4 (evidence-pack layout
                       check)
```

### Step R4 — Hosting Options

```
BUILD STEP R4: Hosting Options
  Reference:    DOC 2 → §2.2 (Deployment decision: VM + Caddy, PaaS fallback), §2.8 T14/T17
  EXECUTOR:     Research agent
  REASON:       Comparing current VM/PaaS pricing and constraints (free-tier disk persistence,
                SQLite compatibility) is a fast-moving web-lookup task, cheaper to do once here than
                for each teammate to re-check individually.

  RESEARCH AGENT PROMPT:
    "For hosting a small Dockerized web app (FastAPI + SQLite + a Node service) that needs a
    persistent local disk (SQLite needs a real writable volume, not ephemeral storage) reachable
    over public HTTPS: compare current options for (1) a cheap small VM (2 vCPU/4 GB) with
    providers and approximate monthly cost, and (2) PaaS fallbacks (Railway, Render, Fly.io) —
    specifically whether their free or cheapest paid tier gives a persistent volume, whether the
    app can sleep/wake without losing SQLite data, and rough setup steps for a Docker Compose-style
    deployment. Give current pricing and note any recent platform changes."

  OUTPUT LANDS AT:    docs/research/hosting-options.md
  CONSUMED BY:        Track A Step A5 (skeleton deployment) — the Systems lead's VM/DNS
                       provisioning decision
```

---

## §4.1a — Sync Points

```
SYNC 1: After Track A Step A2 → before any track builds against generated contracts (Track B's
        schema validation in B1 and Steps B2-B4; Track C Step C1's typed API client). B1 and C1 themselves
        start earlier, on the golden generator and the placeholder client.
  What must be confirmed: the generated JSON Schemas under packages/contracts/schemas validate a
    hand-written sample payload for every LC-1 shape.
  Who confirms it: Systems lead sends the schema folder link; each track owner checks their own
    consuming step against it.

SYNC 2: After Track B Step B1 (golden generator) and Track A Step A3 (intake) → before Track B
        Steps B8/B9 rely on live ingest
  What must be confirmed: B1's golden JSONL stream posts to A3's /ingest endpoints and is accepted
    with the expected counts.
  Who confirms it: Algo dev and Systems lead, together.

SYNC 3: After Track B Steps B2, B3, B4 (graph, interception, forecast v0) → before Track A Step A6
        replaces pipeline stubs with real facades, and before Track C Steps C5/C8 swap their
        fixtures for live data
  What must be confirmed: each facade's output matches the LC-4 shapes the stubs promised; the
    golden pipeline test in A6 passes with real facades swapped in one at a time.
  Who confirms it: Systems lead, reviewing with the Algo dev.

SYNC 4: After Track A Step A7 (alerting core) → before Track C Steps C3 (stream endpoint), C4, and
        C7 swap their fixtures for the real API
  What must be confirmed: GET /alerts, /alerts/{id}, GET /stream exist and match LC-4/LC-5 shapes;
    `npm run types` regenerates with no unexpected diff.
  Who confirms it: Systems lead notifies the Web dev; Web dev confirms the type regeneration.

SYNC 5: After Track A Step A8 (alerting delivery/actions) and Track C Step C2 (bank simulator) →
        before either side is considered done for the hero flow
  What must be confirmed: a real request_hold from the API produces a webhook the bank simulator
    accepts, and a console Apply produces a callback the API accepts — run together, not separately.
  Who confirms it: Systems lead and Web dev, run jointly.

SYNC 6: After Track D Step D1 (tokens) → before Track C Step C3 (and everything downstream of it)
        is styled for real
  What must be confirmed: tokens.css contains every token name the Web App Shell contract lists,
    for both themes, and compiles with no missing-variable error.
  Who confirms it: Web dev.

SYNC 7: After Track B Step B5 (live runner) → before Track C Step C8 (demo console) is rehearsed
        for real
  What must be confirmed: the control API's start/pause/resume/speed/inject-cluster endpoints
    behave as LC-8 specifies against a running deployment, not just in unit tests.
  Who confirms it: Algo dev and Web dev, run together against the skeleton deployment (A5).

SYNC 8: After Track R Step R3 (evidence law schedule text) → before Track D Step D4's certificate
        layout is finalised, and before Track A Step A12 labels its Section63Draft fields
  What must be confirmed: R3's transcription is checked line by line against the layout and the
    Section63Draft field list.
  Who confirms it: Designer, with the Systems lead reviewing the field list against A12.
```

---

## §4.1b — Ownership & Merge Strategy

```
OWNERSHIP MAP:
  Track A  owns: /apps/api/src/nakabandi/{shared,intake,access,audit,alerting,analytics,casework,
                 evaluation,pipeline}/, /apps/api/src/nakabandi/{geo/application,geo/infrastructure,
                 geo/interfaces}/, /apps/api/src/nakabandi/main.py, /packages/contracts/, /config/,
                 /infra/, /scripts/ (except sweep), /.github/
  Track B  owns: /apps/api/src/nakabandi/{graph,forecast,interception}/,
                 /apps/api/src/nakabandi/geo/domain/, /apps/world-sim/, /scripts/sweep, /docs/results/
  Track C  owns: /apps/web/ (except shared/tokens/), /apps/bank-sim/
  Track D  owns: /apps/web/src/shared/tokens/, /data/geo/, /docs/design/, /docs/reference/,
                 /README.md, /docs/architecture-figure.*, /docs/demo-script.md

  Integration Owner (Systems lead) also owns: /AGENTS.md, /DOC1.md … /DOC4.md, /vibe-antipatterns.md,
                 /prompt-patterns.md. Nobody else edits them; spec change requests go to the Integration
                 Owner (locked contracts: Contract Change Process below).
  STATE FILES:   each track writes only its own /docs/state/track-{a,b,c,d,r}.md (Track R's is written by
                 the Designer). No other file is shared for status, so status never causes a merge conflict.
  RESEARCH:      anyone may add a NEW file under /docs/research/ (one per research task) and never edits
                 another task's file.

  SHARED (coordinate before touching — see the Contract Change Process below):
    /packages/contracts/           Track A generates it, but the LC-1..LC-10 shapes affect every
                                    track that builds against them.
    /apps/api/src/nakabandi/geo/   split between Track A (application/infrastructure/interfaces)
                                    and Track B (domain) — coordinate at the Sync points above.
    /config/policy.yaml, /config/sim.default.yaml   Track A creates the skeleton; Track B fills
                                    sim.default.yaml values, Track A fills policy.yaml values — no
                                    double-writing the same key.
    /apps/web/src/shared/tokens/tokens.css   Track D supplies the values; Track C (Step C3) is the
                                    only consumer that codes against the names.

CONTRACT CHANGE PROCESS: any change to a locked contract shape (DOC 3 LC-1 to LC-10) is raised with
  the Integration Owner and confirmed with every track whose stub or fixture depends on that shape
  before the change lands. A silent shape change breaks every stub built against the old shape at
  once, which is a worse failure than the short coordination delay.

INTEGRATION OWNER: Systems lead — responsible for performing the merges below, keeping main green,
  and resolving conflicts on the shared surfaces above.

BRANCHING: One branch per track — feat/track-a, feat/track-b, feat/track-c, feat/track-d. Commit
  messages and PR titles reference the track and step, e.g. feat(track-b): step 4 — forecast v0.

ISOLATION: Track A and Track B's coding-agent sessions will often run concurrently against the same
  apps/api tree; give each its own git worktree, not just a branch, from the start. Track C and Track D
  are naturally isolated (a separate app, and non-code artifacts) and can share a working directory.

MERGE POINTS:
  MP1 — after Track A Step A2: merge contracts into every track's branch (this IS Sync 1).
  MP2 — after Track A Step A3 and Track B Step B1: merge onto a shared integration branch before
        Track B Steps B8/B9 (Sync 2).
  MP3 — after Track A Step A6 and Track B Steps B2-B4: merge Track B's real facades into Track A's
        pipeline branch, one facade at a time (Sync 3).
  MP4 — after Track A Step A7, before Track C Step C4: merge alerting core so the Web dev branch can
        drop its alert fixture (Sync 4).
  MP5 — after Track A Step A8 and Track C Step C2: merge both branches and run the joint webhook/
        callback check (Sync 5).
  MP6 — before Checkpoint 8: full merge of all four tracks onto main, tagged as the freeze
        candidate.

DEFINITION OF DONE (per merge point): `npm run ci` is green; existing tests pass, including the
  golden test (A6) and the hero-flow test (C9) once it exists; no edits outside the pushing track's
  Ownership Map without a Shared Surfaces note in the PR description.
```

---

## §4.1c — Descope Order

```
IF the pipeline has not produced a live, end-to-end alert (the condition behind Checkpoints 3 and
   4, §4.3) by the time Track A and Track B's steps up through A9/B5 would otherwise be complete
  :
  THEN cut, in this order:
    1. Track B v1 upgrades not yet started — Step B6 (Forecast v1) and Step B8 (Simulator v1
       Realism) stay on v0/golden-only; Step B9 (sweeps) drops with them, since a sweep over an
       untrained scorer and an unrealistic simulator has nothing meaningful to report.
    2. SHOULD-tier features that depend on the alerting/graph core being stable: Step A10 (S3
       feedback loop), feature S4's cold-start banner (folds into Steps B4/B8), feature S5 (bilingual
       templates; Step A8's templates stay English-only).
    3. Step A12 (S1/S2 — case bundling and evidence pack) in full, taking Track C Step C6 and
       Track D Step D4 with it — the route degrades to an EmptyState, not a broken link.
  Never cut: the M1-M6 MUST features (Steps A1-A9, B1-B5, C1-C5, C7's evaluation/ops/outbox/audit
    minimum viable versions, C9 hero-flow test), the human-approval gate on every external action
    (DOC 2 §2.1 invariant 7), or the amount-limited-lien invariant (DOC 3 M6).

IF Checkpoint 8 (hosted, unattended guided demo, §4.3) cannot be passed on the hosted VM once the
   MUST steps are otherwise complete:
  THEN fall back, in this order:
    1. The PaaS fallback hosting path from DOC 2 §2.2, accepting its persistence/sleep trade-offs,
       instead of continuing to chase the VM.
    2. The offline laptop backup as the demo path instead of a public link — the same Compose file
       per DOC 2 §2.2, always available, and the true fallback of last resort.
  Never cut: the public repository (KAYA-required, DOC 1 §1.0); a demo path that actually runs
    end to end, even if it is the laptop.
```

---

## §4.2 — Agentic Coding Rules

```
ALWAYS:
  [ ] Record progress only in your own track's state file (docs/state/track-x.md), after every step.
  [ ] Keep dependencies pointing inward — interfaces → application → domain — in every API module;
      domain code stays pure Python/numpy with no I/O, no FastAPI, no SQLAlchemy, no wall clock.
  [ ] Import another module only through its `__init__.py` facade — never reach into
      `other_module.domain` or `other_module.infrastructure` directly.
  [ ] Give every forecasting read a required `as_of` parameter; never default it.
  [ ] Read time only through the injected Clock (SystemClock/SimClock) — never `datetime.now()` or
      `time.time()` outside those two implementations.
  [ ] Put every threshold, weight, cap and policy value in config/policy.yaml or
      config/sim.default.yaml — never a magic number in code.
  [ ] Require an authenticated Principal for any use case that has an effect on a third party
      (RecordAction, MarkOutcome, anything that sends a webhook or SMS/email).
  [ ] Regenerate apps/web's schema.d.ts with `npm run types` after any API shape change, and commit
      the result — never hand-edit the generated client.

NEVER:
  [ ] Never do heavy research yourself (several sources, or facts a decision, licence or public claim rests
      on). Stop, write a Research Handoff prompt (AGENTS.md), give it to the human, and wait for the output in
      docs/research/. Quick lookups and debugging searches are fine.
  [ ] Never edit AGENTS.md, DOC1–DOC4 or another track's state file unless you are the Integration Owner
      (or, for a state file, its owner); raise the change with the Integration Owner instead.
  [ ] Never let `pipeline` be bypassed — `pipeline` and `main.py` are the only places allowed to
      call several module facades in sequence; no other module imports `pipeline`.
  [ ] Never let anything but `evaluation` import the oracle client, and never let `main.py` import
      `evaluation` — the hidden-truth firewall (DOC 2 §2.1) has no exceptions.
  [ ] Never construct a LienProposal with `proposed > disputed`, without an expiry, or without a
      complaint anchor — there is no whole-account-freeze value in the domain at all.
  [ ] Never add an enum member, event field, or endpoint shape beyond what DOC 3's Locked Contracts
      (LC-1 to LC-10) define, even if it looks obviously useful — raise it through the Contract
      Change Process (§4.1b) instead.
  [ ] Never let a web feature import from another feature — only from `shared/*` (eslint-plugin-
      boundaries enforces this; do not work around it).
  [ ] Never write a case brief, evidence-pack certificate, or alert copy that asserts guilt, names a
      real person, or claims legal compliance — DOC 1 §1.5's ethics section is not optional wording
      guidance.

IF THE AGENT GOES OFF-TRACK:
  If the agent starts building a feature not named in the current build step's "What to build" (for
  example, adding UI polish during a backend-only step, or wiring a real endpoint during a stub-
  strategy step), say: "Stop. We are only doing [current step name]. Finish the 'Done when'
  condition for this step before anything else." If the agent reaches into another module's
  `domain/` or `infrastructure/` "to save a round trip," point it at the facade it should be calling
  instead and ask it to undo the direct import. If import-linter or eslint-boundaries fails in CI,
  treat that as a stop-and-fix signal before continuing to the next step, not something to silence.
```

---

## §4.3 — Integration Checkpoints

```
CHECKPOINT 1: After Track A Steps A1-A2 and Track B Step B1 have started
  What to verify:   The monorepo boots, CI is green, and the golden simulator stream exists as a
                     file (even before ingest).
  How to test it:   `npm run ci` on main; run the golden generator and inspect the JSONL output by
                     eye against LC-1.
  If it breaks:     Check the schema/contracts diff first — most early breakage here is a shape
                     mismatch between what B1 emits and what A2 defines.

CHECKPOINT 2: After Track A Step A5 (skeleton deployment)
  What to verify:   A public HTTPS URL is reachable and the same Compose file runs offline.
  How to test it:   curl the public health endpoint; unplug the network and run
                     `docker compose up` on a laptop.
  If it breaks:     Check Caddy's config and DNS first (public path), then check for an accidental
                     network dependency baked into an image (offline path).

CHECKPOINT 3: After Track A Steps A3, A6, A7 and Track B Steps B2-B4 are merged (Sync 3)
  What to verify:   A complaint posted through /ingest produces a real alert (not a stub) end to
                     end, visible via GET /alerts.
  How to test it:   POST the golden fixture, then GET /alerts and confirm at least one alert with a
                     forecast attached.
  If it breaks:     Check the pipeline's stage-by-stage `unprocessed` marker first — it names which
                     facade failed.

CHECKPOINT 4: After Checkpoint 3, with Track C Steps C3-C4 also merged (Sync 4) — "first live alert"
  What to verify:   The alert from Checkpoint 3 is visible live in the web app inbox via SSE, not
                     just via curl.
  How to test it:   Open the alerts inbox in a browser while posting a new complaint; the alert
                     should appear without a manual refresh.
  If it breaks:     Check the SSE connection dot first (amber means it has already fallen back to
                     polling); then check that `npm run types` was regenerated after A7 landed.

CHECKPOINT 5: After Track A Step A8 and Track C Step C2 (Sync 5)
  What to verify:   A hold request made from the alert detail page produces a webhook the bank
                     simulator accepts and shows on its console.
  How to test it:   Click "Request Hold" as an investigator; check the bank console for the pending
                     request; apply it there and confirm the alert's status updates back.
  If it breaks:     Check signature verification first (clock skew and secret mismatch are the two
                     most common causes), then check the outbox view for a dead-lettered delivery.

CHECKPOINT 6: After Track A Step A9 and Track C Step C5 (map fixture swapped to live)
  What to verify:   The heatmap dashboard reflects live alert data, not the fixture.
  How to test it:   Post a new complaint in a region, confirm the corresponding cell's intensity
                     changes on the map without a page reload.
  If it breaks:     Check the heat.version SSE event first, then the rollup projector's event
                     subscription.

CHECKPOINT 7: After Track A Step A11 and a first stress run
  What to verify:   The system survives the 50 complaints/s for 60 s load with no lost complaints
                     and no duplicate alerts, and recovers cleanly from a kill -9.
  How to test it:   Run /scripts/stress against the hosted VM; watch /system/metrics; kill and
                     restart the api container mid-run.
  If it breaks:     Check for an unindexed hot-path query first (p95 creep), then check that
                     `unprocessed` complaints actually get retried after restart.

CHECKPOINT 8: Hosted, unattended guided demo (the descope trigger in §4.1c)
  What to verify:   The full hero flow (Track C Step C9) runs unattended on the hosted VM, including
                     demo-mode protections (auto-pause, rate limits) not interfering with a real
                     guided run.
  How to test it:   Run the guided-demo script (Track D Step D7) against the hosted URL from a
                     machine that was not used to build it.
  If it breaks:     Re-run the hero-flow E2E test (C9) against the hosted URL directly — if it
                     passes there but the manual walkthrough fails, the gap is almost always in the
                     demo-script's assumed starting state (stale seed, wrong demo user).
```

---

## §4.4 — Deployment Checklist

```
[ ] Environment variables set on the VM (not baked into images) — list: DATABASE_URL (or SQLite
    path), JWT_SECRET, WEBHOOK_SECRET, API_SERVICE_KEY, SMTP_* (optional), SMS_PROVIDER_* (optional,
    falls back to Outbox), CADDY_DOMAIN
[ ] `.env.example` in the repo has every variable name with no real values (gitleaks-clean)
[ ] Database created and migrated (SQLAlchemy create_all, or Alembic if introduced later); the
    seeded demo dataset loaded via `npm run seed` — never a manual INSERT
[ ] `npm run ci` passes on the commit being deployed: ruff, pyright, pytest, import-linter, eslint
    (with boundaries), `npm run types` produces no diff, Playwright hero-flow test green
[ ] `docker compose build` and `docker compose up` succeed from a clean checkout, both online and
    with the network disabled (offline-backup path)
[ ] Caddy serves one HTTPS origin covering /, /api, /bank and the gated /sim-control path; DNS
    points at the VM
[ ] Hosted-demo protections active: login/control rate limits, 25-stream SSE cap, simulator speed
    cap, 15-minute auto-pause, nightly reset job scheduled
[ ] External uptime check configured against the public health endpoint
[ ] Smoke test: quick-login as investigator on the public URL, confirm the hero flow (Track C Step
    C9) end to end, then log out
[ ] The offline laptop backup has been run once from the README (Track D Step D7) by someone who
    was not building it
```
