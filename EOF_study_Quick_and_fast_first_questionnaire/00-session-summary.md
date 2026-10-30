# Session summary - quick diagnostic + ease of change study

This document summarizes, on one page, what was done and found during this session (2026-09-08). The detail is in files 01 to 04 of the same directory.

## What was done

Directory created: `EOF_study_Quick_and_fast_first_questionnaire/`, with 5 files: `handoff_first_quick_questionnaire.md`, `01-criteria-inventory.md`, `02-automation-inventory.md`, `03-replay-octo.com.md`, `04-synthesis-and-recommendation.md`, and this summary.

No production file was modified. All the work was done read-only on the EOF-V.1.1 reference, the current questionnaire and the data already collected on octo.com.

## Conclusion, honestly

On the 26 criteria concerned (16 from the "0 - Quick diagnostic" dimension, 10 from the "6 - Ease of change" dimension), there is no big trick to find to reduce the number of questions. The current ratio (25 questions for 26 criteria, i.e. 1.04 criterion per question) is already close to the structural floor of the reference, for three overlapping reasons:

1. **16 of the 21 non-automated criteria are purely internal facts about the team** (available skills, backlog content, engineering practices, access governance). They are invisible from outside the service, whatever the audit tool used.
2. **The only possible overlap without loss of precision is already exploited.** The quick diagnostic (dimension 0) can only be cleanly combined with dimension 6 (dimensions 1 to 5 have a "Not applicable" rung that dimension 0 does not have, which would prevent merging without impoverishing the questionnaire). This overlap (`0.3` + `6.10`, availability) is already merged into a single question.
3. **The QCM format with independent checkboxes has already been tested on almost this same scope** (2026-09-07, 21 criteria targeted in 7 questions) and gave a real result worse (9 criteria settled out of 21) than one direct question per criterion. See the next section for the detailed reasoning.

## The only safe gain found

The question on `0.16` (hosting country / carbon intensity) is asked for nothing: it is already solved by an automatic datum already collected (`env-data.json`, exact duplicate of criterion `3.3`). Removing it from the questionnaire would bring the ratio to 24 questions for 26 criteria, i.e. 1.083, without losing the slightest precision.

Three other leads would improve the quality of the answers, not their number: recalling in questions `0.7`, `0.11` and `0.12` the data already measured (detected architecture, Core Web Vitals scores), and extending the public-page search tool to look for a data policy page for criterion `0.15`. None of these leads was coded: they are recommendations for a later session, not production changes.

## Warning flagged in the handoff

Mid-session, another agent modified production EOF audit files (`audits/octo.com/eof-audit-results.json`, and a new step `39b_questionnaire-eof.md`), in addition to its initial work on HAR analysis. No conflict with this study (nothing was written in these files here), but any resumption of this work must first check the state of `tmp/handoff.md`.

## Why the QCM format (independent checkboxes) is not retained here

A QCM block presents several statements on the same screen, each linked to one or more criteria, and the respondent ticks those that apply. The problem is not grouping questions on screen, it is what this format offers beyond a direct question: a **grouped escape hatch**. On the example shown upstream of this study, each screen has an option of the type "none of these apply" or "I don't know / check with another team". A direct question ("What is your availability constraint level?") offers no such dodge: the respondent must pick a precise rung on the scale, even approximate.

This is not a hypothesis, it was really tested on 2026-09-07, on a run targeting 21 criteria of this same scope (quick diagnostic + ease of change) in 7 QCM questions. Real result: **only 9 criteria out of 21 received a usable answer**, the other 12 stayed at "I don't know" because the escape hatch was taken several times. A direct question per criterion can go up to 21/21 if the respondent goes all the way.

Two effects make it worse with the QCM:
- **The escape hatch is grouped**: a single "none of these" click closes several criteria at once, whereas with a direct question, hesitating on one criterion does not affect the neighboring criteria.
- **Even when a box is ticked**, it often gives the same answer to several criteria at once. That only works without loss of precision if the grouped criteria really concern the same fact (like `0.3` and `6.10`, which both talk about availability constraints). Grouping criteria that are not rigorously identical amounts to guessing an answer rather than measuring it.

The goal of the job is to maximize the number of criteria effectively answered, not to minimize the number of screens for its own sake. On this precise scope, the real numbers show that the QCM loses on the objective that matters, even if it wins on the number of screens displayed. That is why it is not retained, and reopening it would require a mechanism really different from the one already tested (for example a mandatory box per line, without escape hatch), which would in fact amount to a disguised direct question.
