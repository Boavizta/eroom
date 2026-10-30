# Consolidated dashboard - 26 criteria (quick diagnostic + ease of change)

This table brings together, criterion by criterion, what the journey analysis and the current tools can fill in automatically, the duplicates between part 0 and part 6, and the compression status of each question. Figures corrected on 2026-09-08 (an erroneous verbal synthesis from a sub-agent had been taken without recalculation in the first versions of files 02 and 04: "16 non-automated out of 21" instead of the correct count below).

⚠️ **Update of 2026-09-10, after reintegrating this study into the main handoff**
(jobs 36 to 40, detail in `tmp/handoff.md` sections 0-QUATERVICIES and 0-QUINVICIES):
- **Job 36**: the floor "24 questions for 26 criteria" announced below as a target
  is in fact **already reached in production**, verified by really rerunning `generate_questionnaire.py`
  on `audits/octo.com`: `0.16` no longer appears in the questionnaire, removed
  by a general residual mechanism (not a job dedicated to `0.16`). Nothing to do here.
- **Jobs 37, 38, 39**: the reminders for `0.7`, `0.11`, `0.12` and `0.15` (wiring included) are
  **done and committed** (`671b45d`, `3f45a3f`). The table below now reflects this status.
- **Job 40** (alternative source to the sitemap for `0.10`): left aside, not verifiable on
  octo.com (the site has neither `robots.txt` nor `sitemap.xml` at all, confirmed real failure).

## Detail per criterion

| Criterion | Dimension | Short label | Automation today | Duplicate with | Compressible without loss |
|---|---|---|---|---|---|
| 0.1 | 0 | Impact of the service disappearing | Not automatable (structural) | - | No |
| 0.2 | 0 | Redundancy/duplicates in the IS | Not automatable (structural) | - | No |
| 0.3 | 0 | High availability (SLA/SLO/DRP) | Not automatable (structural) | **6.10** | **Yes, already done** |
| 0.4 | 0 | Technical dependencies | Partial (wired hint: third-party domains from the HAR) | - | No |
| 0.5 | 0 | Source code accessible to the team | Not automatable (structural) | - | No |
| 0.6 | 0 | Skills available to maintain the service | Not automatable (structural) | - | No |
| 0.7 | 0 | Architecture complexity | Partial, **wired on 2026-09-10** (CSP + CDN hint displayed, `diag_context_0_7`) | - | No |
| 0.8 | 0 | Infrastructure size | Not automatable (weak proxy rejected) | - | No |
| 0.9 | 0 | Stored data volume | Not automatable (weak proxy rejected) | - | No |
| 0.10 | 0 | Functional complexity | Partial (wired, inert on octo.com: sitemap absent) | - | No |
| 0.11 | 0 | UX/UI smoothness | Partial, **wired on 2026-09-10** (CWV hint all strategies, `diag_context_0_11`) | - | No |
| 0.12 | 0 | Old-hardware compatibility | Partial, **wired on 2026-09-10** (mobile-only CWV hint, `diag_context_0_12`) | - | No |
| 0.13 | 0 | Product backlog (perf/improvement) | Not automatable (structural) | - | No |
| 0.14 | 0 | Optimized features | Not automatable (weak proxy rejected) | - | No |
| 0.15 | 0 | Data deletion/archiving policy | Partial, **wired on 2026-09-10** (reminder if a retention declaration is found on a public page, `diag_context_0_15`; `None` on octo.com, no declaration published) | - | No |
| 0.16 | 0 | Hosting country / carbon intensity | **Automatable (already ticked)** | exact duplicate of `3.3` | **Yes, question to remove** |
| 6.1 | 6 | Observability setup | Partial (wired hint: security grade) | - | No |
| 6.2 | 6 | Code reviews / pair programming | Not automatable (structural) | - | No |
| 6.3 | 6 | CI/CD process | Partial (wired hint: Last-Modified from the HAR) | - | No |
| 6.4 | 6 | Non-regression tests | Not automatable (structural) | - | No |
| 6.5 | 6 | Business/technical decoupling | Not automatable (weak proxy rejected) | - | No |
| 6.6 | 6 | Software quality indicators | Partial (wired hint: CWV + security + security.txt) | - | No |
| 6.7 | 6 | Complete documentation | Not automatable (structural) | - | No |
| 6.8 | 6 | Duplicated code | Partial (wired hint: Lighthouse) | - | No |
| 6.9 | 6 | Autonamey to deploy tools | Not automatable (structural) | - | No |
| 6.10 | 6 | High availability (mirror of 0.3) | Not automatable (weak proxy rejected) | **0.3** | **Yes, already done** |

## Global statistics (26 criteria)

| Status | Count | Detail |
|---|---|---|
| Automatable, box ticked on its own | **1** | `0.16` |
| Partial: hint displayed, human answer still required | **10** (was 9 before 2026-09-10) | `0.4, 0.7, 0.10, 0.11, 0.12, 0.15` (dim. 0) + `6.1, 6.3, 6.6, 6.8` (dim. 6) — **8 out of 10 really display a reminder on octo.com**, `0.10` stays inert (no sitemap) and `0.15` stays empty (no retention declaration published) |
| Structurally not automatable (internal fact about the team) | **15** | 9 in dimension 0 + 6 in dimension 6 |
| **Total** | **26** | |

| Duplicates found between dimension 0 and dimension 6 | Count |
|---|---|
| Pairs identified | **1** (`0.3` ↔ `6.10`, same fact: availability constraints) |
| Already merged in the current questionnaire | **1 out of 1** (no remaining margin) |
| Other duplicates searched and not found | 0 out of the 24 remaining criteria |

## Number of questions: today vs lossless floor

| | Questions asked | Criteria covered | Criterion/question ratio |
|---|---|---|---|
| Current questionnaire (production), at the time of the study (2026-09-08) | 25 | 26 | 1.04 |
| Reachable floor without loss of precision | 24 | 26 | 1.083 |
| **Current questionnaire actually verified on 2026-09-10** | **24** | 26 | **1.083** |

⚠️ **The floor is already reached in production, really verified** (real rerun of
`generate_questionnaire.py` on `audits/octo.com` on 2026-09-10): `0.16` no longer appears in the
generated questionnaire. This is **not** the effect of a job dedicated to `0.16` (job 36, never
implemented): it is a general mechanism already in place, which removes any direct question whose
criterion already carries a settled answer, whatever it is. The "25 questions" figure above was
therefore already stale when it was written (probably a static count on
`questionnaire-blocs.json`, without simulating the real exclusion).

No other compression is possible without degrading an answer, for the reasons detailed in `04-synthesis-and-recommendation.md`: most of the remaining criteria are internal facts about the team, and the only format tested to go further (QCM with independent checkboxes) lowered the real coverage rather than the number of useful questions.
