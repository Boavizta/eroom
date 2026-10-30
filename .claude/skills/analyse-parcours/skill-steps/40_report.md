# Step 40 — HTML summary report

> Source: skill-steps/40_report.md. Return: SKILL.md (end).

## HTML report generation

Call the Python script:

```bash
python3 .claude/skills/analyse-parcours/scripts/generate_report_html.py <audit-dir>
```

The script reads the `.har`, the `Coverage-*.json` and the optional `cwv.json` from the folder.
It produces `journey-report-YYYY-MM-DD.html` in that same folder.

## HTML report structure (sections in order)

### Header (cover)
- Title, date, analyzed domains, nb of pages, source files

### EcoIndex dashboard
Per-page table with: colored grade (A-G), score /100, requests, weight (KB), DOM, LCP/onLoad, INP, CLS
- Source: `har_metrics.py` (step 35)
- If `cwv.json` absent: displayed LCP = HAR onLoad with an explicit note

### Section 1 — Network traffic
- KPIs: total requests, transferred volume, nb of domains
- Domains contacted (visual tags)
- HTTP codes (colored: green/orange/red)
- Top 10 heaviest resources
- Duplicate requests (if any)

### Section 2 — Dead code (Coverage)
Per Coverage page:
- Visual JS and CSS gauges (red/green bar)
- Top 8 files table by unused code (total size, unused KB, %, bar)

### Section 3 — Core Web Vitals
Displayed only if `cwv.json` is provided.
- Per-page table: LCP, INP, CLS with color code (green/orange/red according to Google thresholds)

### Section 4 — Recommendations
- PRIORITY 1 (red background): EcoIndex < 40, DOM > 1500, dead JS code > 70%
- PRIORITY 2 (orange background): EcoIndex 40-55, DOM 800-1500, duplicates, dead JS code 50-70%
- PRIORITY 3 (green background): Brotli, CDN, lightweight third-party libraries

## Output file

The script generates:
```
<audit-dir>/journey-report-YYYY-MM-DD.html
```

Indicate the path of the generated file at the end of the response.
