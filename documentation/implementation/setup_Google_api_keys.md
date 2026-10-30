# Provisioning API keys - Agent EROOM

This document explains how to obtain the necessary API keys.

**Each person taking over the project creates their own key, in their own personal Google
account.** Nothing is shared: `.env` is local to each machine and never versioned (see the
Security section). This is therefore not about asking for access to the existing GCP project
of whoever worked on it before, but about redoing the steps below from scratch, with your own
account.

-----

## Security - absolute rule

API keys are private information. Never share them nor commit them into git.

They go only into the `.env` file at the project root:

```
/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM/.env
```

This file is in `.gitignore`: it will never be versioned. Never copy a key into a `.md`, a
script, or any other versioned file.

-----

## .env file format

```
GOOGLE_API_KEY=your_key_here
IPINFO_TOKEN=your_token_here   # optional: see the IPInfo section
```

The scripts do not load `.env` via `python-dotenv`: they parse it themselves (function
`load_env` in `collect_env_data.py`, line-by-line `key=value` reading).

-----

## Google API Key (PageSpeed Insights + Chrome UX Report)

**Cost**: free (quotas largely sufficient for occasional use)
**Used for**: real field Core Web Vitals (LCP, INP, CLS) via PageSpeed Insights + CrUX

**One key, two APIs, two scripts**: the same `GOOGLE_API_KEY` serves two distinct scripts.
- `collect_cwv_pagespeed.py` calls the **PageSpeed Insights API**
  (`pagespeedonline/v5/runPagespeed`).
  The CrUX data it exploits is extracted from the PageSpeed response, it does not query
  the Chrome UX Report API directly.
- `collect_env_data.py` calls the **Chrome UX Report API** (`chromeuxreport.googleapis.com`)
  in addition to its HAR / ipinfo collection.

Both APIs must therefore be enabled (see Step 1), but they are not called by the same script.

### GCP project to create

Suggested project name: **"Google API Key for Agent EROOM"** (or any other name, it is a
personal project, the name is not structuring). Suggested key name: **"GOOGLE API KEY for
Agent EROOM"**.

### ⚠️ Frequent pitfall — wrong Google account signed in

If you use Chrome/a browser with several Google accounts (personal + work/organization), the
console may open on your **professional** account by default. Observed symptoms:
- the project selector ("No organization" / organization name) only shows unrelated business
  projects;
- clicking "Enable" triggers "We tried to create a project... you do not have the necessary
  permissions to create a project in this organization";
- on an existing organization project, the API page shows "You do not have the necessary
  permissions to check the activation status of this product."

**Switching Chrome profile is not necessarily enough** (the profile can stay signed in to the
same Google account). The solution that works: click the avatar at the top right of
`console.cloud.google.com` → explicitly choose your **personal Google account** (or open a
private browsing window and sign in with that account). Once on the right account, the project
selector must offer creating a new personal project without an organization block.

### Step 1 — Enable the two APIs (BEFORE creating the key)

1. Go to https://console.cloud.google.com, signed in with your **personal** Google account
   (see the pitfall above if the right account does not show up)
2. Create a new project (or select the one already created for this need)
3. Left menu: "APIs & Services" → "Library"
4. Search **"PageSpeed Insights API"** → Enable
5. Back to the library, search **"Chrome UX Report API"** → Enable

### Step 2 — Create the key

6. Left menu: "APIs & Services" → "Credentials"
7. Click "+ Create credentials" → "API key"
8. Name the key: `GOOGLE API KEY for Agent EROOM` (or any other name, free choice)
9. In "APIs accessible with this key": click "Select API restrictions"
   - Type "PageSpeed" in the filter → tick **"PageSpeed Insights API"**
   - Clear, type "Chrome UX" → tick **"Chrome UX Report API"**
   - Click OK
10. Click **"Create"**
11. Copy the key shown in the pop-up → paste it into `.env`

### Free quotas

- PageSpeed Insights API: 25,000 requests/day
- Chrome UX Report API: 150 requests/minute, no daily limit

### Check that the key works

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_cwv_pagespeed.py audits/octo.com/audit --check
```

-----

## IPInfo Token (IP geolocation) — implemented, optional

**Cost**: free up to 50,000 requests/month (https://ipinfo.io)
**Used for**: detecting the country and the hosting provider from the server IP.
The country feeds the electricity mix, hence the carbon intensity of the CO2e calculation; the
provider makes the Boavizta instance choice more reliable.

This feature is **active in production**, not pending: `collect_env_data.py` calls ipinfo.io
on each run (step "[3/3] Server geolocation (ipinfo.io)", functions `call_ipinfo` /
`collect_server_info`).

The token is **optional**: if absent, the script switches to **anonymous mode** (reduced quota,
50,000 req/month shared by public IP) and still works, without crashing.
Providing it in `.env` (`IPINFO_TOKEN=your_token_here`) unlocks the account's nameinal quota.

### Check the Google key AND the ipinfo token at once

```bash
cd "/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"
.venv/bin/python3 .claude/skills/analyse-parcours/scripts/collect_env_data.py audits/octo.com --check
```

`--check` tests both CrUX access (Google key) and ipinfo (token).
