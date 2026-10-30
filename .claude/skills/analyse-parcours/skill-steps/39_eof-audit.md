# Step 39 - Optimization potential (EOF framework)

## Overview

This step automatically fills what can be filled of the
EOF-V.1.1 framework (EROOM Optimization Framework, Boavizta) for the audited site,
from the data already collected. It relies on:

- `eof-reference.json`: produced by the `.claude/skills/eof/` skill
  (54 detailed criteria over 6 dimensions + 16 questions from the
  0-Quick diagnostic), **never regenerated from this step**
- `.claude/skills/analyse-parcours/scripts/eof_criteria_mapping.py`: mapping table
  criterion → data field → rule → confidence
- `.claude/skills/analyse-parcours/scripts/run_eof.py`: evaluates each
  criterion, computes the scores per dimension, generates the radar
- Three Phase 1 extractors (2026-09-03, plan `eof-questionnaire`), now
  produced **automatically** by the DISPATCH orchestration of step 25
  (`skill-steps/25_dispatch-orchestration.md`) — no need to launch them
  manually before `run_eof.py`:
  - `parse_html_criteria.py <source_dir>` (Wave 2, block `extractor-html-css`,
    depends on `env-data.json`) — live re-fetch of the already audited pages (the
    captured `.har` does not contain the HTML/CSS bodies): writes
    `html-css-criteria.json`
  - `analyze_security_headers.py <source_dir>` (Wave 1, block
    `extractor-security-headers`) — local security score from the
    headers already in the `.har`: writes `security-headers-analysis.json`
  - `scan_wellknown.py <source_dir>` (Wave 2, block `extractor-wellknown`,
    depends on `env-data.json`) — direct fetch of security.txt/robots.txt/
    sitemap.xml: writes `wellknown-scan.json`
  For an isolated manual re-run, the CLI commands remain the same
  (see `25_dispatch-orchestration.md` for the dependency details).
- Extended `collect_cwv_pagespeed.py` (same PageSpeed Insights API calls,
  accessibility + best-practices categories in addition to performance):
  adds `accessibility_score_pct` / `best_practices_score_pct` to
  `cwv.json`. The Wave 1 block `collect-cwv` now calls
  this extended variant (`--strategy both`) directly from the first
  pass — the note "re-run with --strategy both" now only concerns
  **existing** audits, generated before this switch.

**This step NEVER reads the Google Sheet nor the human-readable Markdown of the
`eof` skill** — deliberate decoupling (cf. `tmp/handoff.md`, architecture plan) so
that a re-synchronization of the framework can never break
comparability between two audits done at different dates.

-----

## MANDATORY WARNING

Out of the 54 detailed criteria, a manual review (2026-09-03)
showed that only **4 are automatable** (checkbox ticked) and **6 partial**
(contextual indicator shown in the appendix, never a validated answer). The
**44 others remain "I don't know"** by construction: they are
organizational or product questions (code reviews, tests,
documentation, knowledge of target users...) that no
technical audit data can inform.

This reminder must appear:
- in the summary displayed to the user after execution
- in the warning banner of the report section (already handled by
  `_section_eof()`, do not remove it)

The 16 questions of 🏦 0-Quick diagnostic are **never** filled
automatically (different 1-to-5 scale, explicit decision of
2026-09-03): they appear as a preview only, before the radar of the 6
detailed dimensions.

-----

## Triggering

**Automatic**, not a command to type: after Waves 1 + 2 of
Step 25 (at minimum `har-analysis.json` + `coverage-analysis.json`
present, the other Wave 1/2 files best-effort), before Step 40
(HTML report) — so that the first generated report already contains this
section. If `eof-reference.json` is absent (skill `eof` never run),
silently skip this step and continue to Step 40 without an EOF section
(backward-compatible report).

Re-runnable at any time (e.g. after a new data collection):

```bash
python3 .claude/skills/analyse-parcours/scripts/run_eof.py <source_dir>
```

-----

## Execution

1. Check the presence of
   `.claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - English/eof-reference.json`.
   Absent -> report "EOF framework not found, run the `eof` skill if
   an EOF section is wanted in the report" and skip the step.
2. Run `run_eof.py <source_dir>` (source_dir = the audit folder,
   containing `env-data.json`/`cwv.json`, with its `audit/` subfolder
   for `har-analysis.json`/`coverage-analysis.json`).
3. The script writes into `<source_dir>/`:
   - `eof-audit-results.json` - light summary, consumed by
     `generate_report_html.py::_section_eof()`
   - `eof-filled.md` - complete readable framework (answer or "I don't
     know", confidence, source, for the 54 + preview of the 16 of the Quick
     diagnostic)
   - `eof-radar-<domain>.svg` - radar of the 6 dimensions (a dimension with
     no answer at all displays "N/A", never a fake 0%)
4. Display the script's stdout summary (number of criteria answered
   automatically / 54, overall optimization potential).

-----

## HTML report integration

`generate_report_html.py` automatically detects `eof-audit-results.json`
and `eof-radar-*.svg` (in `audit_dir` or its parent) and inserts a section
"Optimization potential (EOF framework)" between "Environmental impact
(CO2e)" and "Appendices". If `eof-audit-results.json` is absent, the section is
simply omitted.

Section content:
- Warning banner (real automatic coverage ratio)
- Preview 🏦 0-Quick diagnostic (16 questions, never filled, placed BEFORE the
  radar)
- KPI: criteria answered / 54, overall optimization potential (weighted
  average, over real answers only)
- Radar of the 6 detailed dimensions
- Table of scores per dimension

An **appendix** ("Detail of the 54 EOF criteria", in the Methodology
& hypotheses section) traces criterion by criterion: answer or "I don't know",
confidence level (badges `_confidence_badge()`, same codes as the rest
of the report), source/data used.

Regeneration after a data change:
```bash
python3 .claude/skills/analyse-parcours/scripts/run_eof.py <source_dir>
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <source_dir>/audit
```

-----

## What remains explicitly OUTSIDE this step

- Extending automation to "no data" criteria: organizational/product
  nature, not a technical defect to fix.
- Automatically filling 🏦 0-Quick diagnostic: explicit decision not to
  do it (different scale, never reliable enough data).
- Modifying `eof-reference.json` or the Google Sheet from this step:
  strictly reserved for the `eof` skill, on explicit request only.

-----

## Key decisions (reference)

- Total decoupling from the `eof` skill: this step only reads
  `eof-reference.json`, never the Sheet nor the human-readable Markdown.
- Generic mapping table (`eof_criteria_mapping.py`),
  reusable for any audited site — not limited to octo.com.
- Strict anti-fabrication policy: "automatable" may tick a
  checkbox, "partial" only shows an indicator in the appendix (never ticked),
  absence from the table = always "I don't know".
- Radar: a dimension without an answer displays "N/A", never a fake 0%
  (0% would mean "strength everywhere", not "unknown").
