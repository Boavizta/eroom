#!/usr/bin/env python3
"""
Analysis of Chrome DevTools Coverage files — produces coverage-analysis.json.

Replaces the manual computation of step 30. Two reasons:

1. The extension is read from the PATH, never from the full URL. A versioned
   URL (dsfr.min.css?version=39.2.0) does not end with its extension. A naive
   `url.endswith(".css")` test classifies it as "other", it disappears from the
   JS/CSS aggregates, and a page whose URLs are ALL versioned is published at
   zero.
2. The page label comes from the URL of the document actually loaded, not from
   the file's rank in alphabetical order.

Usage:
  python3 coverage_metrics.py <source-dir> [--output coverage-analysis.json]
  python3 coverage_metrics.py <source-dir> --check    # compare without writing
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

# Optional subfolder where raw captures (HAR, Coverage) are stored.
RAW_DATA_DIR = "raw-data-potentially-sensitive"  # genericity: ok - constant declaration

# Asset extensions: a URL carrying one is not a page URL.
ASSET_EXTS = re.compile(
    r'\.(js|mjs|css|webp|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|otf|eot|json|map)$',
    re.I,
)

# Recognizable third-party libraries, with their role. The role is part of the
# label: "Swetrix" alone tells the report reader nothing.
KNOWN_LIBRARIES = {                     # genericity: ok-start - explicit third-party table
    "swetrix":            "Swetrix (analytics)",
    "google-analytics":   "Google Analytics",
    "googletagmanager":   "Google Tag Manager",
    "matomo":             "Matomo (analytics)",
    "piwik":              "Matomo/Piwik (analytics)",
    "atinternet":         "AT Internet (analytics)",
    "xiti":               "AT Internet/Xiti (analytics)",
    "kameleoon":          "Kameleoon (A/B testing)",
    "abtasty":            "AB Tasty (A/B testing)",
    "optimizely":         "Optimizely (A/B testing)",
    "orejime":            "Orejime (cookie consent manager)",
    "tarteaucitron":      "Tarteaucitron (cookie consent manager)",
    "didomi":             "Didomi (cookie consent manager)",
    "fonts.googleapis":   "Google Fonts",
    "fonts.gstatic":      "Google Fonts",
    "tolk.ai":            "Tolk.ai (chatbot)",
    "intercom":           "Intercom (chatbot)",
    "zendesk":            "Zendesk (support)",
    "crisp.chat":         "Crisp (chatbot)",
    "recaptcha":          "reCAPTCHA (Google)",
    "hcaptcha":           "hCaptcha",
    "liveidentity":       "LiveIdentity (CAPTCHA)",
    "dsfr":               "DSFR (French State Design System)",
    "bootstrap":          "Bootstrap (UI framework)",
    "tailwind":           "Tailwind (UI framework)",
    "jquery-ui":          "jQuery UI",
    "jquery":             "jQuery",
    "react":              "React",
    "vue":                "Vue.js",
}                                       # genericity: ok-end


def classify(url):
    """Type of a Coverage resource, deduced from the URL PATH.

    Coverage entries carry no mimeType (keys: url, ranges, text),
    so the extension is the only available signal. Query and fragment are
    stripped before the test, otherwise any versioned URL is misclassified.
    """
    path = urlparse(url).path
    if path.endswith((".js", ".mjs")):
        return "javascript"
    if path.endswith(".css"):
        return "css"
    return "other"


def read_entries(cov_path):
    """Reads a Coverage file. Two formats depending on the DevTools version:
    direct array, or an object wrapped under the "entries" key.

    Returns (entries, measurement): `entries` is the list (or None on
    failure), `measurement` follows the measurement-state convention
    (status/target/detail). Never raises: an unreadable file or an
    unrecognized format is returned as a measurement failure, never as an
    exception that would interrupt the analysis of the other Coverage files
    in the folder.
    """
    target = str(cov_path)
    try:
        with open(cov_path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        return None, {"status": "read_error", "target": target, "detail": f"unreadable file: {e}"}
    except json.JSONDecodeError as e:
        return None, {"status": "read_error", "target": target, "detail": f"invalid JSON: {e}"}

    if isinstance(data, list):
        return data, {"status": "ok", "target": target, "detail": None}
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"], {"status": "ok", "target": target, "detail": None}

    return None, {
        "status": "analysis_error",
        "target": target,
        "detail": f'unrecognized Coverage format (expected an array or an "entries" key), '
                  f"found: {type(data).__name__}",
    }


def measure(entries):
    """Measures a page: (list of resources, aggregates by type)."""
    resources = []
    for item in entries:
        url = item.get("url", "")
        total = len(item.get("text", "") or "")
        used = sum(
            r["end"] - r["start"]
            for r in item.get("ranges", [])
            if r.get("start") is not None and r.get("end") is not None
        )
        resources.append({
            "url": url,
            "type": classify(url),
            "total_bytes": total,
            "unused_bytes": total - used,
        })
    return resources


def aggregate(resources, rtype):
    total = sum(r["total_bytes"] for r in resources if r["type"] == rtype)
    unused = sum(r["unused_bytes"] for r in resources if r["type"] == rtype)
    return {
        "total_kb": round(total / 1024, 1),
        "unused_kb": round(unused / 1024, 1),
        "unused_pct": round(unused / total * 100, 2) if total else 0.0,
    }


def page_label(entries, har_documents):
    """URL of the loaded page, corroborated by the HAR when possible.

    The HAR tells which of these URLs were actually served as text/html.
    Without it, a technical URL (anti-CSRF token, message endpoint) can
    pass for the page: it has no asset extension and comes first.
    """
    candidates = []
    domains = Counter()
    for item in entries:
        url = item.get("url", "")
        if url.startswith("http"):
            domains[urlparse(url).netloc] += 1
    main_domain = domains.most_common(1)[0][0] if domains else ""

    for item in entries:
        url = item.get("url", "")
        if not url.startswith("http"):
            continue
        if urlparse(url).netloc != main_domain:
            continue
        if not ASSET_EXTS.search(urlparse(url).path):
            candidates.append(url)

    # Priority to the candidate the HAR declares as an HTML document.
    for url in candidates:
        if url.split("?")[0] in har_documents:
            return url, "HTML document confirmed by the HAR"
    if candidates:
        return candidates[0], "URL without asset extension (not confirmed by the HAR)"
    return "", "no identifiable page URL"


def har_document_urls(source_dir):
    """URLs served as text/html according to the HAR, if findable."""
    har_files = (sorted(source_dir.glob("*.har"))
                 or sorted((source_dir / RAW_DATA_DIR).glob("*.har")))
    if not har_files:
        return set(), None
    with open(har_files[0], encoding="utf-8") as f:
        har = json.load(f)
    docs = set()
    for e in har.get("log", {}).get("entries", []):
        mime = e.get("response", {}).get("content", {}).get("mimeType", "")
        if "html" in mime.lower():
            docs.add(e.get("request", {}).get("url", "").split("?")[0])
    return docs, har_files[0]


def detect_libraries(all_resources):
    found = {}
    for r in all_resources:
        low = r["url"].lower()
        for needle, label in KNOWN_LIBRARIES.items():
            if needle in low:
                found[label] = True
    return sorted(found)


def find_coverage_files(source_dir):
    return (sorted(source_dir.glob("Coverage-*.json"))
            or sorted(source_dir.glob("*coverage*.json"))
            or sorted((source_dir / RAW_DATA_DIR).glob("Coverage-*.json"))
            or sorted((source_dir / RAW_DATA_DIR).glob("*coverage*.json")))


def analyze(source_dir):
    source_dir = Path(source_dir)
    cov_files = [c for c in find_coverage_files(source_dir)
                 if c.name != "coverage-analysis.json"]
    if not cov_files:
        raise FileNotFoundError(
            f"No Coverage-*.json file in {source_dir} nor in "
            f"{source_dir / RAW_DATA_DIR}."
        )

    har_docs, har_path = har_document_urls(source_dir)

    pages, all_resources = [], []
    for i, cf in enumerate(cov_files, 1):
        entries, measurement = read_entries(cf)
        if entries is None:
            # Unreadable file or unrecognized format: the page stays in the
            # report (no silent failure that would make it disappear), with
            # zero aggregates and a measurement block that says why.
            pages.append({
                "name": f"Page {i}",
                "source_file": cf.name,
                "url": "",
                "url_provenance": "Coverage file read failed",
                "js_total_kb": 0.0,
                "js_unused_kb": 0.0,
                "js_unused_pct": 0.0,
                "css_total_kb": 0.0,
                "css_unused_kb": 0.0,
                "css_unused_pct": 0.0,
                "resources_count": 0,
                "no_js_no_css": False,
                "top_js_unused": [],
                "top_css_unused": [],
                "measurement": measurement,
            })
            continue

        resources = measure(entries)
        all_resources.extend(resources)
        url, provenance = page_label(entries, har_docs)

        js, css = aggregate(resources, "javascript"), aggregate(resources, "css")
        # A non-empty Coverage file that produces no JS/CSS byte at all is a
        # sign of misclassification, not of a codeless page. Say it.
        anamealy = (bool(entries) and js["total_kb"] == 0 and css["total_kb"] == 0)

        pages.append({
            "name": f"Page {i}",
            "source_file": cf.name,
            "url": url,
            "url_provenance": provenance,
            "js_total_kb": js["total_kb"],
            "js_unused_kb": js["unused_kb"],
            "js_unused_pct": js["unused_pct"],
            "css_total_kb": css["total_kb"],
            "css_unused_kb": css["unused_kb"],
            "css_unused_pct": css["unused_pct"],
            "resources_count": len(resources),
            "no_js_no_css": anamealy,
            "top_js_unused": [
                {"url": r["url"], "unused_kb": round(r["unused_bytes"] / 1024, 1)}
                for r in sorted((r for r in resources if r["type"] == "javascript"),
                                key=lambda r: -r["unused_bytes"])[:5]
            ],
            "top_css_unused": [
                {"url": r["url"], "unused_kb": round(r["unused_bytes"] / 1024, 1)}
                for r in sorted((r for r in resources if r["type"] == "css"),
                                key=lambda r: -r["unused_bytes"])[:3]
            ],
            "measurement": measurement,
        })

    js_all, css_all = aggregate(all_resources, "javascript"), aggregate(all_resources, "css")

    # Outlier: page whose total code exceeds 2x the median.
    weights = sorted(p["js_total_kb"] + p["css_total_kb"] for p in pages)
    n = len(weights)
    median = weights[n // 2] if n % 2 else (weights[n // 2 - 1] + weights[n // 2]) / 2
    outliers = [p["name"] for p in pages
                if median and (p["js_total_kb"] + p["css_total_kb"]) > 2 * median]

    return {
        "pages": pages,
        "summary": {
            "pages_count": len(pages),
            "total_js_kb": js_all["total_kb"],
            "total_js_unused_kb": js_all["unused_kb"],
            "total_js_unused_pct": js_all["unused_pct"],
            "total_css_kb": css_all["total_kb"],
            "total_css_unused_kb": css_all["unused_kb"],
            "total_css_unused_pct": css_all["unused_pct"],
            "third_party_libraries": detect_libraries(all_resources),
            "outlier_pages": outliers,
            "har_reference": har_path.name if har_path else None,
        },
    }


# Backward-compatible alias: run_efootprint.py still calls `analyse` until it is translated.
analyse = analyze


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_dir", type=Path)
    ap.add_argument("--output", type=Path,
                    help="output path (default: <source_dir>/audit/"  # genericity: ok - skill storage convention, no site named
                         "coverage-analysis.json)")
    ap.add_argument("--check", action="store_true",
                    help="compare against the existing output without writing anything")
    args = ap.parse_args(argv)

    result = analyze(args.source_dir)

    out = args.output or (args.source_dir / "audit" / "coverage-analysis.json")
    s = result["summary"]

    har_note = (f" — reference HAR: {s['har_reference']}" if s["har_reference"]
                else " — no HAR found, labels not corroborated")
    print(f"Coverage: {s['pages_count']} file(s){har_note}")
    for p in result["pages"]:
        flag = "  [!] no JS and no CSS" if p["no_js_no_css"] else ""
        print(f"  {p['name']}  JS {p['js_total_kb']:9.1f} KB "
              f"(unused {p['js_unused_kb']:8.1f})   "
              f"CSS {p['css_total_kb']:8.1f} KB "
              f"(unused {p['css_unused_kb']:8.1f}){flag}")
        print(f"          {p['url'] or '(page not identified)'}")
    print(f"  TOTAL    JS {s['total_js_kb']:9.1f} KB "
          f"(unused {s['total_js_unused_kb']:8.1f}, {s['total_js_unused_pct']}%)   "
          f"CSS {s['total_css_kb']:8.1f} KB "
          f"(unused {s['total_css_unused_kb']:8.1f}, {s['total_css_unused_pct']}%)")

    if args.check:
        if not out.exists():
            print(f"\n[check] {out} absent, nothing to compare.")
            return 0
        with open(out, encoding="utf-8") as f:
            old = json.load(f)
        o = old.get("summary", {})
        print("\n[check] differences vs the existing output:")
        diffs = 0
        for key in ("total_js_kb", "total_js_unused_kb", "total_css_kb", "total_css_unused_kb"):
            before, after = o.get(key), s[key]
            if before != after:
                diffs += 1
                print(f"  {key} : {before} -> {after}")
        print("  no differences." if not diffs else f"  {diffs} difference(s).")
        return 1 if diffs else 0

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print(f"\ncoverage-analysis.json written — {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
