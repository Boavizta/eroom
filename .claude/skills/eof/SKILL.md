---
name: eof
description: >
  Generates or regenerates the blank Markdown template of the EOF-V.1.1 reference
  framework (EROOM Optimization Framework) from its Google Sheet source, with a
  sample SVG radar for the synthesis. Activates when the user
  mentions "EOF", "EROOM Optimization Framework", "EOF reference framework",
  "EOF template", "EOF radar", or "/eof". Current scope: only the
  production of the blank template (not yet filling in a real audit
  nor its integration into the analyse-parcours HTML report — cf. "What this
  skill does not do yet").
version: 1.0.0
---

# Skill: EOF (EROOM Optimization Framework)

## Overview

EOF-V.1.1 is a self-assessment framework for the optimization maturity
of a digital service (9 tabs: presentation, a quick diagnostic with 16
criteria, 6 detailed pillars totaling 54 criteria, a synthesis). It
exists as a **public Google Sheet**, the source of truth:
https://docs.google.com/spreadsheets/d/1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0/edit

This skill produces a **blank Markdown template** of this framework, so that
answers can be entered directly in a text file rather than in
the Google Sheets interface.

## What this skill does not do yet

- Fill in the template for a real case (e.g. octo.com) from data
  already collected in an audit (analyse-parcours, e-footprint).
- Compute a radar with real values.
- Integrate with the HTML report produced by `analyse-parcours` (`generate_report_html.py`).

These three points are scoped (cf. the most recent `tmp/handoff.md` at the time
of writing) but not implemented: to be done in a dedicated session, the
criterion-by-criterion classification work is voluminous.

## Invocation

`/eof` or any request to regenerate/update the EOF template.

## Steps

### 1. The source of truth is versioned: do not re-download it without a reason

The raw export of the 9 tabs is kept in **`docs/source-sheet/`**, versioned, with
its own `README.md`. It is the snapshot of the Sheet as of **2026-09-02**, and it is the
only point of comparison allowing us to know whether EROOM has evolved its framework.

Check whether the Sheet has changed, without modifying anything:

```bash
.claude/skills/eof/scripts/verify_source_sheet.sh
```

Exit code 0 if the Sheet is identical to the snapshot, 1 if a tab changed or if
a download fails. The script also detects a Sheet that became private or a deleted
tab, cases that return HTML with a 200 code and would otherwise be compared silently.

To adopt an evolution, then see exactly what EROOM changed:

```bash
.claude/skills/eof/scripts/verify_source_sheet.sh --refresh
git diff .claude/skills/eof/docs/source-sheet/
```

The Sheet really evolves: verified on 02/09/2026, it had been enriched from 43 to 54
criteria since the Excel export initially provided by EROOM.

The script carries the Sheet identifier and the 9 tab `gid`s. The `gviz` API is
mandatory, the classic CSV and XLSX exports fail on a one-time-token redirect. The raw
recipe, for the record:

```bash
BASE="https://docs.google.com/spreadsheets/d/1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0/gviz/tq?tqx=out:json"
curl -sL -A "Mozilla/5.0" "${BASE}&gid=1677462955" -o .claude/skills/eof/docs/source-sheet/read-me.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=296916801"  -o .claude/skills/eof/docs/source-sheet/quick-diag.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=2022239731" -o .claude/skills/eof/docs/source-sheet/product.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=615231881"  -o .claude/skills/eof/docs/source-sheet/architecture.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=1603246930" -o .claude/skills/eof/docs/source-sheet/infrastructure.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=31675448"   -o .claude/skills/eof/docs/source-sheet/storage.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=1046049603" -o .claude/skills/eof/docs/source-sheet/algo-code.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=24436077"   -o .claude/skills/eof/docs/source-sheet/ease.json
curl -sL -A "Mozilla/5.0" "${BASE}&gid=958616182"  -o .claude/skills/eof/docs/source-sheet/synthesis.json
```

⚠️ These JSON files used to live in `tmp/eof-gviz/`, a git-ignored directory, so
saved nowhere. A copy still sits there, worthless: the reference
is now `docs/source-sheet/`. Never reintroduce a path under `tmp/` here, that
would lose the point of comparison with EROOM's Sheet.

### 2. Build the Markdown template

```bash
python3 .claude/skills/eof/scripts/build_template.py \
  ".claude/skills/eof/docs/source-sheet" \
  ".claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - English/EOF-V.1.1 (EROOM Optimization Framework) - Full reference.md"
```

The script is deterministic (no calculation and no transcription by a model):
it reads the 9 JSON files, automatically detects the evaluation format per tab
(3 different formats exist — cf. `build_template.py` at the top of the file),
and writes a **100% blank** template (no box pre-checked, except "Impact
level" which carries a fixed piece of data from the framework, not an answer).

### 3. (Optional) Regenerate a sample radar

```bash
python3 .claude/skills/eof/scripts/generate_radar_svg.py output.svg
```

Produces a 6-axis SVG radar (circular grid, navy blue `#2D4675`,
contrast ~9.35:1 compliant with RGAA) with fictitious values — useful to
preview the rendering before computing a real radar on a real case.

## Files

- `scripts/build_template.py` — generates the Markdown template from the gviz JSON files
- `scripts/generate_radar_svg.py` — generates an SVG radar (reusable `radar_svg()` function)
- `docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - English/`
  - `EOF-V.1.1 ... (1).xlsx` — Excel provided as a fallback (partially outdated, cf. § retrieval)
  - `EOF-V.1.1 ... Full reference.md` — the delivered blank template
  - `logo1.png` / `logo2.png` — logos extracted from the Excel (logo1 white/transparent, invisible on a white background, flagged in the .md)
- `docs/univocal-version-essay/` — old "univocal quick diagnostic" doc, **out of scope**, do not rework

## Diagram

`documentation/diagrammes/eof-pipeline-outils.puml/.svg/.pdf` (2 pages) — register
in `.claude/skills/diagrammes-analyse-parcours/SKILL.md`, section "Diagram 5".
