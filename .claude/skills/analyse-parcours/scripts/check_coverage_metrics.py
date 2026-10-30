#!/usr/bin/env python3
"""
Checks for coverage_metrics.py — does the fixed defect stay fixed?

The defect: the extension was tested on the full URL. A versioned URL
(dsfr.min.css?version=39.2.0) does not end with its extension, it fell into
"other", and a page whose URLs are ALL versioned was published at
zero KB of JS and CSS. Zero does not look like an error: it looks like a
codeless page. That is why this check exists.

Usage:
  python3 check_coverage_metrics.py [-v]
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coverage_metrics import (          # noqa: E402
    aggregate, analyze, classify, detect_libraries, measure, page_label, read_entries,
)

_checks = []


def check(label):
    def deco(fn):
        _checks.append((label, fn))
        return fn
    return deco


def _entry(url, text, used=0):
    """A Coverage entry: `used` bytes used from the start."""
    return {"url": url, "text": "x" * text,
            "ranges": ([{"start": 0, "end": used}] if used else [])}


# ── The fixed defect ──────────────────────────────────────────────────────────

@check("a versioned URL stays CSS")
def _():
    assert classify("https://h/a/dsfr.min.css?version=39.2.0") == "css"


@check("a versioned URL stays JS")
def _():
    assert classify("https://h/a/jquery-ui.min.js?version=39.2.0") == "javascript"


@check("a fragment does not hide the extension")
def _():
    assert classify("https://h/app.js#module") == "javascript"


@check("several parameters do not hide the extension")
def _():
    assert classify("https://h/s.css?v=1&theme=dark&x=.js") == "css"


@check("a redirect TO a .css is not CSS")
def _():
    # Negative case: without it, an overly permissive test would also pass.
    assert classify("https://h/redirect?target=/style.css") == "other"


@check("a URL without extension is neither JS nor CSS")
def _():
    assert classify("https://h/ihm-spd/csrfguard.action") == "other"


@check("a fully versioned page is NOT published at zero")
def _():
    entries = [_entry("https://h/a/dsfr.min.css?version=39.2.0", 4096, 1024),
               _entry("https://h/a/dsfr.module.min.js?version=39.2.0", 2048, 512)]
    res = measure(entries)
    assert aggregate(res, "css")["total_kb"] == 4.0
    assert aggregate(res, "javascript")["total_kb"] == 2.0


@check("the naive computation would indeed publish zero (the defect was real)")
def _():
    urls = ["https://h/a/dsfr.min.css?version=39.2.0",
            "https://h/a/dsfr.module.min.js?version=39.2.0"]
    assert not any(u.endswith((".css", ".js")) for u in urls)


# ── Measurement ───────────────────────────────────────────────────────────────

@check("unused bytes are total minus used")
def _():
    res = measure([_entry("https://h/a.js", 1000, 400)])
    assert res[0]["unused_bytes"] == 600


@check("a resource without a used range is counted 100% unused")
def _():
    res = measure([_entry("https://h/a.js", 1000)])
    assert res[0]["unused_bytes"] == 1000
    assert aggregate(res, "javascript")["unused_pct"] == 100.0


@check("an absent type gives zero, not a division by zero")
def _():
    assert aggregate(measure([_entry("https://h/a.js", 10)]), "css") == {
        "total_kb": 0.0, "unused_kb": 0.0, "unused_pct": 0.0}


@check("incomplete ranges are ignored without crashing")
def _():
    res = measure([{"url": "https://h/a.js", "text": "x" * 100,
                    "ranges": [{"start": 0}, {"end": 50}, {"start": 0, "end": 10}]}])
    assert res[0]["unused_bytes"] == 90


@check("ranges with null start/end are ignored without crashing")
def _():
    res = measure([{"url": "https://h/a.js", "text": "x" * 100,
                    "ranges": [{"start": None, "end": None}, {"start": 0, "end": 10}]}])
    assert res[0]["unused_bytes"] == 90


# ── Page label ────────────────────────────────────────────────────────────────

@check("the HAR arbitrates between two extensionless URLs")
def _():
    entries = [_entry("https://h/ihm-spd/csrfguard.action?version=1", 10),
               _entry("https://h/ihm-spd/pages/premotifdemandeform.action", 10)]
    url, prov = page_label(entries, {"https://h/ihm-spd/pages/premotifdemandeform.action"})
    assert url.endswith("premotifdemandeform.action"), url
    assert "HAR" in prov


@check("without the HAR, the label is marked as not corroborated")
def _():
    entries = [_entry("https://h/ihm-spd/csrfguard.action", 10)]
    url, prov = page_label(entries, set())
    assert url.endswith("csrfguard.action")
    assert "not confirmed" in prov


@check("no identifiable page URL is stated, not invented")
def _():
    url, prov = page_label([_entry("https://h/a.js", 10)], set())
    assert url == ""
    assert "no identifiable" in prov.lower()


@check("a majority third-party host does not become the page domain")
def _():
    # The main domain is the one carrying the most resources.
    entries = [_entry("https://cdn.tiers/a.js", 10), _entry("https://cdn.tiers/b.js", 10),
               _entry("https://cdn.tiers/c.js", 10), _entry("https://site/page", 10)]
    url, _ = page_label(entries, set())
    assert url == "", url  # no page URL on the majority domain


# ── Formats and refusals ──────────────────────────────────────────────────────

@check("the direct array format is read")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(json.dumps([_entry("https://h/a.js", 10)]), encoding="utf-8")
        entries, _measurement = read_entries(p)
        assert len(entries) == 1


@check("the wrapped format is read")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(json.dumps({"entries": [_entry("https://h/a.js", 10)]}), encoding="utf-8")
        entries, _measurement = read_entries(p)
        assert len(entries) == 1


@check("an unknown format is REFUSED, not read as empty")
def _():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(json.dumps({"coverage": []}), encoding="utf-8")
        entries, measurement = read_entries(p)
        assert entries is None
        assert "entries" in measurement["detail"]


@check("a folder without Coverage is REFUSED, not rendered empty")
def _():
    with tempfile.TemporaryDirectory() as d:
        try:
            analyze(d)
        except FileNotFoundError:
            return
        raise AssertionError("a folder without Coverage produced a result")


@check("a non-empty page without JS or CSS is FLAGGED")
def _():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Coverage-1.json").write_text(
            json.dumps([_entry("https://h/data.bin", 4096)]), encoding="utf-8")
        res = analyze(d)
        assert res["pages"][0]["no_js_no_css"] is True


@check("a normal page is not falsely flagged")
def _():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Coverage-1.json").write_text(
            json.dumps([_entry("https://h/a.css?v=2", 4096, 1024)]), encoding="utf-8")
        res = analyze(d)
        assert res["pages"][0]["no_js_no_css"] is False


# ── Libraries ─────────────────────────────────────────────────────────────────

@check("a library is named with its role")
def _():
    libs = detect_libraries([{"url": "https://swetrix.org/swetrix.js"}])
    assert libs == ["Swetrix (analytics)"], libs


@check("the versioned DSFR is recognized")
def _():
    libs = detect_libraries([{"url": "https://h/assets/dsfr/dsfr.min.css?version=39.2.0"}])
    assert any("DSFR" in x for x in libs), libs


@check("no known library gives an empty list, not an invention")
def _():
    assert detect_libraries([{"url": "https://h/assets/maison.js"}]) == []


# ── Output ────────────────────────────────────────────────────────────────────

@check("the output carries the keys expected by the report")
def _():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Coverage-1.json").write_text(
            json.dumps([_entry("https://h/a.js?v=1", 2048, 512)]), encoding="utf-8")
        res = analyze(d)
        for k in ("total_js_kb", "total_js_unused_kb", "total_css_kb",
                  "total_css_unused_kb", "third_party_libraries", "outlier_pages",
                  "pages_count"):
            assert k in res["summary"], k
        for k in ("name", "url", "url_provenance", "js_total_kb", "css_total_kb",
                  "top_js_unused", "top_css_unused", "source_file"):
            assert k in res["pages"][0], k


@check("the total is the sum of the pages, no byte lost")
def _():
    with tempfile.TemporaryDirectory() as d:
        for i in (1, 2):
            (Path(d) / f"Coverage-{i}.json").write_text(
                json.dumps([_entry(f"https://h/a{i}.js?v=1", 1024 * i, 256)]),
                encoding="utf-8")
        res = analyze(d)
        assert abs(res["summary"]["total_js_kb"]
                   - sum(p["js_total_kb"] for p in res["pages"])) < 0.11


@check("each page names its source file")
def _():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "Coverage-abc.json").write_text(
            json.dumps([_entry("https://h/a.js", 10)]), encoding="utf-8")
        assert analyze(d)["pages"][0]["source_file"] == "Coverage-abc.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    failures = []
    for label, fn in _checks:
        try:
            fn()
        except Exception as e:
            failures.append((label, e))
            print(f"[FAIL] {label}\n         {type(e).__name__}: {e}")
        else:
            if args.verbose:
                print(f"[ok] {label}")

    print("-" * 68)
    if failures:
        print(f"[FAIL] {len(failures)}/{len(_checks)} check(s) failed.")
        return 1
    print(f"[SUCCESS] {len(_checks)} checks. Versioned-URL typing holds.")
    print()
    print("Scope reminder: these checks cover CLASSIFICATION and the")
    print("LABEL, not the accuracy of the bytes reported by Chrome.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
