# DOC 3 — NAKABANDI: Module & Coding Architecture

*Status: Confirmed. Builds on DOC 1 (features) and DOC 2 (architecture). Each entry below follows DOC 2's module boundaries. Locked Shared Contracts at the end are frozen; changing one follows the Contract Change Process there.*

**Reading guide.** Python signatures use type hints; web and bank-simulator shapes use TypeScript. "Facade" means the module's `__init__.py`, the only thing other modules may import. "DSA seam" marks pure code suited to plain functions plus pytest. Default numeric values are **starting values held in `config/policy.yaml` or `config/sim.default.yaml`**, tunable, never hard-coded.

## Table of Contents
- Shared Kernel
- M1 — Scenario Simulator & Synthetic Data Engine
- Evaluation Harness
- M2 — Predictive Engine
- M6 — Interceptability Planner & Intervention Ladder
- M4 — Alert & Notification System
- Bank Gateway Simulator
- M5 — Law Enforcement Interface (API side)
- Web App Shell & Design System
- M3 — Risk Heatmap Dashboard
- S1 — Cluster Case Bundling
- S2 — Evidence Pack & Audit Chain
- S3 — Officer Feedback Loop
- S4 — Cold-Start Drill
- S5 — Bilingual Alert Templates
- Locked Shared Contracts

---

## Shared Kernel

```
FEATURE: Shared Kernel (contracts package + nakabandi.shared)

MODULE STRUCTURE:
  packages/contracts/src/nakabandi_contracts/
    ├── enums.py       Resolution, Channel, LocationKind, Role, AlertStatus, LadderLevel,
    │                  Verdict, ActionType, ComplaintCategory. Enums only, no logic.
    ├── ingest.py      Pydantic v2 models: RegistryUpdate, ComplaintBatch,
    │                  CashOutObservationBatch, Tick. The canonical ingestion contract.
    ├── schemas/       generated JSON Schema files (committed build artifacts)
    └── tests/         schema round-trip and example-payload validation
  apps/api/src/nakabandi/shared/
    ├── types.py       SimTime, Paise, Id aliases; helpers to_sim_time(), paise_from_inr()
    ├── ids.py         new_id() -> ULID string
    ├── clock.py       Clock protocol; SystemClock; SimClock
    ├── scheduler.py   Scheduler: in-memory timers driven by a Clock
    ├── uow.py         UnitOfWork protocol (SQLAlchemy implementation lives in
    │                  shared/infrastructure/uow.py)
    ├── events.py      DomainEvent base; EventBus; event payload classes
    ├── errors.py      DomainError hierarchy; error code registry
    ├── messages.py    user-facing text per error code (separate from developer detail)
    ├── config.py      Settings (pydantic-settings, env only)
    ├── policy.py      Policy: typed model of config/policy.yaml
    └── logging.py     structlog setup; scrub processor; request-id context

SHARED SURFACES:
  Everything. This is the only code every track imports. Edits follow the Contract Change
  Process. Additions (new enum member, new event) are announced; removals and renames are not
  allowed.

FUNCTION & CLASS DESIGN:
  new_id() -> str                         ULID; sortable; no arguments, no state.
  class Clock(Protocol): now() -> SimTime
  class SimClock(Clock):
      advance_to(t: SimTime) -> None      monotonic; an earlier t is ignored and logged.
      Owns: current sim time. Hides: nothing else.
  class SystemClock(Clock)                wall time in UTC; the only place time.time() may appear.
  class Scheduler:
      call_at(key: str, at: SimTime, fn: Callable[[], None]) -> None   replaces any timer with
                                                                       the same key
      cancel(key: str) -> None
      run_due(now: SimTime) -> int        fires due timers in time order; returns count fired.
      Timers are IN MEMORY. Owners (alerting) rebuild theirs from database rows at boot.
  class EventBus:
      subscribe(event_type: type[E], handler: Callable[[E], None]) -> None
      publish(event: DomainEvent) -> None  synchronous, in registration order; a handler
                                           exception is logged and re-raised as HandlerError
                                           after all handlers ran.
  Policy.load(path) -> Policy             validates every key; unknown or missing key aborts boot.
  SRP check: Clock knows time only; Scheduler knows timers only; EventBus knows routing only.

INTERFACES & CONTRACTS:
  SimTime = datetime (timezone-aware, UTC). Naive datetimes are rejected everywhere.
  Paise = int (never float). Id = str (ULID).
  DomainEvent: { event_id: Id, occurred_at: SimTime }  plus payload per event (see Locked
    Contracts LC-3). Events carry IDs and small facts, never entities.
  DomainError(code: str, message: str, details: list[dict] = []) with subclasses
    ValidationFailed(422), Unauthenticated(401), Forbidden(403), NotFound(404), Conflict(409),
    ExternalFailure(502, internal), InvariantViolated(500, a bug).

ERROR HANDLING STRATEGY:
  Errors are raised by domain and application code as DomainError subclasses and translated
  once, in the interfaces layer, to the error JSON in DOC 2 §2.4. Developer detail goes to
  logs with the request id; users get the text from messages.py only. No bare except, no
  silent pass; a swallowed error must log with a reason.

EDGE CASES TO HANDLE:
  - SimClock asked to go backwards: ignore, log once per occurrence with both times.
  - Two timers with the same key: last one wins (documented, tested).
  - Timer callback raises: log, continue with the next timer; never stop run_due.
  - EventBus handler for an unknown event type: no-op.
  - Policy file has a valid YAML but a key of the wrong type: abort boot with the key path.

PERFORMANCE CONSIDERATIONS:
  Scheduler uses a heap keyed by time (plus a dict for cancel). Nothing here is hot except
  run_due, called once per tick and once per ingest batch.

TESTING PLAN:
  Unit:        SimClock monotonicity; Scheduler ordering, replace, cancel, exception isolation;
               EventBus ordering and aggregated error; Policy rejects bad files; new_id sortable.
  Integration: contracts JSON Schema validates the golden-scenario payloads.
  E2E:         none (covered by the golden scenario).
```

---

## M1 — Scenario Simulator & Synthetic Data Engine

```
FEATURE: M1 — Scenario Simulator & Synthetic Data Engine   (external system: apps/world-sim)

MODULE STRUCTURE:
  apps/world-sim/src/worldsim/
    ├── core/                       PURE. No I/O, no wall clock. DSA seam.
    │   ├── config.py               SimConfig: typed model of config/sim.default.yaml
    │   ├── rng.py                  rng_for(seed, *names) -> np.random.Generator (SeedSequence
    │   │                           keyed by names, so order of iteration never changes results)
    │   ├── registry.py             build_registry(cfg, rng) -> Registry (banks, locations, cells,
    │   │                           units, regions)
    │   ├── clusters.py             MuleCluster model; build_clusters(cfg, registry, rng)
    │   ├── behaviour.py            choose_locations(), split_under_caps(), pick_channel()
    │   ├── timing.py               sample_delay_min(mixture, rng)
    │   ├── generator.py            World; World.step(t0, t1) -> list[TruthEvent]
    │   ├── scenarios.py            inject_cluster(), guided_demo_script()
    │   ├── observe.py              observe(events, cfg, rng) -> list[ObservedEvent]
    │   ├── ledger.py               AssumptionLedger.build(cfg) -> LedgerDoc
    │   └── checks.py               compare_to_public(world_summary, anchors) -> CheckReport
    ├── writer/
    │   ├── emitter.py              ApiEmitter (HTTP, idempotent, retry) ; JsonlEmitter (files)
    │   └── batches.py              to_complaint_batch(), to_observation_batch(), to_registry()
    ├── runner.py                   LiveRunner (speed loop), HistoryRunner (bulk)
    ├── truth_store.py              world.db repository (truth, runs)
    ├── control_api/                FastAPI app: /control/*   (demo console backend)
    ├── oracle_api/                 FastAPI app: /oracle/*   (evaluation only, never routed)
    ├── cli.py                      history | live | sweep-world | ledger | check
    └── tests/                      unit/ golden/ property/

SHARED SURFACES:
  packages/contracts (ingest models) and config/sim.default.yaml. Reads the API only through
  ApiEmitter. Never imports nakabandi.*.

FUNCTION & CLASS DESIGN:
  build_registry(cfg: SimConfig, rng) -> Registry
      Places banks, ATM/branch/agent locations inside the four demo states' districts using the
      bundled data; fills gaps with synthetic points (source="synthetic"); assigns grid cells
      and an activity_index in [0,1] per location; places response units.
  build_clusters(cfg, registry, rng) -> list[MuleCluster]
      Each cluster: accounts (each with issuing bank and home location), a runner footprint
      (centre points, radius from footprint.locality, size from footprint.size_per_cluster),
      a channel mix, a timing mixture, a lifetime, a cadence. No real names; ids like C-0114.
  World.step(t0, t1) -> list[TruthEvent]
      Generates complaints for the interval (Poisson count from load, geography from
      state_weights, category and amount from config), assigns a cluster (or an innocent
      account at noise.innocent_layer1_rate), builds hops through 2-12 layers, then schedules
      cash-outs: split_under_caps() over the cluster's accounts and cards, choose_locations()
      (issuing-bank footprint and runner footprint), sample_delay_min() from the mixture,
      pick_channel() from the mix. Returns events sorted by event time.
  observe(events, cfg, rng) -> list[ObservedEvent]
      Complaints are observed at reported time; hops with the complaint; cash-out observations
      at event_at + lag (lag.observation_hours, sampled). Guarantee: observed_at >= event_at.
  inject_cluster(world, district_id, size, fast_weight, locality) -> ClusterId
      Adds a never-seen cluster from "now" (used by S4 and the guided demo).
  AssumptionLedger.build(cfg) -> LedgerDoc
      One row per parameter: key, value, tag (verified | derived | assumed | swept), source
      note, confidence. Exported as Markdown and JSON with every run.
  compare_to_public(summary, anchors) -> CheckReport
      Compares generated complaints/day, mean amount, state weights (and any distribution we
      have an anchor for, via a KS test) with the verified figures; reports matches AND
      mismatches; never raises on mismatch.
  LiveRunner.run(world, emitter, speed_getter, clock_state):
      Loop every 0.5 real seconds: advance sim time by speed x elapsed, call World.step,
      observe, push due observed events (a priority queue keyed by observed_at) in batches,
      then emit Tick(now_sim). Pausable, resumable, speed changeable while running.
  SRP check: core never emits or stores; runner never generates; emitter never decides content.

INTERFACES & CONTRACTS:
  TruthEvent (internal): ComplaintTruth | HopTruth | CashOutTruth, each carrying cluster_id
    (truth). Truth NEVER leaves this app except through the oracle API.
  ObservedEvent -> contracts: ComplaintBatch, CashOutObservationBatch, RegistryUpdate, Tick (LC-1).
  Idempotency key = sha256(f"{seed}:{run_id}:{batch_no}") so a resend is harmless.
  Control API (LC-8):
    POST /control/start   { scenario: "free" | "guided_demo", speed?: number }
    POST /control/pause | /control/resume
    POST /control/speed   { factor: 1..60 }          (hosted cap enforced here as well)
    POST /control/reset   { seed?: number }          admin only, gated at the proxy
    POST /control/inject-cluster { district_id, size, fast_weight, locality }
    GET  /control/status  -> { state, sim_time, speed, seed, counts, scenario, last_error }
  Oracle API (never routed): GET /oracle/cashouts?from&to, GET /oracle/clusters,
    GET /oracle/complaints/{external_ref}/truth.
  SimConfig top-level keys: seed, world, load, amounts, network, caps, timing, channels,
    footprint, mule, geo, kit, lag, noise, scenario. Defaults and priors: DOC 2 Appendix A.

ERROR HANDLING STRATEGY:
  Invalid config: exit at start naming the bad key path (never generate with a guess).
  API unreachable or 5xx: retry with backoff using the SAME idempotency key; after N failed
  attempts, state becomes "stalled", buffering up to a cap of batches, status shows last_error.
  API 4xx on a batch: log the payload id, mark the run "invalid_batch", stop (a contract bug,
  not a transient error). Control API returns the standard error JSON; the console shows it.

EDGE CASES TO HANDLE:
  - observed_at earlier than event_at: impossible by construction; asserted in tests.
  - Cash-out amounts exceed caps: split across cards, days and accounts (never exceed a cap).
  - Cluster dormancy (lifetime ended): no new complaints route to it; residual cash-outs finish.
  - Bridge accounts (an account used by two clusters, config network.bridge_rate): creates
    genuine merges so union-find is exercised.
  - Complaints landing near midnight or window edges: intervals are half-open (t0, t1].
  - Injected cluster while paused: takes effect on resume.
  - Speed change mid-run: no duplicated or skipped sim time.
  - Reset during a run: stops cleanly, wipes world.db, restores seeded state, new run id.
  - History longer than memory allows: generate in daily chunks, stream to the emitter.

PERFORMANCE CONSIDERATIONS:
  Vectorise per day with numpy; do not create one Python object per event in hot paths until
  the final conversion. 30-day history in under 60 s on a laptop. Avoid per-event RNG
  creation (draw arrays). Do not optimise beyond that.

TESTING PLAN:
  Unit:        rng_for determinism; sample_delay_min matches the configured mixture (KS test);
               split_under_caps never exceeds caps; observe() invariants; ledger completeness
               (every config key appears once); compare_to_public reports mismatches.
  Property:    events sorted by time; observed_at >= event_at; same seed and config give an
               identical event hash; different seeds differ.
  Integration: ApiEmitter against a stub API: retry with the same key, stalls and recovers.
  Golden:      config `golden` (3 days, about 600 complaints/day, 6 clusters, seed 42) produces
               a fixed sha256 of its event stream; the API golden test consumes this stream.
  E2E:         Demo Console start/pause/speed/inject changes the status endpoint accordingly.

GUIDED DEMO SCRIPT (scenario "guided_demo", consumed by docs/demo-script.md, Track D Step D7):
  T+0h warm-up on history; T+2h a complaint hits a known cluster (alert, interceptable);
  T+3h a second complaint on the same cluster (merge into the same alert / case);
  T+5h an innocent-holder complaint (low confidence, no hold); T+6h an injected new cluster
  (cold-start banner, wide forecast, abstention); T+8h outcomes reconcile (hit, late, miss).
```

---

## Evaluation Harness

```
FEATURE: Evaluation Harness   (module nakabandi.evaluation, offline; the only oracle reader)

MODULE STRUCTURE:
  apps/api/src/nakabandi/evaluation/
    ├── __init__.py          facade: run_experiment, load_results
    ├── config.py            ExperimentConfig (seed, days_history, days_test, sweep grid, models)
    ├── oracle_client.py     OracleClient: reads world-sim /oracle or a truth file
    ├── runner.py            run_experiment(cfg) -> ExperimentResult
    ├── baselines.py         HotspotBaseline, NearestToVictimBaseline, BankFootprintBaseline
    │                        (each implements the LocationScorer port)
    ├── metrics.py           pure metric functions (DSA seam)
    ├── sweeps.py            expand_grid(), run_sweep()
    ├── store.py             experiment_runs / experiment_metrics repositories
    ├── report.py            to_json(), to_markdown() for the Evaluation page and the README
    ├── cli.py               `npm run sweep`, `npm run calibrate`
    └── tests/

SHARED SURFACES:
  LocationScorer and TimingModel ports (forecast), ingestion use cases (intake), experiment
  tables. Imports the oracle client; main.py must never import this module.

FUNCTION & CLASS DESIGN (metrics.py, all pure):
  hit_rate_at_k(preds: Sequence[RankedItems], truth: Sequence[set[str]], k: int) -> float
      share of forecasts whose top-k contains at least one true cash-out location at that level
  precision_at_k(preds, truth, k) -> float           mean fraction of top-k that is true
  lead_time_minutes(alert_times, hit_event_times) -> LeadTimeStats   (median, p10, p90)
  brier_score(probs: array, outcomes: array) -> float
  reliability_curve(probs, outcomes, bins=10) -> list[BinStat]
  interceptable_share(assessments, true_delays_min, true_etas_min) -> ShareStats
      (predicted-interceptable precision and recall against the oracle)
  dispatches_per_interception(assessments, outcomes) -> float   (ladder vs dispatch-all)
  false_hold_rate(assessments, truth_is_mule: Sequence[bool]) -> float   per 1,000 alerts
  cold_start_curve(results, bucket_by="prior_cashouts") -> list[CurvePoint]
  run_experiment(cfg) -> ExperimentResult:
      1 generate world headless (seeded) -> 2 load history through the SAME ingest use cases
      into a throwaway database with a SimClock -> 3 train scorer and timing (as_of = end of
      history) -> 4 replay the test period complaint by complaint through the pipeline ->
      5 join predictions with oracle truth -> 6 compute every metric per resolution, per
      baseline -> 7 store rows.
  expand_grid(sweep) -> list[ExperimentConfig]   timing median x channel mix x locality.
  SRP check: metrics know nothing about databases; runner orchestrates; store persists.

INTERFACES & CONTRACTS:
  ExperimentResult: { run_id, config_hash, rows: [{ metric, resolution?, baseline?, sweep_key,
    value, n }] }. Stored in experiment_metrics; served by GET /evaluation/runs (DOC 2 §2.4).
  Metric names are an enum in contracts (LC-2 extension): hit_rate_at_k, precision_at_k,
    lead_time_median, brier, interceptable_precision, interceptable_recall,
    dispatches_per_interception, false_hold_rate, cold_start_hit_rate.

ERROR HANDLING STRATEGY:
  A failed run stores status "failed" with the error and does not delete partial rows from
  other runs. The CLI exits non-zero. Sweeps continue past a failed cell and report it.

EDGE CASES TO HANDLE:
  - Forecast with abstained levels: excluded from that level's precision, counted in an
    "abstention rate" metric (so abstention cannot inflate precision unnoticed).
  - Complaint with no truth cash-out inside the horizon: counted as a miss for timing, excluded
    from location hit rate, and reported as a separate "no-cashout" count.
  - Tiny test sets: metrics report n and refuse to compute a rate when n < 30.
  - Reproducibility: config_hash includes seed, sweep parameters, code version and data hash.

PERFORMANCE CONSIDERATIONS:
  Default sweep uses 7-day worlds and a grid of 3 x 3 x 3; target under 3 minutes per cell. Run
  cells sequentially; parallelism is a later option. Cache generated worlds by config hash.

TESTING PLAN:
  Unit:        every metric against a small hand-computed fixture; expand_grid; abstention
               accounting; n < 30 guard.
  Integration: run_experiment on the golden config completes and is deterministic (same
               config hash, same metric rows).
  E2E:         none (the Evaluation page reads stored rows).
```

---

## M2 — Predictive Engine

```
FEATURE: M2 — Predictive Engine   (modules intake, graph, forecast + the pipeline process manager)

MODULE STRUCTURE:
  apps/api/src/nakabandi/
    intake/
      ├── __init__.py            facade: IngestService (complaints, hops, observations, registry, tick)
      ├── domain/                validate_complaint(), normalise_ref()            [pure]
      ├── application/           IngestComplaints, IngestHops, IngestObservations, IngestRegistry,
      │                          AdvanceClock; ports: ComplaintRepo, AccountRepo, HopRepo,
      │                          ObservationRepo, BatchRepo
      ├── infrastructure/        SQLAlchemy repositories
      └── interfaces/            /ingest/* routers (service key)
    graph/
      ├── __init__.py            facade: ClusterService.resolve(), .context_for(), .rebuild()
      ├── domain/                disjoint_set.py, cluster_index.py, footprint.py, stats.py  [DSA seam]
      ├── application/           ResolveCluster, RebuildIndex, RefineCommunities
      └── infrastructure/        repositories for clusters, members, location stats
    forecast/
      ├── __init__.py            facade: Forecaster.generate(ctx, as_of) ; Trainer.train(as_of_end)
      ├── domain/
      │   ├── types.py           ClusterContext, Candidate, FeatureRow, LevelForecast, Forecast, ...
      │   ├── candidates.py      generate_candidates()
      │   ├── features.py        FEATURE_REGISTRY, BLOCKLIST, build_features()
      │   ├── scorers.py         LocationScorer port; HistGradientBoostingScorer
      │   ├── aggregate.py       normalise(), aggregate_levels()
      │   ├── abstain.py         apply_abstention()
      │   ├── timing.py          TimingModel port; MixtureTimingModel (EM, shrinkage, conditioning)
      │   ├── explain.py         explain() -> evidence statements
      │   └── training.py        PointInTimeStats, TrainingSetBuilder, calibrators
      ├── application/           GenerateForecast, TrainModels
      └── infrastructure/        model_store.py (joblib + metadata), forecast repository
    pipeline/
      └── process_complaint.py   ProcessComplaint, RefreshOpenAlerts, RetryUnprocessed
                                 (the ONLY place that calls several module facades in sequence)

SHARED SURFACES:
  Tables: complaints, accounts, fund_hops, cashout_observations (intake); clusters,
  cluster_members, cluster_location_stats (graph); forecasts, model_versions (forecast).
  Types: Forecast and its parts are read by interception, alerting, casework, analytics and the
  web app (LC-4). LocationScorer and TimingModel ports are also used by evaluation baselines.

FUNCTION & CLASS DESIGN:
  intake.validate_complaint(c: ComplaintIn) -> None            raises ValidationFailed
      rules: amount > 0; credited_at <= reported_event_at <= observed_at; layer1 account present.
  DisjointSet:  add(x), find(x), union(a, b) -> MergeResult, size(x)
      path compression + union by size; deterministic tie-break (older cluster id survives).
  ClusterIndex: resolve(accounts: list[Id], as_of) -> ClusterResolution
      unions all given accounts (layer-1 plus known hops); returns the surviving cluster id, or
      a NEW cluster id if none existed; reports merged_from ids.
  graph.ClusterService.context_for(complaint, cluster, as_of) -> ClusterContext
      snapshot of everything the forecast may know: stats observed <= as_of (LC-2 as-of rule).
  RefineCommunities.run(): periodic NetworkX Louvain on clusters above a size threshold; only
      ANNOTATES footprint_summary.sub_communities. It never splits or merges (splitting is post-MVP).
  forecast.generate_candidates(ctx, index, policy) -> list[Candidate]
      union of: locations within radius of the home branch; within radius of the footprint centroid;
      top cells by cluster history; same-bank locations in the home district; capped at
      policy.forecast.candidates.max by distance and history.
  forecast.build_features(ctx, cand) -> FeatureRow
      features (names in FEATURE_REGISTRY): same_bank, dist_home_km, dist_centroid_km,
      cluster_loc_count, cluster_cell_count, recency_days, channel, hour_sin, hour_cos,
      amount_log, amount_x_dist, activity_index, cluster_size_log.
      BLOCKLIST names (demographic or neighbourhood-profile terms) can never enter the registry.
  LocationScorer (port): fit(train: TrainingSet) -> ScorerInfo ; raw_scores(rows) -> array
  HistGradientBoostingScorer: scikit-learn model + isotonic calibration on a time-ordered
      validation slice; raw scores are calibrated BEFORE normalisation.
  aggregate.normalise(scores) -> array (sums to 1)  ;  aggregate_levels(probs, cands) ->
      {LOCATION, CELL, DISTRICT} each a list of (id, prob) built by SUMMING children.
  abstain.apply_abstention(levels, policy) -> levels with abstained flags
      a level abstains when its top probability < policy.forecast.abstain.min_confidence[level].
  MixtureTimingModel: fit(delays_by_type) via EM (two lognormal components), then
      horizon_probs(ctx, elapsed_min, horizons) -> TimingForecast
      conditional: P(T <= elapsed + h | T > elapsed). Per-cluster posterior weights shrink toward
      the global mixture with strength n0 (policy). residual_mass = P(T > elapsed).
  explain(ctx, ranked, policy) -> list[EvidenceStatement]
      rule-based statements built from feature values; each has a stable `code`, `params` and
      English text; S5 renders other languages from code + params.
  Forecaster.generate(ctx, as_of) -> Forecast   orchestrates the domain functions above.
  Trainer.train(as_of_end) -> ModelVersionIds    builds point-in-time training rows, fits scorer,
      fits timing, stores versions with a data hash.
  PointInTimeStats: replays observations in observed_at order beside complaints in reported order
      and yields, for each complaint, the stats that were knowable at its reported time.
  pipeline.ProcessComplaint.run(complaint_id) -> ProcessResult
      calls, in order: graph.resolve -> graph.context_for -> forecast.generate ->
      interception.assess -> alerting.raise_or_merge. Marks the complaint `processed`, or
      `unprocessed` with the failing stage.
  pipeline.RefreshOpenAlerts.run(now): every policy.alerting.refresh_min sim-minutes, re-forecast
      complaints behind open alerts (new hops or observations may have changed the picture).
  pipeline.RetryUnprocessed.run(): boot and every 5 minutes; retries unprocessed complaints.
  SRP check: no forecast function reads a database; only use cases fetch data and hand it in.

INTERFACES & CONTRACTS:
  Forecast (LC-4 shape):
    { id, complaint_id, cluster_id | null, generated_at, model_versions: {scorer, timing},
      levels: { district: LevelForecast, cell: LevelForecast, location: LevelForecast },
      timing: TimingForecast, confidence: float, novelty: float, stale: bool,
      evidence: [ { code, params, text_en } ] }
    LevelForecast: { resolution, abstained: bool, confidence: float,
                     items: [ { id, prob, rank } ] }        (empty when abstained)
    TimingForecast: { weights: [w_fast, w_slow], medians_min: [..], sigmas: [..],
                      elapsed_min, residual_mass, p30, p60, p120 }   (conditional, sums are not 1)
  MEANING OF PROBABILITIES: item.prob = P(the cluster's NEXT cash-out is at this item | a cash-out
    occurs). Combined chance within horizon h = item.prob x timing.p_h. Multiple simultaneous
    cash-outs are approximated by this factorisation; the UI labels it "next cash-out".
  As-of rule: every data-reading function takes as_of; features only use records with
    observed_at <= as_of.

ERROR HANDLING STRATEGY:
  Validation errors reject the whole ingest batch item with a per-item error list (200 with
  `rejected[]`, never a silent drop). A failing pipeline stage never loses the complaint: it is
  stored, marked unprocessed with the stage name, logged, and retried. Model files missing at
  boot: the forecaster falls back to the frequency baseline, sets model_versions.scorer to
  "fallback", and the UI shows a low-confidence banner. Users never see stack traces.

EDGE CASES TO HANDLE:
  - Unknown account: create it; cluster is novel; candidates from bank footprint and district.
  - Cluster with no observed history: features from priors; wider forecast; likely abstains at
    location level.
  - Complaint reported long after credit (elapsed large): residual_mass < policy.stale_residual_mass
    marks the forecast stale (no alert; feeds the heatmap only).
  - Duplicate complaint (same external_ref): idempotent, returns the existing result.
  - Hops arrive later and merge two clusters: emit ClusterMerged; alerting re-keys alerts.
  - No candidates within radius: widen once by policy factor; if still none, all levels abstain.
  - EM fails to converge or has < n_min samples: use the global mixture, mark low confidence.
  - Probabilities must sum to 1 within 1e-6 at every level; asserted before returning.
  - Clock ticks with no complaints: only timers run.

PERFORMANCE CONSIDERATIONS:
  BallTree built once per registry version; candidate cap of 200 keeps inference to one batched
  call; cluster stats cached in memory and invalidated by ClusterUpdated. Avoid one database
  query per candidate (fetch stats once per complaint). Do not tune beyond the p95 targets in
  DOC 2 §2.7 until measured.

TESTING PLAN:
  Unit:        DisjointSet property tests (union commutative and idempotent; find stable;
               merge yields one component); MixtureTimingModel recovers a known mixture within
               tolerance; conditional probabilities monotone in h; aggregate_levels sums
               children exactly; abstention monotone in threshold; BLOCKLIST test; explain()
               covers every code.
  Leakage:     inserting an observation with observed_at > as_of does not change the forecast.
  Integration: ingest -> pipeline on the golden stream yields the expected forecasts and
               statuses; retry job recovers a forced stage failure.
  E2E:         covered by the hero-flow Playwright test (M5).
```

---

## M6 — Interceptability Planner & Intervention Ladder

```
FEATURE: M6 — Interceptability Planner & Intervention Ladder   (module interception)

MODULE STRUCTURE:
  apps/api/src/nakabandi/interception/
    ├── __init__.py            facade: Interceptor.assess(forecast, complaint, now), validate_lien()
    ├── domain/
    │   ├── units.py           UnitIndex (BallTree over unit positions)
    │   ├── travel.py          TravelTimeEstimator port; HaversineEstimator
    │   ├── probability.py     interception_probability(eta_min, timing) -> float
    │   ├── verdict.py         verdict_from(p, thresholds) -> Verdict
    │   ├── ladder.py          ladder_level(channel, verdict, confidence, policy) -> LadderLevel
    │   └── lien.py            LienProposal (value object with invariants), build_lien()
    ├── application/           AssessInterception, ValidateLien; ports: UnitRepo, AssessmentRepo
    └── infrastructure/        repositories
  tests/

SHARED SURFACES:
  InterceptAssessment and ProportionalityView shapes are read by alerting and the web app (LC-4).
  policy.yaml keys under interception.* and lien.*. The LienProposal type is used by alerting
  (request_hold) and the bank webhook contract (LC-6).

FUNCTION & CLASS DESIGN:
  HaversineEstimator.eta_min(unit, lat, lon, area_type) -> float
      distance_km x road_factor / speed_kmh[area_type] x 60. All three from policy.
  UnitIndex.nearest(lat, lon, k=3) -> list[UnitEta]
  interception_probability(eta_min, timing: TimingForecast) -> float
      = 1 - F_resid(eta) : the chance the cash-out has not yet happened when a unit arrives,
      using the conditional mixture from the forecast (never a hard-coded window).
  verdict_from(p, thresholds) -> Verdict     INTERCEPTABLE if p >= 0.7; MARGINAL if p >= 0.3;
      else NOT_INTERCEPTABLE (starting values in policy).
  ladder_level(channel, verdict, confidence, policy) -> LadderLevel     first matching rule in
      policy.interception.ladder; confidence below policy.min_confidence_for_action gives NONE
      (monitor only); default rule L2.
  LienProposal (frozen dataclass): complaint_id, account_id, disputed_paise, proposed_paise,
      expires_at, review_at. __post_init__ raises LienInvalid (ValidationFailed) unless:
      0 < proposed <= disputed; expires_at > review_at > now; complaint_id present; account_id
      belongs to the complaint's traced accounts. There is NO field or constructor for a
      whole-account freeze.
  build_lien(complaint, traced_accounts, active_liens, policy, now) -> LienProposal | None
      disputed = traced credit of this complaint into the account; proposed = disputed minus the
      already-proposed sum for this complaint (cannot exceed disputed in total); None if nothing
      is left to hold.
  Interceptor.assess(forecast, complaint, now) -> list[InterceptAssessment]
      for the top targets (up to policy.interception.targets, default 3) at the finest
      non-abstained level: nearest units, ETA, probability, verdict, channel, ladder level,
      lien proposal when the level is L1, plus a ProportionalityView.
  SRP check: probability, verdict, ladder and lien are separate functions; none does I/O.

INTERFACES & CONTRACTS:
  InterceptAssessment (LC-4):
    { id, forecast_id, target: { kind: location|cell|district, id }, channel, window_min,
      best_unit: { id, kind, eta_min } | null, interception_probability, verdict,
      ladder_level: NONE|L1|L2|L3, reason_code, reason_params,
      proportionality: ProportionalityView | null }
  ProportionalityView: { disputed_paise, proposed_paise, ratio, expires_at, review_at,
      magistrate_report_reminder: true, complaint_ref }
  Policy keys: interception.speed_kmh{urban,semi_urban,rural}, interception.road_factor,
      interception.thresholds{interceptable,marginal}, interception.targets,
      interception.min_confidence_for_action, interception.ladder[], lien.expiry_hours,
      lien.review_hours.

ERROR HANDLING STRATEGY:
  LienInvalid surfaces as 422 with a user message from messages.py; the web app shows it on the
  proportionality panel. No units in the registry is a config error: assessments return
  NOT_INTERCEPTABLE with reason_code NO_UNITS, and ops logs a warning. Never raise in the
  pipeline for missing optional data.

EDGE CASES TO HANDLE:
  - No unit within any radius: verdict NOT_INTERCEPTABLE; ladder falls to L1 or L2 by channel.
  - Channel unknown: treated as ATM with a `reason_code` noting it.
  - Timing stale or residual mass near zero: verdict NOT_INTERCEPTABLE; no L3.
  - Disputed amount zero or unknown: no lien proposal; ladder capped at L2.
  - Overlapping requests for one complaint: build_lien enforces the total cap.
  - Two complaints on one account: each has its own anchored lien; no combined lien above the
    sum of disputed amounts.
  - Units without a position: excluded and logged.

PERFORMANCE CONSIDERATIONS:
  Units are few; BallTree query per target is microseconds. Assess at most three targets.

TESTING PLAN:
  Unit:        LienProposal invariants (property test: no valid construction has proposed >
               disputed); verdict boundaries; ladder table exhaustive over channel x verdict
               (a rule exists for every pair); ETA monotone in distance; probability monotone
               non-increasing in ETA; no-units case; build_lien total cap.
  Integration: golden scenario shows L1 with a valid proportionality panel for the known
               cluster and NONE for the innocent-holder complaint.
  E2E:         alert detail shows ETA vs window and the panel (M5 Playwright test).
```

---

## M4 — Alert & Notification System

```
FEATURE: M4 — Alert & Notification System   (module alerting + channel adapters)

MODULE STRUCTURE:
  apps/api/src/nakabandi/alerting/
    ├── __init__.py            facade: AlertService (raise_or_merge, acknowledge, record_action,
    │                          on_observation, on_bank_callback, queries, rebuild_timers)
    ├── domain/
    │   ├── alert.py           Alert entity + state machine (pure)
    │   ├── dedup.py           dedup_key(cluster_id, target) -> str
    │   ├── severity.py        severity(score_inputs, policy) -> Severity
    │   ├── budget.py          rank_and_cap(alerts, policy, seed) -> Ranking
    │   ├── routing.py         route(alert, directory) -> list[Recipient]
    │   ├── outcome.py         classify_outcome(alert, observation, policy) -> Outcome | None
    │   └── messages.py        OutboundMessage (channel-agnostic content model)
    ├── application/
    │   ├── raise_or_merge.py  RaiseOrMergeAlert
    │   ├── acknowledge.py     AcknowledgeAlert          (needs Principal)
    │   ├── record_action.py   RecordAction              (needs Principal; the human gate)
    │   ├── timers.py          EscalateAlert, ExpireAlert, ReviewLien, RebuildTimers
    │   ├── reconcile.py       ReconcileOutcome
    │   ├── bank_callback.py   HandleBankCallback
    │   ├── outbox.py          EnqueueDeliveries, DeliverOutbox (worker)
    │   └── ports.py           AlertRepo, DeliveryRepo, ActionRepo, DirectoryPort, NotificationChannel
    ├── infrastructure/
    │   ├── repos.py
    │   └── channels/          sse_hub.py, email_smtp.py, sms_provider.py, sms_outbox.py, webhook_bank.py
    ├── interfaces/            routers: alerts.py, actions.py, stream.py, integrations.py, outbox_view.py
    └── templates/             (S5)
  tests/

SHARED SURFACES:
  Tables: alerts, deliveries, actions, outcomes. Consumes Forecast and InterceptAssessment (read
  through facades/events). Uses access (authorize, scope) and audit (append). policy.yaml keys
  under alerting.* and outcome.*. SSE hub is shared with analytics (heat.version events).

FUNCTION & CLASS DESIGN:
  dedup_key(cluster_id, target) -> str        f"{cluster_id}:{target.kind}:{target.id}"
  severity(confidence, amount_paise, verdict, policy) -> Severity(LOW|MEDIUM|HIGH|CRITICAL)
      score = confidence x log1p(amount) x max(interception_probability, floor); bands in policy.
  Alert state machine (transition table; anything else raises Conflict):
      open -> acknowledged | actioned | escalated | expired
      escalated -> acknowledged | actioned | expired
      acknowledged -> actioned | closed | expired
      actioned -> closed          expired, closed: terminal
  RaiseOrMergeAlert.run(forecast, assessments) -> AlertResult
      for each target that qualifies (ladder level != NONE and confidence >= alert floor):
      find an open alert by dedup_key; if found, merge (append forecast_id, refresh window and
      confidence, keep the earlier created_at, note the merge on the timeline); else create.
      Then routing, budget ranking, timers, and enqueue deliveries, all in one transaction.
  budget.rank_and_cap(alerts, policy, seed) -> Ranking
      priority = confidence x log1p(amount) x interception_probability; per (role, jurisdiction)
      queue and per shift, the top N are visible; the rest are `deferred` (budget_rank > cap)
      and stay reachable under a Backlog tab. With probability exploration_share a deferred alert
      is promoted with is_probe=True; the draw is seeded by the alert id (deterministic).
  routing.route(alert, directory) -> list[Recipient]     district officers of the target
      district; the state investigator; I4C analysts; the bank nodal contact (informational
      notice only). Escalation goes to the next role up.
  RecordAction.run(principal, alert_id, ActionIn) -> Action
      1 authorize(principal, permission_for(type), alert.scope); 2 load alert and check state;
      3 type-specific validation (request_hold: rebuild the LienProposal through
      interception.validate_lien; override: reason required); 4 create Action; 5 audit.append in
      the same unit of work; 6 transition the alert; 7 enqueue deliveries (hold_request webhook
      for request_hold); 8 publish ActionRecorded. Nothing outside this use case can create a
      hold_request delivery.
  ReconcileOutcome.on_observation(obs) -> list[Outcome]
      hit: observation at a target (or child cell) within [window_start, window_end];
      late: after window_end within outcome.grace_hours; miss: window_end + grace passed with
      none. Misses are decided by the timers, not by the arrival of data.
  HandleBankCallback.run(payload) -> Action    service key required; updates action status
      (applied | rejected | released), audit, publish AlertUpdated.
  DeliverOutbox.run_once(now_wall) -> int      picks pending deliveries whose next_attempt_at <=
      now; sends through the channel; success -> sent; failure -> attempts+1 with exponential
      backoff (5 s, 10 s, ... capped 5 min); attempts >= 5 -> dead, logged, visible in the UI.
  NotificationChannel (port): send(msg: OutboundMessage) -> DeliveryResult
      adapters: SseHub (immediate, not queued), SmtpEmail, ProviderSms with automatic fallback
      to OutboxSms, BankWebhook (HTTPX; signature per LC-6).
  SRP check: state machine, budget, routing, severity and outcome logic are separate pure
  modules; use cases orchestrate them; channels only send.

INTERFACES & CONTRACTS:
  AlertSummary / AlertDetail (LC-4):
    Summary: { id, cluster_ref, target: {kind,id,name}, severity, confidence, status, is_deferred,
               is_probe, window_start, window_end, expires_at, ladder_level, created_at,
               masked: true|false }
    Detail:  Summary + { forecast: Forecast, interception: [InterceptAssessment],
               timeline: [ { at, kind, actor?, text_code, text_params } ],
               deliveries: [ { channel, status, attempts, sent_at?, rendered_body? } ],
               actions: [ { id, type, status, actor_role, at, params } ],
               allowed_actions: [ActionType], case_id? }
  ActionIn: { type, reason (required for override; recommended otherwise), params }
    request_hold.params: { account_id, proposed_paise }  (validated <= disputed)
  OutboundMessage: { kind, alert_id, recipient, locale, subject?, body, deep_link, masked_refs }
  SSE event names and payloads: LC-5. Webhook and callback bodies: LC-6.

ERROR HANDLING STRATEGY:
  Forbidden action -> 403 with FORBIDDEN_ACTION; invalid transition -> 409 INVALID_TRANSITION;
  invalid lien -> 422 LIEN_INVALID. Delivery failures never fail the request path: they become
  Delivery rows with status and last_error, and the UI shows the failed channel and its retry
  state. A dead delivery raises an ops metric and a visible badge. Unhandled exceptions in timers
  are logged with the alert id and do not stop other timers.

EDGE CASES TO HANDLE:
  - Duplicate complaint or forecast refresh: merges into the open alert; no second notification
    unless severity rises or the window extends materially (policy).
  - Cluster merge (ClusterMerged): re-key dedup_key; if two open alerts collide, merge into the
    older and close the newer as `closed(reason=merged)`.
  - Alert acknowledged then window passes: expires only if not actioned; outcome still recorded.
  - Bank callback arrives twice or out of order: keyed by request_id; latest status wins if newer
    sim time; otherwise ignored and logged.
  - Provider SMS failure: automatic fallback adapter; delivery shows channel=sms, provider=outbox.
  - Process restart: RebuildTimers recreates escalation, expiry and lien-review timers from open
    alerts; DeliverOutbox resumes pending rows.
  - Officer without permission tries an action via a direct API call: 403, audited as denied.
  - Alert budget exhausted: deferred alerts still get the heatmap signal and a Backlog entry.

PERFORMANCE CONSIDERATIONS:
  One transaction per complaint for alert + deliveries. Index (status, severity) and the partial
  unique index on open dedup keys. SSE hub sends IDs only. Do not add a message broker.

TESTING PLAN:
  Unit:        state machine (every legal and illegal transition); dedup_key; severity bands;
               budget ranking, cap and seeded exploration determinism; routing table; outcome
               classification at window edges and grace.
  Integration: golden scenario: alert created, merged on the second complaint, escalated after the
               configured time on a fake clock, expired, reconciled; RecordAction denies a
               bank_nodal role; a hold_request delivery cannot exist without an Action row;
               outbox retry and dead-letter with a failing fake channel; restart rebuilds timers.
  E2E:         hero flow: alert appears live, officer requests a hold, bank console applies it,
               status returns to the alert (Playwright, one test).
```

---

## Bank Gateway Simulator

```
FEATURE: Bank Gateway Simulator   (external system: apps/bank-sim, Node 24 LTS + Express + TypeScript)

MODULE STRUCTURE:
  apps/bank-sim/src/
    ├── server.ts              Express app, routes wiring, startup
    ├── config.ts              env: WEBHOOK_SECRET, API_BASE_URL, API_SERVICE_KEY, SIM_STATUS_URL
    ├── verify.ts              verifySignature(), withinWindow(), IdempotencyStore
    ├── store.ts               SQLite (better-sqlite3): requests, liens, callbacks
    ├── routes/
    │   ├── webhook.ts         POST /webhooks/nakabandi
    │   └── console.ts         GET /console, POST /console/requests/:id/apply|reject|release
    ├── services/
    │   ├── liens.ts           applyLien(), releaseLien(), autoReleaseDue()
    │   └── callback.ts        sendCallback() with retry
    ├── simtime.ts             SimTimeSource: polls SIM_STATUS_URL, falls back to last webhook time
    ├── types.ts               WebhookBody, CallbackBody (from contracts JSON Schema)
    ├── views/                 server-rendered console templates (EJS)
    └── tests/                 supertest suites

SHARED SURFACES:
  The webhook and callback contract (LC-6) is shared with alerting. Nothing else.

FUNCTION & CLASS DESIGN:
  verifySignature(secret, timestamp, rawBody, signatureHex) -> boolean   constant-time compare.
  withinWindow(timestampSec, nowSec, windowSec=300) -> boolean
  IdempotencyStore.seen(key) / remember(key, response)
  handleWebhook(req):
      1 verify signature and window (reject 401); 2 dedupe on Idempotency-Key (return the stored
      response); 3 for alert_notice: store and show; respond {ack:true}; 4 for hold_request:
      re-validate proposed_lien_paise <= disputed_amount_paise and > 0 (reject 422, defence in
      depth), store as `pending`, respond {ack:true}.
  applyLien(requestId, operator, appliedPaise): requires 0 < applied <= proposed; writes a lien
      with expires_at_sim; then sendCallback(status="applied").
  autoReleaseDue(simNow): releases liens past expires_at_sim; sendCallback("released").
  sendCallback(payload): POST {API_BASE_URL}/api/v1/integrations/bank/callbacks with the service
      key; retries with backoff; idempotent by request_id + status.
  SRP check: verification, storage, lien rules and callbacks are separate files.

INTERFACES & CONTRACTS:
  WebhookBody / CallbackBody: LC-6. Console pages: /console (list by status), request detail with
  Apply / Reject buttons and the proposed vs disputed amounts. The console has its own simple
  login (env credentials) and is reachable through the proxy at /bank/*.

ERROR HANDLING STRATEGY:
  401 for signature or window failure (no detail beyond "invalid signature"); 422 for contract
  violations with the field list; 500 never leaks stack traces. Callback failures are retried and
  shown on the console as "callback pending".

EDGE CASES TO HANDLE:
  - Duplicate delivery with the same key: same response, no second record.
  - Clock skew between API and bank-sim beyond 5 minutes: 401 with a clear log line.
  - Restart: pending requests and liens persist; auto-release resumes from the last sim time.
  - Sim time source unavailable: use the latest webhook's sim time; never use wall time for lien expiry.
  - Operator applies more than proposed: rejected in the UI and by the API handler.

PERFORMANCE CONSIDERATIONS:
  Tiny volume. No optimisation.

TESTING PLAN:
  Unit:        verifySignature, withinWindow, lien invariants.
  Integration: supertest: valid signature acknowledged; bad signature 401; stale timestamp 401;
               duplicate key returns the same body and stores once; proposed > disputed 422;
               callback retries after a failing API stub.
  E2E:         part of the M4 hero-flow test.
```

---

## M5 — Law Enforcement Interface (API side)

```
FEATURE: M5 — Law Enforcement Interface (API side: modules access and audit; UI is in the web features)

MODULE STRUCTURE:
  apps/api/src/nakabandi/
    access/
      ├── __init__.py          facade: authenticate(), principal_from_request(), authorize(),
      │                        Principal, Scope, Role, Permission, mask_ref()
      ├── domain/              principal.py, permissions.py, masking.py                 [pure]
      ├── application/         Login, Logout, SeedDemoUsers, CheckRole, ListDemoUsers
      ├── infrastructure/      user_repo.py, password.py (argon2), tokens.py (JWT cookie)
      └── interfaces/          auth routers, dependencies.py (get_principal), rate_limit.py
    audit/
      ├── __init__.py          facade: AuditLog.append(entry), verify(), list()
      ├── domain/              chain.py: canonical_json(), compute_hash(), verify_chain()  [pure]
      ├── application/         AppendAudit, VerifyChain, ListAudit
      ├── infrastructure/      audit_repo.py  (INSERT and SELECT only; no update or delete method)
      └── interfaces/          /audit, /audit/verify
  tests/

SHARED SURFACES:
  Principal and Scope types (used by every use case that reads or writes). The permission matrix
  in policy.yaml. The audit facade is called from alerting, casework and access. Table: users,
  audit_entries.

FUNCTION & CLASS DESIGN:
  Principal(user_id, role, scope: Scope, display_name)     Scope(state_id?, district_id?, bank_id?)
  authorize(principal, permission, resource_scope=None) -> None    raises Forbidden. Checks the role
      has the permission (matrix) and, if a resource scope is given, that it lies inside the
      principal's scope (district within state; bank equal).
  mask_ref(ref, principal) -> str        i4c/state/admin: full within scope; district: last 4 only;
      bank_nodal: full for own bank, never returned for other banks (the repository filters first).
  Login.run(username, password) -> Session   argon2 verify; sets the signed cookie; audits success
      and failure; failure returns the same generic message for unknown user and wrong password.
  AuditLog.append(entry) -> AuditEntry
      seq = last seq + 1 inside the caller's unit of work; hash = SHA256(prev_hash || canonical_json(
      entry without hash)); the append and the audited action commit or roll back together.
  verify_chain(entries) -> VerifyReport(ok, first_bad_seq?, head_hash)
  SRP check: authentication (who), authorization (may), masking (what is shown), audit (record)
  are four separate concerns in separate files.

PERMISSION MATRIX (default; in policy.yaml; Y = allowed):
  Permission        i4c_analyst  state_investigator  district_officer  bank_nodal  demo_operator  admin
  VIEW_ALERTS            Y             Y (state)            Y (district)     Y (own bank, notice only)   N       Y
  ACKNOWLEDGE            Y             Y                    Y                Y                           N       Y
  REQUEST_HOLD           Y             Y                    N                N                           N       Y
  NOTIFY_STATION         Y             Y                    Y                N                           N       Y
  DISPATCH               Y             Y                    Y                N                           N       Y
  OVERRIDE (with reason) Y             Y                    N                N                           N       Y
  MARK_OUTCOME           Y             Y                    Y                N                           N       Y
  CREATE_EVIDENCE        Y             Y                    Y                N                           N       Y
  VIEW_CASES             Y             Y                    Y                N                           N       Y
  VIEW_AUDIT             Y             Y (own actions)      N                N                           N       Y
  VIEW_EVALUATION        Y             Y                    Y                N                           Y       Y
  SIM_CONTROL            N             N                    N                N                           Y       Y
  Rows and columns are policy data, not code.

INTERFACES & CONTRACTS:
  Session cookie: HttpOnly, SameSite=Lax, Secure in hosted mode; claims { sub, role, scope, exp }.
  GET /auth/me -> { user_id, name, role, scope, permissions: [Permission] } (the web app renders
  only what permissions allow; the API enforces regardless).
  Demo users (hosted demo mode only): one per role with documented demo-only passwords; listed by
  GET /auth/demo-users for quick-login buttons.
  AuditEntry: { seq, at, actor_id, actor_role, action, entity_type, entity_id, reason?, payload,
                prev_hash, hash }

ERROR HANDLING STRATEGY:
  401 for missing or expired session; 403 for a role or scope failure (also used when a resource
  exists outside the caller's scope, never 404, to avoid leaking existence differences); denials
  are audited. Login is rate limited (5 per minute per IP) with 429.

EDGE CASES TO HANDLE:
  - Token expired mid-session: the web client redirects to login and preserves the route.
  - User deactivated while logged in: is_active is checked on each request.
  - Bank role requests another bank's alert: 403.
  - Audit chain gap or edit: verify returns ok=false with the first bad seq.
  - Two concurrent appends: the single-writer model and UNIQUE(seq) make the second retry.
  - Demo users disabled in a non-demo deployment: /auth/demo-users returns 404.

PERFORMANCE CONSIDERATIONS:
  Principal built once per request. argon2 parameters tuned so login takes about 100 ms; never
  hash on hot paths. Verify the chain incrementally from the last verified seq for large logs.

TESTING PLAN:
  Unit:        permission matrix (table-driven, every role x permission); mask_ref cases;
               compute_hash and verify_chain detect a modified payload, deletion and reorder.
  Property:    a bank_nodal principal never receives an identifier of another bank across
               randomised alert sets.
  Integration: login, cookie flags, expiry; /auth/check for the proxy; audit appended atomically
               with an action (force a failure and confirm neither persists).
  E2E:         hero flow logs in as investigator and as bank_nodal.
```

---

## Web App Shell & Design System

```
FEATURE: Web App Shell & Design System   (apps/web foundation used by every UI feature)

MODULE STRUCTURE:
  apps/web/src/
    ├── app/
    │   ├── main.tsx, providers.tsx      QueryClient, router, toast, stream provider
    │   ├── routes.tsx                   route table with RoleGuard
    │   ├── layout/                      Shell.tsx (top bar: sim time, role, connection dot), SideNav.tsx
    │   └── auth/                        LoginPage.tsx (with quick-login buttons), usePrincipal.ts, RoleGuard.tsx
    ├── shared/
    │   ├── api/                         schema.d.ts (GENERATED), client.ts, apiError.ts
    │   ├── stream/                      useStream.ts (SSE with polling fallback), streamKeys.ts
    │   ├── tokens/                      tokens.css (designer-owned), tailwind.preset.ts
    │   ├── ui/                          Button, Badge variants, ConfidenceBar, Countdown, MaskedRef,
    │   │                                DataTable, KeyValue, Timeline, Drawer, Panel, EmptyState, ErrorState
    │   └── lib/                         format.ts (money in INR, sim-time, durations), permissions.ts
    └── features/                        alerts/ map/ clusters/ cases/ evaluation/ ops/ outbox/ audit/ demo/
  tests/                                 unit (Vitest) and e2e (Playwright)

SHARED SURFACES:
  tokens.css, shared/ui components, the generated API schema, routes.tsx, the stream provider.
  Every feature imports from shared/*, never from another feature (eslint boundaries).

FUNCTION & CLASS DESIGN:
  apiError(e) -> UiError { code, message, fields? }     maps the server's error JSON to a toast or field
      errors; `message` is already user text from the server.
  useStream(): opens GET /api/v1/stream; on alert.created / alert.updated / delivery.updated
      invalidates the matching TanStack Query keys; on heat.version invalidates heatmap queries
      (debounced 1 s); on sim.time updates the clock store. If no event or heartbeat arrives for
      20 s, or on error, it falls back to polling every 5 s and shows an amber connection dot.
  usePrincipal(): { principal, permissions, can(permission) }; RoleGuard hides routes and controls,
      while the API enforces regardless.
  Countdown({ target: SimTime }): renders time remaining using the SIM clock from the stream, not
      the browser clock.
  MaskedRef({ value, masked }): shows the value as delivered by the API (masking is server-side);
      never attempts to unmask.
  Badge variants: SeverityBadge, VerdictBadge, LadderBadge, StatusBadge. Each shows icon + text +
      colour (colour is never the only signal).
  SRP check: components render; hooks fetch or subscribe; lib formats. No component calls fetch
  directly; all data goes through the generated client and query hooks in its feature.

INTERFACES & CONTRACTS:
  Design tokens (designer-owned; names are the contract, values are free):
    color: surface.{base,raised,sunken}, text.{primary,secondary,inverse}, border.{subtle,strong},
      brand.{primary,accent}, severity.{low,medium,high,critical}, verdict.{good,warn,bad},
      status.{open,ack,actioned,expired}, focus.ring
    type: font.{sans,mono}, size scale 12/14/16/20/24/32, weight 400/500/600
    space: 4-point scale; radius.{sm,md,lg}; shadow.{sm,md}; both light and dark themes
  Routes: /login, /, /alerts, /alerts/:id, /clusters/:id, /cases, /cases/:id, /evaluation, /ops,
    /outbox, /audit, /demo (demo_operator and admin only).
  Generated types: `npm run types` regenerates schema.d.ts from the API's OpenAPI; CI fails if
  the generated file differs from what is committed.

ERROR HANDLING STRATEGY:
  Query errors render ErrorState with the server message and a retry button; mutations show a
  toast; 401 redirects to /login keeping the intended route; 403 shows a "not allowed" page
  without hinting whether the resource exists. An error boundary per route stops one feature's
  crash from blanking the shell. Developer detail goes to the console only in development.

EDGE CASES TO HANDLE:
  - SSE reconnect storms: exponential backoff up to 30 s, then polling.
  - Stale data: a subtle "updated Ns ago" indicator when the stream is degraded.
  - Very long tables: DataTable virtualises above 200 rows.
  - Small screens: alert inbox and detail collapse to a single column at 360 px.
  - Keyboard: every action reachable by keyboard; drawers trap focus and restore it.
  - Reduced motion preference respected for map transitions and the countdown.

PERFORMANCE CONSIDERATIONS:
  Route-level code splitting (the map feature is the heavy chunk). Avoid re-render storms: stream
  events invalidate queries, they do not push state into components. No premature memoisation.

TESTING PLAN:
  Unit (Vitest):   apiError mapping, useStream fallback with a fake EventSource, permissions
                   helpers, format helpers (money, durations).
  Component:       Badge variants render label + icon; Countdown uses sim time.
  E2E (Playwright, ONE hero-flow test): quick-login as investigator; an alert appears live; open
                   detail; request a hold; the bank console applies it; status returns; log in as
                   bank_nodal and confirm scope.
```

---

## M3 — Risk Heatmap Dashboard

```
FEATURE: M3 — Risk Heatmap Dashboard   (modules geo and analytics; web feature map)

MODULE STRUCTURE:
  apps/api/src/nakabandi/
    geo/
      ├── __init__.py          facade: GeoService (regions, locations, cell_of, spatial_index)
      ├── domain/              grid.py (cell_id_for(lat, lon, grid_km)), spatial.py (SpatialIndex over BallTree)
      ├── application/         ApplyRegistry (from IngestRegistry), QueryRegions, QueryLocations
      ├── infrastructure/      repositories, bundled GeoJSON loader (data/geo)
      └── interfaces/          /geo/regions, /geo/locations
    analytics/
      ├── __init__.py          facade: HeatmapService.query(filters, principal), TimeseriesService,
      │                        LiveMetrics
      ├── domain/              rollup.py (bucket_hour, mass_from_forecast), potential.py (decayed
      │                        intensity), suppress.py (apply_k_threshold)
      ├── application/         ProjectForecastMass, ProjectAlertChange (event subscribers),
      │                        QueryHeatmap, QueryTimeseries, QueryLiveMetrics
      ├── infrastructure/      rollup_repo.py
      └── interfaces/          /analytics/heatmap, /analytics/timeseries, /analytics/live-metrics
  apps/web/src/features/map/
      ├── MapPage.tsx, HotspotDrawer.tsx, FilterPanel.tsx, TimeSlider.tsx, Legend.tsx
      ├── MapAdapter.ts        interface: setLayerData(), fitTo(), onFeatureClick(), destroy()
      ├── maplibre/MapLibreAdapter.ts      the ONLY file that imports maplibre-gl
      ├── layers/              cellsLayer.ts, locationsLayer.ts, alertsLayer.ts
      └── useHeatmap.ts, useRegions.ts

SHARED SURFACES:
  Tables: heat_rollups (analytics owns), regions/locations/cells/units/banks (geo owns). SSE hub
  (heat.version). The HeatmapResponse shape (LC-4). Bundled GeoJSON in data/geo. Filter option
  values (categories, amount bands) come from policy via the API, not hard-coded in the web app.

FUNCTION & CLASS DESIGN:
  cell_id_for(lat, lon, grid_km) -> str        equirectangular grid; deterministic; no dependencies.
  SpatialIndex.within_radius(lat, lon, km) / nearest(lat, lon, k)   BallTree with haversine.
  mass_from_forecast(forecast, assessment_by_target) -> list[MassItem]
      expected mass per target = item.prob x timing.p120 (next two hours), per level as available.
  potential.decayed_intensity(items, now, lookback_h, half_life_h) -> float
      exponentially decayed sum of recent forecast mass. It is a PERSISTENCE ESTIMATE of recent
      forecast intensity over the next 72 h, not a separate model, and the legend says so.
  suppress.apply_k_threshold(cells, k) -> (kept, suppressed_count)
      cells with fewer than k contributing alerts are suppressed above LOCATION level.
  ProjectForecastMass (subscriber to AlertRaised / AlertUpdated / ForecastGenerated): upserts
      heat_rollups keyed (target_kind, target_id, hour_bucket, category, amount_band,
      confidence_band, layer) and bumps `version`; publishes heat.version through the SSE hub.
  QueryHeatmap.run(filters, principal) -> HeatmapResponse
      reads rollups only, restricted to the principal's scope, sums buckets in the window, rolls
      cells up to districts on request, applies suppression.
  MapPage: composes FilterPanel, TimeSlider (replay uses sim time), the map, Legend, HotspotDrawer
      (click a cell or location -> underlying alerts with links and their evidence statements).
  SRP check: analytics never reads other modules' tables; the map component never formats data.

INTERFACES & CONTRACTS:
  Filters: { layer: live|potential, level: district|cell|location, from, to, state?, district?,
    category?, amount_band?, cluster_id? (LEA roles), min_confidence?, bbox? }
  HeatmapResponse (LC-4): { layer, level, generated_at, version, cells: [ { id, kind, name?, lat,
    lon, value, alert_count } ], suppressed_count, legend: { min, max, unit, note } }
  Drill-down order: state -> district -> cell -> location. Location points and unit markers come
    from /geo/locations (bbox, kind, bank).

ERROR HANDLING STRATEGY:
  Invalid filter combination -> 422 with field details; empty result -> a friendly empty state,
  never an error. A map render failure (WebGL unavailable) shows a table view of the same data so
  the demo never shows a blank canvas.

EDGE CASES TO HANDLE:
  - Cells below the k-threshold: suppressed above location level and counted in suppressed_count.
  - No alerts in the window: empty state with "Nothing predicted in this window".
  - Time slider moved during replay: queries use the slider window; live updates pause with a
    "return to live" button.
  - Role scope: a district officer sees only their district's cells; the API restricts, the UI
    reflects.
  - Large bbox with many points: cluster the point layer; cap points returned per request.
  - Offline: boundaries and points are bundled; no tile request is ever required.

PERFORMANCE CONSIDERATIONS:
  Rollup table indexed (hour_bucket, category) and (target_id); one query sums the window; the
  response carries an ETag from `version`, so unchanged data returns 304. Debounce filter changes
  (250 ms) and stream-triggered refetches (1 s). Location points are served by bbox with a cap.

TESTING PLAN:
  Unit:        cell_id_for round trips; decayed_intensity monotone in age; apply_k_threshold;
               mass_from_forecast sums to at most the forecast's probability mass.
  Integration: rollups after the golden scenario match a hand-computed fixture; a district_officer
               query returns only their district; filters change results as expected.
  Component:   FilterPanel emits the right filter object; MapPage falls back to the table view.
  E2E:         the hero-flow test checks the live layer updates after an alert.
```

---

## S1 — Cluster Case Bundling

```
FEATURE: S1 — Cluster Case Bundling   (module casework: bundling; web feature cases and clusters)

MODULE STRUCTURE:
  apps/api/src/nakabandi/casework/
    ├── __init__.py            facade: CaseService (bundle(cluster_id), get, list)
    ├── domain/                case.py (Case model), bundle.py (build_case), brief.py (render inputs)
    ├── application/           BundleCluster, GetCase, ListCases; subscriber on ClusterUpdated
    ├── infrastructure/        case_repo.py; templates/case_brief.md.j2
    └── interfaces/            /clusters, /clusters/{id}, /cases, /cases/{id}
  apps/web/src/features/{clusters,cases}/   ClusterGraph.tsx (Cytoscape), CasesPage.tsx, CaseDetail.tsx

SHARED SURFACES:
  Reads cluster data through the graph facade (never its tables). Case is read by S2 (evidence
  pack). Cytoscape wrapper component is used by clusters and cases.

FUNCTION & CLASS DESIGN:
  build_case(cluster_view, complaints, accounts, cashouts, as_of) -> Case        [pure]
      Case: { id, cluster_ref, complaint_count, victim_count, total_paise, first_seen, last_seen,
      accounts: [masked refs, bank, complaint_count], top_locations: [{id, count, last_at}],
      sub_communities, timeline, brief_md }
  render_brief(case, locale) -> str     Markdown from a template with the totals and a factual list.
  BundleCluster.run(cluster_id): rebuilds the case on ClusterUpdated (debounced) and on demand.
  SRP check: build_case aggregates; render_brief formats; the use case fetches and stores.

INTERFACES & CONTRACTS:
  GET /clusters/{id} -> { cluster_ref, size, status, novelty, nodes: [{id, kind, masked_ref?,
    bank?}], edges: [{from, to, amount_paise?}] }   (masked per role)
  GET /cases/{id} -> Case. The brief states facts and ends with: "Whether to register an FIR is
  the investigating officer's decision." It never asserts guilt or names real persons.

ERROR HANDLING STRATEGY:
  404-equivalent for out-of-scope clusters returns 403 (see access). A case rebuild failure keeps
  the previous version and logs; the UI shows "updated at".

EDGE CASES TO HANDLE:
  - Cluster merge: the surviving cluster's case absorbs the other's complaints; the merged case is
    closed with a pointer.
  - Very large cluster: the graph view caps nodes at 200, showing top accounts by volume with a
    "+N more" node.
  - Single-complaint cluster: still a case, flagged "single complaint".
  - Missing masked fields for a role: the graph omits refs rather than showing blanks.

PERFORMANCE CONSIDERATIONS:
  Case rebuild is debounced (once per cluster per sim hour) and reads through facades in batches.

TESTING PLAN:
  Unit:        build_case totals on a fixture; masking in the graph payload; brief contains the
               disclaimer and no unmasked refs.
  Integration: golden scenario: two complaints on one cluster give one case with both.
  E2E:         cases page shows the bundled case (covered by the hero-flow test's last step).
```

---

## S2 — Evidence Pack & Audit Chain

```
FEATURE: S2 — Evidence Pack & Audit Chain   (module casework: evidence; audit chain from M5)

MODULE STRUCTURE:
  apps/api/src/nakabandi/casework/evidence/
    ├── bundle.py              EvidenceBundle (JSON export of prediction, evidence, timeline, actions,
    │                          outcomes, audit excerpt with head hash)               [pure]
    ├── hashing.py             hash_report(components) -> HashReport                 [pure]
    ├── certificate.py         Section63Draft model and builder                      [pure]
    ├── pdf.py                 render_pdf(bundle, draft, locale) -> bytes  (ReportLab)
    ├── service.py             BuildEvidencePack use case
    └── file_store.py          FileStore port + LocalFileStore
  interfaces:                  POST /alerts/{id}/evidence-pack, GET /evidence-packs/{id}/download
  apps/web: "Evidence pack" button and download on alert detail and case detail; Audit page with a
            "Verify chain" button.

SHARED SURFACES:
  audit facade (head hash and verify), casework Case, alerting alert detail (through facades),
  FileStore port. Table: evidence_packs.

FUNCTION & CLASS DESIGN:
  hash_report(components: dict[str, bytes]) -> HashReport { algorithm: "SHA-256", items:
      [ {name, sha256} ], bundle_sha256 }        hashes each component and the canonical bundle.
  Section63Draft { record_description, system_description, production_process,
      condition_statements: [text to be confirmed by the signatory], hash_algorithm, hash_values,
      part_a: { role: "person in charge", name: "", designation: "", signature: "" },
      part_b: { role: "expert", name: "", qualification: "", signature: "" },
      label: "DRAFT - unsigned drafting aid, not a legal certificate" }
  render_pdf(...) -> bytes: sections: summary, forecast and evidence statements, interception and
      proportionality, timeline of actions and outcomes, audit excerpt and head hash, hash report,
      certificate draft. Non-LEA roles get masked references.
  BuildEvidencePack.run(principal, alert_id) -> EvidencePack: authorize(CREATE_EVIDENCE); assemble
      bundle; render; save via FileStore (returns the PDF's SHA-256, stored in the database and
      shown in the UI, since a file cannot contain its own hash); write audit entry; return
      metadata. Packs are immutable: regenerating creates a new version.
  SRP check: bundle assembles, hashing hashes, certificate models, pdf renders, service orchestrates.

INTERFACES & CONTRACTS:
  EvidencePack: { id, alert_id | case_id, version, created_at, created_by_role, sha256, size_bytes,
      audit_head_hash, download_url }
  The certificate layout must be checked against the official Schedule form of the evidence law
  before it is presented as matching it; until then the label stays DRAFT.

ERROR HANDLING STRATEGY:
  PDF generation errors return 500 with EVIDENCE_BUILD_FAILED and a log entry; the alert is
  unaffected. Missing components (for example no actions yet) render "none recorded" sections.

EDGE CASES TO HANDLE:
  - Verify chain after a tampered row: the pack embeds the head hash at build time, so later
    tampering is detectable by comparison.
  - Regeneration: version increments; earlier packs stay downloadable.
  - Unicode text (Hindi labels, S5): the PDF embeds a font that supports Devanagari.
  - Large timeline: paginate the PDF; cap listed entries and reference the audit range.

PERFORMANCE CONSIDERATIONS:
  Synchronous generation is acceptable (one alert, few pages). Do not queue it.

TESTING PLAN:
  Unit:        hash_report is reproducible; Section63Draft always carries the DRAFT label; bundle
               contains no unmasked refs for non-LEA roles.
  Integration: build a pack for a golden alert; recompute hashes from the stored bundle and match;
               tamper an audit row and confirm /audit/verify fails and the pack's head hash no
               longer matches.
  E2E:         download link works from alert detail.
```

---

## S3 — Officer Feedback Loop

```
FEATURE: S3 — Officer Feedback Loop   (modules alerting: outcomes and review queue; graph: affinity)

MODULE STRUCTURE:
  alerting/application/feedback.py       MarkOutcome (human), ReviewQueue ordering
  alerting/domain/uncertainty.py         uncertainty(confidence) and queue ordering            [pure]
  graph/application/apply_confirmed.py   ApplyConfirmedCashOut (officer-confirmed observation)
  evaluation/                            feedback sweep parameters and the before/after metric
  apps/web/src/features/alerts/          OutcomeButtons.tsx, ReviewQueue.tsx, FeedbackPanel.tsx

SHARED SURFACES:
  outcomes table (alerting), cluster_location_stats (graph, through its facade), the Evaluation
  page.

FUNCTION & CLASS DESIGN:
  MarkOutcome.run(principal, alert_id, result: hit|miss|late, location_id?, reason?) -> Outcome
      authorize(MARK_OUTCOME); records the outcome with source="officer"; when the officer
      confirms a cash-out location it calls graph.apply_confirmed(...), which records an
      observation with source="police_report" at now, so the affinity updates immediately
      instead of waiting for lagged bank reports; audit entry.
  uncertainty(confidence) -> float      = 1 - abs(2 x confidence - 1); highest near 0.5.
  ReviewQueue.order(alerts) -> list      most uncertain first (active learning); ties by severity.
  Before/after metric: the evaluation harness runs each cell with feedback.enabled = false and true
      (a simulated officer labels a fraction feedback.label_rate of alerts using oracle truth) and
      stores hit_rate_at_k for both; the Evaluation page plots them.
  SRP check: outcome recording, queue ordering and affinity application are separate use cases.

INTERFACES & CONTRACTS:
  POST /alerts/{id}/outcome { result, location_id?, reason? }  ->  Outcome { id, alert_id, result,
    source: officer|reconciled, at }
  policy keys: feedback.label_rate (evaluation only), alerting.review_queue.size.

ERROR HANDLING STRATEGY:
  An officer outcome that conflicts with an automatic reconciliation is stored as a separate row
  (source recorded); the alert shows both; the later one drives the closing state.

EDGE CASES TO HANDLE:
  - Officer marks hit at a location that is not a registry location: 422.
  - Repeated marks: idempotent per (alert, result, location).
  - Feedback on an expired alert: allowed for learning; does not reopen the alert.
  - Feedback that would create an observation earlier than existing data: observed_at is always now.

PERFORMANCE CONSIDERATIONS:
  Negligible.

TESTING PLAN:
  Unit:        uncertainty ordering; MarkOutcome permission (bank_nodal denied).
  Integration: confirmed hit updates the cluster's stats and changes the next forecast for that
               cluster on a fixture; feedback on/off runs both complete in the harness.
  E2E:         outcome buttons change the alert status.
```

---

## S4 — Cold-Start Drill

```
FEATURE: S4 — Cold-Start Drill   (graph: novelty; forecast: fallback priors; simulator: injection)

MODULE STRUCTURE:
  graph/domain/novelty.py                novelty(ctx, known_footprints) -> float             [pure]
  forecast/domain/priors.py              DistrictPrior, fallback_candidates_and_scores()     [pure]
  world-sim/core/scenarios.py            inject_cluster()  (defined in M1)
  apps/web/src/features/alerts/          NoveltyBanner.tsx
  apps/web/src/features/evaluation/      ColdStartChart.tsx
  evaluation/                            cold_start_curve() (defined in the Evaluation Harness)

SHARED SURFACES:
  Forecast.novelty and Forecast.stale fields (LC-4); the alert detail layout.

FUNCTION & CLASS DESIGN:
  novelty(ctx, known_footprints) -> float in [0,1]
      1 - the maximum Jaccard similarity between the context's (bank, district, cell) set and each
      known cluster's footprint set (inverted index for speed); 1.0 for a totally unseen pattern;
      forced to 1.0 for a brand-new cluster with no observed cash-outs.
  fallback: when novelty >= policy.forecast.novelty_threshold (0.7) the candidates and scores come
      from DistrictPrior (aggregate of active clusters' stats in the district) and the issuing
      bank's footprint; confidence is capped by policy.forecast.novel_confidence_cap; the location
      level normally abstains.
  NoveltyBanner: "New pattern: low confidence. Showing district-level priors." with the abstention
      state per level.

INTERFACES & CONTRACTS:
  Forecast.novelty in [0,1]; the banner shows when novelty >= threshold.
  Demo: POST /control/inject-cluster (LC-8), and the guided-demo script includes it.

ERROR HANDLING STRATEGY:
  No known footprints (start of run): novelty = 1.0 and fallback applies; no error.

EDGE CASES TO HANDLE:
  - A novel cluster that later grows history: novelty falls as observations accumulate; the banner
    disappears without a page reload (via stream refetch).
  - Novel cluster in a district with no history: district prior falls back to the state prior.
  - Two novel clusters at once: independent.

PERFORMANCE CONSIDERATIONS:
  Inverted index keyed by (bank, district); recomputed on ClusterUpdated. Negligible.

TESTING PLAN:
  Unit:        novelty is 1.0 for empty knowledge and falls as overlap rises; fallback always returns
               normalised probabilities; abstention triggers at the finest level.
  Integration: injecting a cluster in the golden run produces a novelty banner and low-confidence
               alert; the cold_start_curve shows improvement with observations.
  E2E:         the Demo Console injection shows the banner.
```

---

## S5 — Bilingual Alert Templates

```
FEATURE: S5 — Bilingual Alert Templates   (module alerting: templates and localisation)

MODULE STRUCTURE:
  apps/api/src/nakabandi/alerting/templates/
    ├── en/{sms.txt.j2, email_subject.j2, email_body.j2}
    ├── hi/{sms.txt.j2, email_subject.j2, email_body.j2}
    └── evidence_text.py       EVIDENCE_TEXT[locale][code] with {param} placeholders
  alerting/domain/render.py    render(kind, alert_view, locale) -> RenderedMessage           [pure]
  alerting/domain/sms.py       sms_segments(text) -> SmsInfo(encoding, segments, length)     [pure]

SHARED SURFACES:
  Forecast.evidence codes (from forecast/explain), User.locale, OutboundMessage.

FUNCTION & CLASS DESIGN:
  render(kind, view, locale) -> RenderedMessage { subject?, body }
      Jinja2 in strict mode (an unknown variable raises); masked refs only; deep link included.
  sms_segments(text) -> SmsInfo      GSM-7 limit 160 (153 per segment when concatenated); Unicode
      (Hindi) limit 70 (67 per segment); if the message exceeds `alerting.sms.max_segments`, the
      renderer switches to a shorter template.
  EVIDENCE_TEXT lookup: unknown code in a locale falls back to English and logs.
  SRP check: templates hold wording, render fills them, sms.py measures.

INTERFACES & CONTRACTS:
  User.locale in {en, hi}; default en. Delivery.rendered_body stores exactly what was sent.
  Hindi wording is machine-drafted and MUST be reviewed by a native speaker before any demo use.

ERROR HANDLING STRATEGY:
  A rendering failure never blocks alert creation: the delivery falls back to the English template
  and logs TEMPLATE_RENDER_FAILED.

EDGE CASES TO HANDLE:
  - Missing translation code: English fallback and a log line.
  - Hindi SMS over the segment limit: short template.
  - Names or numbers inside Devanagari text: numerals stay Western digits for consistency.
  - Right-to-left is not needed.

PERFORMANCE CONSIDERATIONS:
  Compile templates once at startup.

TESTING PLAN:
  Unit:        every evidence code exists in both locales (completeness test); strict mode raises on
               a missing variable; sms_segments boundaries for both encodings; no unmasked ref ever
               appears in any rendered output (property test over random views).
  Integration: a Hindi-locale recipient receives the Hindi body in the outbox viewer.
  E2E:         none.
```

---

## Locked Shared Contracts

*Frozen. Definitions here are normative; code is generated from or checked against them. `USED BY` lists who depends on the exact shape.*

```
LOCKED CONTRACT: LC-1 Canonical ingestion contract (packages/contracts/ingest.py)
  DEFINITION:
    AccountIn        { account_ref: str, bank_id: Id, home_location_id?: Id }
    ComplaintIn      { external_ref: str, category: ComplaintCategory, amount_paise: int > 0,
                       victim_district_id: Id, credited_at: SimTime, reported_event_at: SimTime,
                       observed_at: SimTime, layer1_account: AccountIn }
    ComplaintBatch   { batch_id: str, idempotency_key: str, sim_time: SimTime, items: ComplaintIn[<=500] }
    HopIn            { complaint_external_ref: str, from_account: AccountIn, to_account: AccountIn,
                       amount_paise: int > 0, layer: int 1..12, event_at: SimTime, observed_at: SimTime }
    HopBatch         { batch_id, idempotency_key, sim_time, items: HopIn[<=500] }
    CashOutObsIn     { account_ref: str, location_id: Id, channel: Channel, amount_paise: int > 0,
                       event_at: SimTime, observed_at: SimTime, source: bank_report|police_report }
    CashOutObservationBatch { batch_id, idempotency_key, sim_time, items: CashOutObsIn[<=500] }
    RegistryUpdate   { version: str, banks[], regions[], cells[], locations[], units[] }
       location: { id, kind: ATM|BRANCH|AGENT, bank_id, lat, lon, district_id, cell_id, source:
                   osm|synthetic, display_name, area_type: urban|semi_urban|rural, activity_index: 0..1 }
       unit:     { id, kind: cyber_cell|station|patrol, district_id, lat, lon, status }
    Tick             { sim_time }
    Response (all)   { accepted: int, rejected: [ { index, code, message } ], sim_time }
    Rules: observed_at >= event_at; credited_at <= reported_event_at <= observed_at (complaints);
           idempotent by idempotency_key; unknown enum values are rejected, never coerced.
  USED BY: world-sim (writer), intake, evaluation, bank-sim (types only), tests.

LOCKED CONTRACT: LC-2 Shared value types, enums and the as-of rule
  DEFINITION:
    SimTime = tz-aware UTC datetime; Paise = int; Id = ULID string.
    Resolution: district | cell | location
    Channel / LocationKind: ATM | BRANCH | AGENT
    ComplaintCategory: digital_arrest | investment_scam | upi_phishing | task_job_scam
    Role: i4c_analyst | state_investigator | district_officer | bank_nodal | demo_operator | admin
    AlertStatus: open | acknowledged | actioned | escalated | expired | closed
    Severity: LOW | MEDIUM | HIGH | CRITICAL
    Verdict: INTERCEPTABLE | MARGINAL | NOT_INTERCEPTABLE
    LadderLevel: NONE | L1 | L2 | L3
    ActionType: acknowledge | request_hold | notify_station | dispatch | override
    Permission: VIEW_ALERTS | ACKNOWLEDGE | REQUEST_HOLD | NOTIFY_STATION | DISPATCH | OVERRIDE |
                MARK_OUTCOME | CREATE_EVIDENCE | VIEW_CASES | VIEW_AUDIT | VIEW_EVALUATION | SIM_CONTROL
    MetricName: hit_rate_at_k | precision_at_k | lead_time_median | brier | interceptable_precision |
                interceptable_recall | dispatches_per_interception | false_hold_rate |
                cold_start_hit_rate | abstention_rate
    AS-OF RULE: every repository or service method that reads data for forecasting takes a required
                `as_of: SimTime` and returns only records with observed_at <= as_of.
    Naming: money is *_paise; times are event_at / observed_at; ids are *_id.
  USED BY: every track.

LOCKED CONTRACT: LC-3 Domain events (in-process; fan-out only, orchestration is explicit)
  DEFINITION: DomainEvent { event_id, occurred_at } plus
    ComplaintIngested{complaint_id}  HopsIngested{complaint_ids[]}  ObservationIngested{observation_ids[]}
    ClusterUpdated{cluster_id}  ClusterMerged{from_id, into_id}  ForecastGenerated{forecast_id, complaint_id}
    InterceptAssessed{forecast_id}  AlertRaised{alert_id}  AlertUpdated{alert_id, change}
    AlertEscalated{alert_id}  ActionRecorded{action_id, alert_id}  OutcomeRecorded{alert_id, result}
    TickAdvanced{sim_time}
  USED BY: analytics, casework, alerting, graph, audit, SSE hub.

LOCKED CONTRACT: LC-4 REST response shapes consumed by the web app (OpenAPI is generated from these)
  DEFINITION: Forecast, LevelForecast, TimingForecast (M2); InterceptAssessment, ProportionalityView
    (M6); AlertSummary, AlertDetail, ActionIn, Outcome (M4/S3); HeatmapResponse (M3); Case,
    ClusterView (S1); EvidencePack (S2); Principal /auth/me (M5); Error JSON and Page<T>
    { items, next_cursor } (DOC 2 §2.4). Field lists are exactly those written in the entries above.
  USED BY: web app (all features), API routers, contract tests.

LOCKED CONTRACT: LC-5 SSE stream
  DEFINITION: GET /api/v1/stream, text/event-stream, heartbeat comment every 15 s. Events:
    alert.created {alert_id, version}   alert.updated {alert_id, version}
    delivery.updated {alert_id, delivery_id}   heat.version {version}
    sim.time {sim_time, speed, state}
    Payloads carry IDs and versions only. Events are filtered by the principal's scope.
  USED BY: alerting (hub), analytics, web stream provider.

LOCKED CONTRACT: LC-6 Bank webhook and callback
  DEFINITION:
    POST {bank-sim}/webhooks/nakabandi
    Headers: X-Nakabandi-Timestamp (epoch seconds, wall clock), X-Nakabandi-Signature =
      hex(HMAC-SHA256(secret, timestamp + "." + rawBody)), Idempotency-Key
    Body common: { kind: alert_notice | hold_request, request_id, alert_ref, bank_id, account_ref,
      complaint_ref, sim_time }      (account_ref masked for alert_notice)
    Body hold_request adds: { disputed_amount_paise, proposed_lien_paise (<= disputed, > 0),
      expires_at_sim, review_at_sim, requested_by_role }
    Response: 200 { ack: true } | 401 invalid signature | 422 contract violation
    POST {api}/api/v1/integrations/bank/callbacks (service key)
    Body: { request_id, status: applied | rejected | released, applied_amount_paise?, at_sim, note? }
    Rules: window 300 s; dedupe on Idempotency-Key; the bank side re-validates proposed <= disputed.
  USED BY: alerting (webhook adapter, callback handler), bank-sim.

LOCKED CONTRACT: LC-7 Policy configuration keys (config/policy.yaml; values are tunable, keys are frozen)
  DEFINITION:
    forecast.horizons_min[30,60,120]  forecast.candidates.{max,radius_km,widen_factor}
    forecast.abstain.min_confidence.{district,cell,location}  forecast.stale_residual_mass
    forecast.novelty_threshold  forecast.novel_confidence_cap  forecast.timing.{n0,n_min}
    interception.{speed_kmh.{urban,semi_urban,rural},road_factor,thresholds.{interceptable,marginal},
      targets,min_confidence_for_action,ladder[]}
    lien.{expiry_hours,review_hours}
    alerting.{floor_confidence,severity_bands,budget_per_shift,shift_hours,exploration_share,
      escalate_after_min,expire_grace_min,refresh_min,dedup_window_min,review_queue.size,
      delivery.{max_attempts,backoff_s},sms.max_segments}
    outcome.grace_hours
    heatmap.{k_threshold,potential_lookback_hours,decay_half_life_hours,amount_bands[],
      confidence_bands[]}
    access.permissions.<role>[]   feedback.label_rate
  USED BY: forecast, interception, alerting, analytics, access, evaluation.

LOCKED CONTRACT: LC-8 Simulator control API (Demo Console)
  DEFINITION: as written in the M1 entry (start, pause, resume, speed 1..60, reset, inject-cluster,
    status). Reached only through the proxy path /sim-control/* after forward_auth.
  USED BY: web feature demo, world-sim, proxy configuration.

LOCKED CONTRACT: LC-9 Ports (Python protocols)
  DEFINITION:
    Clock.now() -> SimTime
    UnitOfWork: __enter__/__exit__, commit(), rollback()      (repositories obtain the active session
                                                               from it; never commit themselves)
    LocationScorer: fit(train) -> ScorerInfo; raw_scores(rows) -> ndarray
    TimingModel: fit(delays_by_type); horizon_probs(ctx, elapsed_min, horizons) -> TimingForecast
    TravelTimeEstimator: eta_min(unit, lat, lon, area_type) -> float
    NotificationChannel: send(msg: OutboundMessage) -> DeliveryResult
    FileStore: save(name, data: bytes) -> FileRef(sha256, size); open(ref) -> bytes
    Repositories: every read method used by forecasting has a required `as_of` parameter.
  USED BY: forecast, interception, alerting, casework, evaluation (baselines implement LocationScorer).

LOCKED CONTRACT: LC-10 Table ownership
  DEFINITION: geo: regions, banks, locations, cells, units | intake: accounts, complaints, fund_hops,
    cashout_observations, ingest_batches | graph: clusters, cluster_members, cluster_location_stats |
    forecast: forecasts, model_versions | interception: intercept_assessments | alerting: alerts,
    deliveries, actions, outcomes | casework: cases, evidence_packs | access: users |
    audit: audit_entries | analytics: heat_rollups, metric_snapshots | evaluation: experiment_runs,
    experiment_metrics. No module reads or writes another module's tables.
  USED BY: every API track (enforced by import-linter and review).
```

**Contract Change Process** *(for when a locked contract turns out to be wrong mid-build)*
1. The track that needs the change proposes the new definition and states which other tracks it affects (from `USED BY`).
2. Every affected track's owner is notified before the change lands, not after.
3. The contract's `DEFINITION` is updated in this document, and this update is itself a Sync Point (DOC 4 §4.1a) gating any track whose work depends on it.
Additions (a new enum member, a new optional field, a new event) may proceed with notice; removals, renames and type changes always follow the full process.
