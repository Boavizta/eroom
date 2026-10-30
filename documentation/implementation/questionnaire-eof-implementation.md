-----
EOF questionnaire implementation
-----

Date: 2026-09-07
Author: Claude Agent (Sonnet session)
Status: Complete, autotests validated

## Context

Decision of 07/09/2026: cover the EOF radar with a generated and prioritized questionnaire. This implementation produces two Python scripts that generate and parse Markdown questionnaires to complete an existing EOF audit.

## Deliverables created

Two scripts in `.claude/skills/analyse-parcours/scripts/`:

1. **`generate_questionnaire.py`**
   - Reads `eof-audit-results.json`, `eof-reference.json` and `questionnaire-blocs.json`
   - Generates `questionnaire-eof.md` (a single file)
   - Computes the residual (criteria without a useful verdict)
   - Schedules the blocks by decreasing yield (number of criteria covered), then phase "gate" before "detail"

2. **`parse_questionnaire.py`**
   - Reads `questionnaire-eof.md`
   - Produces `lots/questionnaire-review.json`
   - Checks exactly one checkbox per block
   - Respects the lot output contract (5 root keys, null keys omitted)
   - Emits a `measurement` block compliant with the measurement state convention

## What the autotests cover

⚠️ **No case count is written here, on purpose**: a copied number becomes wrong at the
first added case, and then lies without anyone noticing. To know the real state, run
the `--autotest` commands below and read their exit code.

**`generate_questionnaire.py --autotest`** covers:
- Direct block on a detailed criterion (1.x to 6.x)
- Direct block on a quick diagnostic question (0.x, check absence of max_potential)
- Criterion with answer "🤔 To be assessed" in the residual (crucial rule)
- Composite block with already decided criteria (marker `<!-- already-decided:... -->`)
- Gate ordering before detail
- Display-time cleanup of the "I don't know" mention glued to the worst case
- Numeric sorting of identifiers (`0.2` before `0.10`)

**`parse_questionnaire.py --autotest`** covers:
- Direct block, checkbox checked (verification that coefficient is mandatory for a detailed criterion)
- Quick diagnostic without coefficient (contractual rule)
- "I don't know" checkbox = context only, never an answer
- Empty block (no checkbox checked) = nothing poured
- Two checkboxes checked = nothing poured (error reported)
- Already decided criterion ignored
- (Generator/parser round trip: covered implicitly)
- Measurement block compliant with the convention: file absent = `read_error`, empty file = `not_found`, answered file = `ok`

## Key decisions made

### 1. The residual includes "🤔 To be assessed" and "⌛️ Assessment in progress"

**Reason**: These answers have a coefficient of 0 and count as answers in the rest of the
code, but they DECIDE NOTHING. If we do not re-ask them, the criterion remains a
detectable false zero.

**Impact**: A criterion with these answers is re-asked in the questionnaire.

### 2. Options of "direct" blocks read from the framework

**Reason**: Avoid any divergence between the block library and the framework. Options are
never copied.

**Impact**:
- Detailed criterion: read `evaluation_options`
- Quick diagnostic question: read `screens`

### 3. Scheduling by decreasing yield on the remaining criteria

**Reason**: Single and priority axis — minimize the number of questions asked, maximize the
number of criteria answered, and as precisely as possible. Questions that inform SEVERAL
criteria come first.

**Impact**: Yield is computed on the criteria REMAINING in the residual. A block whose
measurement already decided part of them automatically drops in the order. Real example: the
"journey and screens" block falls to 41st position because criterion 1.13 was already
decided by the measurement, so it no longer brings but one criterion.

**Structure**: The questionnaire keeps TWO PARTS (gate then detail), with sorting by
decreasing yield inside each. It is not a global sort, and that is deliberate: the gate
decides whether an in-depth diagnosis is worth it.

**Follow-up measurement**: Session 19 showed that this sort only saves 4.5 questions out
of 37 compared to a random draw. The sort is kept because it costs nothing and lets the
interviewee stop while knowing what they are leaving out, but no compaction gain should be
expected from it. See the section "Session 19: the ceiling of the current format, measured".

### 4. A single file, the recipient is no longer a sorting axis

**Decision**: `questionnaire-eof.md` replaces the two files `questionnaire-produit-usage.md`
and `questionnaire-technique.md`.

**Reason**: The split routed nothing. Out of 4 recipients, 3 received questions in BOTH
files. Sending "the product file" to the product manager hid 5 questions that concerned
them and gave them 5 that did not. Measured distribution of the 62 questions by recipient:
development team 30, product manager 16, infrastructure operations 12, the person who
manages the data 4.

The recipient is still written in the title of each question, in the form "to check with the
development team". Classifying the document by recipient was explicitly REJECTED: the role
split depends too much on each client's organization.

### 5. "I don't know" checkbox added to each block

**Reason**: Distinguish "we asked and nobody knows" from "nobody asked". Avoids
manufacturing a false zero that makes an ignored service indistinguishable from an
exemplary service.

**Impact**: The parser produces a `context` but NEVER an `answer` for this checkbox.

### 6. Provenance = "stated", category = "no_data"

**Reason**: Lot contract — a checkbox ticked by the audited service, without evidence, comes
from no collected data.

**Impact**: All poured criteria carry these fixed values.

### 7. Strict Markdown format

**Reason**: Project style guidelines (macOS TTS reads `-----` separators letter by letter).

**Impact**:
- Separators in `-----` only
- Straight quotes `"`
- No em dash

### 8. Coefficient mandatory for detailed criteria, absent for the quick diagnostic

**Reason**: Lot validator rule. The framework does not define a coefficient for `0.x`
questions.

**Impact**: The parser omits the `coefficient` key for quick diagnostic questions.

## Respected contractual formats

### Block library (input, do NOT modify it)

```json
{
  "version": 1,
  "blocks": [
    {
      "id": "...",
      "file": "product-usage" | "technical",  (vestigial, no longer used)
      "phase": "gate" | "detail",
      "title": "...",
      "interviewee": "..." (optional),
      "type": "direct" | "composite",
      "criterion": "..." (if direct),
      "question": "...",
      "help": "..." (optional),
      "options": [...] (if composite)
    }
  ]
}
```

### Generated Markdown file

- Machine markers: `<!-- questionnaire: ... -->`, `<!-- version-blocks: ... -->`
- Per block: `<!-- block:id -->`, options with `<!-- opt:n -->`, dnk checkbox with `<!-- opt:dnk -->`
- Composite blocks: `<!-- already-decided:id1,id2,... -->` if needed
- Checkbox format: `- [ ] Label  <!-- opt:n -->`

### Lot output contract

Root: exactly 5 keys `lot_id`, `generated_at`, `inputs`, `criteria`, `measurement`.

The `measurement` key is the latest addition. It carries the reading state of the
questionnaire, described further down in "The measurement block on the review lot".

Per criterion:
- `id` and `category`: mandatory
- `answer`, `coefficient`, `provenance`, `source`, `context`: optional
- **NEVER write a key whose value is null**: omit it
- If `answer` is set on a detailed criterion: `coefficient` mandatory and non-null
- If `answer` is set on a quick diagnostic question: `coefficient` ABSENT
- If `answer` or `context` is set: `provenance` AND `source` mandatory

## What is not covered

- Validation of the `questionnaire-blocs.json` file (another agent writes it in parallel)
- Generation of an empty questionnaire (if the residual is empty, no file is created)
- Handling of blocks whose ID changes between two versions of the library
- Fill-in graphical interface (out of scope: manually editable Markdown)
- Wiring into the audit pipeline (see dedicated section below)

## Traceability of bugs fixed in autotest

1. **Regex bug**: `[^-\s]+` did not accept dashes in block IDs (e.g. `test-11`). Fixed to `[^\s]+?`.
2. **Python JSON bug**: `null` instead of `None` in the autotests. Fixed in 5 places.
3. **Missing file bug**: the parser autotests did not create `questionnaire-eof.md`. Fixed by creating the file in the test temporary directory.

## Verifications performed

- **No trace of a specific audit**: no "octo.com", no IP, no `audits/something` path in the code (verified with `grep -i "octo|192\.|audits/"`)
- **Autotests run and validated**: exit code 0 for both scripts
- **Comments in French**: in accordance with the project guidelines
- **Style respected**: `-----` separators, straight quotes, no em dash

## Guardrail: refusal to write into audits/

User's decision, 2026-09-08: **only a questionnaire returned FILLED IN by the client has the
right to exist in `audits/<domain>/`.** But the generator only produces blank questionnaires,
whose checkboxes all remain to be ticked. Such a file placed in the audit folder can be sent
to the client as if it were up to date, while it contains no answer at all.

This is not a theoretical fear. The file found on 2026-09-08 in `audits/octo.com/` carried
**322 empty checkboxes and 0 ticked**, and it was additionally older than the filter feature:
its two filter questions were asked at the top instead of being placed in the detailed part,
and it carried no "IGNORE" mention. It was deleted.

The generator therefore refuses to write into a path where one component is called `audits`,
unless the `--in-audit-dir` flag is passed explicitly. It then exits with code 2 with a message
saying what it refuses, why, and what to do instead.

Recommendation: generate into `/tmp/questionnaire-<domain>`.

Three autotests cover this guardrail: refusal without flag, acceptance with flag, acceptance
without flag outside `audits/`. These are the only cases of the battery that rerun the script
via `subprocess`: they exercise `main()`, not an internal function, and therefore work with
the real framework and the real block library, which the script finds from its own directory.

## The title read by the client no longer says "gate"

User's decision, 2026-09-08. `gate` is our internal label for the screening phase, the one
that decides whether the full audit is worth it. This label was printed as-is as the title in
the document sent to the client: "Part 1: Gate questions". The word only exists in our code,
and it told the user nothing — she knows the project.

The printed title therefore becomes **"Part 1: First pass"**, and the introductory sentence
"This first pass quickly decides whether an in-depth diagnosis is relevant." The phase name
in the code, `gate`, does not change: nothing re-reads this title, neither
`parse_questionnaire.py` nor any other script.

## Reference commands

```bash
# Generate the questionnaire
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py <audit-directory> --output-dir /tmp/questionnaire-<domain>

# Parse the filled-in questionnaire
python3 .claude/skills/analyse-parcours/scripts/parse_questionnaire.py <audit-directory>

# Run the autotests
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py --autotest
python3 .claude/skills/analyse-parcours/scripts/parse_questionnaire.py --autotest

# Merge the lots (MANDATORY after parse_questionnaire.py or run_eof.py)
python3 process/merge_lots.py <audit-directory>

# Check probe health (detects measurement failures)
python3 process/validate_probe_health.py <audit-directory>
```

## Session 19, 2026-09-07: the ceiling of the current format, measured

The goal set by the user: **minimize the number of questions to maximize the number of
criteria filled in**, generically, regardless of the site used as a test bed.

State after the `0.3` + `6.10` merge: **62 questions cover the 70 criteria** and the 80.0 of
potential, i.e. **1.13 criterion per question**.

Three measurements that close false leads. They are here to prevent a future session from
reopening them on a hunch.

| Measurement | Result | What it forbids |
|---|---|---|
| Potential per question, phase `gate` vs phase `detail` | 0.60 vs 1.74 | lengthening the gate to shorten the detail is a bad trade |
| Dispersion of the `max_potential` of detailed criteria | all between 1.0 and 2.0, flat distribution | there is no heavy criterion that could be asked first to cover half the radar |
| Questions needed to cover 50 % of the detail potential | 14 out of 37, vs 18.5 when drawing at random | sorting by decreasing potential only saves 4.5 questions out of 37 |

## Session 19: the independent-checkbox format, evaluated and rejected

An earlier attempt of the project asked **multi-select** questions ("check all the
statements that apply"), each checkbox filling its own criteria, at a rate of 3 to 5 criteria
per question. Theoretical capacity: **3.0 criteria per question**, vs 1.13 for the current
single-choice format.

**This format is rejected.** On the actual run of the attempt, 7 questions targeting 21
criteria filled in 9:

| Question | Criteria targeted | Actually filled in |
|---|---|---|
| Q1 criticality and availability | 3 | 0, the checked box matched no level of the framework |
| Q2 complexity and architecture | 3 | 3 |
| Q3 functional usefulness | 3 | 1 |
| Q4 UX and data | 2 | 2 |
| Q5 engineering maturity | 5 | 3 |
| Q6 development practices | 3 | 0 |
| Q7 observability | 2 | 0 |
| **Total** | **21, i.e. 3.0 per question** | **9, i.e. 1.29 per question** |

**The real gain is 14 %, not 160 %.** The reason is by design: multi-select offers the
client a grouped escape hatch ("none of these statements" or "I don't know" for five
criteria at once), and they take it. Single choice, for its part, forces a determined
answer per question.

Four defects of this attempt, not to be reproduced:

1. **The plumbing was visible to the reader.** Annotations like "0.1 = high impact level if
   checked" and mentions "covers EOF 0.1, 0.3, 6.10" were addressed to the tool, not to the
   audited service. This is the defect that commit `104e0ec` fixed in the current
   questionnaire.
2. **Contradictory checkboxes could be ticked together.** One question offered "a deletion
   policy exists" and "no formal policy" in the same list; another, "formal availability
   target" and "a degraded mode would be acceptable", which pull the same criterion in
   opposite directions. Nothing prevented checking both.
3. **One checkbox glued together "none of these practices is in place" and "I don't know".**
   These are two opposite answers: one is a finding, the other is the absence of a finding.
   The EOF framework already makes this mistake in 8 of its levels, cf.
   `.claude/skills/eof/docs/source-sheet/REFERENCE-PITFALLS.md`. Do not repeat it.
4. **Structural loss of resolution.** 15 of the 16 quick diagnostic questions have **5
   levels** (`0.13` has 3): a checkbox can only express 2. Checking "formal availability
   target" does not distinguish 99 % from 99.99 %. On dimension 6, the intermediate level
   `🟡 Moderate effort`, with coefficient 0.5, becomes unreachable.

## Session 19: what to borrow from this attempt

The format is rejected, **the phrasing is good to take**. Three borrowings, retained by the
user in this order.

### Borrowing 1: recall in the question what the probes already measured

Have the audited service read the measured fact before answering, so that they **confirm
or correct** instead of guessing. Secondary benefit: their answer ceases to be a statement
in the air.

**Real scope, measured: 17 of the 62 blocks**, not all of them.

| | Count | Identifiers |
|---|---|---|
| Detailed criteria with a non-empty `context` and no answer | 16 | `1.4, 1.9, 1.11, 1.14, 1.15, 1.16, 2.3, 2.5, 3.2, 3.4, 3.6, 5.5, 6.1, 6.3, 6.6, 6.8` |
| Quick diagnostic questions with a non-empty `context_index` and no answer | 1 | `0.4` |
| Criteria with a `context` but **already** answered, hence no question asked | 0 | - |

The other 45 blocks have **no** measured fact to recall: the borrowing improves a quarter of
the questionnaire. Good news though: these 17 texts are **written for a human reader**, with
units and nuances, not technical dumps: they are almost reusable as-is.

### Borrowing 2: rephrase the questions as concrete statements about the service

Replace the framework's wording with a statement the client can confirm. "Disappearance of
the service = strong impact on image, recruitment, commerce" is answerable; "Are the main
components subject to high-availability constraints?" makes people hesitate. **Zero code**,
editorial work on the 62 blocks of the library.

⚠️ Non-negotiable constraint: the rephrasing applies to the `question` field and the `help`
field, **never** to the answer labels of a `type: "direct"` block, which are read from the
framework, nor to the values of the `answers` dict of a `type: "composite"` block, which must
remain exact framework labels character for character.

### Borrowing 3: a thematic title that says who to pass the question to

"Engineering maturity and knowledge of the code" indicates the interviewee, where a
criterion title does not. The `product-usage` / `technical` split already exists, the
interviewee indication does not.

## Session 19: decision on granularity and provenance

Question asked: would we accept a **coarser** answer in exchange for a question covering more
criteria, provided it is flagged in the provenance?

**Answer: the provenance axis cannot express it, and we do not modify it.**

The axis is closed to 5 values by `process/validate_lot_output.py:65`, with the precedence
`collected > estimated > stated > declared > assumed` (decision of 2026-09-11: `stated`
ranks ahead of `declared` because the client knows their technical reality directly via the
questionnaire, whereas a public declaration (ToS, legal notice) is sometimes generic,
dated, or written without technical verification). The manifest says what they mean
(`process/lots-manifest.json:11`):

> The 'stated' provenance (checkbox ticked by the client without attached evidence) ranks
> above 'declared' (public declaration found, e.g. ToS): the client knows their team and
> their technical reality directly, whereas a public declaration is sometimes generic or
> dated, written without technical verification. The 'assumed' provenance designates a
> deduction from a weak clue: it is placed last in precedence because a checkbox ticked by
> the client without evidence (stated) is worth more — the client knows their team while we
> guess from a signal that often talks about something else.

The axis therefore answers **"who claims it, and on what basis?"**, not **"how fine is the
answer?"**. Adding a 6th level would mix two natures of uncertainty on a single axis, which
the project guideline forbids, and would break the single axis shared with the e-footprint
badge table.

**Principle decision, to apply the day the question really arises**: granularity would be a
**separate marker**, never a provenance level.

The question does not arise today: none of the three retained borrowings makes an answer
coarser. It only arose with the multi-select format, which was rejected.

## Session 19: what the code already does, and what is missing for borrowing 1

State found in `.claude/skills/analyse-parcours/scripts/generate_questionnaire.py`:

| Point | State |
|---|---|
| Keys read in `eof-audit-results.json` | `id` and `answer` **only**, lines 143-153 |
| `context` and `context_index` | **not read**, that is the whole gap |
| Condition for retaining a block | lines 216-219, retained if at least one of its criteria has no answer |
| Rendering of the `help` field | lines 312-313, rendered **as-is**, wrapped in italics, no other formatting |

Lot contract, in `process/validate_lot_output.py`: the `context` field is **allowed** on a
criterion entry (lines 159-162), and `provenance` as well as `source` are **required and
non-empty** as soon as `answer` **or** `context` is non-null (lines 246-249, verbatim rule
"required if answer or context non-null").

Genericity: the measured fact is injected **at generation time**, from the audit folder. The
`questionnaire-blocs.json` library therefore contains no value from any particular site and
**stays generic**. ⚠️ To know about the control tool: `check_genericite.py` targets the `.py`
files of `efootprint_model/` by default. Pointed explicitly at the JSON library it runs and
passes. **Pointed at a Markdown file it always fails**, even on an intact file, because it
parses its targets as Python. This is not a regression: do not go hunting for it.

## Session 19: specification of borrowing 1, for the next session

Work executable by Sonnet from this section alone.

**Objective**: when a block is retained, show under the question the already measured fact
for the criterion or criteria this block covers, if it exists.

**Sources to read in the audit folder**: `criteria[].context` for the detailed criteria,
`quick_diag_overview.questions[].context_index` for the `0.x`.

**Pitfalls to handle explicitly, each has already cost the project**:

1. **A key can exist and be worth `null`.** A fallback like `block.get("context", "")`
   protects against nothing: the key is present, its value is `None`, and it displays as-is
   to the reader. Test `is not None` **and** the empty string.
2. **The injected text is addressed to the audited service, not to the tool.** Forbidden to
   include a criterion identifier, a probe name, a file or function name. This is the defect
   fixed by `104e0ec`, and the control is visual: read the generated Markdown.
3. **A `type: "composite"` block covers several criteria**, hence potentially several
   `context`s. Decide and document what we do: concatenate them, keep only one, or show
   nothing. Do not let the behavior emerge from the randomness of iteration.
4. **The recall must not assert anything more than what the probe found.** A probe that
   found nothing does not prove absence: never turn a zero into a finding.
5. **45 blocks out of 62 have no fact to recall.** The absence must be silent: no orphan
   heading, no "Recall:" followed by nothing.

**Controls to pass before any commit**:

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"
python3 .claude/skills/analyse-parcours/scripts/validate_questionnaire_blocks.py
python3 .claude/skills/analyse-parcours/scripts/validate_questionnaire_blocks.py --autotest
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py --autotest
python3 .claude/skills/analyse-parcours/scripts/parse_questionnaire.py --autotest
python3 .claude/skills/analyse-parcours/scripts/check_report_values.py --autotest
python3 process/validate_manifest.py
python3 process/validate_key_consistency.py
```

⚠️ Never chain a script with `| tail`: the exit code returned would be that of `tail`.

**New expected autotests**: a criterion whose `context` is `null`, one whose it is the empty
string, a composite block where only one of the two criteria has a context, and an audit whose
**all** contexts are empty.

**Verification by rendering, mandatory**: generate the questionnaire on a real audit **and**
on a fully empty audit, then **read the produced Markdown**, do not count occurrences. The
empty audit is built in `/tmp`, never in `audits/`:

```bash
mkdir -p /tmp/audit-zero/site-x.fr
jq '.domain="site-x.fr"
  | .criteria = [.criteria[] | .answer=null | .coefficient=null | .provenance=null
                 | .source=null | .context=null | .category="no_data"]
  | .answered_criteria=0 | .global_completeness_pct=0
  | .quick_diag_overview.questions = [.quick_diag_overview.questions[]
      | .answer=null | .provenance=null | .source=null | .context_index=null]' \
  audits/octo.com/eof-audit-results.json > /tmp/audit-zero/site-x.fr/eof-audit-results.json
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py /tmp/audit-zero/site-x.fr
```

Expected on the empty audit: **62 blocks asked**, the whole library, and **no measurement
recall displayed**.

## The three borrowings are done

| Borrowing | Commit | What the client sees |
|---|---|---|
| 1, the recall of measurements | `9ba4f5b`, texts rewritten for them in `e091e98` | under the question, the already measured fact, to confirm or correct |
| 2, questions as statements | `2f4205d`, re-read in `009a647` | the 62 questions written in their words, with no internal acronym |
| 3, titles and the interviewee | `431e127`, re-read in `009a647` | `## 3 of 41 - Code source availability (to check with the development team)` |

The internal plumbing of the Markdown (`Criteres EOF couverts`, `Potentiel debloque`) moved to
HTML comments in `f28bf8e`: it is no longer read by the client.

⚠️ **The measurement texts come from the audit folder, not from the generation code.** An
audit folder produced before `e091e98` therefore still publishes the old texts, with their
internal acronyms. Refreshing them is done **without a network call**, by replaying
`run_eof.py` on a copy of the folder: it only re-reads files already on disk. Verified, no
verdict changes and the radar stays identical to the byte; only the 16 context texts are
rewritten.

-----

## Session 25, 2026-09-08: the single axis, and what it gives when followed

Everything below falls under a single axis, set by the user and taking precedence over
everything else: **ask as few questions as possible to get the largest number of criteria
answered, and as precisely as possible.** The content of the questions and their order
derive from this axis, and from nothing else. In particular, neither the recipient nor reading
comfort are sorting axes.

Two consequences are worth stating right away, because they close leads that naturally come
back to mind. The apparent redundancy between questions is almost not exploitable, and saving
questions by replacing a question with an approximate technical clue is a step backward, not
a gain: it lowers the counter by manufacturing imprecision.

### The real counts

70 criteria in the framework (54 detailed over 6 dimensions + 16 quick diagnostic questions).

62 question blocks in the library, which is a CEILING and not the number asked:
`generate_questionnaire.py` only keeps the criteria left unanswered.

On a real audit, 57 questions were produced, vs 16 + 41 = 57 with the old code: the grouping
costs no question.

8 criteria are decided by measurement alone (1.5, 1.6, 1.12, 1.13, 2.1, 3.3, 5.4 and 0.16).

16 criteria receive a displayed context but NEVER an answer.

46 criteria that no probe reaches.

### The merge is exhausted

The 8 composite-type blocks cover 16 criteria by themselves. An exhaustive search concluded
that NO further merge is possible without loss.

A single new pair was proposed, 1.1 with 1.7, and it was rejected: 1.1 asks whether a
non-digital solution was ruled out with evidence in hand, 1.7 whether each feature is
really used, and a "improvement potential" answer would no longer say which of the two is
missing.

Ten tempting merges were examined and rejected, all on the same mechanism: TWO PRACTICES
DECOUPLED IN REAL LIFE. List not to reopen: 1.2 with 2.2, 1.5 with 1.10, 1.3 with 1.6, 3.1
with 3.2, 4.2 with 4.3, 6.1 with 6.6, 6.2 with 6.4, 6.3 with 6.4, 1.11 with 1.12, 2.3 with 2.4.
Telling examples: a CI/CD can run without tests, one can do FinOps without GreenOps, a badly
chosen database can be correctly optimized.

### The constraint of the two vocabularies

⚠️ **This paragraph claimed the opposite of what the framework says, and it was corrected in
session 26 after directly reading `eof-reference.json`. The framework is authoritative.**

The 44 criteria of dimensions 1 to 5 offer "🚫 Not applicable", coefficient 0, as well as
"🤔 To be assessed". The 16 quick diagnostic questions 0.x offer NEITHER: they carry graduated
levels, with no non-applicability option. The 10 criteria of dimension 6 carry their own
three-level scale, "🟢 Easy to change" / "🟡 Moderate effort" / "🔴 Hard to change", and do
not offer "Not applicable" either.

Consequence, unchanged: merging a 0.x with a criterion of dimensions 1 to 5 makes an answer
UNEXPRESSIBLE. It is the "🚫 Not applicable" of the detailed criterion that becomes
impossible to tick, since the levels of the 0.x do not offer it.

That is why the only composite block touching a 0.x associates 0.3 and 6.10.

Practical consequence: out of 5 groups of redundant questions spotted, 4 cross this boundary
and are therefore not mergeable; only 0.7 with 0.10 is, for a gain of a single question. The
apparent redundancy is NOT the lever.

### "Not applicable" and not_applicable are now ONE SINGLE mechanism, the discarded criterion

⚠️ **Unified in session 26. Full contract in `discarded-criterion-convention.md`, which is
authoritative. What follows summarizes, and incidentally describes the BEFORE state, because
it is that defect that was closed.**

A criterion is **discarded** when it does not apply to the service. Two paths lead to the same
state and produce exactly the same figures: its `answer` is "🚫 Not applicable", or its
boolean `not_applicable` is true. A discarded criterion is removed from ALL denameinators,
counts in no numerator, and is only visible in the new key `discarded_criteria`.

**The previous state, not to be restored.** The answer "🚫 Not applicable" counted in
`answered_criteria` and removed the criterion from no denameinator. It therefore behaved
exactly like "🤔 To be assessed": both inflated completeness while adding nothing to the
potential. Demonstration: 10 criteria with 3 answered, switching the 7 others to "Not
applicable" gave `answered_criteria` 3 to 10, `completeness_pct` 30 % to 100 %, and
`optimization_potential_pct` 15 % to 15 %, UNCHANGED.

**The underlying trap, which decided the rest.** "🚫 Not applicable" and "✅ Confirmed
strength" carry the SAME coefficient 0. Counting a discarded criterion as answered therefore
makes it arithmetically identical to a strength: a service without a database would have
seen its dimension 4 displayed at 0 % optimization potential, i.e. as the best-scored
dimension of its report. Hence the third state `out_of_scope` per dimension, which outputs
`null` and never 0 %.

**The divergence between the two producers is corrected**: `run_eof.py` and `merge_lots.py`
now treat both paths the same way. Incidentally, an internal inconsistency of `merge_lots.py`
was closed: its per-dimension total already subtracted the discarded ones, its global total did
not.

### An apparent lever, refused: replacing a question with a technical clue

Six questions could be approximated by a signal we already measure: 0.4 by the number of
third-party domains, 0.10 by the number of URLs in the sitemap, 1.9 and 1.14 by the page weight,
2.5 by HTTP 304 codes, 6.3 by deployment freshness.

These are weak proxies. A recent deployment does not prove a pipeline exists, a page weight
says nothing about screen clarity. Turning them into answers would save 6 questions **while
degrading precision**, i.e. the opposite of the goal. Refused.

### Filter questions, implemented in session 26

A filter question does not make 2 criteria answered, it makes ten answered when the answer is
"this does not apply to us": a service without its own database settles dimension 4 all at
once, without loss of precision since "Not applicable" is a legitimate framework answer for
dimensions 1 to 5.

**Full contract in `discarded-criterion-convention.md`. What follows only says what you need
to know when reading the code.**

A third block `type`, `filter`, alongside `direct` and `composite`. It carries a `criteria`
list instead of a singular `criterion`, plus a `discarded_label` and an `applicable_label`.
Ticking `discarded_label` pours one "🚫 Not applicable" entry per criterion, with no
provenance promotion; ticking `applicable_label` pours NOTHING, the criteria remain to be
asked.

The three delivered filters:

| Filter | Governed criteria | Potential |
|---|---|---|
| No human user interface | 1.4, 1.5, 1.8, 1.9, 1.10, 1.11, 1.13, 1.14, 5.9 | 12.5 |
| No persistent data of its own | 4.1 to 4.6 | 8.0 |
| No separate test environment | 3.7, 3.8 | 4.5 |

4.4 is deliberately left to the "persistent data" filter alone:
`validate_questionnaire_blocks.py` forbids overlap between two filters, whereas it tolerates
that of a filter with a `direct` block, which is the very principle of the lever.

Three rules you cannot guess by reading the code:

1. **A filter is printed only if none of its criteria already carries a decisive answer.** If
   the measurement has decided a single one of its criteria, it has proven that the subject
   applies. On `audits/octo.com`, the "no human user interface" filter is therefore NOT
   printed, because 1.5 and 1.13 are decided by the collection.
2. **A filter is in phase `detail`, at the head of the detailed part**, never in phase `gate`:
   it only governs criteria of the detailed diagnostic, and putting it in the gate would ask
   it before even the decision to go further.
3. ⚠️ **A filter REMOVES no question from the document.** The generator does not know the
   answer to the filter at the moment it writes. Without a fix, the lever lengthens the
   questionnaire and saves nothing: it only adds truthfulness to the report, not effort saved
   for the client. Hence the "IGNORE" mention carried by any block whose ALL criteria are
   governed, with a condition in **conjunction, never disjunction**.

**This lever is not a guaranteed reduction.** For a classic website, the filters receive "this
applies" and discard nothing: the questionnaire then grows by two questions. The gain exists
only for services for which a part of the framework does not speak. It is a bet on the
diversity of audited services, to be presented as such.

**GUARDRAIL, held**: the report displays SEPARATELY the number of discarded criteria, via a
`Discarded` KPI reading `discarded_criteria`. Without it, a completeness of 100 % built on
exclusions would be indistinguishable from a genuinely instructed audit: we would be
manufacturing completeness.

### The measurement block on the review lot

`parse_questionnaire.py` produces a `measurement` block compliant with
`documentation/implementation/measurement-state-convention.md`, with three statuses:

- `read_error` if the file is absent or unreadable
- `not_found` if it is read but no checkbox is ticked
- `ok` otherwise

Verified by the three convention tests: file absent, `validate_probe_health.py` exits with 1
and names the failure ; file present and empty, it exits with 0 without false positive ; file
answered, it exits with 0.

A questionnaire returned fully empty is a legitimate audit result, not a failure of our tool:
it is `not_found`, never `ok` nor an error value.

On a folder without a questionnaire, `parse_questionnaire.py` used to write a lot
indistinguishable from a questionnaire returned fully empty. The lot now carries a measurement
block that distinguishes the two cases.

### The questionnaire is wired nowhere in the pipeline

Established by `grep` on `SKILL.md` and the 9 skill-steps files: the word "questionnaire"
appears only once, in a plan name parenthesis in `39_eof-audit.md` line 16. No step calls
`generate_questionnaire.py`. No return deadline is encoded anywhere.

The full circuit is drawn in `documentation/diagrammes/eof-questionnaire-sequence.pdf`, 3 pages:
what the audit launches on its own, generate and send outside the pipeline, re-read and merge.

### The manipulation trap

`run_eof.py` rewrites `eof-audit-results.json` without re-reading the lots. Rerunning it alone
after a merge therefore makes all the questionnaire answers disappear from the report, IN
SILENCE. `merge_lots.py` must always be rerun after it.

### A method lesson not to forget

The single-file merge was first committed after `py_compile` and `validate_key_consistency.py`,
WITHOUT running `parse_questionnaire.py --autotest`. This autotest built its fixtures under the
two old file names: 6 cases out of 7 fell, and the merge was therefore delivered with its own
safety net torn. Fixed, 7 out of 7.

The `process/CHECKS.md` battery is therefore not enough: **a script that carries an
`--autotest` must see its `--autotest` rerun before any commit.** This rule is now written in
`process/CHECKS.md`, with the list of the **six** scripts concerned and the command to find it
rather than trust it.

## Work items delivered

1. **Work item 13, the two-layer radar**: delivered. The script `generate_radar_svg.py`
   produces a radar distinguishing provenances by two layers.
2. **Work item 31, accessible separators**: delivered. The dynamically generated separators
   were fixed.

⛔ **What is closed and must not be reopened**:

- **Question grouping.** The 5 former clusters plus the `0.3` + `6.10` merge close the subject.
- **The independent-checkbox multi-select format.** Rejected on measurement: 1.29 vs 1.13, cf.
  the dedicated section.
- **Sorting questions by decreasing potential.** 4.5 questions saved out of 37, no interest.
- **The hunt for overlaps between quick diagnostic and detailed criteria.** The 6 were screened,
  only one was exploitable.
- **The hope of automating more.** The ceiling is structural, not a tooling defect: the
  framework's evaluation methods require facts internal to the team, that no probe can observe.

The lever that remains is not to ask **fewer** questions, it is to make each question **easier
to answer**.

## A defect of the EROOM framework, left open

Some levels of the quick diagnostic **glue the "I don't know" mention onto the most
unfavorable level** (`0.10`, `0.11`, `0.14`). An honest respondent could therefore be scored
"very complex" for having said they did not know, while the whole project forbids the worst
case by default. The generator removes the mention **at display time only**, and the lot file
keeps the original level character for character, because the parser resolves the answer from
the `<!-- opt:N -->` index and re-reads the framework.

⚠️ **Never make the parser depend on the displayed text**: this cleanup would become a
falsification. Whether to report this defect to EROOM remains to be decided.

-----
End of trace
-----
