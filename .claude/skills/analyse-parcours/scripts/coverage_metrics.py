#!/usr/bin/env python3
"""
Analyse des fichiers Coverage Chrome DevTools — produit coverage-analysis.json.

Remplace le calcul à la main de l'étape 30. Deux raisons :

1. L'extension se lit sur le CHEMIN, jamais sur l'URL entière. Une URL versionnée
   (dsfr.min.css?version=39.2.0) ne se termine pas par son extension. Un test
   naïf `url.endswith(".css")` la classe en "autre", elle disparaît des agrégats
   JS/CSS, et une page dont TOUTES les URLs sont versionnées est publiée à zéro.
2. Le libellé de page vient de l'URL du document réellement chargé, pas du rang
   du fichier dans l'ordre alphabétique.

Usage :
  python3 coverage_metrics.py <dossier-source> [--output coverage-analysis.json]
  python3 coverage_metrics.py <dossier-source> --check    # compare sans écrire
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

# Sous-dossier optionnel où ranger les captures brutes (HAR, Coverage).
RAW_DATA_DIR = "donnees-brutes-potentiellement-sensibles"  # genericite: ok - declaration de la constante

# Extensions d'asset : une URL qui en porte une n'est pas une URL de page.
ASSET_EXTS = re.compile(
    r'\.(js|mjs|css|webp|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|otf|eot|json|map)$',
    re.I,
)

# Bibliothèques tierces reconnaissables, avec leur rôle. Le rôle fait partie du
# libellé : "Swetrix" seul n'apprend rien à qui lit le rapport.
KNOWN_LIBRARIES = {                     # genericite: ok-debut - table explicite de tiers
    "swetrix":            "Swetrix (analytics)",
    "google-analytics":   "Google Analytics",
    "googletagmanager":   "Google Tag Manager",
    "matomo":             "Matomo (analytics)",
    "piwik":              "Matomo/Piwik (analytics)",
    "atinternet":         "AT Internet (analytics)",
    "xiti":               "AT Internet/Xiti (analytics)",
    "kameleoon":          "Kameleoon (A/B testing)",
    "abtasty":            "AB Tasty (A/B testing)",
    "optimizely":         "Optimizely (A/B testing)",
    "orejime":            "Orejime (gestionnaire de consentement cookies)",
    "tarteaucitron":      "Tarteaucitron (gestionnaire de consentement cookies)",
    "didomi":             "Didomi (gestionnaire de consentement cookies)",
    "fonts.googleapis":   "Google Fonts",
    "fonts.gstatic":      "Google Fonts",
    "tolk.ai":            "Tolk.ai (chatbot)",
    "intercom":           "Intercom (chatbot)",
    "zendesk":            "Zendesk (support)",
    "crisp.chat":         "Crisp (chatbot)",
    "recaptcha":          "reCAPTCHA (Google)",
    "hcaptcha":           "hCaptcha",
    "liveidentity":       "LiveIdentity (CAPTCHA)",
    "dsfr":               "DSFR (Design Système de l'État)",
    "bootstrap":          "Bootstrap (framework UI)",
    "tailwind":           "Tailwind (framework UI)",
    "jquery-ui":          "jQuery UI",
    "jquery":             "jQuery",
    "react":              "React",
    "vue":                "Vue.js",
}                                       # genericite: ok-fin


def classify(url):
    """Type d'une ressource Coverage, déduit du CHEMIN de l'URL.

    Les entrées Coverage ne portent pas de mimeType (clés : url, ranges, text),
    l'extension est donc le seul signal disponible. La query et le fragment sont
    retirés avant le test, sinon toute URL versionnée est mal classée.
    """
    path = urlparse(url).path
    if path.endswith((".js", ".mjs")):
        return "javascript"
    if path.endswith(".css"):
        return "css"
    return "other"


def read_entries(cov_path):
    """Lit un fichier Coverage. Deux formats selon la version de DevTools :
    tableau direct, ou objet enveloppé sous la clé "entries"."""
    with open(cov_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    raise ValueError(
        f"{cov_path.name} : format Coverage non reconnu. Attendu un tableau, "
        f'ou un objet avec la clé "entries". Trouvé : {type(data).__name__}.'
    )


def measure(entries):
    """Mesure une page : (liste de ressources, agrégats par type)."""
    resources = []
    for item in entries:
        url = item.get("url", "")
        total = len(item.get("text", "") or "")
        used = sum(
            r["end"] - r["start"]
            for r in item.get("ranges", [])
            if "start" in r and "end" in r
        )
        resources.append({
            "url": url,
            "type": classify(url),
            "total_bytes": total,
            "unused_bytes": total - used,
        })
    return resources


def aggregate(resources, rtype):
    total = sum(r["total_bytes"] for r in resources if r["type"] == rtype)
    unused = sum(r["unused_bytes"] for r in resources if r["type"] == rtype)
    return {
        "total_kb": round(total / 1024, 1),
        "unused_kb": round(unused / 1024, 1),
        "unused_pct": round(unused / total * 100, 2) if total else 0.0,
    }


def page_label(entries, har_documents):
    """URL de la page chargée, corroborée par le HAR quand c'est possible.

    Le HAR dit lesquelles de ces URLs ont réellement été servies en text/html.
    Sans lui, une URL technique (jeton anti-CSRF, endpoint de messages) peut
    passer pour la page : elle n'a pas d'extension d'asset et arrive en premier.
    """
    candidates = []
    domains = Counter()
    for item in entries:
        url = item.get("url", "")
        if url.startswith("http"):
            domains[urlparse(url).netloc] += 1
    main_domain = domains.most_common(1)[0][0] if domains else ""

    for item in entries:
        url = item.get("url", "")
        if not url.startswith("http"):
            continue
        if urlparse(url).netloc != main_domain:
            continue
        if not ASSET_EXTS.search(urlparse(url).path):
            candidates.append(url)

    # Priorité au candidat que le HAR déclare comme document HTML.
    for url in candidates:
        if url.split("?")[0] in har_documents:
            return url, "document HTML confirmé par le HAR"
    if candidates:
        return candidates[0], "URL sans extension d'asset (non confirmée par le HAR)"
    return "", "aucune URL de page identifiable"


def har_document_urls(source_dir):
    """URLs servies en text/html d'après le HAR, s'il est trouvable."""
    har_files = (sorted(source_dir.glob("*.har"))
                 or sorted((source_dir / RAW_DATA_DIR).glob("*.har")))
    if not har_files:
        return set(), None
    with open(har_files[0], encoding="utf-8") as f:
        har = json.load(f)
    docs = set()
    for e in har.get("log", {}).get("entries", []):
        mime = e.get("response", {}).get("content", {}).get("mimeType", "")
        if "html" in mime.lower():
            docs.add(e.get("request", {}).get("url", "").split("?")[0])
    return docs, har_files[0]


def detect_libraries(all_resources):
    found = {}
    for r in all_resources:
        low = r["url"].lower()
        for needle, label in KNOWN_LIBRARIES.items():
            if needle in low:
                found[label] = True
    return sorted(found)


def find_coverage_files(source_dir):
    return (sorted(source_dir.glob("Coverage-*.json"))
            or sorted(source_dir.glob("*coverage*.json"))
            or sorted((source_dir / RAW_DATA_DIR).glob("Coverage-*.json"))
            or sorted((source_dir / RAW_DATA_DIR).glob("*coverage*.json")))


def analyse(source_dir):
    source_dir = Path(source_dir)
    cov_files = [c for c in find_coverage_files(source_dir)
                 if c.name != "coverage-analysis.json"]
    if not cov_files:
        raise FileNotFoundError(
            f"Aucun fichier Coverage-*.json dans {source_dir} ni dans "
            f"{source_dir / RAW_DATA_DIR}."
        )

    har_docs, har_path = har_document_urls(source_dir)

    pages, all_resources = [], []
    for i, cf in enumerate(cov_files, 1):
        entries = read_entries(cf)
        resources = measure(entries)
        all_resources.extend(resources)
        url, provenance = page_label(entries, har_docs)

        js, css = aggregate(resources, "javascript"), aggregate(resources, "css")
        # Un fichier Coverage non vide qui ne produit aucun octet JS/CSS est un
        # signe de mauvaise classification, pas une page sans code. On le dit.
        anomaly = (bool(entries) and js["total_kb"] == 0 and css["total_kb"] == 0)

        pages.append({
            "name": f"Page {i}",
            "source_file": cf.name,
            "url": url,
            "url_provenance": provenance,
            "js_total_kb": js["total_kb"],
            "js_unused_kb": js["unused_kb"],
            "js_unused_pct": js["unused_pct"],
            "css_total_kb": css["total_kb"],
            "css_unused_kb": css["unused_kb"],
            "css_unused_pct": css["unused_pct"],
            "resources_count": len(resources),
            "no_js_no_css": anomaly,
            "top_js_unused": [
                {"url": r["url"], "unused_kb": round(r["unused_bytes"] / 1024, 1)}
                for r in sorted((r for r in resources if r["type"] == "javascript"),
                                key=lambda r: -r["unused_bytes"])[:5]
            ],
            "top_css_unused": [
                {"url": r["url"], "unused_kb": round(r["unused_bytes"] / 1024, 1)}
                for r in sorted((r for r in resources if r["type"] == "css"),
                                key=lambda r: -r["unused_bytes"])[:3]
            ],
        })

    js_all, css_all = aggregate(all_resources, "javascript"), aggregate(all_resources, "css")

    # Outlier : page dont le code total dépasse 2x la médiane.
    weights = sorted(p["js_total_kb"] + p["css_total_kb"] for p in pages)
    n = len(weights)
    median = weights[n // 2] if n % 2 else (weights[n // 2 - 1] + weights[n // 2]) / 2
    outliers = [p["name"] for p in pages
                if median and (p["js_total_kb"] + p["css_total_kb"]) > 2 * median]

    return {
        "pages": pages,
        "summary": {
            "pages_count": len(pages),
            "total_js_kb": js_all["total_kb"],
            "total_js_unused_kb": js_all["unused_kb"],
            "total_js_unused_pct": js_all["unused_pct"],
            "total_css_kb": css_all["total_kb"],
            "total_css_unused_kb": css_all["unused_kb"],
            "total_css_unused_pct": css_all["unused_pct"],
            "third_party_libraries": detect_libraries(all_resources),
            "outlier_pages": outliers,
            "har_reference": har_path.name if har_path else None,
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_dir", type=Path)
    ap.add_argument("--output", type=Path,
                    help="chemin de sortie (défaut : <source_dir>/audit/"  # genericite: ok - convention de rangement du skill, aucun site nommé
                         "coverage-analysis.json)")
    ap.add_argument("--check", action="store_true",
                    help="compare à la sortie existante sans rien écrire")
    args = ap.parse_args(argv)

    result = analyse(args.source_dir)

    out = args.output or (args.source_dir / "audit" / "coverage-analysis.json")
    s = result["summary"]

    har_note = (f" — HAR de référence : {s['har_reference']}" if s["har_reference"]
                else " — aucun HAR trouvé, libellés non corroborés")
    print(f"Coverage : {s['pages_count']} fichier(s){har_note}")
    for p in result["pages"]:
        flag = "  [!] aucun JS ni CSS" if p["no_js_no_css"] else ""
        print(f"  {p['name']}  JS {p['js_total_kb']:9.1f} Ko "
              f"(non utilisé {p['js_unused_kb']:8.1f})   "
              f"CSS {p['css_total_kb']:8.1f} Ko "
              f"(non utilisé {p['css_unused_kb']:8.1f}){flag}")
        print(f"          {p['url'] or '(page non identifiée)'}")
    print(f"  TOTAL    JS {s['total_js_kb']:9.1f} Ko "
          f"(non utilisé {s['total_js_unused_kb']:8.1f}, {s['total_js_unused_pct']}%)   "
          f"CSS {s['total_css_kb']:8.1f} Ko "
          f"(non utilisé {s['total_css_unused_kb']:8.1f}, {s['total_css_unused_pct']}%)")

    if args.check:
        if not out.exists():
            print(f"\n[check] {out} absent, rien à comparer.")
            return 0
        with open(out, encoding="utf-8") as f:
            old = json.load(f)
        o = old.get("summary", {})
        print("\n[check] écarts avec la sortie existante :")
        diffs = 0
        for key in ("total_js_kb", "total_js_unused_kb", "total_css_kb", "total_css_unused_kb"):
            before, after = o.get(key), s[key]
            if before != after:
                diffs += 1
                print(f"  {key} : {before} -> {after}")
        print("  aucun écart." if not diffs else f"  {diffs} écart(s).")
        return 1 if diffs else 0

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print(f"\ncoverage-analysis.json écrit — {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
