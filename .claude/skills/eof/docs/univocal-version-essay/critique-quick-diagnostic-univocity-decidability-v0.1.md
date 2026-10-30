# Critique — quick diagnostic, univocal version (v0.1)

> This document critiques `quick-diagnostic-univocity-decidability-v0.1.md` (same folder).
> It does not replace it and corrects none of its content: it is an external re-reading, backed
> by a read-only exploration of the "Agent EROOM" repository.
>
> Scope: the source document (16 criteria, 6 pillars, quick diagnostic) and its articulation
> with the audits already produced by the `analyse-parcours` skill in this same repository.
>
> This document is a **proposal** — no file was modified, no trade-off is
> decided.

---

## Open point n° 8 — "pillar" or "dimension"

The EROOM reference framework and the source document use the term **pillar** for the six
groupings of criteria (Product, Architecture, Infrastructure, Storage & Data,
Algorithm & Code, Ease of change). This choice was however not obvious: the
term **dimension** had been mentioned in the exchanges with Tristan as an alternative.

No file in this repository documents this trade-off — neither as a decision made, nor as a
point under discussion. It is recorded here so it is not lost, following the seven
trade-off points of the source document:

| # | Point | Scope |
|---|---|---|
| 8 | "Pillar" (retained) vs "dimension" (mentioned with Tristan) to name the six groupings of criteria. Not decided, not documented elsewhere in the repository. | 6 pillars, any future bridge with the application or with other framework documents |

**Consequence if the term changed**: renaming the six section titles of the source
document, of its summary table, of any mention in the application (if the field is
exposed there), and of any document built on top — including this one and a future bridge with
the `analyse-parcours` audits (see below). Until it is decided, this document uses
"pillar" for consistency with the source document, without that being a position.

---

## What is consistent

The source document is already rigorous on its own scope, and says so itself:

- **Scale axis** (1 = high optimization potential, 5 = nothing to gain): checked
  criterion by criterion against the EOF V1.1 template, on all 16 criteria. No inversion
  found, including on `Product 1` — a point on which the cited companion files
  would nevertheless mislead.
- **Low-label ↔ explanation ↔ recommendation consistency**: checked on all 16 criteria,
  no contradiction found.
- **"I don't know" mechanism**: already implemented on the application side (dedicated button, answer
  excluded from the score, counted in the confidence rate). The residual defect identified (ten
  level-1 labels still containing "unknown") is correctly isolated as a writing defect, not a
  mechanical one.
- The document accepts and quantifies its own limits (the "53 % → 99 %" measurement explicitly
  qualified as misleading, edge cases not written, decidability classification not confronted with a
  real agent) — a rare self-critique, to be kept as a method.

## What raises questions

### Verifiability of the cited sources

The source document claims **piece-by-piece replayability** ("so that the table is
replayable", section "Decidability"). Yet the exploration of this repository finds none of
the files it cites as sources or companions:

- `docs/EOF-V.1.1 …/🏦 0-Diagnostic rapide.html`
- `docs/diagnostic-rapide.csv`
- `docs/questions-diagnostic-comparaison.md`
- `docs/user-tests-march-2026.md`
- `src/data/questionnaire-qd.json`
- `src/lib/computeResults.ts`
- `src/lib/electricityMap.ts`

No US tracker, no trade-off log was found either. The folder
`docs/Référenciel EROOM/` contains only the source document and the workbook
`EROOM-diagnostic-rapide-univoque-v0.1.xlsx`; the skill's parent `docs/` folder contains
only the HAR/Coverage capture guide.

This is probably not an error in the source document: these files most likely live
in the EROOM application's own repository, distinct from "Agent EROOM". But it is
a blind spot for anyone reading this document from this repository without access to the other one: the
cited proofs (US 2.22, `computeResults.ts:77`, `ScaleInput.tsx`, `co2Weight`) are not at hand
here. To be flagged explicitly rather than left to the presentation to imply
they are.

### Two parallel reference frameworks, never connected

This repository already contains real audits produced by the `analyse-parcours` skill:
`audits/octo.com`, `audits/audit-30000-octo`, `audits/ants-permis` (e.g.
`journey-report-2026-08-11.html`). These are "Audit EROOM v1.1.0" reports: prioritized
recommendations, GreenIT-Analysis good practices, CO2e/e-footprint impact, EcoIndex/Core Web
Vitals, network traffic, JS/CSS coverage. Examples of recommendations already produced: lazy
loading + tree shaking on dead JS, PurgeCSS on dead CSS, browser cache, Brotli,
limit third-party domains.

**None of these audits references the 16 criteria or the 6 pillars** of the quick diagnostic.
These are two reference frameworks coexisting in the same repository without a documented bridge, while the
source document explicitly talks about a future agent that would pre-fill the questionnaire from
external evidence (section "Decidability by an agent"). The agent that today
produces comparable external evidence (`analyse-parcours`) does not feed this
questionnaire, and vice versa. See below the most immediate path to close this
gap.

### Figures cited without a source verifiable in this repository

The comparison "the advanced diagnostic is at 30 % / 57 %, all accesses combined" (section
"Decidability") has no document or calculation findable in this repository. To be treated as a
claim to verify, not as an established fact, until its source is located
(probably in the application's repository, like the files above).

### Limits already admitted, confirmed by the exploration

The exploration contradicts none of the six limits listed at the end of the source document; it
confirms at least two with more force: the decidability classification has indeed
never been confronted with a real agent (no trace of an implementation in this repository), and none
of the eight measurement tests is machine-verified here.

---

## Coverage per pillar — what an external audit can already feed

Reminder of the three decidability classes, under the constraint **URL only, without access to the repository, to
the IaC nor to observability** (definition taken from the source document):

- **AUTO** — a machine source accessible from the URL is enough to determine the level, without
  any additional information the machine does not have. The agent decides alone.
- **SEMI** — the source exists but covers only part of what the method requires:
  it grounds a proposal, not a decision. The agent proposes, a human confirms.
- **HUMAN** — the method requires contractual, organizational or
  intentional information, which no external measurement produces.

By aggregating per pillar the source document's decidability table (column "black box,
URL only"):

| Pillar | AUTO | SEMI | HUMAN | % covered (AUTO + SEMI) |
|---|---|---|---|---|
| 1 — Product | 0 | 1 (1.3) | 2 | 33 % |
| 2 — Architecture | 0 | 1 (2.2, reliability **low**) | 2 | 33 % (fragile) |
| 3 — Infrastructure | 1 (3.2) | 0 | 2 | 33 % (the framework's only reliable AUTO) |
| 4 — Storage & Data | 0 | 0 | 2 | 0 % |
| 5 — Algorithm & Code | 0 | 2 (5.2, 5.3) | 1 | 67 % |
| 6 — Ease of change | 0 | 0 | 2 | 0 % |

Reading: pillar 5 is the best covered by an external audit, but entirely in SEMI
(proposals to confirm, never an automatic decision); pillar 3 carries the only really
automatable criterion (3.2, hosting region) and it is also the one with the most
direct carbon impact; pillars 4 and 6 are out of reach of any external audit — these are
interviews to conduct, not measurements to automate.

## Pillar to explore first: Algorithm & Code, bridging with Infrastructure (3.2)

Two reasons converge toward pillar **5 — Algorithm & Code**, with criterion **3.2 —
hosting region** as a natural extension:

1. **It is the pillar best covered by external evidence** (67 %), and the criteria
   concerned (5.2 journey friction, 5.3 comfort on old devices) concern quantities that the
   `analyse-parcours` audits already measure: mobile Core Web Vitals, JavaScript
   weight, number of requests and reloads per journey.
2. **The audits already carried out already produce this data**, without it being linked to the
   framework: the `ants-permis`, `octo.com` and `audit-30000-octo` reports document dead
   JS, dead CSS, cache, compression and third-party domains — enough to feed a first
   SEMI estimate of 5.2 and 5.3, and a quantified caveat on 3.2 as soon as the network
   origin / CDN is known from the HAR.

**General recommendation, low-cost, generalizable to any audit already produced**: build an explicit
mapping "HAR/Coverage audit output field → criterion level" for this
subset (5.2, 5.3, 3.2) before aiming at all 16 criteria. It is the subset where
the gain — reliable SEMI pre-fill, consistency between audits already produced and the
pillar framework — is the most immediate given the work already done, without waiting for the
writing of edge cases (US 2.28) on the other 13 criteria.

Conversely, pillars 4 (Storage & Data) and 6 (Ease of change) will
gain nothing from work on HAR/Coverage audits: these are interviews to conduct, not
measurements to automate.

---

## What this document does not do

- It decides no trade-off, including the added point n° 8.
- It does not check the content of the workbook `EROOM-diagnostic-rapide-univoque-v0.1.xlsx`.
- It proposes neither code nor questionnaire modification: only a cross-reading
  between the source document and the real state of this repository (files present, audits already
  produced).
- It does not locate the missing files (probably in the EROOM
  application's repository): their absence here is noted, not explained.
