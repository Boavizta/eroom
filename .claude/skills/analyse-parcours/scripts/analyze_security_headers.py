#!/usr/bin/env python3
"""
Calcule un score de sécurité des en-têtes HTTP (type securityheaders.com),
localement, sans appel à aucune API tierce — uniquement à partir des en-têtes
de réponse déjà présents dans le .har capturé (aucun nouveau téléchargement).

Analyse la réponse "document principal" (mimeType text/html) de chaque page
listée dans env-data.json (ou, à défaut, chaque entrée HTML unique du HAR).

Usage :
    python3 analyze_security_headers.py <source_dir>

Écrit <source_dir>/security-headers-analysis.json.
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"

# (nom d'en-tête, poids, validateur) — validateur reçoit la valeur brute (str),
# retourne True si l'en-tête est considéré "correctement positionné".
# Pondération inspirée de securityheaders.com (CSP et HSTS pèsent le plus).
_HEADER_CHECKS = [
    ("content-security-policy", 25, lambda v: bool(v.strip())),
    ("strict-transport-security", 20, lambda v: "max-age=" in v.lower()),
    ("x-content-type-options", 15, lambda v: v.strip().lower() == "nosniff"),
    ("x-frame-options", 15, lambda v: v.strip().lower() in ("deny", "sameorigin")),
    ("referrer-policy", 15, lambda v: bool(v.strip())),
    ("permissions-policy", 10, lambda v: bool(v.strip())),
]
_TOTAL_WEIGHT = sum(w for _, w, _ in _HEADER_CHECKS)

_GRADE_THRESHOLDS = [(90, "A"), (70, "B"), (50, "C"), (30, "D"), (0, "F")]


def find_har(source_dir):
    hars = list(source_dir.glob("*.har")) or list((source_dir / RAW_DATA_DIR).glob("*.har"))
    return hars[0] if hars else None


def grade_for_score(score_pct):
    for threshold, letter in _GRADE_THRESHOLDS:
        if score_pct >= threshold:
            return letter
    return "F"


def score_headers(headers):
    """headers : dict nom_minuscule -> valeur. Retourne (score_pct, detail[])."""
    detail = []
    obtained = 0
    for name, weight, is_ok in _HEADER_CHECKS:
        value = headers.get(name)
        ok = value is not None and is_ok(value)
        if ok:
            obtained += weight
        detail.append({
            "header": name, "present": value is not None,
            "valide": ok, "valeur": value, "poids": weight,
        })
    score_pct = round(obtained / _TOTAL_WEIGHT * 100)
    return score_pct, detail


def load_page_urls(source_dir):
    env_path = source_dir / "env-data.json"
    if not env_path.exists():
        return None
    env = json.loads(env_path.read_text(encoding="utf-8"))
    return [p["url"] for p in env.get("pages", []) if p.get("url")]


def analyze(har_path, target_urls=None):
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)
    entries = har.get("log", {}).get("entries", [])

    def norm(u):
        return u.rstrip("/") if u else u

    target_set = {norm(u) for u in target_urls} if target_urls else None

    pages = []
    seen_urls = set()
    for e in entries:
        content = e.get("response", {}).get("content", {})
        if "html" not in content.get("mimeType", ""):
            continue
        url = e.get("request", {}).get("url", "")
        if target_set is not None and norm(url) not in target_set:
            continue
        if norm(url) in seen_urls:
            continue
        seen_urls.add(norm(url))
        headers = {h["name"].lower(): h["value"] for h in e.get("response", {}).get("headers", [])}
        score_pct, detail = score_headers(headers)
        pages.append({
            "url": url, "score_pct": score_pct, "grade": grade_for_score(score_pct),
            "detail": detail,
        })

    if not pages:
        return None

    worst = min(pages, key=lambda p: p["score_pct"])
    return {
        "pages": pages,
        "worst_page": {"url": worst["url"], "score_pct": worst["score_pct"], "grade": worst["grade"]},
        "note": "Score calculé localement (pondération inspirée de securityheaders.com), "
                "depuis les en-têtes déjà capturés dans le .har — aucun appel réseau.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir")
    args = parser.parse_args()
    source_dir = Path(args.source_dir).resolve()

    har_path = find_har(source_dir)
    if not har_path:
        print(f"Erreur : aucun .har trouvé dans {source_dir} (ni dans {RAW_DATA_DIR}/).")
        sys.exit(1)

    target_urls = load_page_urls(source_dir)
    result = analyze(har_path, target_urls)
    if result is None:
        print("Aucune réponse HTML trouvée dans le HAR — analyse impossible.")
        sys.exit(1)

    out_path = source_dir / "security-headers-analysis.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"security-headers-analysis.json écrit : {out_path}")
    print(f"Page la moins bien notée : {result['worst_page']['url']} "
          f"({result['worst_page']['score_pct']}%, grade {result['worst_page']['grade']})")


if __name__ == "__main__":
    main()
