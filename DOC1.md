# DOC 1 — NAKABANDI: Project Brief & Feature Specification

*KAYA at IIT (BHU) · problem text originates from Smart India Hackathon 2025, PS SIH25257 (MHA Cyber & Information Security Division / I4C)*
*Status: Confirmed. This document says WHAT we build and WHY (users, features, evidence, ethics). HOW it is built is DOC 2; per-module contracts are DOC 3; build order is DOC 4.*

## Table of Contents
- §1.0 — Context & Constraints
- §1.1 — Problem, Evidence & Verified Figures
- §1.2 — Feature Set (MoSCoW)
- §1.3 — User Flow Overview
- §1.4 — Technical Differentiator
- §1.5 — Ethics, Privacy & False-Positive Guardrails

---

## §1.0 — Context & Constraints

```
EVENT:        KAYA at IIT (BHU). The problem text is Smart India Hackathon 2025's PS SIH25257
              (MHA, Cyber & Information Security Division / I4C); SIH rules and formats do NOT apply.
              REQUIRED: a public hosted link and a public repository.
GOAL:         A working prototype that wins or places at KAYA and stands as a portfolio-grade
              public artifact.

TEAM:         4 people: designer, systems lead, algo dev, web dev. Roles and ownership are in DOC 4.

DEFINITION OF "FULL-FLEDGED":
  A working, end-to-end prototype. Every feature under MUST works for real on simulated
  data. Nothing is hard-coded, mocked, or faked on our side of the system. Judges are told
  plainly that the data, and the bank/CFCFRMS receiving endpoints, are simulated.
  "Full-fledged" is bounded by the MUST list in §1.2; it does not mean "everything in the PS".

STACK:        See DOC 2.
DATA:         No official dataset. Synthetic data engine is a first-class component (M1).
DEMO GEOGRAPHY: Maharashtra, Uttar Pradesh, Haryana, Jharkhand (public reporting names them
              as high-risk regions), with synthetic cluster IDs.
DOMAIN ACCESS: None. All operational claims must be traceable to public sources.
```

---

## §1.1 — Problem, Evidence & Verified Figures

```
PROJECT NAME: NAKABANDI   ("naka" = police checkpoint)
TAGLINE: Predicts where stolen money will turn into cash, and picks the cheapest way
         to stop it before it does — for cyber-cell investigators and I4C analysts.

PROBLEM STATEMENT
  Who:           A state cyber-cell investigator or I4C analyst on shift when a
                 financial-fraud complaint lands.
  Pain:          They can see which account received the money, but not where it will
                 physically come out. By the time a freeze request clears bank workflows,
                 the cash is often gone. Field teams can't be positioned because nobody
                 knows where. The one step that is tied to geography and time, cash-out,
                 is treated as a black box.
  Current state: Complaint → freeze request to banks hop by hop → phone/WhatsApp
                 coordination with local police. Tools that flag mule accounts say WHO
                 is suspicious, not WHERE and WHEN they will withdraw. Mapping and
                 analytics tend to explain yesterday's network.
  Root insight:  Digital layering is instant and unbounded, but cash-out is physical.
                 A person or runner must stand at a specific ATM, branch counter, or
                 agent point that can service that particular account (its issuing
                 bank's network, home branch, and the runners positioned there), and
                 per-card withdrawal caps push them into repeat visits. That physical
                 constraint is the one place where fraud becomes predictable, and the
                 one place where interception is still possible. (Public evidence shows
                 runners positioned near branches and ATMs across states; it does NOT
                 show a same-district pattern. See H1 below.)

CORE VALUE PROPOSITION
  NAKABANDI forecasts, per complaint, where and when a mule network is likely to cash
  out, then scores whether interception is actually possible in the time available and
  recommends the least intrusive action that works: a bank-side friction, a branch/ATM
  alert, or a field team. The same signals roll up into a heatmap for deployment
  planning, and complaints from the same network are bundled into one cluster-level
  case. Unlike tools that detect mule accounts, it answers "where and when", and it
  never acts without a human officer's approval.
```

**Positioning vs. existing systems** *(descriptions from official sources where noted in the verified-figures block below)*

| System | Answers | Gap NAKABANDI targets |
|---|---|---|
| MuleHunter.AI (RBI Innovation Hub; ML mule-account detection inside banks; bank-adoption count reported only by secondary sources, roughly 15-20 in 2025) | *Who* is a mule account | Doesn't say where the cash will be withdrawn |
| Suspect Registry / CFCFRMS (I4C; Suspect Registry launched 10 Sep 2024 and shares Layer-1 mule accounts and suspect identifiers with banks) | *Which identifiers / what money* to flag or freeze | Reactive, per-complaint, hop-by-hop |
| Samanvaya (LEA data-sharing and analytics platform) / Pratibimb (GIS mapping of criminals and crime infrastructure) | *Where* did linked crime happen (retrospective) | Backward-looking |
| **NAKABANDI** | ***Where and when* cash will surface, and *can we get there in time*** | Complements the above; consumes their outputs conceptually |

**Working hypotheses, graded against public evidence** *(public reporting and official sources, mostly news-grade; the simulator encodes these, so all performance claims are conditional on them and we say so openly)*

| # | Hypothesis | Evidence status |
|---|---|---|
| H1′ | Cash-out is anchored to the mule account's **servicing footprint** (issuing bank's network, home branch) and to where the cluster's **runners** are positioned, not to the victim's location | **Partly supported.** Multi-state accounts, victim-independent geography, and runners stationed near branches and ATMs are documented. A same-district anchoring pattern is **not** supported. The mechanism "own-bank ATMs are preferred because of free-transaction limits" is our inference, unverified. |
| H2a | Mule **accounts** are reused across many complaints | **Supported** (e.g., one reported case links 11 accounts to 181 complaints in three months; anecdotal). |
| H2b | Clusters reuse a small set of **ATMs/branches** | **Not supported.** One hotspot report cites nearly 5,000 ATM IDs; no per-network counts were found. |
| H3 | Withdrawal caps shape multi-visit, multi-ATM patterns | **Partly supported.** No universal RBI cap; limits are bank- and card-specific (typically ₹20,000 to ₹1 lakh/day for cards; AePS about ₹10,000 per transaction). Splitting across cards, ATMs and cheques is documented in cases. Limit figures come from secondary sources. |
| H4 | Time-to-cash-out is minutes to hours | **Partly supported.** Cases report roughly 15 to 29 minutes for large sums, but no distribution is published and many cases are already cashed out by report time. Timing is a **swept parameter**, not a fact. |

**Design consequences of the evidence**
1. **Predict hierarchically, and abstain honestly.** Because H2b failed, forecast at three resolutions (district → area cell → individual location) with a calibrated confidence at each, and abstain at the finest level when evidence is thin. A single-ATM promise would be overclaiming.
2. **Model channels.** Branch counter/cheque and ATM are both documented as major; micro-ATM/AePS agents, POS and DMT agents also appear. Channel shares are not published, so they are swept parameters. Crypto off-ramps are outside geographic prediction and are out of scope.
3. **Make the intervention ladder channel-aware.** Branch cash-outs involve large sums and can be delayed by the bank; ATM cash-outs are lower value per event and suit velocity or cap friction; agent cash-outs need agent-level action.
4. **Report results as sensitivity sweeps** over the timing distribution and channel mix, not as one number. The deck's honest claim is "robust across these assumptions", not "accurate".

**Verified public figures** *(primary sources: PIB and MHA parliamentary replies; quote with the period stated)*

| Figure | Value | Period / source |
|---|---|---|
| Financial-fraud complaints on NCRP | 2021: 2,62,846 · 2022: 6,94,446 · 2023: 13,10,357 · 2024: 19,18,835 · 2025: 24,02,579 · total 65,89,063 | Data till 31 Dec 2025, PIB / MHA |
| Amount reported (₹ crore) | 2021: 551 · 2022: 2,290 · 2023: 7,465 · 2024: 22,848 · 2025: 22,495 | Same. The yearly figures sum to about ₹55,649 crore; the Lok Sabha reply says "more than ₹55,050 crore", so quote "over ₹55,000 crore". |
| CFCFRMS saved / blocked | Over ₹11,158 crore across over 32.80 lakh complaints | Till 30 Jun 2026, PIB |
| Suspect Registry | Launched 10 Sep 2024; 32.08 lakh Layer-1 mule accounts and over 30.48 lakh suspect identifiers shared | Till 30 Jun 2026, PIB |
| FIRs vs. financial-fraud complaints | Over 1,95,760 FIRs against over 65.89 lakh complaints, about 3% | 2021 to 2025, MHA Lok Sabha reply, July 2026 (ratio derived by us) |
| Samanvaya / Pratibimb | LEA data-sharing and analytics platform / GIS mapping of criminals and crime infrastructure | PIB |

**Derived by us** *(arithmetic on the figures above; label as derived on slides)*
- 2025 average ≈ **6,600** financial-fraud complaints per day (24,02,579 ÷ 365). The PS states about 8,000 per day; no primary source gives that number. The simulator defaults to 8,000, configurable from 6,500 to 8,000, and we cite the PS as the source of that figure.
- Mean reported loss per complaint ≈ **₹94,000 in 2025** vs. ≈ ₹1.19 lakh in 2024: complaints grew about 25% while reported amounts stayed flat. Use it to calibrate the simulator's amount distribution; do not over-interpret it.

**Do not quote:** any official daily complaint volume (about 6,000 or 8,000/day); a 1930 daily call volume; a MuleHunter.AI adoption count as official; Operation Octopus as a national figure; "1-3% FIR conversion" as an official statistic; all-cybercrime incident totals (4,52,429 in 2021 to 22,68,346 in 2024) as financial-fraud figures. **Verify before quoting:** the Suspect Registry "declined transactions" value (₹25,698 crore at 30 Jun 2026 vs. about ₹9,055 crore at 31 Dec 2025); a near-threefold jump in six months probably reflects a definition or integration change (an I4C–RBIH data-sharing MoU in May 2026 is reported), so do not present the jump as impact.

**Prototype-level success metrics** *(targets set after the first simulator run, not invented now)*
1. Precision@k: the true cash-out ATM is within the top-k predictions.
2. Lead time: minutes between alert and the true cash-out event.
3. Interceptable share: fraction of simulated cash-outs where the ETA of the nearest unit was less than the predicted window.
4. Dispatches per successful interception: ladder vs. dispatch-everything baseline.
5. False-hold rate: legitimate accounts wrongly held per 1,000 alerts.
6. Cold-start degradation: precision when a never-seen cluster appears.
7. Alert load: alerts per officer per shift under the alert budget.

---

## §1.2 — Feature Set (MoSCoW)

Effort: **S** ≈ ≤1 builder-day · **M** ≈ 2-3 · **L** ≈ 4+ (vibecoding estimate, before integration).

```
MUST HAVE (MVP — project fails without these; all real, none mocked)

Feature: M1 — Scenario Simulator & Synthetic Data Engine                       [L]
  Description: Generates a realistic world: ATM/branch/agent registry, mule clusters
    (servicing footprint: issuing bank and home branch; runner deployment and mobility;
    channel mix; cash-out cadence; withdrawal-cap behaviour), victim complaints (category,
    amount, time), fund-flow hops across 2-12 layers, cash-out events, and legitimate
    background withdrawals. Supports history generation and a live replay stream (speed
    control), plus scenario injection.
  Why load-bearing: No data exists for this PS. Every other feature consumes this.
  Acceptance criteria:
    - Fully seedable and reproducible from a single config file.
    - Ships with a documented data format and a way to refit its parameters from any
      dataset in that format, so real agency data could replace the simulator.
    - Complaint geography is weighted by official state-wise counts (MHA parliamentary
      replies) rather than invented.
    - Auto-exports an "assumption ledger" listing every parameter, its value, and its
      justification or public-source anchor.
    - Calibrated to verified public aggregates (§1.1 verified-figures block; parameter priors in DOC 2 Appendix A):
      about 6,600/day derived from 2025 official data, with the PS's ~8,000/day as the
      default load, and it can sustain that volume in live mode.
    - Can inject a new mule cluster mid-stream (used by S4, the cold-start drill).
    - Cash-out timing is a MIXTURE (fast runners: minutes; delayed handlers: hours), not a
      single distribution, so the engine is tested against multi-modal timing.
    - Every cash-out event carries a CHANNEL attribute: ATM, branch counter/cheque,
      micro-ATM/AePS agent (baseline set documented as major channels in public reports).
      Channel shares are UNPUBLISHED, so they are configurable parameters.
    - A SENSITIVITY SWEEP is a built-in mode: the same experiment can be re-run across the
      timing distribution (e.g., median 15 vs 60 vs 240 minutes) and channel mixes, and
      results are reported as curves, not single numbers.
    - Distribution checks (e.g., Kolmogorov-Smirnov) against every public aggregate we can
      anchor to; matches AND mismatches are reported, not hidden.
    - Cluster identities are synthetic IDs (e.g., C-114); no real person or real locality is
      ever labelled as criminal.

Feature: M2 — Predictive Engine (tactical forecast + mule-cluster resolution)  [L]
  Description: For each incoming complaint: trace the layer-1 account, resolve it to a
    mule cluster on the account/ATM graph (or flag "unknown"), and output (a) a ranked list
    of likely cash-out locations at THREE resolutions (district → area cell → individual
    ATM/branch/agent point) with calibrated probabilities, abstaining at the finest level
    when evidence is thin, (b) a time-to-cash-out distribution that allows fast and delayed
    cash-outs (e.g., P(cash-out within 30/60/120 min)), calibrated and scored, (c) a
    confidence score and the top contributing evidence.
  Why load-bearing: It is the PS's core deliverable (a).
  Acceptance criteria:
    - Prediction returned within a few seconds of ingest in live mode.
    - Evaluated on held-out simulated days against THREE baselines: (i) historical-frequency
      hotspot, (ii) nearest-ATM-to-victim, (iii) issuing-bank footprint only. Precision@k,
      lead time and calibration are shown PER RESOLUTION.
    - Every prediction carries a machine-readable explanation (feeds the "why" panel).
    - Unknown-cluster cases degrade gracefully to a wider, lower-confidence prediction.

Feature: M3 — Risk Heatmap Dashboard (GIS)                                      [M-L]
  Description: Map-based dashboard with two layers: "Live risk" (now to next ~2h, from
    open alerts) and "Potential risk" (next ~72h, aggregated forecasts). Drill-down from
    state → district → area cell → location. Filters: time window, geography, crime category,
    amount band, cluster, confidence. Time slider with replay.
  Why load-bearing: PS deliverable (b) and the strategic view of the same signals.
  Acceptance criteria:
    - Filters update the map within ~1 second on the full simulated dataset.
    - Clicking any hotspot opens the underlying alerts and their explanations.
    - Small-count cells are suppressed above location level (k-threshold, see §1.5).
    - Runs on a public hosted link, and also fully offline as a backup demo path.

Feature: M4 — Alert & Notification System                                       [M]
  Description: Turns forecasts into alerts with severity, confidence, expected window,
    target ATMs/branches, recommended action and expiry. Deduplicates by cluster + target,
    routes by role and jurisdiction, and tracks acknowledgment with timed escalation.
    Channels: live dashboard push, email, SMS, and a signed informational notice to the
    affected bank's (simulated) system. A per-officer, per-shift "alert budget" ranks and caps alert volume.
  Why load-bearing: PS deliverable (d); alert fatigue is the failure mode that kills
    real deployments.
  Acceptance criteria:
    - One complaint travels end-to-end and reaches all four channels with a visible
      delivery log.
    - Duplicate complaints merge into an existing alert instead of creating a new one.
    - An unacknowledged alert escalates to the supervisor role after a configurable time.
    - The notice to the bank is signed and verified by the bank's system, which
      acknowledges it. A hold request is sent only after an officer approves it (M5, M6),
      and the bank's system applies the amount-limited lien on its own side.
    - SMS reaches a test number or falls back to a visible on-screen outbox.

Feature: M5 — Law Enforcement Interface (secure)                               [L]
  Description: Role-based web interface for I4C analyst, state cyber-cell investigator,
    district officer, and bank nodal officer. Alert inbox, alert detail with "why this
    ATM" panel, mini cluster graph, actions (acknowledge, request bank hold, notify
    station, dispatch, mark outcome hit / miss / late), notes, and a generated case brief.
  Why load-bearing: PS deliverable (c); it is where a human approves every action.
  Acceptance criteria:
    - Login with role-based access. A bank role sees only its own bank's accounts and
      cannot see other banks' data or LEA-only fields. The bank role can acknowledge but not
      act: lien execution happens in the bank's own (simulated) system.
    - Every view and action is written to an audit log with user, time and reason.
    - No action executes without explicit officer confirmation.

Feature: M6 — Interceptability Planner & Intervention Ladder        [M]
  Description: For each alert, compares predicted time-to-cash-out against the ETA of
    the nearest available unit and labels it Interceptable / Marginal / Not interceptable.
    Recommends the least intrusive sufficient action, chosen by channel: L1 bank-side
    friction, meaning an AMOUNT-LIMITED, time-boxed lien on the account, capped at the
    traced disputed amount of a filed complaint (the natural lever for branch/cheque
    cash-outs), L2 branch/ATM/agent security or CCTV alert, L3 field-team dispatch.
    Predictions decide WHERE and WHEN to act; they never widen the lien beyond what the
    complaint supports (see §1.5 legal basis and court limits on blanket freezes).
  Why load-bearing: It is the main innovation beyond the PS text, and it converts a
    prediction into a decision, which is what an investigator actually needs.
  Acceptance criteria:
    - Every alert shows ETA-vs-window and a recommended ladder level with its reason.
    - Recommendation changes when unit positions, channel, or predicted window change.
    - An L1 recommendation always shows a PROPORTIONALITY PANEL: traced disputed amount,
      proposed lien amount (never above the disputed amount), expiry/review time, and a
      reminder that the seizure must be reported to the Magistrate. No whole-account
      freeze option exists in the UI.
    - Backtest reports interceptable share and dispatches per successful interception vs
      a "dispatch-to-every-alert" baseline, as a curve over the timing sweep (M1).

SHOULD HAVE (v1.1 — high value, not blocking MVP)

Feature: S1 — Cluster Case Bundling      [M]
  Description: Groups complaints that resolve to the same mule cluster into one bundled
    case with a consolidated brief across victims, amounts, accounts and ATMs.

Feature: S2 — Evidence Pack with Tamper-Evident Audit Chain      [S-M]
  Description: Generates a timestamped PDF evidence pack (prediction, explanation,
    actions, outcomes) and links audit-log entries in a hash chain so tampering is
    detectable. The pack includes a DRAFT electronic-record certificate laid out to match
    the Bharatiya Sakshya Adhiniyam section 63(4) Schedule form, pre-filled with the
    record description and a SHA-256 hash report. The certificate is left unsigned: the
    person in charge and the expert sign it themselves. It is a drafting aid, not a
    compliance claim.

Feature: S3 — Officer Feedback Loop                                             [S-M]
  Description: Outcomes marked in M5 update ATM-affinity priors for the cluster, and the
    dashboard shows precision before vs. after feedback. Most-uncertain alerts are surfaced
    first for review (active learning), so scarce officer attention buys the most information.

Feature: S4 — Cold-Start "New Gang" Drill      [M]
  Description: A demo scenario where a never-seen cluster appears; the system shows a
    novelty flag, widened confidence, and fallback to district-level priors.

Feature: S5 — Bilingual Alert Templates (Hindi / English)                       [S]
  Description: SMS and email templates in both languages.

COULD HAVE (Backlog — nice to have)

Feature: C1 — Adversary-Aware What-If Room      [L]
  Description: Place N teams on the replayed simulation, where mules can shift after
    interception, and compare naive top-k allocation against a displacement-aware one.
Feature: C2 — PWA responder view for beat officers
  Description: Mobile-first view with navigation to the flagged ATM.
Feature: C3 — Drift monitor panel (input distribution and calibration over time)
Feature: C4 — MFA on the LEA interface

WON'T HAVE (explicitly cut)

  - Real integration with NCRP, CFCFRMS, or any bank core system (we simulate the receiving
    side and say so).
  - Real transaction data or any real personal data.
  - Graph neural networks as the primary model (classical graph features plus ranking; see §1.4).
  - Automatic freezing or any autonomous enforcement action (human approval on every action, §1.5).
  - Person-level or neighbourhood-demographic profiling (we score accounts and ATMs, not people
    or communities).
  - "Blockchain" branding for the audit chain. It is a hash chain, and we call it that.
  - Native mobile apps; crypto tracing; hawala modelling; LLM chatbot.

⚠️ SCOPE CREEP FLAGS
  - "Let's use a GNN / Transformer." Sounds impressive; eats the whole schedule.
  - Road-network isochrones for the whole country. Precompute for the demo states only.
  - Too many crime categories. Restrict the simulator to 3-4 categories that clearly
    end in cash-out.
  - Real SMS/telecom compliance work (DLT registration). Use test delivery.
  - Building a beautiful design system before the data flows end to end.
```

---

## §1.3 — User Flow Overview

**Primary flow (tactical, hero use-case)**

```
[Complaint ingested (simulated stream)]
        ↓
[Trace layer-1 account → resolve to mule cluster on the account/ATM graph]
        ↓
[Forecast: ranked ATMs/branches + time-to-cash-out window + confidence + evidence]
        ↓
[Interceptability check: window vs. nearest-unit ETA → ladder level recommended]
        ↓
[Alert created, deduplicated, routed by role/jurisdiction, budget applied]
        ↓
[Alert delivered: dashboard + SMS + email + signed notice to the affected bank]
        ↓
[Officer reviews in LEA interface: "why this location", cluster graph, evidence]
        ↓
[Officer approves action: hold request (L1) / branch alert (L2) / dispatch (L3)]
   (a hold request goes to the bank's own system, which applies the lien)
        ↓
[Outcome logged: hit / miss / late]  →  [Feedback updates priors, heatmap, metrics]

Edge cases:
  Low confidence            → no alert; signal still feeds the heatmap
  Duplicate complaint       → merged into the existing alert and cluster case
  Unknown cluster           → wider prediction, novelty flag, district-level priors
  No unit within reach      → recommend bank-side friction (L1) or branch alert (L2) only
  Alert unacknowledged      → timed escalation to supervisor role
  Officer overrides         → reason required and audit-logged
```

**Secondary flow — Strategic planning (I4C analyst)**
`Open heatmap → set time/state/category filters → inspect "Potential risk" for the next 72h → drill to district → ATM → view cluster and alerts → export deployment note`

**Secondary flow — Bank nodal officer**
`Receive signed notice in the bank's own system → see only own accounts → acknowledge → (if an officer sends a hold request) apply an amount-limited, time-boxed lien → mark applied/released → status flows back to the investigator`

---

## §1.4 — Technical Differentiator

*Technical decisions and the components that implement each are in DOC 2 §2.2.*

```
D1 (lean)      Hierarchical location forecast (district → area cell → individual location)
               with calibrated probabilities and abstention, plus a time-to-cash-out model
               that allows fast and delayed cash-outs.
  Why it fits: evidence supports reuse of mule ACCOUNTS across complaints but not reuse of
               specific ATMs, so a single-ATM promise would overclaim.
  Feasibility: medium. Literature-backed: yes.

D2 (haversine) Straight-line reachability for the interceptability check.
  Feasibility: high. Literature-backed: no (engineering call).

D3 (stretch)   Adversary-aware allocation for the What-If Room (C1). Built only if the MUST
               tier lands early.
  Feasibility: low-medium. Literature-backed: yes.

NOT CHOSEN     Graph neural networks. Kept as the stated upgrade path in the deck.
```

**Positioning claim.** A literature scan found no validated minute-level mule cash-out model. NAKABANDI is a novel combination of adjacent methods (spatial choice, graph features, time-to-event) and is pitched that way, never as "state of the art". All performance claims are conditional on the simulator's stated assumptions. Because the simulator encodes our hypotheses, results are never claimed as accuracy: report baselines, recovery of planted structure, the cold-start drill and sensitivity sweeps.

---

## §1.5 — Ethics, Privacy & False-Positive Guardrails

*The mechanisms that enforce each principle are traced in DOC 2 §2.5.*

```
PRINCIPLES
  1. Human-in-the-loop (accountability): the system recommends and never executes.
     Every action needs explicit officer confirmation and is audit-logged with a reason.
  2. Score accounts and ATMs, not people or communities: no demographic, caste,
     religion, or neighbourhood-profile features; a documented feature blocklist.
  3. Data minimisation & purpose limitation: role-based views. Bank roles see only their
     own accounts; LEA roles see clusters; the heatmap shows aggregates.
  4. Aggregate privacy: heatmap cells below a minimum event count (k-threshold) are
     suppressed above ATM level.
  5. Time-boxed, reversible interventions: L1 holds expire automatically and have an
     explicit release path through the bank nodal officer.
  6. Alert budget: ranked, capped alerts per officer per shift to prevent fatigue and
     rubber-stamping.
  7. Tamper-evident logging (S2) so decisions can be reviewed after the fact.
  8. Synthetic-only data: no real personal or transaction data, and cluster IDs are
     synthetic rather than real names or named localities.
  9. Alert compartmentalisation: predictions are sensitive (an insider leak can tip off
     mules). Need-to-know routing, no broadcast lists of flagged ATMs, masked identifiers in
     SMS/email, and access logging.
 10. Alert triage tiers (auto-expire / review / escalate) so officers are not asked to
     rubber-stamp everything; explanations are narrative, not just a score.

FALSE-POSITIVE HANDLING
  - Report false-hold rate per 1,000 alerts as a first-class metric.
  - Operating point is tunable (precision vs. recall) and shown to the officer.
  - Low-confidence signals go to the heatmap only; they never trigger holds.

FEEDBACK-LOOP RISK (predictive-policing critique)
  Deploying patrols where predictions point creates more observed events there and can
  reinforce the model. Mitigations: log deployment exposure alongside outcomes, keep an
  exploration share of alerts, and evaluate on displacement-aware replays (C1 if built).

LEGAL FRAMING  (official-source summary, NOT legal advice)
  Data protection (DPDP Act 2023): processing for prevention, detection, investigation
    or prosecution of offences is exempt from most obligations under s.17(1)(c), but the
    general duty of compliance (s.8(1)) and reasonable security safeguards (s.8(5)) remain.
    Section 17 is enacted but, per the commencement notification, not in force until
    13 May 2027, and most Rules provisions are also phased to that date. So our
    minimisation, role-based access and audit choices are DESIGN principles, not claimed
    compliance.
  Holds and liens (BNSS 2023): s.106 (police seizure, with a forthwith report to the
    Magistrate) and s.107 (proceeds of crime, Magistrate route, show-cause notice with an
    ex parte interim option). An NCRP-CFCFRMS SOP exists but is not public. MHA's
    money-restoration FAQ says restoration below ₹50,000 can proceed on police
    instructions without an FIR, an FIR is required above ₹50,000, and custody to the
    victim follows an IO's s.106(3) order within 15 days. No RBI circular on CFCFRMS
    liens was found, so never call it an "RBI SOP".
  Court limits on broad freezes (REPORTED High Court rulings from unofficial mirrors;
    verify on court portals before citing): Kerala, Bombay (Nagpur), Allahabad (Lucknow)
    and MP High Courts criticised whole-account or oversized freezes, said liens should
    be limited to the identified disputed amount, and asked for the lien amount and FIR
    details to be specified and the Magistrate informed. One reported Allahabad ruling
    allows s.106 freezes only up to the quantified tainted amount. Only the Supreme Court's
    Tapas D. Neogy (1999) baseline (a bank account is "property") was retrievable from an
    official URL.
  Electronic evidence (BSA 2023 s.63): a certificate in the Schedule form must accompany
    the record, signed by the person in charge and an expert, and must state the record's
    hash value (SHA-1, SHA-256, MD5 or another accepted standard) with a hash report. Who
    counts as the "expert" is not clearly defined.
  Design consequences: (1) L1 holds are amount-limited, time-boxed, complaint-anchored
    and proportionality-checked; (2) S2 drafts the s.63 certificate with a SHA-256 hash
    report for human signatures; (3) we make no claim of legal compliance anywhere.
```

---
