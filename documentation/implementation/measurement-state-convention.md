-----
-----
# Measurement state convention
-----
-----

How our extractors say whether their probe succeeded, and why this changes nothing
in the deliverable the client reads.

-----

## 1. The problem this convention solves

Our extractors confuse two very different things:

- **the audited service does not have the thing**: no `robots.txt`, no accessibility
  declaration. It is a fact about the service, and it is an audit result ;
- **our probe failed**: network timeout, API quota exceeded, incomplete capture,
  unreadable file. It is a fact about our tool, and it is not an audit result.

Today both produce the same fallback value. A timeout on `robots.txt` makes
`present: False`, exactly like a real 404. A capture without an HTML body makes a tag
count of zero, which fabricates a flattering EcoIndex.

**Consequence measured on octo.com on September 8, 2026.** Out of the 11 HAR captures,
6 have a zero DOM. The report deduplicates by URL and prefers the capture whose DOM was
measured, which hides the defect most of the time. But when a URL has ONLY captures
without an HTML body, the zero reaches the reader:

| Report row | DOM shown | EcoIndex | Weight | Requests |
|---|---|---|---|---|
| P4 `/recrutement/offers/consultant-mlops-engineer...` | 292 | B 79/100 | 557 KB | 28 |
| P5 `/recrutement/offers/consultant-ai-engineer-senior...` | 0 | **A 91/100** | 557 KB | 28 |

Two job offers with the same weight and the same number of requests. The second gets the
best score of the report because its tags were never counted. **The reader has no way of
knowing**, and deduplication cannot fix it for lack of a second capture for this URL.

### 1.1 The cause of this specific case, and the lesson it carries

Verified in the HAR on September 8, 2026: **the HTML body of this page was present**,
33,168 characters. Its entry carries `response.content.encoding == "base64"`, a field
that `har_metrics.py` did not look at. It therefore counted tags in base64, and found
zero, necessarily. Decoded, the document has 311 tags.

Out of the 20 HTML entries of the three archived HARs of the repository, **2 are in
base64**, one per octo.com capture. The case is neither theoretical nor rare.

⚠️ **The lesson, and it holds for the whole work stream**: the page was not unmeasurable,
it was mismeasured. Reporting a failure never dispenses from first checking whether the
data is there. The guardrail that would have caught this bug is arithmetic and fits in one
sentence: **an HTML document read successfully that yields zero tags is an
`analysis_error`, never an `ok`.** An impossible zero must be treated as a probe failure,
not as a measurement.

### 1.2 Result after the fix

`har_metrics.py` now honors `content.encoding`. Verified by replaying the report
deduplication on the octo.com HAR:

| Row | Before | After |
|---|---|---|
| P5 `/recrutement/offers/consultant-ai-engineer-senior...` | DOM 0, **A 91/100** | DOM 311, **B 78/100** |

The 5 other rows keep exactly their values, and the EcoIndex reference autotest stays at
53 out of 100. **The 6 rows of the report now have a really measured DOM**: the display
rule of section 4.1 no longer triggers on this audit. It remains necessary for future
captures, where a response body can genuinely be missing.

Out of the 11 HAR captures, 5 remain unmeasurable and are now reported as such:
3 `read_error` (response body absent from the capture) and 2 `analysis_error` (no HTML
entry for this page). None survives deduplication, so none reaches the reader.

-----

## 2. The principle

**An extractor failure is not a state of the audited service, it is a state of our tool.**
It therefore has no place in the client deliverable. It goes out through an internal alert.

Two separate destinations, and that is all.

-----

## 3. Internal destination: the `measurement` block

Each extractor result carries a `measurement` block:

```json
"measurement": {
  "status": "ok",
  "target": "https://example.com/robots.txt",
  "detail": null
}
```

| Field | Content |
|---|---|
| `status` | one of the five values below, never anything else |
| `target` | what was looked for: URL, file path, field name |
| `detail` | a short sentence explaining the failure, or `null` if `status` is `ok` |

The five values of `status`, and only them:

| Value | Meaning | Is the produced value worth anything? |
|---|---|---|
| `ok` | measured | yes |
| `not_found` | the probe did look, the thing is really absent | yes, it is an audit result |
| `network_error` | request impossible: timeout, DNS, connection refused, API quota | **no** |
| `read_error` | the resource is there but unreadable: file missing, broken encoding, invalid JSON | **no** |
| `analysis_error` | the resource is read but unusable: expected field missing, 200 response without data | **no** |

**The distinction that matters is `not_found` vs `network_error`/`read_error`/`analysis_error`.**
`not_found` is an audit result and is treated as such. The three error values say that we
don't know.

-----

## 4. Client destination: nothing new

A criterion whose measurement failed is treated **exactly like unanswered**:

```json
"answer": null,
"provenance": null
```

It goes into the questionnaire like the other unanswered criteria. The reader sees
"no answer", a label that already exists. **There is no seventh absence label to invent.**

### 4.1 The only place in the report that changes: the EcoIndex table

This table is not an EOF criterion, the rule above did not cover it. **Arbitrated by the
user on September 8, 2026**: on a page whose DOM could not be counted, the EcoIndex and DOM
cells display **"not measured"**, and the row stays in the table.

```
Page                     | EcoIndex   | Requests | Weight | DOM
-------------------------|------------|----------|--------|-----------
P4 /...consultant-mlops  | B 79/100   |       28 | 557 KB |        292
P5 /...consultant-ai     | not measured |     28 | 557 KB | not measured
```

The reasoning: it is the equivalent, in this table, of the "no answer" imposed on EOF
criteria. **We do not publish a figure we do not have.**

⛔ **The row is not removed**, and the weight and the number of requests stay displayed:
those were really measured, and making the page disappear would recreate precisely the
silent absence that this convention corrects.

-----

## 5. What this convention does not touch, and that is intended

⛔ **The provenance axis gains no new value.** Provenance answers "where does this value
come from". A measurement failure answers "did my probe succeed". They are two independent
axes: mixing them would corrupt a canonical vocabulary protected by validators, and placing
a new value at the wrong precedence rank would silently overwrite an already established
answer.

So they remain untouched, without a single line of change:

| File | What does not change |
|---|---|
| `process/validate_lot_output.py` | `PROVENANCE_VALUES` |
| `process/lot-output-schema.json` | the provenance enumeration |
| `process/lots-manifest.json` | `precedence_provenance` |
| `.claude/skills/eof/scripts/generate_radar_svg.py` | `PROVENANCES_ETABLI`, `LIBELLES_PROVENANCE` |
| `process/merge_lots.py` | `compute_metrics` |
| `.claude/skills/eof/scripts/generate_questionnaire.py` | `compute_residu` |

⛔ **The arithmetic does not change by a single line.** Since a measurement failure
produces `answer: null`, all existing counts keep working without modification:
`answered_criteria`, `completeness_pct`, `optimization_potential_pct`,
`answered_by_provenance`. The 8 canonical keys are intact and
`process/validate_key_consistency.py` stays green without exemption.

⛔ **Do not use `not_applicable`.** It removes the criterion from the denameinator. A failed
measurement must **stay** in the denameinator: we don't know, so the potential remains to be
assessed. `not_applicable` keeps its own meaning, "the criterion does not apply".

-----

## 6. Where the alert is

In `process/validate_probe_health.py`, and nowhere else.

It re-reads an audit folder, collects all the `measurement.status` it finds there, and
**exits with 1 if a single error value is present**. It makes no network call.

```bash
python3 process/validate_probe_health.py audits/<domain>
```

-----

## 7. How to verify it

**By negative test, extractor by extractor.** Force the failure, then check two things:
that `status` is not `ok`, and that `validate_probe_health.py` exits with 1.

⛔ **Never conclude on the faith of a success.** An extractor that works proves nothing
about what it does when it fails: that is precisely the defect this convention corrects.
