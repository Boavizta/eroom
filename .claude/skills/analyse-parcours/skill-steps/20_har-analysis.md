# Step 20 — HAR file analysis

> Source: skill-steps/20_har-analysis.md. Return: SKILL.md step 30.

## Execution — one script, not a hand calculation

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/analyze_har.py <source-dir>
```

The script writes `<source-dir>/audit/har-analysis.json`. `--check`
option to compare against the existing output without rewriting anything.

**Do not recompute these aggregates by hand.** Work item 35: this step had
no script until now, and a manual read of the `.har` had produced a
`blocking_resources` key invented by eyeballing the HTML,
with no archive to back it up — impossible to verify that the numbers feeding
the EOF (duplicate-requests criterion) are stable.

The script classifies 1st-party/3rd-party from `env-data.json` (canonical
rule shared with `deploy_freshness.py`), deduplicates by URL before the top10
of the heaviest resources (otherwise an uncached resource, loaded
8 times, can take 8 of the 10 slots), and computes the blocking resources of
the `<head>` only for pages whose HTML archive (work item 27,
`<source_dir>/html-pages/`) is available — otherwise the field is marked "not
computed", never guessed from the MIME type alone.

Non-regression checks: `analyze_har.py --autotest` (17 cases).

The section below documents the **format** of the files read and the **shape**
of the expected output. It only becomes a calculation instruction again if the
script is unavailable.

## 20a — Traffic overview

Read the HAR (JSON format, key `log.entries[]`). Extract:

- Total number of requests (`log.entries.length`)
- Domains contacted (extract host from `request.url`, group: first-party / third-party)
- HTTP code distribution (200, 301, 302, 404, 5xx...)
- Total transferred volume (sum of `response.content.size` in bytes, convert to MB)
- Top 10 heaviest requests (by `response.content.size`)

## 20b — Network performance

- Requests without cache (absence of `Cache-Control` or `Expires` in the response)
- Requests to identical URLs (duplicates)
- Blocking resources (synchronous JS/CSS in `<head>` - inferred from MIME types)
- Slow third-party resources (response time > 1s)
