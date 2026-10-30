-----
Technology detection (technical stack) with home-grown rules
-----

This document explains WHY and HOW the EROOM agent detects the technical stack
of a site (CDN, web server, language, framework, CMS, analytics, fonts) without
using Wappalyzer or any external API. It also serves as a maintenance guide
for adding or correcting a detection rule.

The module concerned is `.claude/skills/analyse-parcours/scripts/detect_tech.py`.
It can be rerun standalone and is integrated into the collection (`collect_env_data.py`)
and the report (`generate_report_html.py`).


-----
1. The licensing reasoning (why NOT Wappalyzer)
-----

"Reference" technology detection relies on the open source project
**webappanalyzer** (community fork of Wappalyzer, ~2500 technologies),
distributed under the **GPL v3** license.

The EROOM toolbox is meant to be published under **CC BY-SA 4.0**. These two
licenses are **incompatible in this direction**:

- CC BY-SA 4.0 -> GPL v3: possible (a one-way compatibility clause exists on
  the Creative Commons side).
- GPL v3 -> CC BY-SA 4.0: **impossible**. Embedding webappanalyzer's GPL data
  into our repository would contaminate the whole and forbid publication under
  CC BY-SA.

Conclusion: we do **NOT** embed webappanalyzer. We write our own detection
rules, 100% original, therefore 100% CC BY-SA-compatible, offline, with no
dependency and no network call.

Side note (to keep in mind for the toolbox as a whole): CC BY-SA 4.0 is a
license designed for **works and data**, not ideal for **executable code**.
Creative Commons explicitly discourages it for software. The license choice
for the toolbox as a whole would deserve to be reconsidered (e.g. a software
license like MIT/GPL for the code, CC BY-SA for the documentation and data),
but that is beyond the scope of this module.


-----
2. The finding that makes home-grown rules sufficient
-----

Wappalyzer does nothing magical: it is **pattern matching** on signals already
present in a network capture. The EROOM agent already collects a complete
**HAR** (`<site>/<site>.har`) that contains all the raw material:

- the **response headers** of each request (`server`, `via`, `x-powered-by`,
  `cf-ray`, `x-amz-cf-id`, `x-served-by`, `set-cookie`…) ;
- the **URLs** of all requests (scripts, fonts, analytics, third-party CDNs) ;
- the **HTML** of the pages (`<meta name="generator">` tag, framework patterns) ;
- the **cookies** set (`Set-Cookie`).

No API, no extension, no driven browser needed: we re-read the HAR and apply
our rules.


-----
3. What can / cannot be retrieved
-----

RETRIEVABLE (the core of the stack, sufficient for CO2e and the report):

- CDN (CloudFront, Cloudflare, Fastly, jsDelivr…) via headers and hosts.
- Cloud host (S3, Vercel, Netlify, GitHub Pages…) via headers; cross-checked
  with ipinfo to make the provider more reliable (see section 5).
- Web server (nginx, Apache, IIS, LiteSpeed…) via `server`.
- Announced server language (PHP, ASP.NET, Node/Express…) via `x-powered-by` / cookies.
- Front / SSR frameworks (Next.js, Nuxt, Gatsby, Astro, React, Vue) via HTML / URLs.
- CMS (WordPress, Drupal, Joomla, Webflow, Shopify) via `<meta generator>` / URLs.
- Analytics and tag managers (GA4, Matomo, Swetrix, Plausible, Hotjar, GTM).
- Fonts (Google Fonts, Font Awesome) and consent banners (Orejime, Axeptio…).

NOT RETRIEVABLE from the outside:

- **Server instance type** (t3.medium, e2-standard…) : totally invisible
  client-side. Remains a **question to ask the user** (it influences the
  e-footprint calculation via the Boavizta instance choice in `run_efootprint.py`).
- Hidden backend: database, unannounced server language, server framework
  without a distinctive header.
- Masked signals: some sites empty or falsify their headers (on
  octo.com, `server:` sometimes returns `-`). Detection is then partial.
- Anything that does not show up in a standard network capture (purely
  server-side logic, feature flags, etc.).

What webappanalyzer would add if it were ever plugged in (see section 6):
precise lib versions, marketing pixels, A/B testing tools, micro JS libraries.
**Useless for CO2e** (weight and requests are already measured in the HAR),
and above all optional for the targeted documentary report.


-----
4. Rule format and engine behavior
-----

Rules live in the `TECH_RULES` dict of `detect_tech.py`. Each entry:

    "Technology name": {
        "cat": "CDN",                       # category (cf. CATEGORY_ORDER)
        "confidence": "high",               # base confidence if strong signal
        "headers": {"via": r"cloudfront"},  # regex on a header value
        "url": r"cdn\.jsdelivr\.net",       # regex on request URLs
        "meta_generator": r"WordPress",     # regex on <meta name=generator>
        "html": r"id=[\"']__NEXT_DATA__",   # regex on the HTML (weak hint)
        "cookie": r"^PHPSESSID=",           # regex on a cookie name
    }

Confidence hierarchy applied by the engine (`_match_rule`):

- A match on `headers`, `meta_generator` or `cookie` is a **strong signal**:
  it takes the rule's base `confidence` (often `high`).
- A match on `url` is **capped at `medium`** (a third-party host can be shared).
- A match on `html` is **capped at `low`** (substring, false positives
  possible; e.g. the word "vue" appears in text without Vue.js being used).

The confidence kept for a technology is the **strongest** of the matching signals.

The result (`detect()`) is a dict:

    {
      "technologies": [{"name", "category", "confidence", "evidence"}, ...],
      "categories": {cat: [names]},
      "third_party_hosts": [...],   # hosts distinct from the main domain
      "request_count": int
    }

It is written as-is into `env-data.json` under the `tech_stack` key. The code
sets `schema_version` to the exact value `"1.3"` (the `tech_stack` block appeared
at this schema version).


-----
5. Cross-check with ipinfo (CO2e provider reliability)
-----

In `build_env_data()` (`collect_env_data.py`), a cross-check happens AFTER ipinfo:

- If ipinfo concluded a provider (e.g. `aws`), it is authoritative: the detected
  CDN does not override it.
- If ipinfo concluded **nothing** but a CDN / cloud host is detected, we add
  `provider_from_tech` to the `server` block and raise `confidence_provider`
  from `low`/`default` to `medium`.

Downstream effect: the provider influences the Boavizta instance choice in
`run_efootprint.py`, hence the manufacturing CO2e.


-----
6. Options not chosen, but still possible (for a future maintainer)
-----

If the need for detail is ever confirmed, several paths exist. Ranked from most
to least recommended:

a) **On-the-fly download (opt-in) — the natural evolution.**
   Fetch the ~2500 webappanalyzer rules **at runtime, on the user's side**,
   on explicit activation (flag). The GPL data is **never committed** to the
   repository: it is downloaded and cached locally. The toolbox stays CC BY-SA
   (it does not distribute GPL).
   Cost: re-implement the full Wappalyzer matching engine (headers, cookies,
   js, dom, meta, scriptSrc, html, plus the `implies` / `excludes` relations and
   version extraction), plus download + cache + fallback if unavailable.
   This is the option to prefer if we ever want full coverage.

b) **Git submodule.**
   Point a pinned submodule at the GPL repository, separate from our code. The
   legal argument ("mere aggregation") is **fragile** as soon as our code
   functionally depends on the data: the contamination risk reappears. Not
   recommended.

c) **Publish the whole agent under GPL v3.**
   Technically the simplest, but **rejected**: incompatible with the CC BY-SA
   target of the toolbox.


-----
7. Rule maintenance
-----

To add or correct a rule:

1. Open `detect_tech.py`, edit the `TECH_RULES` dict.
2. Choose the right signal type (prefer `headers` / `cookie` / `meta_generator`,
   more reliable than `url`, itself more reliable than `html`).
3. Write a targeted regex. Beware of anchors: for a host, do NOT use
   `(^|\.)` (URLs start with `https://`) ; use a pattern like
   `cdn\.jsdelivr\.net` or `(//|\.)mondomaine\.com`.
4. Adjust the base `confidence` (`high` only if the signal is distinctive
   and not shared).

Test on the control site (octo.com):

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/detect_tech.py audits/octo.com

Beware: the argument is a **local folder** (the audit case), not a domain fetched
over the network. Audit cases live under `audits/<site>/`. The HAR is looked for
flat in this folder, then, as a fallback, in the `raw-data-potentially-sensitive/`
subfolder (see the convention at the end of the section). The module is 100%
offline: it re-reads the already captured HAR, it makes no network call. The
command must therefore be run from the project root.

Expected detection on octo.com (non-regression reference): Amazon CloudFront,
Cloudflare, Fastly, jsDelivr (CDN) ; Google Frontend (server) ; Swetrix
(analytics) ; Google Fonts (fonts) ; Orejime (consent). The word "vue" present
in the HTML must NOT trigger a Vue.js false positive (`html` rule capped
at `low` and pattern requiring `data-v-xxxxxxxx` / `__VUE__`, not the bare substring).

Then check the full integration:

    .venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py \
        audits/octo.com --refresh                      # tech_stack block, schema 1.3
    # then regenerate the HTML report -> "Technical stack" section in the appendix

Storage of raw captures: each script looks for the HAR and the `Coverage-*.json`
**flat in the audit case first**, then in the `raw-data-potentially-sensitive/`
subfolder as a fallback. This subfolder is in `.gitignore` (an authenticated
journey HAR can contain credentials or personal data). Both storages work: an
audit whose files stayed flat keeps working.

If the on-the-fly enrichment is ever activated (section 6a), follow the upstream
webappanalyzer format and DO NOT commit its data into the repository.
