#!/usr/bin/env python3
"""Inventory of third parties DECLARED in the `Content-Security-Policy` header.

Why this module: the CSP is the list, written by the site's team, of all the
domains from which the browser is allowed to load something. It is therefore
an inventory of intent, structurally **wider** than the HAR, which only
captures what was actually requested during the recorded journey.

The gap between the two is information in itself. Case verified on octo.com
(2026-09-03): the CSP declares the whole HubSpot suite and the LinkedIn pixel,
but the capture HAR contains **no** trace of them (only
`api.analytics.octo.tools`, `swetrix.org`, jsDelivr and Google Fonts).
The most likely explanation is that the capture was made without accepting
consent (the site uses Orejime), so the marketing trackers never started —
exactly the blind spot documented in the project's capture instructions. The
CSP makes it visible anyway.

Cost: **no network call**. The CSP value is already stored in
`security-headers-analysis.json` (`pages[].detail[]` where
`header == "content-security-policy"`), produced by `analyze_security_headers.py`
from the `.har` headers.

Structural limit never to forget: a domain allowed by the CSP is **not** a
domain used. An authorization can be a leftover, a preparation, or concern
another part of the site than the one audited. This module therefore never
produces a verdict: it produces a classified inventory, which the EOF rules
cross-reference with what is actually loaded.

Usage as a module:
    from csp_inventory import inventory_from_headers_analysis
    inv = inventory_from_headers_analysis(headers_analysis_dict)

Command-line usage (inspection):
    python3 csp_inventory.py <source_dir>
"""

import argparse
import json
import re
import sys
from pathlib import Path

# CSP keywords that are not domains (to exclude from the inventory).
_CSP_KEYWORDS = {
    "'self'", "'none'", "'unsafe-inline'", "'unsafe-eval'", "'strict-dynamic'",
    "'unsafe-hashes'", "'report-sample'", "'wasm-unsafe-eval'",
    "data:", "blob:", "filesystem:", "mediastream:", "about:", "https:", "http:",
    "*",
}

# Directives that declare a resource load. `report-uri`,
# `report-to`, `upgrade-insecure-requests`, `sandbox`... do not.
_RESOURCE_DIRECTIVES = {
    "default-src", "script-src", "script-src-elem", "script-src-attr",
    "style-src", "style-src-elem", "style-src-attr", "img-src", "font-src",
    "connect-src", "media-src", "frame-src", "child-src", "worker-src",
    "object-src", "manifest-src", "prefetch-src", "form-action",
}

# Third-party families. Order matters: the first matching pattern wins,
# so the most specific families must come before the more generic ones
# (e.g. `hs-analytics` before any broad pattern on "analytics").
#
# The split deliberately separates sober analytics (no cookie, no advertising
# profile, often self-hostable) from the rest: that is exactly the distinction
# EOF criterion 1.12 assumes, and a plain "an Analytics tech is detected"
# does not make.
_FAMILIES = [
    ("analytics_sobre", [
        r"\bswetrix\b", r"\bplausible\b", r"\bmatomo\b", r"\bpiwik\b",
        r"\bumami\b", r"\bfathom\b", r"goatcounter", r"simpleanalytics",
        r"\bpirsch\b", r"counter\.dev", r"\bcabin\b", r"\btinylytics\b",
    ]),
    ("marketing_crm", [
        r"\bhubspot\b", r"\bhubapi\b", r"\bhs-\w+", r"hsforms", r"hsappstatic",
        r"hs-sites", r"hsadspixel", r"\bmarketo\b", r"\bpardot\b",
        r"\bsalesforce\b", r"\bintercom\b", r"\bdrift\b", r"\bklaviyo\b",
        r"\bmailchimp\b", r"list-manage", r"activecampaign", r"\bbraze\b",
        r"\biterable\b", r"\bcustomer\.io\b", r"\bsendinblue\b", r"\bbrevo\b",
    ]),
    ("pixels_publicitaires_sociaux", [
        r"doubleclick", r"googlesyndication", r"googleadservices",
        r"connect\.facebook", r"facebook\.net", r"\blicdn\b", r"linkedin",
        r"\bcriteo\b", r"\btaboola\b", r"\boutbrain\b", r"\btiktok\b",
        r"snapchat", r"\bsc-static\b", r"pinterest", r"\bpinimg\b",
        r"\bbat\.bing\b", r"clarity\.ms", r"\bads-twitter\b", r"\bt\.co\b",
        r"\badnxs\b", r"rubiconproject", r"pubmatic", r"\badform\b",
    ]),
    ("behavioral_analytics", [
        r"google-analytics", r"googletagmanager", r"analytics\.google",
        r"\bomniture\b", r"\bdemdex\b", r"\b2o7\.net\b", r"adobedtm",
        r"\bsegment\.(io|com)\b", r"\bmixpanel\b", r"\bamplitude\b",
        r"\bheap(analytics)?\.", r"fullstory", r"\bhotjar\b",
        r"contentsquare", r"\bquantcast\b", r"chartbeat", r"\bmouseflow\b",
        r"\bsmartlook\b", r"\bluckyorange\b", r"\bcrazyegg\b",
    ]),
    ("paas_backend", [
        r"herokuapp", r"\bappspot\b", r"azurewebsites", r"\bvercel\.app\b",
        r"netlify\.app", r"\bworkers\.dev\b", r"\brun\.app\b",
        r"elasticbeanstalk", r"\bfly\.dev\b", r"\brailway\.app\b",
        r"\bonrender\.com\b", r"\bcloudfunctions\b", r"\blambda-url\b",
    ]),
    ("captcha_antibot", [
        r"recaptcha", r"\bhcaptcha\b", r"challenges\.cloudflare",
        r"\bturnstile\b", r"\bdatadome\b", r"\bperimeterx\b",
        r"\bfriendlycaptcha\b", r"\barkoselabs\b",
    ]),
    ("cdn_bibliotheques", [
        r"\bjsdelivr\b", r"\bcdnjs\b", r"\bunpkg\b", r"\bcloudfront\b",
        r"\bakamai\w*", r"\bfastly\b", r"cdn\.cloudflare", r"\bbootstrapcdn\b",
        r"\bskypack\b", r"\besm\.sh\b",
    ]),
    ("polices", [
        r"fonts\.googleapis", r"fonts\.gstatic", r"use\.typekit",
        r"\bfonts\.net\b", r"\bfontawesome\b", r"\bcloud\.typography\b",
    ]),
    ("cartes_media_embed", [
        r"\byoutube(-nocookie)?\.com\b", r"\bytimg\b", r"\bvimeo\b",
        r"maps\.googleapis", r"\bmapbox\b", r"openstreetmap",
        r"\bdailymotion\b", r"\bsoundcloud\b", r"\bspotify\b",
        r"\bdeezer\b", r"\btwitch\b",
    ]),
    ("consentement_rgpd", [
        r"\borejime\b", r"cookiebot", r"onetrust", r"\baxeptio\b",
        r"\btarteaucitron\b", r"\bdidomi\b", r"\bsirdata\b", r"\bquantcast\.mgr\b",
        r"\bklaro\b", r"\btrustarc\b",
    ]),
    ("infra_cloud_generique", [
        r"amazonaws", r"\bgstatic\b", r"\bgoogleapis\b", r"\bblob\.core\b",
        r"\bstorage\.googleapis\b",
    ]),
]

# Families considered non-essential tracking for the service, in the sense of
# EOF criterion 1.12. Sober analytics is deliberately excluded: it is the
# minimal audience measurement, not tracking.
TRACKING_FAMILIES = (
    "marketing_crm", "pixels_publicitaires_sociaux", "behavioral_analytics",
)


def parse_csp(csp_value):
    """Splits a CSP into {directive: [sources]}. Tolerant of malformed CSPs."""
    directives = {}
    if not csp_value:
        return directives
    for chunk in csp_value.split(";"):
        parts = chunk.strip().split()
        if not parts:
            continue
        directives[parts[0].lower()] = parts[1:]
    return directives


def _normalize_host(source):
    """'*.hs-scripts.com' -> 'hs-scripts.com' ; 'https://a.b/c' -> 'a.b'.

    Returns None if the source is not a domain (CSP keyword, bare scheme,
    inline hash/nonce).
    """
    s = source.strip()
    if not s or s.lower() in _CSP_KEYWORDS:
        return None
    if s.startswith("'"):  # 'nonce-...', 'sha256-...', other quoted keywords
        return None
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", s, flags=re.IGNORECASE)
    s = s.split("/")[0]
    s = s.lstrip("*.")
    s = s.split(":")[0]  # strip any port
    if not s or "." not in s:
        return None
    return s.lower()


def classify_host(host):
    """Returns the family of a domain, or 'non_classe' if no pattern matches."""
    for family, patterns in _FAMILIES:
        for pattern in patterns:
            if re.search(pattern, host, re.IGNORECASE):
                return family
    return "non_classe"


def extract_csp_value(headers_analysis):
    """Retrieves the CSP value from security-headers-analysis.json.

    Takes the CSP of the first page that declares one. If several pages have
    different CSPs, the union would be misleading (we could no longer tell
    which page allows what): we prefer the value from one real page, and we
    report the number of pages concerned.
    """
    pages = (headers_analysis or {}).get("pages") or []
    values = []
    for page in pages:
        for item in page.get("detail") or []:
            if item.get("header") == "content-security-policy" and item.get("value"):
                values.append((page.get("url"), item["value"]))
                break
    if not values:
        return None, 0, None
    url, value = values[0]
    return value, len(values), url


def inventory_from_headers_analysis(headers_analysis):
    """Classified inventory of declared third parties. None if no CSP available."""
    csp_value, pages_with_csp, source_url = extract_csp_value(headers_analysis)
    if not csp_value:
        return None

    directives = parse_csp(csp_value)
    hosts_by_directive = {}
    all_hosts = set()
    for directive, sources in directives.items():
        if directive not in _RESOURCE_DIRECTIVES:
            continue
        hosts = set()
        for source in sources:
            host = _normalize_host(source)
            if host:
                hosts.add(host)
        if hosts:
            hosts_by_directive[directive] = sorted(hosts)
            all_hosts |= hosts

    families = {}
    for host in sorted(all_hosts):
        families.setdefault(classify_host(host), []).append(host)

    return {
        "source": "security-headers-analysis.json (Content-Security-Policy header)",
        "page_source": source_url,
        "pages_with_csp": pages_with_csp,
        "hosts_declares": sorted(all_hosts),
        "families": families,
        "par_directive": hosts_by_directive,
        "note": (
            "DECLARED inventory, not observed: a domain allowed by the CSP "
            "is not necessarily requested. Cross-reference with the HAR to "
            "distinguish 'planned' from 'actually loaded'."
        ),
    }


def loaded_hosts_from_har_analysis(har_analysis):
    """Domains actually requested, according to har-analysis.json.

    Returns None (and not an empty set) if the information is missing:
    an empty set would wrongly mean "no third party loaded".
    """
    domains = (har_analysis or {}).get("domains") or {}
    first = domains.get("first_party") or []
    third = domains.get("third_party") or []
    if not first and not third:
        return None
    return {h.lower() for h in list(first) + list(third)}


def _host_matches(host, loaded):
    """A CSP domain is considered loaded if itself or a subdomain of it is."""
    return any(h == host or h.endswith("." + host) for h in loaded)


def tracking_summary(inventory, har_analysis):
    """Cross-references the declared inventory and the domains actually loaded.

    Returns a dict describing trackers by family, distinguishing
    declared-and-loaded / declared-only. Renders no verdict.
    """
    if not inventory:
        return None
    loaded = loaded_hosts_from_har_analysis(har_analysis)
    families = inventory["families"]

    tracking_declared, sober_declared = [], []
    for family, hosts in families.items():
        if family in TRACKING_FAMILIES:
            tracking_declared.extend(hosts)
        elif family == "analytics_sobre":
            sober_declared.extend(hosts)

    def split(hosts):
        if loaded is None:
            return sorted(hosts), []
        loaded_hosts = sorted(h for h in hosts if _host_matches(h, loaded))
        declared_only = sorted(h for h in hosts if not _host_matches(h, loaded))
        return loaded_hosts, declared_only

    tracking_loaded, tracking_only_declared = split(tracking_declared)
    sober_loaded, sober_only_declared = split(sober_declared)

    return {
        "loaded_connu": loaded is not None,
        "load_tracking": tracking_loaded,
        "declared_not_loaded": tracking_only_declared,
        "analytics_sobre_charge": sober_loaded,
        "sober_analytics_declared_not_loaded": sober_only_declared,
        "retained_tracking_families": list(TRACKING_FAMILIES),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir")
    args = parser.parse_args()
    source_dir = Path(args.source_dir).resolve()

    headers_path = source_dir / "security-headers-analysis.json"
    if not headers_path.exists():
        print(f"Error: {headers_path} absent. Run analyze_security_headers.py first.")
        sys.exit(1)
    headers_analysis = json.loads(headers_path.read_text(encoding="utf-8"))

    inv = inventory_from_headers_analysis(headers_analysis)
    if inv is None:
        print("No Content-Security-Policy header in the analyzed pages: "
              "no declared third-party inventory possible.")
        sys.exit(0)

    har_analysis = None
    for candidate in (source_dir / "audit" / "har-analysis.json", source_dir / "har-analysis.json"):
        if candidate.exists():
            har_analysis = json.loads(candidate.read_text(encoding="utf-8"))
            break

    print(f"CSP read on: {inv['page_source']} ({inv['pages_with_csp']} page(s) with CSP)")
    print(f"{len(inv['hosts_declares'])} declared domain(s), by family:")
    for family, hosts in sorted(inv["families"].items()):
        print(f"  - {family} ({len(hosts)}) : {', '.join(hosts)}")

    summary = tracking_summary(inv, har_analysis)
    if summary:
        print("\nCross-reference with the domains actually loaded (har-analysis.json):")
        if not summary["loaded_connu"]:
            print("  har-analysis.json unavailable: cannot distinguish declared/loaded.")
        else:
            print(f"  tracking actually loaded      : {summary['load_tracking'] or 'none'}")
            print(f"  tracking declared but NOT loaded: {summary['declared_not_loaded'] or 'none'}")
            print(f"  sober analytics loaded          : {summary['analytics_sobre_charge'] or 'none'}")


if __name__ == "__main__":
    main()
