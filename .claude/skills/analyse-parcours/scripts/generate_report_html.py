#!/usr/bin/env python3
"""
Generates an HTML audit report of a web journey.
Structure modeled on the ANTS PDF report (generate_pdf.py).
OCTO palette.

Usage:
  python3 generate_report_html.py <audit-dir> [--output report.html]

The directory must contain:
  - 1 .har file
  - 1+ Coverage-*.json files
  - cwv.json (optional)
"""

import base64
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

# ── Palette OCTO ──────────────────────────────────────────────────────────────
OCTO_DARK      = "#1C2856"
OCTO_BLUE      = "#5BA1BC"
OCTO_LIGHT     = "#82C1DD"
OCTO_PALE      = "#E0F0F4"
OCTO_GREY      = "#ECECF2"
OCTO_WHITE     = "#FFFFFF"

# Colors by resource type
# Optional subdirectory for raw captures (HAR, Coverage), in .gitignore.
RAW_DATA_DIR = "raw-data-potentially-sensitive"

TYPE_COLORS = {
    "javascript": "#f0ad4e",
    "css":        "#5bc0de",
    "image":      "#5cb85c",
    "font":       "#d9534f",
    "html":       "#337ab7",
    "json":       "#9b59b6",
    "video":      "#e67e22",
    "pdf":        "#c0392b",
    "other":      "#95a5a6",
}

# Status palette (good/medium/bad/neutral), used for GreenIT compliance badges,
# confidence levels and Core Web Vitals. Colors chosen for a contrast >= 4.5:1
# (WCAG AA) on white background (colored text) AND on colored background (white
# text) — the historical lighter shades (e.g.
# #0cce6b, #ffa400, #5bc0de) were below this threshold. An emoji always
# accompanies the status: color alone must never carry the information
# (accessibility: color blindness/screen reader/B&W printing).
STATUS_GOOD    = "#1e7e34"   # dark green — ✅
STATUS_WARN    = "#9a4d00"   # dark orange — ⚠️
STATUS_BAD     = "#c0392b"   # dark red — 🔴
STATUS_NEUTRAL = "#5a5a5a"   # darkish grey — ➖ (not measured / not applicable)
STATUS_EMOJI = {"good": "✅", "warn": "⚠️", "bad": "🔴", "neutral": "➖"}

# Matching light backgrounds ("chip" style: light background + border + colored
# text/emoji), used instead of the old saturated-background + white-text badges.
# A colored emoji (e.g. ✅ green Unicode, 🔴 red Unicode) becomes almost invisible
# on a saturated background of the SAME color (little emoji/background contrast);
# on a light background, the emoji keeps its own Unicode color and stays readable.
STATUS_BG = {
    "good": "#e8f5e9", "warn": "#fff3e0", "bad": "#fdecea", "neutral": "#eeeeee",
}


def _status_chip(status, text, extra_style=""):
    """Badge style "chip" (light background + border + colored text/emoji) for a
    good/warn/bad/neutral status. Contrast checked >= 4.5:1 (text on light background)
    AND emoji always visible (never placed on a background of its own color)."""
    color = {"good": STATUS_GOOD, "warn": STATUS_WARN, "bad": STATUS_BAD,
             "neutral": STATUS_NEUTRAL}[status]
    bg = STATUS_BG[status]
    emoji = STATUS_EMOJI[status]
    return (f'<span style="background:{bg};border:1.5px solid {color};color:{color};'
            f'font-weight:bold;padding:1px 8px;border-radius:4px;font-size:13px;'
            f'white-space:nowrap;{extra_style}">{emoji} {text}</span>')

# Known third-party tracker/analytics domains (merged with the
# "Analytics"/"Tag manager" categories of detect_tech.py — the two lists
# target the same scope but are maintained separately according to their use:
# here to count/quantify, in detect_tech.py to qualify the stack).
TRACKER_DOMAINS = {
    "google-analytics.com", "analytics.google.com", "googletagmanager.com",
    "hotjar.com", "segment.io", "mixpanel.com", "amplitude.com", "heap.io",
    "clarity.ms", "swetrix.org", "matomo.org", "plausible.io",
    "doubleclick.net", "facebook.net", "connect.facebook.net",
}
TRACKER_PATHS = {"/log/", "/log/hb", "/hb", "/ping", "/beacon", "/collect", "/track", "/event"}


def _is_tracker(host, url):
    """True if the host/path matches a known third-party tracker/analytics."""
    if host in TRACKER_DOMAINS or any(t in host for t in
            ("analytics", "swetrix", "gtm", "hotjar", "segment", "mixpanel", "clarity")):
        return True
    path = url.split("?")[0].lower()
    return any(p in path for p in TRACKER_PATHS)


# ── Agent EROOM version (source of truth: SKILL.md) ────────────────────────
_skill_md = Path(__file__).parent.parent / "SKILL.md"
AGENT_VERSION = "?.?.?"
if _skill_md.exists():
    for _line in _skill_md.read_text(encoding="utf-8").splitlines():
        if _line.startswith("version:"):
            AGENT_VERSION = _line.split(":", 1)[1].strip()
            break

# ── Imports EcoIndex ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from har_metrics import extract_page_metrics, load_cwv, ecoindex_score, ecoindex_grade, lcp_delta_s
from efootprint_model.user_time import nielsen_raw_seconds as _nielsen_raw_seconds


# ── Country names (display) ────────────────────────────────────────────────
# ISO-2 code -> English name, for the 30 countries of the
# iOS/macOS tables of collect_env_data.py. Purely cosmetic (the calculation uses
# the codes). An unknown country falls back to its raw code.
_COUNTRY_NAMES = {
    "FR": "France", "DE": "Germany", "GB": "United Kingdom", "IE": "Ireland",
    "NL": "Netherlands", "BE": "Belgium", "CH": "Switzerland", "AT": "Austria",
    "ES": "Spain", "IT": "Italy", "PT": "Portugal", "PL": "Poland",
    "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
    "RU": "Russia", "US": "United States", "CA": "Canada", "MX": "Mexico",
    "BR": "Brazil", "JP": "Japan", "KR": "South Korea", "CN": "China",
    "IN": "India", "AU": "Australia", "ZA": "South Africa", "SN": "Senegal",
    "TN": "Tunisia", "MA": "Morocco",
}


def _country_label(code):
    """'BR' -> 'Brazil (BR)'. Unknown code -> the code alone."""
    cc = (code or "").upper()
    name = _COUNTRY_NAMES.get(cc)
    return f"{name} ({cc})" if name else (cc or "?")


# ── HAR parsing ───────────────────────────────────────────────────────────────

def _classify_type(mime, url):
    mime = (mime or "").lower()
    url  = (url  or "").lower()
    # The extension is read on the PATH only: a versioned URL
    # (style.css?v=2026-6-10) or fragmented (app.js#x) keeps its extension but
    # no longer ends with it. Without this cleanup, those files fall into
    # "other" and disappear from the JS/CSS aggregates of the dead-code report.
    # Coverage entries are the only ones concerned in practice: HAR entries
    # carry a mimeType, tested before the extension.
    path = url.split("#", 1)[0].split("?", 1)[0]
    if "javascript" in mime or path.endswith(".js") or path.endswith(".mjs"):
        return "javascript"
    if "css" in mime or path.endswith(".css"):
        return "css"
    if "html" in mime:
        return "html"
    if "image" in mime or re.search(r'\.(png|jpg|jpeg|gif|svg|webp|ico|jxl)$', path):
        return "image"
    if "font" in mime or re.search(r'\.(woff2?|ttf|otf|eot)$', path):
        return "font"
    if "video" in mime or re.search(r'\.(mp4|webm|ogv|mov|avi)$', path):
        return "video"
    if "pdf" in mime or path.endswith(".pdf"):
        return "pdf"
    if "json" in mime or path.endswith(".json"):
        return "json"
    return "other"


def parse_har(har_path):
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)
    return har


def har_traffic_analysis(har_data):
    """Traffic analysis: domains, HTTP codes, top resources, duplicates."""
    entries = har_data.get("log", {}).get("entries", [])

    domains = defaultdict(int)
    http_codes = defaultdict(int)
    resources = []
    url_counts = defaultdict(int)
    # Store response headers per URL to analyze caching
    url_resp_headers = {}

    _FONT_DOMAINS  = {"fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net", "use.fontawesome.com"}

    def _dup_category(url, host, hdrs_resp):
        from urllib.parse import urlparse as _up
        path = _up(url).path.lower()
        # Tracker / analytics
        if _is_tracker(host, url):
            return "tracker", "Analytics/tracker request — normal behavior, intentional repeated sending"
        # External font
        if host in _FONT_DOMAINS or "font" in host:
            return "font", "External font — no browser cache between pages"
        # Static resource: check cache-control
        cc = hdrs_resp.get("cache-control", "")
        has_long_cache = "max-age" in cc and any(
            int(v) >= 3600 for v in re.findall(r"max-age=(\d+)", cc)
        ) if "max-age" in cc else False
        rtype = _classify_type("", url)
        if rtype in ("javascript", "css", "image", "font"):
            if has_long_cache:
                return "static_cached", "Static resource with long cache — reload due to multi-page journey (normal)"
            else:
                return "static_no_cache", "Static resource WITHOUT long cache — re-downloaded on every page, add Cache-Control: max-age"
        return "other", "URL called several times — check whether intentional"

    for e in entries:
        req  = e.get("request", {})
        resp = e.get("response", {})
        url  = req.get("url", "")
        status = resp.get("status", 0)
        size   = resp.get("content", {}).get("size", 0)
        mime   = resp.get("content", {}).get("mimeType", "")
        hdrs_resp = {h["name"].lower(): h["value"] for h in resp.get("headers", [])}

        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc
        except Exception:
            host = url[:40]

        domains[host] += 1
        http_codes[status] += 1
        url_counts[url] += 1
        resources.append({"url": url, "size": size, "mime": mime, "status": status, "host": host})
        if url not in url_resp_headers:
            url_resp_headers[url] = hdrs_resp

    # Deduplicate by URL before ranking (keep the max observed size)
    seen_urls = {}
    for r in resources:
        url_key = r["url"].split("?")[0]
        if url_key not in seen_urls or r["size"] > seen_urls[url_key]["size"]:
            seen_urls[url_key] = r
    top10 = sorted(seen_urls.values(), key=lambda x: x["size"], reverse=True)[:10]

    # Duplicates enriched with category and cause
    duplicates = []
    for u, c in url_counts.items():
        if c <= 1:
            continue
        try:
            host = urlparse(u).netloc
        except Exception:
            host = ""
        hdrs = url_resp_headers.get(u, {})
        cat, cause = _dup_category(u, host, hdrs)
        duplicates.append({"url": u, "count": c, "category": cat, "cause": cause})

    # Third-party trackers/scripts (Lot 2): request count + cumulative weight,
    # computed on the raw requests (not deduplicated by URL, to reflect the
    # real network traffic generated, tracking duplicates included).
    tracker_entries = [r for r in resources if _is_tracker(r["host"], r["url"])]
    total_size = sum(r["size"] for r in resources) or 1
    trackers = {
        "count": len(tracker_entries),
        "size_ko": round(sum(r["size"] for r in tracker_entries) / 1024, 1),
        "pct_requests": round(len(tracker_entries) / len(resources) * 100, 1) if resources else 0,
        "pct_size": round(sum(r["size"] for r in tracker_entries) / total_size * 100, 1),
        "domains": sorted({r["host"] for r in tracker_entries}),
    }

    return {
        "total_req": len(entries),
        "total_ko": round(sum(r["size"] for r in resources) / 1024, 1),
        "domains": dict(sorted(domains.items(), key=lambda x: -x[1])),
        "http_codes": dict(http_codes),
        "top10": top10,
        "duplicates": duplicates,
        "trackers": trackers,
    }


# ── Coverage parsing ──────────────────────────────────────────────────────────

def parse_coverage_file(cov_path):
    with open(cov_path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data if isinstance(data, list) else data.get("entries", [])
    results = []

    for item in entries:
        url    = item.get("url", "")
        text   = item.get("text", "") or ""
        ranges = item.get("ranges", [])
        total  = len(text)
        used   = sum(r["end"] - r["start"] for r in ranges
                      if r.get("end") is not None and r.get("start") is not None)
        unused = total - used
        pct    = round(unused / total * 100, 1) if total > 0 else 0.0
        mime   = item.get("mimeType", "")
        rtype  = _classify_type(mime, url)

        results.append({
            "url":        url,
            "filename":   url.split("/")[-1].split("?")[0][:60] or url[:60],
            "type":       rtype,
            "total_kb":   round(total / 1024, 1),
            "used_kb":    round(used / 1024, 1),
            "unused_kb":  round(unused / 1024, 1),
            "unused_pct": pct,
        })

    return results


def coverage_summary(entries):
    js  = [e for e in entries if e["type"] == "javascript"]
    css = [e for e in entries if e["type"] == "css"]

    def _agg(lst):
        total  = sum(e["total_kb"]  for e in lst)
        unused = sum(e["unused_kb"] for e in lst)
        pct    = round(unused / total * 100, 1) if total > 0 else 0.0
        return {"total_kb": round(total, 1), "unused_kb": round(unused, 1), "pct": pct}

    return {"js": _agg(js), "css": _agg(css), "all": _agg(entries)}


# ── Images: AVIF compression + base64 embedding ───────────────────────────

def embed_image(source, alt="", max_dim=500):
    """
    Compresses an image (URL or local path) to AVIF 500×500 max and returns
    the HTML <figure> block with the inline base64.

    Returns an empty HTML string if vipsthumbnail is not available or if
    the source is unreachable.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = Path(tmpdir) / "orig"
            avif = Path(tmpdir) / "out.avif"

            # Download or copy
            src = str(source)
            if src.startswith("http://") or src.startswith("https://"):
                urllib.request.urlretrieve(src, orig)
            else:
                orig = Path(source)
                if not orig.exists():
                    return ""

            # Original dimensions
            r = subprocess.run(
                ["vipsheader", "-f", "width", str(orig), "-f", "height", str(orig)],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                return ""
            dims = r.stdout.strip().split()
            orig_w, orig_h = (int(dims[0]), int(dims[1])) if len(dims) == 2 else (0, 0)

            # AVIF compression
            size_arg = f"{max_dim}x{max_dim}>"
            r2 = subprocess.run(
                ["vipsthumbnail", str(orig), "--size", size_arg,
                 "-o", f"{avif}[Q=60,effort=9,keep=none]"],
                capture_output=True
            )
            if r2.returncode != 0 or not avif.exists():
                return ""

            # Compressed dimensions
            r3 = subprocess.run(
                ["vipsheader", "-f", "width", str(avif), "-f", "height", str(avif)],
                capture_output=True, text=True
            )
            dims2 = r3.stdout.strip().split()
            comp_w, comp_h = (int(dims2[0]), int(dims2[1])) if len(dims2) == 2 else (orig_w, orig_h)

            b64 = base64.b64encode(avif.read_bytes()).decode()

        resized = (orig_w != comp_w or orig_h != comp_h) and orig_w > 0
        caption = (
            f"(For this report, image resized: {orig_w}×{orig_h} → {comp_w}×{comp_h} px and file lightened to AVIF format)"
            if resized else
            "(For this report: file lightened to AVIF format)"
        )
        return (
            f'<figure style="margin:0.75rem 0; text-align:center;">'
            f'<img src="data:image/avif;base64,{b64}" alt="{alt}" '
            f'style="max-width:100%; max-height:{max_dim}px; border:1px solid #e0e0e0; border-radius:4px;">'
            f'<figcaption style="font-size:0.78rem; color:#9e9e9e; margin-top:0.3rem;">{caption}</figcaption>'
            f'</figure>'
        )
    except Exception:
        return ""


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _html_head(title):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --octo-dark:  {OCTO_DARK};
    --octo-blue:  {OCTO_BLUE};
    --octo-light: {OCTO_LIGHT};
    --octo-pale:  {OCTO_PALE};
    --octo-grey:  {OCTO_GREY};
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; font-size: 18px; color: #222; background: #f9f9f9; }}
  header {{ background: var(--octo-dark); color: white; padding: 32px 40px 24px; }}
  header h1 {{ font-size: 28px; font-weight: bold; margin-bottom: 6px; }}
  header .meta {{ font-size: 16px; opacity: .75; margin-top: 8px; }}
  nav[role="navigation"] {{ background: var(--octo-pale); border-bottom: 2px solid var(--octo-blue);
    padding: 14px 40px; }}
  nav[role="navigation"] h2 {{ font-size: 17px; font-weight: bold; color: var(--octo-dark);
    margin-bottom: 8px; border: none; padding: 0; }}
  nav[role="navigation"] ul {{ display: flex; flex-wrap: wrap; align-items: flex-start; gap: 6px 20px; padding: 0;
    margin: 0; font-size: 17px; list-style: none; }}
  nav[role="navigation"] a {{ color: var(--octo-dark); text-decoration: none; }}
  nav[role="navigation"] a:hover {{ text-decoration: underline; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px; }}
  section {{ margin-bottom: 40px; }}
  h2 {{ font-size: 22px; color: var(--octo-dark); border-left: 4px solid var(--octo-blue);
        padding-left: 12px; margin-bottom: 16px; margin-top: 4px; }}
  h3 {{ font-size: 18px; color: var(--octo-dark); margin: 16px 0 8px; font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 17px; margin-bottom: 12px; }}
  th {{ background: var(--octo-dark); color: white; padding: 7px 10px; text-align: left; font-size: 16px; }}
  /* RGAA/WCAG: a link in a dark header must never keep the browser default blue/purple
     default (insufficient contrast on --octo-dark); white = ~14:1
     contrast (well above the required 4.5:1), underlined to stay distinguishable without
     depending on color alone. */
  th a {{ color: white; text-decoration: underline; }}
  th a:visited {{ color: white; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #ddd; }}
  tr:nth-child(even) td {{ background: var(--octo-pale); }}
  tr.alert td {{ background: #ffe0e0; }}
  tr.bold td {{ background: #dde8f0; font-weight: bold; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-weight: bold; font-size: 17px; color: white; min-width: 32px; text-align: center; }}
  .bar-wrap {{ display: flex; height: 16px; border-radius: 3px; overflow: hidden; width: 120px; }}
  .bar-used   {{ background: #50b450; }}
  .bar-unused {{ background: #dc5050; }}
  .kpi-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
  .kpi {{ background: var(--octo-pale); border: 1px solid var(--octo-blue); border-radius: 6px;
          padding: 14px 20px; min-width: 140px; }}
  .kpi .val {{ font-size: 26px; font-weight: bold; color: var(--octo-dark); }}
  .kpi .lbl {{ font-size: 15px; color: #555; margin-top: 2px; }}
  .prio {{ margin: 6px 0; padding: 10px 14px; border-radius: 4px; font-size: 17px; }}
  .prio-1 {{ background: #ffe0e0; border-left: 4px solid #dc3545; }}
  .prio-2 {{ background: #fff3cd; border-left: 4px solid #fd7e14; }}
  .prio-3 {{ background: #d4edda; border-left: 4px solid #28a745; }}
  .domain-tag {{ display: inline-block; background: var(--octo-grey); border-radius: 3px;
                 padding: 1px 6px; font-size: 15px; margin: 2px; }}
  footer {{ text-align: center; padding: 20px; font-size: 15px; color: #888;
            border-top: 1px solid #ddd; margin-top: 40px; }}
  @media print {{ body {{ background: white; }} header {{ -webkit-print-color-adjust: exact; }} }}
</style>
</head>
<body>
"""


def _badge(grade, color):
    return f'<span class="badge" style="background:{color}">{grade}</span>'


def _bar(used_pct):
    unused_pct = 100 - used_pct
    return (f'<div class="bar-wrap">'
            f'<div class="bar-used" style="width:{used_pct:.0f}%"></div>'
            f'<div class="bar-unused" style="width:{unused_pct:.0f}%"></div>'
            f'</div>')


def _normalize_page_url(url):
    """Shared normalization of a page URL: no query string, no trailing slash.
    Used to deduplicate `page_metrics` (1st-party fallback/HAR dedup)
    and to match `page_url` (from `reductions_detail`, raw) to the
    corresponding `page_metrics` entries."""
    return url.split("?")[0].rstrip("/") or url


def _dedup_page_metrics(page_metrics):
    """Deduplicates by canonical URL: keeps the row with a successful measurement (status ok), else the heaviest.
    Adds a page_num field (1-indexed) in order of first appearance."""
    seen = {}
    order = []
    for m in page_metrics:
        url = _normalize_page_url(m["title"])
        prev = seen.get(url)
        if prev is None:
            seen[url] = m
            order.append(url)
        else:
            # Prefer the successful measurement (status ok) over a failed one
            m_ok = m.get("measurement", {}).get("status") == "ok"
            prev_ok = prev.get("measurement", {}).get("status") == "ok"
            if m_ok and not prev_ok:
                seen[url] = m
            elif m_ok and prev_ok and m["req"] > prev["req"]:
                seen[url] = m
            elif not m_ok and not prev_ok and m["req"] > prev["req"]:
                seen[url] = m
    result = []
    for i, url in enumerate(order, 1):
        m = dict(seen[url])
        m["page_num"] = i
        result.append(m)
    return result


def _cwv_for_page(m, cwv):
    """Looks up the CWV data of a page (dict grouped by strategy).

    Returns {"mobile": row, "desktop": row} (keys possibly absent),
    by URL (normalized) first, then by page_id."""
    url = m.get("title", "").rstrip("/")
    return cwv.get(url) or cwv.get(m["page_id"], {})


def _cwv_device_marker(strat):
    """Device pictogram to annotate which device a retained value comes from."""
    return "📱" if strat == "mobile" else "🖥"


def _cwv_worst_per_metric(by_strategy):
    """Composes a synthetic row taking, for EACH metric (lcp/inp/cls),
    the WORST value among the available strategies (mobile / desktop).

    For the three CWVs, "worst" = highest value (LCP/INP/CLS: higher =
    worse). On a tie, mobile wins (dominant traffic + most
    constraining conditions).

    Returns (row, strat_by_metric) where:
      - row = {"lcp": .., "inp": .., "cls": ..} (keys present only if measured) ;
      - strat_by_metric = {"lcp": "mobile"|"desktop", ...} indicating the device
        retained for each metric.
    Returns (None, {}) if no usable data."""
    if not by_strategy:
        return None, {}
    row = {}
    strat_by_metric = {}
    for metric in ("lcp", "inp", "cls"):
        best_strat = None
        best_val = None
        for strat in ("mobile", "desktop"):  # mobile first => wins on a tie
            r = by_strategy.get(strat)
            if not r:
                continue
            v = r.get(metric)
            if not isinstance(v, (int, float)):
                continue
            if best_val is None or v > best_val:
                best_val = v
                best_strat = strat
        if best_strat is not None:
            row[metric] = best_val
            strat_by_metric[metric] = best_strat
    if not row:
        return None, {}
    return row, strat_by_metric


# Readable labels of CWV sources (distinguishes field / lab API / local lab).
_CWV_SOURCE_LABELS = {
    "crux": ("field", STATUS_GOOD, "CrUX field (real Chrome users, via PageSpeed)"),
    "pagespeed_lab": ("lab", STATUS_WARN, "Lab PageSpeed (simulation via the PSI API)"),
    "lighthouse": ("local lab", STATUS_WARN, "Lab Lighthouse (local simulation)"),
}


_STATUS_BY_COLOR = {STATUS_GOOD: "good", STATUS_WARN: "warn", STATUS_NEUTRAL: "neutral"}


def _cwv_source_badge(source):
    """Small badge indicating the real source of a CWV measurement ("chip" style)."""
    label, color, _ = _CWV_SOURCE_LABELS.get(source, ("?", STATUS_NEUTRAL, "Unknown source"))
    bg = STATUS_BG[_STATUS_BY_COLOR.get(color, "neutral")]
    return (f'<span style="display:inline-block;font-size:13px;padding:1px 7px;'
            f'border-radius:10px;background:{bg};border:1.5px solid {color};'
            f'color:{color};font-weight:bold">{label}</span>')


def _section_dashboard(page_metrics, cwv):
    deduped = _dedup_page_metrics(page_metrics)
    rows = ""
    for m in deduped:
        badge = _badge(m["grade"], m["grade_color"])
        url = m["title"]
        from urllib.parse import urlparse
        parsed = urlparse(url)
        short = parsed.path.rstrip("/") or "/"
        num = m.get("page_num", "")
        page_cell = f'<a href="{url}" target="_blank" rel="noopener" title="{url}"><span style="color:#888;font-size:15px;margin-right:4px">P{num}</span>{short}</a>'
        # Dashboard = "worst of both" per metric (mobile or desktop, the worst).
        cwv_data, worst_strat = _cwv_worst_per_metric(_cwv_for_page(m, cwv))

        def _cwv_cell(val, unit, thresholds, strat=None):
            # thresholds = (good_max, needs_improvement_max)
            if not isinstance(val, (int, float)):
                return f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'
            if val <= thresholds[0]:
                color, emoji = STATUS_GOOD, STATUS_EMOJI["good"]
            elif val <= thresholds[1]:
                color, emoji = STATUS_WARN, STATUS_EMOJI["warn"]
            else:
                color, emoji = STATUS_BAD, STATUS_EMOJI["bad"]
            # Pictogram indicating the device the retained value comes from (worst of the two)
            marker = (f'<span style="color:#999;font-size:12px;margin-right:3px" '
                      f'title="most unfavorable value: {strat}">{_cwv_device_marker(strat)}</span>'
                      if strat else "")
            return (f'<td style="text-align:right;color:{color};font-weight:bold">'
                    f'{emoji} {marker}{val} {unit}</td>')

        if cwv_data:
            lcp_val = cwv_data.get("lcp")
            inp_val = cwv_data.get("inp")
            cls_num = cwv_data.get("cls")
            lcp_cell = _cwv_cell(lcp_val, "s", (1.8, 2.5), worst_strat.get("lcp"))
            inp_cell = _cwv_cell(inp_val, "ms", (200, 500), worst_strat.get("inp"))
            cls_cell = _cwv_cell(cls_num, "", (0.1, 0.25), worst_strat.get("cls"))
        else:
            lcp_cell = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">{m["on_load_ms"]} ms *</td>'
            inp_cell = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'
            cls_cell = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'

        # EcoIndex and DOM display: "not measured" if the measurement failed
        measured_ok = m.get("measurement", {}).get("status") == "ok"
        if measured_ok:
            ecoindex_cell = f'<td style="text-align:center">{badge} {m["ecoindex"]}/100</td>'
            dom_cell = f'<td style="text-align:right">{m["dom"]}</td>'
        else:
            ecoindex_cell = f'<td style="text-align:center;color:{STATUS_NEUTRAL}">not measured</td>'
            dom_cell = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">not measured</td>'

        rows += f"""<tr>
      <td>{page_cell}</td>
      {ecoindex_cell}
      <td style="text-align:right">{m['req']}</td>
      <td style="text-align:right">{m['size_ko']:.0f} KB</td>
      {dom_cell}
      {lcp_cell}{inp_cell}{cls_cell}
    </tr>"""

    cwv_legend = f"""<div style="font-size:15px;margin-top:8px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">
    <span style="font-weight:bold;color:#555">CWV legend:</span>
    <span style="color:{STATUS_GOOD}">{STATUS_EMOJI['good']} Good</span>
    <span style="color:{STATUS_WARN}">{STATUS_EMOJI['warn']} Needs improvement</span>
    <span style="color:{STATUS_BAD}">{STATUS_EMOJI['bad']} Poor</span>
    <span style="color:#999">📱/🖥 device of the most unfavorable value (worst of both per metric)</span>
    <span style="color:{STATUS_NEUTRAL};font-style:italic">{STATUS_EMOJI['neutral']} Field data unavailable (provide cwv.json)</span>
  </div>"""
    cwv_note = "" if cwv else '<p style="font-size:15px;color:#888;margin-top:6px">* LCP = onLoad HAR (proxy). INP and CLS need field data (PageSpeed API or cwv.json).</p>'

    return f"""<section id="dashboard">
  <h2>EcoIndex and CWV dashboard (Core Web Vitals)</h2>
  <table>
    <thead><tr>
      <th>Page</th><th>{_glossary_link("EcoIndex")}</th><th>Requests</th>
      <th>Weight</th><th>{_glossary_link("DOM")}</th><th>{_glossary_link("LCP")}</th><th>{_glossary_link("INP")}</th><th>{_glossary_link("CLS")}</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {cwv_legend}
  {cwv_note}
</section>"""


def _section_traffic(traffic):
    domains_html = "".join(
        f'<span class="domain-tag">{d} <b>({c})</b></span>'
        for d, c in list(traffic["domains"].items())[:15]
    )

    CODE_LABELS = {
        200: ("Success", "Resource loaded normally"),
        201: ("Created", "API request accepted (POST)"),
        204: ("No content", "Empty response, often analytics pings"),
        206: ("Partial", "Partial content (streaming, range request)"),
        301: ("Permanent redirect", "URL moved permanently"),
        302: ("Temporary redirect", "URL redirected (e.g. /jobs → /jobs/)"),
        304: ("Not modified (cache)", "Resource in browser cache, not re-downloaded"),
        400: ("Bad request", "Client-side error"),
        401: ("Unauthorized", "Access denied, authentication required"),
        403: ("Forbidden", "Server blocks the request"),
        404: ("Not found", "Resource missing on the server"),
        500: ("Server error", "Server-side problem"),
        503: ("Service unavailable", "Server temporarily out of service"),
    }
    codes_rows = ""
    for k, v in sorted(traffic["http_codes"].items()):
        color = "green" if k < 300 else ("orange" if k < 400 else "red")
        label, desc = CODE_LABELS.get(k, ("", ""))
        codes_rows += (
            f'<tr>'
            f'<td><b style="color:{color}">{k}</b></td>'
            f'<td style="text-align:right"><b>{v}</b></td>'
            f'<td>{label}</td>'
            f'<td style="color:#555;font-size:16px">{desc}</td>'
            f'</tr>'
        )
    codes_html = f"""<table style="border-collapse:collapse;width:100%">
  <thead><tr>
    <th style="text-align:left;width:60px">Code</th>
    <th style="text-align:right;width:50px">Count</th>
    <th style="text-align:left;width:160px">Status</th>
    <th style="text-align:left">Meaning</th>
  </tr></thead>
  <tbody>{codes_rows}</tbody>
</table>"""

    top_rows = ""
    for r in traffic["top10"]:
        fname = r["url"].split("/")[-1].split("?")[0][:50] or r["url"][:50]
        color = TYPE_COLORS.get(_classify_type(r["mime"], r["url"]), "#999")
        top_rows += f"""<tr>
      <td><a href="{r['url']}" target="_blank" rel="noopener" title="{r['url']}">{fname}</a></td>
      <td><span style="color:{color}">{_classify_type(r['mime'], r['url'])}</span></td>
      <td style="text-align:right">{round(r['size']/1024, 1)} KB</td>
      <td style="color:#555;font-size:15px">{r['host']}</td>
    </tr>"""

    # Duplicate categories: color + short label
    _CAT_META = {
        "tracker":        ("#5a3494", "#f0e9fa", "🔗 Tracker / analytics"),
        "font":           ("#a83232", "#fbe9e9", "🔤 External font"),
        "static_no_cache":("#a72834", "#fbe9e9", "🔴 Static without cache"),
        "static_cached":  (STATUS_GOOD, STATUS_BG["good"], "✅ Static with cache"),
        "other":          (STATUS_NEUTRAL, STATUS_BG["neutral"], "➖ Other"),
    }

    dup_section = ""
    dups = traffic["duplicates"]
    if dups:
        # Group by category
        from collections import OrderedDict
        groups = OrderedDict()
        for cat in _CAT_META:
            groups[cat] = [d for d in dups if d.get("category") == cat]

        # Duplicate KPIs
        nb_problematic = sum(1 for d in dups if d.get("category") in ("static_no_cache", "other"))
        nb_tracker     = sum(1 for d in dups if d.get("category") == "tracker")
        nb_font        = sum(1 for d in dups if d.get("category") == "font")

        dup_kpis = (
            f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px;font-size:16px">'
            f'<span style="background:#fbe9e9;border:1.5px solid #a72834;color:#a72834;font-weight:bold;padding:2px 8px;border-radius:4px">🔴 <b>{nb_problematic}</b> to fix (no cache)</span>'
            f'<span style="background:#f0e9fa;border:1.5px solid #5a3494;color:#5a3494;font-weight:bold;padding:2px 8px;border-radius:4px">🔗 <b>{nb_tracker}</b> trackers (normal)</span>'
            f'<span style="background:#fbe9e9;border:1.5px solid #a83232;color:#a83232;font-weight:bold;padding:2px 8px;border-radius:4px">🔤 <b>{nb_font}</b> external fonts</span>'
            f'</div>'
        )

        # Table per group
        dup_tables = ""
        for cat, items in groups.items():
            if not items:
                continue
            cat_color, cat_bg, cat_label = _CAT_META[cat]
            # Cause (identical for the whole group)
            cause = items[0].get("cause", "")
            rows_html = ""
            for d in sorted(items, key=lambda x: -x["count"]):
                fname = d["url"].split("/")[-1].split("?")[0][:70] or d["url"][:70]
                rows_html += (
                    f'<tr>'
                    f'<td><a href="{d["url"]}" target="_blank" rel="noopener" title="{d["url"]}">{fname}</a></td>'
                    f'<td style="text-align:center;font-weight:bold;color:{cat_color}">{d["count"]}×</td>'
                    f'</tr>'
                )
            dup_tables += (
                f'<details style="margin-bottom:8px" {"open" if cat == "static_no_cache" else ""}>'
                f'<summary style="cursor:pointer;font-weight:bold;font-size:17px;padding:6px 0">'
                f'<span style="background:{cat_bg};border:1.5px solid {cat_color};color:{cat_color};font-weight:bold;padding:1px 7px;border-radius:4px;font-size:16px;margin-right:6px">{cat_label}</span>'
                f'{len(items)} URL(s) — <span style="font-weight:normal;color:#555;font-size:16px">{cause}</span>'
                f'</summary>'
                f'<table style="margin-top:6px">'
                f'<thead><tr><th>File</th><th style="width:50px">Count</th></tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                f'</table>'
                f'</details>'
            )

        dup_section = f'<h3 id="trafic-doublons">Duplicate requests ({len(dups)} URL(s))</h3>{dup_kpis}{dup_tables}'

    tr = traffic.get("trackers") or {}
    trackers_section = ""
    if tr.get("count", 0) > 0:
        tr_domains_html = "".join(f'<span class="domain-tag">{d}</span>' for d in tr.get("domains", [])[:10])
        trackers_section = f"""<h3 id="trafic-trackers">Trackers and third-party scripts</h3>
  <div class="kpi-grid" style="margin-bottom:8px">
    <div class="kpi"><div class="val">{tr['count']}</div><div class="lbl">Tracker requests ({tr['pct_requests']}% of total)</div></div>
    <div class="kpi"><div class="val">{tr['size_ko']:.0f} KB</div><div class="lbl">Tracker weight ({tr['pct_size']}% of total)</div></div>
  </div>
  <div style="margin-bottom:8px">{tr_domains_html}</div>
  <p style="font-size:15px;color:#888">For reference, third-party trackers typically add 20 to 100 HTTP requests per page (source: web tracking studies) — a figure to compare with the measurement above.</p>
"""

    return f"""<section id="traffic">
  <h2>Network traffic</h2>
  <div class="kpi-grid">
    <div class="kpi"><div class="val">{traffic['total_req']}</div><div class="lbl">Total requests</div></div>
    <div class="kpi"><div class="val">{traffic['total_ko']:.0f} KB</div><div class="lbl">Transferred volume</div></div>
    <div class="kpi"><div class="val">{len(traffic['domains'])}</div><div class="lbl">Domains</div></div>
  </div>
  {trackers_section}
  <h3>Contacted domains</h3>
  <div style="margin-bottom:12px">{domains_html}</div>
  <h3>HTTP codes</h3>
  <div style="margin-bottom:16px">{codes_html}</div>
  <h3>Top 10 heaviest resources</h3>
  <table>
    <thead><tr><th>File</th><th>Type</th><th>Weight</th><th>Domain</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>
  {dup_section}
</section>"""


def _section_coverage(coverage_by_page):
    html = '<section id="coverage">\n  <h2>Dead code (Coverage JS/CSS)</h2>\n'

    for page_name, page_data in coverage_by_page.items():
        entries = page_data["entries"] if isinstance(page_data, dict) else page_data
        page_url = page_data.get("url", "") if isinstance(page_data, dict) else ""
        if not entries:
            continue
        summ = coverage_summary(entries)
        h3_label = (f'<a href="{page_url}" target="_blank" rel="noopener" title="{page_url}">{page_name}</a>'
                    if page_url else page_name)
        html += f'  <h3>{h3_label}</h3>\n'

        # Gauges
        js_used = 100 - summ["js"]["pct"] if summ["js"]["total_kb"] else 0
        css_used = 100 - summ["css"]["pct"] if summ["css"]["total_kb"] else 0
        html += f"""  <div style="display:flex;gap:24px;margin-bottom:10px;align-items:center">
    <div>JS {_bar(js_used)} <span style="font-size:16px">{summ['js']['unused_kb']} KB unused ({summ['js']['pct']}%)</span></div>
    <div>CSS {_bar(css_used)} <span style="font-size:16px">{summ['css']['unused_kb']} KB unused ({summ['css']['pct']}%)</span></div>
  </div>\n"""

        # Top files
        top = sorted(entries, key=lambda e: e["unused_kb"], reverse=True)[:8]
        rows = ""
        for e in top:
            color = TYPE_COLORS.get(e["type"], "#999")
            rows += f"""<tr>
      <td><a href="{e['url']}" target="_blank" rel="noopener" title="{e['url']}">{e['filename']}</a></td>
      <td style="color:{color}">{e['type']}</td>
      <td style="text-align:right">{e['total_kb']} KB</td>
      <td style="text-align:right;color:#dc5050">{e['unused_kb']} KB</td>
      <td style="text-align:right">{e['unused_pct']}%</td>
      <td>{_bar(100 - e['unused_pct'])}</td>
    </tr>"""
        html += f"""  <table>
    <thead><tr><th>File</th><th>Type</th><th>Total</th><th>Unused</th><th>%</th><th></th></tr></thead>
    <tbody>{rows}</tbody>
  </table>\n"""

    html += "</section>\n"
    return html


def _cwv_colored(val, unit, thresholds):
    if not isinstance(val, (int, float)):
        return f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'
    if val <= thresholds[0]:
        color, emoji = STATUS_GOOD, STATUS_EMOJI["good"]
    elif val <= thresholds[1]:
        color, emoji = STATUS_WARN, STATUS_EMOJI["warn"]
    else:
        color, emoji = STATUS_BAD, STATUS_EMOJI["bad"]
    return f'<td style="text-align:right;color:{color};font-weight:bold">{emoji} {val} {unit}</td>'


def _section_cwv(page_metrics, cwv):
    if not cwv:
        return ""

    deduped = _dedup_page_metrics(page_metrics)
    from urllib.parse import urlparse
    rows = ""
    for m in deduped:
        by_strat = _cwv_for_page(m, cwv)
        url = m["title"]
        parsed = urlparse(url)
        short = parsed.path.rstrip("/") or "/"
        num = m.get("page_num", "")
        page_cell = f'<a href="{url}" target="_blank" rel="noopener" title="{url}"><span style="color:#888;font-size:15px;margin-right:4px">P{num}</span>{short}</a>'

        # One sub-row per available device (mobile then desktop)
        strats = [s for s in ("mobile", "desktop") if by_strat.get(s)]
        if not strats:
            na = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'
            rows += f"""<tr>
      <td>{page_cell}</td>
      <td style="color:{STATUS_NEUTRAL}">—</td>
      {na}{na}{na}
    </tr>"""
            continue
        for i, strat in enumerate(strats):
            c = by_strat[strat]
            device_label = "📱 Mobile" if strat == "mobile" else "🖥 Desktop"
            device_cell = f'{device_label} {_cwv_source_badge(c.get("source"))}'
            lcp_cell = _cwv_colored(c.get("lcp"), "s", (1.8, 2.5))
            inp_cell = _cwv_colored(c.get("inp"), "ms", (200, 500))
            cls_cell = _cwv_colored(c.get("cls"), "", (0.1, 0.25))
            # The "Page" cell is only displayed on the 1st sub-row (rowspan)
            first_cell = f'<td rowspan="{len(strats)}">{page_cell}</td>' if i == 0 else ""
            rows += f"""<tr>
      {first_cell}
      <td>{device_cell}</td>
      {lcp_cell}{inp_cell}{cls_cell}
    </tr>"""

    legend = f"""<div style="font-size:15px;margin-top:8px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">
    <span style="font-weight:bold;color:#555">Legend:</span>
    <span style="color:{STATUS_GOOD}">{STATUS_EMOJI['good']} Good</span>
    <span style="color:{STATUS_WARN}">{STATUS_EMOJI['warn']} Needs improvement</span>
    <span style="color:{STATUS_BAD}">{STATUS_EMOJI['bad']} Poor</span>
    <span style="color:#888">Definitions and thresholds: see the <a href="#glossaire">Glossary</a> (Appendices)</span>
  </div>"""

    methodology_note = _cwv_methodology_note(cwv)

    return f"""<section id="cwv">
  <h2>Core Web Vitals</h2>
  {methodology_note}
  <table>
    <thead><tr><th>Page</th><th>Device</th><th>{_glossary_link("LCP")}</th><th>{_glossary_link("INP")}</th><th>{_glossary_link("CLS")}</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {legend}
</section>"""


def _cwv_methodology_note(cwv):
    """CWV methodology note, adapted to the sources ACTUALLY present.

    Distinguishes the 3 sources (crux field / pagespeed_lab / local lighthouse)
    instead of confusing crux and pagespeed_lab under 'manual field'."""
    sources = {row.get("source")
               for by_strat in cwv.values() if isinstance(by_strat, dict)
               for row in by_strat.values() if row}
    present = [s for s in ("crux", "pagespeed_lab", "lighthouse") if s in sources]
    src_lines = "".join(
        f'<li><strong>{_CWV_SOURCE_LABELS[s][0]}</strong> : {_CWV_SOURCE_LABELS[s][2]}</li>'
        for s in present
    ) or '<li>Source not provided</li>'

    has_lab = bool(sources & {"pagespeed_lab", "lighthouse"})
    has_field = "crux" in sources
    color = STATUS_GOOD if has_field and not has_lab else STATUS_WARN
    bg = "#e8f5e9" if has_field and not has_lab else "#fff8e1"

    lab_caveat = ""
    if has_lab:
        lab_caveat = ('<span style="color:#888;margin-top:6px;display:block">'
                      'Lab measurements are simulations (throttled network/CPU). Real field values '
                      'are often better, especially on desktop and fast connections. '
                      'Pages requiring authentication are analyzed without a session: the '
                      'metrics then reflect the login page, not the target page.</span>')
    field_caveat = ""
    if has_field:
        field_caveat = ('<span style="color:#888;margin-top:6px;display:block">'
                        'CrUX field data only covers Chrome users: iOS/Safari are '
                        'not measured (see methodology appendix).</span>')

    return (f'<div style="background:{bg};border-left:3px solid {color};padding:10px 14px;'
            f'margin-bottom:14px;font-size:16px;color:#555;border-radius:0 4px 4px 0">'
            f'<strong>Methodology note - measurement sources</strong>'
            f'<ul style="margin:6px 0 0 16px;padding:0">{src_lines}</ul>'
            f'{field_caveat}{lab_caveat}</div>')


CWV_ACTIONS = {
    "lcp_warn": "The page's main element (often the hero image or block) takes a "
                "little too long to appear. Check: is this image/block loaded "
                "with priority, or does a script/another resource delay it?",
    "lcp_bad":  "The page's main element (hero image or block) takes too long to "
                "appear. Likely causes: image not preloaded, unoptimized formats, "
                "lazy loading wrongly enabled on the hero, or a render-blocking script.",
    "inp_warn": "The main thread takes a little time to respond after a click or tap. "
                "Likely cause: event handlers or JS processing that delay "
                "the response.",
    "inp_bad":  "The main thread takes too long to respond after an interaction "
                "(click, tap). Likely cause: long JS tasks or heavy event "
                "handlers saturating the main thread.",
    "cls_warn": "Page elements shift slightly after the initial display. "
                "Likely cause: images, iframes or fonts without reserved dimensions.",
    "cls_bad":  "Page elements shift noticeably after the initial display, "
                "disrupting reading. Likely cause: images/iframes without reserved "
                "dimensions, or content injected late into the page.",
}

_CWV_THRESHOLDS = {"lcp": (1.8, 2.5), "inp": (200, 500), "cls": (0.1, 0.25)}
_CWV_UNITS = {"lcp": "s", "inp": "ms", "cls": ""}
_CIRCLED_DIGITS = "①②③④⑤⑥⑦⑧⑨⑩"


def _cwv_status(metric, val):
    """Returns (status, color) for a given CWV metric value."""
    lo, hi = _CWV_THRESHOLDS[metric]
    if val > hi:
        return "bad", STATUS_BAD
    if val > lo:
        return "warn", STATUS_WARN
    return "good", STATUS_GOOD


def _cwv_fmt_value(metric, val):
    if metric == "cls":
        return f"{val:.2f}"
    if metric == "lcp":
        return f"{val:.1f} {_CWV_UNITS[metric]}"
    return f"{int(round(val))} {_CWV_UNITS[metric]}"


def _cwv_diagnostic_signal(action_key, traffic, greenit, coverage_by_page):
    """Lot 5: cross-references the detected CWV problem with already collected
    data (trackers, external fonts, heaviest resource, unused JS) to
    name a likely cause rather than a generic message. Returns an
    additional sentence (cautious wording: "indicative signal", no
    certainty) or an empty string if no usable signal is available.
    """
    metric = action_key.split("_")[0]
    agg = (greenit or {}).get("aggregated", {}) or {}

    if metric == "cls":
        signals = []
        trackers = (traffic or {}).get("trackers") or {}
        if trackers.get("count"):
            signals.append(f"{trackers['count']} third-party tracker/script request(s) detected")
        fonts = agg.get("UseStandardTypefaces", {}).get("evidence") or []
        if fonts:
            signals.append(f"external web font(s) detected ({', '.join(fonts[:2])})"),
        if signals:
            return (f"Indicative signal: {' and '.join(signals)}, likely to inject "
                    f"content late into the page (widgets, font fallback) — to check "
                    f"as a possible cause of the shift.")
        return ""

    if metric == "lcp":
        top10 = (traffic or {}).get("top10") or []
        for r in top10:
            rtype = _classify_type(r.get("mime", ""), r.get("url", ""))
            if rtype in ("image", "font"):
                ko = round(r["size"] / 1024, 1)
                return (f"Indicative signal: the heaviest resource of the journey is "
                        f"a {rtype} of {ko} KB ({r.get('host', '')}) — check whether it "
                        f"matches the LCP element of the page concerned.")
        return ""

    if metric == "inp":
        if coverage_by_page:
            heavy_pages = [
                label for label, pd in coverage_by_page.items()
                if coverage_summary(pd["entries"] if isinstance(pd, dict) else pd)["js"]["pct"] > 60
            ]
            if heavy_pages:
                return (f"Indicative signal: unused JS rate &gt; 60 % found on "
                        f"{len(heavy_pages)} page(s) (see Coverage in appendix) — possible "
                        f"cause of main-thread overload, without certainty about the JS "
                        f"actually executed at runtime.")
        return ""

    return ""


def _section_cwv_analyse(page_metrics, cwv, traffic=None, greenit=None, coverage_by_page=None):
    if not cwv:
        return ""

    from urllib.parse import urlparse

    deduped = _dedup_page_metrics(page_metrics)

    methodology_note = _cwv_methodology_note(cwv)

    legend = f"""<div style="font-size:15px;margin-top:16px;display:flex;gap:16px;align-items:center">
    <span style="font-weight:bold;color:#555">Legend:</span>
    <span style="color:{STATUS_GOOD}">{STATUS_EMOJI['good']} Good</span>
    <span style="color:{STATUS_WARN}">{STATUS_EMOJI['warn']} Needs improvement</span>
    <span style="color:{STATUS_BAD}">{STATUS_EMOJI['bad']} Poor</span>
    <span style="color:{STATUS_NEUTRAL}">{STATUS_EMOJI['neutral']} Not measured</span>
  </div>"""

    # Numbering of problem types (①②③...), assigned in order of
    # first appearance while scanning the table page by page, metric by
    # metric — the same problem type (e.g. "lcp_warn") keeps the same number
    # everywhere, even when it affects several pages/devices.
    problem_order = []
    problem_number = {}

    def _note_number(action_key):
        if action_key not in problem_number:
            problem_order.append(action_key)
            problem_number[action_key] = len(problem_order)
        return problem_number[action_key]

    def _render_value(metric, strat, val):
        """Renders a value line (status emoji + device emoji + value +
        numbered marker if degraded). Returns (html, status)."""
        status, color = _cwv_status(metric, val)
        status_emoji = STATUS_EMOJI.get(status, "")
        marker = f'{status_emoji} {_cwv_device_marker(strat)}'
        txt = _cwv_fmt_value(metric, val)
        sup = ""
        if status in ("bad", "warn"):
            n = _note_number(f"{metric}_{status}")
            sup = f'<sup style="font-size:11px;color:#000">{_CIRCLED_DIGITS[n - 1]}</sup>'
        return marker, txt, sup, status, color

    def _render_cell(metric, by_strat):
        row_worst, strat_by_metric = _cwv_worst_per_metric(by_strat)
        worst_strat = strat_by_metric.get(metric) if strat_by_metric else None
        if worst_strat is None:
            return f'<span style="color:{STATUS_NEUTRAL}" title="Not measured">{STATUS_EMOJI["neutral"]}</span>'

        marker_w, txt_w, sup_w, status_w, color_w = _render_value(metric, worst_strat, row_worst[metric])
        line1 = f'<div><b style="color:{color_w}">{marker_w} {txt_w}</b>{sup_w}</div>'

        other_strat = "desktop" if worst_strat == "mobile" else "mobile"
        other_row = by_strat.get(other_strat)
        line2 = ""
        if other_row and isinstance(other_row.get(metric), (int, float)):
            marker_o, txt_o, sup_o, status_o, color_o = _render_value(metric, other_strat, other_row[metric])
            style_o = f"color:{color_o};font-weight:bold"
            line2 = f'<div style="font-size:14px;{style_o}">{marker_o} {txt_o}{sup_o}</div>'
        elif other_row and (measurement := other_row.get("measurement", {})).get("status") not in (None, "ok"):
            # Measurement attempted but failed (e.g. network timeout): say it
            # rather than let it disappear silently (cf. absence != failure).
            detail = measurement.get("detail", "")
            title_attr = f' title="{detail}"' if detail else ""
            marker_fail = _cwv_device_marker(other_strat)
            line2 = (f'<div style="font-size:14px;color:{STATUS_NEUTRAL}"{title_attr}>'
                      f'{marker_fail} measurement failed</div>')
        return line1 + line2

    rows = ""
    for m in deduped:
        by_strat = _cwv_for_page(m, cwv)
        url = m["title"]
        parsed = urlparse(url)
        short = parsed.path.rstrip("/") or "/"
        num = m.get("page_num", "")

        # Ignore strategies whose measurement failed (no "source"):
        # otherwise a network failure on a single strategy (e.g. mobile) wipes
        # the source badge of the strategy actually used by the other.
        sources = {s for r in by_strat.values() if r and (s := r.get("source"))}
        page_badge = _cwv_source_badge(next(iter(sources))) if len(sources) == 1 else ""

        if by_strat:
            lcp_cell = _render_cell("lcp", by_strat)
            inp_cell = _render_cell("inp", by_strat)
            cls_cell = _render_cell("cls", by_strat)
        else:
            not_measured = f'<span style="color:{STATUS_NEUTRAL}" title="Not measured">{STATUS_EMOJI["neutral"]}</span>'
            lcp_cell = inp_cell = cls_cell = not_measured

        rows += (
            '<tr style="border-bottom:1px solid #eee">'
            f'<td style="padding:8px;white-space:nowrap">'
            f'<span style="color:#888;font-size:14px;margin-right:4px">P{num}</span>'
            f'<a href="{url}" target="_blank" rel="noopener" style="color:inherit">{short}</a>'
            f' {page_badge}</td>'
            f'<td style="padding:8px;text-align:center">{lcp_cell}</td>'
            f'<td style="padding:8px;text-align:center">{inp_cell}</td>'
            f'<td style="padding:8px;text-align:center">{cls_cell}</td>'
            '</tr>'
        )

    table = f"""<table style="width:100%;border-collapse:collapse;margin-top:10px">
    <thead><tr style="background:#E0F0F4">
      <th style="padding:8px;text-align:left">Page</th>
      <th style="padding:8px">{_glossary_link("LCP")}</th>
      <th style="padding:8px">{_glossary_link("INP")}</th>
      <th style="padding:8px">{_glossary_link("CLS")}</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>"""

    legend_notes = ""
    if problem_order:
        def _note_html(key):
            signal = _cwv_diagnostic_signal(key, traffic, greenit, coverage_by_page)
            extra = f' <span style="color:#888">{signal}</span>' if signal else ""
            return f"{CWV_ACTIONS[key]}{extra}"
        items = "".join(
            f'<li><sup style="color:#000">{_CIRCLED_DIGITS[i]}</sup> {_note_html(key)}</li>'
            for i, key in enumerate(problem_order)
        )
        legend_notes = (
            '<div style="font-size:15px;margin-top:10px;color:#555">'
            f'<ul style="margin:4px 0 0 16px;padding:0;line-height:1.6">{items}</ul>'
            '</div>'
        )

    return f"""<section id="cwv-analyse">
  <h2>Core Web Vitals analysis</h2>
  {methodology_note}
  {table}
  {legend}
  {legend_notes}
</section>"""


GREENIT_RULES = {
    "AddExpiresOrCacheControlHeaders": {
        "name": "Add expires or cache-control headers (>= 95%)",
        "description": "Configure headers so CSS, JS and images are cached as long as possible.",
    },
    "CompressHttp": {
        "name": "Compress resources (>= 95%)",
        "description": "Enable gzip/Deflate. Pre-compress static resources; on-the-fly compression suits dynamic HTML.",
    },
    "DomainsNumber": {
        "name": "Limit the number of domains (< 3)",
        "description": "Fewer domains = fewer HTTP connections. Exception: a separate cookie-less domain for static resources.",
    },
    "DontResizeImageInBrowser": {
        "name": "Do not resize images in the browser",
        "description": "Resizing via HTML wastes bandwidth: a 350×300 px PNG weighs 41 KB even when displayed at 70×60 px.",
    },
    "EmptySrcTag": {
        "name": "Avoid empty SRC tags",
        "description": "An empty src attribute triggers useless HTTP requests to the page's directory.",
    },
    "ExternalizeCss": {
        "name": "Externalize CSS",
        "description": "Inline CSS is sent on every page request; external files can be cached.",
    },
    "ExternalizeJs": {
        "name": "Externalize JS",
        "description": "Same principle as CSS: separate JS files allow browser caching.",
    },
    "HttpError": {
        "name": "Avoid error requests",
        "description": "Error responses consume resources for nothing.",
    },
    "HttpRequests": {
        "name": "Limit the number of HTTP requests (< 27)",
        "description": "Fewer requests per page lighten the server load and reduce the environmental impact.",
    },
    "ImageDownloadedNotDisplayed": {
        "name": "Do not download images unnecessarily",
        "description": "Images loaded but displayed only after user interaction waste resources.",
    },
    "JsValidate": {
        "name": "Validate JavaScript",
        "description": "JSLint guarantees cross-browser syntactic compliance and allows faster interpreter execution.",
    },
    "MaxCookiesLength": {
        "name": "Maximum cookie size per domain (< 512 bytes)",
        "description": "Cookies are sent with every request: keeping them short saves bandwidth.",
    },
    "MinifiedCss": {
        "name": "Minify CSS (>= 95%)",
        "description": "Use YUI Compressor or mod_pagespeed to strip spaces and line breaks.",
    },
    "MinifiedJs": {
        "name": "Minify JS (>= 95%)",
        "description": "Strip spaces, line breaks, useless semicolons and shorten local variable names.",
    },
    "NoCookieForStaticRessources": {
        "name": "No cookies for static resources",
        "description": "Cookies on static resources waste bandwidth. Use a separate domain or limit cookie scope.",
    },
    "NoRedirect": {
        "name": "Avoid redirects",
        "description": "Redirects slow down response times and consume resources for nothing.",
    },
    "OptimizeBitmapImages": {
        "name": "Optimize bitmap images",
        "description": "Bitmaps usually make up the bulk of downloaded bytes: optimizing them has a strong impact.",
    },
    "OptimizeSvg": {
        "name": "Optimize SVG images",
        "description": "Although lighter than bitmaps, SVGs can be minified with tools like svgo.",
    },
    "Plugins": {
        "name": "Do not use plugins",
        "description": "Flash, Java, Silverlight impose a heavy CPU/RAM load. Prefer HTML5 and ECMAScript.",
    },
    "PrintStyleSheet": {
        "name": "Provide a print CSS",
        "description": "A print stylesheet reduces the number of printed pages; hide menus, headers and non-essential images.",
    },
    "SocialNetworkButton": {
        "name": "Do not use standard social network buttons",
        "description": "Official plugins (Facebook, Twitter…) load useless resources; use direct links.",
    },
    "StyleSheets": {
        "name": "Limit the number of CSS files (< 3)",
        "description": "Concatenate stylesheets into a single file to reduce HTTP requests.",
    },
    "UseETags": {
        "name": "Use ETags (>= 95%)",
        "description": "ETags allow cache reuse of resources when the server signature matches.",
    },
    "UseStandardTypefaces": {
        "name": "Use standard typefaces",
        "description": "Standard fonts are already present on the user's device: no download needed.",
    },
    "PreferHttp2": {
        "name": "Prefer HTTP/2 over HTTP/1",
        "description": (
            "HTTP/2 allows multiplexing requests over a single TCP connection "
            "(end of the 6-connections-per-domain cap of HTTP/1.1) and compresses headers "
            "(HPACK), reducing latency and the number of TCP/TLS handshakes. "
            "Activation depends on the server: Apache -> mod_http2 (requires the event or "
            "worker MPM ; incompatible with mpm_prefork) ; Nginx -> 'listen 443 ssl "
            "http2;' directive (>= 1.25 for HTTP/3 QUIC) ; behind a CDN/reverse-proxy -> HTTP/2 "
            "is usually enabled by default at the edge, check the configuration between "
            "the CDN and the origin."
        ),
    },
}

COMPLIANCE_STATUS = {"A": "good", "B": "warn", "C": "bad", "NA": "neutral"}
COMPLIANCE_ORDER  = {"C": 0, "B": 1, "A": 2, "NA": 3}


def _compliance_badge_html(level, count=None, min_width="28px"):
    """GreenIT compliance badge (A/B/C/N.A), "chip" style (light background + border
    + colored emoji): color alone must never carry the information, and
    the emoji must stay visible even on its own status (accessibility)."""
    status = COMPLIANCE_STATUS.get(level, "neutral")
    display = "N.A" if level == "NA" else level
    label = f"<b>{count}</b> {display}" if count is not None else display
    return _status_chip(status, label, extra_style=f"min-width:{min_width}")


def load_greenit(audit_dir):
    """
    Loads greenit.json if present.
    Accepted formats:
      - GreenIT-Analysis-cli CLI: list of pages {"url":..., "bestPractices":{...}}
      - EcoSonar export          : {"ecodesign": {"RuleName": {"compliance":..., "auditedMetric":..., "averageScore":..., "description":...}}}
    Returns a dict {"pages": [...], "aggregated": {"RuleName": {...}}} or None.
    """
    path = Path(audit_dir) / "greenit.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # EcoSonar format
    if isinstance(data, dict) and "ecodesign" in data:
        aggregated = {}
        for key, val in data["ecodesign"].items():
            aggregated[key] = {
                "complianceLevel": val.get("compliance", "NA"),
                "comment":         str(val.get("auditedMetric", "")),
                "detailComment":   val.get("description", ""),
            }
        return {"pages": [], "aggregated": aggregated}

    # CLI format: list of pages
    pages = data if isinstance(data, list) else [data]
    aggregated = {}
    for page in pages:
        for key, bp in page.get("bestPractices", {}).items():
            level = bp.get("complianceLevel", "NA")
            if key not in aggregated:
                aggregated[key] = {"complianceLevel": level, "comment": bp.get("comment", ""), "detailComment": bp.get("detailComment", ""), "_levels": []}
            aggregated[key]["_levels"].append(level)

    # Overall compliance = worst level among pages
    for key, val in aggregated.items():
        levels = val.pop("_levels", [])
        worst = sorted(levels, key=lambda x: COMPLIANCE_ORDER.get(x, 3))[-1] if levels else "NA"
        val["complianceLevel"] = worst

    return {"pages": pages, "aggregated": aggregated}


def compute_greenit_from_har(har_data):
    """
    Computes GreenIT-Analysis best practices from a HAR.
    Logic based on cnumr/GreenIT-Analysis (open source).
    Returns a dict compatible with load_greenit(): {"pages":[], "aggregated":{...}}
    """
    from urllib.parse import urlparse

    entries = har_data.get("log", {}).get("entries", [])
    if not entries:
        return None

    def _is_static(mime, url):
        return _classify_type(mime, url) in ("javascript", "css", "image", "font")

    def _is_cached(resp):
        hdrs = {h["name"].lower(): h["value"] for h in resp.get("headers", [])}
        return bool(hdrs.get("cache-control") or hdrs.get("expires") or hdrs.get("etag") or resp.get("status") == 304)

    # ── Raw metrics collection ─────────────────────────────────────────
    total = len(entries)
    nb_errors = 0;         urls_errors = []
    nb_redirects = 0;      urls_redirects = []
    nb_no_cache = 0;       urls_no_cache = []
    static_cacheable_bytes = 0;  cacheable_ok_bytes = 0  # Lot 3: estimated "return visit" gain
    nb_no_compress = 0;    urls_no_compress = []
    nb_no_etag = 0;        urls_no_etag = []
    nb_cookie_static = 0;  urls_cookie_static = [];  cookie_static_bytes = 0
    cookie_bytes_by_domain = defaultdict(int)
    domains = set()
    css_files = []
    inline_css = 0
    inline_js = 0
    font_external = 0;     urls_fonts = []
    nb_svg = 0;            urls_svg_heavy = []
    nb_bitmap = 0;         urls_bitmap_heavy = []
    nb_bitmap_heavy = 0
    nb_svg_heavy = 0
    urls_svg_fake = []     # Lot 4: abnormally heavy SVG (> 30 KB), probable encoded bitmap
    nb_video = 0;          video_bytes = 0;  urls_video = []
    nb_pdf = 0;            pdf_bytes = 0;    urls_pdf = []
    has_print_css = False
    social_domains = {"facebook.com", "twitter.com", "x.com", "linkedin.com", "instagram.com",
                      "platform.twitter.com", "connect.facebook.net", "platform.linkedin.com"}
    nb_social = 0;         urls_social = []
    http_versions = defaultdict(int)  # for HTTP/2

    def _short(u, n=80):
        return u if len(u) <= n else u[:n] + "…"

    for e in entries:
        req  = e.get("request", {})
        resp = e.get("response", {})
        url  = req.get("url", "")
        status = resp.get("status", 0)
        mime = resp.get("content", {}).get("mimeType", "")
        rtype = _classify_type(mime, url)
        size  = resp.get("content", {}).get("size", 0) or 0
        hdrs_resp = {h["name"].lower(): h["value"] for h in resp.get("headers", [])}
        hdrs_req  = {h["name"].lower(): h["value"] for h in req.get("headers", [])}
        http_ver  = req.get("httpVersion", "") or resp.get("httpVersion", "")

        try:
            netloc = urlparse(url).netloc
        except Exception:
            netloc = ""
        if netloc:
            domains.add(netloc)

        # HTTP version
        if http_ver:
            http_versions[http_ver] += 1

        # Errors
        if 400 <= status < 600:
            nb_errors += 1
            if len(urls_errors) < 20:
                urls_errors.append((url, status))

        # Redirects
        if 300 <= status < 400 and status != 304:
            nb_redirects += 1
            if len(urls_redirects) < 20:
                urls_redirects.append((url, status))

        # Cache-control / expires
        if _is_static(mime, url) and status != 304:
            has_cc   = bool(hdrs_resp.get("cache-control") or hdrs_resp.get("expires"))
            has_etag = bool(hdrs_resp.get("etag"))
            static_cacheable_bytes += size
            if has_cc:
                cacheable_ok_bytes += size
            else:
                nb_no_cache += 1
                if len(urls_no_cache) < 20:
                    urls_no_cache.append(url)
            if not has_etag:
                nb_no_etag += 1
                if len(urls_no_etag) < 20:
                    urls_no_etag.append(url)

        # Compression
        if rtype in ("javascript", "css", "html") and size > 1024:
            enc = hdrs_resp.get("content-encoding", "")
            if not enc or enc.lower() == "identity":
                nb_no_compress += 1
                if len(urls_no_compress) < 20:
                    urls_no_compress.append(url)

        # Cookies on static resources
        if _is_static(mime, url) and hdrs_req.get("cookie"):
            nb_cookie_static += 1
            cookie_static_bytes += len(hdrs_req["cookie"].encode())
            if len(urls_cookie_static) < 20:
                urls_cookie_static.append(url)
        for h in req.get("headers", []):
            if h["name"].lower() == "cookie" and netloc:
                cookie_bytes_by_domain[netloc] += len(h["value"].encode())

        # CSS
        if rtype == "css":
            if url.startswith("http"):
                css_files.append(url)
                for h in req.get("headers", []):
                    if "print" in h.get("value", "").lower():
                        has_print_css = True
            else:
                inline_css += 1

        # Inline JS
        if rtype == "html":
            body = resp.get("content", {}).get("text", "") or ""
            if "<script" in body and "src=" not in body.split("<script")[1][:100] if "<script" in body else False:
                inline_js += 1

        # External fonts
        if "googleapis.com" in netloc or "gstatic.com" in netloc or "typekit" in netloc or rtype == "font":
            if netloc:
                font_external = 1
                if netloc not in [u for u in urls_fonts]:
                    urls_fonts.append(netloc)

        # Images
        if rtype == "image":
            ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext == "svg":
                nb_svg += 1
                if size > 10 * 1024:
                    nb_svg_heavy += 1
                    if len(urls_svg_heavy) < 20:
                        urls_svg_heavy.append((url, round(size/1024, 1)))
                # Lot 4: beyond 30 KB, an SVG (vectorial, normally light)
                # most often hides a base64-encoded bitmap (signal, not certainty)
                if size > 30 * 1024 and len(urls_svg_fake) < 20:
                    urls_svg_fake.append((url, round(size/1024, 1)))
            else:
                nb_bitmap += 1
                if size > 200 * 1024 and ext not in ("webp", "avif", "jxl"):
                    nb_bitmap_heavy += 1
                    if len(urls_bitmap_heavy) < 20:
                        urls_bitmap_heavy.append((url, round(size/1024, 1)))

        # Videos and PDFs (Lot 4): factual reporting, no A/B/C judgment
        if rtype == "video":
            nb_video += 1
            video_bytes += size
            if len(urls_video) < 20:
                urls_video.append((url, round(size/1024, 1)))
        elif rtype == "pdf":
            nb_pdf += 1
            pdf_bytes += size
            if len(urls_pdf) < 20:
                urls_pdf.append((url, round(size/1024, 1)))

        # Social networks
        if netloc in social_domains or any(s in netloc for s in ("facebook", "twitter", "linkedin", "instagram")):
            nb_social += 1
            if len(urls_social) < 10:
                urls_social.append(url)

    # print CSS: search in HTML bodies
    for e in entries:
        body = e.get("response", {}).get("content", {}).get("text", "") or ""
        if "media" in body and "print" in body:
            has_print_css = True
            break

    # ── Rule evaluation ─────────────────────────────────────────────────
    static_total = sum(
        1 for e in entries
        if _is_static(
            e.get("response",{}).get("content",{}).get("mimeType",""),
            e.get("request",{}).get("url","")
        ) and e.get("response",{}).get("status",0) != 304
    )

    def _pct_ok(nb_bad, total_concerned):
        if total_concerned == 0:
            return "A", "100% compliant"
        pct_bad = nb_bad / total_concerned * 100
        if pct_bad == 0:
            return "A", "100% compliant"
        elif pct_bad <= 5:
            return "B", f"{nb_bad}/{total_concerned} non-compliant resource(s)"
        else:
            return "C", f"{nb_bad}/{total_concerned} non-compliant resource(s)"

    def _ev(urls, label="URL"):
        """Formats the evidence list for storage."""
        return urls

    agg = {}

    # AddExpiresOrCacheControlHeaders
    lvl, cmt = _pct_ok(nb_no_cache, static_total)
    # "Return visit" gain (Lot 3): weight already saved by the cache in place
    # + additional weight that would be saved if the uncached resources were fixed.
    _no_cache_bytes = static_cacheable_bytes - cacheable_ok_bytes
    if static_cacheable_bytes > 0:
        cmt += (f" — current return-visit gain: {cacheable_ok_bytes/1024:.0f} KB saved/return visit"
                f"{f', {_no_cache_bytes/1024:.0f} KB additional possible if fixed' if _no_cache_bytes > 0 else ''}")
    agg["AddExpiresOrCacheControlHeaders"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_no_cache}

    # CompressHttp
    compressible = sum(
        1 for e in entries
        if _classify_type(
            e.get("response",{}).get("content",{}).get("mimeType",""),
            e.get("request",{}).get("url","")
        ) in ("javascript","css","html")
        and (e.get("response",{}).get("content",{}).get("size",0) or 0) > 1024
    )
    lvl, cmt = _pct_ok(nb_no_compress, compressible)
    agg["CompressHttp"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_no_compress}

    # DomainsNumber
    nd = len(domains)
    if nd < 3:
        lvl = "A"
    elif nd < 6:
        lvl = "B"
    else:
        lvl = "C"
    agg["DomainsNumber"] = {"complianceLevel": lvl, "comment": f"{nd} domain(s)", "evidence": sorted(domains)}

    # HttpError
    lvl = "A" if nb_errors == 0 else "C"
    cmt = "No HTTP error" if nb_errors == 0 else f"{nb_errors} error request(s)"
    agg["HttpError"] = {"complianceLevel": lvl, "comment": cmt, "evidence": [f"{u} ({s})" for u, s in urls_errors]}

    # HttpRequests
    pages_har = har_data.get("log", {}).get("pages", [])
    nb_pages_har = max(len(pages_har), 1)
    avg_req = total / nb_pages_har
    if avg_req < 27:   lvl = "A"
    elif avg_req < 40: lvl = "B"
    else:              lvl = "C"
    agg["HttpRequests"] = {"complianceLevel": lvl, "comment": f"{avg_req:.0f} req/page on average ({total} total, {nb_pages_har} pages)", "evidence": []}

    # NoRedirect
    if nb_redirects == 0:     lvl, cmt = "A", "No redirect"
    elif nb_redirects <= 2:   lvl, cmt = "B", f"{nb_redirects} redirect(s)"
    else:                     lvl, cmt = "C", f"{nb_redirects} redirect(s)"
    agg["NoRedirect"] = {"complianceLevel": lvl, "comment": cmt, "evidence": [f"{u} ({s})" for u, s in urls_redirects]}

    # NoCookieForStaticRessources
    lvl = "A" if nb_cookie_static == 0 else "C"
    if nb_cookie_static == 0:
        cmt = "No cookie on static resource"
    else:
        cmt = (f"{nb_cookie_static} static resource(s) with cookie — "
               f"{cookie_static_bytes} bytes of cookie sent uselessly on this journey "
               f"(measured from HAR headers, not an estimate)")
    agg["NoCookieForStaticRessources"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_cookie_static}

    # UseETags
    lvl, cmt = _pct_ok(nb_no_etag, static_total)
    agg["UseETags"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_no_etag[:10]}

    # ExternalizeCss
    lvl = "A" if inline_css == 0 else "C"
    cmt = "No inline CSS detected" if inline_css == 0 else f"{inline_css} inline CSS detected"
    agg["ExternalizeCss"] = {"complianceLevel": lvl, "comment": cmt, "evidence": []}

    # ExternalizeJs
    lvl = "A" if inline_js == 0 else "C"
    cmt = "No inline JS detected" if inline_js == 0 else f"{inline_js} inline JS detected"
    agg["ExternalizeJs"] = {"complianceLevel": lvl, "comment": cmt, "evidence": []}

    # StyleSheets
    nb_css = len(set(u.split("?")[0] for u in css_files))
    if nb_css <= 2:   lvl = "A"
    elif nb_css <= 5: lvl = "B"
    else:             lvl = "C"
    agg["StyleSheets"] = {"complianceLevel": lvl, "comment": f"{nb_css} distinct CSS file(s)", "evidence": sorted(set(u.split("?")[0] for u in css_files))}

    # UseStandardTypefaces
    lvl = "C" if font_external else "A"
    cmt = "External fonts detected" if font_external else "No external font detected"
    agg["UseStandardTypefaces"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_fonts}

    # MinifiedCss / MinifiedJs — whitespace ratio heuristic
    def _count_unminified(rtype_filter):
        nb = 0; tot = 0; urls_bad = []
        for e in entries:
            mime = e.get("response",{}).get("content",{}).get("mimeType","")
            u = e.get("request",{}).get("url","")
            if _classify_type(mime, u) != rtype_filter:
                continue
            sz = e.get("response",{}).get("content",{}).get("size",0) or 0
            if sz < 2048:
                continue
            tot += 1
            body = e.get("response",{}).get("content",{}).get("text","") or ""
            if len(body) > 500 and body.count("\n") > len(body) / 200:
                nb += 1
                if len(urls_bad) < 20:
                    urls_bad.append(u)
        return nb, tot, urls_bad

    nb_unmin_css, tot_css, urls_unmin_css = _count_unminified("css")
    lvl, cmt = _pct_ok(nb_unmin_css, tot_css)
    agg["MinifiedCss"] = {"complianceLevel": lvl, "comment": cmt if cmt else f"{tot_css} CSS file(s)", "evidence": urls_unmin_css}

    nb_unmin_js, tot_js, urls_unmin_js = _count_unminified("javascript")
    lvl, cmt = _pct_ok(nb_unmin_js, tot_js)
    agg["MinifiedJs"] = {"complianceLevel": lvl, "comment": cmt if cmt else f"{tot_js} JS file(s)", "evidence": urls_unmin_js}

    # OptimizeBitmapImages
    if nb_bitmap == 0:
        agg["OptimizeBitmapImages"] = {"complianceLevel": "NA", "comment": "No bitmap image", "evidence": [], "evidence_images": []}
    elif nb_bitmap_heavy == 0:
        # Top 10 heaviest images even when compliant (for an overview)
        top_bitmaps = sorted(
            [(e.get("request",{}).get("url",""), e.get("response",{}).get("content",{}).get("size",0) or 0)
             for e in entries
             if _classify_type(e.get("response",{}).get("content",{}).get("mimeType",""), e.get("request",{}).get("url","")) == "image"
             and e.get("request",{}).get("url","").split("?")[0].rsplit(".",1)[-1].lower() not in ("svg",)],
            key=lambda x: -x[1]
        )[:10]
        agg["OptimizeBitmapImages"] = {
            "complianceLevel": "A",
            "comment": f"{nb_bitmap} image(s), none > 200 KB non-webp/avif/jxl",
            "evidence": [],
            "evidence_images": [{"url": u, "size_kb": round(s/1024, 1)} for u, s in top_bitmaps if u],
        }
    else:
        heavy_ko = sum(s for _, s in urls_bitmap_heavy)
        # Flat cnumr gains JPEG/PNG -> WebP: -31.5% / -50.3% (average ~-41% kept,
        # no distinction by source format here — range to specify in the methodology)
        gain_low_ko  = round(heavy_ko * 0.315)
        gain_high_ko = round(heavy_ko * 0.503)
        agg["OptimizeBitmapImages"] = {
            "complianceLevel": "C",
            "comment": (f"{nb_bitmap_heavy} image(s) > 200 KB, non-webp/avif/jxl format — "
                        f"estimated webp gain: {gain_low_ko} to {gain_high_ko} KB (flat rate, not measured)"),
            "evidence": [f"{u} ({s} KB)" for u, s in urls_bitmap_heavy],
            "evidence_images": [{"url": u, "size_kb": s} for u, s in urls_bitmap_heavy],
        }

    # OptimizeSvg
    if nb_svg == 0:
        agg["OptimizeSvg"] = {"complianceLevel": "NA", "comment": "No SVG", "evidence": [], "evidence_images": []}
    elif nb_svg_heavy == 0:
        agg["OptimizeSvg"] = {"complianceLevel": "A", "comment": f"{nb_svg} SVG, none > 10 KB", "evidence": [], "evidence_images": []}
    else:
        cmt = f"{nb_svg_heavy} heavy SVG(s) (> 10 KB)"
        if urls_svg_fake:
            cmt += (f" — including {len(urls_svg_fake)} probable base64-encoded bitmap(s) "
                    f"(> 30 KB, unconfirmed signal)")
        agg["OptimizeSvg"] = {
            "complianceLevel": "C",
            "comment": cmt,
            "evidence": [f"{u} ({s} KB)" for u, s in urls_svg_heavy],
            "evidence_images": [{"url": u, "size_kb": s} for u, s in urls_svg_heavy],
        }

    # PrintStyleSheet
    lvl = "A" if has_print_css else "C"
    cmt = "Print CSS detected" if has_print_css else "No print stylesheet detected"
    agg["PrintStyleSheet"] = {"complianceLevel": lvl, "comment": cmt, "evidence": []}

    # SocialNetworkButton
    lvl = "A" if nb_social == 0 else "C"
    cmt = "No standard social network button" if nb_social == 0 else f"{nb_social} social network resource(s) detected"
    agg["SocialNetworkButton"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_social}

    # MaxCookiesLength
    max_cookie = max(cookie_bytes_by_domain.values()) if cookie_bytes_by_domain else 0
    if max_cookie == 0:
        lvl, cmt = "A", "No cookie"
    elif max_cookie <= 512:
        lvl, cmt = "A", f"Max {max_cookie} bytes/domain"
    else:
        lvl, cmt = "C", f"Max {max_cookie} bytes/domain (> 512)"
    agg["MaxCookiesLength"] = {"complianceLevel": lvl, "comment": cmt,
                                "evidence": [f"{d} : {b} bytes" for d, b in sorted(cookie_bytes_by_domain.items(), key=lambda x: -x[1])[:10]]}

    # PreferHttp2
    nb_h1 = sum(v for k, v in http_versions.items() if "1.1" in k or k == "HTTP/1.0")
    nb_h2 = sum(v for k, v in http_versions.items() if "2" in k or "h2" in k.lower())
    if not http_versions or (nb_h1 == 0 and nb_h2 == 0):
        # No version info in the HAR
        agg["PreferHttp2"] = {"complianceLevel": "NA", "comment": "HTTP version not available in the HAR", "evidence": []}
    elif nb_h1 == 0:
        agg["PreferHttp2"] = {"complianceLevel": "A", "comment": f"HTTP/2 or higher ({nb_h2} requests)", "evidence": []}
    elif nb_h2 == 0:
        agg["PreferHttp2"] = {"complianceLevel": "C", "comment": f"HTTP/1.x only ({nb_h1} requests)", "evidence": list(http_versions.items())}
    else:
        agg["PreferHttp2"] = {"complianceLevel": "B", "comment": f"Mix HTTP/1.x ({nb_h1}) and HTTP/2+ ({nb_h2})",
                               "evidence": [f"{k}: {v} request(s)" for k, v in sorted(http_versions.items())]}

    # Lot 4: bulky media (videos, PDFs) — factual reporting, no A/B/C badge
    # (no defensible universal threshold, no possible weight/real-usage comparison here)
    media = {
        "video": {"count": nb_video, "size_ko": round(video_bytes/1024), "urls": urls_video},
        "pdf":   {"count": nb_pdf,   "size_ko": round(pdf_bytes/1024),   "urls": urls_pdf},
    }

    return {"pages": [], "aggregated": agg, "_source": "har", "media": media}


def _section_greenit(greenit):
    if not greenit:
        return ""

    agg = greenit["aggregated"]
    # Sort: C first, then B, then A, then NA
    sorted_keys = sorted(agg.keys(), key=lambda k: COMPLIANCE_ORDER.get(agg[k]["complianceLevel"], 3))

    rows = ""
    for key in sorted_keys:
        bp    = agg[key]
        rule  = GREENIT_RULES.get(key, {"name": key, "description": ""})
        level = bp["complianceLevel"]
        badge = _compliance_badge_html(level)
        detail = bp.get("comment") or bp.get("detailComment") or ""

        # <details> block with the implicated URLs if available
        evidence = bp.get("evidence", [])
        evidence_images = bp.get("evidence_images", [])  # [{url, size_kb}]

        # Deduplicate by canonical URL (no query string)
        _seen_ev = {}
        for img in evidence_images:
            key = img["url"].split("?")[0]
            if key not in _seen_ev or img.get("size_kb", 0) > _seen_ev[key].get("size_kb", 0):
                _seen_ev[key] = img
        evidence_images = list(_seen_ev.values())

        # Thumbnails for the 10 heaviest images
        thumbs_html = ""
        if evidence_images:
            top_imgs = sorted(evidence_images, key=lambda x: -x.get("size_kb", 0))[:10]
            thumbs = []
            for img in top_imgs:
                url = img["url"]
                size_kb = img.get("size_kb", 0)
                fname = url.split("/")[-1].split("?")[0][:40]
                thumb = embed_image(url, alt=fname, max_dim=50)
                if thumb:
                    # Replace the figure with a compact inline version
                    thumb_inline = (
                        f'<div style="display:inline-block;text-align:center;margin:4px;vertical-align:top">'
                        f'<a href="{url}" target="_blank" rel="noopener">'
                        f'{thumb}'
                        f'</a>'
                        f'<div style="font-size:14px;color:#555;max-width:60px;word-break:break-all">'
                        f'{fname}<br><b>{size_kb} Ko</b></div>'
                        f'</div>'
                    )
                    thumbs.append(thumb_inline)
                else:
                    # Fallback: text link if vipsthumbnail is missing
                    thumbs.append(
                        f'<div style="display:inline-block;margin:4px;font-size:15px;vertical-align:top">'
                        f'<a href="{url}" target="_blank" rel="noopener">{fname}</a>'
                        f'<br><b>{size_kb} Ko</b></div>'
                    )
            if thumbs:
                thumbs_html = (
                    f'<div style="margin-top:6px;padding:6px;background:#f8f8f8;border-radius:4px">'
                    f'<div style="font-size:15px;color:#555;margin-bottom:4px">Top {len(thumbs)} heaviest images:</div>'
                    f'{"".join(thumbs)}'
                    f'</div>'
                )

        if thumbs_html:
            # Thumbnails replace the text list for image rules
            nb = len(evidence_images)
            details_html = (
                f'<details style="margin-top:4px">'
                f'<summary style="cursor:pointer;font-size:15px;color:#555">'
                f'Preview ({nb} image(s))</summary>'
                f'{thumbs_html}'
                f'</details>'
            )
        elif evidence:
            # Other rules: simple text list
            ev_items = "".join(
                f'<li style="font-size:15px;word-break:break-all;margin:2px 0">'
                f'<a href="{item}" target="_blank" rel="noopener">{item}</a></li>'
                if str(item).startswith("http")
                else f'<li style="font-size:15px;margin:2px 0">{item}</li>'
                for item in evidence
            )
            details_html = (
                f'<details style="margin-top:4px">'
                f'<summary style="cursor:pointer;font-size:15px;color:#555">'
                f'Detail ({len(evidence)} item(s))</summary>'
                f'<ul style="margin:4px 0 0 12px;padding:0">{ev_items}</ul>'
                f'</details>'
            )
        else:
            details_html = ""

        detail_html = f'<span style="font-size:15px;color:#666">{detail}</span>' if detail else ""
        rows += f"""<tr>
      <td style="text-align:center;width:48px;vertical-align:top;padding-top:10px">{badge}</td>
      <td><b>{rule['name']}</b><br>{detail_html}{details_html}</td>
      <td style="font-size:16px;color:#555;vertical-align:top">{rule['description']}</td>
    </tr>"""

    nb_c  = sum(1 for k in agg if agg[k]["complianceLevel"] == "C")
    nb_b  = sum(1 for k in agg if agg[k]["complianceLevel"] == "B")
    nb_a  = sum(1 for k in agg if agg[k]["complianceLevel"] == "A")
    nb_na = sum(1 for k in agg if agg[k]["complianceLevel"] == "NA")

    summary = (
        f'<span style="margin-right:6px">{_compliance_badge_html("C", nb_c, min_width="auto")}</span>'
        f'<span style="margin-right:6px">{_compliance_badge_html("B", nb_b, min_width="auto")}</span>'
        f'<span style="margin-right:6px">{_compliance_badge_html("A", nb_a, min_width="auto")}</span>'
        f'{_compliance_badge_html("NA", nb_na, min_width="auto")}'
    )

    legend = (
        '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px;font-size:16px">'
        f'<span>{_compliance_badge_html("C", min_width="auto")} &nbsp;<b>Non-compliant</b> - corrective action required</span>'
        f'<span>{_compliance_badge_html("B", min_width="auto")} &nbsp;<b>Partially compliant</b> - improvement possible</span>'
        f'<span>{_compliance_badge_html("A", min_width="auto")} &nbsp;<b>Compliant</b> - best practice followed</span>'
        f'<span>{_compliance_badge_html("NA", min_width="auto")} &nbsp;<b>Not applicable</b> - criterion irrelevant for this site</span>'
        '</div>'
    )

    source_note = ' <span style="font-size:16px;font-weight:normal;color:#888">(computed from HAR)</span>' if greenit.get("_source") == "har" else ""
    return f"""<section id="greenit">
  <h2>GreenIT-Analysis best practices{source_note}</h2>
  <div style="margin-bottom:8px">{summary}</div>
  {legend}
  <table>
    <thead><tr><th style="width:48px">Level</th><th>Best practice</th><th>Description</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


def _section_medias(greenit):
    """Lot 4 section: heavy media content (videos, PDFs) — factual reporting,
    no A/B/C badge (no defensible universal threshold for these formats).
    Returns "" if no media detected (section absent, not an empty line)."""
    media = (greenit or {}).get("media") or {}
    video = media.get("video", {})
    pdf = media.get("pdf", {})
    if not video.get("count") and not pdf.get("count"):
        return ""

    def _kpi_block(label, data, color):
        if not data.get("count"):
            return ""
        rows = "".join(
            f'<tr><td><a href="{u}" target="_blank" rel="noopener" title="{u}">'
            f'{u.split("/")[-1].split("?")[0][:60] or u[:60]}</a></td>'
            f'<td style="text-align:right">{s} KB</td></tr>'
            for u, s in data.get("urls", [])
        )
        return f"""<div style="margin-bottom:16px">
  <div class="kpi-grid" style="margin-bottom:8px">
    <div class="kpi"><div class="val">{data['count']}</div><div class="lbl">{label} detected</div></div>
    <div class="kpi"><div class="val">{data['size_ko']:,} KB</div><div class="lbl">Cumulative weight</div></div>
  </div>
  <details><summary style="cursor:pointer;color:{color};font-weight:bold">Detail of the {data['count']} file(s)</summary>
    <table style="margin-top:6px"><tbody>{rows}</tbody></table>
  </details>
</div>"""

    return f"""<section id="medias">
  <h2>Media and documents to watch</h2>
  <p style="font-size:15px;color:#888;margin-bottom:12px">
    Factual reporting (weight, count): no compliance threshold is applied here,
    the expected use of a video or PDF varying too much with the site's context to
    set a universal benchmark.
  </p>
  {_kpi_block("Video", video, TYPE_COLORS.get("video", "#e67e22"))}
  {_kpi_block("PDF", pdf, TYPE_COLORS.get("pdf", "#c0392b"))}
</section>"""


_CONFIDENCE_LEVELS = ("high", "medium", "low", "default", "default_efootprint",
                      "default_script", "unjustified",
                      # Canonical names of the provenance axis (EOF chain). The names
                      # above stay accepted in reading so that audits already
                      # produced keep displaying.
                      "collected", "estimated", "declared", "stated", "assumed",
                      "defaut_lib", "defaut_script")


def _confidence_badge(conf):
    """Renders a small colored badge for a confidence level.

    "default"/"default_efootprint": default value of the e-footprint LIBRARY
    (e.g. smartphone/laptop archetypes). "default_script": value hard-coded by
    OUR script (e.g. 50 GB storage), not by e-footprint — a distinction needed
    because both were previously confused under a single misleading badge.
    "unjustified": data specified manually by the person running the audit,
    but without a verifiable justification/source provided (e.g. instance type
    chosen without proof).
    """
    # Canonical table with all accepted synonyms
    mapping = {
        "high":               ("#1e7e34", "#e8f5e9", "✅", "collected"),
        "collected":           ("#1e7e34", "#e8f5e9", "✅", "collected"),
        "medium":             ("#0f6674", "#e0f4f7", "🔎", "estimated"),
        "estimated":             ("#0f6674", "#e0f4f7", "🔎", "estimated"),
        "declared":            ("#2a5f99", "#e3f0ff", "📣", "declared (public)"),
        "low":                ("#9a4d00", "#fff3e0", "❓", "assumed"),
        "assumed":            ("#9a4d00", "#fff3e0", "❓", "assumed"),
        "unjustified":        ("#5a3d34", "#f3e8e4", "📝", "stated"),
        "stated":            ("#5a3d34", "#f3e8e4", "📝", "stated"),
        "default":            ("#5a5a5a", "#eeeeee", "📦", "lib default"),
        "default_efootprint": ("#5a5a5a", "#eeeeee", "📦", "lib default"),
        "defaut_lib":         ("#5a5a5a", "#eeeeee", "📦", "lib default"),
        "default_script":     ("#33383d", "#e4e5e7", "🛠️", "script default"),
        "defaut_script":      ("#33383d", "#e4e5e7", "🛠️", "script default"),
    }
    color, bg, emoji, label = mapping.get(conf, ("#5a5a5a", "#eeeeee", "❔", conf or "?"))
    return (
        f'<span style="background:{bg};border:1.5px solid {color};color:{color};'
        f'font-weight:bold;padding:1px 8px;border-radius:4px;font-size:13px;'
        f'white-space:nowrap">{emoji} {label}</span>'
    )


def _provenance_of(entry):
    """Reads the provenance axis of an EOF entry (criterion or diagnostic question).

    The EOF chain writes `provenance` (collected > estimated > declared > stated).
    `confidence` is the old name, kept as a fallback so that audits produced
    before the rename keep displaying. No default value: a missing provenance
    stays missing, it does not silently become "collected".
    """
    return entry.get("provenance") or entry.get("confidence")


# Known domains -> short label displayed in "(↗ source <name>)". The site name
# is ALWAYS visible in the link (never a bare "source" that does not say where
# the data comes from); fallback to the domain as-is if not listed here.
_SOURCE_DOMAIN_LABELS = {
    "similarweb.com": "similarweb",
    "www.similarweb.com": "similarweb",
    "boavizta.org": "boavizta",
    "api.boavizta.org": "boavizta",
    "ecoindex.fr": "ecoindex.fr",
    "www.ecoindex.fr": "ecoindex.fr",
    "web.dev": "web.dev",
    "blog.octo.com": "blog OCTO",
    "ademe.fr": "ademe",
    "base-empreinte.ademe.fr": "ademe",
}


def _source_link(url, label=None):
    """'(↗ source <name>)' link to a provenance URL, site name deduced
    from the domain (never a bare "source"). Returns an empty string if url is
    absent, for direct use in an f-string without a prior test."""
    if not url:
        return ""
    if label is None:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        label = _SOURCE_DOMAIN_LABELS.get(host, host.removeprefix("www."))
    return f' (<a href="{url}" target="_blank" rel="noopener">&#8599;&nbsp;source {label}</a>)'


def _audience_source_label(label, url):
    """Source label of the audience country mix, suffixed with a readable link
    ("↗ source similarweb") to the provenance URL if provided."""
    return f'{label}{_source_link(url)}' if url else label


def _instance_type_row(hyp):
    """"Instance type" row with 3 confidence levels:
    - never specified (--instance not provided): SCRIPT default value
      (not e-footprint), "script default" badge.
    - specified (--instance provided) but without justification (--instance-source
      absent): "stated" badge, active choice but unverified.
    - specified AND justified (--instance-source provided): "estimated" badge, with
      the justification text (and source link if provided), modeled on
      _traffic_source_label()/_audience_source_label().

    hyp: hypotheses dict of efootprint-python-summary.json. Returns (label_value, conf).
    """
    # `.get(key, fallback)` is not enough: the key EXISTS and is `None` when no
    # instance type was retained. The fallback therefore never applied and the
    # report displayed "Instance type: None" to the reader (found by
    # check_report_values.py on already produced reports). "no data" is
    # the label already used elsewhere for an absence.
    value = hyp.get("instance_type") or "no data"
    source_text = hyp.get("instance_type_source")
    source_url = hyp.get("instance_type_source_url")

    if not hyp.get("instance_type_manual"):
        return value, "default_script"

    if not source_text:
        return value, "unjustified"

    label = f'{source_text}{_source_link(source_url)}'
    return f'{value} <span style="color:#888;font-size:0.85em">— {label}</span>', "medium"


def _traffic_source_label(traffic):
    """Provenance label of the annual traffic, with snapshot and source link.

    traffic: {source, source_url, snapshot, confidence} block of efootprint-python-summary.json.
    Returns a readable label ("SimilarWeb estimate, June 2026 ↗ source",
    "manual entry (client analytics)", "default assumption") meant for the source
    column of the assumptions tables."""
    traffic = traffic or {}
    source = traffic.get("source") or "parameter"
    url = traffic.get("source_url")
    snapshot = traffic.get("snapshot")

    if source == "default":
        return "default assumption (100,000/year)"

    label = source
    if snapshot:
        label = f'{label}, {snapshot}'
    label = f'{label}{_source_link(url)}'
    return label


def load_python_summary(audit_dir):
    """Looks for efootprint-python-summary.json in audit_dir or its parent
    (source_dir): application-level summary written by
    `run_efootprint.py::save_python_summary()`, NOT the native e-footprint
    model (`efootprint-boavizta-model.json`, never read by this report)."""
    audit_dir = Path(audit_dir)
    for candidate in [audit_dir / "efootprint-python-summary.json",
                       audit_dir.parent / "efootprint-python-summary.json"]:
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                return json.load(f)
    return None


def load_recommendations_gains(audit_dir):
    """Looks for efootprint-recommendations-gains.json in audit_dir or its parent
    (source_dir): CO2e gains per recommendation tier, written by
    `run_efootprint.py::run_recommendation_scenarios()`. Optional — absent on an
    audit not yet re-run with this version of the script (backward-compatible report,
    same principle as load_python_summary())."""
    audit_dir = Path(audit_dir)
    for candidate in [audit_dir / "efootprint-recommendations-gains.json",
                      audit_dir.parent / "efootprint-recommendations-gains.json"]:
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                return json.load(f)
    return {}


def load_topology_svg(audit_dir):
    """Looks for a topology-*.svg in audit_dir or its parent (source_dir).

    Produced by Step 25 of the efootprint skill (build_topology_overview() +
    plantuml -tsvg compilation, cf. run_efootprint.py): the topology diagram
    already validated with the user before the calculation. Does not attempt
    any on-the-fly regeneration (backward-compatible report if absent, same
    principle as load_python_summary()/load_tech_stack()).
    """
    audit_dir = Path(audit_dir)
    for parent in (audit_dir, audit_dir.parent):
        candidates = sorted(parent.glob("topology-*.svg"))
        if candidates:
            return candidates[0].read_text(encoding="utf-8")
    return None


def load_eof_results(audit_dir):
    """Looks for eof-audit-results.json (audit_dir or parent) — light summary
    written by `run_eof.py::main()`. Never read if absent (backward-compatible report,
    same principle as load_python_summary())."""
    audit_dir = Path(audit_dir)
    for candidate in [audit_dir / "eof-audit-results.json",
                       audit_dir.parent / "eof-audit-results.json"]:
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                return json.load(f)
    return None


def load_eof_radar_svg(audit_dir):
    """Looks for an eof-radar-*.svg (audit_dir or parent), produced by `run_eof.py` or
    by `process/merge_lots.py` (build_radar_from_results() of the eof skill:
    two layers, count per axis, coverage gauge)."""
    audit_dir = Path(audit_dir)
    for parent in (audit_dir, audit_dir.parent):
        candidates = sorted(parent.glob("eof-radar-*.svg"))
        if candidates:
            return candidates[0].read_text(encoding="utf-8")
    return None


def load_tech_stack(audit_dir):
    """Looks for the tech_stack block in env-data.json (audit_dir or parent).

    Same "audit_dir or parent" lookup scheme as the HAR / efootprint.
    Returns the tech_stack dict (technologies/categories/third_party_hosts) or None
    (env-data.json missing, unreadable, or a schema older than 1.3 without the key)."""
    audit_dir = Path(audit_dir)
    for candidate in [audit_dir / "env-data.json",
                      audit_dir.parent / "env-data.json"]:
        if candidate.exists():
            try:
                with open(candidate, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
            return data.get("tech_stack")
    return None


def _section_tech(tech_stack):
    """'Tech stack' section — detected technologies (home-grown rules on the HAR).

    Rendered as an appendix sub-section (documentary character). Groups the
    technologies by category with a confidence badge and the hint that allowed
    the detection. Non-regression: returns "" if tech_stack is absent (old
    env-data.json)."""
    if not tech_stack:
        return ""

    technos = tech_stack.get("technologies", [])
    third_party = tech_stack.get("third_party_hosts", [])
    req_count = tech_stack.get("request_count", 0)

    if not technos:
        return ""

    # Grouping by category while preserving arrival order (already sorted upstream)
    by_cat = defaultdict(list)
    for t in technos:
        by_cat[t.get("category", "Other")].append(t)

    rows = ""
    for cat, items in by_cat.items():
        first = True
        for t in items:
            cat_cell = (
                f'<td style="padding:6px 8px;vertical-align:top;font-weight:600" '
                f'rowspan="{len(items)}">{cat}</td>' if first else ""
            )
            first = False
            rows += (
                f'<tr>'
                f'{cat_cell}'
                f'<td style="padding:6px 8px">{t.get("name", "?")}</td>'
                f'<td style="padding:6px 8px">{_confidence_badge(t.get("confidence"))}</td>'
                f'<td style="padding:6px 8px;color:#666;font-size:14px">{t.get("evidence", "")}</td>'
                f'</tr>'
            )

    tp_html = ""
    if third_party:
        tp_items = "".join(
            f'<li style="display:inline-block;background:{OCTO_PALE};border-radius:4px;'
            f'padding:2px 8px;margin:2px;font-size:14px">{h}</li>'
            for h in third_party
        )
        tp_html = (
            f'<h4 style="margin:20px 0 8px">Third-party hosts ({len(third_party)})</h4>'
            f'<p style="font-size:14px;color:#666;margin:0 0 6px">Distinct domains '
            f'from the main domain requested during loading (scripts, fonts, '
            f'analytics, external {_glossary_link("CDN")}).</p>'
            f'<ul style="list-style:none;padding:0;margin:0">{tp_items}</ul>'
        )

    return f"""<section id="stack-technique">
  <h2>Tech stack</h2>
  <p style="font-size:16px;color:#555;margin-bottom:8px">
    Technologies detected by <b>home-grown rules</b> (offline pattern-matching on the
    HAR: response headers, URLs, HTML, cookies). No external call, no
    dependency. Detection deliberately limited to client-side visible signals:
    the hidden backend and the server instance type remain undetectable.
  </p>
  <p style="font-size:15px;color:#666">
    Confidence: {_confidence_badge("high")} distinctive signal
    &nbsp;·&nbsp;
    {_confidence_badge("medium")} shared/indirect signal
    &nbsp;·&nbsp;
    {_confidence_badge("low")} weak hint (HTML)
  </p>
  <table style="width:100%;border-collapse:collapse;margin-top:8px">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Category</th>
      <th style="padding:6px 8px;text-align:left">Technology</th>
      <th style="padding:6px 8px;text-align:left">Confidence</th>
      <th style="padding:6px 8px;text-align:left">Hint</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {tp_html}
  <p style="font-size:14px;color:#888;margin-top:12px">
    {len(technos)} technolog(y/ies) detected over {req_count} analyzed requests.
    To re-run detection alone:
    <code>python3 detect_tech.py &lt;source_dir&gt;</code>
  </p>
</section>"""


def _section_efootprint(results, topology_svg=None, gains=None):
    """Section 'Environmental impact (hypothetical estimate)' - CO2e from e-footprint."""
    if not results:
        return ""

    totals = results.get("totals", {})
    hyp = results.get("hypotheses", {})
    visits = results.get("visits_per_year", 0)
    traffic = results.get("traffic", {})
    _traffic_is_sourced = traffic.get("source") not in (None, "default", "parameter")
    _traffic_kpi_sub = (
        f'{traffic.get("source")}{", " + traffic["snapshot"] if traffic.get("snapshot") else ""}'
        if _traffic_is_sourced else "assumption"
    )

    total_kg = totals.get("total_kg_co2e_per_year", 0)
    per_visit_g = totals.get("per_visit_g_co2e", 0)
    fab = totals.get("fabrication_kg_co2e_per_year", {})
    ener = totals.get("energy_kg_co2e_per_year", {})

    fab_total = sum(fab.values())
    ener_total = sum(ener.values())

    # KPIs at the top
    kpi_style = (
        "flex:1;min-width:180px;background:white;border:1px solid #ddd;"
        "border-radius:6px;padding:16px;text-align:center"
    )
    kpis = (
        f'<div style="display:flex;flex-wrap:wrap;gap:12px;margin:16px 0 24px">'
        f'  <div style="{kpi_style}">'
        f'    <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px">Annual total</div>'
        f'    <div style="font-size:28px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">~{total_kg:.1f} kg CO2e</div>'
        f'    <div style="font-size:14px;color:#888">for {visits:,} visits/year ({_traffic_kpi_sub})</div>'
        f'  </div>'
        f'  <div style="{kpi_style}">'
        f'    <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px">Per visit</div>'
        f'    <div style="font-size:28px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">~{per_visit_g:.2f} g CO2e</div>'
        f'    <div style="font-size:14px;color:#888">order of magnitude (assumption)</div>'
        f'  </div>'
        f'  <div style="{kpi_style}">'
        f'    <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px">Manufacturing / Energy</div>'
        f'    <div style="font-size:24px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">'
        f'{fab_total:.1f} / {ener_total:.1f} kg</div>'
        f'    <div style="font-size:14px;color:#888">amortized / annual usage</div>'
        f'  </div>'
        f'</div>'
    )

    # Breakdown: simple stacked bars for manufacturing and energy
    def _breakdown_rows(d, decimals=2):
        total = sum(d.values()) or 1e-9
        rows = ""
        for cat, kg in sorted(d.items(), key=lambda x: -x[1]):
            if kg <= 0:
                continue
            pct = kg / total * 100
            bar = (
                f'<div style="background:#eee;border-radius:3px;height:14px;position:relative;overflow:hidden">'
                f'  <div style="background:{OCTO_BLUE};height:100%;width:{pct:.1f}%"></div>'
                f'</div>'
            )
            rows += (
                f'<tr>'
                f'<td style="padding:6px 8px">{cat}</td>'
                f'<td style="padding:6px 8px;text-align:right;font-variant-numeric:tabular-nums">'
                f'{kg:.{decimals}f} kg</td>'
                f'<td style="padding:6px 8px;text-align:right;color:#666;font-variant-numeric:tabular-nums">'
                f'{pct:.1f} %</td>'
                f'<td style="padding:6px 8px;width:180px">{bar}</td>'
                f'</tr>'
            )
        return rows

    fab_table = f"""<table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Item (manufacturing)</th>
      <th style="padding:6px 8px;text-align:right">kg CO2e/year</th>
      <th style="padding:6px 8px;text-align:right">Share</th>
      <th style="padding:6px 8px">Breakdown</th>
    </tr></thead>
    <tbody>{_breakdown_rows(fab, 2)}</tbody>
  </table>"""

    ener_table = f"""<table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Item (energy)</th>
      <th style="padding:6px 8px;text-align:right">kg CO2e/year</th>
      <th style="padding:6px 8px;text-align:right">Share</th>
      <th style="padding:6px 8px">Breakdown</th>
    </tr></thead>
    <tbody>{_breakdown_rows(ener, 4)}</tbody>
  </table>"""

    # Storage (manufacturing) is not a data-volume measurement: below 1 TB,
    # e-footprint/Boavizta has no resolution (any non-null storage is rounded up to
    # a whole 1 TB disk). This item reflects the number of declared servers, not
    # an audit datum about storage practices (cf. EOF dimension 4, assessed
    # separately). Decision recorded in tmp/handoff-2026-08-06-efootprint-fourchettes.md
    # (section C.3), never written in the report before today.
    storage_caveat_html = ""
    if fab.get("Storage", 0) > 0:
        storage_caveat_html = f"""
  <p style="font-size:14px;color:#888;margin:8px 0 0">
    The <b>Storage</b> item above ({fab.get("Storage", 0):.2f} kg) does not measure a
    data volume: below 1 TB, e-footprint has no resolution (any non-null storage
    is rounded up to a whole 1 TB disk on the Boavizta side). This figure reflects
    the number of declared servers, not the real data management practices
    (archiving, duplicates, test databases...) — see EOF dimension "4 — Storage and
    data", assessed independently of this calculation.
  </p>"""

    # Assumptions table
    # LOT 1: page_weight_kb = TRANSFERRED weight (real network) if available; we show the
    # decompressed one as a reference when the two differ (env-data >= 1.4).
    _pw_transferred = hyp.get("page_weight_transferred_kb")
    _pw_uncompressed = hyp.get("page_weight_uncompressed_kb")
    if _pw_transferred:
        _ratio = hyp.get("compression_ratio")
        _pw_label = "Transferred page weight (real network)"
        _pw_note = f' <span style="color:#888">(decompressed: {_pw_uncompressed} kB'
        _pw_note += f', ratio {_ratio})</span>' if _ratio else ')</span>'
        _pw_value = f'{hyp.get("page_weight_kb", "?")} kB{_pw_note}'
    else:
        _pw_label = "Page weight (representative)"
        _pw_value = f'{hyp.get("page_weight_kb", "?")} kB'
    hyp_rows = [
        (_pw_label, _pw_value,                                                          hyp.get("confidence_page_weight")),
        ("Load duration",                    f'{hyp.get("request_duration_ms", "?")} ms', hyp.get("confidence_request_duration")),
        ("Hosting country",                 hyp.get("country", "?"),                     hyp.get("confidence_country")),
        ("Electricity carbon intensity",    f'{hyp.get("carbon_intensity_g_kwh", "?")} g/kWh', hyp.get("confidence_carbon_intensity")),
        ("Hosting provider",                hyp.get("provider", "?"),                    hyp.get("confidence_provider")),
        ("Instance type",                   *_instance_type_row(hyp)),
        ("Device mix (mobile / desktop)",   f'{hyp.get("phone_fraction", 0):.0%} / {hyp.get("desktop_fraction", 0):.0%}',  hyp.get("confidence_device_mix")),
    ]
    audience_mix = hyp.get("audience_mix")
    if audience_mix:
        _asrc = hyp.get("audience_source", "default")
        if _asrc == "default":
            _asrc_short = "default"
        elif isinstance(_asrc, str) and "similarweb" in _asrc.lower():
            _asrc_short = "SimilarWeb (estimated)"
        elif isinstance(_asrc, str) and _asrc.startswith("manual entry"):
            _asrc_short = "manual entry"
        else:
            _asrc_short = "estimated"
        hyp_rows.append(
            ("Audience country mix (→ iOS/macOS)",
             ", ".join(f'{cc} {w:.0%}' for cc, w in audience_mix.items()),
             _audience_source_label(_asrc_short, hyp.get("audience_source_url"))))
    hyp_rows += [
        ("Network (derived from device mix)", "mobile → mobile network ; desktop → wifi", "derived"),
        ("Estimated annual traffic",        f'{visits:,} visits',                       _traffic_source_label(traffic)),
        ("Server storage (nb. of declared servers, not a data volume — see below)",
         f'{hyp.get("storage_gb", 50)} GB',           "default_script"),
    ]
    hyp_html = "".join(
        f'<tr>'
        f'<td style="padding:6px 8px">{label}</td>'
        f'<td style="padding:6px 8px"><b>{value}</b></td>'
        f'<td style="padding:6px 8px">{_confidence_badge(conf)}</td>'
        f'</tr>'
        for label, value, conf in hyp_rows
    )

    warning = (
        f'<div style="background:#fff3cd;border-left:4px solid #ffc107;'
        f'padding:12px 16px;margin:16px 0;border-radius:4px">'
        f'<b>&#9888; Hypothetical estimate</b><br>'
        f'These values are <b>orders of magnitude</b> computed from automatically '
        f'collected data (HAR, CrUX, IP geolocation) and many default assumptions. '
        f'They <b>are not a real measurement</b>. They serve to compare '
        f'scenarios and identify the dominant items.'
        f'</div>'
    )

    # Page weight composition (documentary: explains the input, does not enter
    # the CO2e calculation which relies on the aggregated total of page_weight_kb).
    # LOT 4: TRANSFERRED weight (real network, LOT 1) as the main value if available,
    # decompressed as a reference — consistency with page_weight_kb above.
    weight_by_type_transfer = hyp.get("weight_by_type_transfer_bytes") or {}
    weight_by_type_uncompressed = hyp.get("weight_by_type_bytes") or {}
    weight_by_type = weight_by_type_transfer or weight_by_type_uncompressed
    _using_transfer = bool(weight_by_type_transfer)
    weight_composition = ""
    if weight_by_type:
        _type_labels = {
            "html": "HTML", "css": "CSS", "js": "JavaScript",
            "image": "Images", "font": "Fonts", "other": "Other",
        }
        _wtotal = sum(v for v in weight_by_type.values() if v > 0) or 1e-9
        comp_rows = ""
        for typ, nbytes in sorted(weight_by_type.items(), key=lambda x: -x[1]):
            if nbytes <= 0:
                continue
            pct = nbytes / _wtotal * 100
            kb = nbytes / 1024
            kb_uncompressed = weight_by_type_uncompressed.get(typ, 0) / 1024
            note = (
                f' <span style="color:#888;font-size:13px">(decompressed: {kb_uncompressed:,.0f} KB)</span>'
                if _using_transfer and weight_by_type_uncompressed else ""
            )
            bar = (
                f'<div style="background:#eee;border-radius:3px;height:14px;position:relative;overflow:hidden">'
                f'  <div style="background:{OCTO_BLUE};height:100%;width:{pct:.1f}%"></div>'
                f'</div>'
            )
            comp_rows += (
                f'<tr>'
                f'<td style="padding:6px 8px">{_type_labels.get(typ, typ)}</td>'
                f'<td style="padding:6px 8px;text-align:right;font-variant-numeric:tabular-nums">'
                f'{kb:,.0f} KB{note}</td>'
                f'<td style="padding:6px 8px;text-align:right;color:#666;font-variant-numeric:tabular-nums">'
                f'{pct:.1f} %</td>'
                f'<td style="padding:6px 8px;width:180px">{bar}</td>'
                f'</tr>'
            )
        req_count = hyp.get("page_request_count")
        tp_share = hyp.get("third_party_transfer_share") if _using_transfer else hyp.get("third_party_share")
        tp_requests = hyp.get("third_party_requests")
        tp_bytes = hyp.get("third_party_transfer_bytes") if _using_transfer else hyp.get("third_party_bytes")
        meta_bits = []
        if req_count is not None:
            meta_bits.append(f'{req_count} requests')
        if tp_share is not None:
            _tp_extra = ""
            if tp_requests is not None and tp_bytes is not None:
                _tp_extra = f' ({tp_requests} requests, {tp_bytes / 1024:,.0f} KB)'
            meta_bits.append(
                f'third-party resources: <b>{tp_share * 100:.1f} %</b> of the weight{_tp_extra}')
        meta_line = (
            f'<p style="font-size:14px;color:#666;margin:8px 0 0">{" &nbsp;·&nbsp; ".join(meta_bits)}</p>'
            if meta_bits else ""
        )
        _weight_label = "transferred weight (real network)" if _using_transfer else "decompressed weight"
        weight_composition = f"""
  <h3 style="margin-top:24px">Page weight composition of the representative page</h3>
  <p style="font-size:14px;color:#888;margin:0 0 8px">
    Breakdown by resource type of the heaviest page of the journey (the one used
    as reference weight for the calculation), in {_weight_label}. Documentary: this
    breakdown <b>explains</b> the retained weight, it does <b>not enter separately into the
    CO2e calculation</b>.
  </p>
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Resource type</th>
      <th style="padding:6px 8px;text-align:right">Weight</th>
      <th style="padding:6px 8px;text-align:right">Share</th>
      <th style="padding:6px 8px">Breakdown</th>
    </tr></thead>
    <tbody>{comp_rows}</tbody>
  </table>
  {meta_line}"""

    dominant_fab = max(fab, key=fab.get) if fab else "?"
    dominant_ener = max(ener, key=ener.get) if ener else "?"

    # Summary at the top, plain language: explicit request from the user
    # for a "very synthetic and clear" reading before the technical detail
    # (tables/ranges below). Categorical colors VALIDATED by the dataviz skill
    # script (validate_palette.js): the existing OCTO blue
    # (#5BA1BC) fails the chroma floor in categorical use — replaced
    # here by the reference blue/orange pair, never reused for the
    # text (text tokens stay OCTO_DARK/grey, cf. the rule "text
    # never carries the series color").
    _SYN_FAB_COLOR = "#2a78d6"
    _SYN_ENER_COLOR = "#eb6834"
    _POST_LABELS = {
        "Devices": "visitor devices (phones, computers)",
        "Servers": "application servers",
        "Storage": "storage",
        "Network": "network (data transport)",
        "ExternalAPIs": "generative AI calls",
        "EdgeDevices": "intermediate network equipment",
    }
    _grand_total = fab_total + ener_total
    _fab_share = fab_total / _grand_total if _grand_total else 0
    _ener_share = 1 - _fab_share
    _top_post_kg = {}
    for _poste in set(fab) | set(ener):
        _top_post_kg[_poste] = fab.get(_poste, 0) + ener.get(_poste, 0)
    _top_post = max(_top_post_kg, key=_top_post_kg.get) if _top_post_kg else None
    _top_post_share = (_top_post_kg.get(_top_post, 0) / _grand_total) if _top_post and _grand_total else 0
    _top_post_label = _POST_LABELS.get(_top_post, _top_post or "?")

    _fab_bar_pct = _fab_share * 100
    _ener_bar_pct = _ener_share * 100
    summary_html = f"""
  <div style="background:white;border:1px solid #ddd;border-radius:6px;padding:16px 20px;margin:16px 0 24px">
    <p style="font-size:16px;color:#333;margin:0 0 12px;line-height:1.5">
      This site emits the equivalent of <b>~{total_kg:.1f} kg of CO2e per year</b>, of which
      <b>{_fab_share:.0%}</b> comes from the <b>manufacturing</b> of the equipment (amortized over their
      lifetime) and <b>{_ener_share:.0%}</b> from the <b>energy</b> consumed in use.
      The heaviest item, all causes combined, is
      <b>{_top_post_label}</b> ({_top_post_share:.0%} of the total).
    </p>
    <div role="img" aria-label="Breakdown {_fab_share:.0%} manufacturing, {_ener_share:.0%} energy">
      <div style="display:flex;height:22px;border-radius:4px;overflow:hidden;gap:2px">
        <div style="background:{_SYN_FAB_COLOR};width:{_fab_bar_pct:.1f}%"></div>
        <div style="background:{_SYN_ENER_COLOR};width:{_ener_bar_pct:.1f}%"></div>
      </div>
      <div style="display:flex;gap:20px;margin-top:8px;font-size:13px;color:#555">
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{_SYN_FAB_COLOR};margin-right:5px"></span>Manufacturing — {fab_total:.1f} kg ({_fab_share:.0%})</span>
        <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{_SYN_ENER_COLOR};margin-right:5px"></span>Energy — {ener_total:.1f} kg ({_ener_share:.0%})</span>
      </div>
    </div>
  </div>"""

    # Uncertainty ranges (Lot 4bis, rendered in Lot 9): two MEASURED axes by
    # replaying the same model, never cumulative (cf. ranges.py and persistent memory
    # "non-cumulative ranges"). Absent if model.ranges does not exist (old schema).
    ranges = (results.get("model") or {}).get("ranges")
    ranges_html = ""
    if ranges:
        infra_lo, infra_hi = ranges["infra_range_kg"]
        usage_lo, usage_hi = ranges["usage_range_kg"]

        def _range_row(label, lo, hi, detail):
            if abs(hi - lo) < 1e-9:
                span = (f'{lo:.1f} kg <span style="color:#888;font-size:14px">'
                        f'(closed range, no measurable uncertainty here)</span>')
            else:
                ratio = f' <span style="color:#888;font-size:14px">({hi / lo:.2f}x)</span>' if lo else ""
                span = f'{lo:.1f} - {hi:.1f} kg{ratio}'
            return (
                f'<tr><td style="padding:6px 8px">{label}</td>'
                f'<td style="padding:6px 8px"><b>{span}</b></td>'
                f'<td style="padding:6px 8px;font-size:14px;color:#666">{detail}</td></tr>'
            )

        ranges_html = f"""
  <h3 style="margin-top:24px">Uncertainty ranges</h3>
  <p style="font-size:15px;color:#666;margin:0 0 8px">
    Two distinct uncertainties bound the central estimate above, each measured
    by replaying the same model with a single assumption changed at a time. They
    are <b>never</b> added together: stacking the worst case of each axis
    would assume all uncertainties play in the same direction at the same time, which
    would be statistically dishonest.
  </p>
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Axis</th>
      <th style="padding:6px 8px;text-align:left">Range</th>
      <th style="padding:6px 8px;text-align:left">What varies</th>
    </tr></thead>
    <tbody>
      {_range_row("Infrastructure", infra_lo, infra_hi,
                   "server sizing mode: serverless ↔ autoscaling")}
      {_range_row("Usage", usage_lo, usage_hi,
                   "Nielsen reading time: recalibrated (SimilarWeb measurement) ↔ raw")}
    </tbody>
  </table>"""
        if fab.get("Storage", 0) > 0:
            ranges_html += (
                '\n  <p style="font-size:14px;color:#888;margin:8px 0 0">'
                "Storage (storage_gb) deliberately does not appear as a 3rd axis "
                "here: below 1 TB, e-footprint has no resolution (see above and "
                "methodology appendix) — a range on this parameter would be closed "
                "or artificial, not a real measured uncertainty.</p>"
            )

    # CDN/third-party vs generative AI consistency (decided in Lot 7): displayed only if this
    # site has at least one generative AI call (non-zero ExternalAPIs item), otherwise the
    # distinction has nothing to explain on this particular site.
    external_apis_kg = fab.get("ExternalAPIs", 0) + ener.get("ExternalAPIs", 0)
    cdn_ia_html = ""
    if external_apis_kg > 0:
        cdn_ia_html = """
  <p style="font-size:15px;color:#666;margin:12px 0 0">
    This site's third-party services are treated differently depending on what they
    really do. A CDN or a font serves an already-ready file: the necessary
    computation is almost nil, the bulk of their cost is network, already counted
    in this report. Conversely, a call to a generative AI model triggers a real
    computation on every request (the model produces the text word by word): this computation is
    counted separately, via a specialized library (EcoLogits), because no equivalent
    public source exists for a CDN.
  </p>"""

    # "Mental math" marker per step (Lot 10): what weighs the most in the
    # journey, so reading no longer has to guess why one step
    # counts more than another. `impact_pct_of_grand_total` comes from a
    # PROPORTIONAL SPLIT of the already computed Devices/Network CO2e
    # (step_impact_shares(), build.py): it is not an independent measurement
    # per step, the label must say so to avoid suggesting a
    # calculation finesse that does not exist. Absent if model.steps does not exist
    # (old schema): backward-compatible report, like the other Lot 9 blocks.
    model_steps = (results.get("model") or {}).get("steps") or []
    steps_block = ""
    if model_steps:
        steps_sorted = sorted(
            model_steps, key=lambda s: s.get("impact_pct_of_grand_total", 0), reverse=True)
        step_rows = ""
        for s in steps_sorted:
            pct = s.get("impact_pct_of_grand_total", 0) * 100
            time_s = s.get("user_time_min", 0) or 0
            label = s.get("url") or s.get("label", "?")
            bar = (
                f'<div style="background:#eee;border-radius:3px;height:14px;position:relative;overflow:hidden">'
                f'  <div style="background:{OCTO_BLUE};height:100%;width:{min(pct, 100):.1f}%"></div>'
                f'</div>'
            )
            step_rows += (
                f'<tr>'
                f'<td style="padding:6px 8px">{label}</td>'
                f'<td style="padding:6px 8px;text-align:right;font-variant-numeric:tabular-nums">{time_s:.0f} s</td>'
                f'<td style="padding:6px 8px">{_confidence_badge(s.get("user_time_confidence"))}</td>'
                f'<td style="padding:6px 8px;text-align:right;color:#666;font-variant-numeric:tabular-nums">{pct:.1f} %</td>'
                f'<td style="padding:6px 8px;width:160px">{bar}</td>'
                f'</tr>'
            )
        steps_block = f"""
  <h3 style="margin-top:24px">What weighs the most, step by step</h3>
  <p style="font-size:14px;color:#888;margin:0 0 8px">
    <b>Proportional</b> split of the CO2e of visitor devices and network already
    computed above, pro rata of the time spent and the weight transferred per step. This
    is <b>not</b> an independent measurement per step: it is a marker to spot
    at a glance the steps that count the most in the total.
  </p>
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Step</th>
      <th style="padding:6px 8px;text-align:right">Retained time</th>
      <th style="padding:6px 8px;text-align:left">Source</th>
      <th style="padding:6px 8px;text-align:right">Share of total CO2e</th>
      <th style="padding:6px 8px">Breakdown</th>
    </tr></thead>
    <tbody>{step_rows}</tbody>
  </table>"""

    # Topology diagram (Step 25 of the efootprint skill): documented proof of the
    # model validated with the user before calculation, NOT regenerated here (report
    # backward-compatible if absent, cf. load_topology_svg()).
    topology_block = ""
    if topology_svg:
        topology_block = f"""
  <h3 style="margin-top:24px">Model topology</h3>
  <p style="font-size:15px;color:#666;margin:0 0 8px">
    Model validated with you before calculation (Step 25): 1st-party servers, jobs,
    third-party hosts, DB/streaming/generative-AI suspicions detected from the HAR, and
    main calculation assumptions (annual traffic, device/country mix, reading time).
  </p>
  <div style="max-width:100%;overflow-x:auto;border:1px solid #ddd;border-radius:6px;padding:12px;background:white">
    {topology_svg}
  </div>"""

    # Pointer to the CO2e gain per recommendation tier (efootprint-recommendations-gains.json),
    # computed and displayed in _recommendations_gains_block() (Recommendations section): not duplicated
    # here, only referenced, to keep a single calculation and a single place to fix.
    gains_ref_html = ""
    if gains and gains.get("tiers"):
        gains_ref_html = (
            '<p style="font-size:15px;color:#555;margin:8px 0 0">'
            'The estimated gain if you apply the prioritized recommendations (tiers prio1 / '
            'prio1+2 / prio1+2+3) is detailed in the block '
            '<a href="#gain-co2e">Estimated CO2e gain</a> of the section '
            '<a href="#recommandations">Recommendations</a>.</p>'
        )

    return f"""<section id="efootprint">
  <h2>Environmental impact (estimate {_glossary_link("CO2e")})</h2>
  {summary_html}
  <p style="font-size:16px;color:#555;margin-bottom:8px">
    Estimate via the <a href="https://github.com/Boavizta/e-footprint" target="_blank" rel="noopener">e-footprint</a> library (Boavizta).
    Dominant manufacturing item: <b>{dominant_fab}</b> ({fab.get(dominant_fab, 0):.1f} kg CO2e/year).
    Dominant energy item: <b>{dominant_ener}</b> ({ener.get(dominant_ener, 0):.3f} kg CO2e/year).
  </p>
  {warning}
  {kpis}
  {gains_ref_html}
  {ranges_html}
  {topology_block}

  <h3 style="margin-top:24px">Breakdown by item</h3>
  <div style="display:grid;grid-template-columns:1fr;gap:20px">
    <div>
      <h4 style="margin:0 0 8px">Manufacturing (amortized over lifetime)</h4>
      {fab_table}
    </div>
    <div>
      <h4 style="margin:0 0 8px">Energy (annual usage)</h4>
      {ener_table}
    </div>
  </div>
  {storage_caveat_html}
  {cdn_ia_html}
  {weight_composition}
  {steps_block}

  <h3 style="margin-top:24px">Input assumptions</h3>
  <p style="font-size:15px;color:#666">
    Confidence level: {_confidence_badge("high")} API/HAR
    &nbsp;·&nbsp;
    {_confidence_badge("medium")} inferred
    &nbsp;·&nbsp;
    {_confidence_badge("declared")} publicly declared by the organization
    &nbsp;·&nbsp;
    {_confidence_badge("low")} typical value
    &nbsp;·&nbsp;
    {_confidence_badge("unjustified")} manual choice without proof
    &nbsp;·&nbsp;
    {_confidence_badge("default_efootprint")} e-footprint library default value
    &nbsp;·&nbsp;
    {_confidence_badge("default_script")} value set by our script (not e-footprint)
  </p>
  <table style="width:100%;border-collapse:collapse;margin-top:8px">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Parameter</th>
      <th style="padding:6px 8px;text-align:left">Retained value</th>
      <th style="padding:6px 8px;text-align:left">Source</th>
    </tr></thead>
    <tbody>{hyp_html}</tbody>
  </table>

  <p style="font-size:14px;color:#888;margin-top:12px">
    To recompute with other assumptions:
    <code>python3 run_efootprint.py &lt;source_dir&gt; --visits N --instance TYPE</code>
    then regenerate the report.
  </p>
</section>"""


def _section_eof(results, radar_svg_text=None):
    """Section 'Optimization potential (EOF framework)' - from
    eof-audit-results.json (run_eof.py). Absent -> section omitted, report
    backward-compatible (same principle as _section_efootprint()).

    The vast majority of the 54 detailed criteria CANNOT be deduced
    from the audit data (organizational/product questions): the real
    observed ratio is low (a few criteria out of 54), displayed as-is,
    never glossed over. A dimension with no answer at all is marked "no
    answer", never a false 0% (cf. radar_svg() of the eof skill)."""
    if not results:
        return ""

    total = results.get("total_criteria", 0)
    # Read answered_criteria (new, LOT 1) with fallback to auto_answered_criteria (old)
    n_answered = results.get("answered_criteria") if results.get("answered_criteria") is not None else results.get("auto_answered_criteria", 0)
    n_partial = results.get("criteria_with_partial_evidence", 0)
    potential = results.get("global_optimization_potential_pct")
    dimensions = results.get("dimensions", [])
    diag = results.get("quick_diag_overview", {})

    # "answered" mixes several provenances: collected/estimated/assumed come from our
    # tools (automatic), declared comes from a page published by the audited service,
    # stated comes from a human who filled in the questionnaire during THIS audit. The
    # confusing them as "answered automatically" produces a false sentence as soon as a
    # questionnaire has been merged (seen in session 32 on octo.com: 19 stated announced
    # as automatic). Distinguish the three, never aggregate them under a single word.
    provenance = results.get("answered_by_provenance") or {}
    n_auto = provenance.get("collected", 0) + provenance.get("estimated", 0) + provenance.get("assumed", 0)
    n_declared = provenance.get("declared", 0)
    n_stated = provenance.get("stated", 0)

    phrase_answered = f'<b>{n_auto}</b> could be answered automatically from the audit data'
    if n_declare:
        phrase_answered += f', <b>{n_declared}</b> from a public declaration of the audited service'
    if n_precise:
        phrase_answered += f', <b>{n_stated}</b> by a person of the audited service via the questionnaire'

    warning = (
        f'<div style="background:#fff3cd;border-left:4px solid #ffc107;'
        f'padding:12px 16px;margin:16px 0;border-radius:4px">'
        f'<b>&#9888; Very partial automatic audit</b><br>'
        f'Out of {total} detailed criteria, {phrase_answered} '
        f'(+ {n_partial} contextual hint(s), never a validated answer). The others '
        f'remain <b>"I don\'t know"</b> by construction: they are '
        f'organizational or product questions that no technical measurement '
        f'can settle. Full criterion-by-criterion detail in the appendix. '
        f'To fill in these criteria, generate the corresponding questionnaire with the script '
        f'<code>generate_questionnaire.py</code> (it produces a '
        f'<code>questionnaire-eof.md</code> file) and send it to the audited service, which can '
        f'answer it directly.'
        f'</div>'
    )

    # Quick diagnostic (0) preview — always "to be filled in by a human", never
    # an automatic answering attempt (different 1-5 scale, explicit
    # decision): placed BEFORE the radar of the 6 detailed dimensions.
    def _diag_row(q):
        duplicate_note = ' <span style="color:#888;font-size:12px">(exact duplicate of 3.3)</span>' if q["id"] == "0.16" else ""
        if q.get("answer"):
            value = f'{q["answer"].replace("<", "&lt;")}{duplicate_note}'
            conf = _provenance_of(q)
            source = q.get("source") or "—"
        elif q.get("context_index"):
            value = f'I don\'t know <span style="color:#888">— indicative data: {q["context_index"]}</span>{duplicate_note}'
            conf = _provenance_of(q)
            source = q.get("source") or "—"
        else:
            value = f'I don\'t know{duplicate_note}'
            conf = None
            source = "reserved for human assessment (1-5 scale, not derivable from audit data)"
        src_html = _confidence_badge(conf) if conf else '<span style="color:#aaa">—</span>'
        return (
            f'<tr>'
            f'<td style="padding:5px 8px;white-space:nowrap">{q["id"]}</td>'
            f'<td style="padding:5px 8px">{q["criterion"]}</td>'
            f'<td style="padding:5px 8px">{value}</td>'
            f'<td style="padding:5px 8px">{src_html}</td>'
            f'<td style="padding:5px 8px;font-size:13px;color:#666">{source}</td>'
            f'</tr>'
        )

    diag_total = diag.get("total_questions", 0)
    diag_answered = sum(1 for q in diag.get("questions", []) if q.get("answer"))
    diag_pct = (diag_answered / diag_total * 100) if diag_total else 0
    diag_bar = (
        f'<div style="background:#e0e0e0;border-radius:3px;height:10px;width:120px;'
        f'display:inline-block;vertical-align:middle;margin-left:10px;overflow:hidden">'
        f'<div style="background:{OCTO_BLUE};height:100%;width:{diag_pct:.0f}%"></div>'
        f'</div>'
    )
    diag_header_row = (
        f'<tr><td colspan="5" style="padding:10px 8px 6px;background:{OCTO_PALE};font-weight:bold">'
        f'🏦 0 — Quick diagnostic{diag_bar} '
        f'<span style="font-weight:normal;font-size:13px;color:#555">{diag_answered}/{diag_total}</span>'
        f'</td></tr>'
    )
    diag_rows = "".join(_diag_row(q) for q in diag.get("questions", []))
    diag_table = f"""<table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:5px 8px;text-align:left">ID</th>
      <th style="padding:5px 8px;text-align:left">Criterion</th>
      <th style="padding:5px 8px;text-align:left">Answer</th>
      <th style="padding:5px 8px;text-align:left">Provenance</th>
      <th style="padding:5px 8px;text-align:left">Source / data used</th>
    </tr></thead>
    <tbody>{diag_header_row}{diag_rows}</tbody>
  </table>"""
    diag_block = f"""
  <h3>🏦 0 — Quick diagnostic (preview)</h3>
  <p style="font-size:15px;color:#666;margin:0 0 8px">
    {diag.get("total_questions", 0)} questions, 1-to-5 scale, <b>never filled in
    automatically</b> (explicit decision: no audit data can reliably
    judge these criteria), with one exception (0.16, exact duplicate
    of 3.3, see below). To be assessed by a human in the <code>eof</code> skill
    template.
  </p>
  <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px 16px;margin:12px 0;border-radius:4px">
    <b>&#9888; A prerequisite, not a bonus</b><br>
    The EOF framework is strict: if the result of this diagnostic is very
    low, there is no need to go through the detail of the 6 dimensions
    below. The optimization potential is either already low, or too
    costly to reach. To be assessed by a human BEFORE reading on.
  </div>
  {diag_table}"""

    # KPIs at the top, scoped to the 54 detailed criteria only (decision of 2026-09-03)
    kpi_style = (
        "flex:1;min-width:180px;background:white;border:1px solid #ddd;"
        "border-radius:6px;padding:16px;text-align:center"
    )
    potential_txt = f"~{potential:.0f}%" if potential is not None else "n/a"

    # Overall completeness (new field of the process layer, optional)
    completeness_global = results.get("global_completeness_pct")
    completeness_kpi = ""
    if completeness_global is not None:
        completeness_kpi = (
            f'  <div style="{kpi_style}">'
            f'    <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px">Completeness</div>'
            f'    <div style="font-size:28px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">{completeness_global:.0f}%</div>'
            f'    <div style="font-size:14px;color:#888">criteria actually examined</div>'
            f'  </div>'
        )

    # Discarded criteria (new LOT C field, optional)
    criteria_discarded = results.get("discarded_criteria")
    discarded_kpi = ""
    if criteria_discarded is not None:
        discarded_kpi = (
            f"  <div style=\"{kpi_style}\">"
            f"    <div style=\"font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px\">Discarded</div>"
            f"    <div style=\"font-size:28px;font-weight:bold;color:{OCTO_DARK};margin:6px 0\">{criteria_discarded}</div>"
            f"    <div style=\"font-size:14px;color:#888\">criteria outside the service's scope</div>"
            f"  </div>"
        )

    kpis = (
        f'<div style="display:flex;flex-wrap:wrap;gap:12px;margin:16px 0 24px">'
        f'  <div style="{kpi_style}">'
        f'    <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px">Criteria answered</div>'
        f'    <div style="font-size:28px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">{n_answered}/{total}</div>'
        f'    <div style="font-size:14px;color:#888">detailed criteria, whatever the provenance</div>'
        f'  </div>'
        f'  <div style="{kpi_style}">'
        f"    <div style=\"font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px\">Optimization potential</div>"
        f'    <div style="font-size:28px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">{potential_txt}</div>'
        f'    <div style="font-size:14px;color:#888">over all criteria of each dimension</div>'
        f'  </div>'
        f'{completeness_kpi}'
        f'{discarded_kpi}'
        f'</div>'
    )

    radar_block = ""
    if radar_svg_text:
        provenance_reminder = (
            '<div style="margin-top:10px;font-size:13px;color:#444;text-align:left;'
            'max-width:700px;margin-left:auto;margin-right:auto">'
            '<b>Detail of the 5 possible provenances:</b><br>'
            f'{_confidence_badge("collected")} real measurement &middot; '
            f'{_confidence_badge("estimated")} deduction of an order of magnitude &middot; '
            f'{_confidence_badge("declared")} public declaration found &middot; '
            f'{_confidence_badge("stated")} service answer via the questionnaire '
            '&rarr; <b>retained potential</b> (solid)<br>'
            f'{_confidence_badge("assumed")} deduction from a weak hint '
            '&rarr; <b>uncertainty margin</b> (hatched)'
            '</div>'
        )
        radar_block = f"""
  <div style="max-width:100%;overflow-x:auto;border:1px solid #ddd;border-radius:6px;padding:12px;background:white;text-align:center">
    {radar_svg_text}
    {provenance_reminder}
  </div>"""

    criteria_list = results.get("criteria", [])
    dim_rows = ""
    for d in dimensions:
        # LOT C: handle discarded criteria
        out_of_scope = d.get("out_of_scope", False)
        discarded = d.get("discarded", 0)

        if out_of_scope:
            # Dimension entirely out of scope: never display 0%
            discarded_s = "s" if discarded > 1 else ""
            pct_txt = f'<span style="color:#888">out of scope</span> <span style="font-size:0.85em;color:#999">({discarded} discarded{discarded_s})</span>'
            completeness_txt = ""
        else:
            # Accept both names (old score_pct, new optimization_potential_pct)
            pct_val = d.get("optimization_potential_pct") if d.get("optimization_potential_pct") is not None else d.get("score_pct")
            # Same label as the radar just above: two different words for the
            # same state ("no data" here, "no answer" on the figure) would make
            # the reader believe they designate two distinct situations.
            pct_txt = f"{pct_val:.0f}%" if pct_val is not None else '<span style="color:#888">no answer</span>'

            # Display completeness if available (new LOT 1 fields)
            completeness = d.get("completeness_pct")
            completeness_txt = f' <span style="color:#888;font-size:0.85em">({completeness:.0f}% completeness)</span>' if completeness is not None else ""

            # Add the discarded count if partially discarded
            if discarded > 0:
                discarded_s = "s" if discarded > 1 else ""
                completeness_txt += f' <span style="font-size:0.85em;color:#999">({discarded} discarded{discarded_s})</span>'

        dim_rows += (
            f'<tr>'
            f'<td style="padding:6px 8px">{d["name"]}</td>'
            f'<td style="padding:6px 8px;text-align:right">{d["answered"]}/{d["total"]}</td>'
            f'<td style="padding:6px 8px;text-align:right;font-weight:bold">{pct_txt}{completeness_txt}</td>'
            f'</tr>'
        )
        # With only 1 answered criterion, the percentage rests on a single judgment:
        # say which one to contextualize the figure, otherwise the % gives a false
        # impression of an overall verdict (cf. plan).
        if d.get("answered") == 1:
            matched = next(
                (c for c in criteria_list if c.get("dimension") == d["name"] and c.get("answer")),
                None,
            )
            if matched:
                dim_rows += (
                    f'<tr><td colspan="3" style="padding:0 8px 10px;font-size:13px;color:#888">'
                    f'(rests on {matched["id"]} — {matched["criterion"]} → {matched["answer"]})'
                    f'</td></tr>'
                )
    dim_table = f"""<table style="width:100%;border-collapse:collapse;margin-top:12px">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Dimension</th>
      <th style="padding:6px 8px;text-align:right">Answered</th>
      <th style="padding:6px 8px;text-align:right">Optimization potential</th>
    </tr></thead>
    <tbody>{dim_rows}</tbody>
  </table>"""

    return f"""<section id="eof">
  <h2>Optimization potential (EOF framework)</h2>
  {warning}
  {diag_block}
  <h3 style="margin-top:24px">Six detailed dimensions</h3>
  {kpis}
  {radar_block}
  {dim_table}
  <p style="font-size:14px;color:#888;margin-top:12px">
    A higher percentage signals a greater optimization potential: the
    service is less mature on this dimension, it does not behave any better there. Criterion-by-criterion
    detail, source and provenance of each answer in the appendix.
  </p>
</section>"""


def _section_eof_detail(results):
    """Standalone appendix (not a sub-part of Methodology & assumptions,
    content too substantial for that): the detail of the EOF criteria, one by one —
    answer or "I don't know", confidence, source/data used. Never
    a hidden value: this is where the criteria without any data
    are explicitly visible, not just the optimistic summary of the body."""
    if not results:
        return ""
    dims_by_name = {d["name"]: d for d in results.get("dimensions", [])}
    rows = ""
    last_dimension = None
    for c in results.get("criteria", []):
        dimension = c.get("dimension")
        emoji = dimension.split(" ", 1)[0] if dimension else ""
        if dimension != last_dimension:
            d = dims_by_name.get(dimension, {})
            answered, dim_total = d.get("answered", 0), d.get("total", 0)
            pct = (answered / dim_total * 100) if dim_total else 0
            bar = (
                f'<div style="background:#e0e0e0;border-radius:3px;height:10px;width:120px;'
                f'display:inline-block;vertical-align:middle;margin-left:10px;overflow:hidden">'
                f'<div style="background:{OCTO_BLUE};height:100%;width:{pct:.0f}%"></div>'
                f'</div>'
            )
            rows += (
                f'<tr><td colspan="5" style="padding:10px 8px 6px;background:{OCTO_PALE};font-weight:bold">'
                f'{dimension}{bar} '
                f'<span style="font-weight:normal;font-size:13px;color:#555">{answered}/{dim_total}</span>'
                f'</td></tr>'
            )
            last_dimension = dimension
        if c["answer"]:
            value = c["answer"]
            source = c.get("source") or "—"
            conf = _provenance_of(c)
        elif c.get("context"):
            value = f'I don\'t know <span style="color:#888">— hint: {c["context"]}</span>'
            source = c.get("source") or "—"
            conf = _provenance_of(c)
        else:
            value = "I don't know"
            source = "no audit data (organizational/product criterion)"
            conf = None
        src_html = _confidence_badge(conf) if conf else '<span style="color:#aaa">—</span>'
        rows += (
            f'<tr>'
            f'<td style="padding:5px 8px;white-space:nowrap">{emoji} {c["id"]}</td>'
            f'<td style="padding:5px 8px">{c["criterion"]}</td>'
            f'<td style="padding:5px 8px">{value}</td>'
            f'<td style="padding:5px 8px">{src_html}</td>'
            f'<td style="padding:5px 8px;font-size:13px;color:#666">{source}</td>'
            f'</tr>'
        )
    return f"""<section id="eof-detail">
  <h2>EOF criteria detail</h2>
  <p style="font-size:15px;color:#666">
    {_confidence_badge("collected")} measured by our scripts (CrUX, ipinfo, PageSpeed Insights, HTTP headers)
    &nbsp;·&nbsp;
    {_confidence_badge("estimated")} deduced from an indirect signal or a threshold we set (technology detection, re-fetched HTML/CSS)
    &nbsp;·&nbsp;
    {_confidence_badge("declared")} publicly declared by the audited organization
    &nbsp;·&nbsp;
    {_confidence_badge("stated")} ticked in the questionnaire, without verifiable proof
  </p>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:5px 8px;text-align:left">ID</th>
      <th style="padding:5px 8px;text-align:left">Criterion</th>
      <th style="padding:5px 8px;text-align:left">Answer</th>
      <th style="padding:5px 8px;text-align:left">Provenance</th>
      <th style="padding:5px 8px;text-align:left">Source / data used</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="font-size:14px;color:#888;margin-top:8px">
    Mapping table: <code>eof_criteria_mapping.py</code> (18 criteria with a rule:
    7 automatable + 11 "partial" hints, 36 absent by choice = always "I don't know").
    Sources used, in addition to <code>env-data.json</code>/<code>har-analysis.json</code>/
    <code>coverage-analysis.json</code>/<code>cwv.json</code>: <code>html-css-criteria.json</code>
    (live re-fetch of already audited pages — <code>parse_html_criteria.py</code>),
    <code>security-headers-analysis.json</code> (local security score from the HAR —
    <code>analyze_security_headers.py</code>), <code>wellknown-scan.json</code> (direct fetch
    security.txt/robots.txt/sitemap.xml — <code>scan_wellknown.py</code>), and
    <code>accessibility_score_pct</code>/<code>best_practices_score_pct</code> in
    <code>cwv.json</code> (PageSpeed Insights categories added to the existing call).
    Regenerate after a new data collection:
    <code>python3 run_eof.py &lt;source_dir&gt;</code> then regenerate the report.
  </p>
</section>"""


def _methodology_table(rows):
    """Renders a Parameter / Value / Source-confidence table for the methodology appendix.

    rows: list of (label, value, confidence|label). If the confidence matches
    a known level (cf. _CONFIDENCE_LEVELS), show the badge; otherwise raw text.
    """
    body = ""
    for label, value, conf in rows:
        if conf in _CONFIDENCE_LEVELS:
            src = _confidence_badge(conf)
        else:
            src = f'<span style="font-size:14px;color:#666">{conf}</span>'
        body += (f'<tr>'
                 f'<td style="padding:5px 8px">{label}</td>'
                 f'<td style="padding:5px 8px"><b>{value}</b></td>'
                 f'<td style="padding:5px 8px">{src}</td>'
                 f'</tr>')
    return (f'<table style="width:100%;border-collapse:collapse;margin-top:6px">'
            f'<thead><tr style="background:{OCTO_PALE}">'
            f'<th style="padding:6px 8px;text-align:left">Parameter</th>'
            f'<th style="padding:6px 8px;text-align:left">Retained value</th>'
            f'<th style="padding:6px 8px;text-align:left">Source</th>'
            f'</tr></thead><tbody>{body}</tbody></table>')


def _methodology_efootprint(python_summary):
    """Sub-section A: assumptions AND methods of the CO2e calculation."""
    if not python_summary:
        return ""
    hyp = python_summary.get("hypotheses", {})
    visits = python_summary.get("visits_per_year", 0)
    traffic = python_summary.get("traffic", {})

    def pct(v):
        return f'{v:.0%}' if isinstance(v, (int, float)) else "?"

    # Traffic: monthly value as a note if available (e.g. 36,700/month × 12)
    _monthly = traffic.get("monthly_visits")
    _visits_val = (f'{visits:,} visites (≈ {_monthly:,}/mois × 12)'
                   if _monthly else f'{visits:,} visites')

    # --- Data/assumptions table ---
    # LOT 1: transferred weight (real network) as the value; decompressed as a reference if available.
    _pw_transferred_m = hyp.get("page_weight_transferred_kb")
    if _pw_transferred_m:
        _ratio_m = hyp.get("compression_ratio")
        _note_m = f' <span style="color:#888">(decompressed: {hyp.get("page_weight_uncompressed_kb")} kB'
        _note_m += f', ratio {_ratio_m})</span>' if _ratio_m else ')</span>'
        _pw_row = ("Transferred page weight (real network)",
                   f'{hyp.get("page_weight_kb", "?")} kB{_note_m}',
                   hyp.get("confidence_page_weight", "default"))
    else:
        _pw_row = ("Page weight (representative)",
                   f'{hyp.get("page_weight_kb", "?")} kB',
                   hyp.get("confidence_page_weight", "default"))
    rows = [
        _pw_row,
        ("Load duration", f'{hyp.get("request_duration_ms", "?")} ms', hyp.get("confidence_request_duration", "default")),
        ("Hosting country", hyp.get("country", "?"), hyp.get("confidence_country", "default")),
        ("Electricity carbon intensity", f'{hyp.get("carbon_intensity_g_kwh", "?")} g/kWh', hyp.get("confidence_carbon_intensity", "default")),
        ("Hosting provider", hyp.get("provider", "?"), hyp.get("confidence_provider", "default")),
        ("Instance type", *_instance_type_row(hyp)),
        ("Annual traffic", _visits_val, _traffic_source_label(traffic)),
    ]
    # Audience country mix (used to weight iOS/macOS)
    audience_mix = hyp.get("audience_mix")
    if audience_mix:
        mix_str = ", ".join(f'{cc} {w:.0%}' for cc, w in audience_mix.items())
        rows.append(("Audience country mix", mix_str,
                     _audience_source_label(hyp.get("audience_source", "default"),
                                            hyp.get("audience_source_url"))))
    # Device mix: raw CrUX (if available) + retained corrected
    mob_raw = hyp.get("mobile_fraction_raw")
    if mob_raw is not None:
        rows.append(("Raw CrUX mix (mobile / desktop)",
                     f'{pct(mob_raw)} / {pct(hyp.get("desktop_fraction_raw"))} '
                     f'(including phone {pct(hyp.get("phone_fraction_raw"))}, tablet {pct(hyp.get("tablet_fraction_raw"))})',
                     hyp.get("device_mix_source", "crux")))
        rows.append(("Retained iOS share (mobile correction)",
                     pct(hyp.get("ios_share_used")),
                     hyp.get("ios_share_source", "?")))
        rows.append(("Retained macOS share (desktop correction)",
                     pct(hyp.get("macos_share_used")),
                     hyp.get("macos_share_source", "?")))
    rows.append(("Retained device mix (mobile / desktop)",
                 f'{pct(hyp.get("phone_fraction"))} / {pct(hyp.get("desktop_fraction"))}',
                 hyp.get("confidence_device_mix", "default")))
    rows.append(("Traffic split (mobile / desktop)",
                 f'{hyp.get("visits_mobile", "?"):,} / {hyp.get("visits_desktop", "?"):,} visits'
                 if isinstance(hyp.get("visits_mobile"), int) else "?",
                 "derived from the mix"))
    rows.append(("Network (derived from device mix)",
                 "mobile → mobile network ; desktop → wifi",
                 "derived from device mix"))
    rows.append((
        "Server storage (nb. of declared servers, not a data volume: below "
        "1 TB, e-footprint has no resolution)",
        f'{hyp.get("storage_gb", 50)} GB', "default_script"))
    rows.append(("Modeled devices (e-footprint)", "smartphone + laptop (lib archetypes)", "default_efootprint"))

    table = _methodology_table(rows)

    # --- iOS scenario range ---
    scenarios_html = ""
    sc = hyp.get("device_scenarios")
    if sc:
        sc_rows = ""
        for key, human in (("conservative", "Conservative"), ("central", "Central (retained)"), ("apple_heavy", "Apple audience")):
            s = sc.get(key, {})
            sc_rows += (f'<tr><td style="padding:5px 8px">{human}</td>'
                        f'<td style="padding:5px 8px">iOS share {pct(s.get("ios_share"))}</td>'
                        f'<td style="padding:5px 8px"><b>{pct(s.get("mobile"))}</b> mobile / {pct(s.get("desktop"))} desktop</td></tr>')
        scenarios_html = (
            f'<h4 style="margin:14px 0 4px">Mix range according to the iOS share</h4>'
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr style="background:{OCTO_PALE}">'
            f'<th style="padding:6px 8px;text-align:left">Scenario</th>'
            f'<th style="padding:6px 8px;text-align:left">Assumption</th>'
            f'<th style="padding:6px 8px;text-align:left">Resulting mix</th>'
            f'</tr></thead><tbody>{sc_rows}</tbody></table>')

    # --- Audience country mix detail (iOS/macOS weighting) ---
    audience_html = ""
    per_country = hyp.get("audience_per_country")
    if per_country:
        ac_rows = ""
        for d in per_country:
            flag_note = "" if d.get("in_table") else ' <span style="color:#999;font-size:13px">(default world value)</span>'
            ac_rows += (f'<tr><td style="padding:5px 8px">{_country_label(d.get("country"))}{flag_note}</td>'
                        f'<td style="padding:5px 8px">{pct(d.get("weight"))}</td>'
                        f'<td style="padding:5px 8px">{pct(d.get("ios_share"))}</td>'
                        f'<td style="padding:5px 8px">{pct(d.get("macos_share"))}</td></tr>')
        ios_w = hyp.get("audience_ios_weighted")
        mac_w = hyp.get("audience_macos_weighted")
        ac_foot = (f'<tr style="background:{OCTO_PALE};font-weight:bold">'
                   f'<td style="padding:5px 8px">Weighted (retained)</td>'
                   f'<td style="padding:5px 8px">100 %</td>'
                   f'<td style="padding:5px 8px">{pct(ios_w)}</td>'
                   f'<td style="padding:5px 8px">{pct(mac_w)}</td></tr>')
        src = hyp.get("audience_source", "default")
        src_url = hyp.get("audience_source_url")
        _src_link = _source_link(src_url)
        caveat = ""
        if isinstance(src, str) and "similarweb" in src.lower():
            caveat = ('<p style="font-size:14px;color:#888;margin:4px 0 0">'
                      'Country mix estimated via SimilarWeb (public page, unofficial source, '
                      'ToS-limited usage, potentially unavailable): order of magnitude, '
                      'to confirm with the site analytics (GA/Matomo) via <code>--audience</code>.</p>')
        elif src == "default":
            caveat = ('<p style="font-size:14px;color:#888;margin:4px 0 0">'
                      'No country mix provided: France (100%) by default. Provide '
                      '<code>--audience "FR:0.7,US:0.3"</code> or let the agent estimate via SimilarWeb.</p>')
        audience_html = (
            f'<h4 style="margin:14px 0 4px">Audience country mix (iOS / macOS weighting)</h4>'
            f'<p style="font-size:15px;color:#666;margin:0 0 4px">Source: {src}{_src_link}. '
            f'This mix is ONLY used to weight the iOS/macOS shares of the CrUX correction '
            f'(CrUX has no country dimension); it does not change the Core Web Vitals.</p>'
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr style="background:{OCTO_PALE}">'
            f'<th style="padding:6px 8px;text-align:left">Country</th>'
            f'<th style="padding:6px 8px;text-align:left">Audience weight</th>'
            f'<th style="padding:6px 8px;text-align:left">iOS share (mobile)</th>'
            f'<th style="padding:6px 8px;text-align:left">macOS share (desktop)</th>'
            f'</tr></thead><tbody>{ac_rows}{ac_foot}</tbody></table>{caveat}')

    # --- LOT 2/3: factual server/network signals appended (documentary) ---
    har_facts_html = ""
    hf = hyp.get("har_facts")
    if hf:
        conf_hf = hyp.get("confidence_har_facts", "high")
        methods_str = ", ".join(f'{v}×{k}' for k, v in sorted(hf.get("methods", {}).items(), key=lambda kv: -kv[1]))
        statuses_str = ", ".join(f'{v}×{k}' for k, v in sorted(hf.get("statuses", {}).items(), key=lambda kv: -kv[1]))
        cache_bytes_kb = round(hf.get("cache_304_uncompressed_bytes", 0) / 1024)
        hf_rows = [
            ("Requests served from browser cache (304)",
             f'{hf.get("cache_304_count", 0)} / {hf.get("request_count", 0)} '
             f'({pct(hf.get("cache_304_share"))}, ≈ {cache_bytes_kb} kB not re-downloaded)',
             conf_hf),
            ("Server wait time (TTFB, wait)",
             f'median {hf.get("wait_ms_median", "?")} ms, p95 {hf.get("wait_ms_p95", "?")} ms',
             conf_hf),
            ("HTTP methods", methods_str or "?", conf_hf),
            ("HTTP statuses", statuses_str or "?", conf_hf),
            ("Dominant HTTP version", hf.get("dominant_http_version", "?"), conf_hf),
        ]
        har_facts_html = (
            f'<h4 style="margin:14px 0 4px">Factual network/server signals (appendix)</h4>'
            f'<p style="font-size:14px;color:#888;margin:0 0 4px">'
            f'{hf.get("note", "Documentary, does not enter the CO2e calculation.")}</p>'
            f'{_methodology_table(hf_rows)}'
        )

    # --- Reading time per step (Nielsen 2008 recalibrated, Lot 10) ---
    reading_html = ""
    rt = hyp.get("reading_time")
    model_steps = (python_summary.get("model") or {}).get("steps") or []
    if rt and model_steps:
        rt_rows = ""
        for s in model_steps:
            words = s.get("words")
            time_s = s.get("user_time_min") or 0
            words_txt = f'{words:.0f}' if words is not None else "?"
            raw_s_txt = f'{_nielsen_raw_seconds(words):.0f} s' if words is not None else "?"
            label = s.get("url") or s.get("label", "?")
            rt_rows += (
                f'<tr><td style="padding:5px 8px">{label}</td>'
                f'<td style="padding:5px 8px;text-align:right">{words_txt}</td>'
                f'<td style="padding:5px 8px;text-align:right">{raw_s_txt}</td>'
                f'<td style="padding:5px 8px;text-align:right"><b>{time_s:.0f} s</b></td>'
                f'<td style="padding:5px 8px">{_confidence_badge(s.get("user_time_confidence"))}</td></tr>'
            )
        factor = rt.get("recalibration_factor")
        total_raw = rt.get("total_raw_s")
        total_recal = rt.get("total_recalibrated_s")
        avg_swb = rt.get("avg_time_on_page_s")
        if rt.get("recalibrated"):
            _swb_link = _source_link(traffic.get("source_url"))
            recal_note = (
                f'The raw value ({total_raw:.0f} s cumulative, Nielsen formula alone) is <b>recalibrated</b> by a '
                f'single factor <b>{factor:.3f}</b> = average SimilarWeb time{_swb_link} per page viewed '
                f'across all pages ({avg_swb:.1f} s/page) ÷ average of the raw Nielsens of the journey pages '
                f'Retained result: <b>{total_recal:.0f} s</b> cumulative. This factor corrects the '
                'bias of the Nielsen formula (2005 study, pre-smartphone usage, therefore structurally '
                'overestimated for mobile usage) by anchoring it on a real engagement measurement '
                'of the whole site, but it remains specific to THIS site (not generic) and applies to an '
                'aggregate (site-wide average time/page), not to the precise pages of the captured journey. '
                'Like the other SimilarWeb data in this report: third-party estimate (public page, '
                'unofficial source, ToS-limited usage, potentially unavailable), not a measurement.'
            )
        else:
            recal_note = (
                f'No SimilarWeb measurement available for this site: the retained time is the Nielsen '
                f'<b>raw, unrecalibrated</b> ({total_raw:.0f} s cumulative), probably overestimated '
                '(underlying study from 2005, before mass smartphone usage).'
            )
        reading_html = (
            '<h4 style="margin:14px 0 4px">Reading time per step (Nielsen 2008 recalibrated)</h4>'
            f'<p style="font-size:15px;color:#666;margin:0 0 4px">'
            f'Formula: <code>{rt.get("formula")}</code>, applied to the REAL word count of the body '
            f'HTML of each page captured in the HAR (source: '
            f'<a href="{rt.get("source_url")}" target="_blank" rel="noopener">{rt.get("source_name")}</a>, '
            f'published validity domain {rt.get("domain_min_words"):.0f}-{rt.get("domain_max_words"):.0f} words). '
            f'{recal_note}</p>'
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr style="background:{OCTO_PALE}">'
            f'<th style="padding:6px 8px;text-align:left">Step</th>'
            f'<th style="padding:6px 8px;text-align:right">Words</th>'
            f'<th style="padding:6px 8px;text-align:right">Raw Nielsen</th>'
            f'<th style="padding:6px 8px;text-align:right">Retained time</th>'
            f'<th style="padding:6px 8px;text-align:left">Confidence</th>'
            f'</tr></thead><tbody>{rt_rows}</tbody></table>'
        )

    # --- Methods / formulas ---
    methods = (
        '<h4 style="margin:14px 0 4px">Methods applied</h4>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        '<li><b>Symmetric CrUX correction (iOS + macOS).</b> CrUX only measures Chrome: '
        'on mobile, iPhone/iPad (Safari, and even Chrome on iOS) are absent; on '
        'desktop, Macs under Safari are too. We inflate <b>both</b> sides with '
        '<code>corrected_mobile = raw_mobile / (1 − ios_share)</code> and '
        '<code>corrected_desktop = raw_desktop / (1 − macos_share)</code>, then we renormalize '
        'the whole to 100%. Correcting the desktop too removes the "pro-mobile" bias of '
        'the old unilateral correction.</li>'
        '<li><b>Weighting by audience country mix.</b> iOS and macOS shares depend '
        'on the country. They are therefore weighted by the audience country mix (see table above). '
        'Mix resolution order: <code>--audience</code> entered (client analytics) &gt; '
        'SimilarWeb estimate written by the agent &gt; France (100%) by default. CrUX having '
        'no geographic dimension, this mix is ONLY used for this weighting, never for the CWVs.</li>'
        '<li><b>Tablet attachment.</b> The tablet is counted with mobile '
        '(touch/portable logic). The report body only shows mobile/desktop; '
        'the detail is in the table above.</li>'
        '<li><b>CO2e weighting.</b> Traffic is split into <b>two usage profiles</b> '
        '(mobile → smartphone + mobile network ; desktop → laptop + wifi), with volumes '
        'proportional to the mix. This corrects a previous overcount where each visit was '
        'charged 100% to both smartphone AND laptop.</li>'
        '<li><b>Nature of the figures.</b> Hypothetical orders of magnitude (HAR/CrUX/IP-geolocation data '
        '+ default values), not a real measurement.</li>'
        '</ul>'
    )

    return (f'<h3 id="methodo-efootprint" style="margin-top:20px">__LETTRE__. Impact environnemental ({_glossary_link("CO2e")})</h3>'
            f'<p style="font-size:16px;color:#555;margin-bottom:8px">Ce n\'est pas une {_glossary_link("ACV")} '
            f'complete: e-footprint only models 2 phases (manufacturing + usage), not transport nor end of life.</p>'
            f'{table}{audience_html}{scenarios_html}{har_facts_html}{reading_html}{methods}')


def _methodology_cwv(cwv):
    """Sous-section B : sources et limites des Core Web Vitals."""
    if not cwv:
        return ""
    sources = {row.get("source")
               for by_strat in cwv.values() if isinstance(by_strat, dict)
               for row in by_strat.values() if row}
    src_items = "".join(
        f'<li><b>{_CWV_SOURCE_LABELS[s][0]}</b> : {_CWV_SOURCE_LABELS[s][2]}</li>'
        for s in ("crux", "pagespeed_lab", "lighthouse") if s in sources
    ) or '<li>Source not provided</li>'
    return (
        '<h3 id="methodo-cwv" style="margin-top:20px">__LETTRE__. Core Web Vitals</h3>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        f'<li><b>Sources present:</b><ul style="margin:2px 0 6px 16px">{src_items}</ul></li>'
        f'<li><b>{_glossary_link("CrUX")} = Chrome field data.</b> "Field" data comes from the field '
        f'<code>loadingExperience</code> of the PageSpeed Insights response ({_glossary_link("P75")} '
        'of real Chrome users): this is NOT a dedicated call to the CrUX API.</li>'
        '<li><b>iOS/Safari limitation.</b> Like the device mix, the CrUX field data only covers '
        'Chrome; iOS/Safari users are not represented.</li>'
        '<li><b>Mobile AND desktop, "worst of both" per metric.</b> Both PageSpeed strategies '
        'are collected. In the dashboard and the recommendations, each '
        'metric (LCP, INP, CLS) retains the <b>most unfavorable</b> value between mobile '
        'and desktop, independently metric by metric (a 📱/🖥 pictogram signals '
        'the retained device). A desktop problem therefore surfaces in the recos. The detail '
        'mobile + desktop side by side stays available in the "Core Web Vitals analysis" '
        'section. Thresholds: LCP &lt; 1.8 s good / 1.8-2.5 s needs improvement / &gt; 2.5 s poor; '
        'INP 200/500 ms ; CLS 0,1/0,25.</li>'
        '<li><b>Lab (simulation).</b> Les sources "lab" (PageSpeed lab ou Lighthouse local) '
        'are simulations with throttled network/CPU, generally more pessimistic than field.</li>'
        '<li><b>Indicative signals (causal diagnostic).</b> When an LCP/INP/CLS problem is '
        'detected, the report adds a signal cross-referenced with already collected data (trackers, '
        'external web fonts, heaviest resource of the journey, unused JS rate). '
        'These are correlations, not confirmed causes: the HAR captures neither the JS actually executed '
        'at runtime, nor the real page rendering (no DOM/CSS measurement). To check '
        'manuellement avant conclusion.</li>'
        '</ul>'
    )


def _methodology_ecoindex():
    """Sous-section C : formule EcoIndex."""
    return (
        f'<h3 id="methodo-ecoindex" style="margin-top:20px">__LETTRE__. {_glossary_link("EcoIndex")} / {_glossary_link("GreenIT")}</h3>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        '<li><b>Formule (cnumr/ecoindex_reference) :</b> '
        '<code>score = 100 − 5 × (3·q_DOM + 2·q_req + q_poids) / 6</code>, '
        'where q_x is the rank (0-20) of the value in the reference quantiles '
        '(number of DOM elements, number of requests, weight in KB).</li>'
        '<li><b>Grades :</b> A ≥ 80, B ≥ 70, C ≥ 55, D ≥ 40, E ≥ 25, F ≥ 10, G sinon.</li>'
        '<li><b>Inputs:</b> DOM, requests and weight are extracted from the capture HAR.</li>'
        '</ul>'
    )


def _methodology_medias():
    """Sub-section E: limits of the media rules (Lot 4)."""
    return (
        '<h3 id="methodo-medias" style="margin-top:20px">__LETTRE__. Media and documents to watch</h3>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        '<li><b>Seuils "image bitmap lourde" (200 Ko) et "SVG suspect" (30 Ko).</b> '
        'Unsourced internal heuristics (no official GreenIT-Analysis/EcoIndex '
        'framework sets a weight threshold in KB for these rules) — <b>low confidence</b>, '
        'to adjust if a documented framework is identified.</li>'
        '<li><b>Estimated WebP format gain (-31.5% to -50.3%).</b> Flat cnumr figures '
        'applied to the cumulative weight of the images concerned, without a real measurement per image nor '
        'distinction JPEG/PNG source.</li>'
        '<li><b>"Fake" SVG (probable base64-encoded bitmap).</b> Abnormal-weight signal, not '
        'a confirmation: a legitimately complex SVG (map, detailed illustration) can '
        'also exceed the threshold without containing a bitmap.</li>'
        '<li><b>Real oversizing not measurable.</b> The pipeline performs no capture '
        'of the render DOM/CSS (no Puppeteer/Playwright/CDP): impossible to compare the file weight '
        'of the file to its real display size. The media rules stay at the "weight '
        'raw vs threshold" level, not "measured oversizing".</li>'
        '<li><b>Videos and PDFs.</b> Factual reporting (weight, count), without a compliance badge: '
        'no universal threshold would be defensible, the expected use varying too much with the site.</li>'
        '</ul>'
    )


def _methodology_traffic(python_summary=None):
    """Sub-section D: traffic and network. Describes the real provenance of the traffic volume
    (analytics entry, SimilarWeb estimate, or default baseline)."""
    traffic = (python_summary or {}).get("traffic", {})
    source = traffic.get("source")
    url = traffic.get("source_url")
    snapshot = traffic.get("snapshot")
    monthly = traffic.get("monthly_visits")
    visits = (python_summary or {}).get("visits_per_year")

    if source and source not in ("default", "parameter"):
        src_txt = source
        if snapshot:
            src_txt += f', {snapshot}'
        src_txt += _source_link(url)
        derivation = ""
        if monthly and visits:
            derivation = (f' Derivation: {monthly:,}/month × 12 ≈ {visits:,}/year.')
        volume_li = (
            f'<li><b>Traffic volume.</b> Third-party estimate: <b>{src_txt}</b>.{derivation} '
            'Neither PageSpeed nor CrUX provide an audience volume (their APIs return '
            'only distributions, never counters); third-party estimators remain '
            '<b>estimates with a wide margin</b>, not to be taken as a measurement. '
            'An exact figure can only come from the site\'s own analytics (GA4/Matomo/logs).</li>'
            '<li><b>Sensitivity to volume.</b> The <b>total</b> CO2e grows with traffic, above '
            'a <b>fixed base</b> (server manufacturing + storage, amortized whatever the traffic): '
            'the relation is <b>affine, not strictly proportional</b>. The CO2e <b>per visit</b> '
            '<b>decreases</b> therefore when traffic grows (the base spreads over more visits). '
            'An error on the volume shifts mostly the order of magnitude of the total, less the per-visit.</li>'
        )
    else:
        volume_li = (
            '<li><b>Traffic volume.</b> The number of visits/year is a <b>default assumption</b> '
            '(100 000/year): neither PageSpeed nor CrUX provides an audience volume (their APIs '
            'only return distributions, never counters). To get a reliable figure: enter the '
            'site analytics (<code>--visits</code>) or a SimilarWeb estimate.</li>'
            '<li><b>Sensitivity to volume.</b> The <b>total</b> CO2e grows with traffic above '
            'a fixed base (server manufacturing + storage); the CO2e <b>per visit</b> decreases '
            'when traffic grows.</li>'
        )

    return (
        '<h3 id="methodo-trafic" style="margin-top:20px">__LETTRE__. Traffic &amp; network</h3>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        f'{volume_li}'
        '<li><b>Network volume.</b> The transferred weight and the request count come '
        'from the HAR (real measurement of the capture), not to be confused with an audience volume.</li>'
        '</ul>'
    )


# Public Boavizta interface to reload a .e-f.json and explore the detail
# (breakdown by component) - capped at 2 models per comparison (MAX_SLOTS=2,
# verified in the interface code), hence the export as individual files.
_MODEL_BUILDER_URL = "https://e-footprint.boavizta.org/model_builder/"

# Readable labels of the quantified recommendations (efootprint-recommendations-gains.json).
_RECO_LABELS = {
    "js_dead": "Code JS mort",
    "css_dead": "Code CSS mort",
    "duplicates": "Ressources en double",
    "brotli": "Compression Brotli",
    "inp": "INP (interactivity)",
    "cls": "CLS (visual stability)",
}

# Tier labels used both for a recommendation's "tier"
# (reductions_detail/excluded_recommendations : prio1/prio2/prio3, parfois
# prio1_2/prio1_2_3 on the excluded_recommendations side) and, with the variant
# _TIER_STAGE_LABELS below, for the cumulative keys of "tiers".
_TIER_LABELS = {
    "prio1": "Prio 1",
    "prio2": "Prio 2",
    "prio3": "Prio 3",
    "prio1_2": "Prio 1 + 2",
    "prio1_2_3": "Prio 1 + 2 + 3",
}
_TIER_STAGE_LABELS = {
    "prio1": "Prio 1 seule",
    "prio1_2": "Prio 1 + 2",
    "prio1_2_3": "Prio 1 + 2 + 3",
}

# Same cumulative tier sets as efootprint_model/recommendations.py::_TIER_SETS
# (not imported from here: this module never depends on efootprint_model, it only
# reads the JSON already written by run_efootprint.py).
_ECOINDEX_TIER_SETS = {
    "prio1": frozenset({"prio1"}),
    "prio1_2": frozenset({"prio1", "prio2"}),
    "prio1_2_3": frozenset({"prio1", "prio2", "prio3"}),
}


def _ecoindex_reductions_by_page(gains):
    """Aggregates `reductions_detail` by normalized page x cumulative tier.

    Returns `{normalized_url: {tier: {"decomp": .., "transfer": .., "requests": ..}}}`,
    or `None` if `gains` is empty OR no entry carries `page_url` (schema
    older than the EcoIndex/LCP work) - distinct from `{}` ("available but
    no quantifiable reduction"), so the caller displays "not available,
    regenerate..." rather than a silently empty table."""
    if not gains:
        return None
    reductions = gains.get("reductions_detail") or []
    if not any(r.get("page_url") for r in reductions):
        return None

    result = {}
    for r in reductions:
        page_url = r.get("page_url")
        tier = r.get("tier")
        if not page_url or tier is None:
            continue
        url = _normalize_page_url(page_url)
        for cumul_tier, member_tiers in _ECOINDEX_TIER_SETS.items():
            if tier not in member_tiers:
                continue
            bucket = result.setdefault(url, {}).setdefault(
                cumul_tier, {"decomp": 0.0, "transfer": 0.0, "requests": 0}
            )
            bucket["decomp"] += r.get("bytes_removed_decompressed") or 0.0
            bucket["transfer"] += r.get("bytes_removed") or 0.0
            bucket["requests"] += r.get("requests_removed") or 0
    return result


def _lcp_baseline_s(m, cwv):
    """Reference LCP for a page, same hierarchy as `_section_dashboard`:
    real CWV (worst of both strategies) if available, else onLoad HAR fallback
    (proxy). Retourne (valeur_s, est_un_proxy)."""
    cwv_data, _ = _cwv_worst_per_metric(_cwv_for_page(m, cwv))
    if cwv_data and isinstance(cwv_data.get("lcp"), (int, float)):
        return cwv_data["lcp"], False
    return m["on_load_ms"] / 1000, True


def _ecoindex_lcp_for_tier(m, cwv, reductions_for_tier):
    """Recomputes EcoIndex and rough LCP for a page, at a given tier.

    `new_size_ko` subtracts the DECOMPRESSED weight (EcoIndex is computed on this
    weight, cf. `har_metrics.py::extract_page_metrics` which already sums
    `content.size`); `lcp_delta_s` subtracts the TRANSFERRED weight (the simulated
    bandwidth applies to the bytes actually sent on the wire). The DOM
    is unchanged: no recommendation of this work removes a DOM node."""
    decomp = reductions_for_tier.get("decomp", 0.0)
    transfer = reductions_for_tier.get("transfer", 0.0)
    req_removed = reductions_for_tier.get("requests", 0)

    # `duplicate_reductions()` detects duplicates over the whole HAR, not
    # page par page (cf. efootprint_model/recommendations.py) : les octets/
    # requests attributed to THIS page can exceed its own weight/count
    # of requests if duplicates from other pages are attached to it. `size_ko`/
    # `req` are then CLAMPED to 0, not negative - to be reported explicitly
    # rather than letting one believe the page becomes empty.
    size_clamped = (decomp / 1024) > m["size_ko"]
    req_clamped = req_removed > m["req"]
    new_size_ko = max(0.0, m["size_ko"] - decomp / 1024)
    new_req = max(0, m["req"] - req_removed)
    dom = m["dom"]
    score = ecoindex_score(dom, new_req, new_size_ko)
    grade, color = ecoindex_grade(score)

    lcp_baseline, lcp_is_proxy = _lcp_baseline_s(m, cwv)
    new_lcp = max(0.0, lcp_baseline - lcp_delta_s(transfer))

    return {
        "size_ko": new_size_ko, "req": new_req, "dom": dom,
        "score": score, "grade": grade, "grade_color": color,
        "lcp": new_lcp, "lcp_baseline": lcp_baseline, "lcp_is_proxy": lcp_is_proxy,
        "size_clamped": size_clamped, "req_clamped": req_clamped,
    }


def _ecoindex_tier_table(page_metrics, gains, cwv, tier, tier_label):
    """Detailed appendix table for a tier: one row per page, columns
    Page / EcoIndex / Requests / Weight / DOM / LCP - NO INP/CLS columns
    (not estimated, cf. `_EXCLUDED_RECOMMENDATIONS` on the run_efootprint.py side).
    Each cell shows the new value with the delta in parentheses."""
    reductions_by_page = _ecoindex_reductions_by_page(gains)
    if not reductions_by_page:
        return ""

    deduped = [m for m in _dedup_page_metrics(page_metrics)
               if m.get("measurement", {}).get("status") == "ok"]

    rows = ""
    for m in deduped:
        url = _normalize_page_url(m["title"])
        reductions_for_tier = (reductions_by_page.get(url) or {}).get(tier)
        if not reductions_for_tier:
            continue
        t = _ecoindex_lcp_for_tier(m, cwv, reductions_for_tier)
        num = m.get("page_num", "")
        badge = _badge(t["grade"], t["grade_color"])
        eco_delta = t["score"] - m["ecoindex"]
        req_delta = t["req"] - m["req"]
        size_delta = t["size_ko"] - m["size_ko"]
        lcp_delta = t["lcp"] - t["lcp_baseline"]
        lcp_suffix = " *" if t["lcp_is_proxy"] else ""
        req_suffix = " &dagger;" if t["req_clamped"] else ""
        size_suffix = " &dagger;" if t["size_clamped"] else ""
        rows += f"""<tr>
      <td>P{num} {url}</td>
      <td style="text-align:center">{badge} {t['score']}/100 ({eco_delta:+.0f})</td>
      <td style="text-align:right">{t['req']} ({req_delta:+.0f}){req_suffix}</td>
      <td style="text-align:right">{t['size_ko']:.0f} Ko ({size_delta:+.0f}){size_suffix}</td>
      <td style="text-align:right">{t['dom']}</td>
      <td style="text-align:right">{t['lcp']:.2f} s ({lcp_delta:+.2f}){lcp_suffix}</td>
    </tr>"""

    if not rows:
        return ""
    return f"""<h5 style="margin:10px 0 4px">Tier {tier_label}</h5>
  <table>
    <thead><tr>
      <th>Page</th><th>{_glossary_link("EcoIndex")}</th><th>Requests</th>
      <th>Weight</th><th>{_glossary_link("DOM")}</th><th>{_glossary_link("LCP")}</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>"""


def _methodology_recommendations(gains):
    """Sub-section F: detail of the CO2e recomputation per recommendation tier
    (efootprint-recommendations-gains.json, written by
    run_efootprint.py::run_recommendation_scenarios()). The per-page detail of the
    EcoIndex/LCP recalculation per tier lives in the separate standalone appendix
    "Gain EcoIndex & LCP per page" (`_section_gain_ecoindex_lcp`), not here.

    A REAL recomputation of the e-footprint model per cumulative tier (not a
    flat approximation), the detail by recommendation type (grouped
    by (recommendation, tier), not by Job/page), and the explicit list of
    recommendations excluded from the quantified calculation and why."""
    if not gains:
        return ""

    reductions = gains.get("reductions_detail") or []
    excluded = gains.get("excluded_recommendations") or []
    hypotheses = gains.get("hypotheses_generales") or []

    intro = (
        '<p style="font-size:16px;color:#555;margin-bottom:8px">'
        'Each tier (Prio 1, Prio 1 + 2, Prio 1 + 2 + 3) is a REAL recomputation of the model '
        'e-footprint (new SiteSpec with the transferred weight reduced, Job by Job), not a '
        'flat approximation applied after the fact: the CO2e calculation is not strictly '
        'linear in the transferred weight.</p>'
    )

    if reductions:
        groups = {}
        order = []
        for r in reductions:
            key = (r.get("recommendation"), r.get("tier"))
            if key not in groups:
                groups[key] = {"bytes": 0.0, "count": 0,
                               "comment": (r.get("traced") or {}).get("comment")}
                order.append(key)
            groups[key]["bytes"] += r.get("bytes_removed") or 0
            groups[key]["count"] += 1

        rows = []
        note_items = ""
        for key in order:
            reco, tier = key
            g = groups[key]
            label = _RECO_LABELS.get(reco, reco or "?")
            tier_label = _TIER_LABELS.get(tier, tier or "?")
            ko = round(g["bytes"] / 1024, 1)
            n = g["count"]
            value = f'{ko} Ko sur {n} page{"s" if n > 1 else ""} ({tier_label})'
            rows.append((label, value, "medium"))
            if g["comment"]:
                note_items += f'<li><b>{label} ({tier_label})</b> : {g["comment"]}</li>'

        table_html = _methodology_table(rows)
        notes_html = (
            f'<h4 style="margin:14px 0 4px">Notes by recommendation type</h4>'
            f'<ul style="margin:0 0 0 16px;padding:0;font-size:15px;color:#666;line-height:1.5">'
            f'{note_items}</ul>'
        ) if note_items else ""
    else:
        table_html = (
            '<p style="font-size:15px;color:#555">No quantifiable recommendation found on '
            'this audit (missing Coverage/HAR data, or no quantifiable threshold exceeded).</p>'
        )
        notes_html = ""

    excluded_html = ""
    if excluded:
        items = "".join(
            f'<li><b>{_RECO_LABELS.get(e.get("recommendation"), e.get("recommendation") or "?")}</b> '
            f'({_TIER_LABELS.get(e.get("tier"), e.get("tier") or "?")}) : {e.get("reason", "?")}</li>'
            for e in excluded
        )
        excluded_html = (
            '<h4 style="margin:14px 0 4px">Recommendations not included in the quantified calculation, and why</h4>'
            f'<ul style="margin:0 0 0 16px;padding:0;font-size:15px;color:#555;line-height:1.5">{items}</ul>'
        )

    hyp_html = ""
    if hypotheses:
        hyp_items = "".join(f'<li>{h}</li>' for h in hypotheses)
        hyp_html = (
            '<h4 style="margin:14px 0 4px">General assumptions</h4>'
            f'<ul style="margin:0 0 0 16px;padding:0;font-size:15px;color:#555;line-height:1.5">{hyp_items}</ul>'
        )

    return (
        '<h3 id="methodo-recommandations" style="margin-top:20px">__LETTRE__. Recommendations &amp; estimated gain</h3>'
        f'{intro}{table_html}{notes_html}{excluded_html}{hyp_html}'
    )


def _section_gain_ecoindex_lcp(gains, page_metrics, cwv):
    """Standalone appendix (not a sub-part of Methodology & assumptions,
    content too substantial for that): per-page detail of the EcoIndex/LCP recalculation
    per recommendation tier (same `reductions_detail` as sub-section F
    of Methodology & assumptions, seen from the EcoIndex/LCP angle rather than CO2e).
    3 tables per page: result content, not a methodology note."""
    if not gains or page_metrics is None:
        return ""

    reductions_by_page = _ecoindex_reductions_by_page(gains)
    if reductions_by_page is None:
        return (
            '<section id="gain-ecoindex-lcp">\n'
            '<h2>Gain EcoIndex &amp; LCP per page</h2>'
            '<p style="font-size:15px;color:#888">Not available for this audit (gains file '
            'gains generated before the EcoIndex/LCP work) - regenerate '
            '<code>run_efootprint.py</code> to get it.</p>\n'
            '</section>'
        )

    tier_tables = "".join(
        _ecoindex_tier_table(page_metrics, gains, cwv, tier, _TIER_STAGE_LABELS.get(tier, tier))
        for tier in ("prio1", "prio1_2", "prio1_2_3")
    )
    if not tier_tables:
        return ""

    return (
        '<section id="gain-ecoindex-lcp">\n'
        '<h2>Gain EcoIndex &amp; LCP par page</h2>'
        '<p style="font-size:15px;color:#555">EcoIndex recomputed on the weight '
        'DECOMPRESSED (direct calculation, unlike the CO2e '
        'detailed in F of the Methodology &amp; assumptions appendix, below). '
        'Rough LCP via the formula sourced in this same appendix (F) - '
        '<b>risk of overestimation</b>. '
        'The DOM is not modified by these recommendations. INP and CLS are not estimated '
        '(see "Recommendations not included", Methodology &amp; assumptions appendix, F). '
        '<b>&dagger;</b>: the HAR duplicate calculation detects duplicates over '
        'the WHOLE captured journey, not page by page - the number of requests '
        'it attributes to a page can therefore exceed its own request count '
        'if duplicates loaded on OTHER pages are attached to it (first '
        'occurrence seen elsewhere in the journey). A &dagger; marks a value '
        'clamped to 0 in that case - the page does not really become empty, it is an '
        'artifact of this cross-page attribution (the weight, for its part, already excludes the '
        'HTTP 304 revalidations from the calculation - only a real full re-download '
        'counts as removable weight - so much less exposed to the same artifact, '
        'but not totally safe if several full re-downloads overlap '
        'chevauchent entre pages).</p>'
        f'{tier_tables}\n'
        '</section>'
    )


def _section_methodology(python_summary, cwv, recommendations_gains=None):
    """Methodology appendix structured by sub-section (CO2e, CWV, EcoIndex, traffic,
    media, recommendations & estimated gain): only methodology/assumption notes
    (formulas, sources, limits, confidence level). The EcoIndex/LCP gain detail
    per page and the EOF criteria detail are no longer part of it: result content
    substantial content is in separate annexes (`_section_gain_ecoindex_lcp`,
    `_section_eof_detail`), not methodology notes.

    The letters A, B, C... are not hard-coded in each sub-function:
    they are computed here by enumerating only the sub-sections whose HTML
    is non-empty, so that the displayed letter always matches the real
    position (a sub-section absent for a given audit no longer leaves a letter gap).
    lettre). Retourne (html, nav_entries) : nav_entries = [(lettre, ancre, titre), ...]
    so that generate() can build the "A · B · C..." line of the TOC without
    recompute the sub-sections a second time.

    Traces all the data and assumptions of the calculations: value, source, confidence,
    and the methods/formulas applied."""
    entries = [
        ("methodo-efootprint", "Environmental impact (CO2e)", _methodology_efootprint(python_summary)),
        ("methodo-cwv", "Core Web Vitals", _methodology_cwv(cwv)),
        ("methodo-ecoindex", "EcoIndex / GreenIT", _methodology_ecoindex()),
        ("methodo-trafic", "Traffic & network", _methodology_traffic(python_summary)),
        ("methodo-medias", "Media and documents to watch", _methodology_medias()),
        ("methodo-recommandations", "Recommendations & estimated gain", _methodology_recommendations(recommendations_gains)),
    ]
    present = [(anchor, title, html) for anchor, title, html in entries if html]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    body_parts = []
    nav_entries = []
    for letter, (anchor, title, html) in zip(letters, present):
        body_parts.append(html.replace("__LETTRE__", letter, 1))
        nav_entries.append((letter, anchor, title))
    body = "".join(body_parts)
    html_out = (
        '<section id="methodologie">\n'
        '<h2>Methodology &amp; assumptions</h2>\n'
        '<p style="font-size:16px;color:#555;margin-bottom:8px">'
        'This appendix lists, by domain, the data and assumptions entering '
        'each calculation (value, source, confidence level) as well as the methods applied.</p>\n'
        f'{body}\n'
        '</section>'
    )
    return html_out, nav_entries


def _glossary_link(acronym):
    """Link to the glossary entry (Appendices) for a given acronym, to be
    placed on table headers and the first mention of each
    section — not at every occurrence (cf. decision: a term is not
    re-explained in each sentence, like a Wikipedia link once per article)."""
    slug = acronym.lower()
    return f'<a href="#glossaire-{slug}" title="See the definition in the Glossary">{acronym}</a>'


# (acronym, full name + short definition, optional thresholds, optional source url)
_GLOSSARY_ENTRIES = [
    ("LCP", "Largest Contentful Paint: display time of the largest visible element of the page.",
     "< 1.8 s good · 1.8-2.5 s needs improvement · > 2.5 s poor", "https://web.dev/articles/vitals"),
    ("INP", "Interaction to Next Paint: delay between a user interaction and the resulting visual update.",
     "< 200 ms good · 200-500 ms needs improvement · > 500 ms poor", "https://web.dev/articles/vitals"),
    ("CLS", "Cumulative Layout Shift: sum of unexpected visual shifts during page loading.",
     "< 0.1 good · 0.1-0.25 needs improvement · > 0.25 poor", "https://web.dev/articles/vitals"),
    ("EcoIndex", "Eco-design score 0 to 100 (grade A to G), computed from the number of requests, "
     "the transferred weight and the DOM size of a page (GreenIT-Analysis / cnumr formula).",
     "≥ 80 = A · ≥ 55 = C · < 25 = F/G", "https://www.ecoindex.fr/comment-ca-marche/"),
    ("GreenIT", "GreenIT-Analysis: reference methodology and tool to measure the eco-design of a "
     "website, at the origin of the EcoIndex formula used in this report.",
     "", "https://www.ecoindex.fr/comment-ca-marche/"),
    ("DOM", "Document Object Model: the tree of the page as the browser builds it from "
     "the HTML (each tag becomes a node).", "", ""),
    ("HAR", "HTTP Archive: export format of the network traffic captured by the browser dev tools "
     "(Network tab), source of all the measurements in this report.", "", ""),
    ("CDN", "Content Delivery Network: network of geographically distributed servers that cache and "
     "deliver the content as close as possible to the user.", "", ""),
    ("CrUX", "Chrome UX Report: real performance data aggregated by Google from "
     "Chrome users (percentiles over the last 28 days), as opposed to 'lab' measurements.", "", ""),
    ("P75", "75th percentile: value below which 75% of the collected measurements fall "
     "(25% of visitors therefore have a worse experience than this figure).", "", ""),
    ("TTFB", "Time To First Byte: wait delay between sending the request and receiving the "
     "first byte of the server response.", "", ""),
    ("PUE", "Power Usage Effectiveness: energy efficiency ratio of a datacenter (total energy "
     "consumed ÷ energy used by the servers alone). Closer to 1 = more efficient.", "", ""),
    ("ACV", "Life Cycle Assessment (LCA): standardized method (ISO 14040/14044) assessing the environmental impact "
     "of a product over all its phases. The e-footprint library used here only models "
     "two of them (manufacturing + usage), see Methodology appendix A.", "", ""),
    ("CO2e", "CO2 equivalent: unit that converts all emitted greenhouse gases into a single "
     "comparable indicator, according to their global warming potential.", "", ""),
]


def _section_glossary():
    """Centralized glossary of all the report acronyms, a single
    definition per term (linked from table headers
    and the first mention of each section, never re-explained in full
    several times — otherwise the report becomes unreadable for very
    repeated terms like HAR or CO2e)."""
    rows = ""
    for acro, definition, thresholds, url in _GLOSSARY_ENTRIES:
        rows += (
            f'<tr id="glossaire-{acro.lower()}">'
            f'<td style="white-space:nowrap"><b>{acro}</b></td>'
            f'<td>{definition}{_source_link(url)}</td>'
            f'<td style="color:#555;font-size:15px">{thresholds}</td>'
            f'</tr>'
        )
    reliability_order = (
        '<p style="font-size:16px;color:#555;margin-top:16px">'
        '<b>Provenance reliability order (from most to least reliable):</b><br>'
        f'{_confidence_badge("collected")} (real measurement) &gt; '
        f'{_confidence_badge("estimated")} (deduction of an order of magnitude) &gt; '
        f'{_confidence_badge("stated")} (service answer via the questionnaire) &gt; '
        f'{_confidence_badge("declared")} (public declaration found) &gt; '
        f'{_confidence_badge("assumed")} (deduction from a weak hint).<br>'
        'In case of disagreement between two sources on the same criterion, it is the highest provenance '
        'highest in this order is retained in the report.</p>\n'
    )
    return (
        '<section id="glossaire">\n'
        '<h2>Glossary</h2>\n'
        '<p style="font-size:16px;color:#555;margin-bottom:8px">'
        'Each acronym is defined only here: the tables and the report text refer to it '
        'by a link rather than repeating the definition at each occurrence.</p>\n'
        '<table>\n'
        '<thead><tr><th>Term</th><th>Definition</th><th>Thresholds</th></tr></thead>\n'
        f'<tbody>{rows}</tbody>\n'
        '</table>\n'
        f'{reliability_order}'
        '</section>'
    )


def _cwv_reco_signal_html(metric, traffic, greenit, coverage_by_page):
    """Lot 5 (recommandations) : version courte du signal indicatif de
    _cwv_diagnostic_signal(), with a pointer to the detail in the CWV analysis section.
    Returns an empty string if no usable signal (same calculation logic
    as the detailed section, shortened text only)."""
    long_signal = _cwv_diagnostic_signal(f"{metric}_x", traffic, greenit, coverage_by_page)
    if not long_signal:
        return ""
    short = {
        "cls": "third-party trackers and/or external web font(s) detected",
        "inp": "unused JS &gt; 60 % found",
    }.get(metric)
    if not short:
        return ""
    return (f'<br><span style="color:#888;font-size:0.85em">Signal : {short} '
            f'(detail in <a href="#cwv-analyse">CWV analysis section</a>).</span>')


def _recommendations_gains_block(gains):
    """Synthetic "Estimated CO2e gain" block for _section_recommendations, from
    efootprint-recommendations-gains.json. Nothing is added if `gains` is
    empty/absent (backward-compatible report for audits without this file)."""
    if not gains:
        return ""

    tiers = gains.get("tiers") or {}
    reductions = gains.get("reductions_detail")
    reference = gains.get("reference") or {}
    ref_scenario = reference.get("scenario_file")

    if reductions == []:
        body = (
            '<p style="font-size:15px;color:#555;margin:6px 0">'
            'No quantifiable recommendation found on this audit '
            '(missing data or no threshold exceeded).</p>'
        )
    else:
        rows_html = ""
        for key in ("prio1", "prio1_2", "prio1_2_3"):
            p = tiers.get(key)
            if not p:
                continue
            label = _TIER_STAGE_LABELS.get(key, key)
            delta_kg = p.get("delta_kg_co2e_per_year")
            delta_pct = p.get("delta_pct")
            scenario_file = p.get("scenario_file")
            kg_txt = f'{delta_kg:.2f} kg CO2e/an' if isinstance(delta_kg, (int, float)) else "?"
            pct_txt = f' ({delta_pct:.2f} %)' if isinstance(delta_pct, (int, float)) else ""
            link = (f' &middot; <a href="{scenario_file}">download the JSON</a>'
                    f' &middot; <a href="{_MODEL_BUILDER_URL}" target="_blank" rel="noopener">'
                    f'ouvrir sur e-footprint.boavizta.org</a>'
                    if scenario_file else "")
            rows_html += f'<li>-<b>{kg_txt}</b>{pct_txt} en appliquant <b>{label}</b>{link}</li>'
        ref_link = (f' <a href="{ref_scenario}" target="_blank" rel="noopener">reference scenario</a>'
                    if ref_scenario else "")
        body = (
            f'<ul style="margin-top:6px;padding-left:20px">'
            f'{rows_html or "<li>No tier computed.</li>"}</ul>'
            f'<p style="font-size:15px;color:#555;margin:8px 0 4px">'
            f'Download the <code>.e-f.json</code> file of the tier that interests you, then '
            f'chargez-le (bouton "Open file") sur '
            f'<a href="{_MODEL_BUILDER_URL}" target="_blank" rel="noopener">'
            f'e-footprint.boavizta.org/model_builder</a> to explore the detail (breakdown by '
            f'component); compare it to the{ref_link} to check the gap manually.</p>'
        )

    return f"""
  <div class="prio" id="gain-co2e" style="background:{OCTO_PALE};border-left:4px solid {OCTO_BLUE}">
    <b>Estimated CO2e gain if you apply these recommendations</b>
    {body}
    <p style="font-size:13px;color:#888;margin:4px 0 0">
      Some recommendations (Core Web Vitals, EcoIndex, DOM, third-party CDN/scripts, third-party domains)
      are not included in this quantified calculation, for lack of a reliable e-footprint parameter or a measured
      target, see the detail in the <a href="#methodologie">Methodology appendix</a>.
    </p>
  </div>"""


def _ecoindex_gains_block(gains, page_metrics, cwv):
    """Synthetic "Estimated EcoIndex &amp; LCP gain" block, same visual style as
    `_recommendations_gains_block` (OCTO_PALE/OCTO_BLUE). Aggregation: average
    of the EcoIndex and LCP delta on pages with `measurement.status == "ok"`
    (one page = one voice, not weighted by traffic - consistent with the filter already
    applied by the dashboard). Returns "" if no usable data
    (gains absent, pre-work schema, or no page with a successful measurement)."""
    reductions_by_page = _ecoindex_reductions_by_page(gains)
    if not reductions_by_page:
        return ""

    deduped = [m for m in _dedup_page_metrics(page_metrics)
               if m.get("measurement", {}).get("status") == "ok"]
    if not deduped:
        return ""

    rows_html = ""
    for key in ("prio1", "prio1_2", "prio1_2_3"):
        deltas_eco = []
        deltas_lcp = []
        for m in deduped:
            url = _normalize_page_url(m["title"])
            reductions_for_tier = (reductions_by_page.get(url) or {}).get(key)
            if not reductions_for_tier:
                continue
            t = _ecoindex_lcp_for_tier(m, cwv, reductions_for_tier)
            deltas_eco.append(t["score"] - m["ecoindex"])
            deltas_lcp.append(t["lcp_baseline"] - t["lcp"])
        if not deltas_eco:
            continue
        label = _TIER_STAGE_LABELS.get(key, key)
        avg_eco = sum(deltas_eco) / len(deltas_eco)
        avg_lcp = sum(deltas_lcp) / len(deltas_lcp)
        rows_html += (
            f'<li>+<b>{avg_eco:.1f} points EcoIndex</b> en moyenne, et '
            f'&asymp; -<b>{avg_lcp:.2f} s</b> of LCP (rough estimate) by applying <b>{label}</b></li>'
        )

    if not rows_html:
        return ""

    return f"""
  <div class="prio" style="background:{OCTO_PALE};border-left:4px solid {OCTO_BLUE}">
    <b>Estimated EcoIndex &amp; LCP gain if you apply these recommendations</b>
    <ul style="margin-top:6px;padding-left:20px">{rows_html}</ul>
    <p style="font-size:13px;color:#888;margin:4px 0 0">
      <b>Rough LCP estimate: risk of overestimation</b> (ignores latency,
      HTTP/2+ parallelization and the browser cache). The DOM is not modified by these
      recommendations. INP and CLS are not estimated, see the detail in
      <a href="#methodologie">Methodology appendix</a>.
    </p>
  </div>"""


def _section_recommendations(page_metrics, traffic, coverage_by_page, cwv=None, tech_stack=None, greenit=None, gains=None):
    prio1, prio2, prio3 = [], [], []
    cwv = cwv or {}
    deduped = _dedup_page_metrics(page_metrics)

    # CWV — grouped by metric (LCP, INP, CLS), one recommendation per problem
    from urllib.parse import urlparse

    # Check whether dead JS > 60% is present (to enrich the LCP reco)
    _has_heavy_js = any(
        coverage_summary(pd["entries"] if isinstance(pd, dict) else pd)["js"]["pct"] > 60
        for pd in coverage_by_page.values()
    ) if coverage_by_page else False

    lcp_bad, lcp_warn = [], []
    inp_bad, inp_warn = [], []
    cls_bad, cls_warn = [], []
    cwv_failed = []

    for m in deduped:
        # Recos = "worst of both" per metric: a desktop problem surfaces too.
        by_strat = _cwv_for_page(m, cwv)
        c, worst_strat = _cwv_worst_per_metric(by_strat)
        num = m.get("page_num", "")
        url = m["title"]
        short = urlparse(url).path.rstrip("/") or "/"

        # Measurement attempted but failed (e.g. network timeout) on at least one
        # strategy: say it rather than let it disappear silently
        # (cf. absence != failure) — even when the other strategy succeeded, otherwise
        # a failed measurement on mobile passes for a "no problem" given the
        # desktop result alone.
        failed_strats = [
            s for s, r in (by_strat or {}).items()
            if r and r.get("measurement", {}).get("status") not in (None, "ok")
        ]
        if failed_strats:
            mk = "".join(_cwv_device_marker(s) for s in failed_strats)
            cwv_failed.append(f'<a href="{url}" target="_blank" rel="noopener">{mk} P{num} {short}</a>')

        if not c:
            continue

        def _label(metric):
            # Annotates the page with the device the most unfavorable value comes from
            mk = _cwv_device_marker(worst_strat[metric]) if worst_strat.get(metric) else ""
            mk = f'<span title="pire des deux : {worst_strat.get(metric)}">{mk}</span> ' if mk else ""
            return f'<a href="{url}" target="_blank" rel="noopener">{mk}P{num} {short}</a>'

        lcp  = c.get("lcp")
        inp  = c.get("inp")
        cls_ = c.get("cls")
        if isinstance(lcp, (int, float)):
            if lcp > 2.5:   lcp_bad.append((lcp, _label("lcp")))
            elif lcp > 1.8: lcp_warn.append((lcp, _label("lcp")))
        if isinstance(inp, (int, float)):
            if inp > 500:   inp_bad.append((inp, _label("inp")))
            elif inp > 200: inp_warn.append((inp, _label("inp")))
        if isinstance(cls_, (int, float)):
            if cls_ > 0.25: cls_bad.append((cls_, _label("cls")))
            elif cls_ > 0.1: cls_warn.append((cls_, _label("cls")))

    def _pages_str(items):
        return ", ".join(lbl for _, lbl in items)

    def _lcp_item(items, severity):
        vals = [v for v, _ in items]
        range_str = f"{min(vals):.1f} s" if len(vals) == 1 else f"entre {min(vals):.1f} s et {max(vals):.1f} s"
        n = len(items)
        js_note = " (dead JS code > 60% identified)" if _has_heavy_js else ""
        return (
            f"<strong>Reduce the {_glossary_link('LCP')}</strong> ({range_str} on {n} page{'s' if n>1 else ''} — {severity})<br>"
            f'<span style="color:#555;font-size:0.9em">'
            f"Likely causes: hero image not preloaded, render-blocking JS{js_note}, high {_glossary_link('TTFB')}.<br>"
            f"Actions : ajouter <code>&lt;link rel=\"preload\"&gt;</code> sur l'image hero &middot; "
            f"passer le JS non critique en <code>defer</code>/<code>async</code> &middot; "
            f"analyser le TTFB avec WebPageTest.<br>"
            f"Pages : {_pages_str(items)}"
            f"</span>"
        )

    def _inp_item(items, severity):
        vals = [v for v, _ in items]
        range_str = f"{int(min(vals))} ms" if len(vals) == 1 else f"entre {int(min(vals))} ms et {int(max(vals))} ms"
        n = len(items)
        signal = _cwv_reco_signal_html("inp", traffic, greenit, coverage_by_page)
        return (
            f"<strong>Reduce the {_glossary_link('INP')}</strong> ({range_str} on {n} page{'s' if n>1 else ''} — {severity})<br>"
            f'<span style="color:#555;font-size:0.9em">'
            f"Likely causes: long JS tasks, main thread saturated during interactions.<br>"
            f"Actions: split long tasks (&gt; 50 ms) &middot; "
            f"utiliser <code>scheduler.yield()</code> &middot; lazy-loader les composants non visibles.<br>"
            f"Pages : {_pages_str(items)}"
            f"</span>{signal}"
        )

    def _cls_item(items, severity):
        vals = [v for v, _ in items]
        range_str = f"{min(vals):.2f}" if len(vals) == 1 else f"entre {min(vals):.2f} et {max(vals):.2f}"
        n = len(items)
        signal = _cwv_reco_signal_html("cls", traffic, greenit, coverage_by_page)
        return (
            f"<strong>Fix layout shifts ({_glossary_link('CLS')})</strong> ({range_str} on {n} page{'s' if n>1 else ''} — {severity})<br>"
            f'<span style="color:#555;font-size:0.9em">'
            f"Causes probables : images ou iframes sans dimensions explicites, polices web sans size-adjust.<br>"
            f"Actions: set <code>width</code>/<code>height</code> on media &middot; "
            f"utiliser <code>font-display: optional</code> ou <code>size-adjust</code>.<br>"
            f"Pages : {_pages_str(items)}"
            f"</span>{signal}"
        )

    if lcp_bad:
        prio1.append(_lcp_item(lcp_bad, "mauvais"))
    elif lcp_warn:
        prio2.append(_lcp_item(lcp_warn, "needs improvement"))

    if inp_bad:
        prio1.append(_inp_item(inp_bad, "mauvais"))
    elif inp_warn:
        prio2.append(_inp_item(inp_warn, "needs improvement"))

    if cls_bad:
        prio1.append(_cls_item(cls_bad, "mauvais"))
    elif cls_warn:
        prio2.append(_cls_item(cls_warn, "needs improvement"))

    if cwv_failed:
        n = len(cwv_failed)
        prio2.append(
            f"CWV measurement failed (network timeout) on {n} page{'s' if n > 1 else ''} : "
            + ", ".join(cwv_failed)
            + " - re-run before concluding on these pages."
        )

    # EcoIndex < 40 → priority 1
    for m in page_metrics:
        if m["ecoindex"] < 40:
            prio1.append(f"<b>{m['title'][:40]}</b> : {_glossary_link('EcoIndex')} {m['ecoindex']}/100 (grade {m['grade']}) - optimisation urgente")
        elif m["ecoindex"] < 55:
            prio2.append(f"<b>{m['title'][:40]}</b> : {_glossary_link('EcoIndex')} {m['ecoindex']}/100 (grade {m['grade']}) - needs improvement")

    # High DOM
    for m in page_metrics:
        if m["dom"] > 1500:
            prio1.append(f"{_glossary_link('DOM')} {m['dom']} elements on <b>{m['title'][:30]}</b> - remove inactive components")
        elif m["dom"] > 800:
            prio2.append(f"{_glossary_link('DOM')} {m['dom']} elements on <b>{m['title'][:30]}</b> - assess superfluous components")

    # Doublons
    if traffic["duplicates"]:
        prio2.append(
            f"{len(traffic['duplicates'])} resources loaded twice - configure the browser cache"
            f' <a href="#trafic-doublons" style="color:inherit;text-decoration:underline;font-size:16px">&#8594; see the detail</a>'
        )

    # Code mort > 70%
    for page_name, page_data in coverage_by_page.items():
        entries = page_data["entries"] if isinstance(page_data, dict) else page_data
        summ = coverage_summary(entries)
        # page_name is a raw path ("/jobs"): prefix "Page" to
        # avoid a bullet starting directly with a "/" without context, and
        # link to the full URL when known.
        page_label = f"Page {page_name}" if page_name.startswith("/") else page_name
        page_url = page_data.get("url") if isinstance(page_data, dict) else None
        if page_url:
            page_label = f'<a href="{page_url}" target="_blank" rel="noopener">{page_label}</a>'
        if summ["js"]["pct"] > 70:
            prio1.append(f"<b>{page_label}</b> : {summ['js']['pct']}% of JS unused ({summ['js']['unused_kb']} KB) - lazy loading + tree shaking")
        elif summ["js"]["pct"] > 50:
            prio2.append(f"<b>{page_label}</b> : {summ['js']['pct']}% of JS unused - assess route-level splitting")
        if summ["css"]["pct"] > 80:
            prio2.append(f"<b>{page_label}</b> : {summ['css']['pct']}% of CSS unused ({summ['css']['unused_kb']} KB) - PurgeCSS recommended")

    # PRIORITY 3 — continuous improvement, cross-referenced with the detected stack (documentary).
    # The rules read the detected CATEGORIES, never site names: generic.
    prio3 = ["Activer la compression Brotli sur tous les serveurs"]

    _technos = (tech_stack or {}).get("technologies", []) if tech_stack else []
    _cats = {t.get("category") for t in _technos}
    _by_cat = defaultdict(list)
    for _t in _technos:
        _name = _t.get("name")
        if _name:
            _by_cat[_t.get("category")].append(_name)

    # CDN: highlight it if present, otherwise recommend setting one up.
    if "CDN" in _cats:
        _cdn_names = ", ".join(dict.fromkeys(_by_cat.get("CDN", [])))
        prio3.append(
            f"<b>CDN already in place</b> ({_cdn_names}): good point, static assets "
            "are served as close as possible to visitors. Keep it up."
        )
    else:
        prio3.append("Mettre en place un CDN pour les assets statiques")

    # Third-party scripts: name them if detected, otherwise keep the generic lead.
    _third_labels = []
    for _cat in ("Analytics", "Tag manager", "JS library"):
        for _name in _by_cat.get(_cat, []):
            _third_labels.append(f"{_name} ({_cat.lower()})")
    if _third_labels:
        prio3.append(
            "Third-party scripts detected: <b>" + ", ".join(_third_labels) + "</b>. "
            "Assess their real weight and necessity; consider lighter alternatives "
            "or deferred loading."
        )
    else:
        prio3.append(
            "Assess replacing heavy third-party libraries (analytics, chatbot) "
            "with lighter alternatives"
        )

    # Third-party domain multiplication: each host adds DNS + TLS.
    _tp_hosts = (tech_stack or {}).get("third_party_hosts", []) if tech_stack else []
    if len(_tp_hosts) >= 8:
        prio3.append(
            f"<b>{len(_tp_hosts)} third-party domains</b> requested at load time: each domain "
            "adds a DNS resolution and a TLS handshake. Grouping or self-hosting "
            "critical resources reduces latency and connections."
        )

    def _items(lst):
        return "".join(f"<li>{i}</li>" for i in lst) if lst else "<li>Aucun constat critique.</li>"

    def _see_also(items_list, *links):
        if not items_list:
            return ""
        parts = " &nbsp;·&nbsp; ".join(
            f'<a href="#{sid}" style="color:inherit;text-decoration:underline;font-size:16px">{label}</a>'
            for sid, label in links
        )
        return f'<div style="margin-top:8px;opacity:.8">&#8594; Voir : {parts}</div>'

    return f"""<section id="recommandations">
  <h2>Recommandations</h2>
  <div class="prio prio-1">
    <b>PRIORITY 1 - High impact</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio1)}</ul>
    {_see_also(prio1, ("dashboard", "A.1 EcoIndex dashboard"), ("cwv-analyse", "CWV analysis"), ("coverage", "A.3 Dead code (Coverage)"))}
  </div>
  <div class="prio prio-2">
    <b>PRIORITY 2 - Medium impact</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio2)}</ul>
    {_see_also(prio2, ("traffic", "A.2 Network traffic"), ("dashboard", "A.1 EcoIndex dashboard"))}
  </div>
  <div class="prio prio-3">
    <b>PRIORITY 3 - Continuous improvement</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio3)}</ul>
    {_see_also(prio3, ("traffic", "A.2 Network traffic"), ("greenit", "2. GreenIT best practices"))}
  </div>
  {_recommendations_gains_block(gains)}
  {_ecoindex_gains_block(gains, page_metrics, cwv)}
</section>"""


# ── Main entry point ──────────────────────────────────────────────────────────

def generate(audit_dir, output_path=None):
    audit_dir = Path(audit_dir)

    # Localisation des fichiers — chercher dans audit_dir, sinon dans le dossier parent (SOURCE_DIR)
    har_files = list(audit_dir.glob("*.har"))
    source_dir = audit_dir
    if not har_files and audit_dir.parent != audit_dir:
        har_files = list(audit_dir.parent.glob("*.har"))
        if har_files:
            source_dir = audit_dir.parent
    if not har_files:
        # Dernier repli : le sous-dossier de captures brutes (dans .gitignore),
        # searched under audit_dir then under its parent.
        for cand in (audit_dir, audit_dir.parent):
            har_files = list((cand / RAW_DATA_DIR).glob("*.har"))
            if har_files:
                source_dir = cand
                break
    if not har_files:
        raise FileNotFoundError(f"No .har file in {audit_dir} nor in {audit_dir.parent}")
    har_path = har_files[0]

    # Coverage files follow the same layout as the HAR: flat, otherwise in the
    # sous-dossier de captures brutes. source_dir reste le dossier de l'audit, car
    # that is where the PRODUCED files live (cwv.json, etc.).
    cov_files = (sorted(source_dir.glob("Coverage-*.json"))
                 or sorted(source_dir.glob("*coverage*.json"))
                 or sorted((source_dir / RAW_DATA_DIR).glob("Coverage-*.json"))
                 or sorted((source_dir / RAW_DATA_DIR).glob("*coverage*.json")))
    cwv_path  = audit_dir / "cwv.json"
    if not cwv_path.exists():
        cwv_path = source_dir / "cwv.json"

    greenit_path = audit_dir / "greenit.json"

    print(f"HAR      : {har_path.name}")
    print(f"Coverage : {len(cov_files)} file(s)")
    print(f"CWV      : {'yes' if cwv_path.exists() else 'no (HAR timings used)'}")
    print(f"GreenIT  : {'JSON file' if greenit_path.exists() else 'computed from HAR'}")

    har_data     = parse_har(har_path)
    page_metrics = extract_page_metrics(har_data)
    traffic      = har_traffic_analysis(har_data)
    cwv          = load_cwv(cwv_path) if cwv_path.exists() else {}
    greenit      = load_greenit(audit_dir) or compute_greenit_from_har(har_data)
    python_summary = load_python_summary(audit_dir)
    recommendations_gains = load_recommendations_gains(audit_dir)
    topology_svg = load_topology_svg(audit_dir)
    tech_stack = load_tech_stack(audit_dir)
    eof_results = load_eof_results(audit_dir)
    eof_radar_svg = load_eof_radar_svg(audit_dir)

    coverage_by_page = {}
    _asset_exts = re.compile(r'\.(js|css|webp|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|otf|eot|json|map)(\?.*)?$', re.I)
    _generic_scripts = {"header", "footer", "orejime", "swetrix", "gtm", "analytics",
                        "style", "main", "bundle", "chunk", "home", "index"}

    # URLs the HAR declares as served as text/html: only those are pages.
    _har_documents = {
        e.get("request", {}).get("url", "").split("?")[0]
        for e in har_data.get("log", {}).get("entries", [])
        if "html" in (e.get("response", {}).get("content", {}).get("mimeType", "") or "").lower()
    }

    for cf in cov_files:
        with open(cf, encoding="utf-8") as _f:
            _raw = json.load(_f)
        raw_entries = _raw if isinstance(_raw, list) else _raw.get("entries", [])
        entries = parse_coverage_file(cf)

        # 1. URL de page : chercher une URL sans extension d'asset dans tous les domaines,
        #    preferring URLs that are not third-party fonts/cdn.
        from urllib.parse import urlparse as _up0
        from collections import Counter as _Counter

        # Main domain = the most represented among URLs with assets
        _domain_counts = _Counter()
        for item in raw_entries:
            u = item.get("url", "")
            if u.startswith("http"):
                _domain_counts[_up0(u).netloc] += 1
        _main_domain = _domain_counts.most_common(1)[0][0] if _domain_counts else ""

        # The HAR says which of these URLs were actually served as
        # text/html. Without this corroboration, the first URL without
        # asset extension wins: on a teleprocedure, it is often a
        # technique (jeton anti-CSRF, endpoint de messages) et la page s'affiche
        # under a label that is not the one of the screen seen by the user.
        _candidates = []
        first_party = None
        for item in raw_entries:
            u = item.get("url", "")
            if not u.startswith("http"):
                continue
            _netloc = _up0(u).netloc
            if _netloc != _main_domain:
                continue
            if not _asset_exts.search(u.split("?")[0]):
                _candidates.append(u)
            elif first_party is None and u.endswith(".js"):
                fname = u.split("/")[-1].split("?")[0].replace(".js", "").lower()
                if fname not in _generic_scripts:
                    first_party = u

        page_url = ""
        for u in _candidates:
            if u.split("?")[0] in _har_documents:
                page_url = u
                break
        if not page_url and _candidates:
            page_url = _candidates[0]

        # 2. Fallback: page-specific JS script
        if not page_url and first_party:
            from urllib.parse import urlparse as _up
            _p = _up(first_party)
            _fname = _p.path.split("/")[-1].split("?")[0].replace(".js", "")
            page_url = f"{_p.scheme}://{_p.netloc}/{_fname}"

        ts_raw = cf.stem.replace("Coverage-", "")
        # Convertir "20260710T152838" → "15:28" (heure de capture)
        import re as _re
        _m = _re.match(r'\d{8}T(\d{2})(\d{2})', ts_raw)
        ts_human = f"{_m.group(1)}h{_m.group(2)}" if _m else ts_raw[:10]

        if page_url:
            from urllib.parse import urlparse as _up2
            path = _up2(page_url).path.rstrip("/") or "/"
            label = path
        else:
            label = f"Page — {ts_human}"
        # Avoid collisions if two captures of the same page
        base_label = label
        n = 2
        while label in coverage_by_page:
            label = f"{base_label} ({ts_human})"
            if label in coverage_by_page:
                label = f"{base_label} ({ts_human}-{n})"
                n += 1
            else:
                break
        coverage_by_page[label] = {"entries": entries, "url": page_url}

    # Construction HTML
    today   = date.today().strftime("%d/%m/%Y")
    domains = ", ".join(list(traffic["domains"].keys())[:4])
    title   = f"Web journey audit - {today}"
    deduped_metrics = _dedup_page_metrics(page_metrics)
    nb_pages = len(deduped_metrics)

    # The tech section is only rendered if technologies were detected
    has_tech = bool(tech_stack and tech_stack.get("technologies"))

    # EcoIndex/LCP gain per page and EOF detail computed early: these are appendices
    # standalone (substantial result, not methodology notes - cf. their docstrings)
    # whose presence conditions both the appendix list of the TOC and the
    # corps du rapport plus bas ; on ne les computed qu'une fois.
    gain_lcp_html = _section_gain_ecoindex_lcp(recommendations_gains, page_metrics, cwv)
    eof_detail_html = _section_eof_detail(eof_results)

    # Sections present (for the TOC). Methodology & assumptions last
    # position (after Glossary, not before): explicit request, so that its
    # sub-sections A→F continue the same sequence without leaving anything behind.
    annex_sections = [
        ("dashboard", "EcoIndex dashboard"),
        ("traffic",    "Network traffic"),
        ("coverage",  "Code mort (Coverage)"),
    ]
    if cwv:
        annex_sections.append(("cwv", "Core Web Vitals"))
    if has_tech:
        annex_sections.append(("stack-technique", "Tech stack"))
    if gain_lcp_html:
        annex_sections.append(("gain-ecoindex-lcp", "EcoIndex & LCP gain per page"))
    if eof_detail_html:
        annex_sections.append(("eof-detail", "EOF criteria detail"))
    annex_sections.append(("glossaire", "Glossary"))
    annex_sections.append(("methodologie", "Methodology & assumptions"))

    has_medias = bool((greenit or {}).get("media", {}).get("video", {}).get("count") or
                       (greenit or {}).get("media", {}).get("pdf", {}).get("count"))

    # Main sections (1-6) numbered by enumerating only those present -
    # replaces the old manual counter `n`, which could desync from the TOC
    # if a section was added to the report body without being reflected here.
    main_sections = [
        ("recommandations", "Recommandations", True),
        ("greenit", "Bonnes pratiques GreenIT", True),
        ("medias", "Media and documents to watch", has_medias),
        ("cwv-analyse", "Analyse Core Web Vitals", bool(cwv)),
        ("efootprint", "Environmental impact (CO2e)", bool(python_summary)),
        ("eof", "Optimization potential (EOF)", bool(eof_results)),
    ]
    present_main = [(anchor, title) for anchor, title, present in main_sections if present]
    main_nav_items = "".join(
        f'<li><a href="#{anchor}">{i}. {title}</a></li>'
        for i, (anchor, title) in enumerate(present_main, start=1)
    )
    annex_num = len(present_main) + 1
    # TOC number per anchor, to prefix the <h2> of each main section
    # (same number as the "N. Title" link of the TOC, cf. _prefix_h2_main below).
    main_num = {anchor: i for i, (anchor, _) in enumerate(present_main, start=1)}

    # Methodology computed before the TOC: its letters A/B/C... depend on the
    # sub-sections actually present for this audit, so its result is needed
    # to build the TOC, even before assembling the report body below.
    methodology_html, methodology_nav_entries = _section_methodology(python_summary, cwv, recommendations_gains)
    methodology_inline = " &nbsp;·&nbsp; ".join(
        f'<a href="#{manchor}">{letter}. {mtitle}</a>' for letter, manchor, mtitle in methodology_nav_entries
    )

    # "{annex_num}.N" to match exactly the numbering of the appendix body
    # (_prefix_h2 avec _anum(), plus bas dans cette fonction).
    annex_inline = " &nbsp;·&nbsp; ".join(
        f'<a href="#{sid}">{annex_num}.{i+1} {slabel}</a>'
        for i, (sid, slabel) in enumerate(annex_sections)
    )
    nav_items = (
        f'{main_nav_items}'
        f'<li>'
        f'<a href="#annexes">{annex_num}. Appendices</a>'
        f'<div style="margin-top:6px;margin-left:18px;font-size:15px;opacity:.85">{annex_inline}</div>'
        + (f'<div style="margin-top:4px;margin-left:36px;font-size:14px;opacity:.85">{methodology_inline}</div>'
           if methodology_nav_entries else '')
        + f'</li>'
        f'<li><a href="#couts" style="opacity:.75">Generation costs</a></li>'
    )

    html = _html_head(title)
    html += f"""<header>
  <h1>EROOM Audit Version {AGENT_VERSION}</h1>
  <div style="font-size:18px;margin-top:6px;opacity:.9">{domains}</div>
  <div class="meta">
    Date: {today} &nbsp;|&nbsp;
    {n_pages} page(s) analyzed &nbsp;|&nbsp;
    <a href="#glossaire-har" title="See the definition in the Glossary" style="color:inherit;text-decoration:underline">HAR</a> : {har_path.name} &nbsp;|&nbsp;
    Coverage: {len(cov_files)} file(s)
  </div>
</header>
<nav role="navigation" aria-label="Report contents">
  <h2>Contents</h2>
  <ul style="list-style:none;padding:0;margin:0">{nav_items}</ul>
</nav>
<main id="contenu">
"""
    def _prefix_h2(html_str, prefix):
        return html_str.replace('<h2>', f'<h2>{prefix} — ', 1)

    def _prefix_h2_main(html_str, anchor):
        # Same mechanism as _prefix_h2 for appendices, but "N. " (like the
        # TOC) rather than "N — ": these are the 6 top sections, not
        # appendix sub-sections.
        return html_str.replace('<h2>', f'<h2>{main_num[anchor]}. ', 1)

    html += _prefix_h2_main(
        _section_recommendations(page_metrics, traffic, coverage_by_page, cwv, tech_stack, greenit, gains=recommendations_gains),
        "recommandations")
    html += _prefix_h2_main(_section_greenit(greenit), "greenit")
    if has_medias:
        html += _prefix_h2_main(_section_medias(greenit), "medias")
    if cwv:
        html += _prefix_h2_main(
            _section_cwv_analyse(page_metrics, cwv, traffic, greenit, coverage_by_page), "cwv-analyse")
    if python_summary:
        html += _prefix_h2_main(
            _section_efootprint(python_summary, topology_svg, gains=recommendations_gains), "efootprint")
    if eof_results:
        html += _prefix_h2_main(_section_eof(eof_results, eof_radar_svg), "eof")

    # Numbering {annex_num}.N derived uniformly from the position in
    # annex_sections (same mechanism for all appendices, no more special case).
    _annex_ids = [sid for sid, _ in annex_sections]

    def _anum(sid):
        return f"{annex_num}.{_annex_ids.index(sid) + 1}"

    html += '<section id="annexes" style="background:#f4f6fa;border:2px solid var(--octo-blue);border-radius:6px;padding:24px 24px 8px;margin-bottom:40px">\n'
    html += '<h2 style="border-left:none;padding-left:0;font-size:17px;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:20px">Annexes</h2>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_dashboard(page_metrics, cwv), _anum("dashboard"))}</div>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_traffic(traffic), _anum("traffic"))}</div>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_coverage(coverage_by_page), _anum("coverage"))}</div>\n'
    if cwv:
        html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_cwv(page_metrics, cwv), _anum("cwv"))}</div>\n'
    if has_tech:
        html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_tech(tech_stack), _anum("stack-technique"))}</div>\n'
    if gain_lcp_html:
        html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(gain_lcp_html, _anum("gain-ecoindex-lcp"))}</div>\n'
    if eof_detail_html:
        html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(eof_detail_html, _anum("eof-detail"))}</div>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_glossary(), _anum("glossaire"))}</div>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(methodology_html, _anum("methodologie"))}</div>\n'
    html += '</section>\n'

    html += "</main>\n"
    html += f"""<div id="couts" class="cost-info" style="background:#f0f4f8;border-top:1px solid #ccc;padding:1.5rem 0;">
  <div style="max-width:700px;margin:0 auto 0 40px">
    <details style="padding:0.75rem 1rem;background:white;border:1px solid #ccc;border-radius:4px;">
      <summary style="cursor:pointer;font-weight:600;">Generation costs (<span data-cost-field="cout">—</span> [*])</summary>
      <p style="margin:0.75rem 0 0.5rem;font-size:0.9rem;font-style:italic;opacity:0.8;">[*] Estimate computed over a time window on the session JSONL file. The duration is wall-clock time between the first and last message of the session (reading, writing, back-and-forths with the user included), not active computation time; it and the tokens can therefore include exchanges outside the analysis. Cost at public Anthropic API rates; under AWS Bedrock, consult AWS Cost Explorer.</p>
      <p style="margin:0.3rem 0;"><strong>Model:</strong> <span data-cost-field="modele">—</span></p>
      <p style="margin:0.3rem 0;"><strong>Effort :</strong> <span data-cost-field="effort">—</span></p>
      <p style="margin:0.3rem 0;"><strong>Duration:</strong> <span data-cost-field="duration">—</span></p>
      <p style="margin:0.3rem 0;"><strong>Tokens :</strong> <span data-cost-field="tokens">—</span></p>
      <p style="margin:0.3rem 0;"><strong>Estimated CO2e:</strong> <span data-cost-field="co2e">—</span></p>
      <p style="margin:0.3rem 0;font-size:0.9rem;color:#666;"><span data-cost-field="ratio-co2e"></span></p>
      <p style="margin:0.75rem 0 0 0;font-size:0.8rem;font-style:italic;opacity:0.75;">Estimated CO2e from the compute tokens (input + output + cache creation, excluding cache reads): 0.3-1.0 Wh/1000 tokens (Epoch AI 2025, Google Cloud August 2025), {_glossary_link("PUE")} 1.1-1.3, electricity carbon intensity 450-480 gCO2/kWh (world average, IEA). Wide range because no precise public data exists on the real compute infrastructure of the session; order of magnitude, not a measurement.</p>
      <p style="margin:0.3rem 0;font-size:0.85rem;color:#888;"><strong>Source files:</strong> {har_path.name}, {len(cov_files)} Coverage file(s)</p>
    </details>
  </div>
</div>
<footer>Report generated on {today} - EROOM Agent v{AGENT_VERSION}</footer>
"""
    html += "</body>\n</html>\n"

    if output_path is None:
        output_path = audit_dir / f"journey-report-{date.today().isoformat()}.html"
    output_path = Path(output_path)
    output_path.write_text(html, encoding="utf-8")
    print(f"\nHTML report generated: {output_path}")

    import subprocess
    patch_script = Path.home() / ".claude/scripts/patch-audit-cost.sh"
    if patch_script.exists():
        subprocess.run(["bash", str(patch_script), str(output_path)], check=False)
    else:
        print(f"[costs] patch-audit-cost.sh not found ({patch_script}) — costs section not patched")

    _warn_internal_values(output_path)

    return output_path


def _warn_internal_values(output_path):
    """Relit le rapport produit et signale les values internes visibles.

    WARNS, does not block: the report stays written and the generation ends
    normally. An EOF axis without an answer is a legitimate state of the framework
    today, it must not break the deliverable's production. The full check,
    complete, returns a non-zero exit code and can join a
    batterie : `python3 check_report_values.py <rapport>`.

    Run AFTER `patch-audit-cost.sh`, hence on the really final file.

    This check exists because the project's validators watch the NAMES
    of keys and never the DISPLAYED VALUES: a bold `None%` in the center of the
    EOF radar went through the whole chain unseen.

    A non-blocking check must not be able to crash the
    generation as a side effect: any error on its part is caught and reported.
    The report is already written at this stage, it is safe, but a crash here
    donnerait une trace Python en fin de commande et ferait croire que la
    would look like the generation failed.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from check_report_values import check
        leaks, _exempted, _malformed = check(
            output_path.read_text(encoding="utf-8", errors="replace")
        )
    except Exception as error:  # volontairement large, cf. la docstring
        print(
            f"[values] check not run ({type(error).__name__}: {error}) - "
            "displayed values NOT checked, the report is produced anyway"
        )
        return

    if not leaks:
        print("[values] no internal value visible in the report.")
        return

    print(
        f"\n[values] WARNING: {len(leaks)} internal value(s) visible "
        "to the report reader."
    )
    for line_no, name, reason, excerpt in leaks[:10]:
        print(f"    {output_path.name}:{line_no}  {name} - {reason}")
        print(f"        {excerpt}")
    if len(leaks) > 10:
        print(f"    ... and {len(leaks) - 10} more.")
    print(f"    Detail: python3 check_report_values.py {output_path}")
    print("    The report was indeed produced: this warning blocks nothing.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_report_html.py <audit-dir> [--output report.html]")
        sys.exit(1)

    audit_dir = sys.argv[1]
    out = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            out = sys.argv[idx + 1]

    generate(audit_dir, out)
