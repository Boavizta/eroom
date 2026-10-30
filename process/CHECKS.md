-----
-----
# Check battery
-----
-----

To rerun before every commit. Each check exits 0 if happy, 1 otherwise.

⚠️ **Until now this list only existed in a session handoff, under `tmp/`, which is
gitignored.** It therefore lived outside git, and was lost at every cleanup. This
file is now its home.

-----

## With no network call

```bash
python3 process/validate_key_consistency.py
python3 process/validate_manifest.py
python3 .claude/skills/analyse-parcours/scripts/check_report_values.py --autotest
python3 process/validate_probe_health.py audits/<domain>
```

| Check | What it guarantees | Expected output |
|---|---|---|
| `validate_key_consistency.py` | the 9 canonical keys are written by both producers and read by both consumers, with no dead name nor invented key | `[SUCCESS]` |
| `validate_manifest.py` | the lot manifest is consistent | `[SUCCESS]`, 17 lots, 6 waves |
| `check_report_values.py --autotest` | the known report accidents are detected and legitimate usages ignored | 28 cases passed |
| `validate_probe_health.py` | **no probe failed silently** in the targeted audit directory | `[SUCCESS]`, or the list of failures |

-----

## The `--autotest` rule, do not forget it

⛔ **This battery is not enough.** It checks the repo, not the scripts you just
modified.

**When a change touches a script that carries an `--autotest`, rerun that `--autotest`.
And rerun the one of ALL the touched scripts, not only the one you are thinking of.**

This mistake was paid for twice in the same session, the second time without anyone
seeing it. A refactoring renamed a function without touching its 16 call sites in the
autotest, which fell from 15 out of 15 to **0 out of 15**; the 5 checks of this battery
all exited 0 in the meantime, because none of them looks at what a script does. A torn
safety net is more dangerous than an absent one: it reassures.

The **nine** scripts that carry an `--autotest`. ⚠️ They are **no longer all** in the same
directory since session 26: `merge_lots.py` lives under `process/`. To run from the repo
root:

```bash
S=.claude/skills/analyse-parcours/scripts
python3 $S/check_report_values.py       --autotest
python3 $S/generate_questionnaire.py      --autotest
python3 $S/parse_questionnaire.py         --autotest
python3 $S/validate_questionnaire_blocks.py --autotest
python3 $S/parse_html_criteria.py         --autotest
python3 $S/parse_public_pages.py       --autotest
python3 $S/run_eof.py                     --autotest
python3 $S/analyze_har.py                 --autotest
python3 process/merge_lots.py       --autotest
```

`analyze_har.py` (job 35, step 20 "HAR file analysis"): before it, this step
had NO script — an agent read the `.har` by hand, and the real file produced on
octo.com carried a `blocking_resources` key invented by reading the HTML with the naked
eye, not replayable. Its `--autotest` counts **17 cases**: total count, 1st/3rd-party split
(canonical rule imported from `deploy_freshness._first_party_hosts_from_env`, never
reinvented), URL deduplication before the top10 of the heaviest resources, no-cache,
slow third-party requests (> 1 s), blocking resources of the `<head>` with and without the
archived HTML (job 27) available, and a cross-consistency case with
`generate_report_html.har_traffic_analysis()` on the same fixture HAR (read-only import,
no writing).

`parse_html_criteria.py` and `parse_public_pages.py` are easy to forget, because one
does not think of an extractor as a tested script. `parse_html_criteria.py` goes to the
network in normal use; its `--autotest`, on the other hand, works on fixtures and writes
nothing (the job-27 archiving cases use a temporary directory, never `audits/`). Its
`--autotest` currently counts **38 cases** (32 HTML/CSS reading + 6 on the
`html-pages/` archiving and the `--refresh` flag).

The last two are the **producers** of the results file, and their `--autotest` was born
in session 26: the discarded-criterion arithmetic had been delivered without any test. They
notably keep the case proving that a fully discarded dimension never outputs **0%** of
optimization potential, which would make it pass for the best-rated one in the report.

⚠️ To welcome `--autotest`, their positional argument became optional (`nargs="?"`),
with a `parser.error` that refuses a call without argument. **Do not remove this
guardrail**: without it, a call without argument would leave with a `None` path.

To find the up-to-date list rather than trusting this one. The `--` is
indispensable, otherwise `grep` takes `--autotest` for one of its own options, and the
quotes are too, otherwise zsh tries to expand `*.py`:

```bash
grep -rl -- "--autotest" .claude/skills process "--include=*.py"
```

-----

## With a network call, to run separately

```bash
.claude/skills/eof/scripts/verify_source_sheet.sh
```

Checks that the EOF reference published by EROOM has not changed under our feet. Expected:
9 identical tabs. **It is the only check of the battery that goes to the network**, to
Google Sheets: do not put it in a loop.

-----

## Notes on `validate_probe_health.py`

It is the most recent check, laid down with the convention described in
`documentation/implementation/measurement-state-convention.md`.

- It takes an audit directory as argument, e.g. `audits/octo.com`. Without argument, it
  exits 2 with its usage.
- It searches recursively, at any depth and across lists, for any
  `measurement` block carrying a `status`.
- **It exits 1 only on `network_error`, `read_error` or `analysis_error`.** A
  `not_found` is a legitimate audit result, never a problem.
- An unreadable JSON in the directory makes it exit 1: that is in itself a health problem.
- A `status` outside the five allowed values, or a `measurement` block without `target`, are
  signaled but do not fail: they denounce a badly placed extractor, not a sick audit.
- `--list-files` says which JSON files were found and how many `measurement` blocks each
  carries. Useful when the script sees nothing.

⚠️ **On an audit directory older than the convention, it announces it found no
`measurement` block and exits 0.** That is intended, but read the message: it is not a green
light, it is the admission that it had nothing to check. The blocks only appear after the
extractors have been rerun.
