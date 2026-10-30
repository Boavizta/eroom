# EROOM — Quick diagnostic, univocal version

> **Main deliverable: `EROOM-diagnostic-rapide-univoque-v0.1.xlsx`** (same folder) — the
> questionnaire in EOF format, ready to fill in: 16 criteria, 1–5 dropdown +
> "I don't know", computed synthesis, trade-offs. This document is its companion:
> it explains each choice, quantifies the corrected defects and lists what remains open.
>
> Extended EOF format: `CRITERION` · `✏️ EVALUATION` · `EVALUATION METHODS` ·
> `ADDITIONAL EXPLANATION` · `IMPACT LEVEL` · `RECOMMENDATION (REPORT)` — plus a
> seventh column to come, `EDGE CASE` (see "The seven columns").
>
> Scope: **quick diagnostic, 16 criteria, 6 pillars.** The advanced diagnostic
> (54 criteria) is not covered here.
>
> Sources: the repo's EOF V1.1 template
> (`docs/EOF-V.1.1 …/🏦 0-Diagnostic rapide.html`) as the framework reference, and
> `src/data/questionnaire-qd.json` v1.2 as the application's state.
> ⚠️ The two companion files `docs/diagnostic-rapide.csv` and
> `docs/questions-diagnostic-comparaison.md` **invert the direction of `Product 1`
> version v1.1**: they place "Critical impact" at level 1 where the EOF template places
> it at level 5. Do not use them as a direction source until they are corrected
> (US 2.22). This document was written against the template.
>
> This document is a **proposal** — no data file was modified.

---

## The scale's axis

> **1 = high optimization potential · 5 = nothing to gain on this point**

The quick diagnostic is a **qualification** grid: it identifies the services that
present the greatest optimization potential — that is the template EOF's own wording.
A low score is not a bad grade, it is a priority signal.

Checked criterion by criterion against the template: **the application's 16 criteria
respect this axis.** A critical service gets 5 (its footprint is an accepted constraint);
a service whose disappearance nobody would notice gets 1 (a deletion candidate).

The defect is not a violation of the axis — it is that the axis is declared **neither in the data,
nor in the types, nor in the interface** of the application. It lives in the template's intent
and in a comment of `computeResults.ts:77` ("1=bad, 5=optimal"). Nothing mechanically
prevents adding a criterion backwards, and nothing would catch it (US 2.26).

## The seven columns

| Column | What it carries | Exists today? | Whose responsibility |
|---|---|---|---|
| **CRITERION** | The statement, as a degree question | yes (`text`) | questionnaire |
| **✏️ EVALUATION** | The five levels, all named | EOF: yes · app: levels 1/3/5 only | questionnaire |
| **EDGE CASE** | A concrete situation placed between two neighboring levels, which forces the rule to be explicit | **no — to be written (US 2.28)** | questionnaire |
| **ADDITIONAL EXPLANATION** | Why this criterion is in EROOM: the environmental impact mechanism | yes (`hint`) | questionnaire |
| **IMPACT LEVEL** | Decisive · Significant · Moderate | EOF: "Decisive" ×16, so mute · app: no | questionnaire |
| **RECOMMENDATION (REPORT)** | What comes out in the action plan when the score is low | yes (`action`; `Infrastructure 2` via code) | questionnaire |
| **EVALUATION METHODS** | The decision rule: what is counted, where to look, what separates two neighboring levels | **no** | **agent** |

### The split between the two decisive columns

`EVALUATION METHODS` is the column that removes the ambiguity — it is what makes the same
situation yield the same level, whoever or whatever answers. **It belongs to the
agent**, because it depends on the available evidence source and the retained threshold.

`EDGE CASE` is its counterpart on the questionnaire side: a concrete situation, deliberately
placed between two levels, which **forces the rule to declare itself**. The questionnaire poses the case, the
agent writes the rule that decides it. An edge case that no rule decides is a proven
ambiguity, not a suspected one. The 16 cases remain to be written — that is US 2.28, and it is
the next step of this work.

> The content of the `EVALUATION METHODS` column in the tables below is a
> **starter**, proposed so that future sheets have a starting point to challenge.
> It is not meant to be the retained version.

## The four rules applied here

1. **A criterion is a degree question**, never a closed question nor an alternative.
   "Does this service store a lot of data?" calls for yes or no; you cannot answer it on
   five levels without a mental conversion nobody wrote down. → "How much data
   does this service store?" **14 criteria out of 16** are in this case: 11
   closed questions and 3 alternatives ("X, or Y?"). Only `Architecture 2` and
   `Infrastructure 2` are well formed. A defect inherited from EOF, whose statements are
   also closed.
2. **A criterion carries a single dimension.** No "fast *and* without overloading".
   **3 criteria** pile up several: `Product 3` (response time + machine load),
   `Algo 2` (superfluous steps + back-and-forth + reloads), `Storage 2` (deletion +
   archiving).
3. **The five levels are named.** The EOF template names the five levels of the 16 criteria;
   the application's v1.2 kept only three (1, 3, 5), and **displays only
   two** — the `midLabel` field exists in the data and is read by no component
   (`ScaleInput.tsx` renders only `lowLabel` and `highLabel`). The levels 2 and 4 proposed
   below draw on the EOF labels, adapted to v1.2's usage language; their
   fine reconciliation with the template is part of US 2.27.
4. **"I don't know" is a separate answer, excluded from the score — and only one.**
   The application already does it: the quick questionnaire has a dedicated
   button (`DontKnowButton`, answer `null`, excluded from the score, counted in the confidence rate).
   The defect is the **competing double path**: ten level-1 labels still say
   "(or unknown)". The person who follows the label gets the worst score; the one who
   uses the button is excluded from the score. Two people ignorant of the same thing,
   two different results. This defect comes from EOF itself, five of whose criteria
   embed "I don't know" in the level-1 label — a point to raise (E2-9).

## IMPACT LEVEL column

The quick diagnostic's EOF template **carries** the column — filled with "Decisive" on
all 16 rows, which makes it mute: it differentiates nothing.

The values proposed below are **derived** from the application data's `co2Weight` field:
`5 or 4 → Decisive` · `3 → Significant` · `2 or 1 → Moderate`. It is a differentiation
proposal, not EROOM data.

⚠️ **This derivation is debatable and must be validated.** `co2Weight` scores the gain
brought by **treating** the criterion; `IMPACT LEVEL` scores the importance of the criterion
itself. The two often coincide, not always: `Ease of change 1` (access to the
code) carries `co2Weight: 1`, so "Moderate" by derivation, while without access to the code
no optimization is possible. It is a prerequisite, not a moderate criterion.

## Scope of the criteria — a comparability gap

`Algo 2` and `Algo 3` are only asked of `fullstack` and `frontend` services. For a
`backend` service, the Algo & Code pillar counts only **one criterion** instead of three.

Yet a pillar's score is the average of its visible criteria **that received a
numeric answer**. A pillar scored on one criterion and a pillar scored on three do not carry the same
information, and nothing in the report says so. A congruence defect of the result, not
of the statement (US 2.30).

---

## Pillar 1 — Product

| CRITERION | ✏️ EVALUATION | EVALUATION METHODS | ADDITIONAL EXPLANATION | IMPACT LEVEL | RECOMMENDATION (REPORT) |
|---|---|---|---|---|---|
| **1.1** — What would be the impact on users if this service disappeared tomorrow? | **1** Nobody would notice<br>**2** A few users inconvenienced — immediate alternatives<br>**3** Moderate impact — alternatives exist, but cost time<br>**4** Heavy disruption to main activities<br>**5** Immediate blockage — teams can no longer work | Take the end users' point of view, not the operating team's. Assess the situation 24 h after the disappearance. Keep 1 if the service can be shut down without anyone reporting it; 5 if no alternative exists and the activity stops. Source: product or business manager. | A service whose absence would go unnoticed is a direct candidate for deletion or sharing — one of the easiest gains. Conversely, a critical service is justified: its footprint is an accepted constraint, not waste. | Moderate | Assess whether this service can be reduced in scope, shared, or deleted. |
| **1.2** — To what extent are this service's features already covered elsewhere in the organization? | **1** Fully duplicated — several tools do exactly the same thing<br>**2** Large overlap — most functions exist elsewhere<br>**3** Some similarities, without real functional overlap<br>**4** Overlap limited to one secondary function<br>**5** Totally unique in the organization | Compare against applications of the same business scope, not the whole IS. Count the overlap in **main functions**, not screens. Keep 1 if another tool could replace this one without functional loss. Source: application map or IS urbanist. | Each duplicate multiplies the resources consumed: servers, data, energy. Functional redundancies are often the first low-risk gains. | Moderate | Identify and eliminate features duplicated with other services of the organization. |
| **1.3** — How do this service's main functions behave in terms of response time? | **1** Slow and visibly failing, no identified reason<br>**2** Frequent slowness, no action taken<br>**3** Functional, but obvious improvements remain to be made<br>**4** Correct — occasional optimizations already done<br>**5** Efficient and regularly reviewed | **Response time only.** Cumulating time and machine load forces a single number to score two often-diverging observations: a service that is fast because it is over-provisioned. Measure: Lighthouse / Core Web Vitals on the display side, API response time on the server side. Level 5 requires a **documented regular review**, not an absence of complaints. ⚠️ This split loses one piece of information: efficiency per request is no longer captured anywhere — trade-off n° 1. | Inefficient code can consume 2 to 10× more CPU than well-written code for the same result. Functional efficiency is the most direct impact lever. | Significant | Audit and optimize the service's slow or underperforming functions. |

**Note on `Product 1`.** Checked against the EOF template: the application's direction is
**compliant** (EOF: "1 - No or negligible impact" → "5 - Critical impact"). The files
`docs/diagnostic-rapide.csv` and `docs/questions-diagnostic-comparaison.md` document the
v1.1 backwards and are to be corrected (US 2.22) — any re-reading based on them
would wrongly conclude that this criterion was reversed.

---

## Pillar 2 — Architecture

| CRITERION | ✏️ EVALUATION | EVALUATION METHODS | ADDITIONAL EXPLANATION | IMPACT LEVEL | RECOMMENDATION (REPORT) |
|---|---|---|---|---|---|
| **2.1** — What level of availability must this service maintain? | **1** Permanent worldwide availability — the slightest outage has serious consequences<br>**2** High availability 24/7 required<br>**3** Availability commitments exist, without a permanent requirement<br>**4** Availability expected during business hours only<br>**5** Can stop without consequences — no constraint | Keep the availability **required**, not the observed one. A service that runs at 99.99% without anyone requiring it is scored on the requirement. Source: service contract, written commitment; failing that, the level the team declares it maintains, flagged as such. ⚠️ Same question as `ease-advanced-10` of the advanced diagnostic — trade-off n° 6. | High SLAs (99.99%) require permanent hardware redundancy, often underused. Each additional "9" has an almost exponential carbon cost. | Significant | Review the availability requirements and remove unjustified hardware redundancy. |
| **2.2** — How many other systems or services must work for this one to work properly? | **1** Interconnected with almost the whole organization (access, identity…)<br>**2** Numerous dependencies, several of them critical<br>**3** Connected to several systems, with important dependencies<br>**4** One or two dependencies, not critical<br>**5** No connection — works alone | Count the dependencies **whose unavailability degrades the service**, not all network calls. Include authentication and shared databases. A dependency is critical if its shutdown makes the service unusable. Source: architecture diagram or interview with the team. | A strongly coupled system is hard to optimize in isolation. Each dependency adds network calls, latency and induced consumption that is hard to control. | Moderate | Reduce the number of inter-service dependencies and limit unnecessary network calls. |
| **2.3** — How much effort does a newcomer need to understand this service's architecture? | **1** Very complex — even the creators struggle to explain it<br>**2** Several weeks of onboarding needed<br>**3** About one week of onboarding<br>**4** One or two days to get up to speed<br>**5** Very simple — explainable in a few minutes | Criterion worded as an **onboarding effort** rather than a judgment on complexity: it is an observable fact in the team, not an opinion. Take the real observed delay of the last hire, if any. Source: development team. | Complex architectures consume more resources to run and cost more to maintain. Simplicity is ecodesign's best ally. | Moderate | Simplify the architecture — split into independent modules and document the flows. |

---

## Pillar 3 — Infrastructure

| CRITERION | ✏️ EVALUATION | EVALUATION METHODS | ADDITIONAL EXPLANATION | IMPACT LEVEL | RECOMMENDATION (REPORT) |
|---|---|---|---|---|---|
| **3.1** — What is this service's hardware footprint — servers, containers, compute power? | **1** Among the most resource-hungry in the organization<br>**2** Clearly above average<br>**3** In the organization's average<br>**4** Light — below average<br>**5** Very light — a few servers or a small cloud service | Count **all environments**, production and non-production. Scale **relative to the organization**: the same sizing is scored differently depending on context — scores are therefore not comparable from one organization to another (trade-off n° 3). Source: infrastructure inventory or cloud bill. | Oversized machines often run at 10–15% load. Reducing the infrastructure size is one of the most immediate carbon impact levers. | Decisive | Right-size the infrastructure to the real load — remove or reduce oversized resources. |
| **3.2** — In which country or region is this service hosted? ⚠️ | *Free text entry: country or cloud region.*<br>Score derived from carbon intensity, table **implemented** (`electricityMap.ts`):<br>**1** > 500 gCO₂e/kWh<br>**2** 300 – 500<br>**3** 150 – 300<br>**4** 50 – 150<br>**5** ≤ 50 gCO₂e/kWh | Keep the **production** hosting region. If the service is multi-region, keep the most carbon-intensive one. Region → carbon intensity conversion by `src/lib/electricityMap.ts`. ⚠️ These thresholds diverge from EOF V1.1 — boxed below. | Carbon intensity of electricity varies from 1 to 10 depending on the country. Hosting in Northern Europe rather than South-East Asia can divide the carbon footprint by 5 at almost identical cost. | Decisive | Migrate hosting to a zone with less carbon-intensive electricity (the detected zone and its intensity are cited in the generated text). |
| **3.3** — Where do you stand on handling the slowness or consumption issues identified on this service? | **1** Recurring topic in the team, never handled<br>**2** Issues identified, none entered into the backlog<br>**3** Some improvements identified and backlogged<br>**4** Treatment started, fixes in progress<br>**5** No known issue | The criterion concerns the **handling**, not the existence of issues. A team that knows its issues and handles them scores better than a team that sees none for lack of measurement — if no performance measurement exists, flag it with the answer. Source: product backlog. | Ignored performance tickets are documented, quantifiable resource waste. Each pending ticket is a continuous energy cost. | Decisive | Handle the identified performance and waste tickets — each pending ticket costs energy. |

**`Infrastructure 2` — in the action plan, absent from the score.** Its answer is free
text, and `computeResults.ts` computes pillar scores only on numeric
answers. This criterion therefore enters **neither the pillar score nor the overall score**
— while it carries `co2Weight: 5`, the questionnaire's strongest weighting. It is
not absent everywhere: `computeResults.ts:79` converts the zone into a 1–5 score and injects a
recommendation into the action plan. **The only criterion handled by a dedicated code path
rather than by data** — invisible to anyone reading the questionnaire without reading the code.
Trade-off n° 2.

**Threshold divergence between the framework and its implementation.** The EOF V1.1
template sets five bounds: `1 > 750` · `2 < 500` · `3 < 300` · `4 < 200` · `5 < 100` gCO₂e/kWh —
with a **gap between 500 and 750**: a region at 600 gCO₂e/kWh falls into no band.
`electricityMap.ts` applies `500 / 300 / 150 / 50`, continuous but different everywhere. No
trace of the decision. To be raised (E2-9) and decided (trade-off n° 2).

---

## Pillar 4 — Storage & Data

*(named "Storage & Data" in the application — trade-off n° 5.)*

| CRITERION | ✏️ EVALUATION | EVALUATION METHODS | ADDITIONAL EXPLANATION | IMPACT LEVEL | RECOMMENDATION (REPORT) |
|---|---|---|---|---|---|
| **4.1** — How much data does this service store? | **1** Massive — several terabytes<br>**2** Important — hundreds of gigabytes<br>**3** In the organization's average<br>**4** Modest — a few gigabytes<br>**5** Very little — a few megabytes | Count the **useful** volume, excluding replication and backups, and say so if the available measure includes them. Add up all environments. Source: database console or storage bill. ⚠️ The scale mixes absolute benchmarks and a benchmark relative to level 3, and leaves gaps between orders of magnitude (where do 40 GB fall?) — trade-off n° 3, and first candidate for edge cases (US 2.28). | Storing data has a permanent energy cost. 1 TB represents about 20 kWh/year, often multiplied by 3 for redundancy — before even counting backups. | Decisive | Audit the volume of stored data and purge what is no longer used. |
| **4.2** — What is the level of automation of this service's data lifecycle? | **1** No rule — data accumulates indefinitely<br>**2** Rules considered, never written<br>**3** Rules exist, rarely followed<br>**4** Rules applied, partially automated<br>**5** Strict lifecycle, fully automated and controlled | The criterion covers **purge and archiving together**, from the automation angle — the current statement asks "delete **or** archive", which a team that archives without ever purging cannot answer. Keep 4 if the rules run but need an intervention; 5 if they run alone and are controlled. Source: retention policy, scheduled tasks. | Without an archiving policy, data accumulates indefinitely. Automating the lifecycle is one of the most durable and lowest-risk gains. | Significant | Set up a data lifecycle policy with automatic archiving and purging. |

---

## Pillar 5 — Algo & Code

*(named "Algo & Code" in the application **and** in the advanced diagnostic — trade-off n° 5.)*

| CRITERION | ✏️ EVALUATION | EVALUATION METHODS | ADDITIONAL EXPLANATION | IMPACT LEVEL | RECOMMENDATION (REPORT) |
|---|---|---|---|---|---|
| **5.1** — How intense are the processing tasks this service performs? | **1** Very heavy — intensive calculations on large data masses<br>**2** Regular heavy processing<br>**3** A few significant processing tasks<br>**4** Light, occasional processing<br>**5** Minimal — display or transmission only | Concerns **business processing**: calculations, aggregations, transformations, training. A service that only reads and displays scores 5, even if it serves high traffic — the hardware volume is handled in 3.1. "Heavy" vs "significant" remains to be bounded by edge case (US 2.28). Source: development team, CPU profile if available. | An O(n²) algorithm can consume 100× more CPU than an O(n log n) on real data. Algorithmic complexity has a direct, measurable impact on consumption. | Decisive | Review costly algorithms and reduce the computational complexity of processing. |
| **5.2** — What is the friction level of the main user journeys? *(fullstack, frontend)* | **1** Users get lost or complain — known issues, not fixed<br>**2** Frequent frictions, never measured<br>**3** Functional, a few known irritants<br>**4** Journeys reviewed — minor residual irritants<br>**5** Tested with users — smooth and consistent | Limit to the **main journeys**, the ones carrying most of the usage. Measurable clues: number of steps, back-and-forth, page reloads per completed task. Level 5 requires a **user test actually carried out**, not an internal conviction. | UX frictions generate unnecessary requests, page reloads and longer sessions out of frustration. Smooth UX reduces the number of interactions, hence consumption. | Moderate | Improve the UX to eliminate unnecessary reloads and journeys in error. |
| **5.3** — What is the comfort level of use on your users' oldest devices? *(fullstack, frontend)* | **1** Incompatible — users cannot use it<br>**2** Usable at the price of very long waits<br>**3** Usable, but simple tasks take several seconds<br>**4** Correct — occasional slowdowns<br>**5** Fast and comfortable, even on devices more than 5 years old | Assess on the **real fleet of users**, not on a test device chosen by the team. Failing that, define a reference hardware profile and name it in the answer. Measure: Lighthouse with CPU/network throttling, JavaScript weight. ⚠️ The "more than 5 years" threshold is backed by no hardware profile — trade-off n° 4. | Forcing terminal renewal is one of the heaviest impacts of digital technology. Compatibility with old hardware extends its lifespan and avoids its premature manufacture. | Significant | Optimize compatibility with old devices to extend their lifespan. |

---

## Pillar 6 — Ease of change

*(named "Ease of Change" in the application — trade-off n° 5.)*

| CRITERION | ✏️ EVALUATION | EVALUATION METHODS | ADDITIONAL EXPLANATION | IMPACT LEVEL | RECOMMENDATION (REPORT) |
|---|---|---|---|---|---|
| **6.1** — What is your team's level of access to this service's code? | **1** No access — total black box<br>**2** Read-only access<br>**3** Partial access — some modules only<br>**4** Full access, but modification subject to external validation<br>**5** Total access — code fully open and modifiable | The criterion concerns access **in modification**, not in reading: it is the prerequisite of any optimization. A configurable package without source access: keep 1 if nothing is modifiable, 2 if configuration is the only lever. Source: development team, publisher contract. | Without access to the code, no optimization is possible. Control of the source is the absolute prerequisite of any ecodesign project. | Moderate | Recover full access to the source code — prerequisite to any optimization. |
| **6.2** — What is your team's level of technical autonamey on this service? | **1** Nobody can intervene on this service<br>**2** A single person knows how to intervene<br>**3** Partial knowledge — risky intervention, possible with support<br>**4** Several people autonameous on most of the service<br>**5** Autonameous team — full mastery, confident intervention | Assess the skills **effectively available today**, not those recruitable. Level 2 — a single person — is a fragility point to distinguish from level 3: it is not handled the same way (knowledge transfer rather than training). Source: team and its management. | The implicit knowledge of a single developer who leaves blocks all evolution. The availability of skills concretely determines the capacity to act. | Moderate | Train the team or recruit the skills to master and evolve this service. |

---

## The "I don't know" answer

The mechanism already exists in the application (dedicated button, answer excluded from the score, counted
in the `confidencePercent` confidence rate). The remaining work is to **remove the
competing path**: no 1–5 level label must contain "unknown" — ten
contain it today, a direct inheritance of the EOF template (US 2.23, E2-9).

The rate of known answers — `confidencePercent`: usable answers over visible
questions — is the **confidence indicator of the diagnostic**, distinct from the score. A service
whose team ignores half the answers is a finding in itself.

---

## Decidability by an agent — quick diagnostic in a black box

Classification under the constraint **URL only**, without access to the repository, to the
IaC nor to observability. Triage convention of the advanced diagnostic: **AUTO** (the agent decides alone),
**SEMI** (it proposes, a human confirms), **HUMAN**.

**Classification rule applied**, so that the table is replayable:

- **AUTO** — a machine source accessible from the URL is enough to determine the level, and the
  evaluation method asks for no information the machine does not have.
- **SEMI** — the source exists but covers only part of what the method requires:
  it grounds a proposal, not a decision. Each SEMI row names what is missing.
- **HUMAN** — the method requires contractual, organizational or
  intentional information, which no external measurement produces.

The classification is deduced from the EVALUATION METHODS column, not from the statement alone.

**Expected output format of the agent** — that of the pre-fill contract (E3-1):
`{ questionId, answer (level 1–5 or abstention), confidence, evidence[] }`. A proposal
without evidence is refused at import. The exploitation of the declared ↔ measured gap is
specified separately (E3-5), not here.

| Criterion | Class | Evidence source |
|---|---|---|
| **3.2** hosting region | AUTO | IP / CDN → region → carbon intensity. **Caveat:** behind a CDN, the origin can be masked, and multi-region invisible — if the origin region cannot be identified with certainty, abstain rather than score the entry point's region. |
| **1.3** response time | SEMI | CWV, Lighthouse — the display only, nothing of the back office. |
| **2.2** dependencies | SEMI **weak** | Third-party domains in the HAR. **Deceptive proxy**: blind to internal dependencies (SSO, bus, shared database), precisely the ones the criterion targets. Abstain rather than propose a low score out of blindness. |
| **5.2** journey friction | SEMI | Requests and reloads per journey. The user's perception remains out of reach. |
| **5.3** old devices | SEMI | Mobile CWV, JS weight, throttling. The users' real fleet is unknown to the agent. |
| The other 11 | HUMAN | Business criticality, contractual SLA, stored volume, retention policy, code access, team autonamey, application duplication, performance backlog. |

**1 AUTO · 4 SEMI · 11 HUMAN** — 6% in AUTO, 31% in AUTO+SEMI. The advanced diagnostic is at
30% / 57%, all accesses combined.

This is not a defect: it is the nature of the quick diagnostic. It concerns the **context**
of a service — what it is for, what it costs the organization, who can touch it — and not
its observable behavior. **Consequence:** on the quick diagnostic, automatic pre-fill
is not the useful use. The two uses that are: leading the interview without
ambiguity — hence this document's columns — and confronting the declared answer with the measurement
on the five AUTO/SEMI criteria.

---

## Measurement — before / after

Eight binary tests, applied to the 16 criteria: **128 points**. Each test is verifiable
on pieces — data, code or interface — without judgment: anyone must find the
same number. **"Before" = the application's current state. "After" = once this
document's proposal is applied, data and interface included** (tests U3 and U5
assume US 2.27 and the delivered method sheets).

| # | Test | Passes if… | Before | After |
|---|---|---|---|---|
| **U1** | Degree statement | The statement is neither a closed question nor an alternative | **2** | 16 |
| **U2** | Single dimension | The statement does not pile up two separately assessable observations | **13** | 16 |
| **U3** | Five levels named | Levels 1 to 5 each carry a label, and it is displayed | **0** | 16 |
| **U4** | Ignorance as a single answer | No scale label contains "unknown" | **6** | 16 |
| **U5** | Evaluation method written | A rule says what is counted and what separates two neighboring levels | **0** | 16 |
| **U6** | Direction compliant with the axis | Level 1 corresponds well to the high optimization potential | **16** | 16 |
| **C1** | The answer enters the score | The answer feeds the pillar score and the overall score | **15** | 15 |
| **C2** | Recommendation present and consistent | A recommendation exists and targets the low levels well | **16** | 16 |
| | | **Total** | **68 / 128** | **127 / 128** |

> ### **53 % → 99 %**

The only persistent failure: `Infrastructure 2` in **C1** — its answer feeds the action
plan but not the pillar score, and this document proposes the fix without deciding it
(trade-off n° 2).

Note on the action plan, which grounds C2: `computeResults.ts` only keeps the criteria whose
level is **strictly below 5**, then sorts by `(5 − score) × co2Weight`. The
recommendations of the 16 criteria target the low levels well — checked one by one.

### Why this 99 % is misleading

**The grid tests exactly the defects this document corrects.** Built from
its own findings, it can only grade its own work well. The number measures the
completeness of the editorial fix, not real univocity.

Two harder measurements:

**1. How many criteria are closed, with no reserve or open trade-off?**

| Criterion | Reserve |
|---|---|
| `Product 3` | trade-off 1 — split, information loss |
| `Architecture 1` | trade-off 6 — duplicate with the advanced diagnostic |
| `Infrastructure 1` | trade-off 3 — relative scale |
| `Infrastructure 2` | trade-offs 2 and 6 — score, thresholds, duplicate |
| `Storage 1` | trade-offs 3 and 5 |
| `Storage 2`, `Algo 1`, `Algo 2`, `Ease 1`, `Ease 2` | trade-off 5 — pillar name |
| `Algo 3` | trade-offs 4 and 5 |
| **`Product 1`, `Product 2`, `Architecture 2`, `Architecture 3`, `Infrastructure 3`** | **none** |

> ### **5 criteria out of 16 are closed — 31 %**

*(Trade-off n° 7 — 5 or 3 levels — applies to all 16 and is not counted: a
global shape choice, not a per-criterion reserve.)*

**2. How many edge cases does the decision rule settle?** `0 / 16` today —
the edge cases are not written (US 2.28). This is the measurement that will replace the two others:
it alone can fail against reality, and it directly serves the agent.

Overall reading: **53 % → 99 %** says the mechanical writing defects are handled.
**31 %** says that eleven criteria still carry a substantive question raised but not decided.
The first number only rises through writing, alone. The second only rises through decisions —
several of which engage the framework, hence Boavizta, not just the implementation.
**The number to follow is the second, then the third once edge cases exist.**

---

## Trade-off points

None is decided. Each is flagged where relevant.

| # | Point | Scope |
|---|---|---|
| 1 | `Product 3`: the "response time only" split loses efficiency per request (a service frugal in hardware but greedy per call is no longer captured). Accept, or split — the quick diagnostic would go to 17 criteria. | 1 criterion |
| 2 | `Infrastructure 2`: bring its answer into the pillar score and the overall score, or accept that it only feeds the action plan? And decide the thresholds: EOF sets 750/500/300/200/100 **with a gap between 500 and 750**; the app applies 500/300/150/50. | 1 criterion |
| 3 | `Storage 1` and `Infrastructure 1`: absolute or organization-relative scale? As is, level 3 is not comparable to the other levels, and the orders of magnitude leave gaps. | 2 criteria |
| 4 | `Algo 3`: which reference hardware profile behind "devices more than 5 years old"? | 1 criterion |
| 5 | Pillar names: three in English in the quick diagnostic (`Storage & Data`, `Algo & Code`, `Ease of Change`), one in the advanced one (`Algo & Code`) — and the translations do not coincide between depths. Harmonize, including `Algo & Code`. | 3 pillars |
| 6 | Duplicates between quick and advanced: `Architecture 1` ≡ `ease-advanced-10` (high availability) and `Infrastructure 2` ≡ `infrastructure-advanced-3` (region). Same question, two pillars, two scales. Deduplicate, or write a consistency rule between the two answers? | 2 criteria |
| 7 | Scale: reuse the five EOF labels adapted to usage language (this document's proposal), or reduce to three named levels? | 16 criteria |

---

## What was checked and found compliant

- **Scale direction: the 16 criteria checked one by one against the EOF V1.1
  template.** None is reversed — including `Product 1`, contrary to what the companion
  CSV and comparison files suggest (they invert this criterion's v1.1, US 2.22).
- **Low-label ↔ explanation ↔ recommendation consistency**: checked on all 16, no
  contradiction. Recommendations only trigger on low scores and target the low
  situation well.
- **"I don't know"**: the application mechanism exists (button, score exclusion, confidence rate) — the remaining defect is in the labels, not the code.

## Limits of this document

1. **The rewordings were not tested on anyone.** They correct verifiable defects,
   but proof that they are better understood comes from user testing
   (`docs/user-tests-march-2026.md` exists for that).
2. **The labels of levels 2 and 4 are adapted, not validated.** The EOF template names the
   five levels; the proposals above draw on them in usage language but have not
   been reconciled line by line with it (US 2.27).
3. **The `IMPACT LEVEL` column is derived from a field that does not measure the same thing** —
   see the caveat in the "IMPACT LEVEL column" section.
4. **The decidability classification was not confronted with a real agent.** The four SEMI
   and the CDN caveat on 3.2 are the most likely to move in use.
5. **Several scales mix technical observation and handling maturity** (`1.3`, `3.3`,
   `5.2`) — inherited from EOF, accepted for a declarative questionnaire. The edge cases
   (US 2.28) will have to bound those levels first.
6. **Nothing prevents the drift from starting again.** None of the eight tests is machine-verified. U3, U4 and U6 are mechanically testable (US 2.26); U1, U2 and U5 remain
   human reviews. Without a test, this document describes a state, it does not hold it.
