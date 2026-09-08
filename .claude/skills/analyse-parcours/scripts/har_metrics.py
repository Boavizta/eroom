#!/usr/bin/env python3
"""
EcoIndex utilities — formule officielle (cnumr/ecoindex_reference).
Extraction DOM depuis HAR, métriques par page, calcul score + grade.

Usage autonome :
  python3 ecoindex_utils.py capture.har
"""

import base64
import json
from pathlib import Path
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
    """Extrait le DOM depuis une entrée HAR de type document (HTML).

    Retourne (count, success, reason) :
      - count : nombre de balises (0 si échec)
      - success : True si mesuré avec succès
      - reason : None si succès, message d'erreur sinon
    """
    content = entry.get("response", {}).get("content", {})
    mime = content.get("mimeType", "")
    if "html" not in mime:
        return 0, False, "no_html_entry"

    text = content.get("text", "")
    if not text:
        return 0, False, "no_content"

    # Gestion de l'encodage
    encoding = content.get("encoding", "")
    if encoding == "base64":
        try:
            decoded_bytes = base64.b64decode(text)
            text = decoded_bytes.decode("utf-8")
        except Exception as exc:
            return 0, False, f"echec_decodage_base64: {str(exc)}"
    elif encoding and encoding != "":
        # Encodage non vide et inconnu
        return 0, False, f"encodage_inconnu: {encoding}"

    # Compte des balises
    count = count_dom_elements(text)

    # Garde-fou : un document HTML non vide avec zéro balise est anormal
    if count == 0 and len(text.strip()) > 0:
        return 0, False, "aucune_balise_reconnue"

    return count, True, None


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
        dom_success = False
        dom_reason = None
        url = page.get("title", "")  # HAR pages stockent l'URL dans title

        for e in page_entries:
            count, success, reason = extract_dom_from_har_entry(e)
            if success:
                dom = count
                dom_success = True
                dom_reason = None
                break
            # Garder trace de la première tentée
            if dom_reason is None:
                dom_reason = reason

        # Construction du bloc mesure selon la convention
        if dom_success:
            mesure = {
                "statut": "ok",
                "cible": url,
                "detail": None
            }
        elif dom_reason == "no_content":
            mesure = {
                "statut": "echec_lecture",
                "cible": url,
                "detail": "La capture HAR ne contient pas les corps de réponse HTML"
            }
        elif dom_reason and dom_reason.startswith("echec_decodage_base64"):
            mesure = {
                "statut": "echec_lecture",
                "cible": url,
                "detail": f"Échec du décodage base64: {dom_reason.split(': ', 1)[1] if ': ' in dom_reason else 'invalide'}"
            }
        elif dom_reason and dom_reason.startswith("encodage_inconnu"):
            encoding_name = dom_reason.split(": ", 1)[1] if ": " in dom_reason else "inconnu"
            mesure = {
                "statut": "echec_lecture",
                "cible": url,
                "detail": f"Encodage non supporté: {encoding_name}"
            }
        elif dom_reason == "aucune_balise_reconnue":
            mesure = {
                "statut": "echec_analyse",
                "cible": url,
                "detail": "Corps HTML lu mais aucune balise reconnue"
            }
        elif dom_reason == "no_html_entry":
            mesure = {
                "statut": "echec_analyse",
                "cible": url,
                "detail": "Aucun document HTML trouvé pour cette page"
            }
        else:
            # Cas par défaut si aucune entrée du tout
            mesure = {
                "statut": "echec_analyse",
                "cible": url,
                "detail": "Aucun document HTML trouvé pour cette page"
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
            "mesure": mesure,
        })

    return results


def load_cwv(cwv_path):
    """Charge cwv.json. Retourne un dict indexé par URL (normalisée) ET par page_id.

    Chaque valeur est un dict groupé par stratégie : {"mobile": row, "desktop": row}.
    Cela permet de conserver mobile ET desktop côte à côte pour une même page.
    Les entrées historiques sans champ 'strategy' sont classées 'mobile' (ancien défaut).
    La correspondance par URL est prioritaire (robuste si les IDs HAR et CWV divergent)."""
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


# --- CLI autonome pour validation ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ecoindex_utils.py <fichier.har> [cwv.json]")
        sys.exit(1)

    har_path = sys.argv[1]

    # Borne de début pour le calcul des coûts (lue par patch-audit-cost.sh)
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

    # Comptage des échecs
    total_pages = len(metrics)
    failed_pages = sum(1 for m in metrics if m["mesure"]["statut"] != "ok")

    print(f"\n{'Page':<30} {'Req':>5} {'Ko':>8} {'DOM':>6} {'Score':>6} {'Grade':>6} {'onLoad':>9} {'Mesure':<10}")
    print("-" * 95)
    for m in metrics:
        status_marker = "✓" if m["mesure"]["statut"] == "ok" else "✗ ÉCHEC"
        print(f"{m['title'][:29]:<30} {m['req']:>5} {m['size_ko']:>8.1f} {m['dom']:>6} "
              f"{m['ecoindex']:>6} {m['grade']:>6} {m['on_load_ms']:>8}ms {status_marker:<10}")
        if m["mesure"]["statut"] != "ok":
            print(f"  └→ {m['mesure']['statut']}: {m['mesure']['detail']}")
        if m["page_id"] in cwv:
            c = cwv[m["page_id"]]
            print(f"  CWV → LCP: {c.get('lcp','?')}s  INP: {c.get('inp','?')}ms  CLS: {c.get('cls','?')}")

    print()
    if failed_pages > 0:
        print(f"⚠️  ATTENTION : {failed_pages} pages sur {total_pages} ont un DOM non mesuré")
        print()

    print()
    # Validation contre ANTS connus (si P1 avec dom=483, req=82, poids=1930 → score=53)
    test_score = ecoindex_score(483, 82, 1930)
    print(f"[Validation ANTS P1] dom=483 req=82 poids=1930 Ko → score={test_score}/100 (attendu: 53)")
    g, c = ecoindex_grade(test_score)
    print(f"  Grade: {g} ({c})")
