"""Generic mapping table between the 54 detailed criteria of the
EOF framework (`eof-reference.json`, produced by the `eof` skill) and the
audit data already collected by `analyse-parcours`
(`env-data.json`, `audit/har-analysis.json`, `audit/coverage-analysis.json`,
`cwv.json`, `efootprint-python-summary.json`).

Built once, reusable for any audited site (same principle as
`run_efootprint.py`: generic, not limited to octo.com). The field paths
and value examples below were verified on `audits/octo.com/`
at the time of writing (2026-09-03); revalidate if the structure of these
files changes.

Initial scan (all 54 criteria reviewed one by one): 4 are automatable from
already-collected data, 6 give a weak/indirect hint (never a validation), and 44
are organizational or product questions that no technical audit data can answer.
This is not a flaw of this file: it is the nature of the EOF framework, largely
human by design.

Phase 1 extension (2026-09-03, cf. `eof-questionnaire` plan): +3
automatable (1.5, 1.6, 1.13, via `parse_html_criteria.py` and the
accessibility/best-practices extension of `collect_cwv_pagespeed.py`) and +5 hints
(1.4, 1.11, 6.1, 6.3, 6.6, via `parse_html_criteria.py`,
`analyze_security_headers.py`, `scan_wellknown.py`).

Phase 2 extension (2026-09-07): added 0.16 as automatable (unique
exception for the quick diagnostic, exact duplicate of 3.3).

Current MAPPING total: **24 entries, 8 automatable and 16 partial**.
⚠️ These two figures refer to the MAPPING, not to the 54 detailed criteria:
0.16 is a quick-diagnostic question, it is not part of the 54. The
two counts must never be mixed, on pain of producing a wrong total:
   - over the **54 detailed criteria**: 23 usable (7 automatable,
     16 partial), hence **31 with no data**. Unchanged by the addition of 0.16.
   - over the **16 quick-diagnostic questions**: 1 usable (0.16),
     hence 15 with no data.
Two workstreams foreseen by the
initial plan turned out to be unrealizable in practice and were
abandoned (never inventing a value instead):
- 1.1 (Lighthouse a11y/Best Practices) assumed data already collected
  in `audit/lighthouse-*.json` — nonexistent: neither `run_lighthouse.sh` nor
  `collect_cwv_pagespeed.py` requested these categories. Fixed by
  extending `collect_cwv_pagespeed.py` (same API call, additional categories,
  no extra network cost) rather than abandoned.
- 1.2/1.8 (CrUX network "effective_connection_type", "phone_lowend"):
  the CrUX API (`chromeuxreport.googleapis.com`) does NOT expose these
  dimensions (HTTP 400 "invalid metric" error tested under real conditions) — this
  is not a "low effort" job, the data simply does not exist
  via this API. 1.8 and 1.9 therefore remain "partial" as before Phase 1.
- 1.4/1.5 (HTML/CSS parsing) assumed reading the HTML/CSS bodies already
  present in the `.har` — verified: only 46/311 entries have a captured body
  (none of them page HTML/CSS). `parse_html_criteria.py`
  therefore re-fetches the same already-audited URLs directly over HTTP (not a
  new page scope, just a different content source).

Strict output policy, to never artificially fabricate a potential:
- "automatable" -> the rule can tick a specific option of the 5-option menu
  (`evaluation_options` of `eof-reference.json`). If the signal is ambiguous
  at runtime (e.g. value exactly at the threshold), fall back to
  "🤔 To be assessed", never guess.
- "partial"        -> NEVER auto-tick a box. The data is only a contextual hint
  displayed in the appendix ("indicative data: ...", provenance always
  "assumed" or "estimated", NEVER "collected"), the criterion stays
  "I don't know" in the filled-in framework. A hint presented as
  collected would suggest a measurement where there is only a weak signal.
- absent from MAPPING -> "no_data" by default: no field answers it, the
  criterion stays "I don't know", with no dedicated entry here (44
  criteria in this case — listing their ids one by one would add nothing).

This module contains ONLY the mapping table (data), not the rule execution
logic: that is planned in `run_eof.py`, not written yet (cf. architecture
plan, section "What is explicitly OUTSIDE this plan").
"""

MAPPING = {
    "0.16": {
        "short_criterion": "Is the service hosted in a country whose electricity mix has a significant impact? (depending on location)",
        "category": "automatable",
        "data_field": "env-data.json: servers[].carbon_intensity_g_kwh (exact duplicate of 3.3, same source data)",
        "rule": (
            "Same rule as 3.3: if at least one server in the list has carbon_intensity_g_kwh "
            "above the threshold (~250 gCO2/kWh, average European electricity mix) -> "
            "corresponding 1-5 scale level. If all are below -> low end of the scale."
        ),
        "max_provenance": "collected",
        "note": "Exact duplicate of criterion 3.3: same measured data (carbon intensity of the electricity mix of the hosting country), same source (env-data.json: servers[].carbon_intensity_g_kwh). Unique exception for the quick diagnostic (16 questions never filled automatically).",
    },
    "1.12": {
        "short_criterion": "Are there many trackers on the product?",
        "category": "automatable",
        "data_field": "security-headers-analysis.json: Content-Security-Policy (declared third-party inventory) ; har-analysis.json: domains (third parties actually loaded)",
        "rule": (
            "If a CSP is present and tracking hosts (families "
            "marketing_crm, pixels_publicitaires_sociaux, behavioral_analytics) "
            "are effectively loaded -> '💡 Improvement potential identified'. "
            "If tracking hosts are declared in the CSP but absent from the HAR -> "
            "'🤔 To be assessed' (likely gap: capture made without accepting consent). "
            "If only lean analytics is loaded (no cookie, no profiling) -> "
            "'✅ Confirmed strength'. "
            "If no CSP is available, fall back on the old tech_stack heuristic."
        ),
        "max_provenance": "estimated",
        "note": "Only detects what flows client-side (HAR); server-side tracking (e.g. logs) is invisible. Lean analytics (Swetrix, Plausible, Matomo...) is deliberately excluded from tracking.",
    },
    "2.1": {
        "short_criterion": "Does the product use technologies with a significant environmental impact (generative AI, blockchain) without clear justification?",
        "category": "automatable",
        "data_field": "env-data.json: ai_external_apis (dict, empty if no AI host detected) ; tech_stack.technologies[].category",
        "rule": (
            "If ai_external_apis is empty AND no AI/Blockchain category tech "
            "is listed -> '✅ Confirmed strength'. If at least one "
            "AI host or a blockchain tech is detected -> "
            "'💡 Improvement potential identified' (detection does not judge "
            "whether the usage is justified, only its presence - never an automatic "
            "'🚫 Not applicable')."
        ),
        "max_provenance": "estimated",
        "note": "An AI call made backend-side (never visible in the client HAR) is invisible to this rule - a 'no signal' is never proof of absence.",
    },
    "2.3": {
        "short_criterion": "Is it possible to optimize the separation and communication between components?",
        "category": "partial",
        "data_field": "security-headers-analysis.json: Content-Security-Policy (paas_backend family)",
        "rule": "The presence of distinct backend PaaS domains declared in the CSP (paas_backend family of csp_inventory) is a hint of separated components - it proves neither the optimization of their coupling nor the efficiency of their communication.",
        "max_provenance": "assumed",
        "note": "Declared inventory (CSP), not observed. An allowed PaaS domain is not necessarily contacted. Structural blind spot: a self-hosted backend behind a 1st-party reverse proxy is invisible here.",
    },
    "2.5": {
        "short_criterion": "Are the results of costly computations or queries cached instead of recomputed every time?",
        "category": "partial",
        "data_field": "har-analysis.json: duplicate_urls (list {url, count}) ; http_codes (share of 304)",
        "rule": (
            "A URL with a high 'count' in duplicate_urls, with a low share "
            "of 304 responses in http_codes, is a hint of a potentially uncached "
            "repeated query - never proof: an analytics beacon "
            "called on every interaction produces the same pattern without "
            "being a cache problem."
        ),
        "max_provenance": "assumed",
        "note": "Real risk of confusing an audience-measurement beacon (normal behavior) with a server computation mistakenly recomputed - display the URL and count in the appendix, never tick automatically.",
    },
    "3.2": {
        "short_criterion": "Is there a system for monitoring the environmental impact of the infrastructure?",
        "category": "partial",
        "data_field": "public-pages-criteria.json: tracking_declarations (sentence extracted from public HTML pages about eco-design)",
        "rule": (
            "A public declaration of monitoring or measuring environmental impact "
            "is a hint that the organization cares about the topic - it does not prove "
            "that this monitoring covers the infrastructure (carbon emissions, datacenter PUE/WUE) "
            "rather than just the site's pages. Criterion 3.2 explicitly "
            "targets infrastructure monitoring, not content."
        ),
        "max_provenance": "declared",
        "note": "First use of provenance 'declared': the page is published by the organization itself, it is neither a measurement (collected) nor a deduction (estimated) but an official public declaration.",
    },
    "3.3": {
        "short_criterion": "Is the hosting located in a region where the electricity mix is highly carbon-intensive?",
        "category": "automatable",
        "data_field": "env-data.json: servers[].carbon_intensity_g_kwh, servers[].country_code (iterate over ALL 1st-party servers in the list, not just the first - cf. a 1st-party host with different infra is a distinct server)",
        "rule": (
            "If at least one server in the list has carbon_intensity_g_kwh above "
            "a threshold (benchmark: ~250 gCO2/kWh, average European electricity mix) -> "
            "'💡 Improvement potential identified'. If all are below -> "
            "'✅ Confirmed strength'."
        ),
        "max_provenance": "collected",
        "note": "The carbon_intensity data (ipinfo + carbon table) is already provenance 'collected' at source; it only covers servers identified from the HAR, never invisible infra (self-hosted DB/service behind the application).",
    },
    "3.4": {
        "short_criterion": "Can the infrastructure be shared/mutualized?",
        "category": "partial",
        "data_field": "security-headers-analysis.json: Content-Security-Policy (families paas_backend, cdn_bibliotheques, infra_cloud_generique)",
        "rule": "The presence of declared shared PaaS/CDN/cloud domains in the CSP is a hint of shared infrastructure - it does not prove that ALL the infrastructure is shared, nor the absence of dedicated servers elsewhere.",
        "max_provenance": "assumed",
        "note": "Declared inventory (CSP), not observed. An allowed cloud domain is not necessarily contacted. Structural blind spot: a self-hosted infra behind a 1st-party reverse proxy is invisible here.",
    },
    "3.6": {
        "short_criterion": "Can elasticity/auto-scaling tools and strategies be deployed to reduce the size of the infrastructure?",
        "category": "partial",
        "data_field": "security-headers-analysis.json: Content-Security-Policy (paas_backend family)",
        "rule": "The presence of declared backend PaaS domains in the CSP is a hint of a platform supporting elasticity - it does not prove that auto-scaling is configured, nor that the load varies enough to justify it.",
        "max_provenance": "assumed",
        "note": "Declared inventory (CSP), not observed. An allowed PaaS domain is not necessarily contacted, and even if contacted, nothing says elasticity is enabled. Structural blind spot: a self-hosted Kubernetes is invisible here.",
    },
    "5.4": {
        "short_criterion": "Are the performance indicators (Core Web Vitals) good?",
        "category": "automatable",
        "data_field": "cwv.json (per page: lcp, inp, cls, mobile/desktop strategy, source='crux')",
        "rule": (
            "Official Google thresholds: LCP > 4s, INP > 500ms, or CLS > 0.25 "
            "on AT LEAST one page -> '💡 Improvement potential identified' "
            "('poor', unambiguous). All pages under the "
            "'good' thresholds (LCP<=2.5s, INP<=200ms, CLS<=0.1) -> "
            "'✅ Confirmed strength'. Intermediate zone ('needs improvement') "
            "with no 'poor' page -> '🤔 To be assessed' (ambiguous, do not decide)."
        ),
        "max_provenance": "collected",
        "note": "Real field CrUX data (source='crux'), not a lab test - already the most reliable measurement in the whole mapping.",
    },
    "1.9": {
        "short_criterion": "Does the product require a high-speed connection?",
        "category": "partial",
        "data_field": "env-data.json: har_summary.efootprint.data_transferred_bytes_real (actual transferred weight)",
        "rule": "A high page weight is an indirect hint of bandwidth need - a heavy page does not necessarily imply a high-speed requirement (also depends on the usage's tolerance for loading time).",
        "max_provenance": "assumed",
        "note": "Weight proxy, not a measurement of the real throughput need.",
    },
    "1.14": {
        "short_criterion": "Are the main screens/pages designed in a lightweight way?",
        "category": "partial",
        "data_field": "env-data.json: pages[].size_kb (comparison between pages of the same journey)",
        "rule": "A page significantly heavier than the others of the same journey is a hint of less lightweight design - it does not judge the design quality itself (justified vs superfluous content).",
        "max_provenance": "assumed",
        "note": "Weight proxy, not a measure of \"design lightness\".",
    },
    "1.15": {
        "short_criterion": "Is the service frequently used relative to its resource consumption?",
        "category": "partial",
        "data_field": "env-data.json: traffic.visits_per_year / traffic.monthly_visits (SimilarWeb estimate)",
        "rule": "Gives an order of magnitude of usage, not a judgment of proportionality between usage and resources consumed (which assumes knowing the deployed architecture).",
        "max_provenance": "estimated",
        "note": "Third-party source with a wide margin (cf. step 20c of efootprint) - a figure, not a comparison.",
    },
    "1.16": {
        "short_criterion": "Does the user volume justify the deployed infrastructure?",
        "category": "partial",
        "data_field": "env-data.json: traffic.visits_per_year",
        "rule": "Same field as 1.15: gives the traffic figure, not the comparison to the actually deployed infrastructure (server sizing not reliably measured, cf. efootprint-python-summary.json where server_type/instance_type are often script defaults, not observations).",
        "max_provenance": "estimated",
        "note": "Never cross-reference with server_type/instance_type from efootprint-python-summary.json if their source is 'default_script' - that would fabricate a judgment from a technical default, not a measurement.",
    },
    "1.5": {
        "short_criterion": "Are there animations/videos/sounds played automatically?",
        "category": "automatable",
        "data_field": "html-css-criteria.json: pages[].has_autoplay_media (HTML re-fetched live, cf. script note — the .har does not contain HTML bodies)",
        "rule": (
            "No page with <video autoplay> or <audio autoplay> -> "
            "'✅ Confirmed strength'. At least one affected page -> "
            "'💡 Improvement potential identified'."
        ),
        "max_provenance": "collected",
        "note": "Only detects the HTML autoplay attribute at load time, not an autoplay triggered by JS afterwards (known blind spot).",
    },
    "1.6": {
        "short_criterion": "Is it possible to adapt resources to the user's hardware configuration?",
        "category": "automatable",
        "data_field": "html-css-criteria.json: pages[].adaptive_img_ratio (srcset/<picture>) AND css.media_query_count",
        "rule": (
            "'✅' only if NO page has an adaptive_img_ratio of 0 (with "
            "images) AND at least 3 distinct CSS media queries exist. "
            "'💡' only if NEITHER srcset/<picture> NOR media query is found "
            "anywhere. Otherwise (mixed signal: e.g. many media queries but one "
            "page without adaptive images) -> '🤔 To be assessed' (deterministic constraint: two "
            "conflicting signals are never decided by guesswork)."
        ),
        "max_provenance": "estimated",
        "note": "Two distinct proxies (responsive images, adaptive CSS) merged cautiously; does not measure JS adaptation (e.g. dynamic video quality).",
    },
    "1.13": {
        "short_criterion": "Are the main user journeys optimized to be smooth and efficient?",
        "category": "automatable",
        "data_field": "cwv.json: accessibility_score_pct (PageSpeed Insights API, accessibility category, same calls as CWV)",
        "rule": (
            "Accessibility score >= 90 on ALL pages/strategies -> "
            "'✅ Confirmed strength'. Score < 60 on at least one -> "
            "'💡 Improvement potential identified'. Zone 60-90 with no page "
            "< 60 -> '🤔 To be assessed' (ambiguous, do not decide)."
        ),
        "max_provenance": "collected",
        "note": "Accessibility proxy (not directly 'journey smoothness') — the framework has no dedicated a11y criterion among the 54, this one is the closest semantically. To be corroborated by a human.",
    },
    "1.4": {
        "short_criterion": "Does the design include custom components rather than native components?",
        "category": "partial",
        "data_field": "html-css-criteria.json: pages[].native_buttons vs pages[].custom_role_buttons",
        "rule": "A high custom/native ratio is a hint of reinvented rather than native components - only covers buttons (partial proxy, not all custom UI components).",
        "max_provenance": "assumed",
        "note": "Static HTML detection only (post-hydration React/Vue the real DOM may differ) — a hint, never proof.",
    },
    "1.11": {
        "short_criterion": "Sobriety by default: are system preferences respected (reduced motion, theme)?",
        "category": "partial",
        "data_field": "html-css-criteria.json: css.has_prefers_reduced_or_scheme",
        "rule": "The presence of @media (prefers-reduced-motion) or (prefers-color-scheme) in the loaded CSS is a hint of sobriety by default - absence is not proof of absence of sobriety (may be handled otherwise, e.g. JS).",
        "max_provenance": "assumed",
        "note": "Simple syntactic detection (presence of the rule), no verification that the actual behavior changes as a result.",
    },
    "6.1": {
        "short_criterion": "Is there an effective observability setup for the product?",
        "category": "partial",
        "data_field": "security-headers-analysis.json: worst_page.grade (local security score, proxy for prod maturity)",
        "rule": "A high security score (grade A/B) is an indirect hint of general operational maturity, never proof of observability (metrics/logs/traces) - data totally invisible client-side.",
        "max_provenance": "assumed",
        "note": "Very indirect proxy (security rigor != observability); displayed in the appendix only, never ticked.",
    },
    "6.3": {
        "short_criterion": "Is there an effective CI/CD process?",
        "category": "partial",
        "data_field": "*.har: Last-Modified headers of 1st-party resources (HTML/CSS/JS code)",
        "rule": "Deployment freshness (age of the most recent resource) and atomicity (dispersion of Last-Modified across code resources) are indirect hints of deployment maturity - they measure neither the actual deployment frequency nor the existence of a CI/CD pipeline (content can be updated manually).",
        "max_provenance": "assumed",
        "note": "A tight dispersion can result from manually pushing the whole tree, and a recent deployment says nothing about deployment frequency.",
    },
    "6.6": {
        "short_criterion": "Are there indicators to track software quality?",
        "category": "partial",
        "data_field": "cwv.json: best_practices_score_pct ; security-headers-analysis.json: worst_page.grade ; wellknown-scan.json: security_txt.present",
        "rule": "A high Best Practices score and/or a well-formed security.txt are hints of tool-supported quality practices - they never prove the existence of quality indicators tracked internally (SonarQube, etc., invisible client-side).",
        "max_provenance": "assumed",
        "note": "Three weak proxies combined in the informative appendix only, never an automatically tickable criterion.",
    },
    "6.8": {
        "short_criterion": "Is there duplicated code in the application?",
        "category": "partial",
        "data_field": "cwv.json: lighthouse_insights['duplicated-javascript'] (Lighthouse audit)",
        "rule": "The absence of duplication detected by Lighthouse (score=1, 0 items) does not prove that dependency management is good, only the absence of obvious client-side JS bundle duplication - a weak hint, never a validation.",
        "max_provenance": "assumed",
        "note": "Client-side detection only (JS loaded in the HAR), blind spot on backend code and on duplication within the same bundle.",
    },
    "5.5": {
        "short_criterion": "Are the critical journeys (the most frequent ones) prioritized for optimization?",
        "category": "partial",
        "data_field": "coverage-analysis.json (unused JS/CSS per page) ; cwv.json (per page)",
        "rule": "Assumes that the actually audited pages are the site's most frequent journeys - hypothesis not verified by the available data (no usage ranking per page).",
        "max_provenance": "assumed",
        "note": "\"Critical\"/\"frequent\" is never measured: only the content of the audited pages is.",
    },
}
