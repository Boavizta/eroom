#!/usr/bin/env python3
"""
Scans three standard public files of the audited domain, via direct HTTP
request (plain fetch, no scraping, no authentication):
  - /.well-known/security.txt (RFC 9116)
  - /robots.txt
  - /sitemap.xml (declared in robots.txt, otherwise /sitemap.xml at the root)

Usage:
    python3 scan_wellknown.py <domain>          # e.g. octo.com
    python3 scan_wellknown.py <source_dir>       # domain inferred from env-data.json

Writes <source_dir>/wellknown-scan.json (if source_dir provided), otherwise prints the JSON.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; eof-audit-scan/1.0)"


def fetch(url):
    """Plain GET. Returns (status_code, text, error_detail).

    - HTTP success: (status_code, text, None)
    - HTTP error: (status_code, None, None)
    - Network/other error: (None, None, error_description)
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as e:
        return e.code, None, None
    except urllib.error.URLError as e:
        return None, None, f"URLError: {e.reason}"
    except Exception as e:
        return None, None, f"{type(e).__name__}: {str(e)}"


def _looks_like_html(text):
    """Detects a SPA catch-all fallback (status 200 but the app's HTML page,
    not the requested resource) — otherwise any SPA without the requested
    file would be falsely counted as "present". Verified under real conditions
    on octo.com: robots.txt AND sitemap.xml both return the SPA's index HTML
    with a 200 status."""
    head = text[:200].lstrip().lower()
    return head.startswith("<!doctype html") or head.startswith("<html")


def scan_security_txt(domain):
    """Scans security.txt at the two standard locations.

    Returns a dict with present (bool) and measurement (dict with status/target/detail).
    """
    paths = ("/.well-known/security.txt", "/security.txt")
    last_status, last_error = None, None

    for path in paths:
        url = f"https://{domain}{path}"
        status, text, error_detail = fetch(url)

        # Success case: 200 with valid content
        if status == 200 and text and not _looks_like_html(text):
            fields = ("contact:", "expires:")
            well_formed = all(f in text.lower() for f in fields)
            return {
                "present": True,
                "path": path,
                "well_formed": well_formed,
                "excerpt": text[:300],
                "measurement": {"status": "ok", "target": url, "detail": None}
            }

        # Remember the last result for the final failure report
        last_status = status
        last_error = error_detail

        # 200 but empty or HTML content: analysis failure
        if status == 200 and (not text or _looks_like_html(text)):
            return {
                "present": False,
                "measurement": {"status": "analysis_error", "target": url, "detail": "empty or HTML content"}
            }

    # Neither path succeeded: build the right failure status
    # Report the result of the second path tried (last one)
    url = f"https://{domain}{paths[-1]}"

    if last_status in (404, 410):
        return {
            "present": False,
            "measurement": {"status": "not_found", "target": url, "detail": f"HTTP {last_status}"}
        }
    elif last_status is not None:
        # Other HTTP code (403, 500, etc.)
        return {
            "present": False,
            "measurement": {"status": "network_error", "target": url, "detail": f"HTTP {last_status}"}
        }
    else:
        # No HTTP code at all: timeout, DNS, etc.
        return {
            "present": False,
            "measurement": {"status": "network_error", "target": url, "detail": last_error or "network error"}
        }


def scan_robots_txt(domain):
    """Scans robots.txt at the root.

    Returns a dict with present (bool), sitemap_urls (list) and measurement (dict).
    """
    url = f"https://{domain}/robots.txt"
    status, text, error_detail = fetch(url)

    # Success: 200 with valid content
    if status == 200 and text and not _looks_like_html(text):
        sitemap_urls = re.findall(r"(?im)^sitemap:\s*(\S+)", text)
        return {
            "present": True,
            "sitemap_urls": sitemap_urls,
            "measurement": {"status": "ok", "target": url, "detail": None}
        }

    # 200 but empty or HTML content: analysis failure
    if status == 200 and (not text or _looks_like_html(text)):
        return {
            "present": False,
            "measurement": {"status": "analysis_error", "target": url, "detail": "empty or HTML content"}
        }

    # 404 or 410: really absent
    if status in (404, 410):
        return {
            "present": False,
            "measurement": {"status": "not_found", "target": url, "detail": f"HTTP {status}"}
        }

    # Other HTTP code: network failure
    if status is not None:
        return {
            "present": False,
            "measurement": {"status": "network_error", "target": url, "detail": f"HTTP {status}"}
        }

    # No HTTP code at all: timeout, DNS, etc.
    return {
        "present": False,
        "measurement": {"status": "network_error", "target": url, "detail": error_detail or "network error"}
    }


def scan_sitemap(domain, sitemap_urls):
    """Scans sitemap.xml at the given URLs or /sitemap.xml by default.

    Returns a dict with present (bool), sitemap metadata if found,
    and measurement (dict with status/target/detail).
    """
    urls_to_try = sitemap_urls or [f"https://{domain}/sitemap.xml"]
    last_status, last_error = None, None

    for url in urls_to_try:
        status, text, error_detail = fetch(url)

        # Success: 200 with valid XML content
        if status == 200 and text and not _looks_like_html(text):
            url_count = len(re.findall(r"<loc>", text, re.IGNORECASE))
            lastmods = re.findall(r"<lastmod>([^<]+)</lastmod>", text, re.IGNORECASE)
            most_recent = max(lastmods) if lastmods else None
            days_ago = None
            if most_recent:
                try:
                    dt = datetime.fromisoformat(most_recent.replace("Z", "+00:00"))
                    days_ago = (datetime.now(timezone.utc) - dt).days
                except ValueError:
                    pass
            return {
                "present": True,
                "url": url,
                "url_count": url_count,
                "most_recent_lastmod": most_recent,
                "days_since_lastmod": days_ago,
                "measurement": {"status": "ok", "target": url, "detail": None}
            }

        # Remember the last result
        last_status = status
        last_error = error_detail

        # 200 but empty or HTML content: analysis failure
        if status == 200 and (not text or _looks_like_html(text)):
            return {
                "present": False,
                "measurement": {"status": "analysis_error", "target": url, "detail": "empty or HTML content"}
            }

    # No URL succeeded: build the right failure status
    # Report the result of the last URL tried
    url = urls_to_try[-1]

    if last_status in (404, 410):
        return {
            "present": False,
            "measurement": {"status": "not_found", "target": url, "detail": f"HTTP {last_status}"}
        }
    elif last_status is not None:
        # Other HTTP code
        return {
            "present": False,
            "measurement": {"status": "network_error", "target": url, "detail": f"HTTP {last_status}"}
        }
    else:
        # No HTTP code at all: timeout, DNS, etc.
        return {
            "present": False,
            "measurement": {"status": "network_error", "target": url, "detail": last_error or "network error"}
        }


def scan(domain):
    """Scans the three standard public files."""
    security_txt = scan_security_txt(domain)
    robots = scan_robots_txt(domain)
    sitemap = scan_sitemap(domain, robots.get("sitemap_urls"))

    return {
        "domain": domain,
        "security_txt": security_txt,
        "robots_txt": robots,
        "sitemap": sitemap,
        "note": "Direct public fetch (no authentication), no call beyond these "
                "2-3 HTTP requests per domain.",
    }


def infer_domain(source_dir):
    env_path = source_dir / "env-data.json"
    if not env_path.exists():
        return None
    env = json.loads(env_path.read_text(encoding="utf-8"))
    pages = env.get("pages") or []
    if not pages:
        return None
    from urllib.parse import urlparse
    return urlparse(pages[0]["url"]).netloc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="Domain (e.g. octo.com) or audit folder (env-data.json)")
    args = parser.parse_args()

    target_path = Path(args.target)
    source_dir = None
    if target_path.exists() and target_path.is_dir():
        source_dir = target_path.resolve()
        domain = infer_domain(source_dir)
        if not domain:
            print(f"Error: cannot infer the domain from {source_dir}/env-data.json.")
            sys.exit(1)
    else:
        domain = args.target

    print(f"[scan_wellknown] Domain: {domain}")
    result = scan(domain)

    if source_dir:
        out_path = source_dir / "wellknown-scan.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wellknown-scan.json written: {out_path}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    print(f"  security.txt : {'present' if result['security_txt']['present'] else 'absent'}")
    print(f"  robots.txt   : {'present' if result['robots_txt']['present'] else 'absent'}")
    print(f"  sitemap.xml  : {'present' if result['sitemap']['present'] else 'absent'}"
          + (f" ({result['sitemap'].get('url_count')} URLs)" if result["sitemap"]["present"] else ""))

    # Warning if measurement failures are present (computed on the fly)
    failures = []
    for name, res in [("security.txt", result["security_txt"]), ("robots.txt", result["robots_txt"]), ("sitemap", result["sitemap"])]:
        status = res.get("measurement", {}).get("status")
        if status in ("network_error", "read_error", "analysis_error"):
            detail = res["measurement"].get("detail", "")
            failures.append(f"{name}: {status} ({detail})")

    if failures:
        print("\n⚠️  MEASUREMENT FAILURES DETECTED:")
        for failure in failures:
            print(f"  - {failure}")


if __name__ == "__main__":
    main()
