# Step 39b — EOF questionnaire (generation and review)

> Source: skill-steps/39b_questionnaire-eof.md. Return: SKILL.md step 40.

## Overview

Out of the 54 detailed criteria of the EOF-V.1.1 framework, Step 39 (`run_eof.py`)
only decides a small part automatically. The **residual** (criteria without
an answer, or answered "🤔 To be assessed" / "⌛️ Assessment in progress") can be asked
as checkbox questions to the audited service. Two scripts already
written and tested do this work:

- `generate_questionnaire.py`: reads `eof-audit-results.json` (Step 39) and
  `questionnaire-blocs.json`, produces a single Markdown file
  `questionnaire-eof.md` containing only the still-useful questions, sorted
  by decreasing yield (the blocks that unlock the most criteria
  come first).
- `parse_questionnaire.py`: reads `questionnaire-eof.md` once FILLED IN by the
  audited service, writes `lots/questionnaire-review.json` (standard lot output
  contract, provenance `"stated"`).

This step corresponds to wave `4-questionnaire` of
`process/lots-manifest.json` (lots `questionnaire-generation` and
`questionnaire-review`), but documents only the two existing scripts,
not the reconstruction of the full multi-lot pipeline (cf. "What remains
explicitly OUTSIDE this step").

-----

## MANDATORY WARNING

Never a blank questionnaire in `audits/`. `generate_questionnaire.py`
refuses by default to write to a path
containing `audits` (exit code 2, explicit error message). Reason: a
generated questionnaire is blank, all its checkboxes remain to be ticked; if it
lands in `audits/<domain>/`, it can be sent back to the client as if it
were up to date when it contains no answer at all.

- **Working generation (systematic)**: output to `/tmp`, never to
  `audits/`.
- **`--in-audit-dir`**: reserved for the moment when the questionnaire is
  actually being sent to the client right away. Do not use it
  "to see" or out of habit.

-----

## Triggering

**Manual** step, not automatic like Step 39: it is a
mission decision (is the questionnaire going to the audited service now?), not
a calculation that must be redone at each analysis. Placed after Step 39
(`eof-audit-results.json` must exist), before or in parallel with
Step 40 (the report).

-----

## Generation

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py <audit-dir> --output-dir /tmp/questionnaire-<domain>
```

- `<audit-dir>` = the folder containing `eof-audit-results.json` (that of
  Step 39, e.g. `audits/<domain>/`).
- Output: `/tmp/questionnaire-<domain>/questionnaire-eof.md`, a single
  file, not a product/technical split (see manifest note below).
- If the residual is empty (Step 39 already covered everything), the script
  writes nothing and displays `No block to display (empty residual)`: this is not
  an error.
- Re-read the generated file before any sending: nothing automatically guarantees
  that it fits the mission context.

For the actual sending to the audited service, regenerate directly in the
audit folder:

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py <audit-dir> --in-audit-dir
```

Non-regression checks: `generate_questionnaire.py --autotest`
(15 cases).

-----

## Review (once the questionnaire comes back filled in)

```bash
python3 .claude/skills/analyse-parcours/scripts/parse_questionnaire.py <audit-dir>
```

- Human prerequisite: `<audit-dir>/questionnaire-eof.md` must be the
  **filled-in** version from the audited service (not the blank version produced
  under `/tmp`).
- Writes `<audit-dir>/lots/questionnaire-review.json`.
- A checkbox left empty stays empty: no default answer, no worst
  case. A block without exactly one checkbox ticked contributes nothing.

Non-regression checks: `parse_questionnaire.py --autotest`
(7 cases).

-----

## WARNING

Never re-run `run_eof.py` alone after a questionnaire review.
`run_eof.py` (Step 39) rewrites `eof-audit-results.json` only from
automatic data: it **never** re-reads `lots/questionnaire-review.json`.
Re-running it alone after a questionnaire review therefore silently erases
the answers already contributed.

Merging the lots (including `questionnaire-review.json`) into
`eof-audit-results.json` is the role of `process/merge_lots.py`:

```bash
python3 process/merge_lots.py <audit-dir>
```

Then regenerate the report (Step 40) to reflect the new answers.

-----

## What remains explicitly OUTSIDE this step

- Wiring the LLM judgment lots (`quick-diagnostic-judgment`,
  `dimension-1-judgment` to `dimension-6-judgment`, `go-no-go-gate`): all
  `"state": "to_write"` in `process/lots-manifest.json`, they are not
  (yet) scripted steps of this skill.
- Automating the merge (`merge_lots.py`) or the report regeneration
  after review: mentioned above as the logical next step, not triggered
  automatically by `parse_questionnaire.py`.
- Designing a new process: the two scripts documented here already exist
  and are tested (`--autotest`), this step only says when and
  how to run them.

-----

## Key decisions (reference)

- A single `questionnaire-eof.md` file, never a
  product/technical split: explicit decision (the old two-file split
  sent 3 recipients out of 4 into both files at once). Note:
  `process/lots-manifest.json` (lots `questionnaire-generation` and
  `questionnaire-review`) still mentions `questionnaire-produit-usage.md`
  and `questionnaire-technique.md`: known drift with the current code, not
  corrected by this step (cf. workstream report).
- The questionnaire is **generated**, never hand-written: the
  automatic coverage differs from one service to another, a fixed questionnaire would
  be wrong for the next service.
- An empty checkbox stays empty: no default answer, no worst case.
