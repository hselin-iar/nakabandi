# TRACK B — Algorithms & Simulator
OWNER:            Algo dev + coding agent
CURRENT_STEP:     B1 — Simulator v0 Golden Generator
LAST_COMPLETED:   B1 — Simulator v0 Golden Generator
STATUS:           CHECKPOINT
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

## B1 — Done When Evidence (DOC4)
- [x] `worldsim hash --seed 42 --days 3` printed same sha256 twice
  → 9a4ecbd8b11a2bd7afaff7c91f768864c51201d3766674ab2c41899fd051148b (both runs)
- [x] `npm run ci` green — 85/85 passed, 18 contracts kept, 0 pyright errors
- [x] All 6 property tests pass (sort, observe invariant, determinism, seed independence, cashout-after-complaint, positive amounts)
- [x] All 13 unit tests pass (rng, timing, config, caps)
- [x] Golden test: every emitted batch validates against its LC-1 Pydantic schema
- [x] Committed on feat/track-b at 1f64da6; pushed to origin
