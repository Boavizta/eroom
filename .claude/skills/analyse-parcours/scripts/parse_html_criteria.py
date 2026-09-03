#!/usr/bin/env python3
"""
Parsing HTML + CSS statique des pages déjà auditées, pour des critères EOF
déterministes (autoplay, images adaptatives, media queries, viewport...).

Écart assumé par rapport au plan initial : le .har capturé pour ce projet ne
contient PAS les corps de réponse HTML/CSS (vérifié sur audits/octo.com :
46/311 entrées avec un body, aucune n'étant du HTML/CSS de page — capture
DevTools sans "response bodies"). Ce script refait donc un fetch HTTP direct
des MÊMES URLs de pages déjà listées dans env-data.json (aucune page
nouvelle), plus leurs feuilles de style liées — pas un nouveau périmètre
d'audit, seulement une source de donnée différente pour le même périmètre.

Usage :
    python3 parse_html_criteria.py <source_dir>

Écrit <source_dir>/html-css-criteria.json.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; eof-audit-scan/1.0)"
MAX_CSS_PER_PAGE = 8


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


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
# Règles HTML
# ---------------------------------------------------------------------------

_AUTOPLAY_RE = re.compile(r"<(video|audio)\b[^>]*\bautoplay\b[^>]*>", re.IGNORECASE)
_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_PICTURE_RE = re.compile(r"<picture\b", re.IGNORECASE)
_BUTTON_RE = re.compile(r"<button\b", re.IGNORECASE)
_DIV_ROLE_BUTTON_RE = re.compile(r"role=[\"']button[\"']", re.IGNORECASE)
_VIEWPORT_RE = re.compile(
    r"<meta\s+name=[\"']?viewport[\"']?\s+content=[\"']([^\"']+)[\"']", re.IGNORECASE)
_STYLESHEET_LINK_RE = re.compile(
    r"<link\b[^>]*\brel=[\"']?stylesheet[\"']?[^>]*\bhref=[\"']([^\"']+)[\"']", re.IGNORECASE)
_MEDIA_QUERY_RE = re.compile(r"@media\b", re.IGNORECASE)
_PREFERS_RE = re.compile(r"@media[^{]*prefers-(reduced-motion|color-scheme)", re.IGNORECASE)


def analyze_html(html, page_url):
    has_autoplay = bool(_AUTOPLAY_RE.search(html))
    imgs = _IMG_RE.findall(html)
    srcset_count = sum(1 for tag in imgs if re.search(r"\bsrcset=", tag, re.IGNORECASE))
    picture_count = len(_PICTURE_RE.findall(html))
    adaptive_img_ratio = None
    if imgs:
        adaptive_img_ratio = round((srcset_count + picture_count) / len(imgs), 2)
    native_buttons = len(_BUTTON_RE.findall(html))
    custom_buttons = len(_DIV_ROLE_BUTTON_RE.findall(html))
    viewport_match = _VIEWPORT_RE.search(html)
    viewport_ok = bool(viewport_match and "width=device-width" in viewport_match.group(1))
    stylesheet_hrefs = _STYLESHEET_LINK_RE.findall(html)[:MAX_CSS_PER_PAGE]
    stylesheet_urls = [urljoin(page_url, href) for href in stylesheet_hrefs]
    return {
        "url": page_url,
        "has_autoplay_media": has_autoplay,
        "img_count": len(imgs),
        "adaptive_img_ratio": adaptive_img_ratio,
        "native_buttons": native_buttons,
        "custom_role_buttons": custom_buttons,
        "viewport_content": viewport_match.group(1) if viewport_match else None,
        "viewport_ok": viewport_ok,
        "stylesheet_urls": stylesheet_urls,
    }


def analyze_css(css_texts):
    media_query_count = sum(len(_MEDIA_QUERY_RE.findall(css)) for css in css_texts)
    has_prefers = any(_PREFERS_RE.search(css) for css in css_texts)
    return {"media_query_count": media_query_count, "has_prefers_reduced_or_scheme": has_prefers}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir")
    args = parser.parse_args()
    source_dir = Path(args.source_dir).resolve()

    urls = load_page_urls(source_dir)
    if not urls:
        print(f"Erreur : aucune page trouvée dans {source_dir}/env-data.json.")
        sys.exit(1)

    pages_result = []
    all_css_texts = []
    for url in urls:
        html = fetch_text(url)
        if html is None:
            print(f"  [parse_html] échec fetch : {url}")
            continue
        page_data = analyze_html(html, url)
        css_texts = []
        for css_url in page_data["stylesheet_urls"]:
            css = fetch_text(css_url)
            if css:
                css_texts.append(css)
        all_css_texts.extend(css_texts)
        pages_result.append(page_data)
        print(f"  [parse_html] {url} — autoplay={page_data['has_autoplay_media']} "
              f"adaptive_img_ratio={page_data['adaptive_img_ratio']} viewport_ok={page_data['viewport_ok']}")

    if not pages_result:
        print("Erreur : aucune page n'a pu être récupérée (réseau indisponible ?).")
        sys.exit(1)

    css_result = analyze_css(all_css_texts)

    result = {
        "pages": pages_result,
        "css": css_result,
        "note": "HTML/CSS re-fetchés en direct sur les mêmes URLs déjà listées dans "
                "env-data.json (le .har capturé ne contient pas les corps de réponse "
                "HTML/CSS) — pas de nouveau périmètre de pages.",
    }

    out_path = source_dir / "html-css-criteria.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"html-css-criteria.json écrit : {out_path}")


if __name__ == "__main__":
    main()
