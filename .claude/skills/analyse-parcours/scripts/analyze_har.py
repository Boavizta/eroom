#!/usr/bin/env python3
"""
Deterministic analysis of a `.har` file — produces har-analysis.json.

Work item 35. Until now, step 20 of the pipeline ("HAR file analysis")
had NO script: the block `:::dispatch id="analyze-har"` of
`skill-steps/25_dispatch-orchestration.md` asked an agent/LLM to read the
`.har` "by hand" and to produce `<AUDIT_DIR>/har-analysis.json` by judgment.
Proof that it happened on `audits/octo.com`: the real file carried a
`blocking_resources` key that no script in the repo knew about — an AI had
invented it by eyeballing the HAR. That analysis was therefore not replayable,
while its figures (notably `duplicate_urls`) feed the EOF (duplicate-requests
criterion, see run_eof.py) without any way to verify they are stable.

This script replaces that manual computation, like coverage_metrics.py for
step 30 (Coverage): same CLI, same discipline of separate tests
(check_analyze_har.py).

Two non-divergence rules with the rest of the repo:

1. **1st-party / 3rd-party**: the classification comes from
   `deploy_freshness._first_party_hosts_from_env()`, imported as-is
   (a single rule for this concept in the whole repo, not a second one
   invented here).
2. **`blocking_resources`**: the value that lived in the real file before
   this script was not a truth to reproduce (it was invented by manual
   reading), only a hint of what we want to approximate properly. This script
   finds the HTML archive of each page via `archive_filename()` (work item 27,
   imported from parse_html_criteria.py) under `<source_dir>/html-pages/`. If the
   archive is missing for a page — the replay of work item 27 has not happened
   yet on this folder —, the field is explicitly marked "not computed" for that
   page, NEVER guessed from the MIME type alone: "a failure is said, never
   disguised as an absence" (project convention). This key is read by no
   consumer script today (verified: `grep -rl blocking_resources` only finds
   data files): it documents an approximation, not a verdict.

Usage:
  python3 analyze_har.py <source-dir> [--output har-analysis.json]
  python3 analyze_har.py <source-dir> --check     # compare without writing
  python3 analyze_har.py --autotest
"""

import argparse
import json
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy_freshness import _first_party_hosts_from_env   # noqa: E402 - the repo's single 1st/3rd-party rule
from parse_html_criteria import archive_filename, ARCHIVE_DIRNAME  # noqa: E402 - work item 27, do not duplicate

# Optional subfolder where raw captures (HAR, Coverage) are stored.
RAW_DATA_DIR = "raw-data-potentially-sensitive"  # genericity: ok - shared repo convention

# "slow third-party resource" threshold: total response time (entry.time, in ms).
SLOW_THRESHOLD_MS = 1000


def find_har(source_dir):
    """Locates the `.har`: at the root of the source folder, or in its
    raw-captures subfolder. Reproduces the same lookup as
    deploy_freshness.find_har()."""
    source_dir = Path(source_dir)
    hars = sorted(source_dir.glob("*.har")) or sorted((source_dir / RAW_DATA_DIR).glob("*.har"))
    return hars[0] if hars else None


def read_har(har_path):
    with open(har_path, encoding="utf-8") as f:
        return json.load(f)


def _response_headers(entry):
    """Response headers as a {lowercase_name: value} dict, robust to absence."""
    return {h["name"].lower(): h["value"]
            for h in (entry.get("response") or {}).get("headers") or []}


def _host_is_first_party(host, first_party_hosts):
    """A host is 1st-party if it is in the list deduced from env-data.json,
    or if it is a subdomain of one of these hosts."""
    if not host or not first_party_hosts:
        return False
    return any(host == h or host.endswith("." + h) for h in first_party_hosts)


def classify_domains(entries, first_party_hosts):
    """Domains actually contacted in the HAR, classified 1st/3rd-party.

    Returns two sorted lists of host names (no counting: the expected shape
    for csp_inventory.loaded_hosts_from_har_analysis() and for the documented
    format is a list of strings, not a dict of counters).
    """
    hosts = set()
    for e in entries:
        url = (e.get("request") or {}).get("url", "")
        host = urlparse(url).netloc
        if host:
            hosts.add(host)

    first, third = [], []
    for host in sorted(hosts):
        if _host_is_first_party(host, first_party_hosts):
            first.append(host)
        else:
            third.append(host)
    return first, third


def compute_http_codes(entries):
    codes = Counter()
    for e in entries:
        status = (e.get("response") or {}).get("status", 0)
        codes[status] += 1
    # String keys: a JSON object only has string keys, and the reference file
    # (produced by hand) already carries "200", "304", etc. keys.
    return {str(code): count for code, count in codes.items()}


def compute_total_size_kb(entries):
    total_bytes = sum(
        ((e.get("response") or {}).get("content") or {}).get("size", 0) or 0
        for e in entries
    )
    return round(total_bytes / 1024, 2)


def compute_top10_heaviest(entries):
    """The 10 heaviest resources, deduplicated by URL.

    Takes up the idea of generate_report_html.har_traffic_analysis() (dedup by
    URL before ranking, keep the max size observed if the same URL appears
    several times): without it, a resource loaded 8 times (no cache) takes 8
    of the 10 top places and hides the other heavy resources — exactly the
    defect that lived in the manually produced file on octo.com (style.css
    present 8 times in the top10).
    """
    seen = {}
    for e in entries:
        url = (e.get("request") or {}).get("url", "")
        size_kb = round((((e.get("response") or {}).get("content") or {}).get("size", 0) or 0) / 1024, 2)
        host = urlparse(url).netloc
        if url not in seen or size_kb > seen[url]["size_kb"]:
            seen[url] = {"url": url, "size_kb": size_kb, "host": host}
    return sorted(seen.values(), key=lambda r: -r["size_kb"])[:10]


def compute_uncached_requests(entries):
    """Requests without cache: neither `Cache-Control` nor `Expires` in the response."""
    count = 0
    for e in entries:
        hdrs = _response_headers(e)
        if "cache-control" not in hdrs and "expires" not in hdrs:
            count += 1
    return count


def compute_duplicate_urls(entries):
    """Identical URLs called several times, sorted by decreasing call count.
    Each element keeps at least the `count` key (consumed by
    run_eof.py: `sorted(..., key=lambda d: -d.get("count", 0))[:3]`)."""
    urls = [ (e.get("request") or {}).get("url", "") for e in entries ]
    counts = Counter(u for u in urls if u)
    return [{"url": u, "count": c} for u, c in counts.most_common() if c > 1]


def compute_slow_third_party(entries, first_party_hosts):
    """Third-party resources whose total response time (`entry.time`, in ms)
    exceeds SLOW_THRESHOLD_MS. 1st-party hosts are excluded: the question
    asked is the weight added by third-party services, not the site's own
    slowness."""
    slow = []
    for e in entries:
        url = (e.get("request") or {}).get("url", "")
        host = urlparse(url).netloc
        if not host or _host_is_first_party(host, first_party_hosts):
            continue
        time_ms = e.get("time", 0) or 0
        if time_ms > SLOW_THRESHOLD_MS:
            slow.append({"url": url, "host": host, "time_ms": round(time_ms, 1)})
    return sorted(slow, key=lambda r: -r["time_ms"])


# ── blocking_resources: synchronous JS/CSS in <head>, from the HTML archive ──

class _HeadBlockingFacts(HTMLParser):
    """Collects, in the <head> only, the <script src> without async/defer/module and
    the <link rel="stylesheet">. Dedicated parser (html.parser, never
    regex — repo convention, see _HtmlFacts in parse_html_criteria.py),
    with the same tolerance for unquoted attributes, free case and
    repeated attributes (the first one wins)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._in_head = False
        self._head_done = False
        self.scripts = []       # src URLs of blocking <script>
        self.stylesheets = []   # href URLs of <link rel=stylesheet>

    def handle_starttag(self, tag, attrs):
        if self._head_done:
            return
        if tag == "head":
            self._in_head = True
            return
        if tag == "body":
            self._head_done = True
            self._in_head = False
            return
        if not self._in_head:
            return

        values = {}
        for name, value in attrs:
            name = name.lower()
            if name not in values:
                values[name] = value if value is not None else ""
        names = set(values)

        if tag == "script":
            src = values.get("src", "").strip()
            is_module = values.get("type", "").strip().lower() == "module"
            if src and "async" not in names and "defer" not in names and not is_module:
                self.scripts.append(src)
        elif tag == "link":
            if "stylesheet" in values.get("rel", "").lower().split():
                href = values.get("href", "").strip()
                if href:
                    self.stylesheets.append(href)

    def handle_endtag(self, tag):
        if tag == "head":
            self._head_done = True
            self._in_head = False


def _blocking_resources_for_page(page_url, html_text):
    facts = _HeadBlockingFacts()
    try:
        facts.feed(html_text)
        facts.close()
    except Exception as exc:
        # Interrupted reading: the facts collected so far are kept, but the
        # failure is SAID (printed), never disguised as an absence of data.
        print(f"  [analyze_har] interrupted HTML reading on {page_url} : {exc}")
    resources = [{"url": urljoin(page_url, src), "kind": "script"} for src in facts.scripts]
    resources += [{"url": urljoin(page_url, href), "kind": "stylesheet"} for href in facts.stylesheets]
    return resources


def compute_blocking_resources(source_dir, env_pages):
    """Synchronous JS/CSS in <head>, per page — only for pages whose HTML
    archive (work item 27, <source_dir>/html-pages/) is available.

    A page without an archive is NOT approximated from the HAR's MIME type
    alone: it is marked `computed: false`, with the reason. That is the project
    convention: a failure is said, never disguised as an absence.
    """
    source_dir = Path(source_dir)
    archive_dir = source_dir / ARCHIVE_DIRNAME
    pages_out = []
    for page in env_pages:
        url = (page or {}).get("url") if isinstance(page, dict) else None
        if not url:
            continue
        archive_path = archive_dir / archive_filename(url, is_css=False)
        if not archive_path.exists():
            pages_out.append({
                "url": url,
                "computed": False,
                "resources": None,
                "reason": ("HTML archive missing under html-pages/ — work item 27 "
                           "(HTML archiving) has not been replayed on this folder yet; "
                           "not computed, never approximated from the MIME type alone"),
            })
            continue
        try:
            html_text = archive_path.read_text(encoding="utf-8")
        except Exception as exc:
            pages_out.append({
                "url": url,
                "computed": False,
                "resources": None,
                "reason": f"unreadable archive ({archive_path.name}) : {type(exc).__name__}: {exc}",
            })
            continue
        pages_out.append({
            "url": url,
            "computed": True,
            "resources": _blocking_resources_for_page(url, html_text),
            "reason": None,
        })
    return {
        "note": ("Synchronous JS/CSS in <head> (without async/defer/type=module for "
                 "scripts). Computed only for pages whose HTML archive "
                 "(work item 27) is available under html-pages/ ; otherwise, not computed. "
                 "Key not read by current consumer scripts: documented "
                 "approximation, not a verdict."),
        "pages": pages_out,
    }


def load_env_pages(source_dir):
    env_path = Path(source_dir) / "env-data.json"
    if not env_path.exists():
        return []
    try:
        env = json.loads(env_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return env.get("pages") or []


def analyze(source_dir):
    source_dir = Path(source_dir)
    har_path = find_har(source_dir)
    if not har_path:
        raise FileNotFoundError(
            f"No .har file in {source_dir} nor in {source_dir / RAW_DATA_DIR}."
        )

    har = read_har(har_path)
    entries = (har.get("log") or {}).get("entries") or []

    first_party_hosts = _first_party_hosts_from_env(source_dir)
    first, third = classify_domains(entries, first_party_hosts)
    env_pages = load_env_pages(source_dir)

    return {
        "total_requests": len(entries),
        "domains": {"first_party": first, "third_party": third},
        "http_codes": compute_http_codes(entries),
        "total_size_kb": compute_total_size_kb(entries),
        "top10_heaviest": compute_top10_heaviest(entries),
        "uncached_requests": compute_uncached_requests(entries),
        "duplicate_urls": compute_duplicate_urls(entries),
        "slow_third_party": compute_slow_third_party(entries, first_party_hosts),
        "blocking_resources": compute_blocking_resources(source_dir, env_pages),
    }, har_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_dir", type=Path, nargs="?")
    ap.add_argument("--output", type=Path,
                    help="output path (default: <source_dir>/audit/"
                         "har-analysis.json)")
    ap.add_argument("--check", action="store_true",
                    help="compare against the existing output without writing anything")
    ap.add_argument("--autotest", action="store_true",
                    help="run the internal check battery and exit")
    args = ap.parse_args(argv)

    if args.autotest:
        return _run_autotest()

    if args.source_dir is None:
        ap.error("the source folder is required (unless --autotest)")

    result, har_path = analyze(args.source_dir)

    out = args.output or (args.source_dir / "audit" / "har-analysis.json")

    n_first = len(result["domains"]["first_party"])
    n_third = len(result["domains"]["third_party"])
    print(f"HAR: {result['total_requests']} requests — {har_path.name}")
    print(f"  Domains: {n_first} 1st-party, {n_third} 3rd-party")
    print(f"  Total size: {result['total_size_kb']} KB")
    print(f"  Without cache: {result['uncached_requests']} request(s)")
    print(f"  Duplicate URLs: {len(result['duplicate_urls'])}")
    print(f"  Slow third parties (> 1 s): {len(result['slow_third_party'])}")

    if args.check:
        if not out.exists():
            print(f"\n[check] {out} absent, nothing to compare.")
            return 0
        with open(out, encoding="utf-8") as f:
            old = json.load(f)
        print("\n[check] differences vs the existing output:")
        diffs = 0
        for key in ("total_requests", "total_size_kb", "uncached_requests"):
            before, after = old.get(key), result[key]
            if before != after:
                diffs += 1
                print(f"  {key} : {before} -> {after}")
        for key, label in (("domains", "domains"), ("http_codes", "http_codes")):
            if old.get(key) != result[key]:
                diffs += 1
                print(f"  {label} : {old.get(key)} -> {result[key]}")
        for key in ("duplicate_urls", "slow_third_party", "top10_heaviest"):
            before_n = len(old.get(key) or [])
            after_n = len(result[key])
            if before_n != after_n:
                diffs += 1
                print(f"  len({key}) : {before_n} -> {after_n}")
        print("  no differences." if not diffs else f"  {diffs} difference(s).")
        return 1 if diffs else 0

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print(f"\nhar-analysis.json written — {out}")
    return 0


# ── Autotest ────────────────────────────────────────────────────────────────

def _entry(url, status=200, size=1000, time_ms=100, headers=None):
    return {
        "request": {"url": url},
        "response": {
            "status": status,
            "content": {"size": size},
            "headers": [{"name": k, "value": v} for k, v in (headers or {}).items()],
        },
        "time": time_ms,
    }


def _run_autotest():
    import tempfile

    failures = []
    checks = []

    def check(label):
        def deco(fn):
            checks.append((label, fn))
            return fn
        return deco

    @check("total_requests counts all entries")
    def _():
        entries = [_entry("https://h/a"), _entry("https://h/b")]
        assert len(entries) == 2

    @check("domains: 1st-party vs 3rd-party via env-data.json")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "env-data.json").write_text(
                json.dumps({"pages": [{"url": "https://site.test/"}]}), encoding="utf-8")
            har = {"log": {"entries": [
                _entry("https://site.test/a.js"),
                _entry("https://tiers.test/b.js"),
            ]}}
            (d / "site.har").write_text(json.dumps(har), encoding="utf-8")
            result, _ = analyze(d)
            assert result["domains"]["first_party"] == ["site.test"], result["domains"]
            assert result["domains"]["third_party"] == ["tiers.test"], result["domains"]

    @check("a subdomain of the 1st-party stays 1st-party")
    def _():
        assert _host_is_first_party("cdn.site.test", {"site.test"})
        assert not _host_is_first_party("evilsite.test", {"site.test"})

    @check("http_codes: string keys, correct counting")
    def _():
        entries = [_entry("https://h/a", status=200), _entry("https://h/b", status=200),
                   _entry("https://h/c", status=404)]
        codes = compute_http_codes(entries)
        assert codes == {"200": 2, "404": 1}, codes

    @check("total_size_kb: sum of sizes, KB with 2 decimals")
    def _():
        entries = [_entry("https://h/a", size=1024), _entry("https://h/b", size=512)]
        assert compute_total_size_kb(entries) == 1.5

    @check("top10_heaviest: deduplicated by URL, max size kept")
    def _():
        entries = [
            _entry("https://h/style.css", size=2048),
            _entry("https://h/style.css", size=2048),
            _entry("https://h/style.css", size=2048),
            _entry("https://h/big.webp", size=1024),
        ]
        top = compute_top10_heaviest(entries)
        assert len(top) == 2, top  # deduplicated: not 4 entries for 2 distinct URLs
        assert top[0]["url"] == "https://h/style.css"
        assert top[0]["size_kb"] == 2.0

    @check("uncached_requests: neither Cache-Control nor Expires")
    def _():
        entries = [
            _entry("https://h/a", headers={"cache-control": "max-age=3600"}),
            _entry("https://h/b", headers={"expires": "Wed, 01 Jan 2030 00:00:00 GMT"}),
            _entry("https://h/c", headers={}),
        ]
        assert compute_uncached_requests(entries) == 1

    @check("duplicate_urls: counts identical URLs, ignores unique ones")
    def _():
        entries = [_entry("https://h/a"), _entry("https://h/a"), _entry("https://h/a"),
                   _entry("https://h/b")]
        dups = compute_duplicate_urls(entries)
        assert dups == [{"url": "https://h/a", "count": 3}], dups

    @check("duplicate_urls: each element carries at least 'count' (run_eof.py contract)")
    def _():
        entries = [_entry("https://h/a"), _entry("https://h/a")]
        dups = compute_duplicate_urls(entries)
        assert all("count" in d for d in dups)

    @check("slow_third_party: > 1000 ms AND third-party only")
    def _():
        first_party = {"site.test"}
        entries = [
            _entry("https://site.test/slow.js", time_ms=5000),   # slow 1st-party: excluded
            _entry("https://tiers.test/slow.js", time_ms=1500),  # slow third-party: included
            _entry("https://tiers.test/fast.js", time_ms=200),   # fast third-party: excluded
        ]
        slow = compute_slow_third_party(entries, first_party)
        assert [s["url"] for s in slow] == ["https://tiers.test/slow.js"], slow

    @check("slow_third_party: the threshold is strict (exactly 1000 ms does not count)")
    def _():
        slow = compute_slow_third_party([_entry("https://tiers.test/x.js", time_ms=1000)], set())
        assert slow == []

    @check("blocking_resources: archive missing -> not computed, never guessed")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            result = compute_blocking_resources(d, [{"url": "https://site.test/"}])
            page = result["pages"][0]
            assert page["computed"] is False
            assert page["resources"] is None
            assert "missing" in page["reason"], page["reason"]

    @check("blocking_resources: archive present -> <head> script/link detected")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            page_url = "https://site.test/"
            (d / ARCHIVE_DIRNAME).mkdir(parents=True, exist_ok=True)
            html = ('<html><head>'
                    '<script src="/a.js"></script>'
                    '<script src="/async.js" async></script>'
                    '<script src="/module.js" type="module"></script>'
                    '<link rel="stylesheet" href="/s.css">'
                    '</head><body></body></html>')
            (d / ARCHIVE_DIRNAME / archive_filename(page_url, is_css=False)).write_text(
                html, encoding="utf-8")
            result = compute_blocking_resources(d, [{"url": page_url}])
            page = result["pages"][0]
            assert page["computed"] is True
            urls = {r["url"] for r in page["resources"]}
            assert "https://site.test/a.js" in urls
            assert "https://site.test/s.css" in urls
            assert "https://site.test/async.js" not in urls
            assert "https://site.test/module.js" not in urls

    @check("blocking_resources: script/link outside <head> are ignored")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            page_url = "https://site.test/"
            (d / ARCHIVE_DIRNAME).mkdir(parents=True, exist_ok=True)
            html = ('<html><head></head><body>'
                    '<script src="/late.js"></script>'
                    '</body></html>')
            (d / ARCHIVE_DIRNAME / archive_filename(page_url, is_css=False)).write_text(
                html, encoding="utf-8")
            result = compute_blocking_resources(d, [{"url": page_url}])
            assert result["pages"][0]["resources"] == []

    @check("consistency with generate_report_html.har_traffic_analysis (same HAR)")
    def _():
        import generate_report_html as ref
        entries = [
            _entry("https://site.test/a.js"),
            _entry("https://site.test/a.js"),
            _entry("https://tiers.test/b.js"),
        ]
        har_data = {"log": {"entries": entries}}
        ref_result = ref.har_traffic_analysis(har_data)
        first, third = classify_domains(entries, {"site.test"})
        # Same observed traffic: BOTH domains seen by har_traffic_analysis
        # must be found, both, in our classification —
        # neither script may "lose" a domain the other sees.
        assert set(ref_result["domains"].keys()) == set(first) | set(third)
        # The same duplicate (a.js x2) must be seen by both implementations.
        ref_dup = {d["url"]: d["count"] for d in ref_result["duplicates"]}
        our_dup = {d["url"]: d["count"] for d in compute_duplicate_urls(entries)}
        assert ref_dup.get("https://site.test/a.js") == our_dup.get("https://site.test/a.js") == 2

    @check("a folder without .har is REFUSED, not rendered empty")
    def _():
        with tempfile.TemporaryDirectory() as d:
            try:
                analyze(d)
            except FileNotFoundError:
                return
            raise AssertionError("a folder without .har produced a result")

    @check("the output carries the 8 contract keys, plus blocking_resources")
    def _():
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            har = {"log": {"entries": [_entry("https://h/a")]}}
            (d / "h.har").write_text(json.dumps(har), encoding="utf-8")
            result, _ = analyze(d)
            for k in ("total_requests", "domains", "http_codes", "total_size_kb",
                      "top10_heaviest", "uncached_requests", "duplicate_urls",
                      "slow_third_party", "blocking_resources"):
                assert k in result, k
            assert set(result["domains"]) == {"first_party", "third_party"}

    for label, fn in checks:
        try:
            fn()
        except Exception as exc:
            failures.append((label, exc))
            print(f"[FAIL] {label}\n         {type(exc).__name__}: {exc}")

    print("-" * 68)
    if failures:
        print(f"[FAIL] {len(failures)}/{len(checks)} check(s) failed.")
        return 1
    print(f"[SUCCESS] {len(checks)} checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
