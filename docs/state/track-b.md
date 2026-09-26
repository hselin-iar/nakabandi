# TRACK B — Algorithms & Simulator
OWNER:            Algo dev + coding agent
CURRENT_STEP:     POST-B9 model improvements (P0-P5 applied, retrained, evaluated)
LAST_COMPLETED:   P5 — priority sort, same_bank, class_weight, NaN recency, expected_hour
STATUS:           ACTIVE
PAUSED_AT:        none
NEXT SYNC POINT:  SYNC 8 — after B7 (evaluation harness) and A9; gates final analytics (DOC4 §4.1a)

STATUS is one of ACTIVE | RESUMING | BLOCKED | CHECKPOINT. Only this track's owner (and its agent) edits this file.
Update it after every completed step and before ending a session.

## Learnings
One line per entry, newest last: [Step] — what was found (a gotcha, a rejected approach and why, a decision not in the docs).
[B-onboarding] — machine confirmed green: node v24.18.0, uv 0.12.17, python 3.11.9 (venv), npm 11.16.0; npm run ci passed (17 import-linter contracts kept, 14 pytest passed, vite build OK). uv.exe placed at C:\Users\luffy\.local\bin and added to user PATH permanently.
[B1] — Pydantic v2 classmethod on BaseModel is shadowed if a field has the same name; renamed SimConfig.load() → SimConfig.from_yaml() to avoid collision with the `load: LoadConfig` field.
[B1] — rng_for() XOR-chaining produced hash collisions for short name pairs ("a","b"); replaced with SHA-256 of the full "seed=N|0=name0|1=name1" path — collision-resistant and order-sensitive by construction.
[B1] — LC-1 ComplaintBatch has maxItems: 500; a single day at 600 complaints/day exceeded the cap. Fixed by chunking into ≤500-item batches in cli._stream_events and the golden test runner.
[B1] — SimTime in nakabandi_contracts is Annotated[datetime, AfterValidator]; pass datetime objects not ISO strings. RegistryLocation/RegistryUnit are typed models, not raw dicts.
[B1] — Golden stream hash (seed=42, 3 days, 6 clusters, ~600/day): 9a4ecbd8b11a2bd7afaff7c91f768864c51201d3766674ab2c41899fd051148b — identical across two runs; stored in commit 1f64da6.
[B2] — import-linter "other modules use shared only through its facade" forbids nakabandi.shared.** (sub-modules); all graph/geo imports must use nakabandi.shared (the facade). Added ClusterMerged/ClusterUpdated to shared/__init__.py re-exports to make them available through the facade.
[B2] — DisjointSet tie-break: lex-smaller id survives on equal size. Since fresh ULIDs start with '01…' and old hand-written test ids like 'CLU-X' start with 'C', the ULID wins (lex smaller). Test must assert "all in same cluster" not "surviving_id == 'CLU-X'".
[B3] — interception_probability(0, timing) = 1.0, not residual_mass. F_cond(0)=0 by definition (conditional CDF starts at 0), so P(intercept | eta=0) = 1-0 = 1. residual_mass is only a shortcut for negative eta (guard for bad input).
[B3] — LienProposal.__post_init__ with **kwargs confuses pyright on frozen dataclasses — pyright cannot narrow dict[str,Any] to specific field types. Replace _valid(**overrides) test helper with explicit per-test construction.
[B4] — ruff B027: an ABC method with only a pass body but no @abstractmethod fires B027. Suppress with # noqa: B027 when the method is intentionally a no-op default (fit() on LocationScorer).
[B4] — normalise() uses softmax, not simple sum-normalise. This is important: raw heuristic scores can be negative, so dividing by the sum would fail. Softmax maps arbitrary reals to (0,1) safely.
[B4] — MixtureTimingModel.fit EM initialises by splitting at the log-delay median. Must guard against empty sub-partitions (all samples above or below split) and std=0 (use max(std, 0.05)).
[B4/MP3] — Sync 3 confirmed by Systems Lead; real facades (graph, forecast, interception) verified against golden pipeline test (297/297 green, 18 contracts); merged feat/track-a into feat/track-b cleanly (no conflicts, 84 files, 5127 insertions).
[B5] — control_api module-level state (_runner, _world, _clock) must be set by the CLI before uvicorn starts; set_runner() / set_store() are the injection points. FastAPI TestClient shares the same module-level globals, so fixture order matters.
[B5] — _frac_day_to_iso in batches.py is an alias for frac_day_to_dt which returns datetime, not str; batch functions (to_complaint_batch etc.) take datetime for sim_time.
[B5] — District.lat/lon (not centre_lat/centre_lon); Registry.districts is list[District] not dict — use next() linear scan.
[B5] — TruthStore.save_cluster uses OR IGNORE prefix (idempotent on re-injection of same cluster_id). truth_store.py noqa: TID251 on datetime.now() calls — world-sim has no injected Clock, it IS the clock boundary.
[B5] — TimingConfig validates mixture weights sum to 1.0; test fixture needs both fast+slow components summing to 1.0.

## B5 — Done When Evidence (DOC4)
- [x] L1 LiveRunner.pause() → PAUSED; resume() → RUNNING; speed clamp [1,60] tested
- [x] L2 inject_cluster while paused: appends to world.clusters; truth_store record verified
- [x] L3 TruthStore: begin_run/save_complaints/save_cashouts/get_complaint_truth/get_cashouts_in_range/save_cluster/get_clusters all round-trip
- [x] L4 Control API /control/status returns correct shape (state, sim_time, speed, seed, scenario, counts, last_error)
- [x] L5 Control API /control/speed rejects factor<1 and >60 (422)
- [x] L6 Control API /control/inject-cluster returns 409 when IDLE
- [x] L7 guided_demo_script() ascending elapsed_h; history_warmup/inject_cluster/outcome kinds present
- [x] L8 ClockState shared: speed mutation visible to /control/status
- [x] L9 TruthStore.reset() wipes all tables
- [x] L10 Oracle API /oracle/complaints/{ref}/truth returns 404 for unknown ref
- [x] `npm run ci` green — 323/323 passed, 18 contracts kept, 0 pyright errors
- [x] Committed on feat/track-b at 3d17f51; pushed to origin

- [x] Probabilities sum to 1 ± 1e-6 at every level — asserted in GenerateForecast + 3 test cases (F10)
- [x] Cell probability equals sum of its location probs — tested exactly (F3)
- [x] Abstention monotone in threshold (F4)
- [x] Leakage test: features derived purely from ctx; future data in ctx changes features (F8)
- [x] BLOCKLIST: no registry name in BLOCKLIST; all 13 FEATURE_REGISTRY names present (F1)
- [x] MixtureTimingModel.fit recovers a known mixture within tolerance (F7)
- [x] Conditional probs monotone non-decreasing in horizon (F5)
- [x] generate_candidates never exceeds policy.max; deduplicates; sorted by dist (F9)
- [x] `npm run ci` green — 189/189 passed, 18 contracts kept, 0 pyright errors
- [x] Committed on feat/track-b at a4c2f56; pushed to origin

## B3 — Done When Evidence (DOC4)
- [x] LienProposal invariants: 11 tests — proposed>0, proposed<=disputed, expires>review, non-empty ids, no freeze field (P1-P3)
- [x] Ladder exhaustive: all Channel×Verdict pairs return a defined LadderLevel (P4); confidence gate returns NONE
- [x] ETA monotone: larger distance → larger ETA; area_type ordering urban>semi_urban>rural (P5)
- [x] Probability monotone non-increasing in ETA across 7 breakpoints; in [0,1] at all points (P6)
- [x] No-units case: UnitIndex.build([]) raises ValueError (P7)
- [x] build_lien total-cap: remaining enforced, untraceable account → None, expiry from policy (P8)
- [x] verdict_from boundaries: at and around threshold values (P9)
- [x] `npm run ci` green — 157/157 passed, 18 contracts kept, 0 pyright errors
- [x] Committed on feat/track-b at fb38b07; pushed to origin

## B1 — Done When Evidence (DOC4)
- [x] `worldsim hash --seed 42 --days 3` printed same sha256 twice
  → 9a4ecbd8b11a2bd7afaff7c91f768864c51201d3766674ab2c41899fd051148b (both runs)
- [x] `npm run ci` green — 85/85 passed, 18 contracts kept, 0 pyright errors
- [x] All 6 property tests pass (sort, observe invariant, determinism, seed independence, cashout-after-complaint, positive amounts)
- [x] All 13 unit tests pass (rng, timing, config, caps)
- [x] Golden test: every emitted batch validates against its LC-1 Pydantic schema
- [x] Committed on feat/track-b at 1f64da6; pushed to origin

## B2 — Done When Evidence (DOC4)
- [x] DisjointSet property tests: 16 tests — commutative (P1), idempotent (P2), find stable (P3), one-component (P4), size accurate (P5), MergeResult on disjoint (P6), None on same (P7), lex tie-break (P8), bridge accounts (P9)
- [x] Accounts sharing a truth cluster in golden stream resolve to one cluster (test_golden_stream_bridge_accounts)
- [x] Leakage test passes: future observation does not change context_for result (test_future_stat_excluded_by_as_of)
- [x] cell_id_for round-trips: same inputs → same id; adjacent cells → different ids (7 tests)
- [x] compute_footprint: centroid within bounding box; weighted; top-N ordered (6 tests)
- [x] `npm run ci` green — 123/123 passed, 18 contracts kept, 0 pyright errors
- [x] Committed on feat/track-b at a3c264b; pushed to origin

## B6 Done When Evidence
- [x] T1 — 500 complaints × 5 candidates trained in < 30s (actual: ~2s); 7-day world well within 5-min gate
- [x] T2 — EM recovers planted 70/30 fast/slow mixture within ±0.15 weight tolerance
- [x] T3 — Leakage: future observed_at > as_of not visible in PointInTimeStats snapshot
- [x] T4 — Calibration: brier_after ≤ brier_before; reliability curve (fraction_of_positives, mean_predicted_value) produced
- [x] T5 — Missing model files → load_scorer() returns None → GenerateForecast._using_fallback=True → model_versions.scorer='fallback' (banner)
- [x] T6 — PointInTimeStats.snapshot_at enforces strict as-of boundary (5 tests)
- [x] T7 — TrainingSetBuilder: time-ordered split; data_hash deterministic (4 tests)
- [x] T8 — features_to_array: shape (n,13), float64, channel label-encoded (3 tests)
- [x] T9 — novelty(0, p) == 1.0; novelty(1000, p) < 0.01; monotone decreasing
- [x] T10 — DistrictPrior: Laplace-smoothed weights sum to 1; top_districts ordered; unknown → 0
- [x] 354/354 pytest passed, 18/18 import-linter contracts KEPT, 0 pyright errors
- [x] Committed feat/track-b at 6fb9520; pushed to origin

[B6] — application layer must never import infrastructure directly; injected via ModelStorePort (ABC) — ModelStore(ModelStorePort) satisfies the contract; TrainModels receives ModelStorePort.
[B6] — novelty() is a forecast-domain concern, not a graph-domain concern; placed in forecast/domain/novelty.py to avoid facade-forecast contract violation.
[B6] — scikit-learn and joblib were not in the venv; added via `uv add scikit-learn joblib` (sklearn 1.9.1, joblib 1.6.0).
[B6] — `FeatureRow(**dict[str, Any])` fails pyright type-checking; construct with explicit field references float(d["key"]) instead.

## B7 Done When Evidence
- [x] T1 — every metric matches hand-computed fixture (raw formula checks pass)
- [x] T2 — expand_grid: 3 timing × 3 mixes × 2 localities = 18 configs; sweep_key format verified
- [x] T3 — abstained items: empty truth excluded from precision; counted in abstention_rate
- [x] T4 — n < 30 guard: hit_rate_at_k / brier_score / precision_at_k return NaN when n < 30
- [x] T5 — ExperimentConfig.config_hash() is deterministic; oracle_url excluded from hash
- [x] T6 — MetricRow defaults correct; ExperimentResult.rows accumulates rows
- [x] T7 — HotspotBaseline ranks by frequency; NearestToVictim ranks closer first; BankFootprint by network
- [x] T8 — reliability_curve: non-empty BinStat list from calibrated probs; perfectly calibrated = frac=0
- [x] T9 — dispatches_per_interception and false_hold_rate correct (NaN guarded at n<30)
- [x] T10 — to_json: NaN → null; to_markdown: contains run_id, table rows
- [x] 390/390 pytest passed, 19/19 import-linter contracts KEPT (new oracle-firewall contract added), 0 pyright errors
- [x] Committed feat/track-b at 5577eca; pushed to origin

[B7] — cross-track learning [A1→B7] implemented: oracle_client contract added to .importlinter as Row 8; only nakabandi.evaluation may import oracle_client; now 19 contracts total.
[B7] — evaluation must not import nakabandi.pipeline (existing 'no module imports pipeline' contract); _build_pipeline returns None stub; real wiring injected from main.py at compose time.
[B7] — evaluation must not import nakabandi.intake.infrastructure (facade contract); _bootstrap_tables creates only eval tables; intake tables are created by main.py before passing the DB to evaluation.
[B7] — _generate_world_headless() returns [] stub (compose stack not yet wired); run_experiment() short-circuits to ok/empty-rows when both batches are empty — harness tested structurally without a running world-sim.

## B8 Done When Evidence
- [x] T1  — Caps never exceeded: 10,000-sample property test on split_under_caps (ATM channel)
- [x] T2  — Total preserved: 1,000-sample property test, sum(splits)==total_paise
- [x] T3  — Ledger completeness: every leaf key in sim.default.yaml appears once, no dupes
- [x] T4  — Timing components in ledger: all 4 sub-keys per mixture component
- [x] T5  — Geo state weights in ledger: UP, MH, RJ, HR each have a row
- [x] T6  — Channel mix in ledger: ATM, BRANCH, AGENT each have a row
- [x] T7  — compare_to_public never raises (even on 1.0 cpd vs 6600 anchor)
- [x] T8  — MISMATCH when cpd=1 vs anchor=6600; MATCH when cpd=6600
- [x] T9  — NO_ANCHOR status when anchors dict is empty
- [x] T10 — Report Markdown has '# Public Anchor Check Report' header and status column
- [x] T11 — to_dict() structure correct; n_matches + n_mismatches + n_no_anchor == len(items)
- [x] T12 — Ledger JSON valid; 'rows' key present; count matches
- [x] T13 — Ledger Markdown has '# Assumption Ledger' and '| key |' header
- [x] T14 — All tags are in {verified, derived, assumed, swept}
- [x] T15 — Ledger build does not affect World.step RNG (golden hash unchanged)
- [x] 409/409 pytest passed, 19/19 import-linter contracts KEPT, 0 pyright errors
- [x] Committed feat/track-b at 6c4cbcf; pushed to origin

[B8] — SimConfig classmethod is from_yaml(), not load(); always use from_yaml() in worldsim CLI and tests.
[B8] — PowerShell Set-Content adds BOM; prefer ruff format to strip BOM.
[B8] — split_under_caps signature: (total_paise, accounts: list[Account], caps: CapsConfig, channel, rng).
[B8] — Path(__file__).parents[4] needed from apps/world-sim/tests/unit/ to reach repo root.
[B8] — compare_to_public uses +-30pct relative tolerance for amounts/volume and +-0.10 abs for state weights.
[B8] — Core realism features were already wired in B1; B8 adds ledger audit trail only.

## B9 Done When Evidence
- [x] docs/results/sweep_results.md -- full sweep (18 default + 2 feedback + 1 cold-start) with all cells listed
- [x] docs/results/sweep_results.json -- machine-readable JSON with run_ids for all 21 cells
- [x] 21 per-cell detail files (cell_*.md) written to docs/results/
- [x] No failures; all cells reported honestly as STUB (oracle not reachable; correct per stub strategy)
- [x] Failures section explicitly present; n < 30 notice present; no cherry-picking
- [x] 409/409 pytest, 19/19 import-linter, 0 pyright errors; exit 0
- [x] Committed feat/track-b at 6030f81; pushed to origin

[B9] -- run_sweep.py uses sys.path.insert to access nakabandi.evaluation; requires noqa:E402 on path-dependent imports.
[B9] -- ExperimentResult has no .config attribute; zip(configs, results) to pair them; always use (cfg, r) tuples.
[B9] -- Stub strategy: all cells produce status=ok/empty rows when oracle is not reachable; that is correct and expected per B7 stub strategy -- swap when compose stack runs.
[B9] -- Re-run uv run python scripts/sweep/run_sweep.py --out docs/results once docker compose is up to populate real metrics.
[B9] -- Track B is fully complete: B1-B9 all done and green. HEAD: ccd4c8a on origin/feat/track-b.
[CI] -- Root pyproject.toml and uv.lock (scikit-learn, joblib) committed in ccd4c8a and pushed to origin/feat/track-b.
[POST-B9/P0-P5] -- Model improvement session. Changes: bank_id added to Candidate; priority sort (cluster-history/bank-match); same_bank feature fixed; recency_days NaN for unseen (heuristic also guarded); class_weight='balanced' (P1); expected_hour wired from MixtureTimingModel in evaluate.py. categorical_features=[12] deferred — sklearn HGB binning crashes when channel col has only 1 distinct value (single-bank sim). All-NaN column (recency_days for cold-start clusters) also crashes HGB binning — fixed by replacing all-NaN columns with 0.0 before fit(), constant columns get 1e-7 jitter. npm run ci:py → 673/673 passed.
[POST-B9/eval] -- Metrics on 951 complaints (n grew from 226 due to continued sim run): hgb_v1 Hit@1=2.73% Hit@3=5.57% Hit@5=8.41% Brier=0.0065. Heuristic baseline on same 951: Hit@1=0.21% Hit@3=0.73% Hit@5=2.30% Brier=1286 (raw scores, not calibrated). HGB v1 is 3-4× better than heuristic at all k. Absolute numbers lower than old 226-complaint eval because the larger dataset includes more cold-start complaints added by continued sim run.
[POST-B9/baselines] -- Canonical baselines evaluated on 951 complaints: HotspotBaseline (Hit@1=6.52% Hit@3=16.09% Hit@5=24.19% Prec@5=4.92% Brier=0.0062), NearestToVictim (Hit@1=1.58% Hit@3=4.73% Hit@5=6.73% Prec@5=1.43% Brier=0.0064), BankFootprint (Hit@1=1.26% Hit@3=4.42% Hit@5=6.31% Prec@5=1.35% Brier=0.0075), hgb_v2 (Hit@1=2.73% Hit@3=5.57% Hit@5=8.41% Prec@5=1.77% Brier=0.0065). hgb_v2 outperforms NearestToVictim (+25% Hit@5) and BankFootprint (+33% Hit@5), but trails HotspotBaseline because FeatureRow only carries cluster-scoped counts (`cluster_loc_count`), not global ATM fraud density.
[NEXT_ACTION] -- Add as-of global ATM cashout frequency / Bayesian smoothed prior to FeatureRow so HGB captures the strong hotspot base-rate signal while retaining syndicate/bank/distance personalization.


