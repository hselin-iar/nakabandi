# Vibe-Coding Anti-Patterns Reference

A catalogue of failure modes specific to AI-assisted coding sessions.
These are distinct from general software anti-patterns (covered in `clean-code-and-architecture.md §11`).
These patterns emerge from the specific dynamics of prompting an AI agent to write code over multiple sessions.

Used during CONTROLLER.md generation: the Anti-Drift Rules and Interruption Handling sections
should be written with awareness of whichever of these patterns are most likely given the project's
stack, scope, and build sequence structure.

---

## How to Use This Reference

When generating CONTROLLER.md, scan this list and identify the 4–6 patterns most likely to appear
in this specific project. Embed targeted guards against those specific patterns in:
- CONTROLLER.md §4.2 (Agentic Coding Rules — NEVER list)
- CONTROLLER.md §3 (per-state Do Not instructions)
- CONTROLLER.md §4 (Interruption Handling — add project-specific failure modes)

Do not paste this whole file into CONTROLLER.md. Extract and translate into project-specific rules.

---

## Category 1 — Scope Drift

These patterns all share the same root cause: the agent does more than it was asked to.

---

### AP-01: Feature Creep from Context
**What it looks like:**
The agent reads DOC 1 fully to understand a feature, then starts implementing adjacent features
it noticed while reading — because they "seem related" or "will be needed soon anyway."

**Why it happens:**
The agent optimizes for helpfulness. Seeing a feature list, it tries to be maximally helpful
by building more of it. It has no internal concept of "this session's scope."

**Damage:**
Unverified code accumulates. The build sequence loses meaning. Integration breaks appear
from partially-built features that weren't supposed to exist yet.

**Guard:**
CONTROLLER must restrict context loading to the current build step only.
The agent should never read the full feature list — only the current step's entry.
Add to NEVER list: "Never read DOC 1 in full during a build session. Load only the feature
entry referenced by the current build step."

---

### AP-02: Step Merging
**What it looks like:**
Two build steps are adjacent and related (e.g., "set up auth" followed by "add auth to routes").
The agent merges them into one, implementing both simultaneously.

**Why it happens:**
From the agent's perspective, doing both at once is more efficient. It doesn't respect the
intentional sequencing in DOC 4.

**Damage:**
Done-When verification breaks — the checkpoint was designed for single-step completion.
Bugs become harder to isolate. The build sequence's dependency logic is violated.

**Guard:**
"Complete one build step at a time. Each step has its own Done When condition.
Do not begin the next step until the current one is verified complete."

---

### AP-03: Premature Abstraction
**What it looks like:**
The agent, building a specific feature, notices repetition and immediately extracts a shared
utility, base class, or abstraction — which wasn't in DOC 3.

**Why it happens:**
The agent has internalized DRY and SOLID. It applies them eagerly even when the duplication
is intentional, or when it's too early to know the right abstraction.

**Damage:**
The abstraction is built for patterns that haven't fully emerged yet, creating wrong
generalizations. Other build steps start depending on the new abstraction without knowing it.

**Guard:**
"Do not create shared utilities, base classes, or new abstractions not defined in DOC 3.
If you see repetition that warrants abstraction, note it as [REFACTOR CANDIDATE: ...] in a comment
and continue. Raise it with Nilesh before implementing."

---

### AP-04: Unsolicited Refactoring
**What it looks like:**
The agent is asked to implement Feature B. While reading the file to add to it, it refactors
Feature A's code — renaming things, restructuring functions, "cleaning up" — without being asked.

**Why it happens:**
Clean code instincts. The agent sees code it would write differently and improves it.

**Damage:**
Working code breaks. The refactor introduces bugs. The session is now debugging a change nobody
asked for. Nilesh loses trust in what the agent touched.

**Guard:**
"Do not modify any code not directly required for the current build step.
If existing code needs fixing to complete the step, report what needs changing and why,
then wait for confirmation before touching it."

---

### AP-05: Gold Plating
**What it looks like:**
The agent implements a feature correctly, then adds error messages that are too polished,
loading states that weren't specced, animations, accessibility enhancements, or logging
infrastructure — all in the same step.

**Why it happens:**
The agent has seen production-grade code and tries to meet that standard even on an MVP build.

**Damage:**
Steps take 3× longer. Code becomes harder to verify against Done When conditions.
Scope of each step is unclear. The team wastes time on polish when core functionality isn't done.

**Guard:**
"Build exactly what the current step specifies. No error state UI unless the step says to.
No loading spinners unless specced. No logging infrastructure unless in the build sequence.
Mark polish ideas as [FUTURE IDEA: ...] and continue."

---

## Category 2 — Architecture Drift

The agent builds something that works but violates the architecture defined in DOC 2 and DOC 3.

---

### AP-06: Layer Violation
**What it looks like:**
Business logic appears in a React component. A database query appears in an API route handler
instead of a repository. An API call appears inside a utility function.

**Why it happens:**
The agent takes the shortest path to making something work. It doesn't have a natural concept
of layer boundaries — it just knows how to write code that functions.

**Damage:**
The architecture collapses over time. The codebase becomes impossible to test or modify.
DOC 2's principles are violated in exactly the ways they were designed to prevent.

**Guard:**
State the dependency rules explicitly in CONTROLLER: "Business logic lives in /lib/[feature].
Components render and handle events only. API routes validate, call service functions, return responses.
No DB calls outside /lib/db repositories."

---

### AP-07: Stack Substitution
**What it looks like:**
DOC 2 specifies Supabase for auth. The agent, while building, uses NextAuth instead — because
NextAuth examples are prominent in its training data and it "knows" them better.

**Why it happens:**
The agent defaults to the library it has seen most in training data, especially when implementation
details of the chosen library are slightly harder to recall.

**Damage:**
The project is now on a different stack than planned. Integration with other parts of the system
(which were designed for Supabase auth) breaks.

**Guard:**
Name the exact library and version for every stack decision in DOC 4's Context Snapshot.
Add to NEVER list: "Never substitute a library for an alternative, even one that seems equivalent.
If a chosen library isn't working, set BLOCKED — do not silently switch."

---

### AP-08: Schema Drift
**What it looks like:**
The agent creates a database table or data structure that differs from DOC 2's data model —
renamed fields, different relationships, added columns "for convenience."

**Why it happens:**
The agent writes what makes sense for the immediate code it's writing, without checking the
canonical data model in DOC 2.

**Damage:**
Future build steps that depend on the schema break. Migrations become a mess.
The data model in DOC 2 becomes inaccurate and can't be trusted.

**Guard:**
"Before creating or modifying any database table or type definition, read DOC 2 §2.3 Data Architecture.
Use field names exactly as specified. Do not add columns not in the schema."

---

### AP-09: Interface Invention
**What it looks like:**
Module A needs to call Module B. DOC 3 defines the interface between them.
The agent invents a different interface — different function signature, different return shape —
because it seems cleaner or more convenient for what it's writing right now.

**Why it happens:**
The agent is locally optimizing for the code it's writing, without checking the contract
that other modules will depend on.

**Damage:**
When Module B is built later, it uses the DOC 3 interface. Module A's invented interface is
incompatible. Integration breaks in a way that's hard to trace.

**Guard:**
"All interfaces between modules are defined in DOC 3 for each feature.
Do not invent or modify function signatures for cross-module calls.
If a DOC 3 interface seems wrong, report it — do not silently change it."

---

### AP-10: Config Hardcoding
**What it looks like:**
API URLs, environment-specific values, feature flags, or secrets appear hardcoded in source files
rather than in environment variables.

**Why it happens:**
Fastest path to working code. The agent knows the value and writes it directly.

**Damage:**
Security vulnerability. Deployment breaks when the value needs to change.
Violates 12-Factor App Factor 3 (Config).

**Guard:**
"Never hardcode URLs, API keys, secrets, or environment-specific values.
All config lives in .env files. Reference via process.env.[VAR_NAME].
All required env vars are listed in DOC 4 §4.4 Deployment Checklist."

---

## Category 3 — Context & Memory Failures

Patterns caused by the agent losing track of state, prior decisions, or its current goal.

---

### AP-11: Session Amnesia
**What it looks like:**
A new session starts. The agent begins the project from scratch — re-asking questions, re-explaining
what was already built, sometimes starting to re-implement things that exist.

**Why it happens:**
AI agents have no persistent memory between sessions. Without explicit context loading,
they don't know what was done in a previous session.

**Damage:**
Time wasted. Duplicate code written. Existing working code gets overwritten.

**Guard:**
CONTROLLER.md's RESUMING state handles this. The key rule: at session start, always read
CONTROLLER.md first, find LAST_COMPLETED, verify it in the codebase, then continue from CURRENT_STEP.
"Never assume prior work is complete just because it was marked done. Verify before proceeding."

---

### AP-12: Context Window Bloat
**What it looks like:**
The agent tries to load all four docs, read all existing code files, and hold the entire project
in context simultaneously. As the context window fills, earlier information gets "forgotten"
and output quality degrades. The agent starts contradicting earlier decisions.

**Why it happens:**
Without explicit loading rules, the agent defaults to loading everything it can find.

**Damage:**
Token waste. Output drift as early context gets pushed out. Contradictory code across files.
Session ends prematurely due to context exhaustion.

**Guard:**
CONTROLLER.md's Context Loading Rules — load only the current step. Per-section references.
"Never load a whole document when a section reference points to a specific part.
If you need DOC 2, read the specific section, not the whole file."

---

### AP-13: Goal Displacement
**What it looks like:**
The agent starts working on a build step. Mid-implementation, it encounters a bug in existing code.
It pivots to debugging the existing code — and forgets the original step entirely.
It may spend an entire session fixing something that wasn't the goal.

**Why it happens:**
The agent is problem-oriented. When it sees a problem, it tries to solve it. It doesn't
naturally track "what was I originally doing?"

**Damage:**
Build step not completed. Session wasted. New step introduces more bugs.

**Guard:**
"If you encounter a bug in code outside the current build step, stop.
Report: what you found, where it is, whether it blocks the current step.
Do not fix it unless it directly blocks Done When. Set BLOCKED if it does."

---

### AP-14: Phantom Completion
**What it looks like:**
The agent reports a build step as complete without actually verifying the Done When condition.
It says "Done ✓" after writing the code, before running it or testing it.

**Why it happens:**
The agent conflates "I wrote code that should work" with "this works."
It has no way to run code — unless the setup explicitly includes it.

**Damage:**
Broken code marked complete. The next step builds on a broken foundation.
Checkpoints catch it — but only if they're actually run.

**Guard:**
"A step is not done when the code is written. It is done when the Done When condition
in DOC 4 is satisfied and you have verified this — either by running the code, reading the output,
or asking Nilesh to test the specific interaction. State how you verified it."

---

### AP-15: Contradictory Iteration
**What it looks like:**
Nilesh asks the agent to adjust something. The agent makes the change, but also undoes
or contradicts a decision made two steps ago — because it doesn't have context of why that
earlier decision was made.

**Why it happens:**
Without a decision log, the agent doesn't know which decisions were intentional vs. incidental.
It optimizes locally without understanding the global reasoning.

**Damage:**
Progress regresses. Working features break. The architecture becomes inconsistent.

**Guard:**
DOC 4's Context Snapshot and Agentic Coding Rules serve as the standing decisions.
"Before modifying an existing architectural decision, read DOC 2 §2.2 to understand why it was made.
If a change seems to contradict a prior decision, report the conflict before implementing."

---

## Category 4 — Collaboration Failures

Patterns in how the agent interacts with Nilesh during a session.

---

### AP-16: Silent Assumption
**What it looks like:**
The spec is ambiguous on something. The agent picks an interpretation and builds it without
flagging the ambiguity. Nilesh reviews and discovers the agent built the wrong thing.

**Why it happens:**
The agent optimizes for producing output over asking questions. It guesses rather than pausing.

**Damage:**
Work thrown away. Time lost. Nilesh loses confidence in the agent's output.

**Guard:**
"If a spec is ambiguous — the step could be implemented in two meaningfully different ways —
stop and ask before building. State the two interpretations and ask which is correct.
Never pick one silently."

---

### AP-17: Over-Asking
**What it looks like:**
The inverse of AP-16. The agent asks Nilesh questions that are already answered in the docs.
"What database should I use?" — it's in DOC 2. "Should this be a client or server component?" — it's in DOC 3.

**Why it happens:**
Uncertainty aversion. The agent would rather ask than be wrong.

**Damage:**
Session friction. Nilesh has to re-answer questions from planning. Trust in the docs erodes.

**Guard:**
"Before asking Nilesh a question, check: is this answered in DOC 1, 2, 3, or 4?
If yes, read the relevant section and proceed. Only ask if the answer genuinely isn't there."

---

### AP-18: Verbose Reporting
**What it looks like:**
The agent completes a build step and produces a 500-word summary of everything it did,
every file it touched, every decision it made.

**Why it happens:**
The agent is trained to be thorough and explain its work.

**Damage:**
Nilesh has to read a wall of text to find the one thing that matters: did it work?
Signal-to-noise collapses. Important information gets buried.

**Guard:**
From CONTROLLER.md §5 Anti-Drift Rules: "After completing a build step, report in one sentence
what was built and what the Done When result is. Save detail for BLOCKED states."

---

### AP-19: Approval Seeking on Trivial Decisions
**What it looks like:**
"Should I use `const` or `let` here?" "I used a forEach loop — is that okay?"
"I named this function `handleSubmit` — does that seem right?"

**Why it happens:**
The agent is uncertain and defaults to asking rather than deciding.

**Damage:**
Session grinds to a halt on decisions that don't matter. Nilesh is doing the agent's job.

**Guard:**
"Make all implementation-level decisions independently (naming, loop style, local variable choices)
unless they touch an interface defined in DOC 3 or a decision recorded in DOC 2.
Only ask Nilesh when a decision has architectural significance or isn't covered in the docs."

---

### AP-20: False Confidence on Broken Code
**What it looks like:**
The agent produces code with a type error, a missing import, or a logic bug that should be obvious.
It presents the code confidently with no caveat.

**Why it happens:**
The agent cannot run code. It writes what looks correct based on pattern matching.
It has no feedback signal telling it the code is broken.

**Damage:**
Nilesh runs the code, it breaks immediately, and he has to debug something the agent was confident about.
Time wasted. Trust eroded.

**Guard:**
"After writing code, read it as a reviewer: check imports exist, types match interfaces in DOC 3,
function calls match their signatures. Note any part you are uncertain about with [CHECK: ...].
Never present code as complete without this review pass."

---

## Category 5 — Build Sequence Failures

Patterns specific to following DOC 4's ordered build sequence.

---

### AP-21: Dependency Inversion (Build Order)
**What it looks like:**
The agent builds Step 5 before Step 3 is complete, because Step 5 "seems simpler"
or "can be done in parallel." The build sequence in DOC 4 is treated as a suggestion.

**Why it happens:**
The agent doesn't understand why the sequence is ordered the way it is.
It optimizes for what it can complete, not for what should come first.

**Damage:**
Step 5 may depend on interfaces from Step 3 that don't exist yet.
Integration work multiplies. The dependency logic in DOC 4 is violated.

**Guard:**
"Build steps must be completed in the order listed in DOC 4 §4.1.
The sequence is a dependency graph, not a preference. Do not reorder."

---

### AP-22: Checkpoint Skipping
**What it looks like:**
The agent completes a build step, sees a checkpoint, decides the code is "obviously working,"
and moves to the next step without running the checkpoint verification.

**Why it happens:**
Momentum. The agent wants to keep building. Checkpoints feel like interruptions.

**Damage:**
Integration problems accumulate silently. When discovered, they're across multiple steps
and hard to untangle.

**Guard:**
"Checkpoints are mandatory. Never advance past a checkpoint without completing
the exact verification described in DOC 4 §4.3 and reporting the result to Nilesh."

---

### AP-23: Partial Step Completion
**What it looks like:**
A build step involves three files. The agent implements two of them, decides they're "the hard part,"
and marks the step done — leaving the third file for "next time."

**Why it happens:**
Session length pressure. The agent feels it has made good progress and doesn't want to end on incomplete work.

**Damage:**
The Done When condition isn't actually satisfied. The checkpoint will fail.
The session summary misleads Nilesh about actual progress.

**Guard:**
"A step is either complete (Done When satisfied, all files in Folder/file targets created or modified)
or it is not. There is no partial credit. If a session ends mid-step, update CONTROLLER to CURRENT_STEP
with a note on what remains. Do not mark it done."

---

## Quick Lookup: Most Common Patterns by Project Type

```
Project type                   Watch especially for
─────────────────────────────────────────────────────────────────────
Next.js web app                AP-06 (layer violation), AP-07 (stack sub), AP-03 (premature abstraction)
API-heavy backend              AP-08 (schema drift), AP-09 (interface invention), AP-10 (config hardcoding)
Hackathon / time pressure      AP-01 (feature creep), AP-22 (checkpoint skip), AP-14 (phantom completion)
Multi-session long project     AP-11 (session amnesia), AP-12 (context bloat), AP-15 (contradictory iteration)
AI-powered feature (LLM/ML)    AP-07 (stack sub), AP-05 (gold plating), AP-13 (goal displacement)
Solo developer vibecoding      AP-17 (over-asking), AP-19 (approval seeking), AP-18 (verbose reporting)
```
