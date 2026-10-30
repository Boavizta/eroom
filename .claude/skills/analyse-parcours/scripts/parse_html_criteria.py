#!/usr/bin/env python3
"""
Static HTML + CSS parsing of already-audited pages, for deterministic EOF
criteria (autoplay, adaptive images, media queries, viewport...).

Assumed deviation from the initial plan: the .har captured for this project does
NOT contain HTML/CSS response bodies (verified on audits/octo.com:
46/311 entries with a body, none of them page HTML/CSS — DevTools capture
without "response bodies"). This script therefore re-fetches over HTTP the
SAME page URLs already listed in env-data.json (no new page), plus their
linked stylesheets — not a new audit scope, only a different data source for
the same scope.

The HTML is read with html.parser (standard library, no dependency),
NOT with regular expressions: see _HtmlFacts and autotest().

WORK ITEM 27 — archiving for reproducibility. The captured .har does not contain
response bodies (see above), so this script re-downloads live; but
re-downloading on EVERY run breaks reproducibility (two passes can give
different results if the site changed). Each fetched page/CSS is therefore
archived as-is under <source_dir>/html-pages/, with a deterministic file name
(see archive_filename()). By default, a run re-reads the existing archive
instead of making a new network request; --refresh forces a new download. A
future script (out of scope here) will be able to find the archived file from
a URL by calling archive_filename() itself, without ever having to
"reverse-engineer" a file name.

Usage:
    python3 parse_html_criteria.py <source_dir>
    python3 parse_html_criteria.py <source_dir> --refresh
    python3 parse_html_criteria.py --autotest

Writes <source_dir>/html-css-criteria.json and archives the fetched pages/CSS
under <source_dir>/html-pages/.
"""

import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; eof-audit-scan/1.0)"
MAX_CSS_PER_PAGE = 8
ARCHIVE_DIRNAME = "html-pages"


def archive_filename(url, is_css):
    """Deterministic archive file name for a URL.

    Essential property, exploited by a future script (work item 35): the
    SAME url ALWAYS gives the same name, and two different urls (even if they
    differ only by the query string) give different names.
    The slug makes the name readable (debugging), the SHA1 hash settles any
    ambiguity — including between two urls differing only by the query string,
    since the slug alone would ignore it.
    """
    parsed = urlparse(url)
    slug = (parsed.netloc + parsed.path).strip("/").replace("/", "_") or "index"
    slug = slug[:80]  # avoids absurdly long file names
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    ext = ".css" if is_css else ".html"
    return f"{slug}__{digest}{ext}"


def fetch_text(url):
    """Fetches the textual content of a URL via a direct network request.

    Returns a dict with:
    - content: str|None (content on success)
    - status: "ok" | "not_found" | "network_error" | "read_error"
    - error_detail: str|None (error description on failure)
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            try:
                content = resp.read().decode("utf-8", errors="replace")
                return {"content": content, "status": "ok", "error_detail": None}
            except Exception as exc:
                return {"content": None, "status": "read_error",
                        "error_detail": f"Decoding error: {type(exc).__name__}"}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"content": None, "status": "not_found",
                    "error_detail": f"HTTP {exc.code}"}
        return {"content": None, "status": "network_error",
                "error_detail": f"HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        return {"content": None, "status": "network_error",
                "error_detail": f"URLError: {exc.reason}"}
    except Exception as exc:
        return {"content": None, "status": "network_error",
                "error_detail": f"{type(exc).__name__}: {str(exc)}"}


def fetch_text_cached(url, source_dir, is_css, refresh=False):
    """Fetches the content of a URL via the local archive <source_dir>/html-pages/,
    falling back to the network — this is the function to call instead of
    fetch_text() wherever the result must be archived.

    Behavior:
    - --refresh active: ignores any existing archive, always downloads
      over the network.
    - Otherwise, if the archive file exists and reads correctly: return it
      as-is, status "ok", WITHOUT a network request.
    - Otherwise (archive absent, or present but unreadable/empty): download
      over the network like fetch_text(), then, ONLY on success, write
      (or rewrite) the archive. Assumed choice: a one-off network failure must
      never overwrite a good archive already on disk; only a success
      replaces it.
    """
    archive_dir = source_dir / ARCHIVE_DIRNAME
    archive_path = archive_dir / archive_filename(url, is_css)

    if not refresh and archive_path.exists():
        try:
            content = archive_path.read_text(encoding="utf-8")
            if not content:
                raise ValueError("empty archive file")
            return {"content": content, "status": "ok", "error_detail":
                    "read from the local archive (html-pages/), no network request"}
        except Exception as exc:
            print(f"  [parse_html] unreadable archive for {url} "
                  f"({archive_path.name}) : {type(exc).__name__}: {exc} "
                  f"— falling back to the network")
            # No return here: we fall through to the network fetch below.

    result = fetch_text(url)
    if result["status"] == "ok":
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path.write_text(result["content"], encoding="utf-8")
        except Exception as exc:
            print(f"  [parse_html] archive write failed for "
                  f"{url} : {type(exc).__name__}: {exc}")
    return result


def load_page_urls(source_dir):
    env_path = source_dir / "env-data.json"
    if not env_path.exists():
        return []
    env = json.loads(env_path.read_text(encoding="utf-8"))
    seen, urls = set(), []
    for p in env.get("pages", []):
        u = p.get("url")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


# ---------------------------------------------------------------------------
# HTML rules
# ---------------------------------------------------------------------------

class _HtmlFacts(HTMLParser):
    """Collects, in a single pass, the HTML facts the EOF criteria need.

    WHY a parser and not regular expressions. In HTML, attribute order means
    nothing, quotes are optional, case is free, an attribute value can contain
    a chevron, and an attribute can carry an entity (&amp;). A regular
    expression that assumes only one of these forms returns a FALSE result
    without raising an error: the count drops to zero, which is
    indistinguishable from a legitimate absence. Four defects of this kind
    really happened here, each is an autotest() case.

    Repeated attributes: the first one wins, like in a browser.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_autoplay_media = False
        self.img_count = 0
        self.img_with_srcset = 0
        self.picture_count = 0
        self.native_buttons = 0
        self.custom_role_buttons = 0
        self.viewport_content = None
        self.stylesheet_hrefs = []

    def handle_starttag(self, tag, attrs):
        names = {name.lower() for name, _ in attrs}
        values = {}
        for name, value in attrs:
            name = name.lower()
            if name not in values:
                values[name] = value if value is not None else ""

        if tag in ("video", "audio"):
            # "autoplay" must be a standalone attribute: neither data-autoplay,
            # nor a CSS class containing the word.
            if "autoplay" in names:
                self.has_autoplay_media = True
        elif tag == "img":
            self.img_count += 1
            if "srcset" in names:
                self.img_with_srcset += 1
        elif tag == "picture":
            self.picture_count += 1
        elif tag == "button":
            self.native_buttons += 1
        elif tag == "meta":
            if values.get("name", "").strip().lower() == "viewport":
                if self.viewport_content is None:
                    self.viewport_content = values.get("content")
        elif tag == "link":
            # rel is a list of space-separated words: rel="stylesheet
            # preload" IS a stylesheet, rel="preload" is not.
            if "stylesheet" in values.get("rel", "").lower().split():
                href = values.get("href", "").strip()
                if href:
                    self.stylesheet_hrefs.append(href)

        if values.get("role", "").strip().lower() == "button":
            self.custom_role_buttons += 1


# CSS: these two patterns look for a presence in CSS, not in HTML.
# Neither attribute order nor quotes involved, a regular expression is the
# right tool here.
_MEDIA_QUERY_RE = re.compile(r"@media\b", re.IGNORECASE)
_PREFERS_RE = re.compile(r"@media[^{]*prefers-(reduced-motion|color-scheme)", re.IGNORECASE)


def analyze_html(html, page_url):
    facts = _HtmlFacts()
    try:
        facts.feed(html)
        facts.close()
    except Exception as exc:
        # Interrupted reading: the facts collected so far are kept,
        # but the failure is SAID, it does not disguise itself as an absence of data.
        print(f"  [parse_html] interrupted HTML reading on {page_url} : {exc}")

    adaptive_img_ratio = None
    if facts.img_count:
        adaptive_img_ratio = round(
            (facts.img_with_srcset + facts.picture_count) / facts.img_count, 2)

    viewport_content = facts.viewport_content
    viewport_ok = bool(viewport_content
                       and "width=device-width" in viewport_content.lower())

    stylesheet_hrefs = facts.stylesheet_hrefs[:MAX_CSS_PER_PAGE]
    return {
        "url": page_url,
        "has_autoplay_media": facts.has_autoplay_media,
        "img_count": facts.img_count,
        "adaptive_img_ratio": adaptive_img_ratio,
        "native_buttons": facts.native_buttons,
        "custom_role_buttons": facts.custom_role_buttons,
        "viewport_content": viewport_content,
        "viewport_ok": viewport_ok,
        "stylesheet_urls": [urljoin(page_url, href) for href in stylesheet_hrefs],
    }


def analyze_css(css_texts):
    media_query_count = sum(len(_MEDIA_QUERY_RE.findall(css)) for css in css_texts)
    has_prefers = any(_PREFERS_RE.search(css) for css in css_texts)
    return {"media_query_count": media_query_count, "has_prefers_reduced_or_scheme": has_prefers}


# ---------------------------------------------------------------------------
# Autotest: each case is an HTML that a browser reads in a single way.
# A case marked "regression" is a construct that the regex version read
# WRONG, silently. Do not remove them.
# ---------------------------------------------------------------------------

_URL_TEST = "https://exemple.test/p/"
_A_CSS = "https://exemple.test/a.css"

CAS_AUTOTEST = [
    # --- stylesheet: feeds the downloaded CSS, hence criteria 1.6 and 1.11
    ("stylesheet, rel before href",
     '<link rel="stylesheet" href="/a.css">', "stylesheet_urls", [_A_CSS], False),
    ("stylesheet, REVERSE order href before rel",
     '<link href="/a.css" rel="stylesheet">', "stylesheet_urls", [_A_CSS], True),
    ("stylesheet, unquoted (minified page)",
     "<link rel=stylesheet href=/a.css>", "stylesheet_urls", [_A_CSS], True),
    ("stylesheet, href first and interleaved attribute",
     '<link href="/a.css" type="text/css" rel="stylesheet">',
     "stylesheet_urls", [_A_CSS], True),
    ("stylesheet, &amp; entity in the URL",
     '<link rel="stylesheet" href="/a.css?x=1&amp;y=2">',
     "stylesheet_urls", ["https://exemple.test/a.css?x=1&y=2"], True),
    ("stylesheet, uppercase",
     '<LINK REL="STYLESHEET" HREF="/a.css">', "stylesheet_urls", [_A_CSS], False),
    ("stylesheet, self-closing tag",
     '<link rel="stylesheet" href="/a.css" />', "stylesheet_urls", [_A_CSS], False),
    ("stylesheet, multi-word rel",
     '<link rel="stylesheet preload" href="/a.css">', "stylesheet_urls", [_A_CSS], False),
    ("rel=preload is NOT a stylesheet",
     '<link rel="preload" href="/a.css">', "stylesheet_urls", [], False),
    ("no stylesheet",
     "<html><body>nothing</body></html>", "stylesheet_urls", [], False),

    # --- autoplay: criterion 1.5, provenance "collected", hence shown as a measurement
    ("autoplay, bare attribute",
     "<video autoplay></video>", "has_autoplay_media", True, False),
    ("autoplay on audio",
     '<audio autoplay src="a.mp3"></audio>', "has_autoplay_media", True, False),
    ("data-autoplay is NOT autoplay",
     '<video data-autoplay="false"></video>', "has_autoplay_media", False, True),
    ("a CSS class named no-autoplay is NOT autoplay",
     '<video class="no-autoplay"></video>', "has_autoplay_media", False, True),
    ("autoplay after an attribute value containing a chevron",
     '<video title="a > b" autoplay></video>', "has_autoplay_media", True, True),
    ("video without autoplay",
     '<video src="a.mp4"></video>', "has_autoplay_media", False, False),

    # --- role=button: criterion 1.4
    ("role=button, double quotes",
     '<div role="button">x</div>', "custom_role_buttons", 1, False),
    ("role=button, unquoted (minified page)",
     "<div role=button>x</div>", "custom_role_buttons", 1, True),
    ("role=button, single quotes",
     "<div role='button'>x</div>", "custom_role_buttons", 1, False),
    ("role=button, spaces around the equals sign",
     '<div role = "button">x</div>', "custom_role_buttons", 1, True),
    ("role=buttonbar is NOT role=button",
     '<div role="buttonbar">x</div>', "custom_role_buttons", 0, False),
    ("role=button inside a comment does not count",
     '<!-- <div role="button"> --><p>x</p>', "custom_role_buttons", 0, True),
    ("native button",
     "<button>x</button>", "native_buttons", 1, False),

    # --- viewport: collected today, read by no criterion, fixed anyway
    ("viewport, name before content",
     '<meta name="viewport" content="width=device-width, initial-scale=1">',
     "viewport_ok", True, False),
    ("viewport, REVERSE order content before name",
     '<meta content="width=device-width" name="viewport">', "viewport_ok", True, True),
    ("viewport, unquoted name",
     '<meta name=viewport content="width=device-width">', "viewport_ok", True, False),
    ("viewport, uppercase in the value",
     '<meta name="VIEWPORT" content="WIDTH=DEVICE-WIDTH">', "viewport_ok", True, True),
    ("viewport absent",
     "<html><head></head></html>", "viewport_ok", False, False),

    # --- adaptive images: criterion 1.6
    ("img with srcset",
     '<img src="a.png" srcset="a.png 1x">', "adaptive_img_ratio", 1.0, False),
    ("img without srcset",
     '<img src="a.png">', "adaptive_img_ratio", 0.0, False),
    ("srcset after an attribute value containing a chevron",
     '<img alt="a > b" srcset="a.png 1x">', "adaptive_img_ratio", 1.0, True),
    ("no image",
     "<p>nothing</p>", "adaptive_img_ratio", None, False),
]


# ---------------------------------------------------------------------------
# Autotest — work item 27: archiving under html-pages/ for reproducibility.
# Each case is a no-argument function returning True if it passes. They use
# a temporary folder (never audits/*) and monkeypatch urllib.request.urlopen
# to prove the absence — or the presence — of a network call, without ever
# making a real one.
# ---------------------------------------------------------------------------

class _FakeNetworkResponse:
    """Fake HTTP response, just enough for the `with ... as resp: resp.read()`
    used by fetch_text()."""

    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self):
        return self._data


def _network_forbidden(*_args, **_kwargs):
    raise AssertionError("network called although the local archive existed")


def _test_naming_same_url_same_name():
    url = "https://exemple.test/a/b.css"
    return archive_filename(url, True) == archive_filename(url, True)


def _test_naming_query_string_distinguishes():
    a = archive_filename("https://exemple.test/a.css?x=1", True)
    b = archive_filename("https://exemple.test/a.css?x=2", True)
    return a != b


def _test_archive_read_without_network():
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp)
        url = "https://exemple.test/page-in-cache.html"
        archive_dir = source_dir / ARCHIVE_DIRNAME
        archive_dir.mkdir()
        archive_name = archive_filename(url, False)
        (archive_dir / archive_name).write_text("<html>from the archive</html>", encoding="utf-8")

        original = urllib.request.urlopen
        urllib.request.urlopen = _network_forbidden
        try:
            result = fetch_text_cached(url, source_dir, is_css=False, refresh=False)
        finally:
            urllib.request.urlopen = original

        return (result["status"] == "ok"
                and result["content"] == "<html>from the archive</html>"
                and "local archive" in (result["error_detail"] or ""))


def _test_refresh_forces_network():
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp)
        url = "https://exemple.test/page-to-refresh.html"
        archive_dir = source_dir / ARCHIVE_DIRNAME
        archive_dir.mkdir()
        archive_name = archive_filename(url, False)
        (archive_dir / archive_name).write_text("<html>old version</html>", encoding="utf-8")

        calls = []

        def _network_ok(*_args, **_kwargs):
            calls.append(1)
            return _FakeNetworkResponse(b"<html>fresh from the network</html>")

        original = urllib.request.urlopen
        urllib.request.urlopen = _network_ok
        try:
            result = fetch_text_cached(url, source_dir, is_css=False, refresh=True)
        finally:
            urllib.request.urlopen = original

        archive_content = (archive_dir / archive_name).read_text(encoding="utf-8")
        return (len(calls) == 1
                and result["content"] == "<html>fresh from the network</html>"
                and archive_content == "<html>fresh from the network</html>")


def _test_empty_archive_falls_back_to_network():
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp)
        url = "https://exemple.test/page-empty-archive.html"
        archive_dir = source_dir / ARCHIVE_DIRNAME
        archive_dir.mkdir()
        archive_name = archive_filename(url, False)
        (archive_dir / archive_name).write_text("", encoding="utf-8")  # empty archive = corrupted

        calls = []

        def _network_ok(*_args, **_kwargs):
            calls.append(1)
            return _FakeNetworkResponse(b"<html>repaired</html>")

        original = urllib.request.urlopen
        urllib.request.urlopen = _network_ok
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                result = fetch_text_cached(url, source_dir, is_css=False, refresh=False)
        finally:
            urllib.request.urlopen = original

        message_shown = "unreadable archive" in output.getvalue()
        rewritten_content = (archive_dir / archive_name).read_text(encoding="utf-8")
        return (len(calls) == 1
                and result["status"] == "ok"
                and result["content"] == "<html>repaired</html>"
                and message_shown
                and rewritten_content == "<html>repaired</html>")


def _test_undecodable_archive_falls_back_to_network():
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp)
        url = "https://exemple.test/page-undecodable-archive.html"
        archive_dir = source_dir / ARCHIVE_DIRNAME
        archive_dir.mkdir()
        archive_name = archive_filename(url, False)
        # Invalid bytes in strict UTF-8: causes a UnicodeDecodeError
        # on read, not just an empty content.
        (archive_dir / archive_name).write_bytes(b"\xff\xfe\x00garbage")

        calls = []

        def _network_ok(*_args, **_kwargs):
            calls.append(1)
            return _FakeNetworkResponse(b"<html>repaired 2</html>")

        original = urllib.request.urlopen
        urllib.request.urlopen = _network_ok
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                result = fetch_text_cached(url, source_dir, is_css=False, refresh=False)
        finally:
            urllib.request.urlopen = original

        message_shown = "unreadable archive" in output.getvalue()
        return (len(calls) == 1
                and result["status"] == "ok"
                and result["content"] == "<html>repaired 2</html>"
                and message_shown)


CAS_AUTOTEST_ARCHIVE = [
    ("naming: the same URL always gives the same name", _test_naming_same_url_same_name),
    ("naming: a different query string changes the name", _test_naming_query_string_distinguishes),
    ("archive present: read without a network request", _test_archive_read_without_network),
    ("--refresh: forces the network even if the archive exists", _test_refresh_forces_network),
    ("empty archive: message + network fallback + rewrite", _test_empty_archive_falls_back_to_network),
    ("undecodable archive: message + network fallback", _test_undecodable_archive_falls_back_to_network),
]


def autotest():
    failures = []
    fixed_count = 0
    for label, html, field, expected, regression in CAS_AUTOTEST:
        obtained = analyze_html(html, _URL_TEST).get(field)
        if obtained != expected:
            failures.append((label, field, expected, obtained))
        elif regression:
            fixed_count += 1

    for label, test_fn in CAS_AUTOTEST_ARCHIVE:
        try:
            ok = test_fn()
        except Exception as exc:
            ok = False
            label = f"{label} (exception: {type(exc).__name__}: {exc})"
        if not ok:
            failures.append((label, "archive", True, False))

    total = len(CAS_AUTOTEST) + len(CAS_AUTOTEST_ARCHIVE)
    if failures:
        print(f"AUTOTEST FAILED: {len(failures)} of {total} cases")
        for label, field, expected, obtained in failures:
            print(f"  - {label}")
            print(f"      {field} : expected {expected!r}, got {obtained!r}")
        return 1

    print(f"Autotest: {total} cases passed, including {fixed_count} HTML constructs "
          f"that the regex version misread.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Collects the HTML/CSS facts of the audited pages for the EOF criteria.")
    parser.add_argument("source_dir", nargs="?",
                        help="audit folder containing env-data.json")
    parser.add_argument("--autotest", action="store_true",
                        help="replays the embedded HTML reading cases and exits 1 if a case fails")
    parser.add_argument("--refresh", action="store_true",
                        help="ignores the local html-pages/ archive and re-downloads everything over the network")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())
    if not args.source_dir:
        parser.error("source_dir is required (or use --autotest)")
    source_dir = Path(args.source_dir).resolve()

    urls = load_page_urls(source_dir)
    if not urls:
        print(f"Error: no page found in {source_dir}/env-data.json.")
        sys.exit(1)

    pages_result = []
    stylesheets_failed = []
    all_css_texts = []
    for url in urls:
        fetch_result = fetch_text_cached(url, source_dir, is_css=False, refresh=args.refresh)
        if fetch_result["status"] != "ok":
            # Page not fetched: create an entry with a measurement block
            page_entry = {
                "url": url,
                "measurement": {
                    "status": fetch_result["status"],
                    "target": url,
                    "detail": fetch_result["error_detail"]
                }
            }
            pages_result.append(page_entry)
            print(f"  [parse_html] fetch failed for page: {url} — {fetch_result['status']}: {fetch_result['error_detail']}")
            continue

        # Page fetched: analyze it
        html = fetch_result["content"]
        page_data = analyze_html(html, url)
        # Add the measurement block to indicate success (detail specifies whether the
        # content came from the local archive or from a fresh network request)
        page_data["measurement"] = {
            "status": "ok",
            "target": url,
            "detail": fetch_result["error_detail"]
        }

        # Fetch the CSS
        for css_url in page_data["stylesheet_urls"]:
            css_result = fetch_text_cached(css_url, source_dir, is_css=True, refresh=args.refresh)
            if css_result["status"] == "ok":
                all_css_texts.append(css_result["content"])
            else:
                # CSS not fetched: trace the failure
                stylesheets_failed.append({
                    "url": css_url,
                    "source_page": url,
                    "measurement": {
                        "status": css_result["status"],
                        "target": f"stylesheet {css_url} (linked from {url})",
                        "detail": css_result["error_detail"]
                    }
                })
                print(f"  [parse_html] fetch failed for CSS: {css_url} — {css_result['status']}: {css_result['error_detail']}")

        pages_result.append(page_data)
        print(f"  [parse_html] {url} — autoplay={page_data['has_autoplay_media']} "
              f"adaptive_img_ratio={page_data['adaptive_img_ratio']} viewport_ok={page_data['viewport_ok']}")

    # Check how many pages were measured successfully
    pages_ok = [p for p in pages_result if p.get("measurement", {}).get("status") == "ok"]
    if not pages_ok:
        print("Warning: no page could be fetched successfully (network unavailable?). "
              "The failed entries will be traced in the output file.")

    css_result = analyze_css(all_css_texts)

    result = {
        "pages": pages_result,
        "css": css_result,
        "note": "HTML/CSS re-fetched live on the same URLs already listed in "
                "env-data.json (the captured .har does not contain the HTML/CSS "
                "response bodies) — no new page scope.",
    }

    if stylesheets_failed:
        result["stylesheets_failed"] = stylesheets_failed

    out_path = source_dir / "html-css-criteria.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"html-css-criteria.json written: {out_path}")


if __name__ == "__main__":
    main()
