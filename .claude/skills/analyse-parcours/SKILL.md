---
name: analyse-parcours
description: >
  This skill activates when the user wants to "analyze a web journey", "analyze a HAR",
  "analyze Chrome coverage", "dead JS/CSS code",
  "DevTools coverage", "analyze the traffic of a journey",
  or mentions .har files or Coverage-*.json from Chrome DevTools.
  It also activates for CO2e estimation (e-footprint): "estimate the carbon footprint",
  "CO2 impact", "environmental footprint", "efootprint",
  "ecological footprint of the site", "/efootprint", or mentions an env-data.json /
  efootprint-boavizta-model.json.
version: 1.2.1
---

# Web journey analysis (HAR + Coverage)

## Overview

This skill analyzes a complete web journey from:
1. A **HAR** (HTTP Archive) file - Chrome DevTools network traffic export
2. **Coverage JSON** files - Chrome DevTools > Coverage export (one file per page)

It produces two types of analysis:
- **Network traffic**: requests, domains, volumes, HTTP codes, performance
- **Performance/Eco**: EcoIndex (score + grade A-G), dead JS/CSS code, Core Web Vitals

**User documentation**: `docs/capture-har-and-coverage.md` - step-by-step procedure to capture a HAR, the Coverage files and the optional `cwv.json` file.

**Optional `cwv.json` file** (manually measured Core Web Vitals):
```json
[
  {"page": "page_1", "lcp": 0.76, "inp": 8, "cls": 0.06},
  {"page": "page_2", "lcp": 1.9,  "inp": 16, "cls": 0.66}
]
```
If absent: the report shows HAR `onLoad` as a proxy for LCP.

---

## Invocation

```
/analyse-parcours <folder-path>
/analyse-parcours <file.har> <coverage1.json> <coverage2.json> ...
/efootprint <source_dir>          # step 45 only (CO2e estimation)
```

The skill is also triggered automatically when the `plugin.json` triggers match.

---

## Step 10 — File location

→ See `skill-steps/10_location.md`

Extract from the prompt:
- A **folder** path containing the HAR and JSON files
- Or direct paths: `<file.har> [coverage1.json coverage2.json ...]`

If no argument provided: ask the user for the path.

---

## Step 15 — sessionId capture

Immediately after determining SOURCE_DIR and AUDIT_DIR (step 10), capture the sessionId for the report cost calculation:

```bash
AUDIT_DIR="<SOURCE_DIR>/audit"
mkdir -p "$AUDIT_DIR/analyse-cout-agent"
if [ -f "$HOME/.claude/.current_session_id" ]; then
  cp "$HOME/.claude/.current_session_id" "$AUDIT_DIR/analyse-cout-agent/.cost-session-id"
  date +%s > "$AUDIT_DIR/analyse-cout-agent/.cost-start-ts"
fi
```

These files will be read by `patch-audit-cost.sh` (called at the end of step 40): `.cost-session-id` to identify the session, `.cost-start-ts` to bound the duration to the actual start of the analysis (and not the start of the whole session).

---

## Step 20 — HAR file analysis

→ See `skill-steps/20_har-analysis.md`

Extract from the HAR:
- Traffic overview (requests, domains, HTTP codes, volume)
- Network performance metrics (cache, duplicates, heavy resources)

---

## Step 25 — DISPATCH orchestration

→ See `skill-steps/25_dispatch-orchestration.md`

Two parallel waves via the DISPATCH mechanism. If sub-agents are
available (Claude Code), the blocks of the same wave run in isolated
contexts simultaneously. Otherwise, they run inline one after another. Outputs
are identical in both cases.

- **Wave 1** (5 parallel dispatches): HAR analysis (step 20), Coverage analysis
  (step 30), CWV collection (step 37), env-data collection (step 45
  Step 20), security header extraction (step 39) → produces
  `har-analysis.json`, `coverage-analysis.json`, `cwv.json`, `env-data.json`,
  `security-headers-analysis.json`.
- **Wave 2** (2 parallel dispatches, depends on `env-data.json` produced in
  Wave 1): HTML/CSS criteria + well-known extraction (step 39) → produces
  `html-css-criteria.json`, `wellknown-scan.json`.

Only `har-analysis.json` and `coverage-analysis.json` are required to
continue; the other 5 files are best-effort enrichments
(EOF/report degraded but not blocked in their absence).

---

## Step 30 — Coverage file analysis

→ See `skill-steps/30_coverage-analysis.md`

Run automatically by step 25 (Wave 1, block `analyze-coverage`) —
this section documents the processing and its CLI command for an
isolated manual re-run.

For each Coverage JSON file:
- Per-page metrics (total size, unused code, % rate)
- Most expensive files (JS + CSS)
- Multi-page summary

---

## Step 35 — EcoIndex calculation

→ See `skill-steps/35_ecoindex-calculation.md`

Automatic calculation from the HAR (official formula):
- DOM extracted from the HTML body (`response.content.text`)
- Requests and weight aggregated per page
- Score 0-100 + grade A-G with color code

```bash
python3 .claude/skills/analyse-parcours/scripts/har_metrics.py <har-file> [cwv.json]
```

---

## Step 37 — CWV via Lighthouse

→ See `skill-steps/37_lighthouse.md`

Run automatically by step 25 (Wave 1, block `collect-cwv`) —
this section documents the processing and its CLI command for an
isolated manual re-run (e.g. "re-run Lighthouse").

If `cwv.json` is absent: automatically launch the Lighthouse CLI via `npx` by extracting
the URLs from the HAR. Generates `cwv.json` with LCP, INP, CLS measured in lab mode.
If already present: skipped. If failure: warning and report without CWV.
The user can force a re-run by saying "re-run Lighthouse".

---

## Step 39 — Optimization potential (EOF framework)

→ See `skill-steps/39_eof-audit.md`

**Automatic** step (not a command), sequential: wait for
`har-analysis.json` and `coverage-analysis.json` to exist (Waves 1/2 of
step 25) before launching it, before the report. The three extractors
it consumes (`security-headers-analysis.json`, `html-css-criteria.json`,
`wellknown-scan.json`) are now produced automatically by Waves 1/2 of
step 25, no need to launch them manually beforehand.
Fills what can be filled of the EOF-V.1.1 framework from
`eof-reference.json` (skill `eof`) and the data already collected — never
the Google Sheet. Out of 54 detailed criteria, only ~10 are usable
(4 automatable, 6 partial indicators); the others remain "I don't know"
by construction. If `eof-reference.json` is absent: step skipped,
report without EOF section.

---

## Step 39b — EOF questionnaire (generation and review)

→ See `skill-steps/39b_questionnaire-eof.md`

**Manual** step (mission decision, not an automatic calculation), possible
as soon as Step 39 has written `eof-audit-results.json`. Asks the audited
service the criteria that Step 39 could not decide automatically:

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_questionnaire.py <audit-dir> --output-dir /tmp/questionnaire-<domain>
```

**Never generate directly into `audits/<domain>/`** (the script
refuses by default, exit code 2): a generated questionnaire is blank, and
`--in-audit-dir` must only be used when it is actually going to the client.
Once the file comes back filled in, the review is done with
`parse_questionnaire.py` (writes `lots/questionnaire-review.json`);
see the step file for what follows (lot merging, warning about
`run_eof.py`).

---

## Step 40 — HTML report

→ See `skill-steps/40_report.md`

Sequential step: wait for `cwv.json`, `env-data.json` and
`eof-audit-results.json` to exist (or be marked absent/degraded) before
launching it — corresponding sections are simply omitted if absent,
never a blocker.

Generates `journey-report-YYYY-MM-DD.html` in the audit folder:

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <audit-dir>
```

Sections: EcoIndex | Network traffic | Dead code | CWV (if cwv.json) | Recommendations

---

## Step 45 — CO2e estimation (e-footprint)

→ See `skill-steps/45_efootprint.md`

**Optional** step, triggered by `/efootprint <source_dir>` or by phrases
like "estimate the carbon footprint" / "CO2 impact". Reuses `env-data.json` (HAR +
CrUX + SimilarWeb country/traffic mix) to compute a hypothetical CO2e estimate via
the e-footprint library (Boavizta), then inserts an "Environmental impact"
section into the HTML report (Step 40) if `efootprint-python-summary.json` is present.

If `/analyse-parcours` has already run on this folder, `env-data.json` probably
already exists (produced by Wave 1 of step 25, block
`collect-env-data`): its own Step 20 (§below, `skill-steps/45_efootprint.md`)
is then limited to proposing `--refresh` if the data needs to be refreshed.
The standalone `/efootprint <source_dir>` flow, without a prior
`/analyse-parcours`, remains unchanged: it re-runs `collect_env_data.py` itself if
necessary.

---

## CLI tool maintenance

→ See `scripts/README-tools.md`

### Initial Lighthouse install (once only)

```bash
npm install --prefix .claude/skills/analyse-parcours/scripts/
```

### Check if Lighthouse is up to date

```bash
npm outdated --prefix .claude/skills/analyse-parcours/scripts/
```

### Update Lighthouse

```bash
npm update lighthouse --prefix .claude/skills/analyse-parcours/scripts/
```

The user can tell Claude "check if Lighthouse is up to date" or "update Lighthouse".
Claude runs `npm outdated`, reads the output and proposes or runs `npm update`.

---

## Cross-cutting rules

### HAR file size

HARs can exceed 5 MB (50,000+ lines). Proceed by selective reading:
- Read the JSON header to know the number of entries
- Process entries in batches if necessary
- Do not load everything in a single pass

### Sensitive data

If the HAR contains credentials or tokens:
- **Never** display them in clear text
- Mask: `{"password":"***"}`, `token=****...abc`
- Truncate UIDs: `uid=8116...92`

### Progress

Display a progress line at each step:
```
▶ Step 10 — File location
▶ Step 15 — sessionId capture (silent)
▶ Wave 1 — HAR + Coverage + CWV + env-data + Security analysis (5 parallel dispatches)
▶ Wave 2 — HTML/CSS + well-known extractors (2 parallel dispatches)
▶ Step 39 — EOF audit
▶ Step 40 — Summary report
```
