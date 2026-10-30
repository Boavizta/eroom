#!/usr/bin/env python3
"""
Phase 2 - Environmental data collection for e-footprint.

Automatically collects the data needed for the CO2e estimate:
  - HAR        : page weight, request duration, main server IP
  - CrUX API   : mobile/desktop/tablet distribution (Device + Network mix)
  - ipinfo.io  : country + hosting provider from the server IP

Stores the result in env-data.json next to the HAR.
This file is the entry point for Phase 3 (interactive e-footprint loop).

Usage:
    python3 collect_env_data.py <source_dir>          # Reads the .har in source_dir
    python3 collect_env_data.py <source_dir> --refresh  # Recollect even if env-data.json exists
    python3 collect_env_data.py <source_dir> --check    # Checks the API keys without analyzing

Reads from .env at the project root:
    GOOGLE_API_KEY  (optional — degraded if absent)
    IPINFO_TOKEN    (optional — degraded if absent)
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Sibling module (same folder): traffic + country mix retrieval via SimilarWeb's
# internal API. Guarded import so collect_env_data.py stays usable even if the
# module is absent (we then fall back to assisted entry / the default).
try:
    import similarweb_api
except ImportError:
    similarweb_api = None

# Sibling module (same folder): technology (stack) detection via custom rules
# on the HAR. Guarded import (the rest works if the module is absent).
try:
    import detect_tech
except ImportError:
    detect_tech = None

# efootprint_model/ never imports e-footprint in from_har.py (guard checked by
# check_efootprint_spec.py): this import is therefore risk-free even if the
# e-footprint library is not installed. Guarded anyway, for consistency with the
# other sibling modules.
try:
    from efootprint_model.from_har import detect_infrastructures
except ImportError:
    detect_infrastructures = None


CRUX_API = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
IPINFO_API = "https://ipinfo.io/{ip}/json"

# Optional subfolder where raw captures (HAR, Coverage) are stored. It is in
# .gitignore: an authenticated journey HAR can contain credentials or session
# tokens. Files are looked up there as a fallback, if nothing at the root.
RAW_DATA_DIR = "raw-data-potentially-sensitive"

# Confidence keys for the output JSON
CONFIDENCE_HIGH = "high"       # collected data, reliable
CONFIDENCE_MEDIUM = "medium"   # collected but uncertain
CONFIDENCE_LOW = "low"         # estimated or default value
CONFIDENCE_DEFAULT = "default"  # library default value


# ---------------------------------------------------------------------------
# Device-mix correction: iOS (mobile) AND macOS (desktop) absent from CrUX
# ---------------------------------------------------------------------------
# CrUX only measures Chrome (Blink engine). Two symmetrical blind spots:
#   - MOBILE: iPhones/iPads (Safari), and even Chrome on iOS (WebKit imposed
#     by Apple), do not report. CrUX's "phone" share therefore almost only
#     reflects Android. We inflate mobile via the iOS share of the fleet.
#   - DESKTOP: Macs under Safari do not report. We inflate desktop via the
#     macOS share of the desktop fleet, symmetrically with the iOS correction.
# Assumed (mirror) hypothesis: iOS and macOS are treated as fully absent from
# CrUX. This is a slight over-correction (Chrome-on-Mac is actually measured),
# consistent with the assumption already made on the mobile side.
#
# Values = iOS share of the MOBILE fleet and macOS share of the DESKTOP fleet,
# source StatCounter "Mobile Operating System Market Share" and "Desktop
# Operating System Market Share" (indicative snapshot: 2025-06, to refresh
# periodically). Wide coverage (Europe + Americas + Asia + North/West Africa).
IOS_MOBILE_SHARE = {
    "FR": 0.35, "DE": 0.35, "GB": 0.52, "IE": 0.55, "NL": 0.55, "BE": 0.45,
    "CH": 0.55, "AT": 0.35, "ES": 0.30, "IT": 0.30, "PT": 0.30, "PL": 0.25,
    "SE": 0.55, "NO": 0.60, "DK": 0.65, "FI": 0.50, "RU": 0.30,
    "US": 0.57, "CA": 0.57, "MX": 0.25, "BR": 0.15,
    "JP": 0.69, "KR": 0.30, "CN": 0.22, "IN": 0.04, "AU": 0.55,
    "ZA": 0.18, "SN": 0.10, "TN": 0.15, "MA": 0.15,
    "default": 0.30,
}
MACOS_DESKTOP_SHARE = {
    "FR": 0.17, "DE": 0.15, "GB": 0.28, "IE": 0.25, "NL": 0.13, "BE": 0.13,
    "CH": 0.28, "AT": 0.13, "ES": 0.12, "IT": 0.13, "PT": 0.12, "PL": 0.08,
    "SE": 0.25, "NO": 0.28, "DK": 0.25, "FI": 0.20, "RU": 0.10,
    "US": 0.30, "CA": 0.28, "MX": 0.10, "BR": 0.08,
    "JP": 0.20, "KR": 0.10, "CN": 0.15, "IN": 0.04, "AU": 0.28,
    "ZA": 0.12, "SN": 0.06, "TN": 0.08, "MA": 0.08,
    "default": 0.15,
}
IOS_SHARE_SOURCE = "StatCounter Mobile OS Market Share (snapshot 2025-06, indicative)"
MACOS_SHARE_SOURCE = "StatCounter Desktop OS Market Share (snapshot 2025-06, indicative)"

# Bounds of the scenario range (iOS share of mobile) displayed in the appendix.
IOS_SCENARIO_LOW = 0.25    # conservative (little iOS -> small correction)
IOS_SCENARIO_HIGH = 0.55   # very Apple audience


def correct_device_mix(mobile_raw, desktop_raw, ios_share, macos_share):
    """Inflates mobile (iOS absent from CrUX) AND desktop (macOS/Safari absent),
    then renormalizes to 1.

    mobile_raw / desktop_raw: proportions from Chrome (tablet already
    merged into mobile_raw, sum = 1).
    ios_share   : iOS share of the mobile fleet (0-1). The Android share
                  = 1 - ios_share is the only one fully visible in CrUX.
    macos_share : macOS share of the desktop fleet (0-1). Symmetric: the
                  non-macOS share (Windows/Linux/ChromeOS) is the only one
                  fully visible.
    Returns (mobile_fraction, desktop_fraction) renormalized (sum = 1).
    """
    android_share = 1.0 - ios_share
    non_macos_share = 1.0 - macos_share
    mobile_corr = mobile_raw / android_share if android_share > 0 else mobile_raw
    desktop_corr = desktop_raw / non_macos_share if non_macos_share > 0 else desktop_raw
    total = mobile_corr + desktop_corr
    if total <= 0:
        return round(mobile_raw, 3), round(desktop_raw, 3)
    return round(mobile_corr / total, 3), round(desktop_corr / total, 3)


# ---------------------------------------------------------------------------
# Audience country mix -> iOS / macOS weighting
# ---------------------------------------------------------------------------
# CrUX does not know the visitors' country (no geo dimension). The audience
# country mix is used ONLY to weight the iOS (mobile) and macOS (desktop)
# shares of the correction above: a very "Apple" audience (US, JP, UK)
# inflates mobile+desktop more strongly than an Android-dominant audience
# (IN, BR, SN).
#
# Possible provenance of the mix (priority order, resolved in main()):
#   1. --audience entered (client analytics GA/Matomo, the most reliable);
#   2. audience_mix written by the AGENT in env-data.json (SimilarWeb estimate,
#      via WebFetch — the script never scrapes);
#   3. default France (100% FR) + console warning.

def parse_audience_spec(spec):
    """Parses the --audience value. Accepted formats:
      - weighted list: 'FR:0.7,US:0.3'  -> {'FR': 0.7, 'US': 0.3}
      - single-country shortcut: 'FR'   -> {'FR': 1.0}
    Weights are renormalized to sum to 1.
    Returns (mix_dict, error_msg); mix_dict is None on error."""
    spec = (spec or "").strip()
    if not spec:
        return None, "empty value"

    # Single-country shortcut (neither ':' nor ',')
    if ":" not in spec and "," not in spec:
        cc = spec.upper()
        if not cc.isalpha() or len(cc) != 2:
            return None, f"invalid country code: '{spec}' (expected ISO-2, e.g. FR)"
        return {cc: 1.0}, None

    mix = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            return None, f"invalid segment: '{part}' (expected COUNTRY:weight, e.g. FR:0.7)"
        cc, w = part.split(":", 1)
        cc = cc.strip().upper()
        if not cc.isalpha() or len(cc) != 2:
            return None, f"invalid country code: '{cc}' (expected ISO-2)"
        try:
            w = float(w.strip())
        except ValueError:
            return None, f"invalid weight for {cc}: '{w.strip()}'"
        if w < 0:
            return None, f"negative weight for {cc}"
        mix[cc] = mix.get(cc, 0.0) + w

    total = sum(mix.values())
    if total <= 0:
        return None, "weight sum is zero"
    return {cc: round(w / total, 4) for cc, w in mix.items()}, None


def weighted_os_shares(audience_mix):
    """Weights the iOS share (mobile) AND the macOS share (desktop) by the country mix.

    audience_mix: {country_code: weight} (sum ≈ 1).
    Returns (ios_share, macos_share, per_country_detail) where per_country_detail
    lists, per country, the weight and the iOS/macOS shares used (for the appendix).
    A country absent from the tables falls back to the 'default' value."""
    ios = 0.0
    macos = 0.0
    detail = []
    for cc, w in audience_mix.items():
        cc = cc.upper()
        i = IOS_MOBILE_SHARE.get(cc, IOS_MOBILE_SHARE["default"])
        mth = MACOS_DESKTOP_SHARE.get(cc, MACOS_DESKTOP_SHARE["default"])
        known = cc in IOS_MOBILE_SHARE
        ios += w * i
        macos += w * mth
        detail.append({
            "country": cc,
            "weight": round(w, 4),
            "ios_share": i,
            "macos_share": mth,
            "in_table": known,
        })
    return round(ios, 3), round(macos, 3), detail


def resolve_audience(cli_audience, existing_audience, ios_override=None, audience_measurement=None):
    """Resolves the audience country mix per the priority order and computes the
    weighted iOS/macOS shares.

    cli_audience      : raw --audience value (or None).
    existing_audience : 'audience' block already present in env-data.json, written
                        by the agent (SimilarWeb) or a previous run (or None).
    ios_override      : --ios-mobile-share value (overrides the computed iOS share).
    audience_measurement : 'measurements.audience' block from env-data.json (written
                        by similarweb_api.py), or None. Used to distinguish a data
                        absence (status != 'ok') from a real default.

    Returns an 'audience' dict ready to store in env-data.json:
        {mix, source, ios_share, macos_share, ios_share_source,
         macos_share_source, per_country, confidence, warning?}
    """
    warning = None
    source_url = None

    if cli_audience:
        mix, err = parse_audience_spec(cli_audience)
        if err:
            return {"error": f"--audience: {err}"}
        source = "manual entry"
        confidence = CONFIDENCE_MEDIUM
    elif existing_audience and existing_audience.get("mix") \
            and existing_audience.get("source") not in (None, "default"):
        mix = {k.upper(): float(v) for k, v in existing_audience["mix"].items()}
        total = sum(mix.values()) or 1.0
        mix = {k: round(v / total, 4) for k, v in mix.items()}
        source = existing_audience.get("source", "SimilarWeb (estimation)")
        confidence = existing_audience.get("confidence", CONFIDENCE_MEDIUM)
        source_url = existing_audience.get("source_url")
    else:
        # Fallback to France (100%). Distinguish a data absence (not_found)
        # from a probe failure (network_error, read_error, analysis_error).
        mix = {"FR": 1.0}
        source = "default"
        confidence = CONFIDENCE_DEFAULT

        if audience_measurement:
            status = audience_measurement.get("status", "")
            detail = audience_measurement.get("detail", "")
            target = audience_measurement.get("target", "")

            # The three *_error statuses are failures of OUR tool, not audit results.
            if status in ("network_error", "read_error", "analysis_error"):
                print(f"  ⚠ Audience probe failed ({status}) : {detail}")
                if target:
                    print(f"     Target: {target}")
                warning = (f"Audience probe failed ({status}). "
                           f"Audience delivered: France (100%) BY DEFAULT (not measured). "
                           f"Detail: {detail}")
            # not_found is an audit result: the domain is really not listed.
            # The fallback remains legitimate but say it differently.
            elif status == "not_found":
                print(f"  ⚠ Domain not listed by SimilarWeb: {detail}")
                if target:
                    print(f"     Target: {target}")
                warning = (f"Domain not listed by SimilarWeb. "
                           f"Audience delivered: France (100%) by default. "
                           f"Provide --audience \"FR:0.7,US:0.3\" (client analytics) if available.")
            else:
                # Unexpected status (should not happen): treat as missing data.
                warning = ("No audience country mix provided: France (100%) by default. "
                           "Provide --audience \"FR:0.7,US:0.3\" (client analytics) or let "
                           "the agent write a SimilarWeb mix in env-data.json.")
        else:
            warning = ("No audience country mix provided: France (100%) by default. "
                       "Provide --audience \"FR:0.7,US:0.3\" (client analytics) or let "
                       "the agent write a SimilarWeb mix in env-data.json.")

    ios_share, macos_share, per_country = weighted_os_shares(mix)
    ios_share_source = f"weighted by country mix ({source}), from {IOS_SHARE_SOURCE}"
    macos_share_source = f"weighted by country mix ({source}), from {MACOS_SHARE_SOURCE}"

    if ios_override is not None:
        ios_share = round(ios_override, 3)
        ios_share_source = f"manual entry (--ios-mobile-share {ios_override})"

    return {
        "mix": mix,
        "source": source,
        "source_url": source_url,
        "ios_share": ios_share,
        "macos_share": macos_share,
        "ios_share_source": ios_share_source,
        "macos_share_source": macos_share_source,
        "per_country": per_country,
        "confidence": confidence,
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# Annual traffic volume (visits/year)
# ---------------------------------------------------------------------------
# Neither PageSpeed nor CrUX provides an audience volume (their APIs only
# return distributions, never visit counters). Traffic is therefore either
# entered (client analytics) or estimated by a third-party source (SimilarWeb)
# that the AGENT writes into env-data.json via WebFetch — the script never
# scrapes. Default: baseline 100,000 visits/year + warning.
#
# Possible provenance (priority order, resolved in run_efootprint.py):
#   1. --visits entered (client analytics GA/Matomo, the most reliable);
#   2. 'traffic' block written by the agent in env-data.json (SimilarWeb estimate);
#   3. default 100,000 visits/year + warning.

DEFAULT_VISITS_PER_YEAR = 100_000


def resolve_traffic(existing_traffic):
    """Resolves the 'traffic' block to store in env-data.json.

    existing_traffic : 'traffic' block already present in env-data.json, written
                       by the agent (SimilarWeb) or a previous run (or None).

    The script NEVER collects traffic itself (no reliable public API): it only
    validates and normalizes the block written by the agent, or sets an explicit
    default. Manual entry goes through --visits in run_efootprint.py.

    Returns a dict ready to store: {visits_per_year, monthly_visits?, source,
    source_url, snapshot?, confidence, note, warning?}.
    """
    if existing_traffic and existing_traffic.get("visits_per_year") \
            and existing_traffic.get("source") not in (None, "default"):
        try:
            visits = int(round(float(existing_traffic["visits_per_year"])))
        except (TypeError, ValueError):
            visits = None
        if visits and visits > 0:
            monthly = existing_traffic.get("monthly_visits")
            resolved = {
                "visits_per_year": visits,
                "monthly_visits": int(round(float(monthly))) if monthly else None,
                "source": existing_traffic.get("source", "SimilarWeb (estimation)"),
                "source_url": existing_traffic.get("source_url"),
                "snapshot": existing_traffic.get("snapshot"),
                "confidence": existing_traffic.get("confidence", CONFIDENCE_MEDIUM),
                "note": existing_traffic.get(
                    "note",
                    "Audience volume estimated by a third-party source (wide margin). "
                    "Total CO2e grows with traffic (above a fixed floor of server fabrication + storage); CO2e/visit decreases as traffic grows."),
                "warning": None,
            }
            # Average time per page (TimeOnSite/PagePerVisit): serves the Nielsen
            # recalibration (efootprint_model/user_time.py, Lot 4). Additive,
            # absent if SimilarWeb does not provide it (cf. similarweb_api.py).
            avg_time = existing_traffic.get("avg_time_on_page_s")
            if avg_time is not None:
                resolved["avg_time_on_page_s"] = avg_time
            return resolved

    return {
        "visits_per_year": DEFAULT_VISITS_PER_YEAR,
        "monthly_visits": None,
        "source": "default",
        "source_url": None,
        "snapshot": None,
        "confidence": CONFIDENCE_DEFAULT,
        "note": "No traffic source provided: baseline 100,000 visits/year. "
                "Total CO2e grows with traffic (above a fixed floor of server fabrication + storage); CO2e/visit decreases as traffic grows.",
        "warning": ("No traffic volume provided: baseline 100,000 visits/year by default. "
                    "Provide --visits (client analytics) or let the agent write a "
                    "'traffic' SimilarWeb block in env-data.json."),
    }


# ---------------------------------------------------------------------------
# Automatic SimilarWeb retrieval (internal API)
# ---------------------------------------------------------------------------
# When an 'audience' or 'traffic' block is missing (absent, or source 'default'),
# we automatically query SimilarWeb's internal API via the sibling module
# similarweb_api.py and write the missing blocks into env-data.json BEFORE the
# audience/traffic resolution. This is the main path (replaces the old WebFetch).
#
# Guardrails — the existing priority order is sacred:
#   - a manual entry (--audience) wins: we then do NOT write the audience block;
#   - a block already present with a real source is NEVER overwritten;
#   - API failure (403, unknown domain, network) → clear message, we continue
#     (the caller falls back to assisted retrieval step 20d, then the default).

def _block_missing(block):
    """An audience/traffic block is 'missing' if absent, without mix/visits,
    or marked source 'default'/None (hence to be (re)filled by SimilarWeb)."""
    if not block:
        return True
    if block.get("source") in (None, "default"):
        return True
    return not (block.get("mix") or block.get("visits_per_year"))


def maybe_fetch_similarweb(source_dir, existing_audience, existing_traffic,
                            cli_audience=None, sw_domain=None):
    """Tries to fill the missing audience/traffic blocks via the SimilarWeb API.

    Returns (audience_block, traffic_block, measurements): the blocks built for
    what was missing (or the existing blocks unchanged otherwise), and
    `measurements`, a dict {"audience": measurement, "traffic": measurement}
    carrying only the keys actually attempted (measurement-state convention:
    status/target/detail). Does NOT touch the disk: these blocks are then passed
    to resolve_audience/resolve_traffic and rewritten in one go by
    build_env_data. Never raises: any failure is logged and returned as a
    measurement, never as an exception.

    cli_audience : if provided, the manual entry wins → we do not write the country mix.
    sw_domain    : forces the SimilarWeb domain (otherwise inferred from env-data.json/HAR).
    """
    measurements = {}

    if similarweb_api is None:
        print("  ⚠ module similarweb_api unavailable — automatic call skipped.")
        return existing_audience, existing_traffic, measurements

    # What is missing? The country mix is only targeted if no manual entry (--audience).
    need_audience = (not cli_audience) and _block_missing(existing_audience)
    need_traffic = _block_missing(existing_traffic)
    if not need_audience and not need_traffic:
        return existing_audience, existing_traffic, measurements

    domain = sw_domain or similarweb_api.infer_domain(source_dir)
    if not domain:
        print("  ⚠ SimilarWeb: domain not found (specify --sw-domain) — call skipped.")
        detail = "domain not found (env-data.json/HAR insufficient) — specify --sw-domain"
        target = "SimilarWeb: audited domain inference"
        if need_audience:
            measurements["audience"] = {"status": "analysis_error", "target": target, "detail": detail}
        if need_traffic:
            measurements["traffic"] = {"status": "analysis_error", "target": target, "detail": detail}
        return existing_audience, existing_traffic, measurements

    print(f"  [similarweb] Querying the internal API for: {domain} …")
    data, error_status, error_detail = similarweb_api.fetch_domain_data(domain)
    if error_status:
        print(f"  ⚠ SimilarWeb: {error_detail}")
        print("     Expected fallback: assisted retrieval (SKILL.md step 20d), then default.")
        target = f"SimilarWeb API: {domain}"
        if need_audience:
            measurements["audience"] = {"status": error_status, "target": target, "detail": error_detail}
        if need_traffic:
            measurements["traffic"] = {"status": error_status, "target": target, "detail": error_detail}
        return existing_audience, existing_traffic, measurements

    source_url = f"https://www.similarweb.com/website/{domain}/"
    audience_block = existing_audience
    traffic_block = existing_traffic
    if need_audience:
        built, measurement = similarweb_api.build_audience_block(data, source_url, domain)
        measurements["audience"] = measurement
        if built:
            audience_block = built
            mix_str = ", ".join(f"{cc} {w:.0%}" for cc, w in built["mix"].items())
            print(f"     Country mix: {mix_str}")
    if need_traffic:
        built, measurement = similarweb_api.build_traffic_block(data, source_url, domain)
        measurements["traffic"] = measurement
        if built:
            traffic_block = built
            snap = built.get("snapshot") or "?"
            print(f"     Traffic: {built['monthly_visits']:,}/month ({snap}) "
                  f"→ {built['visits_per_year']:,}/year")

    # The API can answer 200 without usable data (domain little/not tracked by
    # SimilarWeb: no TopCountryShares, null visits). Say it instead of silently
    # falling back to the defaults.
    missing = []
    if need_audience and not audience_block:
        missing.append("country mix")
    if need_traffic and not traffic_block:
        missing.append("traffic")
    if missing:
        print(f"  ⚠ SimilarWeb: no usable {' nor '.join(missing)} for "
              f"{domain} (little-tracked domain?).")
        print("     Expected fallback: assisted retrieval (SKILL.md step 20d), then default.")

    return audience_block, traffic_block, measurements


# ---------------------------------------------------------------------------
# Loading .env
# ---------------------------------------------------------------------------

def load_env(project_root):
    """Reads GOOGLE_API_KEY and IPINFO_TOKEN from .env."""
    env_path = project_root / ".env"
    keys = {}
    if not env_path.exists():
        return keys
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    return keys


def find_project_root(start):
    """Walks up until .env or .git is found."""
    p = Path(start).resolve()
    for _ in range(8):
        if (p / ".env").exists() or (p / ".git").exists():
            return p
        p = p.parent
    return Path(start).resolve()


# ---------------------------------------------------------------------------
# HAR: weight + duration + server IP extraction
# ---------------------------------------------------------------------------

def find_har(source_dir):
    hars = list(source_dir.glob("*.har")) or list(
        (source_dir / RAW_DATA_DIR).glob("*.har"))
    if len(hars) == 1:
        return hars[0]
    if len(hars) > 1:
        print(f"[HAR] Several .har found, using: {hars[0].name}")
        return hars[0]
    return None


def _entry_transfer_bytes(entry):
    """REAL network bytes (compressed) of a HAR entry, for e-footprint ONLY.

    The real byte that travels on the network is the COMPRESSED body
    (brotli/gzip), not content.size (decompressed). data_transferred drives the
    network energy of the CO2e computation: the transferred weight must feed it.

    Robust fallback chain (the _transferSize field, prefixed with _, is a
    non-standardized Chrome extension; always present in our Chrome pipeline,
    the fallback only covers the degraded case of a stripped HAR):
      1. response._transferSize (direct measurement, headers + compressed body);
      2. else bodySize (+ headersSize if known);
      3. else content.size (last resort, DECOMPRESSED, overestimates).

    GUARD: EcoIndex (har_metrics.py) keeps content.size (decompressed weight,
    required by the cnumr formula). This function concerns ONLY the e-footprint path.
    """
    resp = entry.get("response", {})
    ts = resp.get("_transferSize")
    if ts is not None and ts >= 0:
        return ts
    body = resp.get("bodySize", -1)
    if body is not None and body >= 0:
        headers = resp.get("headersSize", -1)
        return body + (headers if headers and headers > 0 else 0)
    return resp.get("content", {}).get("size", 0) or 0


def _resource_category(mime, url):
    """Classifies a resource by type, for the weight breakdown (Part B).

    Combines the mimeType (reliable) and the URL extension (fallback). Categories:
    html, css, js, image, font, other. Direct measurement from the HAR (good confidence)."""
    m = (mime or "").lower()
    u = url.lower().split("?")[0]
    if "html" in m:
        return "html"
    if "css" in m or u.endswith(".css"):
        return "css"
    if "javascript" in m or u.endswith(".js") or u.endswith(".mjs"):
        return "js"
    if "image" in m or "svg" in m or u.endswith((".png", ".jpg", ".jpeg", ".gif",
                                                  ".webp", ".svg", ".ico", ".avif")):
        return "image"
    if "font" in m or u.endswith((".woff", ".woff2", ".ttf", ".otf", ".eot")):
        return "font"
    return "other"


def _page_breakdown(page_entries, page_url):
    """Breaks down a page's weight by resource type and third-party share (Part B).

    Documentary metrics (direct measurement, good confidence). They do NOT enter
    the e-footprint computation: they EXPLAIN the data_transferred already used
    (weight of the representative page). The request count is displayed as an
    indicator, but server CPU (compute_needed) remains underivable from the HAR
    client-side.

    third-party share: bytes/requests to a host different from the page's host.
    """
    main_host = urllib.parse.urlparse(page_url).netloc if page_url else ""
    by_type = {}                # DECOMPRESSED bytes (content.size) — documentary/EcoIndex
    by_type_transfer = {}       # TRANSFERRED bytes (real network) — e-footprint (LOT 1)
    third_party_bytes = 0
    third_party_transfer_bytes = 0
    third_party_requests = 0
    for e in page_entries:
        url = e.get("request", {}).get("url", "")
        content = e.get("response", {}).get("content", {})
        size = content.get("size", 0) or 0
        transfer = _entry_transfer_bytes(e)
        cat = _resource_category(content.get("mimeType", ""), url)
        by_type[cat] = by_type.get(cat, 0) + size
        by_type_transfer[cat] = by_type_transfer.get(cat, 0) + transfer
        netloc = urllib.parse.urlparse(url).netloc
        if main_host and netloc and netloc != main_host:
            third_party_bytes += size
            third_party_transfer_bytes += transfer
            third_party_requests += 1
    total = sum(by_type.values())
    total_transfer = sum(by_type_transfer.values())
    return {
        "by_type_bytes": by_type,
        "total_bytes": total,
        "third_party_bytes": third_party_bytes,
        "third_party_requests": third_party_requests,
        "third_party_share": round(third_party_bytes / total, 3) if total else 0.0,
        # --- LOT 1: same counts in REAL network bytes (compressed) ---
        "by_type_transfer_bytes": by_type_transfer,
        "total_transfer_bytes": total_transfer,
        "third_party_transfer_bytes": third_party_transfer_bytes,
        "third_party_transfer_share": round(third_party_transfer_bytes / total_transfer, 3) if total_transfer else 0.0,
    }


def _median(values):
    if not values:
        return 0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _percentile(values, pct):
    if not values:
        return 0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _har_facts(page_entries):
    """Factual server/network signals attached (LOT 3, direct HAR measurement).

    Purely documentary: does NOT enter the e-footprint computation (compute_needed
    stays fixed, cf. Part B). Used to trace in the methodological appendix the
    browser cache, server timings, methods/statuses and the HTTP version.
    """
    total = len(page_entries)
    cached = [e for e in page_entries if e.get("response", {}).get("status") == 304]
    n_cached = len(cached)
    cached_transfer_bytes = sum(_entry_transfer_bytes(e) for e in cached)
    cached_uncompressed_bytes = sum(
        e.get("response", {}).get("content", {}).get("size", 0) or 0 for e in cached
    )

    waits = [
        e.get("timings", {}).get("wait", -1)
        for e in page_entries
        if e.get("timings", {}).get("wait", -1) is not None and e.get("timings", {}).get("wait", -1) >= 0
    ]

    methods = {}
    statuses = {}
    http_versions = {}
    for e in page_entries:
        m = e.get("request", {}).get("method", "?")
        methods[m] = methods.get(m, 0) + 1
        s = e.get("response", {}).get("status")
        if s is not None:
            statuses[s] = statuses.get(s, 0) + 1
        v = e.get("response", {}).get("httpVersion", "?")
        http_versions[v] = http_versions.get(v, 0) + 1

    dominant_http_version = max(http_versions, key=http_versions.get) if http_versions else "?"

    return {
        "request_count": total,
        "cache_304_count": n_cached,
        "cache_304_share": round(n_cached / total, 3) if total else 0.0,
        "cache_304_transfer_bytes": cached_transfer_bytes,
        "cache_304_uncompressed_bytes": cached_uncompressed_bytes,
        "wait_ms_median": round(_median(waits), 1),
        "wait_ms_p95": round(_percentile(waits, 0.95), 1),
        "methods": methods,
        "statuses": statuses,
        "http_versions": http_versions,
        "dominant_http_version": dominant_http_version,
        "note": "Documentary (direct HAR measurement), does not enter the e-footprint computation.",
    }


def extract_har_data(har_path):
    """
    Extracts from the HAR:
      - pages: list of {url, size_bytes, on_load_ms, breakdown}
      - server_ip: IP of the main server (first document request)
    """
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    log = har.get("log", {})
    pages_raw = log.get("pages", [])
    entries = log.get("entries", [])

    # Index entries by pageref
    entries_by_page = {}
    for e in entries:
        ref = e.get("pageref", "")
        entries_by_page.setdefault(ref, []).append(e)

    pages = []
    server_ip = None

    for i, page in enumerate(pages_raw):
        pid = page.get("id", f"page_{i+1}")
        url = page.get("title", "")
        timings = page.get("pageTimings", {})
        on_load_ms = timings.get("onLoad") or 0

        page_entries = entries_by_page.get(pid, [])
        # DECOMPRESSED weight (content.size): documentary, aligned with EcoIndex.
        size_bytes = sum(
            e.get("response", {}).get("content", {}).get("size", 0)
            for e in page_entries
        )
        # TRANSFERRED weight (real network, compressed): feeds e-footprint (LOT 1).
        size_transfer_bytes = sum(_entry_transfer_bytes(e) for e in page_entries)

        pages.append({
            "page_id": pid,
            "url": url,
            "size_bytes": size_bytes,
            "size_kb": round(size_bytes / 1024, 1),
            "size_transfer_bytes": size_transfer_bytes,
            "size_transfer_kb": round(size_transfer_bytes / 1024, 1),
            "on_load_ms": round(on_load_ms),
            "request_count": len(page_entries),
            "breakdown": _page_breakdown(page_entries, url),
            "har_facts": _har_facts(page_entries),
        })

        # Server IP: from the first HTML entry of this page
        if server_ip is None:
            for e in page_entries:
                mime = e.get("response", {}).get("content", {}).get("mimeType", "")
                if "html" in mime:
                    ip = e.get("serverIPAddress", "")
                    if ip and not ip.startswith("127.") and not ip.startswith("::1"):
                        server_ip = ip
                    break

    # Fallback IP: first entry of the HAR with a non-local IP
    if server_ip is None:
        for e in entries:
            ip = e.get("serverIPAddress", "")
            if ip and not ip.startswith("127.") and not ip.startswith("::1"):
                server_ip = ip
                break

    return pages, server_ip


def aggregate_page_metrics(pages):
    """
    Aggregates the HAR metrics over all pages for e-footprint.
    Returns the size-weighted averages.
    """
    if not pages:
        return {}

    # We use the heaviest page as the journey's representative
    heaviest = max(pages, key=lambda p: p["size_bytes"])
    avg_size_bytes = sum(p["size_bytes"] for p in pages) / len(pages)
    avg_on_load_ms = sum(p["on_load_ms"] for p in pages if p["on_load_ms"] > 0)
    n_with_load = sum(1 for p in pages if p["on_load_ms"] > 0)

    # Breakdown of the representative page (heaviest page = the one used by
    # data_transferred). Documentary metrics that EXPLAIN the input, without
    # changing it. The request count is an indicator; it is NOT used to derive
    # compute_needed (server CPU remains underivable from the HAR client-side).
    breakdown = heaviest.get("breakdown", {})

    return {
        "pages_count": len(pages),
        "heaviest_page_url": heaviest["url"],
        "heaviest_page_size_bytes": heaviest["size_bytes"],
        "avg_size_bytes": round(avg_size_bytes),
        "avg_size_kb": round(avg_size_bytes / 1024, 1),
        "avg_on_load_ms": round(avg_on_load_ms / n_with_load) if n_with_load else 0,
        # Recommended e-footprint inputs (representative page = heaviest)
        "efootprint": {
            # DECOMPRESSED weight (content.size): kept for backward compat and
            # comparison; NO longer the main input on the run_efootprint side.
            "data_transferred_bytes": heaviest["size_bytes"],
            # TRANSFERRED weight (real network, compressed): NEW e-footprint input
            # (LOT 1). data_transferred drives network energy -> it must be the
            # weight actually transmitted, not the decompressed one.
            "data_transferred_bytes_real": heaviest.get("size_transfer_bytes", heaviest["size_bytes"]),
            "compression_ratio": (
                round(heaviest["size_transfer_bytes"] / heaviest["size_bytes"], 3)
                if heaviest.get("size_transfer_bytes") and heaviest["size_bytes"] else None
            ),
            "request_duration_ms": heaviest["on_load_ms"] or round(avg_on_load_ms / n_with_load) if n_with_load else 1000,
            "confidence_data_transferred": CONFIDENCE_HIGH,
            "confidence_data_transferred_real": CONFIDENCE_HIGH,  # direct measurement (_transferSize)
            "confidence_request_duration": CONFIDENCE_HIGH if heaviest["on_load_ms"] > 0 else CONFIDENCE_MEDIUM,
            # --- Part B: transparency on the weight composition (documentary) ---
            "request_count": heaviest.get("request_count", 0),
            "weight_by_type_bytes": breakdown.get("by_type_bytes", {}),
            "weight_by_type_transfer_bytes": breakdown.get("by_type_transfer_bytes", {}),
            "third_party_bytes": breakdown.get("third_party_bytes", 0),
            "third_party_transfer_bytes": breakdown.get("third_party_transfer_bytes", 0),
            "third_party_requests": breakdown.get("third_party_requests", 0),
            "third_party_share": breakdown.get("third_party_share", 0.0),
            "third_party_transfer_share": breakdown.get("third_party_transfer_share", 0.0),
            "confidence_breakdown": CONFIDENCE_HIGH,  # direct HAR measurement
            # --- LOT 2/3: attached factual server/network signals (documentary) ---
            "har_facts": heaviest.get("har_facts", {}),
            "confidence_har_facts": CONFIDENCE_HIGH,  # direct HAR measurement
            # compute_needed stays fixed on the run_efootprint side (0.05 cpu_core): the HAR
            # does not measure server CPU. Documented, not derived.
            "compute_needed_note": "Server CPU underivable from the HAR (client-side signal). "
                                   "compute_needed stays a typical value (low confidence).",
        }
    }


# ---------------------------------------------------------------------------
# CrUX: mobile/desktop/tablet distribution
# ---------------------------------------------------------------------------

def call_crux(url, api_key):
    """
    Queries the CrUX API to get the form-factor distribution.

    Returns (data, measurement): `data` is the raw JSON (or None on failure),
    `measurement` follows the measurement-state convention (status/target/detail).

    CrUX answers HTTP 404 when the origin/URL does not have enough traffic to
    publish data: that is a real absence of the measured service (not_found),
    not a failure of our probe. Any other HTTP error (quota exceeded, invalid
    request, server crash) or network I/O error is a network_error: our tool
    could not get a usable response.
    """
    target = f"CrUX API: {url}"
    params = urllib.parse.urlencode({"key": api_key})
    full_url = CRUX_API + "?" + params
    body = json.dumps({"url": url, "metrics": ["form_factors"]}).encode("utf-8")
    req = urllib.request.Request(
        full_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data, {"status": "ok", "target": target, "detail": None}
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(body_err).get("error", {}).get("message", body_err[:200])
        except Exception:
            msg = body_err[:200]
        print(f"  [CrUX] HTTP error {e.code} : {msg}")
        if e.code == 404:
            return None, {"status": "not_found", "target": target, "detail": msg}
        return None, {"status": "network_error", "target": target, "detail": f"HTTP {e.code} : {msg}"}
    except Exception as e:
        print(f"  [CrUX] Network error: {e}")
        return None, {"status": "network_error", "target": target, "detail": str(e)}


def extract_device_mix(crux_data):
    """
    Extracts the mobile/desktop/tablet distribution from the CrUX response.
    Returns a dict with fractions (0-1) or None if data unavailable.
    """
    if not crux_data:
        return None
    record = crux_data.get("record", {})
    metrics = record.get("metrics", {})
    ff = metrics.get("form_factors", {})
    fractions = ff.get("fractions", {})
    if not fractions:
        return None

    phone = fractions.get("phone", 0.0)
    desktop = fractions.get("desktop", 0.0)
    tablet = fractions.get("tablet", 0.0)

    total = phone + desktop + tablet
    if total == 0:
        return None

    return {
        "phone": round(phone / total, 3),
        "desktop": round(desktop / total, 3),
        "tablet": round(tablet / total, 3),
        "source": "crux",
    }


def collect_device_mix(url, api_key):
    """Collects the device distribution for a URL from CrUX.

    Returns (mix, measurement): `mix` is the distribution dict (or None),
    `measurement` follows the measurement-state convention. If the call succeeds
    (HTTP 200) but the expected form_factors.fractions field is absent, the
    measurement is reclassified as analysis_error (the probe did talk to the API,
    but the expected content is not there) — never left hardcoded at "ok".
    """
    # Try the exact URL, then the origin
    from urllib.parse import urlparse
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    print(f"  [CrUX] {url}")
    data, measurement = call_crux(url, api_key)
    mix = extract_device_mix(data)
    if data is not None and mix is None:
        measurement = {
            "status": "analysis_error",
            "target": measurement["target"],
            "detail": "form_factors.fractions field absent from the CrUX response",
        }

    if mix is None and url != origin:
        print(f"  [CrUX] No data for the URL, trying the origin: {origin}")
        data2, measurement2 = call_crux(origin, api_key)
        mix2 = extract_device_mix(data2)
        if mix2:
            mix2["source"] = "crux_origin"
            mix = mix2
            measurement = measurement2
        elif data2 is not None:
            measurement = {
                "status": "analysis_error",
                "target": measurement2["target"],
                "detail": "form_factors.fractions field absent from the CrUX response (origin)",
            }
        else:
            measurement = measurement2

    return mix, measurement


# ---------------------------------------------------------------------------
# ipinfo.io: country + provider from IP
# ---------------------------------------------------------------------------

def call_ipinfo(ip, token=None):
    """Queries ipinfo.io for an IP.

    Returns (data, measurement): `data` is the JSON (or None on failure),
    `measurement` follows the measurement-state convention (status/target/detail).
    """
    target = f"https://ipinfo.io/{ip}/json"
    url = IPINFO_API.format(ip=ip)
    if token:
        url += f"?token={token}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data, {"status": "ok", "target": target, "detail": None}
    except urllib.error.HTTPError as e:
        print(f"  [ipinfo] HTTP error for {ip} : {e}")
        return None, {"status": "network_error", "target": target, "detail": f"HTTP {e.code} : {e.reason}"}
    except json.JSONDecodeError as e:
        print(f"  [ipinfo] Unreadable response for {ip} : {e}")
        return None, {"status": "read_error", "target": target, "detail": f"invalid JSON: {e}"}
    except Exception as e:
        print(f"  [ipinfo] Error for {ip} : {e}")
        return None, {"status": "network_error", "target": target, "detail": str(e)}


def detect_cloud_provider(org_field):
    """
    Detects the cloud provider from ipinfo's 'org' field.
    Ex: "AS16509 Amazon.com, Inc." -> "aws"
    """
    if not org_field:
        return None
    org_lower = org_field.lower()

    if "amazon" in org_lower or "aws" in org_lower:
        return "aws"
    if "google" in org_lower or "gcloud" in org_lower:
        return "gcp"
    if "microsoft" in org_lower or "azure" in org_lower:
        return "azure"
    if "ovh" in org_lower:
        return "ovh"
    if "scaleway" in org_lower or "online s.a.s" in org_lower:
        return "scaleway"
    if "cloudflare" in org_lower:
        return "cloudflare"  # CDN, not a cloud per se
    if "akamai" in org_lower or "limelight" in org_lower:
        return "cdn"
    if "hetzner" in org_lower:
        return "hetzner"

    return None


_COUNTRY_CARBON_INTENSITY = {
    # g CO2eq/kWh, source: electricitymaps.com 2023 annual averages
    "FR": 56,
    "DE": 381,
    "GB": 239,
    "NL": 295,
    "BE": 148,
    "ES": 192,
    "IT": 371,
    "PL": 774,
    "SE": 45,
    "NO": 29,
    "DK": 154,
    "FI": 128,
    "US": 428,
    "CA": 130,
    "AU": 545,
    "JP": 462,
    "KR": 415,
    "SG": 432,
    "IN": 713,
    "CN": 581,
    "BR": 114,
    "ZA": 840,
}
_DEFAULT_CARBON_INTENSITY = 400  # g/kWh (world average value)


def country_to_efootprint(country_code):
    """
    Returns the e-footprint constant name for an ISO 2 country code.
    Falls back to WORLD if the country is unknown.
    """
    mapping = {
        "FR": "FRANCE",
        "DE": "GERMANY",
        "GB": "UNITED_KINGDOM",
        "NL": "NETHERLANDS",
        "BE": "BELGIUM",
        "ES": "SPAIN",
        "IT": "ITALY",
        "PL": "POLAND",
        "SE": "SWEDEN",
        "NO": "NORWAY",
        "US": "UNITED_STATES",
        "CA": "CANADA",
        "AU": "AUSTRALIA",
        "JP": "JAPAN",
        "SG": "SINGAPORE",
        "BR": "BRAZIL",
        "CN": "CHINA",
    }
    return mapping.get(country_code.upper(), "WORLD") if country_code else "WORLD"


def collect_server_info(ip, token=None):
    """
    Collects country + provider from the server IP via ipinfo.io.

    Returns (info, measurement): `info` is the result dict (or None),
    `measurement` follows the measurement-state convention. A "bogon" IP (private
    or reserved, RFC1918/loopback...) is a real fact about the IP — ipinfo answers
    normally, but there is nothing to geolocate — hence `not_found`, not a probe
    failure.
    """
    if not ip:
        return None, {
            "status": "analysis_error",
            "target": "ipinfo.io (IP unavailable)",
            "detail": "no IP resolved for this target (HAR without a usable serverIPAddress)",
        }

    print(f"  [ipinfo] {ip}")
    data, measurement = call_ipinfo(ip, token)
    if not data:
        return None, measurement
    if "bogon" in data:
        return None, {
            "status": "not_found",
            "target": measurement["target"],
            "detail": "private/reserved IP (bogon): no geolocation possible",
        }

    country_code = data.get("country", "")
    org = data.get("org", "")
    hostname = data.get("hostname", "")
    city = data.get("city", "")

    provider = detect_cloud_provider(org)
    carbon_intensity = _COUNTRY_CARBON_INTENSITY.get(country_code.upper(), _DEFAULT_CARBON_INTENSITY)

    return {
        "ip": ip,
        "country_code": country_code,
        "city": city,
        "org": org,
        "hostname": hostname,
        "detected_provider": provider,
        "carbon_intensity_g_kwh": carbon_intensity,
        "efootprint_country": country_to_efootprint(country_code),
        "source": "ipinfo",
    }, measurement


def collect_multi_server_info(har_path, audited_domain, first_party_extra=(), token=None):
    """Geolocates EACH 1st-party infrastructure detected in the HAR, not
    just the main server (Lot 3: sites with several distinct infras,
    e.g. ANTS with 3 1st-party servers).

    Returns a list of dicts (same shape as `collect_server_info()`, plus
    `host`, `hosts`, `request_count`, `transferred_bytes`, `cache_header_seen`,
    `is_primary`, `measurement`), sorted like `detect_infrastructures()` (bytes
    decreasing, the first one is the main infra). An IP not resolved by
    ipinfo is still included (host/hosts/bytes known, the other fields None):
    a network failure on a secondary server must not make the infra itself
    disappear from the model — but its `measurement` block honestly carries
    the failure (or the absence, or the success), infra by infra.

    Returns [] if `detect_infrastructures` is unavailable (guarded import)
    or if the HAR revealed no 1st-party infra. In that case, no measurement
    block is produced: no geolocation attempt took place.
    """
    if detect_infrastructures is None or not har_path:
        return []

    infrastructures, _ = detect_infrastructures(har_path, audited_domain,
                                                 first_party_extra=first_party_extra)
    results = []
    for i, infra in enumerate(infrastructures):
        ip = infra["ips"][0] if infra["ips"] else None
        info, measurement = collect_server_info(ip, token)
        info = info or {}
        if measurement.get("status") != "ok" and measurement.get("detail"):
            measurement = dict(measurement)
            measurement["detail"] = f"[infra {infra['key']}] {measurement['detail']}"
        results.append({
            "host": infra["key"],
            "hosts": list(infra["hosts"]),
            "ip": ip,
            "country_code": info.get("country_code"),
            "city": info.get("city"),
            "org": info.get("org"),
            "detected_provider": info.get("detected_provider"),
            "carbon_intensity_g_kwh": info.get("carbon_intensity_g_kwh"),
            "efootprint_country": info.get("efootprint_country"),
            "confidence_country": CONFIDENCE_HIGH if info.get("country_code") else CONFIDENCE_DEFAULT,
            "confidence_provider": CONFIDENCE_MEDIUM if info.get("detected_provider") else CONFIDENCE_LOW,
            "request_count": infra["request_count"],
            "transferred_bytes": infra["transferred_bytes"],
            "cache_header_seen": infra["cache_header_seen"],
            "is_primary": i == 0,
            "measurement": measurement,
        })
    return results


# ---------------------------------------------------------------------------
# Building env-data.json
# ---------------------------------------------------------------------------

def build_env_data(har_data, device_mix, server_info, audience=None, traffic=None,
                   tech_stack=None, servers_info=None, ai_external_apis=None, measurements=None,
                   crux_measurement=None, ipinfo_measurement=None):
    """
    Assembles env-data.json from the collected data.
    Each section states the e-footprint inputs and their confidence level.

    crux_measurement  : measurement block of the CrUX call (collect_device_mix), or None
    if no attempt took place (e.g. GOOGLE_API_KEY absent). Embedded in
    "device_mix.measurement" when present.

    ipinfo_measurement : measurement block of the ipinfo call for the MAIN server
    (collect_server_info), or None if no attempt took place (e.g. no IP
    detected in the HAR). Embedded in "server.measurement" when present. Secondary
    infrastructures carry their own "measurement" directly in each entry of
    "servers" (cf. collect_multi_server_info).

    servers_info : optional list produced by `collect_multi_server_info()`,
    ONE ENTRY PER 1st-party infrastructure detected in the HAR (Lot 3). Written
    under the "servers" key (plural), which coexists with "server" (singular,
    UNCHANGED): "server" continues to describe the main infra exactly as
    before (non-regression), "servers" is an ADDITION that the current report
    ignores as long as it does not read it.

    audience : dict resolved by resolve_audience() carrying the audience country
    mix and the weighted iOS/macOS shares used to correct the device mix. If None,
    we fall back to France (100%) via resolve_audience(None, None).

    traffic : dict resolved by resolve_traffic() carrying the annual audience
    volume and its provenance (SimilarWeb / entry / default). If None, baseline 100,000/year.

    tech_stack : tech detection dict (detect_tech.detect_from_har). Written as-is
    under the "tech_stack" key. If None, the key is None (non-regression: the
    report and the computation remain valid without detection).

    ai_external_apis : dict {host: {rule_name, provider, resolved, model_name,
    output_tokens}} merged by merge_ai_external_apis() — PERSISTED (never
    re-asked once "resolved", unlike tech_stack recomputed at each run). If
    None, the key is {} (non-regression: from_har.py ignores an absent block,
    no generative-AI call added to the computation).
    """
    pages, _ = har_data if isinstance(har_data, tuple) else (har_data, None)
    har_metrics = aggregate_page_metrics(pages)

    if audience is None:
        audience = resolve_audience(None, None)
    if traffic is None:
        traffic = resolve_traffic(None)
    ios_share = audience["ios_share"]
    macos_share = audience["macos_share"]
    ios_share_source = audience["ios_share_source"]
    macos_share_source = audience["macos_share_source"]

    # --- Device mix ---
    # Project decision: the tablet is attached to mobile (touch / portable
    # logic). The report body only shows desktop/mobile; the detail (raw
    # phone/tablet fractions, iOS+macOS corrections, range) goes to the appendix.
    if device_mix:
        phone_raw = device_mix["phone"]
        desktop_raw = device_mix["desktop"]
        tablet_raw = device_mix.get("tablet", 0.0)
        # Tablet merged into mobile
        mobile_raw = round(phone_raw + tablet_raw, 3)
        crux_source = device_mix["source"]

        # Symmetric correction: iOS (mobile) AND macOS (desktop). The range
        # varies the iOS share (main sensitivity) at constant macOS share.
        mobile_central, desktop_central = correct_device_mix(mobile_raw, desktop_raw, ios_share, macos_share)
        mobile_low, desktop_low = correct_device_mix(mobile_raw, desktop_raw, IOS_SCENARIO_LOW, macos_share)
        mobile_high, desktop_high = correct_device_mix(mobile_raw, desktop_raw, IOS_SCENARIO_HIGH, macos_share)

        device_section = {
            # Values kept for the computation (mobile = phone+tablet, corrected iOS+macOS)
            "phone_fraction": mobile_central,
            "desktop_fraction": desktop_central,
            "tablet_fraction": 0.0,
            "tablet_merged_into_mobile": True,
            "source": crux_source,
            "confidence": CONFIDENCE_MEDIUM,  # corrected (iOS/macOS estimates) => medium
            # Raw CrUX (Chrome only, before tablet merge and corrections)
            "phone_fraction_raw": phone_raw,
            "desktop_fraction_raw": desktop_raw,
            "tablet_fraction_raw": tablet_raw,
            "mobile_fraction_raw": mobile_raw,
            # iOS (mobile) + macOS (desktop) corrections
            "ios_share_used": round(ios_share, 3),
            "ios_share_source": ios_share_source,
            "macos_share_used": round(macos_share, 3),
            "macos_share_source": macos_share_source,
            "mobile_fraction_corrected": mobile_central,
            "desktop_fraction_corrected": desktop_central,
            # Range for the appendix (variable iOS share, constant macOS share)
            "scenarios": {
                "conservative": {"ios_share": IOS_SCENARIO_LOW, "mobile": mobile_low, "desktop": desktop_low},
                "central": {"ios_share": round(ios_share, 3), "mobile": mobile_central, "desktop": desktop_central},
                "apple_heavy": {"ios_share": IOS_SCENARIO_HIGH, "mobile": mobile_high, "desktop": desktop_high},
            },
            "note": "CrUX = Chrome only (iOS/Safari not measured). Mobile inflated via "
                    "the iOS share, desktop via the macOS share (weighted by the audience "
                    "country mix); tablet merged into mobile.",
        }
        if crux_measurement:
            device_section["measurement"] = crux_measurement
        # Network based on the corrected mobile (phones+tablet = mobile; desktop = wifi)
        network_mix = {
            "wifi": desktop_central,
            "mobile": mobile_central,
            "source": "inferred_from_corrected_device_mix",
        }
    else:
        device_section = {
            "phone_fraction": 0.6,
            "desktop_fraction": 0.4,
            "tablet_fraction": 0.0,
            "tablet_merged_into_mobile": True,
            "source": "default",
            "confidence": CONFIDENCE_DEFAULT,
            "note": "CrUX unavailable - default values (60% mobile, 40% desktop). "
                    "No iOS/macOS correction applied (no data to correct).",
        }
        if crux_measurement:
            device_section["measurement"] = crux_measurement
        network_mix = {"wifi": 0.4, "mobile": 0.6, "source": "default"}

    # --- Network ---
    network_section = {
        "wifi_fraction": network_mix["wifi"],
        "mobile_fraction": network_mix["mobile"],
        "source": network_mix["source"],
        "confidence": CONFIDENCE_MEDIUM if network_mix["source"] != "default" else CONFIDENCE_DEFAULT,
    }

    # --- Server ---
    if server_info:
        server_section = {
            "ip": server_info["ip"],
            "country_code": server_info["country_code"],
            "org": server_info["org"],
            "detected_provider": server_info["detected_provider"],
            "carbon_intensity_g_kwh": server_info["carbon_intensity_g_kwh"],
            "efootprint_country": server_info["efootprint_country"],
            "source": "ipinfo",
            "confidence_country": CONFIDENCE_HIGH,
            "confidence_provider": CONFIDENCE_MEDIUM if server_info["detected_provider"] else CONFIDENCE_LOW,
            "confidence_carbon_intensity": CONFIDENCE_HIGH if server_info["country_code"] in _COUNTRY_CARBON_INTENSITY else CONFIDENCE_MEDIUM,
        }
        if ipinfo_measurement:
            server_section["measurement"] = ipinfo_measurement
    else:
        server_section = {
            "ip": None,
            "country_code": "FR",
            "detected_provider": None,
            "carbon_intensity_g_kwh": 56,
            "efootprint_country": "FRANCE",
            "source": "default",
            "confidence_country": CONFIDENCE_DEFAULT,
            "confidence_provider": CONFIDENCE_DEFAULT,
            "confidence_carbon_intensity": CONFIDENCE_DEFAULT,
            "note": "ipinfo unavailable - France by default",
        }
        if ipinfo_measurement:
            server_section["measurement"] = ipinfo_measurement

    # --- CDN detection and country-confidence downgrade ---
    # When the service sits behind a CDN, the observed IP is a point of presence
    # (PoP) close to the auditor, not the service's origin. The country deduced
    # from ipinfo then does not reflect the real hosting country -> confidence downgraded.
    cdn_detected = False
    cdn_sources = []

    # Signal 1: CDN category in the technical stack
    if tech_stack:
        cdn_list = tech_stack.get("categories", {}).get("CDN", [])
        if cdn_list:
            cdn_detected = True
            cdn_sources.append(f"CDN detected: {', '.join(cdn_list)}.")

    # Signal 2: cache headers observed in the HAR (multi-infra servers_info)
    if servers_info:
        cache_seen_hosts = [s["host"] for s in servers_info if s.get("cache_header_seen")]
        if cache_seen_hosts:
            cdn_detected = True
            cdn_sources.append(f"Cache headers seen ({len(cache_seen_hosts)} host(s)).")

    if cdn_detected:
        server_section["confidence_country"] = CONFIDENCE_LOW
        note_parts = [
            "Observed IP probably a CDN PoP (point of presence close to the auditor), "
            "not the service's origin."
        ]
        note_parts.extend(cdn_sources)
        if server_section.get("org"):
            note_parts.append(f"ASN: {server_section['org']}.")
        server_section["country_note"] = " ".join(note_parts)

    # --- e-footprint job (from the HAR) ---
    job_section = har_metrics.get("efootprint", {}) if har_metrics else {
        "data_transferred_bytes": 500 * 1024,
        "request_duration_ms": 1000,
        "confidence_data_transferred": CONFIDENCE_DEFAULT,
        "confidence_request_duration": CONFIDENCE_DEFAULT,
        "note": "HAR unavailable - default values",
    }

    # --- Audience (country mix -> iOS/macOS weighting) ---
    audience_section = {
        "mix": audience["mix"],
        "source": audience["source"],
        "source_url": audience.get("source_url"),
        "confidence": audience["confidence"],
        "ios_share_weighted": audience["ios_share"],
        "macos_share_weighted": audience["macos_share"],
        "per_country": audience["per_country"],
        "ios_share_source": IOS_SHARE_SOURCE,
        "macos_share_source": MACOS_SHARE_SOURCE,
        "note": "Audience country mix used ONLY to weight the iOS "
                "(mobile) and macOS (desktop) shares of the CrUX correction. CrUX has no "
                "geographic dimension; this mix does not modify the CWVs.",
    }

    # --- Traffic (annual audience volume) ---
    traffic_section = {
        "visits_per_year": traffic["visits_per_year"],
        "monthly_visits": traffic.get("monthly_visits"),
        "source": traffic["source"],
        "source_url": traffic.get("source_url"),
        "snapshot": traffic.get("snapshot"),
        "confidence": traffic["confidence"],
        "note": traffic.get("note"),
    }
    if traffic.get("avg_time_on_page_s") is not None:
        traffic_section["avg_time_on_page_s"] = traffic["avg_time_on_page_s"]

    # --- Tech cross-reference -> server (CO2e provider reliability) ---
    # If ipinfo did not conclude a provider but the tech detection reveals a
    # cloud CDN/host, we use it as a secondary signal to raise the provider
    # confidence. The CDN does not override a provider already determined by ipinfo.
    if tech_stack and not server_section.get("detected_provider"):
        _cdn_names = [t["name"] for t in tech_stack.get("technologies", [])
                      if t["category"] in ("CDN", "Hosting provider")]
        if _cdn_names:
            server_section["provider_from_tech"] = _cdn_names
            if server_section.get("confidence_provider") in (CONFIDENCE_LOW, CONFIDENCE_DEFAULT):
                server_section["confidence_provider"] = CONFIDENCE_MEDIUM
            server_section["note_provider"] = (
                "Provider not concluded by ipinfo; CDN/host detected "
                "via the technical stack: " + ", ".join(_cdn_names) + "."
            )

    result = {
        "schema_version": "1.7",
        "pages": pages if har_metrics else [],
        "har_summary": har_metrics,
        "device_mix": device_section,
        "network_mix": network_section,
        "server": server_section,
        "servers": servers_info or [],
        "audience": audience_section,
        "traffic": traffic_section,
        "job": job_section,
        "tech_stack": tech_stack,
        "ai_external_apis": ai_external_apis or {},
    }
    # Preserve the measurements written by similarweb_api.py (measurement-state convention)
    if measurements:
        result["measurements"] = measurements
    return result


def merge_ai_external_apis(detected, existing, refresh):
    """Merges the detected generative-AI hosts with the answers already given
    by the user (persisted, never expired except on explicit --refresh).

    `detected`: {host: {"rule_name", "provider"}}, cf.
    detect_tech.ai_generative_hosts_from_har(). `existing`: the
    "ai_external_apis" block from the previous env-data.json, or None.

    A "resolved" entry (the user answered, even "I don't know" ->
    model_name=None) is NEVER re-asked except on --refresh: that is the
    contract that lets the skill orchestration know which hosts to question
    (resolved=False) without re-asking a settled question.
    """
    existing = existing or {}
    merged = {} if refresh else dict(existing)
    for host, info in (detected or {}).items():
        if host in merged:
            merged[host]["rule_name"] = info["rule_name"]
            merged[host]["provider"] = info["provider"]
        else:
            merged[host] = {
                "rule_name": info["rule_name"],
                "provider": info["provider"],
                "resolved": False,
                "model_name": None,
                "output_tokens": None,
            }
    return merged


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Collects environmental data for e-footprint")
    parser.add_argument("source_dir", help="Source folder containing the .har")
    parser.add_argument("--refresh", action="store_true",
                        help="Recollect even if env-data.json already exists")
    parser.add_argument("--check", action="store_true",
                        help="Checks the API keys without analyzing")
    parser.add_argument("--audience", default=None,
                        help="Audience country mix used to weight the iOS/macOS shares of the "
                             "CrUX correction. Formats: weighted list 'FR:0.7,US:0.3' or "
                             "single-country shortcut 'FR'. Takes priority over the SimilarWeb mix "
                             "written by the agent in env-data.json. Default: France (100%%).")
    parser.add_argument("--ios-mobile-share", type=float, default=None,
                        help="Forces the iOS share of the mobile fleet (0-1), overrides the value "
                             "weighted by --audience. Advanced/debug use.")
    parser.add_argument("--sw-domain", default=None,
                        help="Forces the domain queried on SimilarWeb (e.g. octo.com). "
                             "Otherwise inferred from env-data.json/HAR.")
    parser.add_argument("--no-similarweb", action="store_true",
                        help="Disables the automatic call to the SimilarWeb API "
                             "(offline mode / avoid the network).")
    parser.add_argument("--first-party-host", action="append", default=[],
                        help="Host to treat as 1st-party even if its domain "
                             "differs from the audited site (e.g. a self-hosted "
                             "service under another domain name). Repeatable.")
    parser.add_argument("--set-ai-model", nargs=2, metavar=("HOST", "MODEL_NAME"),
                        action="append", default=[],
                        help="Records the generative-AI model chosen by "
                             "the user for a detected AI host (e.g. "
                             "--set-ai-model api.anthropic.com claude-sonnet-4-5). "
                             "Use MODEL_NAME=unknown if she does not know the "
                             "exact model (the host then stays out of the computation). Repeatable.")
    parser.add_argument("--set-ai-output-tokens", nargs=2, metavar=("HOST", "TOKENS"),
                        action="append", default=[],
                        help="Typical length of a response from this host, in "
                             "generated tokens (e.g. --set-ai-output-tokens api.anthropic.com 300). "
                             "Repeatable.")
    args = parser.parse_args()

    # Early validation of the --audience format (fail fast before any network collection)
    if args.audience is not None:
        _mix, _err = parse_audience_spec(args.audience)
        if _err:
            print(f"Error: --audience: {_err}")
            sys.exit(1)
    if args.ios_mobile_share is not None and not 0.0 <= args.ios_mobile_share < 1.0:
        print(f"Error: --ios-mobile-share must be in [0, 1[ (got: {args.ios_mobile_share})")
        sys.exit(1)

    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        print(f"Error: folder not found: {source_dir}")
        sys.exit(1)

    project_root = find_project_root(source_dir)
    env = load_env(project_root)
    google_key = env.get("GOOGLE_API_KEY")
    ipinfo_token = env.get("IPINFO_TOKEN")

    # --- --check mode ---
    if args.check:
        print("[check] Checking available API keys...")
        print(f"  GOOGLE_API_KEY : {'OK' if google_key else 'ABSENT (CrUX disabled)'}")
        print(f"  IPINFO_TOKEN   : {'OK' if ipinfo_token else 'ABSENT (anonymous mode, 50k/month max)'}")

        if google_key:
            from urllib.parse import urlparse
            test_url = "https://www.google.com"
            print(f"\n[check] CrUX test on {test_url}...")
            mix, mix_measurement = collect_device_mix(test_url, google_key)
            if mix:
                print(f"  -> OK: desktop={mix['desktop']:.0%} phone={mix['phone']:.0%}")
            else:
                print(f"  -> FAILURE ({mix_measurement.get('status')}) : {mix_measurement.get('detail')}")
                print("    Check that the Chrome UX Report API is enabled:")
                print("    https://console.cloud.google.com/apis/library/chromeuxreport.googleapis.com")

        if ipinfo_token:
            print("\n[check] ipinfo.io test...")
            info, info_measurement = call_ipinfo("8.8.8.8", ipinfo_token)
            if info:
                print(f"  -> OK: {info.get('org', '')} ({info.get('country', '')})")
            else:
                print(f"  -> FAILURE ({info_measurement.get('status')}) : {info_measurement.get('detail')}")
                print("    Check the ipinfo.io token")
        return

    # --- Cache check ---
    env_data_path = source_dir / "env-data.json"
    if env_data_path.exists() and not args.refresh:
        print(f"[collect_env_data] env-data.json already exists in {source_dir.name}/")
        print("  Use --refresh to force recollection.")
        with open(env_data_path, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"  Pages: {len(existing.get('pages', []))}")
        s = existing.get("server", {})
        print(f"  Server: {s.get('country_code', '?')} / {s.get('detected_provider', 'unknown')}")
        d = existing.get("device_mix", {})
        print(f"  Device mix: desktop={d.get('desktop_fraction', '?'):.0%} "
              f"phone={d.get('phone_fraction', '?'):.0%} (source: {d.get('source', '?')})")
        return

    # --- HAR collection ---
    print("[1/3] HAR extraction...")
    har_path = find_har(source_dir)
    if not har_path:
        print(f"  WARNING: no .har found in {source_dir}")
        print("  Page metrics will be replaced by default values.")
        pages, server_ip = [], None
    else:
        print(f"  File: {har_path.name}")
        pages, server_ip = extract_har_data(har_path)
        print(f"  Pages: {len(pages)}")
        for p in pages:
            print(f"    [{p['page_id']}] {p['url'][:60]} — {p['size_kb']} KB, {p['on_load_ms']} ms")
        if server_ip:
            print(f"  Main server IP: {server_ip}")

    # --- CrUX collection ---
    print("\n[2/3] Device distribution collection (CrUX)...")
    device_mix = None
    crux_measurement = None
    if google_key and pages:
        # Use the first page's URL as the origin's representative
        first_url = pages[0]["url"] if pages else None
        if first_url:
            device_mix, crux_measurement = collect_device_mix(first_url, google_key)
            if device_mix:
                print(f"  -> desktop={device_mix['desktop']:.0%} "
                      f"phone={device_mix['phone']:.0%} "
                      f"tablet={device_mix.get('tablet', 0):.0%} "
                      f"(source: {device_mix['source']})")
            else:
                print(f"  -> No CrUX data available ({crux_measurement.get('status')}) "
                      f"— default values used")
    elif not google_key:
        print("  GOOGLE_API_KEY absent — default values (60% mobile, 40% desktop)")
        print(f"  (To enable: add GOOGLE_API_KEY in {project_root}/.env)")
    else:
        print("  No URL available from the HAR")

    # --- ipinfo collection ---
    print("\n[3/3] Server geolocation (ipinfo.io)...")
    server_info = None
    ipinfo_measurement = None
    if server_ip:
        if not ipinfo_token:
            print("  IPINFO_TOKEN absent — anonymous mode (50k req/month limit)")
            print(f"  (To enable: add IPINFO_TOKEN in {project_root}/.env)")
        server_info, ipinfo_measurement = collect_server_info(server_ip, ipinfo_token)
        if server_info:
            provider = server_info["detected_provider"] or "unknown"
            print(f"  -> {server_info['country_code']} ({server_info['city']}) "
                  f"/ {provider} — {server_info['carbon_intensity_g_kwh']} g CO2/kWh")
        else:
            print(f"  -> ipinfo failure ({ipinfo_measurement.get('status')}) "
                  f"— France / unknown provider by default")
    else:
        print("  No server IP detected in the HAR")

    # --- Geolocation of EACH 1st-party infrastructure (Lot 3) ---
    # A site can reveal several distinct 1st-party infras in the HAR
    # (e.g. ANTS: 3 servers). server_info above only geolocates the
    # main one; this block completes for the others.
    print("\n[infras] Geolocation of each 1st-party infrastructure...")
    servers_info = []
    audited_domain = similarweb_api.infer_domain(source_dir) if similarweb_api else None
    if har_path and audited_domain and detect_infrastructures:
        servers_info = collect_multi_server_info(
            har_path, audited_domain,
            first_party_extra=args.first_party_host, token=ipinfo_token)
        if len(servers_info) > 1:
            for s in servers_info:
                tag = "primary" if s["is_primary"] else "secondary"
                provider = s["detected_provider"] or "unknown"
                print(f"  -> [{tag}] {s['host']} : {s['country_code'] or '?'} / "
                      f"{provider} ({s['transferred_bytes']:,} bytes, "
                      f"{s['request_count']} requests)".replace(",", " "))
        elif servers_info:
            print("  -> a single 1st-party infra detected (same as the main one)")
        else:
            print("  -> detection unavailable (HAR absent or domain not found)")
    else:
        print("  -> skipped (HAR, audited domain or infra detection unavailable)")

    # --- Technical stack detection (custom rules on the HAR) ---
    print("\n[techno] Technical stack detection (custom rules)...")
    tech_stack = None
    if har_path and detect_tech:
        tech_stack = detect_tech.detect_from_har(har_path)
        if tech_stack and tech_stack.get("technologies"):
            cats = tech_stack.get("categories", {})
            print(f"  -> {len(tech_stack['technologies'])} technology(ies) "
                  f"in {len(cats)} category(ies): "
                  + ", ".join(f"{c} ({len(names)})" for c, names in cats.items()))
        else:
            print("  -> No technology detected")
    elif not detect_tech:
        print("  Module detect_tech absent — detection skipped")
    else:
        print("  No HAR — detection skipped")

    # --- Third-party generative-AI hosts detection (resolution: see below) ---
    print("\n[ai] Third-party generative-AI hosts detection (custom rules)...")
    ai_hosts_detected = {}
    if har_path and detect_tech:
        ai_hosts_detected = detect_tech.ai_generative_hosts_from_har(har_path) or {}
        if ai_hosts_detected:
            print(f"  -> {len(ai_hosts_detected)} AI host(s) detected: "
                  + ", ".join(f"{h} ({i['rule_name']})" for h, i in ai_hosts_detected.items()))
        else:
            print("  -> No generative-AI host detected")
    else:
        print("  -> skipped (HAR or module detect_tech unavailable)")

    # --- Audience country mix resolution (points 4a/4b) ---
    # Order: --audience > audience_mix already written by the agent (SimilarWeb) > FR default.
    # On --refresh we preserve the agent's audience block if it already exists.
    print("\n[audience] Country mix resolution (iOS/macOS weighting)...")
    existing_audience = None
    existing_traffic = None
    existing_ai_external_apis = None
    existing_measurements = {}
    if env_data_path.exists():
        try:
            with open(env_data_path, encoding="utf-8") as f:
                _prev = json.load(f)
            existing_audience = _prev.get("audience")
            existing_traffic = _prev.get("traffic")
            existing_ai_external_apis = _prev.get("ai_external_apis")
            existing_measurements = _prev.get("measurements", {})
        except (json.JSONDecodeError, OSError):
            existing_audience = None
            existing_traffic = None
            existing_ai_external_apis = None
            existing_measurements = {}

    ai_external_apis = merge_ai_external_apis(
        ai_hosts_detected, existing_ai_external_apis, refresh=args.refresh)

    # User answers, collected by the skill orchestration via
    # AskUserQuestion then passed back here as CLI args (same mechanism as
    # --audience/--ios-mobile-share above): this script never asks a question itself.
    for host, model_name in args.set_ai_model:
        entry = ai_external_apis.setdefault(
            host, {"rule_name": None, "provider": None, "output_tokens": None})
        entry["model_name"] = None if model_name.lower() == "unknown" else model_name
        entry["resolved"] = True
    for host, tokens in args.set_ai_output_tokens:
        entry = ai_external_apis.setdefault(
            host, {"rule_name": None, "provider": None, "model_name": None, "resolved": False})
        entry["output_tokens"] = float(tokens)
    if ai_external_apis:
        _resolved = sum(1 for v in ai_external_apis.values() if v.get("resolved"))
        print(f"\n[ai] {len(ai_external_apis)} AI host(s) tracked, {_resolved} resolved "
              f"(model known or explicitly unknown)")

    # Main path: fill the missing blocks via SimilarWeb's internal API.
    # The manual entry (--audience) wins and blocks writing the country mix.
    if not args.no_similarweb:
        existing_audience, existing_traffic, sw_measurements = maybe_fetch_similarweb(
            source_dir, existing_audience, existing_traffic,
            cli_audience=args.audience, sw_domain=args.sw_domain)
        # maybe_fetch_similarweb() never touches the disk (cf. its docstring):
        # its fresh measurements take priority over any value read back below.
        existing_measurements.update(sw_measurements)

    audience = resolve_audience(args.audience, existing_audience,
                                ios_override=args.ios_mobile_share,
                                audience_measurement=existing_measurements.get("audience"))
    if audience.get("error"):
        print(f"  Error: {audience['error']}")
        sys.exit(1)
    if audience.get("warning"):
        print(f"  ⚠ {audience['warning']}")
    mix_str = ", ".join(f"{cc} {w:.0%}" for cc, w in audience["mix"].items())
    print(f"  Country mix: {mix_str}  (source: {audience['source']})")
    print(f"  -> weighted iOS share {audience['ios_share']:.0%}, "
          f"weighted macOS share {audience['macos_share']:.0%}")

    # --- Traffic volume resolution (preserves the block written by the agent) ---
    # The script never collects traffic itself (no reliable public API): it
    # preserves the 'traffic' SimilarWeb block written by the agent, or sets the baseline.
    print("\n[traffic] Annual audience volume resolution...")
    traffic = resolve_traffic(existing_traffic)
    if traffic.get("warning"):
        print(f"  ⚠ {traffic['warning']}")
    print(f"  Traffic: {traffic['visits_per_year']:,} visits/year  (source: {traffic['source']})")

    # --- Assembling env-data.json ---
    env_data = build_env_data((pages, server_ip), device_mix, server_info,
                              audience=audience, traffic=traffic,
                              tech_stack=tech_stack, servers_info=servers_info,
                              ai_external_apis=ai_external_apis, measurements=existing_measurements,
                              crux_measurement=crux_measurement, ipinfo_measurement=ipinfo_measurement)

    with open(env_data_path, "w", encoding="utf-8") as f:
        json.dump(env_data, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] env-data.json written: {env_data_path}")

    # Summary of the e-footprint inputs
    job = env_data.get("job", {})
    server = env_data.get("server", {})
    device = env_data.get("device_mix", {})
    print("\ne-footprint inputs summary:")
    print(f"  Job.data_transferred  : {job.get('data_transferred_bytes', 0) // 1024} kB "
          f"[{job.get('confidence_data_transferred', '?')}]")
    print(f"  Job.request_duration  : {job.get('request_duration_ms', 0)} ms "
          f"[{job.get('confidence_request_duration', '?')}]")
    print(f"  Country               : {server.get('efootprint_country', '?')} "
          f"({server.get('carbon_intensity_g_kwh', '?')} g/kWh) "
          f"[{server.get('confidence_country', '?')}]")
    print(f"  Provider              : {server.get('detected_provider') or 'not detected'} "
          f"[{server.get('confidence_provider', '?')}]")
    print(f"  Device mobile/desktop : {device.get('phone_fraction', 0):.0%} / "
          f"{device.get('desktop_fraction', 0):.0%} "
          f"[{device.get('confidence', '?')}]")
    if device.get("mobile_fraction_raw") is not None:
        print(f"    (raw CrUX mobile={device.get('mobile_fraction_raw', 0):.0%}, "
              f"iOS-corrected {device.get('ios_share_used', 0):.0%} "
              f"+ macOS {device.get('macos_share_used', 0):.0%} "
              f"-> mobile={device.get('mobile_fraction_corrected', 0):.0%})")


if __name__ == "__main__":
    main()
