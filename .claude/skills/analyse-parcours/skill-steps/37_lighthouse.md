# Step 37 — CWV via Lighthouse or PageSpeed Insights

**When:** after step 35, before step 40.

## Choosing the CWV source

| Source | Command | Data | Advantages |
|--------|----------|---------|-----------|
| PageSpeed + CrUX | `collect_cwv_pagespeed.py` | Real field P75 | Reflects real users; requires `GOOGLE_API_KEY` |
| Lighthouse (fallback) | `run_lighthouse.sh` | Lab (simulation) | Works without an API key, even on auth pages |

`collect_cwv_pagespeed.py` is the main entry point. It automatically triggers the Lighthouse fallback in two cases:
- `GOOGLE_API_KEY` absent from `.env`
- No metric collected via the API (quota exceeded, network, URLs unknown to CrUX)

-----

---

## Automatic flow

### Case 1: cwv.json absent

1. Run the script without URLs: it extracts all unique URLs from the HAR itself.

```bash
bash .claude/skills/analyse-parcours/scripts/run_lighthouse.sh <audit-dir>
```

The script deduplicates URLs (`log.pages[].title`) before launching Lighthouse, so each page is analyzed only once even if it appears several times in the journey.

3. Display progress:
```
[Step 37] Lighthouse CWV — analyzing N page(s) via npx...
  -> page_1 : https://...
  -> page_2 : https://...
[Step 37] cwv.json generated.
```

4. Continue to step 40.

### Case 2: cwv.json already present

Display:
```
[Step 37] cwv.json already present — Lighthouse skipped.
```
Go directly to step 40.

### Case 3: the user asks "re-run Lighthouse"

Delete `cwv.json` from the audit folder, then resume from Case 1.

---

## If Lighthouse fails

Display a warning and continue without CWV:
```
[Step 37] Lighthouse unavailable (npx missing or pages unreachable).
The report will continue without CWV. To retry: "re-run Lighthouse".
```

Possible causes:
- `npx` missing (Node.js not installed)
- Pages behind authentication (headless Chrome without a session)
- Blocked network

---

## Limitations

- "Lab" measurements (network simulation), not real field data
- Pages behind a login are not supported
- Results may differ from the field depending on the connection

For real field data, use `collect_cwv_pagespeed.py` (see section above) or provide a manual `cwv.json` (see docs/capture-har-and-coverage.md).

-----

## PageSpeed Insights + CrUX (field data)

### Prerequisites

- `GOOGLE_API_KEY` in `.env` at the project root (see `documentation/setup/setup_api_keys.md`)
- APIs enabled on Google Cloud: PageSpeed Insights API + Chrome UX Report API

### Check the API key

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <audit-dir> --check
```

### Collect the CWVs

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py <audit-dir>
```

By default (`--strategy both`): collects **both mobile AND desktop** in a single command, kept side by side in `cwv.json` (one entry per url/strategy pair). Restrict if needed with `--strategy mobile` or `--strategy desktop`.

### Results in cwv.json

- `"strategy"` : `"mobile"` or `"desktop"` (one entry per device, no more overwriting between passes)
- `"source": "crux"` : CrUX P75 field data (real users) - priority
- `"source": "pagespeed_lab"` : Lighthouse lab data via API (if CrUX is absent for this URL)
- `"crux_category"` : `"FAST"` / `"AVERAGE"` / `"SLOW"` (overall CrUX classification)

The report displays mobile and desktop separately, with a source badge (field / lab / local lab).

### Methodological note

CrUX data are P75 percentiles over the last 28 days of real usage. They are only available for URLs with enough traffic in Google's CrUX database. For rarely visited pages or pages behind authentication, the script automatically falls back to lab data.
