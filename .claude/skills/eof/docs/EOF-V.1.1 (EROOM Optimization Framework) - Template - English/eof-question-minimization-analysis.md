# Analysis — Minimize human questions to maximize EOF answers

> **v2 (2026-09-03, second pass)**. The v1 (same file, cf. git) only sought
> to group questions together. This v2 adds two things the v1 had
> not done: (a) measure coverage in **score weight** and not in number of criteria,
> (b) look for **new data sources** able to answer criteria currently
> classified "no data".
>
> Intermediate analysis file: not consumed by any code.
>
> Method of this v2: real probes run on `octo.com` on
> 2026-09-03 (DNS, HTTP, headers, CSS, JS, third-party APIs). Each lead is
> labeled **verified for real**, **not verified**, or **discarded after testing**.
> No lead is presented as acquired without a test.

-----
-----

## 1. The real problem is not the number of criteria, it is the weight

The framework weights each criterion (`weight`: 1.0 Moderate, 1.5 Significant,
2.0 Decisive). **Total weight of the 54 detailed criteria: 80.0.**

| | Criteria | Weight | % of score |
|---|---|---|---|
| Answered automatically (today) | 7 | 9.0 | **11.3 %** |
| of which really decided (excluding 1.6 = "🤔 To be assessed") | 6 | 8.0 | **10.0 %** |
| "Partial" clues (never checked) | 11 | 16.5 | 20.6 % |
| No data | 36 | 54.5 | 68.1 % |

**Central finding**: the 8 **Decisive** criteria (weight 2.0, i.e. 16.0 =
**20 % of the score by themselves**) are **all 8 unanswered**: `1.1`, `1.2`,
`2.2`, `5.8`, `5.9`, `6.1`, `6.4`, `6.6`.

Direct consequence for strategy: optimizing the number of questions asked
without looking at the weights misses the essentials. A question that unlocks
`6.4` + `6.6` + `6.1` (3 Decisives, 6.0 of weight) is worth more than six
questions on Moderate criteria (6.0 too, but six interactions).

**Metric to retain from now on: score weight covered per human
interaction.** That is the operational formulation of "minimum questions,
maximum answers".

-----

## 2. Weight covered per cluster (ranking of the questions to ask first)

The v1's clusters, quantified:

| Cluster | Criteria | Weight | Of which Decisive |
|---|---|---|---|
| **D — Engineering maturity** (6.1→6.9) | 9 | **14.0** | 6.1, 6.4, 6.6 (3) |
| **A — Infrastructure / FinOps** (3.1,3.2,3.5→3.9) | 7 | **10.5** | 0 |
| **G — UX design / compatibility** (1.2→1.6,1.10,1.11) | 7 | **9.5** | 1.2 (1) |
| **C — Technical debt / perf** (5.1,5.2,5.6→5.9) | 6 | **9.0** | 5.8, 5.9 (2) |
| **B — Storage and data** (4.2→4.6) | 5 | 6.5 | 0 |
| **E — Architecture** (2.2,2.3,2.4) | 3 | 5.0 | 2.2 (1) |
| **F — Product necessity** (1.1,1.7) | 2 | 3.5 | 1.1 (1) |

**4 composed questions (D + A + G + C) = 43.0 of weight = 54 % of the score**,
and 6 of the 8 Decisives. It is the best answers/questions ratio
available, and it is far above what any additional
automation can bring (cf. section 4: realistic ceiling ~+5 points).

-----

## 3. Strongest lever: ask for artifacts, not answers

The v1's angle was "group the questions". Missed angle: **the same
interaction can ask for a document rather than an answer**, and a document
is read without mobilizing the interlocutor's attention across 9 questions.

### 3.a Read access to the code repository = the biggest single gain

Read access (or even just a capture of the tree + a few
files) allows factual answers, without interpretation:

| Criterion | Weight | What is read in the repository |
|---|---|---|
| `6.3` CI/CD | 1.5 | `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile` |
| **`6.4` non-regression tests** | **2.0** | test directories, Jest/Pytest/Playwright config |
| **`6.6` quality indicators** | **2.0** | `sonar-project.properties`, lint config, CI badges |
| **`6.1` observability** | **2.0** | OpenTelemetry / Datadog / Sentry dependencies |
| `6.2` code reviews | 1.5 | `CODEOWNERS`, PR template, branch rules |
| `6.7` documentation | 1.5 | `README`, `docs/`, ADR |
| `6.8` duplicated code | 1.0 | measurable (`jscpd`) on the repository |
| `6.9` tooling autonamey | 1.0 | diversity of tools already integrated by the team |
| **`5.8` dependencies up to date** | **2.0** | lockfile + Dependabot/Renovate, versions vs latest |
| `5.6` tech stack up to date | 1.5 | `engines`, `.python-version`, `pom.xml` |
| `5.1` static analysis | 1.0 | linter / analyzer config |
| `6.5` business/technical decoupling | 1.5 | folder structure (hexagonal, DDD) |

**12 criteria, 18.5 of weight (23 % of the score), 5 of the 8 Decisives, for
ONE single request.** Compare with the 9.0 produced by the whole current
automatic pipeline. This is the path to prioritize before any new
technical automation.

Honest limit: `6.8` and `5.8` require running a tool on the
repository (not just reading it); and an accessible repository says nothing about the
**quality** of the tests, only their existence. `6.4` can therefore go
from "no data" to a plausible level, not to a certainty.

### 3.b Two other artifacts, same logic

- **Detailed cloud bill or IaC export (Terraform/CloudFormation)** →
  cluster A almost entirely (`3.1`, `3.5`, `3.6`, `3.7`, `3.8`, `3.9`) + `4.3`,
  `4.4`. About 13.5 of weight for one request. The IaC gives the real
  sizing, which corrects the known black spot (`instance_type`
  / `storage_gb` of e-footprint are only script defaults).
- **Backlog export filtered on "perf"** → `5.3` + `0.13`, and confirms
  `5.2`. Low weight (3.0) but almost zero cost if the tool is accessible.

-----

## 4. New automatic sources: what the 2026-09-03 probes yield

### 4.a VERIFIED FOR REAL — non-production environments exposed (`3.8`, `3.9`)

```
dig +short staging.octo.com  ->  d3cowsu17vt1rf.cloudfront.net / 3.164.163.68
curl -sI https://staging.octo.com/  ->  HTTP/2 200, 27947 bytes,
                                         last-modified Tue 01 Sep 2026 01:00:41
prod https://octo.com/       ->  HTTP/2 200, 27748 bytes,
                                         last-modified Thu 03 Sep 2026 01:01:31
```

ETag and last-modified **different** from prod's: it is not a
wildcard alias, it is really a distinct environment, served publicly, with
content almost identical in volume to prod's.

- `3.8` "Are all environments always switched on?" →
  **automatable** (💡 Improvement potential: a non-production env
  answers permanently).
- `3.9` "Are test environments as big as prod's?" →
  **clue** (comparable content volume, but HTML volume says nothing
  about the sizing of the infra behind it).

Gain: +1.5 decided, +1.5 as clue.

⚠️ **Methodological pitfall discovered along the way, to handle before implementing**:
octo.com returns **HTTP 200 + the home page** for any
nonexistent URL (`/package.json`, `/scripts/home.js.map` → 200, 27748 bytes, the
homepage). Any probe that concludes "the file exists" from the
HTTP code will produce **false positives**. Validation must be by content signature
(size + `content-type` + body fingerprint), never by status alone.

⚠️ **Posture decision needed**: probing a client's subdomains
is light reconnaissance. To be framed explicitly (fixed and
short list, DNS + HEAD only, no authentication attempt, never sensitive
paths like `/.git` or `/.env`) and validated before being
put in the default pipeline.

### 4.b VERIFIED FOR REAL — the CSP header is a declared inventory of third parties

Prod's CSP (**already collected** by `analyze_security_headers.py`, but
only its `grade` is used today) lists ~30 allowed domains:

```
*.herokuapp.com  *.hsforms.net  *.hsforms.com  *.hs-scripts.com
*.hs-analytics.net  *.hubspot.com  *.hs-banner.com  *.hsadspixel.net
*.hubapi.com  *.licdn.com  *.linkedin.com  cdnjs.cloudflare.com
swetrix.org  cdn.jsdelivr.net  challenges.cloudflare.com  ...
```

It is **broader than what the HAR captures** (the HAR only sees the third parties
solicited on the captured journey; the CSP declares everything planned).
Cost: **zero additional network calls**. Best gain/effort ratio of
this whole analysis.

Possible uses:
- `2.3` separation/communication of components → `*.herokuapp.com` reveals
  an application platform distinct from the static site → **clue**.
- `3.5` sharing → PaaS (Heroku) + shared CDN → **clue**.
- `3.7` elasticity → Heroku dynos / CloudFront are elastic by nature →
  **clue** (never proof that elasticity is configured).
- `1.12` trackers → **fixes a substantive error**, cf. 5.a.

### 4.c VERIFIED FOR REAL — deployment freshness (`6.3`)

The current `6.3` clue relies on `sitemap.days_since_lastmod`. Yet **octo.com
has no `sitemap.xml`** (verified: 0 `<loc>` tags, `wellknown-scan.json`
contains only `domain` and `note`). The clue is therefore **empty in practice**.

Verified substitute, much more reliable: the cache-busting parameter
`/style.css?v=2026-8-3-1-1`. Decoded with a 0-indexed month (behavior of
`Date.getMonth()` in JS): 2026, month 8 = September, day 3, 01:01. Which
corresponds **exactly** to prod's `last-modified` (Thu 03 Sep 2026
01:01:31 GMT). In other words: automated build, dated the same day, launched around
01:00 → **strong clue of a nightly automated pipeline**, where the sitemap
gave nothing.

Generalizable: cross-check `last-modified` / `ETag` / `?v=` parameters of
assets. Two spaced audits would additionally give a **deployment cadence**.

### 4.d NOT VERIFIED — Lighthouse `legacy-javascript` for `1.3` / `1.8` / `5.9`

`run_lighthouse.sh` already exists. Lighthouse exposes a
`legacy-javascript` audit (polyfills and transpilation targeting old
browsers) and `third-party-summary`. It is the most direct available
proxy for "poor support on old devices" (`1.8`, 1.5) and
"compatibility issues identified" (`5.9`, **2.0 Decisive**) — the v1
had rightly discarded CrUX for this use, but had not examined
Lighthouse.

**I did not run Lighthouse to confirm.** To be tested before counting on it:
potential gain up to 5.0 of weight, real gain unknown.

### 4.e DISCARDED AFTER TESTING — dependency versions by external probing (`5.6`, `5.8`)

Tested on octo.com, all negative: no `<meta name="generator">`, no
`sourceMappingURL` in the HTML nor in `/scripts/home.js` (3771 bytes),
`/scripts/home.js.map` and `/package.json` nonexistent (the observed 200s are
the soft-404 described in 4.a).

The v1's conclusion ("no detectable version") is therefore **confirmed for
this site**. To be nuanced though: on a WordPress/Drupal site (`meta
generator` versioned) or one shipping its source maps, detection would work. To
keep as an **opportunistic probe** (almost zero cost, zero gain here, real gain
elsewhere), never as a source to count on. `5.8` (2.0
Decisive) remains to be covered by the repository (3.a).

### 4.f Marginal — Green Web Foundation

`api.thegreenwebfoundation.org/api/v3/greencheck/octo.com` → `green: false`
(verified). The framework has **no** "renewable hosting" criterion
(the numbering jumps from `3.3` to `3.5`, cf. section 6). Usable only
to corroborate `3.3`, already answered. Gain: 0. Mentioned to close the lead.

-----

## 5. Quality corrections found along the way (independent of the counting)

### 5.a `1.12` currently penalizes frugality — to be corrected

`env-data.json` detects `Analytics: ["Swetrix"]`, and the current rule
("at least one Analytics detected → 💡") therefore classified octo.com as improvement
potential. Yet **Swetrix is precisely the frugal option** (no cookie,
no profiling). And at the same time the real marketing tracking stack
is **invisible** to the rule: the HTML loads `hs-scripts` (HubSpot) and the
CSP allows `hs-analytics`, `hsadspixel`, `licdn`, `linkedin`.

The "💡" answer is right only by accident, with a false reason. Correction:
classify trackers by nature (frugal/self-hosted audience measurement
on one side, marketing-CRM-ad pixels on the other) and base the
answer on the second category. Additional source: the CSP (4.b) + the
HTML already re-fetched.

### 5.b Latent bug in `parse_html_criteria.py`: unquoted attributes — ✅ FIXED on 2026-09-07

⚠️ **This section describes an outdated state, kept for its finding
on octo.com, which remains true and was used to measure the impact.** The
defect is fixed: `parse_html_criteria.py` no longer reads HTML with regular
expressions but with `html.parser` (standard library). Attribute order,
quotes, case, entities and chevrons in an attribute value have
ceased to be a subject. The fix ships with its test:
`python3 parse_html_criteria.py --autotest`, 32 cases, including 13 HTML writings
that the old version read wrongly in silence.

**The fix goes beyond the scope described below**: the defect did
not touch 2 expressions but 4, and the most serious was not this one.
`_AUTOPLAY_RE` took `<video class="no-autoplay">` and
`<video data-autoplay="false">` for autoplay videos, which
fed criterion `1.5` with provenance **`collected`**, so presented to the
reader as a measurement. Verified on the data already on disk:
`has_autoplay_media` is `False` on octo.com's 6 pages, so this false positive
did **not** trigger here.

**The original text follows. Its last sentence, "to be corrected (make the
closing quote optional)", is outdated**: patching the expression would
have left attribute order and the three other writing forms passing.

-----


octo.com serves minified HTML with unquoted attributes
(`<script src=/scripts/home.js defer>`, `<link rel=stylesheet
href=/assets/orejime.css>`). Yet the script's regexes require quotes:

```python
_STYLESHEET_LINK_RE = ... rel=["']?stylesheet["']?[^>]*\bhref=["']([^"']+)["']
_DIV_ROLE_BUTTON_RE = re.compile(r"role=[\"']button[\"']", re.IGNORECASE)
```

Unquoted `href=` and `role=` do not match. Consequence: stylesheets
ignored (→ `media_query_count`, `has_prefers_reduced_or_scheme`
underestimated, criteria `1.6` and `1.11`) and unquoted `role=button`
buttons not counted (`1.4`).

**Real impact on octo.com: none, verified.** The only ignored
CSS (`/assets/orejime.css`, 5654 bytes) contains neither `@media` nor `prefers-*`,
and the main CSS (172 796 bytes, well read) has no `prefers-*` either:
`has_prefers_reduced_or_scheme: false` is a correct result. The bug
is therefore **latent**, not active here — but it will produce a silent
false negative on the first minified site that declares `prefers-reduced-motion`
in a CSS with unquoted `href`. To be corrected (make the closing quote
optional), without urgency.

-----

## 6. Point to raise on the framework itself

The criteria numbering **skips `3.4`** (`3.1`, `3.2`, `3.3`, then
`3.5`...). The total is indeed 54 (16+5+8+6+9+10), so nothing is "lost"
compared to the expected count, but a numbering gap can signal either a
criterion removed on the Google Sheet side, or a row skipped at export. To be checked
at the next synchronization of the `eof` skill: if a "3.4" criterion
exists in the Sheet, the export silently loses one.

-----

## 7. Quantified summary of this v2

Weight coverage (base 80.0):

| Scenario | Decided weight | % | Human interactions |
|---|---|---|---|
| Today | 9.0 | 11 % | 0 |
| + verified probes (4.a, 4.b, 4.c) | 10.5 decided + ~7.5 of clues | 13 % decided | 0 |
| + Lighthouse **if confirmed** (4.d) | ~13 | ~16 % | 0 |
| **+ repository access (3.a)** | **~31.5** | **~39 %** | **1 request** |
| + IaC / cloud bill (3.b) | ~45 | ~56 % | 2 requests |
| + 4 composed questions D/A/G/C | ~65 | ~81 % | 6 |

Reading: **the ceiling of pure automation is around 16 % of the weight.**
Everything else goes through a human or artifacts. Two artifact
requests are worth more (56 %) than six cold questions, and cost
less attention to the interlocutor.

Revision of the v1's figure: "23 interactions" remains valid as an upper
bound if we want all 70 criteria. But if the goal is
"maximum answers for a minimum of questions", the right target is
**2 artifacts + 4 composed questions ≈ 6 interactions for ~81 % of the weight**,
instead of 23 for 100 %.

-----

## 8. What remains to be decided (nothing is implemented)

In decreasing order of gain per unit of effort:

1. **Exploit the CSP already collected** (4.b) — zero network calls, +3 clues
   and corrects `1.12`. No posture risk. To be done first.
2. **Substitute asset freshness for the sitemap for `6.3`** (4.c) — the current
   clue is empty on octo.com, this one is verified.
3. **Correct `1.12`** (5.a) — corrects a false reason, not a count.
4. **Formalize the artifact request** (3.a/3.b): it is the real lever
   (+28 points of weight), but it is a change of nature of the pipeline
   (it becomes collaborative, not only observational). To be validated.
5. **Test Lighthouse `legacy-javascript`** (4.d) before counting on it.
6. **Subdomain probing** (4.a) — net and verified gain, but requires an
   explicit posture decision + content-signature validation
   to avoid the soft-404's false positives.
7. **Fix the unquoted regexes** (5.b) — latent bug, zero impact
   today, to be done when the file is touched.
8. **Check `3.4`** at the next sync (section 6).
