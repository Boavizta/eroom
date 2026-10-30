-----
-----
# Convention: a discarded criterion, and filter questions
-----
-----

Established in session 26, 2026-09-08. This document is the common contract for the
three producers and the two consumers affected by filter questions. It is
authoritative; in case of disagreement with a code comment, the code is wrong.

-----

## 1. The starting fact, verified in the framework

`🚫 Not applicable` is a **EROOM framework** answer option, not an invention of
our tool. It is offered for the **44 criteria of dimensions 1 to 5**, with an
`evaluation_coefficient_options` of **0**.

It is offered neither for the **10 criteria of dimension 6** (which carry the
scale `🟢 Easy to change` / `🟡 Moderate effort` / `🔴 Hard to change`), nor for the
**16 questions 0.x of the quick diagnostic** (which carry graduated levels with no
non-applicability option).

⚠️ The document `questionnaire-eof-implementation.md` claimed the opposite, that the
0.x offered "Not applicable" and that dimensions 1 to 5 did not. It was inverted.
Corrected.

**Consequence: a filter question can only discard criteria of dimensions 1 to 5.**
No dimension 6 criterion, no 0.x question.

-----

## 2. What a discarded criterion is

A criterion is **discarded** when it does not apply to the audited service. Two paths
lead to the same state, and they must produce exactly the same figures:

- its `answer` is `🚫 Not applicable` ;
- or its boolean `not_applicable` is true.

There is **no** third notion to invent. "Discarded" is our tool's word for the state
the framework calls "Not applicable".

### 2.1 What a discarded criterion does to the figures

A discarded criterion is removed from **all** denameinators, and counts in no numerator:

| Quantity | Effect |
|---|---|
| `answered_criteria` | it does **not** count in it |
| `total_criteria` | it is **removed** from it |
| `completeness_pct`, `global_completeness_pct` | removed from the denameinator |
| `optimization_potential_pct`, `global_optimization_potential_pct` | its `max_potential` is subtracted from the denameinator |
| `discarded_criteria` | it counts there, it is the only place where it is visible |

Reason: a criterion outside the scope is neither a success nor a shortcoming. Counting
it as answered with a zero coefficient would make it **arithmetically identical to a
`✅ Confirmed strength`**, which also carries coefficient 0. A service without a
database would then see dimension 4 displayed at 0% optimization potential, i.e. as the
best-scored dimension of its report. This is the defect that work item 13 closed,
through another door.

### 2.2 The guardrail, non-negotiable

A discarded criterion is only honest if it is **counted separately and displayed**. Without
the visible counter, a completeness of 100% built on exclusions is indistinguishable
from a genuinely instructed audit: we would be manufacturing completeness.

-----

## 3. The new keys of the contract

Written by **both producers**, `run_eof.py` and `process/merge_lots.py`, with the
same values for the same input.

### 3.1 At the root of `eof-audit-results.json`

| Key | Type | Meaning |
|---|---|---|
| `discarded_criteria` | integer | number of discarded criteria, all dimensions combined |

`total_criteria` becomes the number of **retained** criteria, i.e. the framework total minus
the discarded ones. The framework's raw total is recovered via `total_criteria + discarded_criteria`.

### 3.2 In each entry of `dimensions[]`

| Key | Type | Meaning |
|---|---|---|
| `discarded` | integer | number of discarded criteria of this dimension |
| `out_of_scope` | boolean | true when **all** the criteria of the dimension are discarded |

When `out_of_scope` is true, `optimization_potential_pct` and `completeness_pct` are
`null`, and `total` is 0. The dimension has no score, because there is nothing to score.

⚠️ Do not confuse `out_of_scope` with a dimension without an answer. A dimension
without an answer is a dimension we failed to instruct; a dimension out of scope is a
dimension we know does not concern this service. The report and the radar must
distinguish them.

-----

## 4. The questionnaire block of type `filter`

### 4.1 Its shape in `questionnaire-blocs.json`

A third `type`, alongside `direct` and `composite`:

```json
{
  "id": "filter-persistent-data",
  "file": "technical",
  "phase": "detail",
  "title": "Data the service retains",
  "interviewee": "the person who operates the infrastructure",
  "type": "filter",
  "criteria": ["4.1", "4.2", "4.3", "4.4", "4.5", "4.6"],
  "question": "...",
  "discarded_label": "...",
  "applicable_label": "..."
}
```

- `criteria` : list of the criteria the filter discards when the answer is "this does
  not apply". All must belong to dimensions 1 to 5.
- `discarded_label` : the label of the checkbox that discards the criteria.
- `applicable_label` : the label of the checkbox saying the subject does apply. Checking
  it pours **no** answer: the criteria remain to be asked.
- `criterion` (singular) and `options` are **forbidden** on a `filter` block.

### 4.2 When a filter is printed

A filter is printed only if **none** of its criteria already carries a **decisive**
answer, i.e. an answer absent from `REPONSES_NON_TRANCHANTES`.

Reason: if the measurement has already decided a single one of the filter's criteria, it
has proven that the subject applies, and the question is useless. Verified example on
`audits/octo.com`: 1.5 and 1.13 are decided by the collection, so the "no human user
interface" filter must not be printed for this site.

A `🤔 To be assessed` proves nothing and therefore does not remove the filter.

### 4.2bis A filter is in phase `detail`, never in phase `gate`

The gate decides whether an in-depth diagnostic is relevant. A filter does not do that:
it says which part of the framework does not concern the service, and it only governs
criteria of the detailed diagnostic. Putting it in the gate would ask it before the
decision to go further, hence sometimes for nothing.

**Filters are placed at the head of the detailed part**, before all other blocks of
this part, and sorted among themselves by decreasing yield. This is not a presentation
preference, it is a necessity: the mention of section 4.2ter refers to a question number,
and this number must always designate a question **already read**. Sorting by yield alone
does not guarantee it, two blocks with equal yield being able to order themselves in any
direction.

### 4.2ter The "to be ignored" mention, which gives the effort back to the client

⚠️ **A filter removes no question from the document.** At the moment the generator writes
the Markdown, it does not know the answer to the filter: it therefore prints the filter
**and** the questions this filter could make useless. Without the mention below, the lever
lengthens the questionnaire by two or three questions and saves none. It then only adds
truthfulness to the report, not effort saved for the client.

**Rule.** A block whose **all** criteria are governed by filters carries, just under its
title, a mention referring to the questions of these filters:

```
IGNORE if you answered "No" to question 1 (Service data storage).
```

- The condition is a **conjunction**, never a disjunction. A block is ignorable only if
  **each** of its criteria is discarded. The block covering 4.4 and 3.9 falls under two
  different filters: it is ignored only if both answered "this does not apply", so the
  mention says `to question 1 AND to question 3`.
- A **partially** governed block carries **no** mention. It remains to be filled in, since
  one of its criteria still applies.
- The mention cites the **number and** the title of the filter question. A number alone forces
  the reader to scroll back blindly.
- **Each term of the conjunction carries ITS OWN `discarded_label`.** Two filters do not
  offer the same checkbox: citing a single label then chaining "AND to question 26" makes
  the reader understand that they must have checked this same label at both questions, which
  is impossible.
  The correct form is `"<discarded_label of filter 25>" to question 25 (title) AND
  "<discarded_label of filter 26>" to question 26 (title)`. This defect was shipped then
  corrected in session 26; an autotest case keeps it closed.
- The label is truncated at the first `(`, with no character limit. That is why the mention
  reads "No, the service retains no data" and not the full label, which adds
  "(or only in temporary cache)".

The governed questions remain **scattered** in the document, because sorting by yield
scatters them. This is accepted: grouping the questions under their filter would sacrifice
the yield sort, and would remain impossible for composite blocks that straddle two filters.

### 4.3 What the re-read pours

When the `discarded_label` checkbox is checked, `parse_questionnaire.py` pours **one entry
per criterion** of `criteria`, each with:

- `answer` : `🚫 Not applicable`
- `provenance` : the same as for `direct` blocks, with no promotion of any kind
- `source` : the mention saying that the answer comes from the filter, with the block id

When the `applicable_label` checkbox is checked, nothing is poured. The block counts as
answered for the `measurement` block, but no criterion comes out of it.

The existing rules do not change: zero or two checkboxes checked pour nothing and are
reported.

### 4.4 What the validator must tolerate

`validate_questionnaire_blocks.py` requires that a criterion be covered by only one block.
A filter covers by construction criteria that **also** have their individual block, and
that is intended: the filter discards them all at once, otherwise we ask them one by one.

**This uniqueness rule must therefore not apply to `filter` blocks.** It remains fully in
force between `direct` and `composite` blocks. However, two `filter` blocks must not
overlap each other, and each criterion cited by a filter must exist in the framework and
offer `🚫 Not applicable`.

-----

## 5. The three delivered filters

| Filter | Discarded criteria | Potential concerned |
|---|---|---|
| No human user interface | 1.4, 1.5, 1.8, 1.9, 1.10, 1.11, 1.13, 1.14, 5.9 | 12.5 |
| No persistent data of its own | 4.1 to 4.6 | 8.0 |
| No separate test environment | 3.8, 3.9, 4.4 | 4.5 |

⚠️ 4.4 appears in two filters. Since a filter only pours `🚫 Not applicable` and both
pour the same thing, the overlap is harmless; but validator rule 4.4 forbids overlap
between filters. **4.4 is therefore carried by the "persistent data" filter alone**, and
the "test environment" filter cites only 3.8 and 3.9.

### 5.1 What these filters cost and bring

They are not a guaranteed reduction. For a classic website, they receive "this applies"
and discard nothing: the questionnaire then grows by two questions, the third being
suppressed by rule 4.2. The gain exists only for services for which a part of the
framework does not speak — a service without an interface, without its own database,
without pre-production. It is a bet on the diversity of audited services, and it must
be presented as such.

-----

## 6. What the display must say

### 6.1 HTML report

- A `Discarded` KPI next to `Completeness` and `Answered criteria`, reading `discarded_criteria`.
- In the dimensions table, a `out_of_scope` dimension shows `out of scope` in place of
  its percentage, followed by the number of discarded criteria. It **never** shows `0 %`.
- A partially discarded dimension shows its percentage, then the number of discarded ones.

### 6.2 Radar

- A `out_of_scope` axis is neutralized like an axis without an answer already is, but
  carries the mention `out of scope` and not `no answer`.
- The coverage gauge calculates its percentage on the **retained** potential, and states
  after it the number of discarded criteria. A service with nothing discarded reads the
  same sentence as before.

⚠️ **The trap that was paid for once.** A discarded criterion carries a **non-null**
`answer`, namely `🚫 Not applicable`. Any code that recognizes an answered criterion by
`answer is not None` therefore counts it **in both the numerator AND the denameinator**
without meaning to. The first draft of the radar did exactly that: out of 54 criteria
with 6 discarded and 7 answered elsewhere, the gauge announced "13 criteria out of 54,
6 discarded" instead of "7 criteria out of 48, 6 discarded". Displaying the discarded
counter does not fix the arithmetic that feeds it: these are two work items, and the
second is the only one that matters.

-----

## 7. Controls

In addition to the `process/CHECKS.md` battery:

- `validate_key_consistency.py` must know `discarded_criteria`, which belongs to the
  watched `criteria_*` family.
- The `--autotest` of **all** touched scripts must be rerun, not only the one we think
  of. This mistake was paid for twice in session 25.
- An autotest case must verify that a fully discarded dimension **never** outputs a
  `optimization_potential_pct` of 0.
