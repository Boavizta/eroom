#!/usr/bin/env python3
"""
Collecte les Core Web Vitals via l'API PageSpeed Insights (Google).
Source privilégiée : données terrain CrUX (P75 réel utilisateurs).
Fallback si CrUX absent : données lab Lighthouse retournées par la même API.

Usage :
    python3 collect_cwv_pagespeed.py <dossier-audit>                    # mobile + desktop (défaut)
    python3 collect_cwv_pagespeed.py <dossier-audit> --strategy mobile  # mobile seul
    python3 collect_cwv_pagespeed.py <dossier-audit> --urls https://example.com https://example.com/page2

Par défaut (--strategy both), collecte mobile ET desktop pour chaque URL et les
conserve côte à côte dans cwv.json (une entrée par couple url/stratégie).

Lit GOOGLE_API_KEY depuis .env à la racine du projet.
Écrit (ou met à jour) <dossier-audit>/cwv.json.

Format de sortie :
    [
      {"page": "page_1", "url": "https://...", "lcp": 2.5, "inp": 200, "cls": 0.1,
       "source": "crux", "strategy": "mobile", "crux_category": "NEEDS_IMPROVEMENT",
       "accessibility_score_pct": 96, "best_practices_score_pct": 92},
      ...
    ]

accessibility_score_pct / best_practices_score_pct : scores Lighthouse (mêmes
appels API, catégories additionnelles demandées dans la même requête — pas
d'appel réseau supplémentaire) — absents (clé omise) si l'API ne les renvoie
pas pour cette page.

Sources possibles :
    "crux"          - Données terrain CrUX P75 (recommandé — utilisateurs réels)
    "pagespeed_lab" - Données lab Lighthouse via API (CrUX indisponible pour cette URL)
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"  # genericite: ok - URL officielle API PageSpeed Insights (Google)

# Sous-dossier optionnel où ranger les captures brutes (HAR, Coverage), dans .gitignore.
RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"  # genericite: ok - declaration de la constante

# Seuils officiels CWV (Google)
LCP_GOOD = 2.5    # s
LCP_POOR = 4.0
INP_GOOD = 200    # ms
INP_POOR = 500
CLS_GOOD = 0.1
CLS_POOR = 0.25

# Audits Lighthouse Insights pertinents pour l'écoconception.
# Structure tolérante aux versions : chaque entrée logique accepte plusieurs noms
# d'audit alias (nouveau et ancien), et l'extracteur retient le premier présent
# dans la réponse. Les noms `-insight` sont récents (Lighthouse 12+) ; les
# anciens existaient avant et peuvent reparaître dans des versions futures ou
# d'autres services. Aucun crash, aucune valeur inventée si aucun alias n'est présent.
INSIGHT_AUDIT_KEYS = [
    {
        "logical_name": "duplicated-javascript",
        "aliases": ["duplicated-javascript-insight", "duplicated-javascript"],
        "description": "Critère EOF 6.8 (duplication de bundles JS)"
    },
    {
        "logical_name": "unused-javascript",
        "aliases": ["unused-javascript"],
        "description": "Code mort JS (optimisation poids)"
    },
    {
        "logical_name": "render-blocking",
        "aliases": ["render-blocking-insight", "render-blocking-resources"],
        "description": "Ressources bloquant le rendu"
    },
    {
        "logical_name": "total-byte-weight",
        "aliases": ["total-byte-weight"],
        "description": "Poids réseau total"
    },
    {
        "logical_name": "dom-size",
        "aliases": ["dom-size-insight", "dom-size"],
        "description": "Taille du DOM"
    },
    {
        "logical_name": "bootup-time",
        "aliases": ["bootup-time"],
        "description": "Temps d'exécution JS"
    },
    {
        "logical_name": "mainthread-work-breakdown",
        "aliases": ["mainthread-work-breakdown"],
        "description": "Charge du thread principal"
    },
    {
        "logical_name": "third-parties",
        "aliases": ["third-parties-insight", "third-party-summary"],
        "description": "Dépendances tierces"
    },
    {
        "logical_name": "cache",
        "aliases": ["cache-insight", "uses-long-cache-ttl"],
        "description": "Durée de vie du cache"
    },
    {
        "logical_name": "font-display",
        "aliases": ["font-display-insight", "font-display"],
        "description": "Affichage des polices"
    },
    {
        "logical_name": "image-size-responsive",
        "aliases": ["image-size-responsive", "uses-responsive-images"],
        "description": "Résolution des images"
    },
]


def load_env(project_root):
    """Lit GOOGLE_API_KEY depuis .env."""
    env_path = project_root / ".env"
    if not env_path.exists():
        return None
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def extract_urls_from_har(har_path):
    """Extrait les URLs des pages depuis un HAR. Retourne [(page_id, url), ...]."""
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)
    pages = har.get("log", {}).get("pages", [])
    result = []
    seen = set()
    for i, page in enumerate(pages):
        url = page.get("title", "")
        if url and url.startswith("http") and url not in seen:
            result.append((f"page_{i + 1}", url))
            seen.add(url)
    return result


def find_har(audit_dir):
    """Trouve le .har dans le dossier source (parent de audit/)."""
    source_dir = audit_dir.parent
    hars = list(source_dir.glob("*.har"))
    if not hars:
        # Chercher aussi dans audit_dir lui-même
        hars = list(audit_dir.glob("*.har"))
    if not hars:
        # Puis dans le sous-dossier de captures brutes, des deux côtés
        hars = (list((source_dir / RAW_DATA_DIR).glob("*.har"))
                or list((audit_dir / RAW_DATA_DIR).glob("*.har")))
    if len(hars) == 1:
        return hars[0]
    if len(hars) > 1:
        print(f"[PageSpeed] Plusieurs .har trouvés : {[h.name for h in hars]}")
        print(f"[PageSpeed] Utilisation de : {hars[0].name}")
    return hars[0] if hars else None


def call_pagespeed(url, api_key, strategy="mobile"):
    """Appelle l'API PageSpeed Insights. Retourne le JSON brut ou None si erreur."""
    params = {
        "url": url,
        "key": api_key,
        "strategy": strategy,
        "category": ["performance", "accessibility", "best-practices"],
    }
    full_url = PAGESPEED_API + "?" + urllib.parse.urlencode(params, doseq=True)
    try:
        req = urllib.request.urlopen(full_url, timeout=30)
        return json.loads(req.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body).get("error", {})
            print(f"  [PageSpeed] Erreur HTTP {e.code} pour {url} : {err.get('message', body[:200])}")
        except Exception:
            print(f"  [PageSpeed] Erreur HTTP {e.code} pour {url}")
        return None
    except Exception as e:
        print(f"  [PageSpeed] Erreur réseau pour {url} : {e}")
        return None


def extract_crux(data):
    """Extrait les métriques CrUX (terrain) depuis la réponse PageSpeed."""
    le = data.get("loadingExperience", {})
    metrics = le.get("metrics", {})
    if not metrics:
        return None

    def get_p75(key, divisor=1):
        m = metrics.get(key, {})
        p = m.get("percentile")
        return round(p / divisor, 3) if p is not None else None

    lcp = get_p75("LARGEST_CONTENTFUL_PAINT_MS", divisor=1000)
    inp = get_p75("INTERACTION_TO_NEXT_PAINT")
    cls = get_p75("CUMULATIVE_LAYOUT_SHIFT_SCORE", divisor=100)

    if lcp is None and inp is None and cls is None:
        return None

    return {
        "source": "crux",
        "crux_category": le.get("overall_category", ""),
        "lcp": lcp,
        "inp": inp,
        "cls": cls,
    }


def extract_lab(data):
    """Extrait les métriques lab Lighthouse depuis la réponse PageSpeed (fallback)."""
    audits = data.get("lighthouseResult", {}).get("audits", {})

    def numeric(key):
        a = audits.get(key, {})
        v = a.get("numericValue")
        return v if v is not None else None

    lcp_ms = numeric("largest-contentful-paint")
    inp_ms = numeric("interaction-to-next-paint")
    cls_raw = numeric("cumulative-layout-shift")

    lcp = round(lcp_ms / 1000, 3) if lcp_ms is not None else None
    inp = round(inp_ms, 0) if inp_ms is not None else None
    cls = round(cls_raw, 3) if cls_raw is not None else None

    if lcp is None and inp is None and cls is None:
        return None

    return {
        "source": "pagespeed_lab",
        "lcp": lcp,
        "inp": inp,
        "cls": cls,
    }


def extract_lighthouse_scores(data):
    """Extrait les scores Lighthouse accessibility / best-practices (0-100),
    présents dans la même réponse API quelle que soit la source (crux/lab) des
    CWV. Retourne {} si absents (jamais une valeur inventée)."""
    categories = data.get("lighthouseResult", {}).get("categories", {})
    out = {}
    a11y = categories.get("accessibility", {}).get("score")
    if a11y is not None:
        out["accessibility_score_pct"] = round(a11y * 100)
    bp = categories.get("best-practices", {}).get("score")
    if bp is not None:
        out["best_practices_score_pct"] = round(bp * 100)
    return out


def extract_insight_scores(data):
    """Extrait les audits Lighthouse Insights pertinents pour l'écoconception.

    Ces audits sont présents dans la même réponse API que les CWV (même appel
    réseau, pas de coût supplémentaire). Leur présence dépend de la version de
    Lighthouse et du contenu de la page analysée.

    Retourne un dict avec une entrée par audit trouvé, indexé par logical_name :
        {
          "logical_name": {
            "score": 0-1 ou None,
            "numericValue": float ou None,
            "itemCount": int,
            "found_as": "audit_key_reel"
          },
          ...
        }

    Retourne {} si aucun audit n'est disponible (jamais de valeur inventée).
    """
    audits = data.get("lighthouseResult", {}).get("audits", {})
    if not audits:
        return {}

    out = {}
    for entry in INSIGHT_AUDIT_KEYS:
        logical_name = entry["logical_name"]
        aliases = entry["aliases"]

        # Retient le premier alias présent dans la réponse
        found_key = None
        audit = None
        for alias in aliases:
            if alias in audits:
                found_key = alias
                audit = audits[alias]
                break

        if not audit:
            continue

        score = audit.get("score")
        numeric = audit.get("numericValue")
        items = audit.get("details", {}).get("items", [])
        item_count = len(items) if isinstance(items, list) else 0

        out[logical_name] = {
            "score": score,
            "numericValue": numeric,
            "itemCount": item_count,
            "found_as": found_key,
        }

    return out


def collect(audit_dir, urls, api_key, strategies=("mobile",)):
    """Collecte les CWV pour chaque URL et chaque stratégie.

    Retourne la liste au format cwv.json : une entrée par couple (url, strategy).
    """
    results = []
    for page_id, url in urls:
        print(f"  [{page_id}] {url}")
        for strategy in strategies:
            data = call_pagespeed(url, api_key, strategy)
            if data is None:
                print(f"    [{strategy}] -> Aucune réponse API, ignoré.")
                continue

            crux = extract_crux(data)
            if crux:
                entry = {"page": page_id, "url": url, "strategy": strategy}
                entry.update(crux)
                print(f"    [{strategy}] -> CrUX terrain : LCP={entry.get('lcp')}s INP={entry.get('inp')}ms CLS={entry.get('cls')} [{entry.get('crux_category')}]")
            else:
                lab = extract_lab(data)
                if lab:
                    entry = {"page": page_id, "url": url, "strategy": strategy}
                    entry.update(lab)
                    print(f"    [{strategy}] -> Lab (CrUX absent) : LCP={entry.get('lcp')}s INP={entry.get('inp')}ms CLS={entry.get('cls')}")
                else:
                    print(f"    [{strategy}] -> Aucune métrique disponible.")
                    continue

            lh_scores = extract_lighthouse_scores(data)
            if lh_scores:
                entry.update(lh_scores)
                print(f"    [{strategy}] -> Lighthouse a11y={lh_scores.get('accessibility_score_pct', '?')} "
                      f"best-practices={lh_scores.get('best_practices_score_pct', '?')}")

            insights = extract_insight_scores(data)
            if insights:
                entry["lighthouse_insights"] = insights
                print(f"    [{strategy}] -> {len(insights)} audit(s) insight disponible(s)")

            results.append(entry)
            time.sleep(0.5)  # Éviter de dépasser le quota par minute

    return results


def merge_with_existing(new_entries, existing_path):
    """Fusionne avec un cwv.json existant.

    Les nouvelles entrées remplacent les anciennes par couple (URL, stratégie),
    afin de conserver côte à côte mobile ET desktop pour une même page (un
    passage desktop n'écrase plus le mobile). Les entrées historiques sans champ
    `strategy` sont considérées comme mobile (ancien défaut).
    """
    if not existing_path.exists():
        return new_entries

    with open(existing_path, encoding="utf-8") as f:
        existing = json.load(f)

    def norm(u):
        return u.rstrip("/") if u else u

    def key(e):
        return (norm(e.get("url", "")), e.get("strategy", "mobile"))

    new_keys = {key(e) for e in new_entries if "url" in e}
    kept = [e for e in existing if key(e) not in new_keys]
    merged = kept + new_entries
    merged.sort(key=lambda e: (e.get("page", ""), e.get("strategy", "")))
    return merged


def fallback_lighthouse(audit_dir, urls):
    """Lance run_lighthouse.sh en fallback si PageSpeed échoue. Retourne True si succès."""
    script = Path(__file__).parent / "run_lighthouse.sh"
    if not script.exists():
        print("[Fallback] run_lighthouse.sh introuvable, fallback impossible.")
        return False

    print("\n[Fallback] Lancement Lighthouse comme source de secours...")
    url_args = [u for _, u in urls]
    cmd = ["bash", str(script), str(audit_dir)] + url_args
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("[Fallback] cwv.json généré par Lighthouse.")
        return True
    else:
        print("[Fallback] Lighthouse a également échoué.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Collecte CWV via PageSpeed Insights API")
    parser.add_argument("audit_dir", help="Dossier audit (contient cwv.json ou parent du .har)")
    parser.add_argument("--strategy", default="both", choices=["mobile", "desktop", "both"],
                        help="Stratégie PageSpeed : mobile, desktop ou both (défaut : both)")
    parser.add_argument("--urls", nargs="+", help="URLs explicites (optionnel, sinon lu depuis .har)")
    parser.add_argument("--check", action="store_true", help="Vérifie la clé API sans analyser")
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir).resolve()
    if not audit_dir.exists():
        print(f"Erreur : dossier introuvable : {audit_dir}")
        sys.exit(1)

    # Trouver la racine projet (remonter jusqu'à trouver .env ou .git)
    project_root = audit_dir
    for _ in range(6):
        if (project_root / ".env").exists() or (project_root / ".git").exists():
            break
        project_root = project_root.parent

    api_key = load_env(project_root)
    if not api_key:
        print("[PageSpeed] GOOGLE_API_KEY introuvable — fallback Lighthouse.")
        print(f"(Pour activer PageSpeed : créer .env dans {project_root} avec GOOGLE_API_KEY=...)")
        if args.urls:
            urls = [(f"page_{i + 1}", u) for i, u in enumerate(args.urls)]
        else:
            har = find_har(audit_dir)
            urls = extract_urls_from_har(har) if har else []
        fallback_lighthouse(audit_dir, urls)
        sys.exit(0)

    if args.check:
        # Test rapide sur une URL simple
        print("[PageSpeed] Vérification clé API...")
        data = call_pagespeed("https://www.google.com", api_key, "mobile")  # genericite: ok - URL neutre pour tester la clé API
        if data and "loadingExperience" in data:
            print("[PageSpeed] Clé API valide.")
        else:
            print("[PageSpeed] Clé API invalide ou APIs non activées.")
            # genericite: ok-debut - URL de documentation officielle Google Cloud
            print("Vérifier que PageSpeed Insights API est activée :")
            print("  https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com")
            # genericite: ok-fin
            sys.exit(1)
        return

    # Construire la liste d'URLs
    if args.urls:
        urls = [(f"page_{i + 1}", u) for i, u in enumerate(args.urls)]
    else:
        har = find_har(audit_dir)
        if not har:
            print(f"Erreur : aucun fichier .har trouvé dans {audit_dir.parent}")
            print("Utiliser --urls pour fournir les URLs explicitement.")
            sys.exit(1)
        urls = extract_urls_from_har(har)
        if not urls:
            print(f"Erreur : aucune URL de page trouvée dans {har.name}")
            sys.exit(1)
        print(f"[PageSpeed] {len(urls)} page(s) extraites depuis {har.name}")

    strategies = ["mobile", "desktop"] if args.strategy == "both" else [args.strategy]
    print(f"[PageSpeed] Stratégie(s) : {', '.join(strategies)} | {len(urls)} URL(s)")
    print()

    entries = collect(audit_dir, urls, api_key, strategies=strategies)

    if not entries:
        print("\n[PageSpeed] Aucune métrique collectée — fallback Lighthouse.")
        fallback_lighthouse(audit_dir, urls)
        sys.exit(0)

    cwv_path = audit_dir / "cwv.json"
    merged = merge_with_existing(entries, cwv_path)

    with open(cwv_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    crux_count = sum(1 for e in entries if e.get("source") == "crux")
    lab_count = len(entries) - crux_count
    mobile_count = sum(1 for e in entries if e.get("strategy") == "mobile")
    desktop_count = sum(1 for e in entries if e.get("strategy") == "desktop")
    print(f"\n[PageSpeed] cwv.json mis à jour : {len(entries)} entrée(s)")
    print(f"  - {mobile_count} mobile / {desktop_count} desktop")
    if crux_count:
        print(f"  - {crux_count} entrée(s) avec données terrain CrUX")
    if lab_count:
        print(f"  - {lab_count} entrée(s) avec données lab (CrUX absent)")
    print(f"  -> {cwv_path}")


if __name__ == "__main__":
    main()
