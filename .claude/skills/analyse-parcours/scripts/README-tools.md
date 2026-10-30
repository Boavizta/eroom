# CLI tools - analyse-parcours

## Lighthouse CLI

Used to compute the Core Web Vitals (LCP, INP, CLS) at step 37 of the skill.

### Initial install (once)

    npm install --prefix .claude/skills/analyse-parcours/scripts/

Installs Lighthouse locally in `scripts/node_modules/`.
The installed version is tracked in `package-lock.json`.

### Check the installed version

    scripts/node_modules/.bin/lighthouse --version

### Check whether an update is available

    npm outdated --prefix .claude/skills/analyse-parcours/scripts/

Example output:

    Package     Current  Wanted  Latest
    lighthouse  12.3.0   12.3.0  12.5.1

### Update Lighthouse

    npm update lighthouse --prefix .claude/skills/analyse-parcours/scripts/

Or ask Claude: "check whether Lighthouse is up to date" / "update Lighthouse".

### How it is used in the skill

`run_lighthouse.sh` prefers the local binary (`node_modules/.bin/lighthouse`).
If the local install is missing, it falls back to `npx` (unpinned version) and
suggests running `npm install` to pin the version.

The version used is shown in the logs:

    [Step 37] Lighthouse 12.3.0 (local install)

-----

## PageSpeed Insights + CrUX (field data)

Alternative to Lighthouse for getting **real field data** (CrUX P75).
Requires `GOOGLE_API_KEY` in `.env` at the project root.

### Check the API key

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <dossier-audit> --check

### Collect field CWVs

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <dossier-audit>

By default: collects **mobile AND desktop** (`--strategy both`), kept side by side.

Options:
- `--strategy mobile` | `desktop` | `both`: restrict to one device (default: `both`)
- `--urls https://... https://...`: explicit URLs (otherwise extracted from the .har)

### Getting the API key

See `documentation/setup/setup_api_keys.md`.
APIs to enable on Google Cloud: PageSpeed Insights API + Chrome UX Report API.
Free quota: 25,000 req/day (PageSpeed), no daily limit (CrUX).

-----

## Coverage analysis — `coverage_metrics.py`

Produces `coverage-analysis.json` (step 30). Use it **instead of** a manual
computation.

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/coverage_metrics.py <dossier-source>
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/coverage_metrics.py <dossier-source> --check

`--check` compares against the existing output and exits 1 on any difference,
without rewriting anything.

### The two mistakes that justify this script

**1. The extension is read from the path, not from the full URL.** A versioned
URL (`dsfr.min.css?version=39.2.0`) does not end with its extension. A naive
`url.endswith(".css")` test classifies it as "other": it disappears from the
JS/CSS aggregates. On a real audit, the page loading the most CSS had *all* its
URLs versioned and was published at **zero KB of JS and CSS**. A zero does not
look like an error, it looks like a codeless page: nobody saw it.
Measured fix: JS total 17,657.4 → 18,226.6 KB, CSS total 3,491.5 → 4,840.4 KB.

**2. A page's label comes from the HTML document, corroborated by the HAR.** Without
this corroboration, the first asset-extensionless URL wins. On a remote procedure,
that is often a technical URL: the page was displayed under
`/ihm-spd/csrfguard.action` (an anti-CSRF token) instead of the form actually seen
by the user. The script only keeps URLs the HAR declares served as `text/html`, and
**says** in `url_provenance` whether the corroboration happened.

### What it reports about itself

A non-empty page whose JS and CSS aggregates are both zero is flagged
`no_js_no_css: true`. That is the symptom of a misclassification, not of a
codeless page: surface it to the user.

### Checks

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_coverage_metrics.py

29 checks, including the negative case (a redirect *to* a `.css` is not CSS)
and the proof that the original defect was real. Verified by mutation: putting
back `path = url` drops 7 checks.

**Its limit, to know**: these checks cover classification and the label, not
the accuracy of the bytes reported by Chrome. If DevTools mis-measures a range,
the script faithfully copies the error.

-----

## e-footprint refactoring safety net

Three checkers, to run after any change touching the CO2e computation.
They answer different questions and do not replace each other:

| Script | Question it answers |
|---|---|
| `check_efootprint_contract.py` | did the JSON output lose a key? |
| `check_genericite.py` | is the code tied to one specific site? |
| `check_efootprint_spec.py` | do the library's refusals still refuse? |
| `check_coverage_metrics.py` | is a versioned URL still typed correctly? |

### `check_efootprint_contract.py` — the output lost nothing

The HTML report reads `efootprint-python-summary.json` key by key with `.get()`.
A missing key causes **no error** there: it produces a silent hole. This script
compares a frozen baseline against the fresh output.

    # Once, BEFORE modifying the code
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_efootprint_contract.py \
        audits/<site> --freeze

    # After each modification
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_efootprint_contract.py \
        audits/<site> --total 174.076

Reports lost paths and type changes (errors), added paths (information).
Exit code 1 on a problem.

Baselines go to `tmp/baselines/`, outside git.

**Its limit, to know**: it checks that keys exist and keep their type, not that
values are correct. A total going from 174 to 300 kg with all keys in place
would not be seen. Hence `--total`, to use as a complement, not as a replacement.

### `check_genericite.py` — the code is not glued to the test case

Fails if the executable code contains a domain name, an IP, an audit-case path,
or **a value measured on one specific site** (the sneakiest mistake: a bare
number looks like a physical constant).

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_genericite.py
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_genericite.py --list-values
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_genericite.py --audit-exemptions

Default target: `efootprint_model/`. As long as it does not exist, the script
exits 0 with a message: that is not a failure.

Docstrings and comments are excluded from the analysis, a documented example
being legitimate. A legitimate occurrence in the code is exempted with its
reason:

    RAW_DATA_DIR = "..."        # genericity: ok - constant declaration

    TRACKER_DOMAINS = {         # genericity: ok-start - explicit third-party table
        "google-analytics.com",
    }                           # genericity: ok-end

An exemption without a written reason is refused.

**Its limit, to know**: it catches copy-paste, not design bias. A function that
assumes a two-server site, or full HTML served, passes without a flinch. Only
execution on a second real site proves genericity. Short integers (82, 317) are
reported as "to check" rather than asserted: they may legitimately mean
something else.

**An unanalyzable file is a violation, not a compliant file.** Hole found in
lot 1 and fixed: a class whose body was only a docstring became an empty body
after cleaning, which broke the syntactic analysis and deactivated *all*
checking of the file's measured values, without any message. The script exited
green without having examined anything. A net that disables itself is worse than
an absent net: you believe you are protected.

### `check_efootprint_spec.py` — the guards still refuse

The `efootprint_model/` library relies only on refusals: a value without
provenance is refused, a key pointing nowhere is refused, a key collision is
refused. A broken guard produces no error, it just lets things through. This
script therefore checks both directions: a correct specification passes, **and
each expected fault is indeed refused**. Only the second direction proves anything.

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_efootprint_spec.py
    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/check_efootprint_spec.py -v

92 checks. It also verifies that the error message mentions the cause: a refusal
in the right place with an incomprehensible message loses the benefit of the guard.

**Its limit, to know**: it checks no CO2e figure, the controlled library
computing none. Numerical non-regression remains that of
`check_efootprint_contract.py`.

### Any newly published value must join the list

When a figure measured on an audit case goes into a report, add it to
`FORBIDDEN_VALUES` with its origin. Otherwise the net goes stale without warning.

Likewise, any new guard added to `efootprint_model/` must receive its refusal
check in `check_efootprint_spec.py`. An untested refusal ends up disappearing
at some reshuffle, silently.
