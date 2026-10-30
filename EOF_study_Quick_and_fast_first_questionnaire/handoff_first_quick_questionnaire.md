# Handoff - Study "Optimizing the quick diagnostic and ease of change"

Session of 2026-09-08. This handoff is specific to this job and lives in its own directory `EOF_study_Quick_and_fast_first_questionnaire/`, separate from the main handoff `tmp/handoff.md` (used by another agent in parallel on a different subject, HAR analysis). Do not merge the two.

## Context of the request

The user asked for an isolated job, on new files, to avoid interfering with the agent working in parallel on `tmp/handoff.md`. Finding mid-session (`git status`): this other agent first touched the HAR analysis (`analyze_har.py`, steps 20/25, `process/CHECKS.md`, `process/lots-manifest.json`), then, later in the same time window, a new step `.claude/skills/analyse-parcours/skill-steps/39b_questionnaire-eof.md` appeared and `audits/octo.com/eof-audit-results.json`, `eof-filled.md`, `wellknown-scan.json`, `html-css-criteria.json`, `lots/automatic-judgment.json` were modified (rerun of `run_eof.py`). The other agent's scope therefore also touches the EOF questionnaire area. This job wrote in none of these files (read-only), but any resumption must check the state of `tmp/handoff.md` before going further, the subject may no longer be only the HAR.

Goal of the job, as clarified with the user over the session (several framing back-and-forths, see decisions below): on the 26 EOF criteria of the "0 - Quick diagnostic" dimension and the "6 - Ease of change" dimension, find a strategy to answer the maximum number of criteria while asking the minimum number of questions to a human, relying first on the data already measured automatically by the project's tools (HAR, Core Web Vitals, Lighthouse/PageSpeed, detected technologies, security headers, carbon footprint...), without changing the EOF-V.1.1 reference nor the current production questionnaire.

## Decisions validated with the user during this session

1. The EOF-V.1.1 reference (Google Sheet) does not change. No production file is modified in this job (`questionnaire-blocs.json`, `run_eof.py`, `eof_criteria_mapping.py`, `parse_public_pages.py` remain intact).
2. New files in a dedicated directory at the project root: `EOF_study_Quick_and_fast_first_questionnaire/`, with this handoff named `handoff_first_quick_questionnaire.md` inside (name given explicitly by the user).
3. Step 1 (abstract analysis on the reference + inventory of the tools) and step 2 (replay against the data already collected on octo.com) are done in the same session, at the user's explicit request.
4. Model used: Sonnet 5, confirmed by the user, consistent with their default preference (bounded task, no architecture nor long debugging).
5. Sub-agents used for the factual research (reference extraction, inventory of automatic data) to preserve the main session's context. A first fork attempt failed silently (0 tools called, just returned text); the research was then rerun with fresh `general-purpose` agents and imperative instructions, successfully.

## What was found (detail in files 00 to 05 of this directory)

- Current questionnaire: 25 questions for 26 covered criteria (ratio 1.04 criterion/question). No coverage gap.
- A single existing and legitimate grouping: `0.3` + `6.10` (same underlying fact, availability). It is the only clean structural overlap between dimension 0 and another dimension (dimensions 1 to 5 have a "Not applicable" rung that dimension 0 does not have, which forbids any crossing with them without impoverishing the questionnaire).
- Real automation: 1 criterion out of 26 (`0.16`), confirmed identical in the abstract and on octo.com's real data. 9 criteria have a "partial" hint (never an automatic answer, just a displayed reminder). 15 criteria are internal facts about the team, no external datum can answer them. 1 criterion (`0.15`) is not structurally out of reach but is not searched by the current tooling.
- A QCM format with independent checkboxes was already tested on almost this same scope (2026-09-07, 21 criteria targeted in 7 questions) and gave a real result of 9/21 criteria settled, worse than one direct question per criterion. Do not relaunch this lead without a method clearly different from the trial already done.
- The only safe and lossless gain identified: removing the manual question on `0.16`, already solved automatically. The ratio would go from 1.04 to 1.083 (24 questions for 26 criteria).

## Conclusion of the study

On this precise scope, the number of questions is already close to the structural floor of the reference (25 asked today, 24 reachable without loss). The detail is in `04-synthesis-and-recommendation.md` and the full numbered table in `05-dashboard.md`.

## Jobs to explore to optimize the automation of answers (to prioritize if this job is resumed)

These jobs do not reduce the number of questions (the floor is already reached, with one exception: removing the redundant question on `0.16`, see below). Their principle: when we cannot answer a criterion with certainty, at least **assist** the human answer with the data already collected "on disk" (files `env-data.json`, `cwv.json`, `security-headers-analysis.json`, `wellknown-scan.json`, HAR, CSP...), rather than leaving the question without any landmark. Full detail and justification in `04-synthesis-and-recommendation.md`, section "Jobs to explore to optimize the automation of answers".

1. **Extend `parse_public_pages.py`** with search patterns on data retention/deletion/archiving, to move `0.15` beyond "no data". The only job that can gain a criterion beyond the simple reminder.
2. **Wire a measured-fact reminder for `0.7`** (CSP + CDN already detected).
3. **Wire a measured-fact reminder for `0.11` and `0.12`** (Core Web Vitals scores already collected in `cwv.json`).
4. Check whether an alternative source to the sitemap exists for `0.10` (mechanism already wired but inert on sites without `sitemap.xml`, not a priority).
5. Do not try to automate the 15 structural criteria (internal facts about the team): no tool will ever answer them from outside the service.

These jobs require touching production files (`run_eof.py`, `eof_criteria_mapping.py`, `parse_public_pages.py`), hence a dedicated decision and session, outside this study's scope.

## State at the end of this session

Done: the 6 files of this directory (`00-session-summary.md`, `01` to `05`) and this handoff. No production file touched. No octo.com data modified (read-only).

## If someone resumes this job

- Do not relaunch the search for another QCM grouping on this scope without a really new method: it is already documented as tested and rejected (file 04).
- Prioritize the 5 automation jobs listed above, plus removing the redundant question on `0.16` (safe gain of 1 question, provided it is confirmed that this is not a voluntary confirmation).
- Before touching `process/lots-manifest.json` or `process/CHECKS.md` to register an official lot, check that the other agent has finished and committed its changes on these same files, including those touching the EOF (`eof-audit-results.json`, `39b_questionnaire-eof.md`, not only the HAR).
