# Changelog — Agent EROOM

Format inspired by [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Dates correspond to the commits that change the `version:` field in `.claude/skills/analyse-parcours/SKILL.md` (source of truth for the version displayed in the footer of generated reports).

## [1.2.1] - 2026-09-21 — Stabilization

No new major feature: this version point consolidates the EOF framework and the audit pipeline after the 1.2.0 extension.

- EOF questionnaire consolidated into a single file, covering the 70 criteria of the framework, duplicate questions removed
- Probe reliability: distinction between a probe failure and a real absence at the audited service, correction of the EcoIndex base64 decoding, confidence degradation on the server country when a CDN is detected
- Report and EOF radar display fixes ("None"/"N/A" values, precise/declared precedence inversion, hatching limited to the uncertainty margin)
- Addition of the CO2e gain and the EcoIndex/LCP gain per recommendation tier (prio 1 / 1+2 / 1+2+3)
- Extension of the parallel dispatch (Core Web Vitals, env-data, security, EOF extractors) and correction of a silent masking of CWV measurement failures
- README cleanup and additions (licenses of third-party projects/services) and diagrams

## [1.2.0] - 2026-09-03

- Extension of Phase 1 automation of the EOF framework (4 → 7 automatable criteria, 6 → 11 indices)
- Latest OSINT / black-box probes: reading the public pages declared by the audited organization (CSR, eco-design), introduction of the "declared" provenance level
- Introduction of the EOF framework (EROOM Optimization Framework) the day before (2026-09-02): dedicated skill, blank template, SVG radar

## [1.1.0] - 2026-07-30

- Merge of the "efootprint" skill (until then standalone) into "analyse-parcours": no more separate skill, integrated as a step (`skill-steps/45_efootprint.md`)

## [1.0.2] - 2026-07-13

- Renaming of the tool to "Agent EROOM" in the footer of generated reports
- Introduction of e-footprint (calculation of the environmental footprint of the audited site, Boavizta library) on 2026-07-27, under this version

## [1.0.0] - 2026-07-08

- Initial creation of the analyse-parcours skill
