#!/usr/bin/env python3
"""
Traffic + country mix retrieval via SimilarWeb's internal extension API.

Unlike scraping the public page (blocked by AWS WAF captcha),
the SimilarWeb Chrome/Firefox extension queries an internal API that answers
without authentication: no cookie, no account, no session. It is enough to send
the same headers as the extension (a real browser User-Agent + the extension
version) and NOT to send an Origin header (CloudFront rejects it -> 403).

Diagnostic validated in July 2026: the previously documented 403 came from a
bad header (`Origin: chrome-extension://...`) and a non-browser User-Agent,
not from missing cookies. Fixed, the call answers 200 from a plain HTTP client.

This module is SEPARATE from collect_env_data.py on purpose: the latter never
fetches traffic or country mix itself (it only validates/normalizes the
'audience' and 'traffic' blocks present in env-data.json). This module writes
these two blocks into env-data.json, in the exact format expected by
resolve_audience() and resolve_traffic(), then `collect_env_data.py <dir>
--refresh` is re-run so they are normalized and integrated into the CO2e
computation.

Usage:
    python3 similarweb_api.py <source_dir>                  # domain inferred from env-data.json/HAR
    python3 similarweb_api.py <source_dir> --domain octo.com
    python3 similarweb_api.py <source_dir> --print-only     # prints the API JSON, writes nothing

Fallback path: if the API fails (403 again, network, domain unknown to
SimilarWeb), the module exits with code != 0 and a clear message. The caller
then falls back to assisted retrieval (SKILL.md step 20d).
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# Internal endpoint of the extension (cf. background.js decompiled from the .crx).
# To redo the discovery if the extension changes (endpoint/header/version),
# see documentation/implementation/similarweb-reconstruction.md
DATA_API = "https://data.similarweb.com/api/v1/data"

# Optional subfolder where raw captures (HAR, Coverage) are stored, in .gitignore.
RAW_DATA_DIR = "raw-data-potentially-sensitive"

# Extension version sent in the X-Extension-Version header. To revalidate if
# the API starts returning 403: install/update the extension, recapture the
# current version (chrome://extensions -> SimilarWeb card).
EXTENSION_VERSION = "6.12.21"

# User-Agent of a real browser: essential. Without it (or with the default UA
# of an HTTP client), CloudFront answers 403.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)

CONFIDENCE_MEDIUM = "medium"

_MONTHS_EN = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November",
    12: "December",
}


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def fetch_domain_data(domain, version=EXTENSION_VERSION, timeout=15):
    """Queries SimilarWeb's internal API for a domain.

    Returns (data_dict, None, None) on success, (None, error_status, detail) otherwise.
    Sends NO Origin header and a real browser User-Agent (the two
    conditions for success). No cookie needed.

    Possible error statuses:
    - read_error: empty domain (client-side call error)
    - network_error: timeout, DNS, connection refused, HTTP error
    - not_found: domain absent from SimilarWeb (200 response without SiteName)
    - analysis_error: 200 response without usable data (other cause)
    """
    domain = (domain or "").strip().lower()
    if not domain:
        return None, "read_error", "empty domain"
    # Cleanup: we want a bare domain (no URL, no www.)
    if "://" in domain:
        domain = urllib.parse.urlparse(domain).netloc or domain
    domain = domain.split("/")[0]
    if domain.startswith("www."):
        domain = domain[4:]

    url = DATA_API + "?" + urllib.parse.urlencode({"domain": domain})
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "X-Extension-Version": version,
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "*/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return None, "network_error", ("403 CloudFront: headers rejected or API hardened. "
                           "Check browser User-Agent + absence of Origin header, "
                           "or revalidate the extension version. Fallback: assisted step 20d.")
        return None, "network_error", f"HTTP {e.code} : {e.reason}"
    except Exception as e:
        return None, "network_error", f"network error: {type(e).__name__} - {e}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, "analysis_error", f"non-JSON response (excerpt: {raw[:120]!r})"

    if not isinstance(data, dict) or not data.get("SiteName"):
        return None, "not_found", "domain absent from SimilarWeb (200 response without SiteName)"
    return data, None, None


# ---------------------------------------------------------------------------
# Transformation -> env-data.json blocks
# ---------------------------------------------------------------------------

def build_audience_block(data, source_url, domain):
    """Builds the 'audience' block in the format expected by resolve_audience().

    Uses TopCountryShares (traffic share by country).
    Returns (block_dict, measurement_dict) on success,
    (None, measurement_dict) if the data is absent.

    The measurement dict always contains: status, target, detail (null if ok).
    """
    target = f"SimilarWeb API: TopCountryShares for {domain}"
    shares = data.get("TopCountryShares") or []
    mix = {}
    for entry in shares:
        cc = (entry.get("CountryCode") or "").upper()
        val = entry.get("Value")
        if cc and isinstance(val, (int, float)) and val > 0:
            mix[cc] = mix.get(cc, 0.0) + float(val)
    if not mix:
        measurement = {
            "status": "analysis_error",
            "target": target,
            "detail": "TopCountryShares absent or empty in the API response"
        }
        return None, measurement
    # Renormalize (Top Countries do not sum to 1: rest of the world ignored).
    total = sum(mix.values())
    mix = {cc: round(w / total, 4) for cc, w in mix.items()}
    block = {
        "mix": mix,
        # Neutral label displayed in the report (does not expose the technical
        # access method, cf. documentation/implementation/similarweb_api.md).
        "source": "SimilarWeb (estimation)",
        "source_url": source_url,
        "confidence": CONFIDENCE_MEDIUM,
    }
    measurement = {"status": "ok", "target": target, "detail": None}
    return block, measurement


def _snapshot_label(data):
    """Readable label of the reference month, e.g. 'June 2026'. None if absent."""
    eng = data.get("Engagments") or {}
    try:
        month = int(eng.get("Month"))
        year = int(eng.get("Year"))
    except (TypeError, ValueError):
        return None
    return f"{_MONTHS_EN.get(month, str(month))} {year}"


def _avg_time_on_page_s(data):
    """Average time per page view, in seconds: TimeOnSite / PagePerVisit.

    Serves as an independent measurement to recalibrate the raw Nielsen time (cf.
    `efootprint_model/user_time.py`, Lot 4). It is an average OVER THE WHOLE
    SITE, to compare with a page average, never with a single page:
    Nielsen computes a time per individual page (cf. Weinreich et al. 2008,
    ACM ToWeb, methodology section 4.4), SimilarWeb only returns an aggregate.

    Returns None if Engagments is absent or incomplete (the site is ignored
    by SimilarWeb, or the API does not return this block): it is MISSING
    INFORMATION, not a zero value.
    """
    eng = data.get("Engagments") or {}
    try:
        time_on_site = float(eng.get("TimeOnSite"))
        page_per_visit = float(eng.get("PagePerVisit"))
    except (TypeError, ValueError):
        return None
    if page_per_visit <= 0:
        return None
    return time_on_site / page_per_visit


def build_traffic_block(data, source_url, domain):
    """Builds the 'traffic' block in the format expected by resolve_traffic().

    Base: the most recent month of EstimatedMonthlyVisits (fallback Engagments.Visits),
    annualized x12 to stay consistent with monthly_visits (visits_per_year =
    monthly_visits x 12).
    Returns (block_dict, measurement_dict) on success,
    (None, measurement_dict) if no visit data.

    `avg_time_on_page_s`, when available, serves the Nielsen recalibration (Lot 4):
    absent from the dict if Engagments does not provide it, never set to 0 or guessed.

    The measurement dict always contains: status, target, detail (null if ok).
    """
    target = f"SimilarWeb API: EstimatedMonthlyVisits and Engagments.Visits for {domain}"
    monthly = None
    emv = data.get("EstimatedMonthlyVisits") or {}
    if isinstance(emv, dict) and emv:
        # Keys = 'YYYY-MM-01' dates; take the most recent one.
        latest_key = max(emv.keys())
        try:
            monthly = int(round(float(emv[latest_key])))
        except (TypeError, ValueError):
            monthly = None
    if not monthly:
        try:
            monthly = int(round(float((data.get("Engagments") or {}).get("Visits"))))
        except (TypeError, ValueError):
            monthly = None
    if not monthly or monthly <= 0:
        measurement = {
            "status": "analysis_error",
            "target": target,
            "detail": "EstimatedMonthlyVisits and Engagments.Visits absent or invalid"
        }
        return None, measurement

    visits_per_year = int(round(monthly * 12 / 1000.0)) * 1000  # rounded to the thousand
    block = {
        "visits_per_year": visits_per_year,
        "monthly_visits": monthly,
        # Neutral label (see build_audience_block).
        "source": "SimilarWeb (estimation)",
        "source_url": source_url,
        "snapshot": _snapshot_label(data),
        "confidence": CONFIDENCE_MEDIUM,
    }
    avg_time = _avg_time_on_page_s(data)
    if avg_time is not None:
        block["avg_time_on_page_s"] = round(avg_time, 3)
    measurement = {"status": "ok", "target": target, "detail": None}
    return block, measurement


# ---------------------------------------------------------------------------
# Domain inference + env-data.json merge
# ---------------------------------------------------------------------------

def _host_from_url(url):
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    host = urllib.parse.urlparse(url).netloc
    if host.startswith("www."):
        host = host[4:]
    return host or None


def infer_domain(source_dir):
    """Infers the audited domain from env-data.json (pages[0].url) then the HAR.
    Returns the bare domain (without www.) or None."""
    env_path = source_dir / "env-data.json"
    if env_path.exists():
        try:
            with open(env_path, encoding="utf-8") as f:
                env = json.load(f)
            pages = env.get("pages") or []
            if pages:
                host = _host_from_url(pages[0].get("url"))
                if host:
                    return host
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback: first .har of the folder, title of the first page.
    hars = list(source_dir.glob("*.har")) or list(
        (source_dir / RAW_DATA_DIR).glob("*.har"))
    if hars:
        try:
            with open(hars[0], encoding="utf-8") as f:
                har = json.load(f)
            for page in har.get("log", {}).get("pages", []):
                host = _host_from_url(page.get("title"))
                if host:
                    return host
        except (json.JSONDecodeError, OSError):
            pass
    return None


def merge_into_env_data(source_dir, audience_block, audience_measurement, traffic_block, traffic_measurement):
    """Writes/updates the 'audience', 'traffic' and 'measurements' blocks in env-data.json.

    If the file exists, everything else is preserved (HAR, device, server…) and
    only these blocks are replaced. Otherwise a minimal file is created: the next
    `collect_env_data.py --refresh` run will complete HAR/CrUX/ipinfo while
    re-reading these blocks (resolve_audience/resolve_traffic).

    IMPORTANT: measurements are ALWAYS written, even on failure. That is the
    core of the measurement-state convention: a failure leaves a trace on
    disk, instead of evaporating with the session.
    """
    env_path = source_dir / "env-data.json"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            env = json.load(f)
    else:
        env = {}

    # Initialize the measurements dict if it does not exist
    if "measurements" not in env:
        env["measurements"] = {}

    # Write the data blocks only if they exist
    if audience_block:
        env["audience"] = audience_block
    if traffic_block:
        env["traffic"] = traffic_block

    # Always write the measurements, even on failure
    if audience_measurement:
        env["measurements"]["audience"] = audience_measurement
    if traffic_measurement:
        env["measurements"]["traffic"] = traffic_measurement

    with open(env_path, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    return env_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetches traffic + country mix via the internal SimilarWeb API "
                    "and writes the audience/traffic blocks into env-data.json.")
    parser.add_argument("source_dir", help="Source folder (containing env-data.json and/or the .har)")
    parser.add_argument("--domain", default=None,
                        help="Domain to query (e.g. octo.com). Inferred from "
                             "env-data.json/HAR if omitted.")
    parser.add_argument("--version", default=EXTENSION_VERSION,
                        help=f"Extension version (X-Extension-Version header). "
                             f"Default: {EXTENSION_VERSION}.")
    parser.add_argument("--print-only", action="store_true",
                        help="Prints the raw API JSON and writes nothing.")
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        print(f"Error: folder not found: {source_dir}")
        sys.exit(1)

    domain = args.domain or infer_domain(source_dir)
    if not domain:
        print("Error: domain not found. Specify --domain (e.g. --domain octo.com).")
        sys.exit(1)

    print(f"[similarweb] Querying the internal API for: {domain}")
    data, error_status, error_detail = fetch_domain_data(domain, version=args.version)
    if error_status:
        print(f"  FAILURE ({error_status}) : {error_detail}")
        print("  -> Expected fallback: assisted retrieval (SKILL.md step 20d).")
        # Build the failure measurements before exiting
        target_base = f"https://data.similarweb.com/api/v1/data?domain={domain}"
        audience_measurement = {"status": error_status, "target": target_base, "detail": error_detail}
        traffic_measurement = {"status": error_status, "target": target_base, "detail": error_detail}
        # Write the failure traces into env-data.json
        env_path = merge_into_env_data(source_dir, None, audience_measurement, None, traffic_measurement)
        print(f"\n[FAILURE] Failure traces written into: {env_path}")
        sys.exit(2)

    if args.print_only:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    source_url = f"https://www.similarweb.com/website/{domain}/"
    audience_block, audience_measurement = build_audience_block(data, source_url, domain)
    traffic_block, traffic_measurement = build_traffic_block(data, source_url, domain)

    if not audience_block and not traffic_block:
        print("  FAILURE: API response without usable TopCountryShares or visits.")
        print("  -> Expected fallback: assisted retrieval (SKILL.md step 20d).")
        # Write the failure measurements into env-data.json
        env_path = merge_into_env_data(source_dir, None, audience_measurement, None, traffic_measurement)
        print(f"\n[FAILURE] Failure traces written into: {env_path}")
        sys.exit(2)

    if audience_block:
        mix_str = ", ".join(f"{cc} {w:.0%}" for cc, w in audience_block["mix"].items())
        print(f"  Country mix: {mix_str}")
    else:
        print("  ⚠ No country mix (TopCountryShares absent): audience block not written, measurement recorded.")

    if traffic_block:
        snap = traffic_block.get("snapshot") or "?"
        print(f"  Traffic: {traffic_block['monthly_visits']:,}/month ({snap}) "
              f"-> {traffic_block['visits_per_year']:,}/year")
    else:
        print("  ⚠ No visit volume: traffic block not written, measurement recorded.")

    env_path = merge_into_env_data(source_dir, audience_block, audience_measurement, traffic_block, traffic_measurement)
    print(f"\n[OK] Blocks written into: {env_path}")
    print(f"     Then re-run: python3 collect_env_data.py \"{source_dir}\" --refresh")


if __name__ == "__main__":
    main()
