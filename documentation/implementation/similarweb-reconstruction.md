-----
Reconstruction guide for the internal SimilarWeb API
-----

This guide explains how to REDO the discovery of the SimilarWeb extension's internal API call,
if the extension ever changes (new endpoint, new header, new version triggering a 403). The
method described here is the one that was actually replayed and verified on 29/07/2026, not a
theoretical procedure.

The module concerned is `.claude/skills/analyse-parcours/scripts/similarweb_api.py`.


-----
1. When to use this guide
-----

The current call works without an account or cookie: it only takes a real browser User-Agent,
the `X-Extension-Version` header, and NOT sending an `Origin` header (CloudFront rejects it
with a 403).

Symptoms that justify a reconstruction:

- persistent 403 while the absence of `Origin` and a browser User-Agent are already in place
  (hence not the "classic" 403 documented in similarweb_api.md).
- The call answers 200 but the expected fields are absent: `TopCountryShares`
  (country mix) or `EstimatedMonthlyVisits` (traffic).

In these cases, the extension has probably changed its endpoint, headers or version. Simple
version revalidation (see similarweb_api.md) is no longer enough: the extension must be
re-inspected.


-----
2. Known facts (starting point)
-----

Values read and verified on 29/07/2026:

- Extension ID (Chrome Web Store): `hoklmmgfnpapgjgcpechhaamimifchmp`
- Installed version: `6.12.21` (manifest V3)
- Endpoint: `https://data.similarweb.com/api/v1/data`
- HTTP headers sent by the extension: `Content-Type: application/json`,
  `X-Extension-Version: <version>`, `Accept: */*`, plus a real browser
  `User-Agent`. NO `Origin` header.
- `redirect: follow` is NOT an HTTP header: it is a `fetch()` option of the
  extension's JS. Python-side (`urllib`), redirects are followed by default, so
  there is nothing to report in the headers dict for this point.
- File carrying the endpoint: `background/background.js` (the endpoint also
  appears in options/popup/panel/content, but the real call goes out from the background).

These values live in the constants of `similarweb_api.py`:
`DATA_API` (= `https://data.similarweb.com/api/v1/data`), `EXTENSION_VERSION`,
`BROWSER_USER_AGENT`, and the headers dict of `fetch_domain_data()`
(`Content-Type`, `X-Extension-Version`, `User-Agent`, `Accept`).


-----
3. Method A - Retrieve and inspect the extension
-----

Goal: find the endpoint, the headers and the version in the extension's code. Three ways to
get the files, from simplest to heaviest. Way 1 is the one that worked this session.

Way 1 (recommended, no third party, no network): read the already installed extension
-----

Chrome unpacks installed extensions on disk. Locate the folder:

    ls -d ~/Library/Application\ Support/Google/Chrome/*/Extensions/hoklmmgfnpapgjgcpechhaamimifchmp/*/

The profile can be `Default`, `Profile 1`, `Profile 5`, etc. ; the final subfolder is the
version (e.g. `6.12.21_0`). This session, the real path was:

    ~/Library/Application Support/Google/Chrome/Profile 5/Extensions/hoklmmgfnpapgjgcpechhaamimifchmp/6.12.21_0/

If the extension is not installed: install it from the Chrome Web Store (page
`https://chrome.google.com/webstore/detail/hoklmmgfnpapgjgcpechhaamimifchmp`),
enable it once on a site, then re-read the folder above.

Way 2 (without installing): download the `.crx`
-----

Download the package via Google's update service:

    https://clients2.google.com/service/update2/crx?response=redirect&prodversion=120&acceptformat=crx2,crx3&x=id%3Dhoklmmgfnpapgjgcpechhaamimifchmp%26uc

(adjust `prodversion` if needed). Or go through a service like CRX Extractor.
A `.crx` is a ZIP prefixed with a small binary header ; `unzip` is enough:

    unzip file.crx -d tmp/similarweb-ext/

(ignore the warning about stray bytes at the start of the archive).

Then, in the obtained folder (way 1 or 2)
-----

Read the version:

    grep '"version"' manifest.json

Find the endpoint (unique strings):

    grep -rhoE "data\.similarweb\.com[a-zA-Z0-9/._?=&-]*" . | sort -u

Expected: `data.similarweb.com/api/v1/data` (the country mix and the traffic come from this
endpoint). We also see `data.similarweb.com/api/v1/identity`,
`rank.similarweb.com/api/v1/global` and a `config.json` on S3, not used here.

Identify the carrier file(s):

    grep -rlniE "data\.similarweb\.com|api/v1/data" .

Expected: `background/background.js` (+ options/popup/panel/content).

Find the headers around the fetch:

    grep -oE ".{60}X-Extension-Version.{120}" background/background.js

This session, the obtained extract was:

    ...{headers:{"Content-Type":"application/json","X-Extension-Version":n},redirect:"follow"}...

This confirms: json Content-Type, X-Extension-Version in the headers ; `redirect:"follow"`
is a `fetch()` option (not a header) ; and above all NO Origin header. The equivalent Python
dict (`similarweb_api.py`, `fetch_domain_data()`) additionally adds `Accept: */*` and a
browser `User-Agent`, both needed on a non-browser HTTP client.


-----
4. Method B - HAR capture (cross-verification)
-----

To use if the JS is too minified to read, or to confirm what the extension really sends on the
network.

Module genesis (this is how it was built)
-----

The `similarweb_api.py` module was not guessed: it was built via this HAR path. The principle:
the public SimilarWeb web page is blocked by captcha, but the extension gets the figures,
because it calls an internal API without an account. The method therefore consisted in
OBSERVING the call the extension makes in operation, then REPLAYING it in Python.

- The extension is in Manifest V3: its network call goes out from the SERVICE WORKER
  (`background/background.js`), not from the visited page. It therefore does not appear in
  the page's Network tab ; the extension's service worker must be inspected via
  `chrome://extensions` (developer mode). We trigger the extension on a site while this
  service worker records the network.
- The HAR capture (procedure below) revealed three things reported as-is in the code: the
  URL (`/api/v1/data?domain=...`), the headers to send (including the absence of
  `Origin`), and above all the SHAPE of the JSON response.
- The fields read in this response are exactly those the module parses:
  `SiteName` (validity), `TopCountryShares` (`CountryCode` + `Value`, the country mix),
  `EstimatedMonthlyVisits` (dict dated `YYYY-MM-01`) and `Engagments`
  (`Visits`/`Month`/`Year`, the traffic). See `fetch_domain_data()`,
  `build_audience_block()` and `build_traffic_block()` in `similarweb_api.py`:
  these functions are the direct trace of what the HAR showed.
- Honesty note: the original session (July 2026) was not logged. This genesis is
  reconstructed from the code (which bears its trace) and from the 29/07/2026 re-verification,
  it is not a step-by-step journal from that time.

Capture procedure
-----

Key point (MV3): the call goes out from the extension's service worker, so we capture the
network OF the service worker, not that of the site tab. Concretely:

1. Tab A: open the site to analyze (or the page where the extension triggers).
2. Tab B: open `chrome://extensions` and enable "Developer mode"
   (toggle at the top right).
3. On the SimilarWeb extension card, click the "service worker" link
   (sometimes "inspect views: service worker"): this opens the DevTools OF
   the service worker.
4. In these DevTools, Network tab: tick "Preserve log"
   (keep the log) so as not to lose the requests, and leave recording active.
5. Go back to tab A and trigger the extension (click its icon / open its panel on the site).
   The `data.similarweb.com/api/v1/data` call then goes out from the service worker.
6. Go back into the service worker's DevTools (`chrome://extensions`): the
   `data.similarweb.com` request appears in the Network.
7. Export as HAR (right-click in the list > "Save all as HAR", or the export /
   download icon of the Network panel) and read the entry:
   - exact URL (must end with `/api/v1/data?domain=...`).
   - Request Headers: `X-Extension-Version`, `User-Agent` (real browser),
     presence or absence of `Origin`.
   - Response JSON: fields `TopCountryShares`, `EstimatedMonthlyVisits`,
     `Engagments`.


-----
5. Report into the code and re-verify
-----

If a value changed, update it in `similarweb_api.py`:
`DATA_API`, `EXTENSION_VERSION`, `BROWSER_USER_AGENT`, and the headers dict of
`fetch_domain_data()`.

Direct verification (writes no file), the one used this session:

    cd .claude/skills/analyse-parcours/scripts
    ../../../../.venv/bin/python3 -c "import similarweb_api as s; d,e=s.fetch_domain_data('octo.com'); print(e or ('OK', 'EstimatedMonthlyVisits' in d, len(d.get('TopCountryShares') or [])))"

Expected result: `('OK', True, 5)` (200, traffic present, 5 countries in the mix).

Alternative on an existing folder:

    ../../../../.venv/bin/python3 similarweb_api.py <folder_with_env-data> --print-only


-----
6. Honesty note and final verification
-----

This guide documents the method actually replayed and verified, not the exact recipe of
July 2026 (it was not logged). A future maintainer must therefore look at the date below to
judge freshness.

- Last verified re-discovery: 29/07/2026.
- Extension version read: 6.12.21.
- Control call: `octo.com` -> 200 OK, `EstimatedMonthlyVisits` present,
  `TopCountryShares` = 5 countries.

ToS reminder: SimilarWeb is a third-party estimate, an unofficial source, whose automated use
is at the limit of the terms of use. The site's analytics (GA4, Matomo, server logs) remain
the priority when available.
