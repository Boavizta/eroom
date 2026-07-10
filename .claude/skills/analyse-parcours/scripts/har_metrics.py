#!/usr/bin/env python3
"""
EcoIndex utilities — formule officielle (cnumr/ecoindex_reference).
Extraction DOM depuis HAR, métriques par page, calcul score + grade.

Usage autonome :
  python3 ecoindex_utils.py capture.har
"""

import json
import math
import re
import sys
from pathlib import Path

# Quantiles officiels (cnumr/ecoindex_reference)
_ECO_Q_DOM  = [0,47,75,159,233,298,358,417,476,537,603,674,753,843,949,1076,1237,1459,1801,2479,594601]
_ECO_Q_REQ  = [0,2,15,25,34,42,49,56,63,70,78,86,95,105,117,130,147,170,205,281,3920]
_ECO_Q_SIZE = [0,1.37,144.7,319.53,479.46,631.97,783.38,937.91,1098.62,1265.47,1448.32,1648.27,
               1876.08,2142.06,2465.37,2866.31,3401.59,4155.73,5400.08,8037.54,223212.26]

# (seuil_min, lettre, rgb)
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
    """Retourne le score EcoIndex (0-100) depuis DOM, requêtes et poids en Ko."""
    qd = _quantile(_ECO_Q_DOM,  dom)
    qr = _quantile(_ECO_Q_REQ,  req)
    qs = _quantile(_ECO_Q_SIZE, size_ko)
    return math.ceil(100 - 5 * (3 * qd + 2 * qr + qs) / 6)


def ecoindex_grade(score):
    """Retourne (lettre, couleur_hex) pour un score EcoIndex."""
    for threshold, letter, color in _ECO_GRADES:
        if score >= threshold:
            return letter, color
    return "G", "#ED2124"


def count_dom_elements(html_text):
    """Compte les balises ouvrantes dans un corps HTML."""
    if not html_text:
        return 0
    return len(re.findall(r'<[a-zA-Z][^/>]*', html_text))


def extract_dom_from_har_entry(entry):
    """Extrait le DOM depuis une entrée HAR de type document (HTML)."""
    content = entry.get("response", {}).get("content", {})
    mime = content.get("mimeType", "")
    if "html" not in mime:
        return 0
    text = content.get("text", "")
    if not text:
        return 0
    return count_dom_elements(text)


def extract_page_metrics(har_data):
    """
    Extrait les métriques par page depuis les données HAR parsées.
    Retourne une liste de dicts :
      { page_id, url, title, req, size_ko, dom, on_load_ms, on_content_load_ms }
    """
    log = har_data.get("log", {})
    pages = log.get("pages", [])
    entries = log.get("entries", [])

    # Index entries par pageref
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

        # DOM : première entrée HTML de la page
        dom = 0
        for e in page_entries:
            d = extract_dom_from_har_entry(e)
            if d > 0:
                dom = d
                break

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
        })

    return results


def load_cwv(cwv_path):
    """Charge cwv.json. Retourne un dict indexé par URL (normaliser) ET par page_id.
    La correspondance par URL est prioritaire (robuste si les IDs HAR et Lighthouse divergent)."""
    p = Path(cwv_path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    result = {}
    for row in data:
        if "url" in row:
            result[row["url"].rstrip("/")] = row
        result[row["page"]] = row
    return result


# --- CLI autonome pour validation ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ecoindex_utils.py <fichier.har> [cwv.json]")
        sys.exit(1)

    har_path = sys.argv[1]
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    cwv = {}
    if len(sys.argv) >= 3:
        cwv = load_cwv(sys.argv[2])

    metrics = extract_page_metrics(har)

    print(f"\n{'Page':<30} {'Req':>5} {'Ko':>8} {'DOM':>6} {'Score':>6} {'Grade':>6} {'onLoad':>9}")
    print("-" * 80)
    for m in metrics:
        print(f"{m['title'][:29]:<30} {m['req']:>5} {m['size_ko']:>8.1f} {m['dom']:>6} "
              f"{m['ecoindex']:>6} {m['grade']:>6} {m['on_load_ms']:>8}ms")
        if m["page_id"] in cwv:
            c = cwv[m["page_id"]]
            print(f"  CWV → LCP: {c.get('lcp','?')}s  INP: {c.get('inp','?')}ms  CLS: {c.get('cls','?')}")

    print()
    # Validation contre ANTS connus (si P1 avec dom=483, req=82, poids=1930 → score=53)
    test_score = ecoindex_score(483, 82, 1930)
    print(f"[Validation ANTS P1] dom=483 req=82 poids=1930 Ko → score={test_score}/100 (attendu: 53)")
    g, c = ecoindex_grade(test_score)
    print(f"  Grade: {g} ({c})")
