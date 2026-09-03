#!/usr/bin/env python3
"""
Scanne trois fichiers publics standards du domaine audité, par requête HTTP
directe (fetch simple, pas de scraping ni d'authentification) :
  - /.well-known/security.txt (RFC 9116)
  - /robots.txt
  - /sitemap.xml (déclaré dans robots.txt, sinon /sitemap.xml à la racine)

Usage :
    python3 scan_wellknown.py <domaine>          # ex. octo.com
    python3 scan_wellknown.py <source_dir>       # déduit le domaine de env-data.json

Écrit <source_dir>/wellknown-scan.json (si source_dir fourni), sinon affiche le JSON.
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
    """GET simple. Retourne (status_code, text) ou (None, None) si erreur réseau."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return None, None


def _looks_like_html(text):
    """Détecte un fallback catch-all de SPA (statut 200 mais page HTML de
    l'appli, pas la ressource demandée) — sinon toute SPA sans le fichier
    demandé serait faussement comptée "présente". Vérifié en conditions
    réelles sur octo.com : robots.txt ET sitemap.xml renvoient tous les deux
    l'index HTML de la SPA avec un statut 200."""
    head = text[:200].lstrip().lower()
    return head.startswith("<!doctype html") or head.startswith("<html")


def scan_security_txt(domain):
    for path in ("/.well-known/security.txt", "/security.txt"):
        status, text = fetch(f"https://{domain}{path}")
        if status == 200 and text and not _looks_like_html(text):
            fields = ("contact:", "expires:")
            well_formed = all(f in text.lower() for f in fields)
            return {"present": True, "path": path, "well_formed": well_formed, "excerpt": text[:300]}
    return {"present": False}


def scan_robots_txt(domain):
    status, text = fetch(f"https://{domain}/robots.txt")
    if status != 200 or not text or _looks_like_html(text):
        return {"present": False}
    sitemap_urls = re.findall(r"(?im)^sitemap:\s*(\S+)", text)
    return {"present": True, "sitemap_urls": sitemap_urls}


def scan_sitemap(domain, sitemap_urls):
    urls_to_try = sitemap_urls or [f"https://{domain}/sitemap.xml"]
    for url in urls_to_try:
        status, text = fetch(url)
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
                "present": True, "url": url, "url_count": url_count,
                "most_recent_lastmod": most_recent, "days_since_lastmod": days_ago,
            }
    return {"present": False}


def scan(domain):
    security_txt = scan_security_txt(domain)
    robots = scan_robots_txt(domain)
    sitemap = scan_sitemap(domain, robots.get("sitemap_urls"))
    return {
        "domain": domain,
        "security_txt": security_txt,
        "robots_txt": robots,
        "sitemap": sitemap,
        "note": "Fetch direct et public (aucune authentification), pas de nouvel appel "
                "au-delà de ces 2-3 requêtes HTTP par domaine.",
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
    parser.add_argument("target", help="Domaine (ex. octo.com) ou dossier d'audit (env-data.json)")
    args = parser.parse_args()

    target_path = Path(args.target)
    source_dir = None
    if target_path.exists() and target_path.is_dir():
        source_dir = target_path.resolve()
        domain = infer_domain(source_dir)
        if not domain:
            print(f"Erreur : impossible de déduire le domaine depuis {source_dir}/env-data.json.")
            sys.exit(1)
    else:
        domain = args.target

    print(f"[scan_wellknown] Domaine : {domain}")
    result = scan(domain)

    if source_dir:
        out_path = source_dir / "wellknown-scan.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wellknown-scan.json écrit : {out_path}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    print(f"  security.txt : {'présent' if result['security_txt']['present'] else 'absent'}")
    print(f"  robots.txt   : {'présent' if result['robots_txt']['present'] else 'absent'}")
    print(f"  sitemap.xml  : {'présent' if result['sitemap']['present'] else 'absent'}"
          + (f" ({result['sitemap'].get('url_count')} URLs)" if result["sitemap"]["present"] else ""))


if __name__ == "__main__":
    main()
