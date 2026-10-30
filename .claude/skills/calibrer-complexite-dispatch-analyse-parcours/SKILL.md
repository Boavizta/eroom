---
name: calibrer-complexite-dispatch-analyse-parcours
description: >
  Maintains the level grid (econamey/standard/advanced model, low/medium/high
  effort) used by the analyse-parcours skill orchestrator to resolve, at each
  dispatch, the COMPLEXITE (A/B/C/D) field of each :::dispatch block into
  concrete model/effort — without ever naming a model in the skill itself.
  To invoke occasionally to refine this grid (thresholds, justifications, new
  cases encountered), never to pick a model name.
triggers:
  - "refine the dispatch complexity grid of analyse-parcours"
  - "review the complexity tiers of dispatch blocks"
  - "/calibrer-complexite-dispatch-analyse-parcours"
version: 1.0.0
---

# Skill: sub-agent complexity grid — analyse-parcours dispatch

## Why this skill exists

The `analyse-parcours` skill dispatches 7 `:::dispatch` blocks per analysis (Wave 1:
`analyze-har`, `analyze-coverage`, `collect-cwv`, `collect-env-data`,
`extractor-security-headers` ; Wave 2: `extractor-html-css`,
`extractor-wellknown` — see
`analyse-parcours/skill-steps/25_dispatch-orchestration.md`). Each block
carries a `COMPLEXITE:` field (A/B/C/D) — an abstract tier, with no model
name.

**The orchestrating agent resolves this tier itself into concrete model/effort,
at dispatch time, with its own knowledge of the current execution environment**
(which models are available in this harness, which is the most econameical, which
is the most capable). This skill therefore never provides a "tier → model name"
table: such a table would go stale at every model release and would break the
sought agnosticism (the `analyse-parcours` skill must remain usable under any
LLM harness/provider, not only Claude Code).

What this skill provides is **the level grid and its concrete justification**:
for each tier, what abstract level of model and effort is needed, and above all
*why* — so that the orchestrator has a solid basis for judgment rather than
guessing (and therefore, out of caution, systematically picking the most capable
model at high effort — exactly the waste this logic aims to avoid).

Unlike the RGAA audit (where each block carries an expert judgment on an
accessibility criterion), the 7 `analyse-parcours` blocks are all
**deterministic Python script wrappers**: the variable that changes from one
block to another is not the depth of business judgment to carry, but the
quantity of sources to cross and the presence (or not) of a fallback or
vigilance logic to interpret around the script.

## What must NEVER appear here nor in `25_dispatch-orchestration.md`

- A model name (sonnet, haiku, opus, gpt-*, gemini-*, etc.) tied to the
  dispatch of the 7 blocks above. *(Note: step 45 — `collect-env-data` /
  e-footprint — elsewhere references third-party AI model names, ex.
  `claude-sonnet-4-5`, via `collect_env_data.py --set-ai-model`, to estimate
  the carbon footprint of a detected generative-AI usage on the audited site.
  That is a homonymous subject unrelated to sub-agent dispatch — out of scope
  of this skill, do not touch it.)*
- An effort value specific to a provider (ex. the enums of a given harness).
  We only speak in abstract levels: econamey/standard/advanced for the model,
  low/medium/high for the effort.

## What must NEVER be recalculated here

The following signals, already documented in the text of each `:::dispatch`
block of `25_dispatch-orchestration.md`, are stable facts of the
`analyse-parcours` pipeline. Do not reinterpret them at each dispatch — they do
not depend on any model:

- **Number of external sources crossed by the script** to produce a single
  consolidated JSON (ex. `collect-env-data` = 4: HAR + CrUX + ipinfo +
  SimilarWeb).
- **Presence of a switch to an alternative tool/method**, documented
  explicitly in the block text (ex. `collect-cwv`: PageSpeed →
  Lighthouse if quota exceeded). **Not to be confused** with a simple
  degradation of scope or field confidence (ex.
  `extractor-security-headers` which analyzes all HAR pages instead of a
  filtered list if `env-data.json` is absent; `collect-env-data` which
  marks fields `confidence: default` in case of network error/missing API
  key): these degradations change the *scope* or the *precision* of the
  result, not the *calculation method* — they do not count as a tier signal.
- **Presence of a validation vigilance beyond simple wrapping**, documented in
  the block text or in the JSON output format (ex.
  `no_js_no_css` in `coverage-analysis.json`, `uncached_requests`/
  `duplicate_urls`/blocking resources in `har-analysis.json`, or — special
  case — the handling of a potentially failing live network re-fetch for
  `extractor-html-css`, which does not just parse a file already on disk).
- The **hard vs soft dependency** between blocks (`depends_on`/sequencing wave
  vs documented degradation in case of unguaranteed order): it is a DISPATCH
  sequencing signal, not a complexity-tier signal in itself.

If one of these facts changes (ex. a script is rewritten to add a real method
switch it did not have), that is an evolution of the `analyse-parcours` skill
itself, not of this skill — update the text of the block concerned directly in
`25_dispatch-orchestration.md` on that occasion, then check that the block's
`COMPLEXITE` is still consistent with the formula below.

## Formula: signals → tier

- **Starting tier: A** (simple script wrapper, none of the conditions below).
- Then, keeping the highest tier triggered:
  - **≥ 3 external sources to cross** → at least **C**.
  - **Switch to an alternative method** documented explicitly
    (tool fallback, not a simple scope/confidence degradation) →
    **+1 tier**.
  - **Validation vigilance beyond simple wrapping** (anamealy detected and
    signaled, or handling of a failing live network re-fetch on already
    audited data) → **+1 tier**.
  - Ceiling: **D**.

**Tier D** is reached by none of the current 7 blocks: it is reserved for a
future block that would cumulate at least two of these signals at once (ex. ≥3
external sources to cross *and* an explicit method switch). Never raise a block
to D "out of caution" without at least two signals of the formula being
effectively cumulated — a simple API call, for example, is not in itself a
reason for tier D.

The processed volume (number of pages, `.har` size) does **not** enter this
calculation: it increases the token cost whatever the model, but not the
orchestration difficulty of the script — it is not a complexity signal, it is a
volume signal.

## Level grid (what the orchestrator consults at each dispatch)

| Tier | Model level | Effort level | Concrete justification |
|---|---|---|---|
| **A** | Econamey (fastest/lightest available) | Low | Strictly mechanical Python script wrapper: a single subprocess call, reading the already-structured JSON produced by the script, no method switch nor anamealy to interpret — relaying a deterministic result. (`extractor-wellknown`, `extractor-security-headers`) |
| **B** | Standard | Low | Script wrapper with a single additional point of attention: either an explicit documented method switch (ex. `collect-cwv`: PageSpeed → Lighthouse), or a simple validation vigilance beyond wrapping (reading an anamealy key in the produced JSON — `no_js_no_css`, blocking/duplicate/uncached resources — and signaling it in natural language), or handling the failure of a live network re-fetch on already-audited pages (`extractor-html-css`). One signal at a time, not a crossing of sources. (`analyze-har`, `analyze-coverage`, `collect-cwv`, `extractor-html-css`) |
| **C** | Standard | Medium | Script that crosses at least 3 external sources (APIs/files) to produce a single consolidated JSON (ex. `collect-env-data`: HAR + CrUX + ipinfo + SimilarWeb): more surface to check (consistency between sources, absence of a source) than a simple wrapper, but without method switch nor extra anamealy to arbitrate beyond the source crossing. (`collect-env-data`) |
| **D** | Advanced (most capable available) | High | Reserved for a future block that would cumulate at least two signals of the formula at once (ex. ≥3 external sources to cross *and* an explicit method switch, or a complex validation vigilance on top of source crossing): a judgment error there would impact several enrichments at once. None of the current 7 blocks reaches this tier. |

**Usage by the orchestrator**: read the `COMPLEXITE` of the block to dispatch,
find the corresponding row, then choose — among the model/effort settings really
available in the current execution environment — those that best match the
indicated level. If the environment only offers two model levels (not three),
merge B and C onto the "standard" level rather than forcing an unjustified
"advanced" level.

## Refinement procedure (occasional invocation)

This skill is not invoked to pick a model, but to review the grid itself:

1. Read `analyse-parcours/skill-steps/25_dispatch-orchestration.md`,
   check for each `:::dispatch` block that `COMPLEXITE` is indeed
   consistent with the formula above applied to the signals documented in
   its text (number of external sources, explicit method switch,
   validation vigilance beyond wrapping). Fix `COMPLEXITE` if a
   discrepancy is found (and only this field).
2. If real analysis experience shows that a tier is miscalibrated
   (ex. a block classified B in practice needs level C), adjust the
   formula or the grid above — with the concrete example that justifies
   the change.
3. Show the diff to the user before writing anything: this
   file and `25_dispatch-orchestration.md` drive all future journey
   analyses.

Last review: 2026-10-15.
