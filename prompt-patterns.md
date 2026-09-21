# Prompt Patterns Reference

A library of proven prompt structures for specific situations during vibecoding sessions.
These are not generic prompting tips — they are patterns for the specific dynamics of
multi-session, architecture-guided, AI-assisted development.

Used during CONTROLLER.md generation: draw from these patterns when writing the
Interruption Handling section and any project-specific agent prompt hints in DOC 4 §4.1.
The patterns are tools, not scripts — adapt the wording to fit the project.

---

## How to Use This Reference

Each pattern has:
- **When to use** — the specific situation it's designed for
- **Structure** — the template
- **Why it works** — the mechanism behind it
- **Common mistake** — the wrong version people reach for first

When generating DOC 4 §4.1 Agent Prompt Hints, select the relevant pattern for each build step type.
When generating CONTROLLER.md Interruption Handling, embed the relevant recovery patterns directly.

---

## Part 1 — Session Start Patterns

### PP-01: Clean Session Start
**When to use:** Beginning a fresh session on an ongoing project.

**Structure:**
```
We are building [project name]. I'll give you the context you need.

Read CONTROLLER.md. Find CURRENT_STEP. Go to DOC4.md and read only that build step's entry.
Follow its reference pointers into DOC2 or DOC3 if specified.

Tell me in one sentence what step you are starting, then begin.
```

**Why it works:**
Forces the agent to load context in the right order rather than asking "what should I work on?"
The one-sentence report confirms it found the right step before work begins.

**Common mistake:**
Starting with "Here's everything about the project: [pasting all four docs]."
This front-loads context the agent doesn't need and will confuse with information it will need later.

---

### PP-02: Resuming After Interruption
**When to use:** Resuming after a broken session, usage limit, or unexpected exit.

**Structure:**
```
We got interrupted. Before doing anything else:
1. Read CONTROLLER.md — find LAST_COMPLETED and CURRENT_STEP
2. Find CURRENT_STEP in DOC4 and verify: does the Done When condition actually hold in the codebase right now?
3. Tell me: what is complete, what is incomplete, and what you're about to do next.

Wait for my confirmation before proceeding.
```

**Why it works:**
Forces verification of prior state before trusting it. Prevents phantom completion (AP-14)
and the assumption that a session-break means the prior step was finished.

**Common mistake:**
"Continue from where we left off." — The agent doesn't know where that is. It will guess,
and guesses at resumption are where the worst drift begins.

---

### PP-03: Context-Constrained Task Start
**When to use:** Beginning a specific build step where you want to prevent the agent loading more than needed.

**Structure:**
```
We are working on Build Step [N]: [Step Name].

Read only this from DOC4: the Build Step [N] entry.
Read only this from DOC3: the [Feature Name] module section.
Do not load anything else.

Your goal: [restate Done When condition from DOC4].
Begin.
```

**Why it works:**
Explicit loading constraints prevent context bloat (AP-12) and feature creep from context (AP-01).
Restating the Done When condition gives the agent a clear success definition before it starts.

**Common mistake:**
Not specifying what not to load. The agent will read everything it can access.

---

## Part 2 — Scope Control Patterns

### PP-04: Hard Scope Boundary
**When to use:** When the agent starts expanding scope within a step.

**Structure:**
```
Stop.

We are only doing [exact build step name] right now.
The Done When condition is: [paste it from DOC4].

Everything else you just mentioned is either a future step or outside scope entirely.
Mark any good ideas as [FUTURE IDEA: ...] in a comment and return to the current step.

What is the next action you'll take toward Done When?
```

**Why it works:**
"Stop" interrupts the momentum. Restating Done When refocuses the target.
Asking for the next action forces the agent to re-engage with the actual goal.

**Common mistake:**
"Please focus on the current step" — too gentle. The agent will acknowledge and continue drifting.
The hard reset needs to be explicit.

---

### PP-05: Future Idea Capture
**When to use:** When the agent identifies a genuinely good idea that's out of scope for now.

**Structure:**
```
Good idea. Add this comment exactly where you thought of it:
// [FUTURE IDEA: {describe the idea in one sentence}]

Now return to [current step]. What's next?
```

**Why it works:**
Validates the idea without losing it. Gives the agent a concrete action (add the comment)
that also serves as closure before refocusing. The comment becomes a trail of good decisions
for post-MVP planning.

**Common mistake:**
Ignoring the idea entirely. The agent will try to implement it anyway or bring it up again later.

---

### PP-06: Scope Negotiation
**When to use:** When you genuinely aren't sure if something belongs in the current step or not.

**Structure:**
```
Before you implement [thing the agent is proposing]:
Tell me which part of the current build step requires it.
Show me the line in DOC4 that covers it.

If it's not there, it's either a future step or we need to update the plan.
Which is it?
```

**Why it works:**
Forces the agent to justify the implementation against the spec. If it can't point to the line,
the thing doesn't belong in this step. This trains both the agent and you to use DOC4 as the authority.

---

## Part 3 — Architecture Enforcement Patterns

### PP-07: Layer Violation Correction
**When to use:** You see business logic in a component, a DB call in a route, or any layer violation.

**Structure:**
```
This code is in the wrong place.

[Describe specifically what it is and where it currently is]

Per DOC2, [this type of logic] belongs in [correct layer / file path].

Move it there. Keep the interface the same. Don't change any other logic.
```

**Why it works:**
Names the principle, cites the authority (DOC2), gives a specific destination, and constrains the scope of the fix.
Without the scope constraint, the agent will often refactor the surrounding code too.

**Common mistake:**
"This doesn't follow clean architecture." — Too abstract. The agent will acknowledge and write
something that still violates the layering in a different way.

---

### PP-08: Interface Contract Enforcement
**When to use:** The agent invents or modifies a cross-module interface not defined in DOC3.

**Structure:**
```
The interface you just wrote for [function/module name] doesn't match DOC3.

Go to DOC3 → [Feature name] section → Interfaces & Contracts.
Use that exact signature. Do not modify it.

If the DOC3 interface doesn't work for what you're building, stop and tell me why —
don't change it unilaterally.
```

**Why it works:**
Makes DOC3 the authority, not the agent's judgment. The conditional at the end creates a
legitimate path for flagging a problem without silently fixing it in a way that breaks other modules.

---

### PP-09: Stack Compliance Check
**When to use:** Before a build step that involves a library or service choice (auth, DB, queues, etc.).

**Structure:**
```
Before you write any code for this step:
Tell me: which library/service will you use for [specific thing]?
Verify it against DOC2 §2.2 Stack Decisions.

If your answer matches DOC2, proceed. If it doesn't, correct it and then proceed.
```

**Why it works:**
Surfaces stack substitution (AP-07) before code is written, not after.
Asking the agent to self-verify is faster than reviewing after the fact.

**Common mistake:**
Not doing this check. The agent will often default to its training data preference.

---

## Part 4 — Unblocking Patterns

### PP-10: Precise BLOCKED Report Request
**When to use:** The agent says it's stuck but gives a vague explanation.

**Structure:**
```
Give me a BLOCKED report. Include exactly:
1. What you were trying to do (one sentence)
2. What specifically is blocking you (error message, missing info, or ambiguous spec — paste it exactly)
3. Which doc section you checked and what it said (or that you couldn't find it)
4. What you need from me to unblock (a decision, a piece of information, a test result)
```

**Why it works:**
Forces precision. "I'm getting a type error" is useless. "The function in /lib/auth/session.ts expects
UserId but DOC3 says the API route passes string — which is the source of truth?" is actionable.

---

### PP-11: Decision Forcing
**When to use:** The agent presents multiple options and asks which one to use, when the answer is in the docs.

**Structure:**
```
Before asking me: did you check DOC[1/2/3] for this?

[If they didn't]: Read [specific section]. The answer is there. Proceed based on what it says.
[If they did and it's genuinely ambiguous]: [Give the decision]. Note it as [RESOLVED: ...] inline.
```

**Why it works:**
Eliminates over-asking (AP-17) by establishing the docs as the first resort.
For genuine gaps, the inline notation creates a record that prevents the same question from coming up again.

---

### PP-12: Bug Isolation Before Fix
**When to use:** There's a bug and the agent is about to start trying fixes.

**Structure:**
```
Before you try anything:
Tell me what you know for certain about this bug:
- What behavior you observe (exactly)
- What behavior you expect (per DOC1 or DOC4 Done When)
- The smallest piece of code you think is responsible (one function or one file)

Then propose one fix. One. Tell me why you think it will work.
Wait for my go-ahead before implementing.
```

**Why it works:**
Prevents the infinite loop anti-pattern (AP-13 variant). Forces diagnostic thinking before
the agent starts spraying fixes. The one-fix constraint prevents compounding changes.

**Common mistake:**
"Try to fix this bug." — The agent will make 5 changes simultaneously. When it still doesn't work,
you have no idea which change to undo.

---

### PP-13: Loop Break
**When to use:** The agent has made 3+ attempts at the same problem and is still stuck.

**Structure:**
```
Stop trying to fix this.

Write a comment block at the top of [file name] with:
// BUG: [what it does]
// EXPECTED: [what it should do per spec]
// TRIED: [list of approaches attempted]
// HYPOTHESIS: [what you currently think the root cause is]

Then tell me this is blocked and wait.
We'll approach it differently.
```

**Why it works:**
Breaks the momentum that causes endless loops. The comment is useful whether you debug it yourself,
ask a different agent, or return to it later. The hypothesis is often the insight that leads to the fix.

**Common mistake:**
"Try a different approach." — The agent will try approach #4 with equal confidence. Same outcome.

---

## Part 5 — Session End Patterns

### PP-14: Clean Pause
**When to use:** Ending a session intentionally before a step is complete.

**Structure:**
```
We're stopping here. Before you end this session:
1. Update CONTROLLER.md — set CURRENT_STEP to [current step], add a one-line note under Session State:
   "Paused at: [exactly what was being done and what remains]"
2. Tell me in one sentence: what is done, what is not done, and what the next action is when we resume.
```

**Why it works:**
Creates a clean handoff to the next session. The CONTROLLER.md update is the artifact.
The verbal summary is for Nilesh's immediate awareness. Both serve different purposes.

---

### PP-15: Step Completion Handoff
**When to use:** A build step is done. Moving to the next one.

**Structure:**
```
[Step name] is complete. [State Done When result in one sentence.]

Update CONTROLLER.md:
- LAST_COMPLETED: Build Step [N] — [Step Name] ✓
- CURRENT_STEP: Build Step [N+1] — [Next Step Name]

Now read the Build Step [N+1] entry in DOC4. Tell me what you're about to do. Then begin.
```

**Why it works:**
The CONTROLLER.md update happens before the next step begins, not after. This means if the
session ends mid-next-step, the state is accurate. The "tell me what you're about to do" step
catches misreadings of the next step before code is written.

---

## Part 6 — Recovery Patterns

### PP-16: Architecture Reality Check
**When to use:** You suspect the agent has drifted from the architecture but aren't sure where.

**Structure:**
```
Stop building for a moment.

Read DOC3 → [Feature that was just built] section.
Compare what you built to what DOC3 describes.

Tell me: does what exists match what DOC3 specifies?
List any differences, even small ones.
```

**Why it works:**
Surfaces drift without accusation. The agent does the audit; you just review the report.
Small differences can be dismissed; large ones need fixing before they compound.

---

### PP-17: Spec Conflict Resolution
**When to use:** The agent reports that two docs seem to contradict each other.

**Structure:**
```
Show me exactly:
- What DOC[X] §[section] says: [paste it]
- What DOC[Y] §[section] says: [paste it]
- Why you think they conflict

[After reviewing:]
[Decision: X takes precedence / Y takes precedence / here's the resolution]
Mark this inline in both places as [RESOLVED: {decision}] and continue.
```

**Why it works:**
Forces the agent to show its work rather than infer a resolution. The RESOLVED tag prevents
the same conflict from being reported again in a future session.

---

### PP-18: The Hard Reset
**When to use:** The session has gone completely off track — wrong files, wrong scope, architecture violated.
A last resort before abandoning the session.

**Structure:**
```
Stop everything.

Don't save any of the code you've written in the last [N] prompts.

Read CONTROLLER.md. Find CURRENT_STEP.
Read only that build step in DOC4.
Tell me: what does Done When say, and what is the minimum code required to satisfy it?

Start over from that minimum. Nothing else.
```

**Why it works:**
A clean discard is better than building on a broken foundation. The "minimum code required"
framing prevents the agent from re-drifting by anchoring to the smallest possible scope.

**When not to use:**
If the code is partially correct, a targeted correction is better than a full reset.
Use this only when the session is fundamentally off-track.

---

## Part 7 — Communication Patterns

### PP-19: One-Sentence Status Request
**When to use:** You want a quick progress update without a wall of text.

**Structure:**
```
Status: one sentence. What did you just finish and what's next?
```

**Why it works:**
Explicit constraint. Without it, status reports become documentation.

---

### PP-20: Verification Request
**When to use:** The agent says something is done. You want proof before marking it complete.

**Structure:**
```
Before I mark this done:
How did you verify the Done When condition?
What specifically did you check, run, or observe?
```

**Why it works:**
Catches phantom completion (AP-14). The agent has to articulate verification, which either
reveals it didn't verify, or produces a clear confirmation you can trust.

---

### PP-21: What's Missing
**When to use:** A step seems done but something feels off and you can't identify it.

**Structure:**
```
Read the Build Step [N] entry in DOC4 in full.
Read Folder/file targets line by line.
Tell me: is there any file or function in that list that doesn't exist yet?
```

**Why it works:**
Specifically targets partial step completion (AP-23). The file-by-file check is harder to
wave through than "is the step done?" — it forces an actual inventory.

---

## Quick Lookup: Pattern by Situation

```
Situation                                   Pattern
────────────────────────────────────────────────────────────────────────
Starting a fresh session                    PP-01
Resuming after interruption                 PP-02
Starting a specific build step              PP-03
Agent expanding scope                       PP-04
Agent has a good idea out of scope          PP-05
Unsure if something is in scope             PP-06
Layer violation spotted                     PP-07
Interface mismatch with DOC3               PP-08
About to use a library — check first       PP-09
Agent vaguely reports being stuck           PP-10
Agent asking a question docs already answer PP-11
Bug appears — about to try fixes            PP-12
Agent has tried 3+ fixes, still stuck      PP-13
Ending session mid-step                     PP-14
Step done, moving to next                   PP-15
Suspect architecture drift                  PP-16
Two docs seem to conflict                   PP-17
Session completely off track                PP-18
Quick status update                         PP-19
Agent says it's done, want proof            PP-20
Step seems done but feels off               PP-21
```
