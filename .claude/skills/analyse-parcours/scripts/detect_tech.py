#!/usr/bin/env python3
"""
Technology detection (technical stack) from a HAR — CUSTOM rules.

Pure-Python pattern-matching engine (stdlib only) over the signals already
present in the HAR: response headers, request URLs / third-party hosts, page
HTML (<meta name="generator"> tag, patterns), cookies (Set-Cookie).

WHY custom rules and not Wappalyzer/webappanalyzer?
  The toolbox is published under CC BY-SA 4.0, incompatible with the
  integration of GPL v3 data (webappanalyzer). So we write our own rules, 100%
  CC BY-SA compatible, offline, with no dependency and no network call.
  Full details: documentation/implementation/detection_technologies.md

Assumed scope: ~20-40 common technologies (CDN, web server, languages,
frameworks, CMS, analytics, fonts). We only detect what is visible client-side.
The instance type (t3.medium…) remains undetectable from the outside.

Standalone usage (re-runnable on its own, like the other project modules):
    python3 detect_tech.py <source_dir>     # folder containing the .har
    python3 detect_tech.py <file.har>       # direct path to a .har
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Optional subfolder where raw captures (HAR, Coverage) are stored, in .gitignore.
RAW_DATA_DIR = "raw-data-potentially-sensitive"

# Confidence keys (aligned with collect_env_data.py)
CONFIDENCE_HIGH = "high"       # distinctive and unambiguous signal
CONFIDENCE_MEDIUM = "medium"   # probable but shared / indirect signal
CONFIDENCE_LOW = "low"         # weak hint (HTML substring, etc.)

# Display order of categories in the report
CATEGORY_ORDER = [
    "CDN",
    "Hosting provider",
    "Web server",
    "Language",
    "Framework",
    "CMS",
    "Analytics",
    "Tag manager",
    "Fonts",
    "JS library",
    "Consent / GDPR",
    "Backend-as-a-Service / DB (third-party)",
    "Media streaming",
    "Generative AI (third-party)",
]


# ---------------------------------------------------------------------------
# CUSTOM detection rules
# ---------------------------------------------------------------------------
# Rule format (all fields optional except "cat"):
#   "cat"            : category (one of CATEGORY_ORDER)
#   "headers"        : {lowercase_header_name: regex} — match if the header
#                      value matches the regex (at least one header suffices)
#   "url"            : regex tested on each request URL (host + path)
#   "meta_generator" : regex tested on the content of <meta name="generator">
#   "html"           : regex tested on page HTML (weak hint)
#   "cookie"         : regex tested on cookie names (Set-Cookie)
#   "content_type"   : regex tested on the mimeType of each response (useful for
#                      media streaming when the URL reveals nothing, e.g. a
#                      stream served behind an opaque path) — MEDIUM confidence
#   "confidence"     : base confidence if a "strong" signal matches (default medium)
#
# A signal via "headers", "meta_generator" or "cookie" is considered STRONG
# (the rule's confidence). A signal via "url" is MEDIUM, via "content_type"
# is MEDIUM, via "html" is LOW.
TECH_RULES = {
    # --- CDN -----------------------------------------------------------------
    "Amazon CloudFront": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "headers": {"via": r"cloudfront", "x-amz-cf-id": r".+", "x-cache": r"cloudfront"},
    },
    "Cloudflare": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"^cloudflare$", "cf-ray": r".+", "cf-cache-status": r".+"},
    },
    "Fastly": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-served-by": r"cache-[a-z]{3}", "x-fastly-request-id": r".+"},
    },
    "Akamai": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-akamai-transformed": r".+", "server": r"AkamaiGHost"},
    },
    "jsDelivr": {
        "cat": "CDN", "confidence": CONFIDENCE_HIGH,
        "url": r"cdn\.jsdelivr\.net",
    },
    "unpkg": {
        "cat": "CDN", "confidence": CONFIDENCE_MEDIUM,
        "url": r"//unpkg\.com",
    },
    "cdnjs (Cloudflare)": {
        "cat": "CDN", "confidence": CONFIDENCE_MEDIUM,
        "url": r"cdnjs\.cloudflare\.com",
    },

    # --- Hosting provider (cloud signals) ------------------------------------
    "Amazon S3": {
        "cat": "Hosting provider", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-amz-request-id": r".+", "server": r"AmazonS3"},
    },
    "GitHub Pages": {
        "cat": "Hosting provider", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"GitHub\.com"},
    },
    "Vercel": {
        "cat": "Hosting provider", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"Vercel", "x-vercel-id": r".+"},
    },
    "Netlify": {
        "cat": "Hosting provider", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"Netlify", "x-nf-request-id": r".+"},
    },

    # --- Web server ----------------------------------------------------------
    "nginx": {
        "cat": "Web server", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"nginx"},
    },
    "Apache": {
        "cat": "Web server", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"apache"},
    },
    "Microsoft IIS": {
        "cat": "Web server", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"Microsoft-IIS"},
    },
    "LiteSpeed": {
        "cat": "Web server", "confidence": CONFIDENCE_HIGH,
        "headers": {"server": r"LiteSpeed"},
    },
    "Google Frontend": {
        "cat": "Web server", "confidence": CONFIDENCE_MEDIUM,
        "headers": {"server": r"^(gws|sffe|ESF|GSE)$"},
    },

    # --- Server language -----------------------------------------------------
    "PHP": {
        "cat": "Language", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-powered-by": r"PHP", "set-cookie": r"^PHPSESSID="},
    },
    "ASP.NET": {
        "cat": "Language", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-powered-by": r"ASP\.NET", "x-aspnet-version": r".+"},
    },
    "Express (Node.js)": {
        "cat": "Language", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-powered-by": r"Express"},
    },
    "Ruby on Rails": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "headers": {"x-powered-by": r"Phusion Passenger"},
        "cookie": r"^_session_id=",
    },

    # --- Front frameworks / SSR ----------------------------------------------
    "Next.js": {
        "cat": "Framework", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-powered-by": r"Next\.js"},
        "url": r"/_next/static/",
        "html": r"id=[\"']__NEXT_DATA__[\"']",
    },
    "Nuxt.js": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "html": r"window\.__NUXT__|id=[\"']__nuxt[\"']",
    },
    "Gatsby": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "html": r"id=[\"']___gatsby[\"']",
    },
    "Astro": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "headers": {"x-powered-by": r"Astro"},
        "html": r"<astro-island",
    },
    "React": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "html": r"data-reactroot|data-reactid|__REACT_DEVTOOLS",
    },
    "Vue.js": {
        "cat": "Framework", "confidence": CONFIDENCE_MEDIUM,
        "html": r"data-v-[0-9a-f]{8}|id=[\"']__vue|__VUE__",
    },

    # --- CMS -----------------------------------------------------------------
    "WordPress": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "url": r"/wp-(content|includes|json)/",
        "meta_generator": r"WordPress",
    },
    "Drupal": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-generator": r"Drupal", "x-drupal-cache": r".+"},
        "meta_generator": r"Drupal",
    },
    "Joomla": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "meta_generator": r"Joomla",
    },
    "Webflow": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "meta_generator": r"Webflow",
        "html": r"data-wf-page|data-wf-site",
    },
    "Shopify": {
        "cat": "CMS", "confidence": CONFIDENCE_HIGH,
        "headers": {"x-shopify-stage": r".+"},
        "url": r"cdn\.shopify\.com",
    },

    # --- Analytics -----------------------------------------------------------
    "Google Analytics (GA4)": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"google-analytics\.com|/gtag/js|/g/collect",
    },
    "Matomo": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"matomo\.(js|php)|piwik\.(js|php)",
    },
    "Swetrix": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)swetrix\.(org|com)|/swetrix\.js",
    },
    "Plausible": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"plausible\.io",
    },
    "Hotjar": {
        "cat": "Analytics", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)hotjar\.com",
    },

    # --- Tag manager ---------------------------------------------------------
    "Google Tag Manager": {
        "cat": "Tag manager", "confidence": CONFIDENCE_HIGH,
        "url": r"googletagmanager\.com/gtm\.js",
    },

    # --- Fonts ---------------------------------------------------------------
    "Google Fonts": {
        "cat": "Fonts", "confidence": CONFIDENCE_HIGH,
        "url": r"fonts\.(googleapis|gstatic)\.com",
    },
    "Font Awesome": {
        "cat": "Fonts", "confidence": CONFIDENCE_MEDIUM,
        "url": r"fontawesome|font-awesome",
    },

    # --- JS libraries --------------------------------------------------------
    "jQuery": {
        "cat": "JS library", "confidence": CONFIDENCE_MEDIUM,
        "url": r"/jquery[.-]",
    },

    # --- Consent / GDPR ------------------------------------------------------
    "Orejime (GDPR)": {
        "cat": "Consent / GDPR", "confidence": CONFIDENCE_MEDIUM,
        "url": r"/orejime[.-]",
    },
    "Axeptio": {
        "cat": "Consent / GDPR", "confidence": CONFIDENCE_HIGH,
        "url": r"axeptio\.(eu|imgix\.net)",
    },
    "Didomi": {
        "cat": "Consent / GDPR", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)didomi\.io",
    },

    # --- Backend-as-a-Service / DB (third-party) ------------------------------
    # The ONLY honest HAR signal for a "database": a BaaS/DBaaS exposed
    # DIRECTLY to the browser. A self-hosted DB behind an application server
    # emits NO visible network signal client-side — its absence here never
    # proves its real absence (cf. topology_overview.py).
    "Firebase / Firestore": {
        "cat": "Backend-as-a-Service / DB (third-party)", "confidence": CONFIDENCE_HIGH,
        "url": r"(firebaseio\.com|firestore\.googleapis\.com)",
    },
    "Supabase": {
        "cat": "Backend-as-a-Service / DB (third-party)", "confidence": CONFIDENCE_HIGH,
        "url": r"\.supabase\.co",
    },
    "MongoDB Atlas (Data API)": {
        "cat": "Backend-as-a-Service / DB (third-party)", "confidence": CONFIDENCE_MEDIUM,
        "url": r"data\.mongodb-api\.com",
    },
    "Airtable (API)": {
        "cat": "Backend-as-a-Service / DB (third-party)", "confidence": CONFIDENCE_MEDIUM,
        "url": r"api\.airtable\.com",
    },

    # --- Media streaming -----------------------------------------------------
    # Two vectors: URL/extension (m3u8/mpd, known video CDNs) and response
    # content-type (key "content_type", cf. _match_rule() — useful when the
    # URL reveals nothing, e.g. a stream served behind an opaque path).
    "HLS stream (.m3u8)": {
        "cat": "Media streaming", "confidence": CONFIDENCE_MEDIUM,
        "url": r"\.m3u8(\?|$)",
        "content_type": r"application/(vnd\.apple\.mpegurl|x-mpegurl)",
    },
    "DASH stream (.mpd)": {
        "cat": "Media streaming", "confidence": CONFIDENCE_MEDIUM,
        "url": r"\.mpd(\?|$)",
        "content_type": r"application/dash\+xml",
    },
    "Video/audio resource (content-type)": {
        "cat": "Media streaming", "confidence": CONFIDENCE_LOW,
        "content_type": r"^(video|audio)/",
    },
    "Mux (video streaming)": {
        "cat": "Media streaming", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)(stream\.mux\.com|mux\.com)",
    },
    "Cloudflare Stream": {
        "cat": "Media streaming", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)cloudflarestream\.com|videodelivery\.net",
    },

    # --- Generative AI (third-party) ------------------------------------------
    # Exact API domain recognized = near-certain signal, but _match_rule()
    # caps any "url" match at MEDIUM (consistency with the other url-only
    # rules of the file): the "near-certain" nuance is carried in the
    # presentation text (topology_overview.py), not in this generic badge.
    "OpenAI (API)": {
        "cat": "Generative AI (third-party)", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)api\.openai\.com",
    },
    "Anthropic (API Claude)": {
        "cat": "Generative AI (third-party)", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)api\.anthropic\.com",
    },
    "Google Generative AI (Gemini)": {
        "cat": "Generative AI (third-party)", "confidence": CONFIDENCE_HIGH,
        "url": r"generativelanguage\.googleapis\.com",
    },
    "Mistral AI (API)": {
        "cat": "Generative AI (third-party)", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)api\.mistral\.ai",
    },
    "Cohere (API)": {
        "cat": "Generative AI (third-party)", "confidence": CONFIDENCE_HIGH,
        "url": r"(//|\.)api\.cohere\.(ai|com)",
    },
    "Azure OpenAI": {
        "cat": "Generative AI (third-party)", "confidence": CONFIDENCE_MEDIUM,
        "url": r"openai\.azure\.com",
    },
    "Hugging Face Inference API": {
        "cat": "Generative AI (third-party)", "confidence": CONFIDENCE_MEDIUM,
        "url": r"api-inference\.huggingface\.co",
    },
}


# ---------------------------------------------------------------------------
# Signal extraction from the HAR
# ---------------------------------------------------------------------------

def find_har(source_dir):
    """Finds the .har in a folder (same logic as collect_env_data.find_har)."""
    source_dir = Path(source_dir)
    hars = list(source_dir.glob("*.har")) or list(
        (source_dir / RAW_DATA_DIR).glob("*.har"))
    if len(hars) >= 1:
        return hars[0]
    return None


def load_har_signals(har_path):
    """
    Walks the HAR entries and aggregates all exploitable signals.

    Reuses the same parsing logic as collect_env_data.extract_har_data()
    (json.load then iteration over log["entries"]).

    Returns a dict:
      - "headers"        : list of (lowercase_name, value) of all response headers
      - "urls"           : list of request URLs (host + path)
      - "hosts"          : set of distinct hosts
      - "main_host"      : most frequent host (presumed main domain)
      - "third_party"    : distinct hosts != main_host
      - "meta_generators": values of the <meta name="generator"> found in the HTML
      - "html_blobs"     : list of HTML bodies (for "html" patterns)
      - "cookies"        : names of cookies seen (Set-Cookie)
      - "content_types"  : list of (host, mimeType) of each response — the host
                           is essential to route a "content_type" detection
                           to the right ThirdPartyHost (cf. topology_overview.py)
      - "request_count"  : number of entries
    """
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    entries = har.get("log", {}).get("entries", [])

    headers = []
    urls = []
    host_counts = {}
    meta_generators = []
    html_blobs = []
    cookies = set()
    content_types = []

    meta_gen_re = re.compile(
        r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    for e in entries:
        url = e.get("request", {}).get("url", "")
        netloc = ""
        if url:
            urls.append(url)
            netloc = urlparse(url).netloc
            if netloc:
                host_counts[netloc] = host_counts.get(netloc, 0) + 1

        resp = e.get("response", {})
        for h in resp.get("headers", []):
            name = h.get("name", "").lower()
            value = h.get("value", "")
            headers.append((name, value))
            if name == "set-cookie" and value:
                cookies.add(value.split("=", 1)[0].strip())

        content = resp.get("content", {})
        mime = content.get("mimeType", "")
        if mime:
            content_types.append((netloc, mime))
        text = content.get("text", "")
        if text and "html" in mime:
            html_blobs.append(text)
            for m in meta_gen_re.findall(text):
                meta_generators.append(m)

    main_host = max(host_counts, key=host_counts.get) if host_counts else ""
    third_party = {h for h in host_counts if h != main_host}

    return {
        "headers": headers,
        "urls": urls,
        "hosts": set(host_counts),
        "main_host": main_host,
        "third_party": sorted(third_party),
        "meta_generators": meta_generators,
        "html_blobs": html_blobs,
        "cookies": sorted(cookies),
        "content_types": content_types,
        "request_count": len(entries),
    }


# ---------------------------------------------------------------------------
# Rule application
# ---------------------------------------------------------------------------

def _match_rule(name, rule, signals):
    """
    Tests a rule against the signals. Returns (confidence, evidence) on match,
    else (None, None).

    The retained confidence is the strongest of the matching signals:
      - headers / meta_generator / cookie -> the rule's base confidence
      - url                               -> capped at MEDIUM
      - html                              -> capped at LOW
    """
    base_conf = rule.get("confidence", CONFIDENCE_MEDIUM)
    best = None  # tuple (rank, conf, evidence)
    rank = {CONFIDENCE_HIGH: 3, CONFIDENCE_MEDIUM: 2, CONFIDENCE_LOW: 1}

    def _consider(conf, evidence):
        nonlocal best
        if best is None or rank[conf] > best[0]:
            best = (rank[conf], conf, evidence)

    # 1. Headers (strong signal)
    for hdr_name, pattern in rule.get("headers", {}).items():
        rx = re.compile(pattern, re.IGNORECASE)
        for name_h, value_h in signals["headers"]:
            if name_h == hdr_name and rx.search(value_h):
                _consider(base_conf, f'header {hdr_name}: "{value_h[:60]}"')
                break

    # 2. meta generator (strong signal)
    if "meta_generator" in rule:
        rx = re.compile(rule["meta_generator"], re.IGNORECASE)
        for gen in signals["meta_generators"]:
            if rx.search(gen):
                _consider(base_conf, f'<meta generator> = "{gen[:60]}"')
                break

    # 3. cookie (strong signal)
    if "cookie" in rule:
        rx = re.compile(rule["cookie"], re.IGNORECASE)
        for ck in signals["cookies"]:
            if rx.search(ck):
                _consider(base_conf, f'cookie "{ck}"')
                break

    # 4. URL (capped at MEDIUM)
    if "url" in rule:
        rx = re.compile(rule["url"], re.IGNORECASE)
        for u in signals["urls"]:
            if rx.search(u):
                conf = base_conf if rank[base_conf] < rank[CONFIDENCE_MEDIUM] else CONFIDENCE_MEDIUM
                # A dedicated third-party host is a reliable signal; we keep MEDIUM out of caution.
                short = urlparse(u).netloc + urlparse(u).path
                _consider(conf, f'request {short[:60]}')
                break

    # 4bis. response content-type (capped at MEDIUM: a video/audio mimeType
    # is a fact about THE RESOURCE, not about the SITE — a page can load
    # a single promo video without being a streaming site).
    if "content_type" in rule:
        rx = re.compile(rule["content_type"], re.IGNORECASE)
        for host_ct, ct in signals["content_types"]:
            if rx.search(ct):
                _consider(CONFIDENCE_MEDIUM, f'content-type "{ct[:40]}" at {host_ct}')
                break

    # 5. HTML (capped at LOW — substring, prone to false positives)
    if "html" in rule:
        rx = re.compile(rule["html"], re.IGNORECASE)
        for blob in signals["html_blobs"]:
            if rx.search(blob):
                _consider(CONFIDENCE_LOW, "pattern in the HTML")
                break

    if best is None:
        return None, None
    return best[1], best[2]


def detect(signals, rules=None):
    """
    Applies the rules to the signals. Returns a dict:
      {
        "technologies": [{"name", "category", "confidence", "evidence"}, ...],
        "categories": {cat: [names]},
        "third_party_hosts": [...],
        "request_count": int,
      }
    """
    rules = rules or TECH_RULES
    technologies = []
    for name, rule in rules.items():
        conf, evidence = _match_rule(name, rule, signals)
        if conf:
            technologies.append({
                "name": name,
                "category": rule["cat"],
                "confidence": conf,
                "evidence": evidence,
            })

    # Sort: by category order, then decreasing confidence, then name
    conf_rank = {CONFIDENCE_HIGH: 3, CONFIDENCE_MEDIUM: 2, CONFIDENCE_LOW: 1}

    def _cat_index(cat):
        return CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else len(CATEGORY_ORDER)

    technologies.sort(key=lambda t: (_cat_index(t["category"]),
                                     -conf_rank[t["confidence"]],
                                     t["name"]))

    categories = {}
    for t in technologies:
        categories.setdefault(t["category"], []).append(t["name"])

    return {
        "technologies": technologies,
        "categories": categories,
        "third_party_hosts": signals["third_party"],
        "request_count": signals["request_count"],
    }


def detect_from_har(har_path):
    """Programmatic entry point: HAR -> detection result (dict) or None."""
    if not har_path or not Path(har_path).exists():
        return None
    signals = load_har_signals(har_path)
    return detect(signals)


# ---------------------------------------------------------------------------
# Third-party generative AI: detection BY HOST (not by aggregated category)
# ---------------------------------------------------------------------------
# detect()/detect_from_har() above serve the presentation (step 25,
# topology_overview.py): they aggregate by category and do not carry the exact
# host. efootprint_model/from_har.py needs, however, the exact host to know
# WHICH network job to attach an EcoLogits computation to (cf. collect_env_data.py
# which calls the function below and writes its result into
# env-data.json::ai_external_apis). Reuses the same "url" rules of
# TECH_RULES, never a pattern rediscovery.

AI_PROVIDER_BY_RULE_NAME = {
    # Rule name (TECH_RULES) -> provider key of the EcoLogits catalog
    # (efootprint_model/build.py::_build_external_api). Azure OpenAI routes to
    # the same models as OpenAI: same EcoLogits catalog, not a distinct provider.
    "OpenAI (API)": "openai",
    "Anthropic (API Claude)": "anthropic",
    "Google Generative AI (Gemini)": "google_genai",
    "Mistral AI (API)": "mistralai",
    "Cohere (API)": "cohere",
    "Azure OpenAI": "openai",
    "Hugging Face Inference API": "huggingface_hub",
}


def ai_generative_hosts_from_har(har_path):
    """Hosts calling a third-party generative AI, detected by exact domain.

    Returns {host: {"rule_name": ..., "provider": ecologits_key}}, one host per
    API domain seen in the HAR (no aggregation by category). None if the
    HAR is absent/unreadable.
    """
    if not har_path or not Path(har_path).exists():
        return None
    signals = load_har_signals(har_path)
    rules = {name: rule for name, rule in TECH_RULES.items()
             if rule["cat"] == "Generative AI (third-party)"}

    result = {}
    for url in signals["urls"]:
        host = urlparse(url).netloc
        if not host or host in result:
            continue
        for name, rule in rules.items():
            rx = re.compile(rule["url"], re.IGNORECASE)
            if rx.search(url):
                provider = AI_PROVIDER_BY_RULE_NAME.get(name)
                if provider:
                    result[host] = {"rule_name": name, "provider": provider}
                break
    return result


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 1

    target = Path(argv[0])
    if target.is_dir():
        har_path = find_har(target)
        if not har_path:
            print(f"[ERROR] No .har found in {target}")
            return 1
    elif target.suffix == ".har" and target.exists():
        har_path = target
    else:
        print(f"[ERROR] Invalid target: {target} (expected: folder or .har file)")
        return 1

    print(f"[HAR] {har_path.name}")
    result = detect_from_har(har_path)
    if not result:
        print("[ERROR] unreadable HAR")
        return 1

    print(f"[HAR] {result['request_count']} requests, "
          f"{len(result['third_party_hosts'])} third-party host(s)\n")

    if not result["technologies"]:
        print("No technology detected by the custom rules.")
        return 0

    print(f"Detected technologies ({len(result['technologies'])}):")
    current_cat = None
    for t in result["technologies"]:
        if t["category"] != current_cat:
            current_cat = t["category"]
            print(f"\n  {current_cat}")
        print(f"    - {t['name']:<28} [{t['confidence']:<6}] {t['evidence']}")

    if result["third_party_hosts"]:
        print("\nThird-party hosts:")
        for h in result["third_party_hosts"]:
            print(f"    - {h}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
