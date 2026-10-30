# Capture a HAR file and Chrome coverage data

**Objective**: capture all the network traffic and the code loaded during a web journey,
for an e-responsibility and performance analysis.

## Table of contents

- [Prerequisites](#prerequisites)
- [Part 1 - Capture the HAR file](#part-1---capture-the-har-file)
  - [Step 1 - Pre-cleaning](#step-1---pre-cleaning)
  - [Step 2 - Prepare the Network tab](#step-2---prepare-the-network-tab)
  - [Step 3 - Perform the journey](#step-3---perform-the-journey)
  - [Step 4 - Export the HAR](#step-4---export-the-har)
  - [Step 5 - Check the HAR file](#step-5---check-the-har-file)
- [Part 2 - Capture the coverage data (Coverage)](#part-2---capture-the-coverage-data-coverage)
  - [Step 1 - Open the Coverage panel](#step-1---open-the-coverage-panel)
  - [Step 2 - Capture a page](#step-2---capture-a-page)
  - [Step 3 - Export the Coverage file](#step-3---export-the-coverage-file)
  - [Step 4 - Repeat for each page](#step-4---repeat-for-each-page)
  - [Step 5 - Check the Coverage files](#step-5---check-the-coverage-files)

## Extended table of contents

- [Part 3 - Core Web Vitals (optional)](#part-3---core-web-vitals)
  - [Option A - Automatic Lighthouse (recommended)](#option-a---automatic-lighthouse-recommended)
  - [Option B - Manual cwv.json (RUM / PageSpeed)](#option-b---manual-cwvjson-rum--pagespeed)

-----

## Prerequisites

- Chrome or Chromium browser (Brave, Edge...) with DevTools available
- Stable network connection (avoid unstable Wi-Fi or slow 4G)
- 15-30 min without interruption
- Journey defined in advance: list of pages and steps to visit
- Known starting URL

-----

## Part 1 - Capture the HAR file

### Step 1 - Pre-cleaning

These steps guarantee a faithful capture of the first load, without cached resources.

**Option A - Global cleaning (recommended):**
1. `Cmd+Shift+Delete` (macOS) or `Ctrl+Shift+Delete` (Windows/Linux)
2. Tick: Cookies, Images and cached files, Form data
3. Select "All time"
4. Click "Delete data"
5. Close Chrome completely then reopen it

**Option B - Targeted cleaning in DevTools:**
1. Open DevTools (`F12` or `Cmd+Option+I`)
2. Go to Application > Storage
3. Click "Clear site data"
4. Reload the page

-----

### Step 2 - Prepare the Network tab

1. Open Chrome (no other window if possible)
2. Press `F12` or `Cmd+Option+I` to open DevTools
3. Go to the **Network** tab
4. Tick **"Preserve log"** - CRUCIAL: without this option, requests are cleared at each navigation
5. In Settings (gear at the top right), tick **"Disable cache"** - forces reloading of all resources

-----

### Step 3 - Perform the journey

**Phase 1 - Initial load:**
1. Type the root URL in the address bar
2. Press `Cmd+R` / `Ctrl+R` to force a full reload
3. Wait 3-5 seconds for the page to stabilize (no more new requests)

**Phase 2 - Trigger lazy-loaded resources:**
1. Scroll slowly from top to bottom over the whole page
2. Interact with the page: buttons, menus, accordions, tabs (without entering sensitive data)
3. Wait 2-3 seconds after each interaction

**Phase 3 - Navigate between the journey pages:**
1. For each step, click the next link or button
2. Wait 3-5 sec for the page to load
3. Repeat scroll + interactions (Phase 2)
4. Continue for all the planned pages

**Phase 4 - Finalization:**
1. Stay on the last page an extra 5-10 seconds
   (gives analytics and beacons time to run)
2. Check that the Network request counter is stable

-----

### Step 4 - Export the HAR

1. Right-click anywhere in the Network request list
2. Select **"Save all as HAR with content"** (or "Export as HAR")
   - The "with content" option includes the full response payloads - necessary for the analysis
3. Name the file: `audit_<site-name>_YYYY-MM-DD.har`
4. Save in the project folder

-----

### Step 5 - Check the HAR file

The `.har` file is standard JSON. Open it in a text editor and check:

- `log.entries` does contain hundreds of objects (one request = one object)
- Several resource types present: HTML, JS, CSS, images, XHR/Fetch requests, fonts
- HTTP headers are complete (`request.headers`, `response.headers`)
- Each entry has its timings (`blocked`, `dns`, `connect`, `send`, `wait`, `receive`)

Expected JSON structure:
```json
{
  "log": {
    "version": "1.2",
    "entries": [
      {
        "startedDateTime": "2026-04-09T10:30:45.123Z",
        "request": { "method": "GET", "url": "...", "headers": [...] },
        "response": { "status": 200, "headers": [...], "content": { "size": ..., "text": "..." } },
        "timings": { "blocked": ..., "dns": ..., "connect": ..., "send": ..., "wait": ..., "receive": ... }
      }
    ]
  }
}
```

**Summary table of critical steps:**

| Step | Action | Why |
|-------|--------|----------|
| 1 - Cleaning | Clear caches and cookies | Faithful capture of the first load |
| 2 - Preserve log | Tick at the start | Accumulates all the journey requests |
| 2 - Disable cache | Tick in Settings | Forces re-downloading of all resources |
| 3 - Full scroll | Slowly, top to bottom | Triggers lazy-loads |
| 3 - Wait | 3-5 sec per page + 5 sec at the end | Gives time to asynchronous requests |
| 4 - "with content" | Export with payloads | Necessary to analyze real sizes |

-----

## Part 2 - Capture the coverage data (Coverage)

Coverage measures which part of the JS and CSS code is actually executed when
a page loads. One JSON file per page.

### Step 1 - Open the Coverage panel

1. In DevTools, press `Cmd+Shift+P` (macOS) or `Ctrl+Shift+P` (Windows/Linux)
2. Type `coverage` and select **"Show Coverage"**
3. The Coverage panel opens at the bottom of DevTools

### Step 2 - Capture a page

1. In the Coverage panel, click the round (record) button to start
2. Reload the page (`Cmd+R` / `Ctrl+R`)
3. Wait for the page to be fully loaded (3-5 seconds)
4. Scroll the whole page to trigger lazy-loads
5. Click the round button again to stop recording

### Step 3 - Export the Coverage file

1. In the Coverage panel, click the download icon (down arrow)
2. Name the file: `Coverage-YYYY-MM-DD_page-N.json`
   - Example: `Coverage-2026-04-09_page-1.json`
3. Save in the project folder

### Step 4 - Repeat for each page

Repeat steps 2-3 for each page of the journey:
- Click the record button
- Navigate to the next page (or reload it)
- Wait + scroll
- Stop + export

**Important:** one JSON file per page. Do not accumulate several pages in a single Coverage file.

### Step 5 - Check the Coverage files

Each file must contain an array of objects with at least:

```json
[
  {
    "url": "https://example.com/app.js",
    "ranges": [
      { "start": 0, "end": 1234 }
    ],
    "text": "/* content of the JS or CSS file */"
  }
]
```

- `url`: URL of the JS or CSS resource
- `ranges`: code ranges actually executed/used
- `text`: full source content (allows computing the total size)

The unused code rate is computed as follows:
```
unused = length(text) - sum(range.end - range.start)
rate (%) = unused / length(text) * 100
```

-----

## Part 3 - Core Web Vitals

The Core Web Vitals (LCP, INP, CLS) are not in the HAR.

**Automatic:** `/analyse-parcours` launches Lighthouse via `npx` automatically if `cwv.json`
is absent. Prerequisite: Node.js installed (`node -v` must answer). Public pages only
(headless Chrome, no authentication).

To force a re-run: tell Claude "re-run Lighthouse".

**Real field data (optional):** if you have RUM or PageSpeed Insights data,
create `cwv.json` manually in the audit folder. The skill detects the file and skips
Lighthouse.

Format:
```json
[
  {"page": "page_1", "lcp": 0.76, "inp": 8,  "cls": 0.06},
  {"page": "page_2", "lcp": 1.9,  "inp": 16, "cls": 0.66}
]
```
- `page`: HAR ID (`page_1`, `page_2`...)
- `lcp`: seconds, `inp`: milliseconds, `cls`: unitless
