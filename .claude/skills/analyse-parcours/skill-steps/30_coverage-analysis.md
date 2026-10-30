# Step 30 — Coverage file analysis

> Source: skill-steps/30_coverage-analysis.md. Return: SKILL.md step 40.

## Execution — one script, not a hand calculation

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/coverage_metrics.py <source-dir>
```

The script writes `<source-dir>/audit/coverage-analysis.json`. `--check`
option to compare against the existing output without rewriting anything.

**Do not recompute these aggregates by hand.** Two mistakes came from doing so:

1. The extension is read on the **path** of the URL, never on the full URL. A
   versioned URL (`dsfr.min.css?version=39.2.0`) does not end with its
   extension: a `url.endswith(".css")` test classifies it as "other". A page whose
   *all* URLs are versioned is then published at **zero KB**, which does
   not look like an error but like a page without code. It happened on the 4th
   page of a remote procedure, the one that loaded the most CSS.
2. A page's label comes from the URL of the **document actually served as
   `text/html`**, corroborated by the HAR. Without that, the first asset URL without
   an extension wins: on a remote procedure, it is often a technical URL
   (anti-CSRF token), and the page is displayed under a name that is not
   the one of the screen seen by the user.

Non-regression checks: `check_coverage_metrics.py` (28 checks).

The section below documents the **format** of the files read and the **shape** of
the expected output. It only becomes a calculation instruction again if the script
is unavailable.

## Chrome Coverage file format

Each JSON file contains an array of entries. Two possible formats depending on the Chrome DevTools version:

**Format A (direct array)**:
```json
[
  {
    "url": "https://example.com/app.js",
    "ranges": [...],
    "text": "..."
  }
]
```

**Format B (wrapped)**:
```json
{
  "timestamp": 1234567890,
  "entries": [
    {
      "url": "https://example.com/app.js",
      "ranges": [...],
      "text": "..."
    }
  ]
}
```

Detect the format before reading.

## 30a — Per-page metrics

For each Coverage JSON file:

1. **Identify the page**: extract from the file name (e.g. `Coverage-20260328T105137_page 1.json` -> "Page 1") or from the URLs present in the entries
2. For each entry:
   - `totalSize` = length of the source text (`text.length`)
   - `usedSize` = sum of the `ranges` (end - start)
   - `unusedSize` = totalSize - usedSize
3. Aggregate by MIME type (JS / CSS / other)

Per-page table:
```
Page [N] — [URL or name]
  JS  : [X KB] total, [Y KB] unused ([Z%])
  CSS : [X KB] total, [Y KB] unused ([Z%])
  Total : [X KB] total, [Y KB] unused ([Z%])
```

## 30b — Most expensive files

Top 5 JS files by unused size (short name + size):
```
1. vendor-xxxx.js          1 600 KB unused
2. chunk.709.js              980 KB unused
...
```

Top 3 CSS files by unused size.

Identify recognizable third-party libraries:
- Analytics: Google Analytics, Matomo, Kameleoon, AT Internet
- Chatbots: tolk.ai, Intercom, Zendesk
- A/B testing: Kameleoon, AB Tasty, Optimizely
- CAPTCHA: reCAPTCHA, hCaptcha, LiveIdentity
- UI frameworks: Bootstrap, Tailwind, DSFR (French Design System)

## 30c — Multi-page summary

Aggregate all files:

```
Coverage summary — [N] pages analyzed
-----
Total JS loaded    : [X MB]
Total JS unused    : [Y MB] ([Z%])
Total CSS loaded   : [X KB]
Total CSS unused   : [Y KB] ([Z%])
-----
Page-by-page evolution:
  Page 1 : [X KB] unused
  Page 2 : [X KB] unused (+[delta] vs page 1)
  ...
```

Report if a page loads significantly more code than the others (outlier > 2x the median).
