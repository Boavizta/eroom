# Replay against the data already collected on octo.com

Goal: check whether the abstract analysis (files 01 and 02) holds against the data really collected on octo.com, or whether the real case reveals additional exploitable signals.

Source: `audits/octo.com/eof-audit-results.json` (read-only, no modification).

## Real state of the 26 criteria on octo.com, today

| Criterion | Answer | Provenance | Available hint |
|---|---|---|---|
| 0.1 to 0.3, 0.5 to 0.9, 0.13 to 0.15 | empty | none | none |
| 0.4 | empty | none | "5 third-party domain(s) detected during the capture: api.analytics.octo.tools, cdn.jsdelivr.net, fonts.googleapis.com, fonts.gstatic.com, swetrix.org" |
| 0.10 | empty | none | none (sitemap absent on octo.com: `wellknown-scan.json: sitemap.present = false`) |
| 0.11, 0.12 | empty | none | none (mechanism not wired in `run_eof.py`, cf. file 02) |
| **0.16** | **"2- < 500 gCO2e / kWh"** | **collected** | `env-data.json: servers[].carbon_intensity_g_kwh = 381 gCO2e/kWh` |
| 6.1 | empty | assumed (hint only) | `security-headers-analysis.json: worst_page.grade` |
| 6.2, 6.4, 6.5, 6.7, 6.9, 6.10 | empty | none | none |
| 6.3 | empty | assumed (hint only) | `*.har`: Last-Modified headers of 1st-party resources |
| 6.6 | empty | assumed (hint only) | `cwv.json: best_practices_score_pct` + `security-headers-analysis.json: worst_page.grade` + `wellknown-scan.json: security_txt.present` |
| 6.8 | empty | assumed (hint only) | `cwv.json: lighthouse_insights['duplicated-javascript']` |

Confirmed by direct reading of the JSON: dimension 6, `answered: 0`, `total: 10`, `completeness_pct: 0.0`. Dimension 0: 15 of the 16 questions have `reponse: null`. Over the whole octo.com audit (54 detailed criteria, all dimensions), `answered_by_provenance` = `{collected: 4, estimated: 3, declared: 0, stated: 0, assumed: 0}`: **no human answer has been entered yet for octo.com**, neither on the 54 detailed criteria, nor on the 26 criteria of the present scope.

## Finding of the replay

**The real data confirms exactly the abstract analysis, with no surprise nor hidden deposit:**

- The only criterion really filled without human intervention is `0.16` (1/26 = 3.8 %), via the same datum as `3.3`.
- The 4 "partial" hints foreseen by the mapping (`6.1`, `6.3`, `6.6`, `6.8`) are indeed present and fed by real octo.com data, but none of them fills `reponse`: consistent with the rule "partial never ticks on its own".
- The `0.4` hint is indeed fed with octo.com's 5 real third-party domains.
- The `0.10` hint is wired but inert, because octo.com has no sitemap.
- No datum collected on octo.com (HAR, CWV, security headers, CSP, wellknown, e-footprint, topology) allows settling one of the 20 remaining criteria without going through the "weak proxy rejected" box already discarded in file 02.

**Conclusion of the replay: there is no octo.com-specific hidden gain that the abstract analysis on the reference alone would not have identified.** The automation ceiling (1 criterion out of 26) is the same in the abstract and in the real data.

## Warning about this snapshot

This replay was done on a snapshot of `audits/octo.com/eof-audit-results.json` taken during this session. Another agent was modifying this same file in parallel (and `wellknown-scan.json`, `html-css-criteria.json`) via a new step `39b_questionnaire-eof.md` being written. The figures for dimension 0 and dimension 6 (structurally little automatable, cf. files 01-02) should not move, but if this job is resumed, re-check the state of the file before citing these figures as final.
