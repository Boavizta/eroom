# Retrieving SimilarWeb via the internal API - Agent EROOM

This document explains how the project retrieves the traffic and the country audience mix
of a site, without going through the SimilarWeb website (blocked by captcha).

-----

## Goal

Two data points are provided by no public API (neither PageSpeed, nor CrUX):

- the **traffic volume** (visits per month / per year);
- the **country audience mix** (distribution of visitors by country).

SimilarWeb estimates them. The public web page `https://www.similarweb.com/website/<domain>/`
is protected by an image-selection captcha (AWS WAF challenge), which blocks any automated
access. We therefore retrieve this data another way.

-----

## Chosen method

The `similarweb_api.py` script calls the **internal API of the SimilarWeb Chrome/Firefox
extension** directly, imitating the requests the extension makes in the background. We no
longer scrape the web page: we replay the API call in Python.

- Endpoint: `https://data.similarweb.com/api/v1/data?domain=<domain>` (GET)
- Sufficient headers (dict of `fetch_domain_data()`):
  - `Content-Type: application/json`
  - `X-Extension-Version: 6.12.21` (extension version, cf. constant `EXTENSION_VERSION`)
  - a real browser `User-Agent` (constant `BROWSER_USER_AGENT`)
  - `Accept: */*`
  - NO `Origin` header (see the 403 diagnostic below)

Important point: **no cookie, no account, no session** is needed. The API answers directly
in JSON, from which we extract `TopCountryShares` (country mix), `EstimatedMonthlyVisits`
and `Engagments` (visits).

-----

## 403 diagnostic (historical pitfall)

A first investigation wrongly concluded that session cookies were needed: the API returned a
403. In reality, the 403 came from two errors in the test request, not from a lack of
authentication:

1. An `Origin: chrome-extension://...` header: CloudFront rejects it. **Do not send it.**
2. The absence of a real browser `User-Agent` (the default User-Agent of an HTTP client is
   blocked). **Always send a browser User-Agent.**

Without an `Origin` header and with a browser User-Agent, the call answers 200 from a plain
HTTP client.

-----

## How this module was built (via HAR)

The module was not guessed: it was built by **observing the SimilarWeb extension in operation**,
capturing its network call (HAR export), then replaying that request in Python. Being in
Manifest V3, the call goes out from its **service worker**: we capture it via
`chrome://extensions` (developer mode > "service worker" > Network), not in the Network tab of
the site. It was the HAR that revealed the URL, the headers (including the absence of
`Origin`) and the shape of the JSON response, from which the parsed fields are taken
(`TopCountryShares`, `EstimatedMonthlyVisits`, `Engagments`).

Detailed genesis story + step-by-step capture procedure: see
`similarweb-reconstruction.md` (Method B - HAR capture).

-----

## Usage

The call is **integrated into `collect_env_data.py`**: a single command suffices. When an
`audience` or `traffic` block is missing in `env-data.json`, the script itself queries the
internal SimilarWeb API (via the sibling module `similarweb_api.py`), writes the missing
blocks, then normalizes and integrates them into the CO2e calculation.

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"

# One command: HAR/CrUX/ipinfo collection + automatic SimilarWeb call if audience/traffic are missing
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py <source_dir> --refresh
```

Associated options (on `collect_env_data.py`):

- `--sw-domain octo.com` : force the queried domain. Otherwise deduced from `env-data.json` (or the `.har`).
- `--no-similarweb` : disable the automatic call (offline mode / avoid the network).
- `--audience "FR:0.7,US:0.3"` : manual entry of the country mix ; **takes precedence** over
  SimilarWeb (the API then does not write the mix, but can still complete the traffic).

Triggering and guardrails:

- The call only happens if the targeted block is **missing** (absent, or `source` = `default`/`None`).
- A block already present with a real source is **never overwritten** (idempotent on `--refresh`).
- The call only writes the missing `audience`/`traffic` blocks ; it touches nothing else in
  `env-data.json` (HAR, device, server preserved).

The `similarweb_api.py` module remains usable **standalone** for inspection:

```bash
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/similarweb_api.py <source_dir> [--domain octo.com] [--print-only]
```

- `--domain octo.com` : force the domain. Otherwise deduced from `env-data.json` (or the `.har`).
- `--print-only` : displays the raw JSON returned by the API and writes nothing (useful for inspection).

-----

## Fallback if the API fails

If the call fails (403 back, domain little/not tracked by SimilarWeb, network cut),
`collect_env_data.py` displays a `⚠ SimilarWeb : …` message then **continues without crashing**:
it does not write the block concerned and proceeds with the available blocks or the defaults.

Note: the API answers 200 even for an unknown domain (it echoes the name back), but without
`TopCountryShares` nor exploitable visits → the blocks are not built, with an explicit message
(no silent fallback). Standalone, `similarweb_api.py` exits with code `2` in this case.

In this case, switch to **assisted retrieval** (efootprint skill, Step 20d): the agent asks the
user to open the SimilarWeb page, pass the captcha and transmit the figures (dictation or
screenshot).

-----

## Label and verification in the report

- The report displays the source under the neutral label **"SimilarWeb (estimate)"**: it does
  not expose the technical method (internal API). The technical description stays in this doc
  and the code.
- The report provides a "↗ source" verification link to the **human-readable web page**
  `https://www.similarweb.com/website/<domain>/`, so the reader can check the figures
  themselves. It is never the API URL (which returns unreadable JSON).

-----

## Caveats and robustness

- SimilarWeb is a **third-party estimate with a wide margin**, an unofficial source, whose
  automated use is at the limit of the ToS. Only the site's analytics (GA4, Matomo, server
  logs) give exact figures ; they are prioritized (`--audience` / `--visits`).
- Source priority order: client analytics (`--audience`/`--visits`) > internal SimilarWeb API
  (automatic) > assisted retrieval after captcha (Step 20d) > defaults (France 100 %,
  100,000 visits/year). The WebFetch route of the public page was removed (systematically
  blocked by the captcha, made useless by the internal API).
- If the API goes back to returning 403: check the absence of an `Origin` header, the presence
  of a browser User-Agent, and revalidate the `EXTENSION_VERSION` value (install/update the
  extension, read the current version in `chrome://extensions`).
- If a simple version revalidation is not enough (endpoint or headers changed), redo the
  discovery from zero: see the reconstruction guide `similarweb-reconstruction.md`
  (extension retrieval, endpoint/headers/version extraction, verification).
