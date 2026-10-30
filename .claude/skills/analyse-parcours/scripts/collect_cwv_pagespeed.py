#!/usr/bin/env python3
"""
Collects Core Web Vitals via the PageSpeed Insights API (Google).
Preferred source: CrUX field data (real-user P75).
Fallback if CrUX is absent: Lighthouse lab data returned by the same API.

Usage:
    python3 collect_cwv_pagespeed.py <audit-folder>                    # mobile + desktop (default)
    python3 collect_cwv_pagespeed.py <audit-folder> --strategy mobile  # mobile only
    python3 collect_cwv_pagespeed.py <audit-folder> --urls https://example.com https://example.com/page2

By default (--strategy both), collects mobile AND desktop for each URL and
keeps them side by side in cwv.json (one entry per url/strategy pair).

Reads GOOGLE_API_KEY from .env at the project root.
Writes (or updates) <audit-folder>/cwv.json.

Output format:
    [
      {"page": "page_1", "url": "https://...", "lcp": 2.5, "inp": 200, "cls": 0.1,
       "source": "crux", "strategy": "mobile", "crux_category": "NEEDS_IMPROVEMENT",
       "accessibility_score_pct": 96, "best_practices_score_pct": 92},
      ...
    ]

accessibility_score_pct / best_practices_score_pct: Lighthouse scores (same
API calls, additional categories requested in the same request — no extra
network call) — absent (key omitted) if the API does not return them for this
page.

Possible sources:
    "crux"          - CrUX field data P75 (recommended — real users)
    "pagespeed_lab" - Lighthouse lab data via API (CrUX unavailable for this URL)
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"  # genericity: ok - official PageSpeed Insights API URL (Google)

# Optional subfolder where raw captures (HAR, Coverage) are stored, in .gitignore.
RAW_DATA_DIR = "raw-data-potentially-sensitive"  # genericity: ok - constant declaration

# Official CWV thresholds (Google)
LCP_GOOD = 2.5    # s
LCP_POOR = 4.0
INP_GOOD = 200    # ms
INP_POOR = 500
CLS_GOOD = 0.1
CLS_POOR = 0.25

# Lighthouse Insights audits relevant to ecodesign.
# Structure tolerant to versions: each logical entry accepts several audit
# alias names (new and old), and the extractor keeps the first one present in
# the response. The `-insight` names are recent (Lighthouse 12+); the older
# ones existed before and may reappear in future versions or other services.
# No crash, no invented value if no alias is present.
INSIGHT_AUDIT_KEYS = [
    {
        "logical_name": "duplicated-javascript",
        "aliases": ["duplicated-javascript-insight", "duplicated-javascript"],
        "description": "EOF criterion 6.8 (JS bundle duplication)"
    },
    {
        "logical_name": "unused-javascript",
        "aliases": ["unused-javascript"],
        "description": "Dead JS code (weight optimization)"
    },
    {
        "logical_name": "render-blocking",
        "aliases": ["render-blocking-insight", "render-blocking-resources"],
        "description": "Render-blocking resources"
    },
    {
        "logical_name": "total-byte-weight",
        "aliases": ["total-byte-weight"],
        "description": "Total network weight"
    },
    {
        "logical_name": "dom-size",
        "aliases": ["dom-size-insight", "dom-size"],
        "description": "DOM size"
    },
    {
        "logical_name": "bootup-time",
        "aliases": ["bootup-time"],
        "description": "JS execution time"
    },
    {
        "logical_name": "mainthread-work-breakdown",
        "aliases": ["mainthread-work-breakdown"],
        "description": "Main-thread load"
    },
    {
        "logical_name": "third-parties",
        "aliases": ["third-parties-insight", "third-party-summary"],
        "description": "Third-party dependencies"
    },
    {
        "logical_name": "cache",
        "aliases": ["cache-insight", "uses-long-cache-ttl"],
        "description": "Cache lifetime"
    },
    {
        "logical_name": "font-display",
        "aliases": ["font-display-insight", "font-display"],
        "description": "Font display"
    },
    {
        "logical_name": "image-size-responsive",
        "aliases": ["image-size-responsive", "uses-responsive-images"],
        "description": "Image resolution"
    },
]


def load_env(project_root):
    """Reads GOOGLE_API_KEY from .env."""
    env_path = project_root / ".env"
    if not env_path.exists():
        return None
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def extract_urls_from_har(har_path):
    """Extracts the page URLs from a HAR. Returns [(page_id, url), ...]."""
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)
    pages = har.get("log", {}).get("pages", [])
    result = []
    seen = set()
    for i, page in enumerate(pages):
        url = page.get("title", "")
        if url and url.startswith("http") and url not in seen:
            result.append((f"page_{i + 1}", url))
            seen.add(url)
    return result


def find_har(audit_dir):
    """Finds the .har in the source folder (parent of audit/)."""
    source_dir = audit_dir.parent
    hars = list(source_dir.glob("*.har"))
    if not hars:
        # Also look inside audit_dir itself
        hars = list(audit_dir.glob("*.har"))
    if not hars:
        # Then in the raw-captures subfolder, on both sides
        hars = (list((source_dir / RAW_DATA_DIR).glob("*.har"))
                or list((audit_dir / RAW_DATA_DIR).glob("*.har")))
    if len(hars) == 1:
        return hars[0]
    if len(hars) > 1:
        print(f"[PageSpeed] Several .har found: {[h.name for h in hars]}")
        print(f"[PageSpeed] Using: {hars[0].name}")
    return hars[0] if hars else None


def call_pagespeed(url, api_key, strategy="mobile"):
    """Calls the PageSpeed Insights API.

    Returns a dict distinguishing failure cases:
    - success: {"ok": True, "data": json_data, "error_type": None, "message": None}
    - HTTPError: {"ok": False, "data": None, "error_type": "http", "http_code": int, "message": str}
    - timeout: {"ok": False, "data": None, "error_type": "timeout", "message": str}
    - other network: {"ok": False, "data": None, "error_type": "network", "message": str}
    """
    params = {
        "url": url,
        "key": api_key,
        "strategy": strategy,
        "category": ["performance", "accessibility", "best-practices"],
    }
    full_url = PAGESPEED_API + "?" + urllib.parse.urlencode(params, doseq=True)
    try:
        req = urllib.request.urlopen(full_url, timeout=30)
        data = json.loads(req.read().decode("utf-8"))
        return {"ok": True, "data": data, "error_type": None, "message": None}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body).get("error", {})
            message = err.get("message", body[:200])
            print(f"  [PageSpeed] HTTP error {e.code} for {url} : {message}")
        except Exception:
            message = f"HTTP {e.code}"
            print(f"  [PageSpeed] HTTP error {e.code} for {url}")
        return {"ok": False, "data": None, "error_type": "http", "http_code": e.code, "message": message}
    except urllib.error.URLError as e:
        if "timed out" in str(e.reason).lower() or "timeout" in str(e.reason).lower():
            message = f"Timeout after 30s"
            print(f"  [PageSpeed] Timeout for {url}")
            return {"ok": False, "data": None, "error_type": "timeout", "message": message}
        else:
            message = str(e.reason)
            print(f"  [PageSpeed] Network error for {url} : {message}")
            return {"ok": False, "data": None, "error_type": "network", "message": message}
    except Exception as e:
        message = str(e)
        print(f"  [PageSpeed] Network error for {url} : {message}")
        return {"ok": False, "data": None, "error_type": "network", "message": message}


def extract_crux(data):
    """Extracts the CrUX (field) metrics from the PageSpeed response."""
    le = data.get("loadingExperience", {})
    metrics = le.get("metrics", {})
    if not metrics:
        return None

    def get_p75(key, divisor=1):
        m = metrics.get(key, {})
        p = m.get("percentile")
        return round(p / divisor, 3) if p is not None else None

    lcp = get_p75("LARGEST_CONTENTFUL_PAINT_MS", divisor=1000)
    inp = get_p75("INTERACTION_TO_NEXT_PAINT")
    cls = get_p75("CUMULATIVE_LAYOUT_SHIFT_SCORE", divisor=100)

    if lcp is None and inp is None and cls is None:
        return None

    return {
        "source": "crux",
        "crux_category": le.get("overall_category", ""),
        "lcp": lcp,
        "inp": inp,
        "cls": cls,
    }


def extract_lab(data):
    """Extracts the Lighthouse lab metrics from the PageSpeed response (fallback)."""
    audits = data.get("lighthouseResult", {}).get("audits", {})

    def numeric(key):
        a = audits.get(key, {})
        v = a.get("numericValue")
        return v if v is not None else None

    lcp_ms = numeric("largest-contentful-paint")
    inp_ms = numeric("interaction-to-next-paint")
    cls_raw = numeric("cumulative-layout-shift")

    lcp = round(lcp_ms / 1000, 3) if lcp_ms is not None else None
    inp = round(inp_ms, 0) if inp_ms is not None else None
    cls = round(cls_raw, 3) if cls_raw is not None else None

    if lcp is None and inp is None and cls is None:
        return None

    return {
        "source": "pagespeed_lab",
        "lcp": lcp,
        "inp": inp,
        "cls": cls,
    }


def extract_lighthouse_scores(data):
    """Extracts the Lighthouse accessibility / best-practices scores (0-100),
    present in the same API response whatever the CWV source (crux/lab) is.
    Returns {} if absent (never an invented value)."""
    categories = data.get("lighthouseResult", {}).get("categories", {})
    out = {}
    a11y = categories.get("accessibility", {}).get("score")
    if a11y is not None:
        out["accessibility_score_pct"] = round(a11y * 100)
    bp = categories.get("best-practices", {}).get("score")
    if bp is not None:
        out["best_practices_score_pct"] = round(bp * 100)
    return out


def extract_insight_scores(data):
    """Extracts the Lighthouse Insights audits relevant to ecodesign.

    These audits are present in the same API response as the CWVs (same
    network call, no extra cost). Their presence depends on the Lighthouse
    version and on the analyzed page content.

    Returns a dict with one entry per audit found, indexed by logical_name:
        {
          "logical_name": {
            "score": 0-1 or None,
            "numericValue": float or None,
            "itemCount": int,
            "found_as": "actual_audit_key"
          },
          ...
        }

    Returns {} if no audit is available (never an invented value).
    """
    audits = data.get("lighthouseResult", {}).get("audits", {})
    if not audits:
        return {}

    out = {}
    for entry in INSIGHT_AUDIT_KEYS:
        logical_name = entry["logical_name"]
        aliases = entry["aliases"]

        # Keep the first alias present in the response
        found_key = None
        audit = None
        for alias in aliases:
            if alias in audits:
                found_key = alias
                audit = audits[alias]
                break

        if not audit:
            continue

        score = audit.get("score")
        numeric = audit.get("numericValue")
        items = audit.get("details", {}).get("items", [])
        item_count = len(items) if isinstance(items, list) else 0

        out[logical_name] = {
            "score": score,
            "numericValue": numeric,
            "itemCount": item_count,
            "found_as": found_key,
        }

    return out


def collect(audit_dir, urls, api_key, strategies=("mobile",)):
    """Collects the CWVs for each URL and each strategy.

    Returns the list in cwv.json format: one entry per (url, strategy) pair.
    Each entry carries a `measurement` block distinguishing success / failure per
    the measurement-state convention. Pages whose measurement failed ARE PRESENT
    in the result (with status != "ok"), to trace the failure in a structured way.
    """
    results = []
    for page_id, url in urls:
        print(f"  [{page_id}] {url}")
        for strategy in strategies:
            result = call_pagespeed(url, api_key, strategy)

            # Base entry, always present
            entry = {"page": page_id, "url": url, "strategy": strategy}

            if not result["ok"]:
                # API call failure: trace as network_error
                entry["measurement"] = {
                    "status": "network_error",
                    "target": f"{url} (strategy={strategy})",
                    "detail": f"{result['error_type']}: {result['message']}"
                }
                if result["error_type"] == "http":
                    entry["measurement"]["detail"] = f"HTTP {result['http_code']}: {result['message']}"
                results.append(entry)
                print(f"    [{strategy}] -> Network failure ({result['error_type']}), traced.")
                time.sleep(0.5)
                continue

            data = result["data"]
            crux = extract_crux(data)
            if crux:
                entry.update(crux)
                entry["measurement"] = {
                    "status": "ok",
                    "target": f"{url} (strategy={strategy})",
                    "detail": None
                }
                print(f"    [{strategy}] -> CrUX field data: LCP={entry.get('lcp')}s INP={entry.get('inp')}ms CLS={entry.get('cls')} [{entry.get('crux_category')}]")
            else:
                lab = extract_lab(data)
                if lab:
                    entry.update(lab)
                    entry["measurement"] = {
                        "status": "ok",
                        "target": f"{url} (strategy={strategy})",
                        "detail": None
                    }
                    print(f"    [{strategy}] -> Lab (CrUX absent): LCP={entry.get('lcp')}s INP={entry.get('inp')}ms CLS={entry.get('cls')}")
                else:
                    # API answers 200 but no CrUX or lab metric available
                    # This is a valid audit result: the API has no data for this URL
                    entry["measurement"] = {
                        "status": "not_found",
                        "target": f"{url} (strategy={strategy})",
                        "detail": "The PageSpeed API has no CrUX or lab data for this URL"
                    }
                    results.append(entry)
                    print(f"    [{strategy}] -> No metric available (not_found), traced.")
                    time.sleep(0.5)
                    continue

            lh_scores = extract_lighthouse_scores(data)
            if lh_scores:
                entry.update(lh_scores)
                print(f"    [{strategy}] -> Lighthouse a11y={lh_scores.get('accessibility_score_pct', '?')} "
                      f"best-practices={lh_scores.get('best_practices_score_pct', '?')}")

            insights = extract_insight_scores(data)
            if insights:
                entry["lighthouse_insights"] = insights
                print(f"    [{strategy}] -> {len(insights)} insight audit(s) available")

            results.append(entry)
            time.sleep(0.5)  # Avoid exceeding the per-minute quota

    return results


def merge_with_existing(new_entries, existing_path):
    """Merges with an existing cwv.json.

    The new entries replace the old ones per (URL, strategy) pair,
    in order to keep mobile AND desktop side by side for the same page (a
    desktop pass no longer overwrites the mobile one). Historical entries
    without a `strategy` field are considered mobile (old default).
    """
    if not existing_path.exists():
        return new_entries

    with open(existing_path, encoding="utf-8") as f:
        existing = json.load(f)

    def norm(u):
        return u.rstrip("/") if u else u

    def key(e):
        return (norm(e.get("url", "")), e.get("strategy", "mobile"))

    new_keys = {key(e) for e in new_entries if "url" in e}
    kept = [e for e in existing if key(e) not in new_keys]
    merged = kept + new_entries
    merged.sort(key=lambda e: (e.get("page", ""), e.get("strategy", "")))
    return merged


def fallback_lighthouse(audit_dir, urls):
    """Runs run_lighthouse.sh as a fallback if PageSpeed fails. Returns True on success."""
    script = Path(__file__).parent / "run_lighthouse.sh"
    if not script.exists():
        print("[Fallback] run_lighthouse.sh not found, fallback impossible.")
        return False

    print("\n[Fallback] Launching Lighthouse as a backup source...")
    url_args = [u for _, u in urls]
    cmd = ["bash", str(script), str(audit_dir)] + url_args
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("[Fallback] cwv.json generated by Lighthouse.")
        return True
    else:
        print("[Fallback] Lighthouse also failed.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Collects CWVs via the PageSpeed Insights API")
    parser.add_argument("audit_dir", help="Audit folder (contains cwv.json or parent of the .har)")
    parser.add_argument("--strategy", default="both", choices=["mobile", "desktop", "both"],
                        help="PageSpeed strategy: mobile, desktop or both (default: both)")
    parser.add_argument("--urls", nargs="+", help="Explicit URLs (optional, otherwise read from the .har)")
    parser.add_argument("--check", action="store_true", help="Checks the API key without analyzing")
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir).resolve()
    if not audit_dir.exists():
        print(f"Error: folder not found: {audit_dir}")
        sys.exit(1)

    # Find the project root (walk up until .env or .git is found)
    project_root = audit_dir
    for _ in range(6):
        if (project_root / ".env").exists() or (project_root / ".git").exists():
            break
        project_root = project_root.parent

    api_key = load_env(project_root)
    if not api_key:
        print("[PageSpeed] GOOGLE_API_KEY not found — Lighthouse fallback.")
        print(f"(To enable PageSpeed: create .env in {project_root} with GOOGLE_API_KEY=...)")
        if args.urls:
            urls = [(f"page_{i + 1}", u) for i, u in enumerate(args.urls)]
        else:
            har = find_har(audit_dir)
            urls = extract_urls_from_har(har) if har else []
        fallback_lighthouse(audit_dir, urls)
        sys.exit(0)

    if args.check:
        # Quick test on a simple URL
        print("[PageSpeed] Checking API key...")
        result = call_pagespeed("https://www.google.com", api_key, "mobile")  # genericity: ok - neutral URL to test the API key
        if result["ok"] and result["data"] and "lighthouseResult" in result["data"]:
            print("[PageSpeed] API key valid.")
        else:
            print("[PageSpeed] Invalid API key or APIs not enabled.")
            # genericity: ok-start - official Google Cloud documentation URL
            print("Check that the PageSpeed Insights API is enabled:")
            print("  https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com")
            # genericity: ok-end
            sys.exit(1)
        return

    # Build the URL list
    if args.urls:
        urls = [(f"page_{i + 1}", u) for i, u in enumerate(args.urls)]
    else:
        har = find_har(audit_dir)
        if not har:
            print(f"Error: no .har file found in {audit_dir.parent}")
            print("Use --urls to provide the URLs explicitly.")
            sys.exit(1)
        urls = extract_urls_from_har(har)
        if not urls:
            print(f"Error: no page URL found in {har.name}")
            sys.exit(1)
        print(f"[PageSpeed] {len(urls)} page(s) extracted from {har.name}")

    strategies = ["mobile", "desktop"] if args.strategy == "both" else [args.strategy]
    print(f"[PageSpeed] Strategy(ies): {', '.join(strategies)} | {len(urls)} URL(s)")
    print()

    entries = collect(audit_dir, urls, api_key, strategies=strategies)

    # Count entries with an OK measurement (usable metrics)
    ok_count = sum(1 for e in entries if e.get("measurement", {}).get("status") == "ok")

    if ok_count == 0:
        print("\n[PageSpeed] No usable metric — Lighthouse fallback.")
        if not fallback_lighthouse(audit_dir, urls):
            # Fallback also failed: still write the traced failures
            cwv_path = audit_dir / "cwv.json"
            merged = merge_with_existing(entries, cwv_path)
            with open(cwv_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            error_count = sum(1 for e in entries if e.get("measurement", {}).get("status") in ("network_error", "analysis_error"))
            not_found_count = sum(1 for e in entries if e.get("measurement", {}).get("status") == "not_found")
            print(f"\n[PageSpeed] cwv.json written despite the failure: {len(entries)} trace(s)")
            print(f"  - {error_count} measurement failure(s)")
            print(f"  - {not_found_count} page(s) without available data")
            print(f"  -> {cwv_path}")
        sys.exit(0)

    cwv_path = audit_dir / "cwv.json"
    merged = merge_with_existing(entries, cwv_path)

    with open(cwv_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    crux_count = sum(1 for e in entries if e.get("source") == "crux")
    lab_count = sum(1 for e in entries if e.get("source") == "pagespeed_lab")
    error_count = sum(1 for e in entries if e.get("measurement", {}).get("status") in ("network_error", "analysis_error"))
    not_found_count = sum(1 for e in entries if e.get("measurement", {}).get("status") == "not_found")
    mobile_count = sum(1 for e in entries if e.get("strategy") == "mobile")
    desktop_count = sum(1 for e in entries if e.get("strategy") == "desktop")
    print(f"\n[PageSpeed] cwv.json updated: {len(entries)} entr(y/ies)")
    print(f"  - {mobile_count} mobile / {desktop_count} desktop")
    if crux_count:
        print(f"  - {crux_count} entr(y/ies) with CrUX field data")
    if lab_count:
        print(f"  - {lab_count} entr(y/ies) with lab data (CrUX absent)")
    if error_count:
        print(f"  - {error_count} traced measurement failure(s)")
    if not_found_count:
        print(f"  - {not_found_count} page(s) without available data")
    print(f"  -> {cwv_path}")


if __name__ == "__main__":
    main()
