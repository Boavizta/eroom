#!/usr/bin/env python3
"""
EcoIndex utilities — official formula (cnumr/ecoindex_reference).
DOM extraction from HAR, per-page metrics, score + grade computation.

Standalone usage:
  python3 har_metrics.py capture.har
"""

import base64
import json
from pathlib import Path
import math
import re
import sys
from pathlib import Path

# Official quantiles (cnumr/ecoindex_reference)
_ECO_Q_DOM  = [0,47,75,159,233,298,358,417,476,537,603,674,753,843,949,1076,1237,1459,1801,2479,594601]
_ECO_Q_REQ  = [0,2,15,25,34,42,49,56,63,70,78,86,95,105,117,130,147,170,205,281,3920]
_ECO_Q_SIZE = [0,1.37,144.7,319.53,479.46,631.97,783.38,937.91,1098.62,1265.47,1448.32,1648.27,
               1876.08,2142.06,2465.37,2866.31,3401.59,4155.73,5400.08,8037.54,223212.26]

# (min threshold, letter, rgb)
_ECO_GRADES = [
    (80, "A", "#349A47"),
    (70, "B", "#51B84B"),
    (55, "C", "#CADB2A"),
    (40, "D", "#F6EB15"),
    (25, "E", "#FECD06"),
    (10, "F", "#F99839"),
    (0,  "G", "#ED2124"),
]


def _quantile(quantiles, value):
    for i in range(1, len(quantiles)):
        if value < quantiles[i]:
            return i - 1 + (value - quantiles[i-1]) / (quantiles[i] - quantiles[i-1])
    return len(quantiles) - 1


def ecoindex_score(dom, req, size_ko):
    """Returns the EcoIndex score (0-100) from DOM, requests and weight in KB."""
    qd = _quantile(_ECO_Q_DOM,  dom)
    qr = _quantile(_ECO_Q_REQ,  req)
    qs = _quantile(_ECO_Q_SIZE, size_ko)
    return math.ceil(100 - 5 * (3 * qd + 2 * qr + qs) / 6)


def ecoindex_grade(score):
    """Returns (letter, hex_color) for an EcoIndex score."""
    for threshold, letter, color in _ECO_GRADES:
        if score >= threshold:
            return letter, color
    return "G", "#ED2124"


# Throughput of the "mobileSlow4G" throttling profile used by Lighthouse
# (`throttlingMethod: 'simulate'`, default mobile setting). RE-VERIFIED on
# 2026-09-14 in the npm package @paulirish/trace_engine@0.0.65
# (models/trace/lantern/simulation/Constants.js), to which
# GoogleChrome/lighthouse (core/config/constants.js, main branch) now re-exports
# its throttling constant: throughputKbps=1.6*1024=1638.4,
# downloadThroughputKbps = throughputKbps * DEVTOOLS_THROUGHPUT_ADJUSTMENT_FACTOR
# (0.9) = 1474.56 kbit/s - it is this DOWNLOAD throughput (not the raw one) that
# actually applies to page loading.
LIGHTHOUSE_SLOW4G_DOWNLOAD_BPS = 1474.56 * 1000  # kbit/s -> bit/s


def lcp_delta_s(bytes_removed_transferred, download_bps=LIGHTHOUSE_SLOW4G_DOWNLOAD_BPS):
    """Estimated transfer-time delta for a removal of transferred bytes.

    ROUGH ESTIMATE: (bytes removed x 8) / Lighthouse Slow4G throughput.
    Ignores latency (RTT), HTTP/2+ parallelism and browser cache
    - RISK OF OVERESTIMATING the real LCP gain, to be stated
    explicitly wherever this figure is displayed.
    """
    return (bytes_removed_transferred * 8) / download_bps


def count_dom_elements(html_text):
    """Counts opening tags in an HTML body."""
    if not html_text:
        return 0
    return len(re.findall(r'<[a-zA-Z][^/>]*', html_text))


def extract_dom_from_har_entry(entry):
    """Extracts the DOM from a HAR entry of type document (HTML).

    Returns (count, success, reason):
      - count: number of tags (0 on failure)
      - success: True if measured successfully
      - reason: None on success, error message otherwise
    """
    content = entry.get("response", {}).get("content", {})
    mime = content.get("mimeType", "")
    if "html" not in mime:
        return 0, False, "no_html_entry"

    text = content.get("text", "")
    if not text:
        return 0, False, "no_content"

    # Encoding handling
    encoding = content.get("encoding", "")
    if encoding == "base64":
        try:
            decoded_bytes = base64.b64decode(text)
            text = decoded_bytes.decode("utf-8")
        except Exception as exc:
            return 0, False, f"base64_decode_failure: {str(exc)}"
    elif encoding and encoding != "":
        # Non-empty and unknown encoding
        return 0, False, f"unknown_encoding: {encoding}"

    # Tag count
    count = count_dom_elements(text)

    # Guard: a non-empty HTML document with zero tags is abnormal
    if count == 0 and len(text.strip()) > 0:
        return 0, False, "no_tag_recognized"

    return count, True, None


def extract_page_metrics(har_data):
    """
    Extracts per-page metrics from parsed HAR data.
    Returns a list of dicts:
      { page_id, url, title, req, size_ko, dom, on_load_ms, on_content_load_ms }
    """
    log = har_data.get("log", {})
    pages = log.get("pages", [])
    entries = log.get("entries", [])

    # Index entries by pageref
    entries_by_page = {}
    for e in entries:
        ref = e.get("pageref", "")
        entries_by_page.setdefault(ref, []).append(e)

    results = []
    for i, page in enumerate(pages):
        pid = page.get("id", f"page_{i+1}")
        title = page.get("title", pid)
        timings = page.get("pageTimings", {})
        on_load = timings.get("onLoad") or 0
        on_content = timings.get("onContentLoad") or 0

        page_entries = entries_by_page.get(pid, [])
        req = len(page_entries)
        size_bytes = sum(
            e.get("response", {}).get("content", {}).get("size", 0)
            for e in page_entries
        )
        size_ko = round(size_bytes / 1024, 1)

        # DOM: first HTML entry of the page
        dom = 0
        dom_success = False
        dom_reason = None
        url = page.get("title", "")  # HAR pages store the URL in title

        for e in page_entries:
            count, success, reason = extract_dom_from_har_entry(e)
            if success:
                dom = count
                dom_success = True
                dom_reason = None
                break
            # Keep track of the first one tried
            if dom_reason is None:
                dom_reason = reason

        # Build the measurement block per the convention
        if dom_success:
            measurement = {
                "status": "ok",
                "target": url,
                "detail": None
            }
        elif dom_reason == "no_content":
            measurement = {
                "status": "read_error",
                "target": url,
                "detail": "The HAR capture does not contain the HTML response bodies"
            }
        elif dom_reason and dom_reason.startswith("base64_decode_failure"):
            measurement = {
                "status": "read_error",
                "target": url,
                "detail": f"base64 decoding failed: {dom_reason.split(': ', 1)[1] if ': ' in dom_reason else 'invalid'}"
            }
        elif dom_reason and dom_reason.startswith("unknown_encoding"):
            encoding_name = dom_reason.split(": ", 1)[1] if ": " in dom_reason else "unknown"
            measurement = {
                "status": "read_error",
                "target": url,
                "detail": f"Unsupported encoding: {encoding_name}"
            }
        elif dom_reason == "no_tag_recognized":
            measurement = {
                "status": "analysis_error",
                "target": url,
                "detail": "HTML body read but no tag recognized"
            }
        elif dom_reason == "no_html_entry":
            measurement = {
                "status": "analysis_error",
                "target": url,
                "detail": "No HTML document found for this page"
            }
        else:
            # Default case if there is no entry at all
            measurement = {
                "status": "analysis_error",
                "target": url,
                "detail": "No HTML document found for this page"
            }

        score = ecoindex_score(dom, req, size_ko)
        grade, color = ecoindex_grade(score)

        results.append({
            "page_id": pid,
            "title": title,
            "req": req,
            "size_ko": size_ko,
            "dom": dom,
            "ecoindex": score,
            "grade": grade,
            "grade_color": color,
            "on_load_ms": round(on_load),
            "on_content_load_ms": round(on_content),
            "measurement": measurement,
        })

    return results


def load_cwv(cwv_path):
    """Loads cwv.json. Returns a dict indexed by (normalized) URL AND by page_id.

    Each value is a dict grouped by strategy: {"mobile": row, "desktop": row}.
    This keeps mobile AND desktop side by side for the same page.
    Historical entries without a 'strategy' field are classified as 'mobile'
    (old default).
    URL matching takes priority (robust if HAR and CWV IDs diverge)."""
    p = Path(cwv_path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    result = {}
    for row in data:
        strat = row.get("strategy", "mobile")
        keys = []
        if "url" in row:
            keys.append(row["url"].rstrip("/"))
        if "page" in row:
            keys.append(row["page"])
        for key in keys:
            result.setdefault(key, {})[strat] = row
    return result


# --- Standalone CLI for validation ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 har_metrics.py <file.har> [cwv.json]")
        sys.exit(1)

    har_path = sys.argv[1]

    # Start bound for cost computation (read by patch-audit-cost.sh)
    import time as _t
    _start_file = Path(har_path).parent / ".analysis_start"
    if not _start_file.exists():
        _start_file.write_text(str(int(_t.time())), encoding="utf-8")

    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    cwv = {}
    if len(sys.argv) >= 3:
        cwv = load_cwv(sys.argv[2])

    metrics = extract_page_metrics(har)

    # Failure count
    total_pages = len(metrics)
    failed_pages = sum(1 for m in metrics if m["measurement"]["status"] != "ok")

    print(f"\n{'Page':<30} {'Req':>5} {'KB':>8} {'DOM':>6} {'Score':>6} {'Grade':>6} {'onLoad':>9} {'Measurement':<10}")
    print("-" * 95)
    for m in metrics:
        status_marker = "✓" if m["measurement"]["status"] == "ok" else "✗ FAIL"
        print(f"{m['title'][:29]:<30} {m['req']:>5} {m['size_ko']:>8.1f} {m['dom']:>6} "
              f"{m['ecoindex']:>6} {m['grade']:>6} {m['on_load_ms']:>8}ms {status_marker:<10}")
        if m["measurement"]["status"] != "ok":
            print(f"  └→ {m['measurement']['status']}: {m['measurement']['detail']}")
        if m["page_id"] in cwv:
            c = cwv[m["page_id"]]
            print(f"  CWV → LCP: {c.get('lcp','?')}s  INP: {c.get('inp','?')}ms  CLS: {c.get('cls','?')}")

    print()
    if failed_pages > 0:
        print(f"⚠️  WARNING: {failed_pages} of {total_pages} pages have an unmeasured DOM")
        print()

    print()
    # Validation against known ANTS values (if P1 with dom=483, req=82, weight=1930 → score=53)
    test_score = ecoindex_score(483, 82, 1930)
    print(f"[ANTS P1 validation] dom=483 req=82 weight=1930 KB → score={test_score}/100 (expected: 53)")
    g, c = ecoindex_grade(test_score)
    print(f"  Grade: {g} ({c})")
