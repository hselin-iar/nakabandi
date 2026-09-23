# TRACK B — Algorithms & Simulator
OWNER:            Algo dev + coding agent
CURRENT_STEP:     B4 — Forecast v0
LAST_COMPLETED:   B3 — Interception Domain
STATUS:           ACTIVE
PAUSED_AT:        none
NEXT SYNC POINT:  SYNC 2 — after B1 (golden generator) and A3 (intake); gates B2-B4 (DOC4 §4.1a)

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
