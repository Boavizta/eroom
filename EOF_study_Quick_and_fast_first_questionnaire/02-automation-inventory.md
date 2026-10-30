# What the already-collected data can (or cannot) bring to the 21 non-automated criteria

Out of the 26 criteria in scope (dimension 0 + dimension 6), only one is really automatable today (`0.16`, cf. file 01). This document evaluates the 21 remaining criteria, one by one, from the data really present in the project (not assumed).

Sources inspected: `audits/octo.com/env-data.json`, `cwv.json`, `security-headers-analysis.json`, `html-css-criteria.json`, `public-pages-criteria.json`, `wellknown-scan.json`, `topology-octo.com.puml`, `efootprint-boavizta-model.json`, `tmp/pagespeed-raw-octo-2026-09-04.json`, as well as the scripts `run_eof.py`, `eof_criteria_mapping.py`, `parse_public_pages.py`, `deploy_freshness.py`, `csp_inventory.py`, `detect_tech.py`.

## Verdicts

| Criterion | Verdict | Justification |
|---|---|---|
| 0.1 | NOT AUTOMATABLE (weak proxy rejected) | The traffic volume (`env-data.json: traffic.visits_per_year`) does not measure business criticality: a critical internal tool can have little traffic. Value judgment, invisible from outside. |
| 0.2 | NOT AUTOMATABLE | Requires knowing the organization's other internal systems. No external signal possible. |
| 0.3 | NOT AUTOMATABLE (weak proxy rejected) | Identical to `6.10`. The presence of a multi-IP CDN proves no real SLA/SLO on the business components. |
| 0.4 | PARTIALLY INFORMATIVE (already wired) | `run_eof.py::diag_context_0_4` reads `har-analysis.json: domains.third_party` and displays the list in the question appendix, with the explicit caveat that it says nothing about the complete architecture. |
| 0.5 | NOT AUTOMATABLE | Question of access rights to an internal repository. |
| 0.6 | NOT AUTOMATABLE | Team skill, purely internal. |
| 0.7 | PARTIALLY INFORMATIVE (not wired) | The datum exists (CSP: `paas_backend` family, ex. `herokuapp.com`; 4 distinct CDNs in `tech_stack.categories.CDN`) but is linked to no `DIAG_CONTEXTS` in `run_eof.py`. Structural blind spot on the backend not exposed to the client. |
| 0.8 | NOT AUTOMATABLE (weak proxy rejected) | `env-data.json: servers[]` only sees a single 1st-party host on the client side; `efootprint-boavizta-model.json` indicates `server_type: "autoscaling"` with the comment "default sizing mode" (a script default, not an observation). |
| 0.9 | NOT AUTOMATABLE (weak proxy rejected) | `efootprint-boavizta-model.json: Storage.storage_capacity = 1.0 TB` has `source: "hypothesis"`: default value of the CO2e model, never a real measurement of the stored volume. |
| 0.10 | PARTIALLY INFORMATIVE (wired but inert on octo.com) | `run_eof.py::diag_context_0_10` reads `wellknown-scan.json: sitemap.url_count`. On octo.com, `sitemap.present: false` so no hint is currently produced. Even when available, the URL count remains a weak proxy (a single page can carry a complex SPA). |
| 0.11 | PARTIALLY INFORMATIVE (not wired) | `cwv.json` shows `accessibility_score_pct=100` (lab), `best_practices_score_pct=81` (lab), and lcp/inp/cls in the "good" zone (`source=crux`, real field data). Lowers the probability of technical friction, but says nothing about perceived navigation clarity. |
| 0.12 | PARTIALLY INFORMATIVE (not wired) | `cwv.json` (`crux_category="FAST"`, mobile) reflects the real visitor population, including low-end hardware, but a single entry and no notion of "oldest hardware in the target fleet". No real test on an old device. |
| 0.13 | NOT AUTOMATABLE | Internal backlog (Jira or equivalent), never exposed publicly. |
| 0.14 | NOT AUTOMATABLE (weak proxy rejected) | The Lighthouse indicators (`bootup-time`, `render-blocking`...) measure the technical execution of the page, not whether the business features are well designed for the intended use. |
| 0.15 | NOT AUTOMATABLE with the current tooling (but not structurally impossible) | A public data policy page is in principle observable from outside (cf. `/protection-donnees` documented in `tmp/handoff-2026-09-04-couverture-eof-sources-ARCHIVE.md` for other sites). But `parse_public_pages.py` is today scoped exclusively to environmental patterns (`PAGE_NAME_PATTERNS`, `KEYWORDS_SUIVI`): no data retention/deletion pattern. That is an implementation gap, not a structural ceiling. |
| 6.1 | PARTIAL (already wired, never an answer) | `security-headers-analysis.json: worst_page.grade` displayed in the appendix. The mapping rule is explicit: `category: "partial"` -> never a box ticked automatically. |
| 6.2 | NOT AUTOMATABLE | Internal team practice (code review, pair programming), invisible from the audited HTTP traffic. |
| 6.3 | PARTIAL (already wired) | `Last-Modified` headers of 1st-party resources in the `.har`, as a deployment-freshness hint. Always a hint, never an answer. |
| 6.4 | NOT AUTOMATABLE | Test suite on the repository/CI side, never exposed via the public site. |
| 6.5 | NOT AUTOMATABLE (weak proxy rejected) | The infrastructure separation visible in the CSP is an infra fact, not a code decoupling (hexagonal architecture...), an internal property of the source code. |
| 6.6 | PARTIAL (already wired) | Three hints combined in the appendix: `cwv.json: best_practices_score_pct`, `security-headers-analysis.json: worst_page.grade`, `wellknown-scan.json: security_txt.present`. Never ticked automatically. |
| 6.7 | NOT AUTOMATABLE | No developer documentation page detectable from outside; internal documentation out of reach of an external audit. |
| 6.8 | PARTIAL (already wired) | `cwv.json: lighthouse_insights['duplicated-javascript']`, client-side detection only. Hint, never an answer. |
| 6.9 | NOT AUTOMATABLE | Internal governance/rights question (cloud access, permissions). |
| 6.10 | NOT AUTOMATABLE (weak proxy rejected) | Identical to `0.3`, same shared questionnaire block. |

## Total over the 25 criteria not yet automated (26 criteria minus 0.16)

**0 additionally automatable (box ticked on its own), 9 partially informative (hint displayed, human answer still required: 0.4, 0.7, 0.10, 0.11, 0.12, 6.1, 6.3, 6.6, 6.8), 1 not automatable with the current tooling but not structurally impossible (0.15), 15 structurally not automatable (internal fact about the team, no external signal possible).**

Counting correction: the first version of this study took as-is a verbal total ("16 non-automated out of 21") given by a sub-agent, without recalculating it from the table above. The correct count, recalculated line by line over the 26 criteria (1 automatable + 9 partial + 1 special case + 15 structural = 26), is the one in this paragraph. The consolidated table of `00-session-summary.md` uses this corrected figure.

Special point: `0.15` is not structurally out of reach (a public data policy page is an observable fact), but the current tool does not look for it. It is an identified implementation gap, not a final verdict.

Three weak-proxy traps were explicitly rejected and documented above: traffic to judge criticality (`0.1`), e-footprint model default values to judge infra size or data volume (`0.8`, `0.9`), and a technical Lighthouse score to judge business functional effectiveness (`0.14`).

**None of these 9 partial hints reduces the number of questions to ask** (the mapping rule explicitly forbids it: `partial` never ticks a box on its own). Their only possible use is to make the question easier and more reliable to answer for the human, by recalling in the question what has already been measured.
