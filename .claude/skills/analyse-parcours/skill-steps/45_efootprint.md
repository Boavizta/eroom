# Step 45 - CO2e estimation (e-footprint)

## Overview

This step orchestrates the calculation of a CO2e estimate of the analyzed site,
via the e-footprint library (Boavizta). It relies on the existing
scripts in `.claude/skills/analyse-parcours/scripts/`:

- `collect_env_data.py`: collects HAR + CrUX + ipinfo -> `env-data.json`
- `run_efootprint.py`: CO2e calculation + serialization -> `efootprint-boavizta-model.json`

**This step does not duplicate the logic**: it detects, asks, calls.

-----

## MANDATORY WARNING

All produced values are **hypothetical estimates**.
They rest on automatically collected data (HAR, CrUX, ipinfo)
and on many default assumptions (traffic, instance, electricity mix).

These results **are not a real measurement** of the
environmental impact. They give an order of magnitude to compare
scenarios or identify the dominant items.

This reminder must appear:
- at the start of the step (before asking for parameters)
- on each entered parameter (`hypothesis` or `parameter`)
- in the final results summary

-----

## Invocation

```
/efootprint <source_dir>
/efootprint                       # source_dir inferred from the analyse-parcours context
```

Text triggers:
- "estimate the site's footprint"
- "calculate the CO2 impact"
- "e-footprint on this journey"
- "environmental impact"

-----

## Architectural principle: each step is re-runnable

```
Step 10 -> source_dir           (detection or input)
Step 20 -> env-data.json        (collect_env_data.py, permanent cache)
Step 25 -> overview (topology + suspected DB/streaming/AI, PlantUML)
Step 30 -> user parameters (AskUserQuestion on traffic + instance)
Step 40 -> efootprint-boavizta-model.json + efootprint-python-summary.json (run_efootprint.py, recalculated at each run)
Step 50 -> synthesis + proposals
```

Each step can be re-run independently:
- Re-run step 20: pass `--refresh` to `collect_env_data.py`
- Re-run step 25: call `build_topology_overview()` again (no parameter,
  re-reads env-data.json + the HAR as they are at call time)
- Re-run step 40: call `run_efootprint.py` again with other `--visits` or `--instance`

-----

## Step 10 - Locating source_dir

Objective: determine the folder containing the HAR (or at least an `env-data.json`).

Resolution order:
1. **Explicit argument**: `/efootprint <path>` -> use as-is
2. **analyse-parcours context**: if a HAR was analyzed recently in the
   conversation, suggest its parent folder to the user for confirmation
3. **Open file**: if a `.har` is visible in the context, suggest its parent
4. **Default**: ask via AskUserQuestion with a list of folders
   containing a `.har` or an `env-data.json` at the project root

Then verify that `source_dir` exists and contains either a `.har` or an
`env-data.json`. Otherwise: report degraded mode and offer to give up or
to create `env-data.json` manually.

-----

## Step 20 - Collecting env-data.json

If this folder was already processed by `/analyse-parcours`, `env-data.json`
probably already exists (Wave 1 of step 25, block `collect-env-data`,
cf. `skill-steps/25_dispatch-orchestration.md`): this step is then
limited to offering `--refresh` if the data must be refreshed. The
standalone `/efootprint <source_dir>` flow (without a prior `/analyse-parcours`)
remains unchanged below.

Check the presence of `<source_dir>/env-data.json`:

- **Absent**: run `collect_env_data.py <source_dir>` (without `--refresh`)
- **Present**: offer via AskUserQuestion:
  - "Use the existing cache" (default, fast)
  - "Fresh re-collection (--refresh)" (useful if the HAR was updated)

**Degraded mode**: if `collect_env_data.py` fails (no HAR, no API key),
the step continues with what exists. Explicitly report the fields
in `confidence: default` -- they will have the highest impact on precision.

After collection, display a short summary of the collected data (2-3 lines).

### Step 20b - Audience country mix (iOS/macOS weighting)

The country mix is used **only** to weight the iOS (mobile) and macOS (desktop)
shares of the CrUX correction (CrUX = Chrome only; see Step 30). It does not touch the CWVs.
Priority order (resolved by `collect_env_data.py`):

1. **`--audience` entered** (most reliable): if the user has the site's
   analytics (GA/Matomo), ask for the country split and pass it as
   `--audience "FR:0.7,US:0.3"` (or single-country shorthand `--audience FR`).
2. **Internal SimilarWeb API** (automatic, see Step 20e): `collect_env_data.py`
   queries the API itself when the `audience` block is missing and no `--audience`
   is provided. This is the default path when client analytics are unavailable.
3. **Assisted retrieval** (Step 20d): if the API fails (403, untracked domain).
4. **France default (100%)** + warning: last resort.

The `audience` block written (by the API or assisted) has this format:
```json
"audience": {
  "mix": {"FR": 0.61, "SN": 0.105, "US": 0.041},
  "source": "SimilarWeb (estimate)",
  "source_url": "https://www.similarweb.com/website/<domain>/",
  "confidence": "medium"
}
```
`source_url` is reused as-is in the report as a "↗ source" link next to the provenance label of the mix. `collect_env_data.py --refresh` **preserves** an `audience` block already present with a real source (unless `--audience` is provided, which takes precedence), renormalizes it and computes the weighted iOS/macOS shares.

**Mandatory caveat**: SimilarWeb is a rough estimate, unofficial source, borderline ToS use. The caveat also appears in the report appendix.

### Step 20c - Annual traffic volume (visits/year)

Same logic as the country mix: **no public API** (PageSpeed, CrUX) gives
audience volume (only distributions, never counters). Traffic is therefore
resolved by priority order:

1. **`--visits` entered** (most reliable, in `run_efootprint.py`): the site's
   analytics (GA4/Matomo/server logs).
2. **Internal SimilarWeb API** (automatic, see Step 20e): `collect_env_data.py`
   fills the `traffic` block when it is missing. Default path when analytics are unavailable.
3. **Assisted retrieval** (Step 20d): if the API fails.
4. **Default 100,000 visits/year** + warning: last resort.

The written `traffic` block has this format:
```json
"traffic": {
  "visits_per_year": 440000,
  "monthly_visits": 36700,
  "source": "SimilarWeb (estimate)",
  "source_url": "https://www.similarweb.com/website/<domain>/",
  "snapshot": "June 2026",
  "confidence": "medium"
}
```

- `visits_per_year` = `monthly_visits × 12` (annualization). Filling in `monthly_visits`
  and `snapshot` (month of the measurement) lets the report display the derivation.
- `collect_env_data.py <source_dir> --refresh` **preserves** this `traffic` block (like
  `audience`); `run_efootprint.py` reads it automatically if `--visits` is not passed.
- `source_url` is reused as a "↗ source" link in the report (body + appendix D).
- **Mandatory caveat**: third-party estimate with a **wide margin**, not a measurement. Only
  the site's analytics give an exact figure. Also recall that total CO2e **grows**
  with traffic (above a fixed base of server manufacturing + storage) while CO2e **per visit**
  decreases when traffic increases (affine relationship).

### Step 20d - Assisted retrieval if the SimilarWeb API fails (captcha / WAF challenge)

SimilarWeb regularly serves an **image-selection captcha** or an AWS WAF challenge
to automated access. **Never invent figures, do not bypass the
captcha**: the data must go through the user. Two ways, offer
**both**.

**Trigger**: the automatic call to the internal API (Step 20e, launched by
`collect_env_data.py`) fails — CloudFront 403, little/untracked domain (message
`⚠ SimilarWeb: …`), or network. Do NOT silently fall through to the default:
offer this assisted retrieval first.

Message to display (adapt `<domain>` and the exact URL):

> 🔒 **SimilarWeb is blocking me (captcha). I need your help to retrieve the traffic
> and the audience country mix.**
>
> 1. Open this URL in your browser: `https://www.similarweb.com/website/<domain>/`
> 2. Pass the captcha (image selection).
> 3. Find these **two** pieces of information on the page:
>    - **Total Visits**: the big monthly traffic figure (e.g. "36.7K") **+ the displayed
>      period** (e.g. "Jun 2026").
>    - The **"Top Countries"** block: the top 3-5 countries with their percentages
>      (e.g. FR 61%, SN 10%, US 4%, TN 3%, BR 3%).
> 4. Send them to me **either way**:
>    - **Way A - dictation**: paste these values directly in the chat (fastest).
>    - **Way B - screenshot**: take one or two screenshots clearly showing these
>      two blocks, drop them in the `<source_dir>/` folder and name them
>      `similarweb-<domain>.png` (or `.jpg`), then tell me "done".

Details to properly "frame" the request, whichever way:
- **Always name the two** expected blocks (Total Visits **+ period**, Top Countries):
  do not ask for "the whole page", ask for these specific areas.
- **Way A (dictation)**: after receiving, read back to the user what you understood
  (monthly figure, period, country list %) before writing, to catch a typo.
  `source` = `"SimilarWeb (manual entry after captcha)"`.
- **Way B (screenshot)**: readable formats = **PNG, JPG/JPEG, WebP, PDF**. **Avoid saved
  HTML** (Cmd+S): SimilarWeb figures are loaded in JavaScript, the raw HTML
  is often empty. The only real constraint is **readability** (clear figures,
  present in the image). Read the dropped file with the Read tool, extract the values.
  `source` = `"SimilarWeb (screenshot after captcha)"`.
- **Writing**: in both cases, write the `audience` (Step 20b) **and**
  `traffic` (Step 20c) blocks into `env-data.json`, with `source_url` = the consulted URL and
  `snapshot` = the read period, then re-run `collect_env_data.py <source_dir> --refresh`
  (which preserves both blocks). The source label and the "↗ source" link appear
  as-is in the report (body + appendix D): distinct from real client analytics.
- **Last resort**: if the user cannot provide the data (no access,
  page unavailable), only then fall back to the defaults (France 100% + 100,000/year)
  with the `⚠` warning, explicitly reported in the report.

### Step 20e - Automation via the internal SimilarWeb API (main path, integrated)

**Context:** The SimilarWeb Chrome/Firefox extension (`hoklmmgfnpapgjgcpechhaamimifchmp`) queries
an internal API (endpoint extracted from the `.crx`) that responds **without authentication**: no cookie, no
account, no session. The `similarweb_api.py` module reproduces this call and builds the
`audience` (20b) and `traffic` (20c) blocks. This is the **main path**: it avoids the captcha and
assisted entry in most cases.

**Integration (new):** `collect_env_data.py` calls this module **itself**, automatically,
when an `audience` or `traffic` block is missing. No need to run two commands anymore: a single
one suffices.
```bash
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --refresh
```
Associated options:
- `--sw-domain <domain>`: force the queried domain (otherwise inferred from `env-data.json`/HAR).
- `--no-similarweb`: disable the call (offline mode / avoid the network).
- The module remains usable in **standalone** for inspection: `similarweb_api.py <dir>
  [--domain octo.com] [--print-only]`.

**Trigger and guardrails** (the priority order remains sacred):
- Call launched **only** if the targeted block is missing (absent, or `source` = `default`/`None`).
- `--audience` provided → manual entry takes precedence, the API **does not write** the country mix (it can
  still complete the traffic if it is missing).
- Block already present with a real source → **never overwritten** (idempotent on `--refresh`).
- Blocks written with `source = "SimilarWeb (estimate)"` (neutral label, the API method remains internal doc),
  `source_url` (readable page `www.similarweb.com/website/<domain>/` for verification) and
  `snapshot`. Touches nothing else in `env-data.json`.

**What was validated (July 2026):**
- Endpoint: `https://data.similarweb.com/api/v1/data?domain=<domain>` (GET)
- **Sufficient** headers: `Content-Type: application/json`, `X-Extension-Version: 6.12.21`,
  and **a real browser `User-Agent`**.
- Returns `TopCountryShares` (country mix), `EstimatedMonthlyVisits` (visits/month),
  `Engagments`, `GlobalRank`, `TrafficSources`…: everything 20b/20c need.

**403 diagnostic (fixed):** the previously documented block did **not** come
from a lack of cookies (false hypothesis), but from two errors in the test request:
1. `Origin: chrome-extension://...` header → CloudFront rejects it (403). **Do not send it.**
2. Non-browser User-Agent (default of an HTTP client) → 403. **Send a browser UA.**
Without `Origin` and with a browser UA, the call answers **200** from a plain HTTP client.

**In case of failure** (403 reappears, little/untracked domain, network), `collect_env_data.py` displays a
`⚠ SimilarWeb: …` message then **continues without crashing**: then fall back to the **assisted
retrieval (Step 20d)**, not to the silent default. Note: the API answers 200 even for an
unknown domain, but without `TopCountryShares` or visits → the blocks are not built (explicit
message).

**Global source priority order** (country mix AND traffic):
1. Client analytics (`--audience` / `--visits`): the most reliable.
2. **Internal SimilarWeb API** (automatic, integrated into `collect_env_data.py`): main path.
3. Assisted retrieval (20d): if the API fails (captcha/WAF/untracked domain).
4. France 100% + 100,000/year defaults + `⚠`: last resort.

**Robustness to watch:** if the API goes back to returning 403, re-validate the extension version
(`EXTENSION_VERSION` in `similarweb_api.py`) and the absence of the `Origin` header. Caveat unchanged:
SimilarWeb remains a **third-party estimate with a wide margin**, unofficial source (borderline ToS use),
distinct from real client analytics: the caveat appears in the report appendix.

-----

## Step 25 - System overview before calculation

**WARNING (mandatory reminder):** what follows is a topology hypothesis built from the HAR, not a confirmed architecture. DB/streaming/AI detection is a SUSPICION (heuristic on network signals
visible on the client side), never a measurement — except for an AI/BaaS provider
recognized by its exact domain name, where the signal is almost certain.

Objective: before launching the CO2e calculation (Step 40), present to
the user the system the agent has "in mind" — detected servers,
third-party services, suspected DB/streaming/AI — and converge with them via
multiple-choice questions on this view before continuing.

### Step 25a - Building the overview

Call `run_efootprint.py::build_topology_overview(source_dir)` (chain:
`load_env_data` -> `find_har` -> `infer_audited_domain` -> `spec_from_env_data`
-> `detect_tech.detect_from_har` -> annotation of suspected third-party hosts ->
`site_to_plantuml`, with the audience country mix read from `env-data.json`). Depends on NO parameter of Step 30: traffic always has a resolved default
(100,000/year) from Step 20.

**Preconditions** (if not met, inform and offer to re-run Step 20
before continuing):
- a `.har` must exist in `source_dir` (or its
  `raw-data-potentially-sensitive/` subfolder)
- `env-data.json` must contain at least one detected server (`servers` non
  empty) — otherwise `collect_env_data.py` has not yet run with this HAR

`build_topology_overview()` raises `RuntimeError` with an actionable message
if a precondition is missing: display this message and offer to re-run
Step 20, never let a raw traceback bubble up.

### Step 25b - Text presentation

Display, in this order:
1. The "hypothetical estimate" reminder (cf. MANDATORY WARNING at the top
   of the file).
2. `print_hypotheses(spec)` (summary of detected servers, number of steps,
   default traffic) — already existing, reused AS-IS, BEFORE any --visits/--instance
   adjustment.
3. The topology summary (second element returned by
   `build_topology_overview()`):
   - Number and label of detected 1st-party servers.
   - Suspected Backend-as-a-Service / third-party DBs (exact domain
     recognized -> "identified"; otherwise -> "suspected").
   - Suspected media streaming (.m3u8/.mpd extension or
     video/audio content-type observed).
   - Identified third-party generative AI (recognized API domain: OpenAI,
     Anthropic, Google Generative AI, Mistral AI, Cohere, Azure OpenAI,
     Hugging Face).
   - **Honest and systematic reminder**, already included in the generated text:
     "a database or a self-hosted service BEHIND the application server
     emits no signal visible from the captured network traffic.
     This section can therefore NEVER conclude to its absence."
4. Any calculation reserve (`calculation_reserves(spec)`), for
   INFORMATION only at this stage (never blocking here — it only blocks
   at Step 40).

### Step 25c - Graphical presentation (PlantUML)

Announced priority to the user: **first the e-footprint web interface**
(https://e-footprint.boavizta.org/model_builder/), which remains the visual
reference if they want to use it directly. **Failing that** (to stay
autonameous, without a heavy dependency like Playwright), offer the automatically
generated PlantUML diagram (third element returned by
`build_topology_overview()`):

1. Write the PlantUML text to `<source_dir>/topology-<domain>.puml`
   (generated file, not committed — cf. `.gitignore`).
2. If `plantuml`/`rsvg-convert` are available in the environment:
   generate the SVG then the PDF (same commands as the skill
   `diagrammes-analyse-parcours`), and show it to the user.
   **PITFALL**: `plantuml -tsvg` names the output file after the
   `@startuml <id>` identifier of the diagram (e.g. `site_octo_com.svg`), NEVER after the
   name of the input `.puml` file. Always rename the produced SVG to
   `topology-<domain>.svg` right after generation (otherwise
   `load_topology_svg()` in `generate_report_html.py`, which only looks for
   `topology-*.svg`, does not find it and the HTML report falls back on a stale SVG
   or stays without a diagram).
3. Otherwise: present the raw PlantUML text in the conversation (they can
   paste it into https://www.plantuml.com/plantuml/uml/ for a one-off rendering
   without installation).

Layout: 3 side-by-side columns (Journey / Processing / Infrastructure),
taller than wide, enlarged font and folded text for readability
(cf. `to_plantuml.py` docstring for the tested attempts).

Diagram content: 1st-party servers (`database`), network processing
(including generative AI calls), third-party hosts — including those annotated with a
DB/streaming/AI suspicion showing their note in the component label — as well as
the main calculation assumptions: a global note (annual traffic, device mix,
audience country mix, cumulative journey reading time) and a
per-component detail (step time, transferred weight of the
processing, server instance/provider type). Value only, without a confidence badge:
the source/confidence detail remains in the report's assumptions table
(`print_hypotheses()`/dedicated HTML section), not duplicated here.

### Step 25d - Multiple-choice validation before continuing

Always converge with the user before Step 30, via `AskUserQuestion`:

```
Question : "Here is the system I identified from the captured journey.
            Does it match what you know about the site?"
Header   : "Detected topology"
Options  :
  - Yes, this topology is correct, we can continue - Recommended
  - No, a server or an infrastructure is missing (specify in the answer)
  - No, a suspicion (DB/streaming/AI) is wrong (specify which one)
  - I don't know / I want to verify on the e-footprint interface first
```

- **"Yes"** -> continue to Step 30.
- **"Infrastructure missing"** -> note the missing infrastructure
  (it cannot be added automatically by this lot, but keep it as a note
  for a future manual archetype, or report that it will be
  absent from the calculation).
- **"Wrong suspicion"** -> remove/correct the mention in the summary
  displayed to the user (do NOT modify the e-footprint model: this
  step stops at presentation).
- **"Verify on the interface"** -> recall the e-footprint web interface
  URL and wait for their feedback before continuing.

**Explicit limitation of this step (to repeat if the user expects
more):** it displays SUSPICIONS, it NEVER
automatically builds a dedicated DB server in the e-footprint model (later
lot, distinct, unscheduled — lead 3 of the comparative review). For third-party
**text** generative AI however (OpenAI/Anthropic/Gemini/Mistral/
Cohere/Azure OpenAI/Hugging Face), this step no longer stops at
presentation: see "Third-party generative AI" at Step 30 below, which can
include this call in the Step 40 calculation if the user knows
the exact model. Without an answer (or "I don't know"), the Step 40 calculation
remains strictly identical to what it was before this step.

-----

## Step 30 - User parameters

The non-auto-detectable parameters are asked via `AskUserQuestion`.
**Always** remind that these are hypotheses.

### Annual traffic

**Priority: reuse the volume already resolved at Step 20c** (client analytics via
`--visits`, or the SimilarWeb estimate of the `traffic` block). Only ask the
question below if no source is available and we must fall back to a manual hypothesis.

```
Question : "Which hypothetical annual traffic should be used for the estimate?"
Header   : "Estimated traffic"
Options  :
  - 10 000 visits/year   (showcase site, low traffic)
  - 100 000 visits/year  (active site, median order of magnitude) - Recommended
  - 500 000 visits/year  (content site with sustained traffic)
  - 1 000 000 visits/year (high-traffic site)
```

Allow "Other" for a free-form value. The chosen value is passed as `--visits`
(takes precedence over the `traffic` block). Always remind that it is an estimate.

### Instance type (only if a cloud provider is detected)

If `env-data.json` contains a `server.detected_provider` in
[aws, gcp, azure, scaleway, ovh]: ask for the instance.

```
Question : "Which {provider} instance size should be assumed?"
Header   : "Instance"
AWS options:
  - t3.medium    (default, small prod hypothesis) - Recommended
  - t3.large
  - m5.large
  - m5.xlarge
```

Adapt the list to the detected provider. If the provider is unknown or unsupported:
`run_efootprint.py` automatically falls back to a generic `Server`
(no question to ask).

### Third-party generative AI (only if a detected host is not yet resolved)

`env-data.json::ai_external_apis` contains a host with `"resolved": false`
when Step 25 identified a call to a third-party **text** generative AI
without the user having specified the exact model yet. As long as a host
remains unresolved (or the model is "unknown"), its call is NOT counted
in the total CO2e — status quo, never an invented value. These two questions
let us include it. Unlike traffic/instance, the answer is
**persisted in env-data.json** (never asked again, except with `--refresh`).

Ask one question per unresolved host, in detection order.

**Question 1 — exact model**:
```
Question : "This site seems to call {provider} (host {host}). Which model
            does it probably use?"
Header   : "Model {provider}"
Options  : 3-4 common models from the EcoLogits catalog for THIS provider
           (e.g. for Anthropic: Claude Sonnet 4.5, Claude Haiku 4.5,
           Claude Opus 4.1) + "I don't know"
```
- NEVER offer unverified free-form entry: EcoLogits rejects any model
  name absent from its catalog (error at construction rather than a
  guessed default). A model not listed -> steer to "I don't know".
- **Model chosen** -> move to Question 2.
- **"I don't know"** -> `collect_env_data.py <source_dir> --set-ai-model <host> unknown`
  (marks `resolved=true, model_name=null`: never asked again except with `--refresh`),
  inform that this host stays out of the calculation, move to the next host.

**Question 2 (if model known) — typical response length**:
```
Question : "On average, how long is a response from this model?"
Header   : "Response length"
Options  : Short (~50 words) / Average (~150 words) / Long (~400 words) /
           I don't know
```
- Convert the option to `output_tokens` (order of magnitude 1 word ≈ 1.3 tokens):
  50 -> 65, 150 -> 195, 400 -> 520.
- **Option chosen** -> `collect_env_data.py <source_dir> --set-ai-model <host> <model_name> --set-ai-output-tokens <host> <tokens>`.
- **"I don't know"** -> `collect_env_data.py <source_dir> --set-ai-model <host> <model_name>`
  ALONE (without `--set-ai-output-tokens`). **Multiple-choice decision of 2026-08-28, different
  from Question 1**: unlike the unknown model (exclusion, no reasonable default
  between providers), the call IS counted here, with a default "average response"
  assumption (~150 words, `_DEFAULT_OUTPUT_TOKENS` in
  `from_har.py`) — visible as such in the report's assumptions appendix,
  never a silent default. Always say it explicitly to the user
  ("I count this call with an average-length assumption, for lack of
  precision").

**The annual number of calls is NOT asked**: it is derived automatically
from the number of requests to this host observed in the captured HAR (cf.
`from_har.py::_ai_job_specs_for_step()`), never from an extra question.

### Other parameters

The other parameters (request duration, page weight, device mix, country)
are **imposed by `env-data.json`**. Do not ask for them -- if the user
wants to change them, they edit `env-data.json` then re-run.

**Device mix (mobile/desktop).** Collected via CrUX (`form_factors`), then:
- **tablet is attached to mobile**;
- **symmetric CrUX correction** (CrUX = Chrome only): mobile is inflated by the
  absence of iOS (`mobile / (1 − part_iOS)`) AND desktop by the absence of macOS/Safari
  (`desktop / (1 − part_macOS)`), then the whole is renormalized. Correcting the
  desktop too removes the "pro-mobile" bias of the old unilateral correction;
- the iOS and macOS shares are **weighted by the audience country mix** (Step 20b).
  Advanced override of the iOS share only: `collect_env_data.py --ios-mobile-share 0.45`.

The mix **really** weights the CO2e: traffic is split into two usage profiles
(mobile → smartphone/mobile network, desktop → laptop/wifi). The raw CrUX mix,
the iOS/macOS shares, the country mix and its provenance, the scenario range and the
traffic split are traced in the report appendix.

-----

## Step 40 - e-footprint calculation

Run the script:

```bash
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py \
    <source_dir> \
    --visits <visits> \
    --instance <instance>
```

The script:
1. Displays the assumptions table (already handled, do not duplicate)
2. Builds the e-footprint model
3. Displays the CO2e results (manufacturing + energy)
4. Serializes to `<source_dir>/efootprint-boavizta-model.json` (native
   e-footprint model) and `<source_dir>/efootprint-python-summary.json`
   (summary consumed by the HTML report and the non-regression check)
5. Regenerates `<source_dir>/topology-<domain>.puml` (overwriting the one from
   Step 25) adding the CO2e share of each step, now known
   since the calculation ran (proportional distribution, cf.
   `build.py::step_impact_shares()`, not an independent measurement per step)

**After Step 40, if an SVG diagram must accompany the final report**,
recompile this regenerated `.puml` (`plantuml -tsvg <path printed by the
script>`, then rename to `topology-<domain>.svg` as at Step 25c):
this version, with the impact share, is the one that must be used in
the final HTML report, not the Step 25 one (pre-calculation overview).

Capture stdout to send it back to the user as a block, then synthesize.

-----

## Step 50 - Synthesis and iteration

After the raw display, produce a 3-line synthesis:

```
CO2e estimate (hypothesis {visits} visits/year, {instance}):
- ~{total_kg} kg CO2e/year
- ~{per_visit_g} g CO2e/visit
- Dominant item: {devices|server|network|storage}
```

Then offer via AskUserQuestion:
- **Re-run with other assumptions** (new traffic or new instance)
- **Re-collect the data** (`--refresh` on `collect_env_data.py`)
- **Regenerate the HTML report** (see section "HTML report integration" below)
- **Finish**

Do not launch an automatic iteration: this is a human-in-the-loop loop.

-----

## Degraded mode (without HAR)

If `source_dir` contains no HAR but the user still wants
an estimate:

1. Explicitly report the fields that will be defaulted:
   - Page weight: 500 kB (library default)
   - Request duration: 1000 ms (library default)
   - Provider: unknown -> generic Server
   - Device mix: 60/40 phone/desktop (default)
2. Ask for confirmation before launching
3. Do not claim precision: the result is a very rough order of magnitude

-----

## Recap: equivalent CLI commands

For the user who prefers to run the scripts directly:

```bash
# Collection (once, then manual --refresh)
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir>
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --refresh
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --check
# Audience country mix (weights the iOS/macOS shares of the CrUX correction):
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --audience "FR:0.7,US:0.3"
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --audience FR
# Advanced override of the iOS share only (debug):
python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --ios-mobile-share 0.45

# Calculation (re-runnable at will)
# Without --visits: reads the 'traffic' block (SimilarWeb) from env-data.json, else baseline 100k/year.
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py <source_dir>
# With --visits: forces the traffic (client analytics), takes precedence over the 'traffic' block.
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py <source_dir> --visits 500000 --instance t3.large
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py <source_dir> --refresh-data
```

-----

## Produced files

In `<source_dir>/`:
- `env-data.json` - Collected data (permanent cache, manual --refresh)
- `efootprint-boavizta-model.json` - Native e-footprint model (Boavizta),
  fully serialized (recreated at each run): reloadable into the real
  model_builder or via `json_to_system`, never read by this project
- `efootprint-python-summary.json` - Application summary specific to this project
  (CO2e totals + assumptions, lightweight format), consumed by
  `generate_report_html.py` and `check_efootprint_contract.py`

These files **must not be committed** to git.

-----

## HTML report integration

The `generate_report_html.py` generator automatically detects
`efootprint-python-summary.json` (in `audit_dir` or its parent) and inserts a
section "Environmental impact (CO2e estimate)" into the report, between
"Core Web Vitals analysis" and "Appendices". If the file is absent, the section
is simply omitted (backward-compatible report).

Section content:
- KPI at the top: total kg CO2e/year, g CO2e/visit, manufacturing/energy split
- "Hypothetical estimate" warning banner
- Breakdown by item (Devices, Storage, Servers, Network, ...) with bars
- Table of input assumptions with confidence level
  (collected / estimated / assumed / library default)

A **methodological appendix** (section "Methodology & assumptions", in the Appendices)
also traces, per domain (A: CO2e, B: CWV, C: EcoIndex, D: traffic), all the data
and assumptions: raw CrUX mix, iOS AND macOS shares with their sources, audience country mix
and its provenance (SimilarWeb estimated / entered / FR default) with per-country detail,
tablet→mobile attachment, scenario range, mobile/desktop traffic split,
and for the CWVs the "worst of both" strategy per metric. Applied formulas included.

Regeneration after an assumptions change:
```bash
python3 .claude/skills/analyse-parcours/scripts/run_efootprint.py <source_dir> --visits N
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <source_dir>/audit
```

-----

## Key decisions (reference)

- e-footprint: Python library only (no REST API), CO2e output only
- Generic approach: not limited to octo.com, applicable to any website
- `env-data.json` cache: never expires automatically (manual --refresh)
- Annual traffic: resolved by priority `--visits` (analytics) > `traffic` block SimilarWeb
  (written by the agent, never scraped by the script) > baseline 100,000/year + warning
  (see Step 20c). Total CO2e grows with traffic; CO2e/visit depends little on it.
- Mandatory "hypothetical estimate" reminder on each parameter and on the results
- IPINFO_TOKEN not provisioned: anonymous mode accepted (50k req/month)
