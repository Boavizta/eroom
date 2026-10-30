-----
-----
# Snapshot of the source Google Sheet of the EOF reference framework
-----
-----

These 9 files are the **raw export of EROOM's EOF-V.1.1 Google Sheet**, one file
per tab. This is not documentation: it is the **source of truth** from which
`eof-reference.json` is built.

**Snapshot date: 2026-09-02.** Verified still identical to the live Sheet on
2026-09-07.

## Why these files are versioned

They used to be in `tmp/eof-gviz/`, a git-ignored directory, so saved
nowhere. The link to the Sheet, however, has always been versioned in `../../SKILL.md`.
The distinction matters:

| | Where | Losable |
|---|---|---|
| The Sheet address and the download recipe | `../../SKILL.md` | no |
| **The snapshot, i.e. the point of comparison** | **here** | **not anymore** |

Without a point of comparison, re-downloading the Sheet learns nothing: you get its
state of the day, without being able to say what changed. The only interest of keeping this snapshot
is therefore to **detect an evolution of the framework at EROOM**.

It is not theoretical: the Sheet has already been enriched from **43 to 54 detailed
criteria** since the Excel export initially provided by EROOM, a discovery made on 2026-09-02.
It will move again.

It is also by re-reading this source that we established that the code applied the **wrong
formula** for the optimization potential: the denameinator covers **all** the criteria
of a dimension, answered or not. These files are the evidence for this
correction.

## Check whether EROOM modified the reference framework

```bash
.claude/skills/eof/scripts/verify_source_sheet.sh
```

No side effect, touches nothing, exit code 0 if nothing changed, 1 otherwise.
Also detects a Sheet that became private or a deleted tab, which return HTML with
a 200 code and would otherwise be compared silently.

To adopt an evolution:

```bash
.claude/skills/eof/scripts/verify_source_sheet.sh --refresh
git diff .claude/skills/eof/docs/source-sheet/   # see exactly what EROOM changed
```

Then regenerate the reference framework, cf. step 2 of `../../SKILL.md`, and re-run
`process/validate_key_consistency.py`.

## File format

These are responses of Google's `gviz` interface, not pure JSON: each file
starts with `/*O_o*/` then `google.visualization.Query.setResponse({...})`. This envelope must be
stripped before parsing, which is what
`../../scripts/build_template.py` already does. The classic CSV and XLSX exports are not
usable here: they go through a one-time-token redirect.

## File-to-tab correspondence

| File | Tab | Content | Criteria |
|---|---|---|---|
| `read-me.json` | Read me | how to use the framework | - |
| `quick-diag.json` | Quick diagnostic | 1-to-5 scale, its own logic | 16 questions |
| `product.json` | dimension 1, Product | | 16 |
| `architecture.json` | dimension 2, Architecture | | 5 |
| `infrastructure.json` | dimension 3, Infrastructure | | 8 |
| `storage.json` | dimension 4, Storage and data | | 6 |
| `algo-code.json` | dimension 5, Algorithms and code | | 9 |
| `ease.json` | dimension 6, Ease of change | vocabulary 🟢 / 🟡 / 🔴 | 10 |
| `synthesis.json` | Synthesis | | - |

Total **54 criteria** detailed, sums of `max_potential` per dimension
**23.5 / 8.0 / 12.0 / 8.0 / 13.0 / 15.5**, total **80.0**.

Two pitfalls of the framework, visible in these files:

- Dimension 3 numbering is continuous (`3.1` to `3.8`, 8 criteria, no gap) in the current
  English sheet. Older French-sheet audits used 3.1–3.3 then 3.5–3.9: subtract one from any
  id in 3.5–3.9 to get the current id.
- **Two answer vocabularies**: 44 criteria in `✅ / 💡 / 🚫 / 🤔 / ⌛️`, and the 10
  criteria of dimension 6 in `🟢 / 🟡 / 🔴`, **without a "To be assessed" option**. Always read
  the criterion's `evaluation_options`, never hardcode these labels.

⚠️ **These two pitfalls are only the most visible ones. The complete inventory is in
[`REFERENCE-PITFALLS.md`](REFERENCE-PITFALLS.md)**, to be read **before** writing a question or
an extractor. It documents verbatim, among others: the 8 quick-diagnostic levels that
assign an extreme level to whoever answers they don't know; the fact that the 1-to-5 scale **has no
constant direction** from one question to the next; the criteria whose label and `method`
do not ask the same question; those validated by the absence of a discovery, thus
rewarding inaction; and all the overlaps between the quick diagnostic and the
detailed criteria, with the reason for each refusal.

**The rule that sums it all up**: it is the `method` that defines what the criterion measures, never the
label nor the `explanation`.
