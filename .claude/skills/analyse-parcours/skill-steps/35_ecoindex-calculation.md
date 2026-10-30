# Step 35 — EcoIndex calculation

> Source: skill-steps/35_ecoindex-calculation.md. Return: SKILL.md step 40.

## Principle

The EcoIndex is computed entirely from the HAR, with no manual input:
- **Requests**: counted from `log.entries` per page (`pageref`)
- **Weight**: sum of `response.content.size` per page
- **DOM**: counted by parsing the HTML body of the first `text/html` response of each page (`response.content.text`)

The official formula (cnumr/ecoindex_reference) with quantiles is implemented in `scripts/har_metrics.py`.

## Execution

```bash
python3 .claude/skills/analyse-parcours/scripts/har_metrics.py <har-file> [cwv.json]
```

The script prints a per-page table and automatically validates against known ANTS values
(dom=483, req=82, weight=1930 KB → expected score 53/100, grade D).

## Produced result

For each page of the HAR:

```
Page             Req    KB    DOM  Score  Grade  onLoad
----------------------------------------------------- ...
Page 1 - [URL]    82  1930    483     53      D   1374ms
Page 2 - [URL]    53  2664    383     61      C    678ms
...
```

Grades: A (≥80) · B (≥70) · C (≥55) · D (≥40) · E (≥25) · F (≥10) · G (<10)

## Special cases

### DOM = 0 after parsing

If the HAR does not contain the HTML body (`response.content.text` field absent or empty for `text/html` entries), the DOM will be 0 and the score overestimated.

In this case: display a warning and note in the report that the DOM could not be extracted automatically.

### SPA (Single Page Application) pages

For SPAs, only one initial `text/html` entry exists. The measured DOM corresponds to the initial state, not the DOM after JS execution. This is consistent with the GreenIT-Analysis method (measurement at the end of loading), but slightly different if the SPA hydrates heavily.

Mention this limitation in the report if several pages share the same HTML document.

## Integration into the workflow

The metrics computed at this step feed directly into:
- The HTML report dashboard (step 40)
- The EcoIndex section of the dashboard
- The prioritized recommendations (score < 40 → PRIORITY 1)
