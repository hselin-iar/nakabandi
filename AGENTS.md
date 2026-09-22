# AGENTS — NAKABANDI

Team build, five tracks (A, B, C, D, R). Routing only: load order, states, triggers, rules. Project knowledge
lives in DOC1–DOC4. Spec files sit at the repo root beside this file: DOC1.md … DOC4.md, vibe-antipatterns.md,
prompt-patterns.md.

YOUR TRACK: the human tells you at session start (for example "Track B"). If they didn't, ask once. Never guess.
Escalate to your track's OWNER. Cross-track, contract or merge questions go to the Integration Owner (Systems lead).
Only the Integration Owner edits this file and DOC1–DOC4; everyone else reads them from main.

## Session State

Status lives in each track's own file, so parallel branches never collide. You write only your own.

| TRACK | OWNER | STATE FILE |
|-------|-------|------------|
| A — Platform & Integration | Systems lead + coding agent (Integration Owner) | docs/state/track-a.md |
| B — Algorithms & Simulator | Algo dev + coding agent | docs/state/track-b.md |
| C — Web & Bank Simulator | Web dev + coding agent | docs/state/track-c.md |
| D — Design, Content & Data Curation | Designer (human) | docs/state/track-d.md |
| R — Research Agent Tasks | Research agent, run by the Designer | docs/state/track-r.md |

A state file holds CURRENT_STEP, LAST_COMPLETED, STATUS (ACTIVE | RESUMING | BLOCKED | CHECKPOINT), PAUSED_AT,
NEXT SYNC POINT and that track's Learnings. Update it after every completed step and before ending a session.
Board for the Integration Owner: `git fetch --all`, then `git show origin/feat/track-b:docs/state/track-b.md`
(same for a, c, d; track-r lives on feat/track-d). main shows only what has been merged.

## Load Order (follow exactly — do not load speculatively)

```
HOW TO LOAD ONLY A SECTION (not the whole file):
  Every DOC opens with a Table of Contents. To read one section: check that DOC's ToC for
  the exact heading text, search the file for that exact string, then read from that
  heading down to the next heading only. Never open the full file when a ToC entry names
  the section you need.

SESSION START:
  1. Read AGENTS.md fully (this file only)
  2. Read your state file (merge main into your branch first if a Merge Point, DOC4 §4.1b, was announced);
     skim the Learnings Log below and your state file's Learnings
  3. Check STATUS in your state file:
       RESUMING   → RESUMING protocol in States
       BLOCKED    → re-read the BLOCKED entry; if it says "waiting on research", see Research Handoff
       CHECKPOINT → CHECKPOINT protocol in States
       ACTIVE     → continue to step 4
  4. DOC4.md ToC → find your CURRENT_STEP entry ("Step A1 — …") → read only that section
  5. Follow its Reference line into DOC2/DOC3 → check each DOC's ToC → read only the named section
  6. Begin work

NEW STEP:
  1. Update your state file
  2. Append anything learned on the finished step to your state file's Learnings before moving on
  3. DOC4.md ToC → read only the next step's section
  4. Follow reference pointers via their DOCs' ToCs
  5. Begin

WHEN SOMETHING IS UNCLEAR:
  Feature intent or user behaviour   → DOC1.md ToC → the one feature entry (§1.2), or §1.5 for ethics
  Architecture or stack decision     → DOC2.md ToC → relevant section only
  Module structure or interface      → DOC3.md ToC → relevant feature section or Locked Shared Contracts
  Build order, done condition        → DOC4.md ToC → your current step entry only
  Path ownership / when to sync      → DOC4.md §4.1b / §4.1a

NEVER load a whole document when its ToC names the section you need.
NEVER read DOC1 in full during a build session; DOC4 is ~2,000 lines, so read your step entry only.
NEVER pre-load the next step before the current one is done.
NEVER load vibe-antipatterns.md or prompt-patterns.md speculatively; only when Triggers says to.
```

## States

Every state applies per track. Track A can be BLOCKED while Track B is ACTIVE. Tracks D and R (human,
research agent) use the same states and the same Done When / Evidence required.

```
### ACTIVE
Working on CURRENT_STEP. Stay here until Done When is satisfied.
  ✓ Work only on the current step; follow its "Folder/file targets" and "Agent prompt hint" exactly
  ✓ Follow the Agentic Coding Rules below at all times
  ✓ Stay inside your track's Ownership Map (DOC4 §4.1b); work on your track's branch
  ✓ Use stubs/fixtures only where the step's STUB/MOCK STRATEGY names them; swap at the named Sync Point
  ✗ Do not touch code outside the step's scope, or load more context than its Reference line names
  ✗ Do not ask questions the DOCs answer
  ✗ Do not do heavy research yourself; use the Research Handoff (quick lookups are fine)

  → CHECKPOINT if Done When holds and a Checkpoint (DOC4 §4.3) or Sync Point (DOC4 §4.1a) follows
  → BLOCKED if you cannot finish without information you don't have
  → ACTIVE (next step) if Done When holds, `npm run ci` is green, the step's
    "Evidence required" is produced, and no Checkpoint or Sync Point follows

### CHECKPOINT
Verification gate. Do not continue until it passes.
  1. Read the Checkpoint entry in DOC4 §4.3 (or the Sync Point entry in §4.1a); run the exact verification
  2. Report to your track owner: what you tested, what happened
  3. Wait for confirmation (Sync Points: the "Who confirms it" people named in §4.1a)
  → ACTIVE if confirmed   → BLOCKED if it fails

### BLOCKED
Cannot proceed. Something is missing, broken, or needs a human decision.
  1. Set STATUS to BLOCKED in your state file
  2. State what you were trying to do (one sentence)
  3. State what is blocking you (paste the error or quote the ambiguity)
  4. State which doc section you checked and what it said
  5. State what you need from your track owner (or the Integration Owner) to unblock
  6. Check Triggers; if there is an entry for this situation, follow its pointer
  7. Wait. Do not attempt workarounds.
  → ACTIVE when the missing information is provided and confirmed

### RESUMING
Picking up after a session break.
  1. Read LAST_COMPLETED; go to that step in DOC4 and verify its Done When holds in the codebase
  2. Verified → set CURRENT_STEP to the next step, STATUS: ACTIVE; not complete → tell your track owner what
     is incomplete and ask whether to finish or move on
  3. Tell your track owner in one sentence: what is done, what is next
  4. Do not assume prior work is correct. Verify before trusting.
  → ACTIVE once the prior step is verified
```

## Research Handoff (heavy research only)

Quick lookups are yours to do: debugging an error, official docs for anything in DOC2 §2.2, an API signature,
syntax or version compatibility, "how do I do X in library Y". Keep them short and targeted; one that hasn't
cracked a bug after ~3 tries is the "stuck 3+ attempts" trigger, not a research task.
Hand off HEAVY research: work that compares or cross-checks several sources (datasets, libraries, approaches,
pricing, hosting), is open-ended ("what exists", "which is better"), or whose answer a decision, licence
obligation or public claim rests on (licence terms, statistics, statute text, dataset provenance). When in doubt,
hand off. A lookup never overrides a DOC: a library outside DOC2 §2.2, or a contradiction with a DOC, is a trigger.
Steps R1–R4 already carry their own prompts in DOC4; use those.

```
1. Set STATUS: BLOCKED; PAUSED_AT: "waiting on research: <slug>".
2. Output ONE self-contained prompt in a code block for the human. The research agent cannot see this repo, so
   the prompt must carry everything:
     CONTEXT:   what NAKABANDI is (2 lines), which step you are on, why this fact blocks it, what you will do
                with the answer
     QUESTIONS: numbered; each answerable with a fact plus a source; include scope limits (four demo states,
                India, redistributable licences only, and so on) when they apply
     SOURCES:   prefer primary sources (statute text, official docs, PIB/MHA, licence files, the dataset's own
                page); avoid forums and SEO blogs unless nothing else exists
     REPORT:    per finding: exact URL, publisher, publication or last-updated date, the relevant figure or
                wording (short verbatim quote where exact wording matters, e.g. licence or statute text);
                mark each VERIFIED (read on the source itself) or UNVERIFIED; flag conflicts; write
                "not found" rather than guessing
     FORMAT:    Markdown, findings first, then a five-line summary, then "What I could not confirm"
     SAVE AS:   docs/research/<slug>.md
3. Tell the human: paste the prompt into the research agent, save the result at docs/research/<slug>.md, tell
   you when it is saved. Then stop and wait. No workarounds, no assumptions.
4. When told it is saved: read only that file; check every question is answered and marked; set STATUS: ACTIVE;
   continue. Treat UNVERIFIED findings as assumptions and record them in Learnings.
5. If the findings contradict a DOC, do not deviate silently: follow the "Two docs seem to conflict" trigger.
```

## Triggers

Read a row only when its situation occurs, never speculatively.

```
When you notice...                                   → Read this immediately

You import sqlalchemy/fastapi/httpx/os/requests in     → vibe-antipatterns.md AP-06
  any `domain/`; put SQL or `commit()` in a router or     then prompt-patterns.md PP-07
  domain; import `other_module.domain` or `.infrastructure`
  instead of its `__init__.py`; or import-linter /
  eslint-boundaries fails and you want to silence it

You reach for Next.js, Redux, MUI/Chakra, Leaflet/     → vibe-antipatterns.md AP-07
  Mapbox, Django/Flask, PostgreSQL/Mongo, Celery/          then prompt-patterns.md PP-09
  Redis/Kafka/APScheduler, WebSockets, PyTorch/GNNs,
  Poetry, a Makefile, or any lib not in DOC2 §2.2

You add an enum member, field, event, endpoint shape,  → vibe-antipatterns.md AP-08, AP-09
  table column or policy key that is not in DOC3           then prompt-patterns.md PP-08
  LC-1…LC-10 or DOC2 §2.3

You type a threshold, weight, cap, speed or URL into   → vibe-antipatterns.md AP-10
  code, or call `datetime.now()` / `time.time()`           then prompt-patterns.md PP-07
  outside SystemClock (target: config/policy.yaml,         (name the destination file)
  config/sim.default.yaml, or the injected Clock)

You build beyond the step's "What to build": a v1     → vibe-antipatterns.md AP-01
  upgrade before v0 is green, an S1–S5 / C1–C4 feature,    then prompt-patterns.md PP-04
  UI polish in a backend step, a live endpoint in a
  stub-strategy step

You say "done" without running Done When and           → vibe-antipatterns.md AP-14
  producing "Evidence required", or `npm run ci` is red    then prompt-patterns.md PP-20

You start the next step past an unconfirmed            → vibe-antipatterns.md AP-22
  Checkpoint (§4.3) or Sync Point (§4.1a)                  then prompt-patterns.md PP-15

A fresh session re-derives something already decided,  → vibe-antipatterns.md AP-11
  or you are about to redo a rejected approach             then prompt-patterns.md PP-01;
                                                           check the Learnings first

You need heavy research (several sources; licence,     → Research Handoff above; hand it off. Quick
  statute or statistics; dataset or library comparison)    lookups and debugging searches stay with you

Session about to end / context filling                 → prompt-patterns.md PP-14
Resuming after any break                               → prompt-patterns.md PP-02
Agent stuck after 3+ attempts on the same problem      → vibe-antipatterns.md AP-13,
                                                           then prompt-patterns.md PP-13
Two docs seem to conflict                              → prompt-patterns.md PP-17
Several steps done since DOC 2/3 was last checked      → compare DOC 3's module structure to the actual
  against the code                                         layout; drift is a deliberate DOC 3 update (Contract
                                                           Change Process if a locked contract is involved),
                                                           never a silent divergence
Session completely off track                           → prompt-patterns.md PP-18

Team projects (fixed rows):
A track reaches a Sync Point (DOC4 §4.1a)              → stop; do not let the gated track start; confirm the "what
                                                           must be confirmed" line, update your state file, proceed
About to touch a Shared Surface (DOC4 §4.1b)           → check MERGE POINTS in §4.1b first; coordinate with the
                                                           other track's owner
About to edit a path outside your track's              → stop; check Shared Surfaces or ask the owning track
  Ownership Map entry (DOC4 §4.1b)
A locked contract needs to change (DOC3 LC-1…LC-10)    → do not edit it; follow the Contract Change Process in
                                                           DOC3 and DOC4 §4.1b exactly
Descope condition (DOC4 §4.1c) appears true            → re-read §4.1c, apply the cut order exactly, tell your
                                                           track owner and the Integration Owner what was cut
A research-agent step's output has landed              → verify it matches "CONSUMED BY" in the R-step (DOC4
  (docs/research/…)                                        §4.1) before the dependent track starts
```

## Agentic Coding Rules

Compiled from DOC4 §4.2, DOC2 §2.1 / §2.5 / §2.6 / §2.7, and DOC3 Locked Shared Contracts.

```
ALWAYS:
  - Record progress only in your own state file (docs/state/track-x.md), after every step.
  - Keep dependencies pointing inward, interfaces → application → domain, in every API module under
    apps/api/src/nakabandi/; domain code is pure Python/numpy: no I/O, FastAPI, SQLAlchemy, httpx, os, wall clock.
  - Import another module only through its `__init__.py` facade; touch only your own module's tables (DOC3 LC-10).
  - Give every forecasting read and repository method a required `as_of` (never a default); read time only
    through the injected Clock; money is integer `*_paise`, times are `event_at` / `observed_at`, ids are ULIDs
    from `new_id()` (DOC3 LC-2).
  - Put every threshold, weight, cap and speed in config/policy.yaml (Track A fills) or config/sim.default.yaml
    (Track B fills); key names are frozen in DOC3 LC-7.
  - Require an authenticated `Principal` for any use case with an effect on a third party (RecordAction,
    MarkOutcome, anything that sends a webhook, SMS or email).
  - After any API shape change run `npm run types` and commit apps/web's schema.d.ts; run `npm run ci`
    before claiming a step done.
  - Commit on your track's branch (feat/track-a … feat/track-d); Track A and B agent sessions each use their own
    git worktree; title commits like `feat(track-b): step 4 — forecast v0` (DOC4 §4.1b).

NEVER:
  - Do heavy research yourself (multi-source, or facts a decision, licence or claim rests on); use the Research Handoff.
  - Edit AGENTS.md, DOC1–DOC4, vibe-antipatterns.md or prompt-patterns.md (Integration Owner only), or another
    track's state file; ask the Integration Owner instead.
  - Bypass `pipeline`: only `pipeline` and `main.py` call several module facades in sequence; no module imports `pipeline`.
  - Import the oracle client outside `evaluation`, or import `evaluation` from `main.py` (hidden-truth firewall,
    DOC2 §2.1 invariant 1). The API process never touches world.db.
  - Construct a `LienProposal` with `proposed > disputed`, without an expiry, or without a complaint anchor;
    there is no whole-account-freeze value anywhere in the domain.
  - Add an enum member, event field or endpoint shape beyond DOC3 LC-1…LC-10, even if it looks obviously useful;
    raise it through the Contract Change Process (DOC4 §4.1b).
  - Let a web feature import another feature (only `shared/*`, eslint-plugin-boundaries enforces it), or
    hand-edit the generated client.
  - Write a case brief, evidence-pack certificate or alert copy that asserts guilt, names a real person, or claims
    legal compliance (DOC1 §1.5 is binding, not wording guidance).
  - Leave a stub, fixture or hard-coded value on a MUST path past its swap point; nothing on our side is mocked
    (DOC1 §1.0). Only the two external simulators are simulated, through real contracts.
  - Add a CDN, online tile source, telemetry or any runtime dependency that needs the network; the offline
    Compose path must run (DOC2 §2.7).
```

## Quick Reference

```
DOC1.md              → Features M1 Scenario Simulator, M2 Predictive Engine, M3 Risk Heatmap Dashboard, M4 Alert &
                       Notification System, M5 Law Enforcement Interface, M6 Interceptability Planner & Ladder;
                       SHOULD S1–S5, COULD C1–C4; §1.5 ethics guardrails
DOC2.md              → Stack: React 18 + TS + Vite / FastAPI + Pydantic v2 + SQLAlchemy 2 on SQLite (WAL) / world-sim
                       (Python) + bank-sim (Node 24 LTS + Express) / Docker Compose + Caddy; modular monolith
DOC3.md              → Modules: shared, geo, intake, graph, forecast, interception, alerting, casework, access, audit,
                       analytics, evaluation, pipeline; apps/world-sim; apps/bank-sim; web features alerts/map/
                       clusters/cases/evaluation/ops/demo; Locked Contracts LC-1…LC-10
DOC4.md              → 5 tracks, 41 steps: A Platform & Integration (A1–A12) / B Algorithms & Simulator (B1–B9) /
                       C Web & Bank Simulator (C1–C9) / D Design, Content & Data Curation (D1–D7) / R Research
                       Agent Tasks (R1–R4); Sync Points 1–8, Checkpoints 1–8
docs/state/          → One state file per track (see Session State)
docs/research/       → Research Handoff outputs, one file per task
vibe-antipatterns.md → Load only via Triggers above
prompt-patterns.md   → Load only via Triggers above
AGENTS.md            → You are here.

Progress: your state file, then DOC4.md ToC → your CURRENT_STEP entry   Unclear: the relevant DOC's ToC, one section
Stuck:    STATUS: BLOCKED in your state file, follow the protocol, check Triggers
Ending:   update your state file, note PAUSED_AT, tell your track owner, stop cleanly
```

## Learnings Log

Cross-track learnings only, appended by the Integration Owner (per-track ones go in your state file).
One line each: `[Track/Step] — what was found`. Architecture corrections go through the Contract Change Process.

[A1→B7] — evaluation/oracle_client.py has no import-linter contract yet; when B7 creates it, add a contract so only `evaluation` may import it (Integration Owner edits .importlinter).
[A1] — four-machine evidence waived as a gate for Track A because teammates had not yet accepted invites; each teammate must pass their own npm run ci before their first step.
