# Step 25 — DISPATCH orchestration (analysis waves)

> Source: skill-steps/25_dispatch-orchestration.md. Triggered from SKILL.md after step 10.
> Return: after the final merge, resume in SKILL.md at step 35.

This file drives the execution of the HAR/Coverage/CWV/env-data/security
analyses (Wave 1) and of the env-data.json-dependent EOF extractors (Wave 2)
via DISPATCH blocks.

-----

## DISPATCH protocol

### Capability detection

Before starting the waves, assess your ability to spawn a sub-agent with an
isolated context window (Agent tool, subagent API, or equivalent mechanism):

- **YES (sub-agents available)**: each DISPATCH block is dispatched into an
  isolated context. The blocks of the same wave (5 in Wave 1, 2 in Wave 2) run in parallel.
- **NO (single context)**: execute each DISPATCH block sequentially in the
  current context, reading/writing the same files on disk.

Whatever the mode, the on-disk outputs are identical.

### Complexity tier per sub-agent (model-agnostic)

Each `:::dispatch` block carries a `COMPLEXITE:` field (A/B/C/D): an abstract
tier that names no model or LLM provider, only the intrinsic difficulty
of the Python script wrapper to execute — not a business judgment to
make, but an orchestration task (call the right script, interpret its
JSON output, handle a documented fallback or report a detected anamealy).
It is pre-computed from stable factual signals already present in each
block's text: number of external sources cross-referenced by the script,
presence of a fallback to a documented alternative method, presence
of a validation watch beyond simple wrapping (anamealy detected
and reported to the user).

**Before dispatch**, resolve this tier yourself into concrete model and effort,
with your current knowledge of the execution environment (which models
are available, which is the most econameical / the most capable). To help
you judge, consult the tier grid (econameical/standard/advanced model,
low/medium/high effort, with the concrete justification of each tier)
in the skill `calibrer-complexite-dispatch-analyse-parcours`, then choose
in your harness whatever fits best. Never write a model name in this file, and
never recompute `COMPLEXITE` during a journey analysis: this calculation has
a token cost and must be done once, not at each dispatch. Do not raise a tier
"out of caution" if the signals do not justify it — that is exactly the waste
this logic aims to avoid (a simple API call, for example, is not in itself a
reason for tier D: only the effective accumulation of several signals from the
formula justifies it).

If the tier grid needs refining (thresholds to adjust, new cases
encountered), invoke the skill `calibrer-complexite-dispatch-analyse-parcours`
— which itself contains no model name either, only abstract tiers
and concrete judgment criteria.

### Variable substitution

**Before any dispatch**, substitute in the block text:
- `{{SOURCE_DIR}}` with the absolute path of the source folder (where the HAR and Coverage live)
- `{{AUDIT_DIR}}` with the absolute path of the audit folder (`SOURCE_DIR/audit/`)
- `{{HAR_FILE}}` with the absolute path of the `.har` file (in `SOURCE_DIR`)
- `{{COVERAGE_FILES}}` with the list of `Coverage-*.json` file paths (in `SOURCE_DIR`)

### File layout convention for produced files

Two locations coexist, to be respected exactly (checked script by
script, do not improvise):
- **`{{AUDIT_DIR}}`** (`SOURCE_DIR/audit/`): `har-analysis.json`,
  `coverage-analysis.json`, `cwv.json`
- **`{{SOURCE_DIR}}`** (root): `env-data.json`,
  `security-headers-analysis.json`, `html-css-criteria.json`,
  `wellknown-scan.json`

### Success condition of a DISPATCH block

A block is considered complete when its `OUTPUT_FILE` exists on disk with data.
If the file is absent after execution, re-run the block once.
If still absent: note the failure, report it to the user and continue in degraded mode.

-----

## Wave 0 — Location (main context — mandatory)

Wave 0 runs entirely in the main context BEFORE any DISPATCH.
The `.har` file and the `Coverage-*.json` must be identified and verified
(step 10 already executed).

Check that the identified files are accessible:
```
ls -lh {{HAR_FILE}}
ls -lh {{COVERAGE_FILES}}
ls -d {{AUDIT_DIR}}
```

→ Display: `✅ Wave 0 complete — launching Wave 1 (HAR + Coverage + CWV + env-data + Security)`

-----

## Wave 1 — HAR + Coverage + CWV + env-data + security headers analysis (5 parallel dispatches)

The five blocks are mutually independent: each reads only the
raw `.har` and/or the raw `Coverage-*.json` and/or calls an external API
— none reads another block's output from this wave. Two of them
(`analyze-har`, `extractor-security-headers`) also read `env-data.json`
in a **soft** way (documented and code-verified degradation if the file
does not exist yet when they run — never a crash): whether
`collect-env-data` finishes before or after them changes nothing about the validity
of the result, only its precision (domain classification/page filtering
a bit less precise in its absence).

> Display: `▶ Wave 1 — HAR + Coverage + CWV + env-data + Security analysis (5 parallel dispatches)`

-----

:::dispatch id="analyze-har" wave="1" parallel_with="analyze-coverage,collect-cwv,collect-env-data,extractor-security-headers"
OUTPUT_FILE: {{AUDIT_DIR}}/har-analysis.json
AUDIT_DIR: {{AUDIT_DIR}}
HAR_FILE: {{HAR_FILE}}
PIPELINE: skill-steps/20_har-analysis.md
COMPLEXITE: B

Read and execute the pipeline `skill-steps/20_har-analysis.md`.

The calculation is done by a script, NOT by hand. A manual read of the `.har`
had already produced a key (`blocking_resources`) invented by eyeballing the HTML,
not replayable:

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/analyze_har.py {{SOURCE_DIR}} --output {{AUDIT_DIR}}/har-analysis.json
```

The script classifies 1st-party/3rd-party domains from `env-data.json`,
deduplicates by URL before the top10 of the heaviest resources, detects
uncached requests, URL duplicates and slow third-party resources
(> 1 s), and computes the blocking resources of the `<head>` only for
pages whose HTML archive (work item 27, `<source_dir>/html-pages/`) is
available — otherwise the field is marked not computed, never guessed from
the MIME type alone.

Expected format:
{
  "total_requests": N,
  "domains": {"first_party": [...], "third_party": [...]},
  "http_codes": {"200": N, "304": N, ...},
  "total_size_kb": N,
  "top10_heaviest": [...],
  "uncached_requests": N,
  "duplicate_urls": [...],
  "slow_third_party": [...]
}
Return only: "har-analysis.json written — <N> requests, <N> domains, <X> MB"
:::

-----

:::dispatch id="analyze-coverage" wave="1" parallel_with="analyze-har,collect-cwv,collect-env-data,extractor-security-headers"
OUTPUT_FILE: {{AUDIT_DIR}}/coverage-analysis.json
AUDIT_DIR: {{AUDIT_DIR}}
SOURCE_DIR: {{SOURCE_DIR}}
COVERAGE_FILES: {{COVERAGE_FILES}}
PIPELINE: skill-steps/30_coverage-analysis.md
COMPLEXITE: B

Read and execute the pipeline `skill-steps/30_coverage-analysis.md`.

The calculation is done by a script, NOT by hand. An extension test on the full URL
once published a page at zero KB (versioned URLs):

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/coverage_metrics.py {{SOURCE_DIR}} --output {{AUDIT_DIR}}/coverage-analysis.json
```

The script detects the Coverage file format, classifies JS/CSS on the URL
path, labels each page from the HTML document corroborated by the HAR,
identifies third-party libraries and reports outliers.

Then check the output: any page marked `no_js_no_css` must be reported to
the user — it is the symptom of a misclassification, not of a page without code.

Produced format:
{
  "pages": [
    {
      "name": "Page 1",
      "source_file": "Coverage-....json",
      "url": "https://...", "url_provenance": "HTML document confirmed by the HAR",
      "js_total_kb": N, "js_unused_kb": N, "js_unused_pct": N,
      "css_total_kb": N, "css_unused_kb": N, "css_unused_pct": N,
      "resources_count": N, "no_js_no_css": false,
      "top_js_unused": [...], "top_css_unused": [...]
    }
  ],
  "summary": {
    "pages_count": N,
    "total_js_kb": N, "total_js_unused_kb": N, "total_js_unused_pct": N,
    "total_css_kb": N, "total_css_unused_kb": N, "total_css_unused_pct": N,
    "third_party_libraries": [...], "outlier_pages": [...],
    "har_reference": "....har"
  }
}
Return only: "coverage-analysis.json written — <N> pages, unused JS: <X> MB (<Y>%), unused CSS: <X> KB (<Y>%)"
:::

-----

:::dispatch id="collect-cwv" wave="1" parallel_with="analyze-har,analyze-coverage,collect-env-data,extractor-security-headers"
OUTPUT_FILE: {{AUDIT_DIR}}/cwv.json
AUDIT_DIR: {{AUDIT_DIR}}
SOURCE_DIR: {{SOURCE_DIR}}
PIPELINE: skill-steps/37_lighthouse.md
COMPLEXITE: B

Read and execute the pipeline `skill-steps/37_lighthouse.md`, section
"PageSpeed Insights + CrUX". Call the extended variant directly
(accessibility + best-practices categories already included in the script,
`--strategy both` = default) to avoid a second pass:

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py {{AUDIT_DIR}} --strategy both
```

If `GOOGLE_API_KEY` is absent from `.env` or no metric was collected (quota,
network, URLs unknown to CrUX): the script itself falls back to
Lighthouse (`run_lighthouse.sh`), no need to invoke it manually.

If the failure persists (npx missing, pages unreachable): note the failure,
continue without `cwv.json` — the report will then show HAR `onLoad` as an
LCP proxy.

Return only: "cwv.json written — <N> pages, mobile+desktop, sources: <crux/pagespeed_lab/lighthouse>"
:::

-----

:::dispatch id="collect-env-data" wave="1" parallel_with="analyze-har,analyze-coverage,collect-cwv,extractor-security-headers"
OUTPUT_FILE: {{SOURCE_DIR}}/env-data.json
SOURCE_DIR: {{SOURCE_DIR}}
PIPELINE: skill-steps/45_efootprint.md (Step 20)
COMPLEXITE: C

Read and execute the pipeline `skill-steps/45_efootprint.md`, section
"Step 20 - Collecting env-data.json" (HAR + CrUX + ipinfo + SimilarWeb
country/traffic mix collection):

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py {{SOURCE_DIR}}
```

Do NOT pass `--refresh` here (first collection of the wave): if
`env-data.json` already exists (audit re-run on an already processed folder), the
script preserves it as-is. Documented degraded mode: in the absence of an API key
(`GOOGLE_API_KEY`/`IPINFO_TOKEN`) or in case of network failure, the script
continues with fields marked `confidence: default`, never a crash.

Return only: "env-data.json written — <N> servers detected, country mix: <source>, traffic: <source>"
:::

-----

:::dispatch id="extractor-security-headers" wave="1" parallel_with="analyze-har,analyze-coverage,collect-cwv,collect-env-data"
OUTPUT_FILE: {{SOURCE_DIR}}/security-headers-analysis.json
SOURCE_DIR: {{SOURCE_DIR}}
PIPELINE: skill-steps/39_eof-audit.md
COMPLEXITE: A

Read and execute:

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/analyze_security_headers.py {{SOURCE_DIR}}
```

The script reads only the already captured `.har` (response headers),
no network call. If `env-data.json` is not yet written at execution time
(block `collect-env-data` of the same wave, order not guaranteed):
the script then analyzes ALL the HTML pages of the HAR instead of filtering on
the `env-data.json["pages"]` list — degradation documented in the code
(`analyze_security_headers.py::load_page_urls`), never a crash.

Return only: "security-headers-analysis.json written — lowest-rated page: <url> (<score>%, grade <grade>)"
:::

-----

> Wait for `har-analysis.json`, `coverage-analysis.json`, `cwv.json`,
> `env-data.json` and `security-headers-analysis.json` to exist (or be
> marked as explicit failures) before launching Wave 2.

-----

## Wave 2 — EOF extractors dependent on env-data.json (2 parallel dispatches)

Unlike the Wave 1 blocks, these two extractors have a
**hard** dependency (not a degradation) on `{{SOURCE_DIR}}/env-data.json`:
`parse_html_criteria.py::load_page_urls()` (lines 149-160) and
`main()` (lines 578-581) call `sys.exit(1)` if the file is absent or has
no page; `scan_wellknown.py::infer_domain()` (lines 244-253) and `main()`
(lines 262-267) do the same. **Do not dispatch these two blocks before
confirming `{{SOURCE_DIR}}/env-data.json` on disk** (Wave 1 block
`collect-env-data` finished) — a simple retry is not enough to
compensate for this hard dependency, unlike the soft degradations of
Wave 1.

> Display: `▶ Wave 2 — HTML/CSS + well-known extractors (2 parallel dispatches)`

-----

:::dispatch id="extractor-html-css" wave="2" depends_on="collect-env-data" parallel_with="extractor-wellknown"
OUTPUT_FILE: {{SOURCE_DIR}}/html-css-criteria.json
SOURCE_DIR: {{SOURCE_DIR}}
COMPLEXITE: B

Read and execute:

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/parse_html_criteria.py {{SOURCE_DIR}}
```

Live re-fetch of the already audited pages (the captured `.har` does not contain the
HTML/CSS bodies). Archives the pages under `{{SOURCE_DIR}}/html-pages/`
(work item 27) — this archive, if it already exists BEFORE the Wave 1
block `analyze-har` runs, lets `analyze_har.py` compute
`blocking_resources`; since `analyze-har` always runs before this
Wave 2 in this breakdown, this secondary field will remain "not computed" on
the first full pass over a new folder — known limitation, not a
bug to fix.

Return only: "html-css-criteria.json written — <N> pages, <N> CSS stylesheets analyzed"
:::

-----

:::dispatch id="extractor-wellknown" wave="2" depends_on="collect-env-data" parallel_with="extractor-html-css"
OUTPUT_FILE: {{SOURCE_DIR}}/wellknown-scan.json
SOURCE_DIR: {{SOURCE_DIR}}
COMPLEXITE: A

Read and execute:

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/scan_wellknown.py {{SOURCE_DIR}}
```

Direct fetch of `security.txt`/`robots.txt`/`sitemap.xml` on the domain
inferred from `env-data.json` (2-3 public HTTP requests, no authentication).

Return only: "wellknown-scan.json written — security.txt: <present/absent>, robots.txt: <present/absent>, sitemap: <present/absent>"
:::

-----

> Wait for `html-css-criteria.json` AND `wellknown-scan.json` to exist (or
> be marked as explicit failures) before the merge.

-----

## Final merge

Waves 1 and 2 are done (or marked as explicit failures, best-effort —
a failure on `collect-cwv`/`collect-env-data`/the two Wave 2 extractors
degrades what follows, it does not block it). Check the presence of:
- `{{AUDIT_DIR}}/har-analysis.json` — key `total_requests` (mandatory)
- `{{AUDIT_DIR}}/coverage-analysis.json` — key `pages` (mandatory)
- `{{AUDIT_DIR}}/cwv.json` (optional — absence reported, not blocking)
- `{{SOURCE_DIR}}/env-data.json` (optional)
- `{{SOURCE_DIR}}/security-headers-analysis.json` (optional)
- `{{SOURCE_DIR}}/html-css-criteria.json` (optional)
- `{{SOURCE_DIR}}/wellknown-scan.json` (optional)

Display a short summary (file / present / absent) for all 7.
The first two are mandatory (blocking warning if absent, cf.
steps 20/30 of SKILL.md); the other five are best-effort enrichments
consumed later by step 39 (EOF) and step 40
(report) — their absence never blocks the rest of the pipeline, it only
reduces coverage (EOF: criteria in "I don't know"; report:
sections omitted).

→ Then return to SKILL.md at **Step 35** (EcoIndex calculation).
