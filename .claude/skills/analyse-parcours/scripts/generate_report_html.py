#!/usr/bin/env python3
"""
Génère un rapport HTML d'audit de parcours web.
Structure calquée sur le rapport PDF ANTS (generate_pdf.py).
Palette OCTO.

Usage :
  python3 generate_report_html.py <dossier-audit> [--output rapport.html]

Le dossier doit contenir :
  - 1 fichier .har
  - 1+ fichiers Coverage-*.json
  - cwv.json (optionnel)
"""

import base64
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

# ── Palette OCTO ──────────────────────────────────────────────────────────────
OCTO_DARK      = "#1C2856"
OCTO_BLUE      = "#5BA1BC"
OCTO_LIGHT     = "#82C1DD"
OCTO_PALE      = "#E0F0F4"
OCTO_GREY      = "#ECECF2"
OCTO_WHITE     = "#FFFFFF"

# Couleurs par type de ressource
TYPE_COLORS = {
    "javascript": "#f0ad4e",
    "css":        "#5bc0de",
    "image":      "#5cb85c",
    "font":       "#d9534f",
    "html":       "#337ab7",
    "json":       "#9b59b6",
    "video":      "#e67e22",
    "pdf":        "#c0392b",
    "other":      "#95a5a6",
}

# Palette de statut (bon/moyen/mauvais/neutre), utilisée pour les badges de
# conformité GreenIT, les niveaux de confiance et les Core Web Vitals. Couleurs
# choisies pour un contraste >= 4.5:1 (WCAG AA) sur fond blanc (texte coloré) ET
# sur fond coloré (texte blanc) — les teintes plus claires historiques (ex.
# #0cce6b, #ffa400, #5bc0de) étaient sous ce seuil. Un emoji accompagne toujours
# le statut : la couleur seule ne doit jamais porter l'information (accessibilité
# daltonisme/lecteur d'écran/impression N&B).
STATUS_GOOD    = "#1e7e34"   # vert foncé — ✅
STATUS_WARN    = "#9a4d00"   # orange foncé — ⚠️
STATUS_BAD     = "#c0392b"   # rouge foncé — 🔴
STATUS_NEUTRAL = "#5a5a5a"   # gris moyen foncé — ➖ (non mesuré / non applicable)
STATUS_EMOJI = {"good": "✅", "warn": "⚠️", "bad": "🔴", "neutral": "➖"}

# Fonds clairs assortis (style "chip" : fond clair + bordure + texte/emoji coloré),
# utilisés à la place des anciens badges fond saturé + texte blanc. Un emoji coloré
# (ex. ✅ vert Unicode, 🔴 rouge Unicode) devient quasi invisible sur un fond saturé
# de la MÊME couleur (peu de contraste emoji/fond) ; sur fond clair, l'emoji garde
# sa couleur Unicode propre et reste toujours lisible.
STATUS_BG = {
    "good": "#e8f5e9", "warn": "#fff3e0", "bad": "#fdecea", "neutral": "#eeeeee",
}


def _status_chip(status, text, extra_style=""):
    """Badge style "chip" (fond clair + bordure + texte/emoji coloré) pour un
    statut good/warn/bad/neutral. Contraste vérifié >= 4.5:1 (texte sur fond clair)
    ET emoji toujours visible (jamais posé sur un fond de sa propre couleur)."""
    color = {"good": STATUS_GOOD, "warn": STATUS_WARN, "bad": STATUS_BAD,
             "neutral": STATUS_NEUTRAL}[status]
    bg = STATUS_BG[status]
    emoji = STATUS_EMOJI[status]
    return (f'<span style="background:{bg};border:1.5px solid {color};color:{color};'
            f'font-weight:bold;padding:1px 8px;border-radius:4px;font-size:13px;'
            f'white-space:nowrap;{extra_style}">{emoji} {text}</span>')

# Domaines de trackers/analytics tiers connus (fusion avec les catégories
# "Analytics"/"Balise / Tag manager" de detect_tech.py — les deux listes
# visent le même périmètre mais sont maintenues séparément selon leur usage :
# ici pour compter/chiffrer, dans detect_tech.py pour qualifier la stack).
TRACKER_DOMAINS = {
    "google-analytics.com", "analytics.google.com", "googletagmanager.com",
    "hotjar.com", "segment.io", "mixpanel.com", "amplitude.com", "heap.io",
    "clarity.ms", "swetrix.org", "matomo.org", "plausible.io",
    "doubleclick.net", "facebook.net", "connect.facebook.net",
}
TRACKER_PATHS = {"/log/", "/log/hb", "/hb", "/ping", "/beacon", "/collect", "/track", "/event"}


def _is_tracker(host, url):
    """True si l'hôte/chemin correspond à un tracker/analytics tiers connu."""
    if host in TRACKER_DOMAINS or any(t in host for t in
            ("analytics", "swetrix", "gtm", "hotjar", "segment", "mixpanel", "clarity")):
        return True
    path = url.split("?")[0].lower()
    return any(p in path for p in TRACKER_PATHS)


# ── Version Agent EROOM (source de vérité : SKILL.md) ────────────────────────
_skill_md = Path(__file__).parent.parent / "SKILL.md"
AGENT_VERSION = "?.?.?"
if _skill_md.exists():
    for _line in _skill_md.read_text(encoding="utf-8").splitlines():
        if _line.startswith("version:"):
            AGENT_VERSION = _line.split(":", 1)[1].strip()
            break

# ── Imports EcoIndex ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from har_metrics import extract_page_metrics, load_cwv


# ── Noms de pays (affichage) ────────────────────────────────────────────────
# Correspondance code ISO-2 -> nom français, pour les 30 pays des tables
# iOS/macOS de collect_env_data.py. Purement cosmétique (le calcul utilise les
# codes). Un pays absent retombe sur son code brut.
_COUNTRY_NAMES = {
    "FR": "France", "DE": "Allemagne", "GB": "Royaume-Uni", "IE": "Irlande",
    "NL": "Pays-Bas", "BE": "Belgique", "CH": "Suisse", "AT": "Autriche",
    "ES": "Espagne", "IT": "Italie", "PT": "Portugal", "PL": "Pologne",
    "SE": "Suède", "NO": "Norvège", "DK": "Danemark", "FI": "Finlande",
    "RU": "Russie", "US": "États-Unis", "CA": "Canada", "MX": "Mexique",
    "BR": "Brésil", "JP": "Japon", "KR": "Corée du Sud", "CN": "Chine",
    "IN": "Inde", "AU": "Australie", "ZA": "Afrique du Sud", "SN": "Sénégal",
    "TN": "Tunisie", "MA": "Maroc",
}


def _country_label(code):
    """'BR' -> 'Brésil (BR)'. Code inconnu -> le code seul."""
    cc = (code or "").upper()
    name = _COUNTRY_NAMES.get(cc)
    return f"{name} ({cc})" if name else (cc or "?")


# ── Parsing HAR ───────────────────────────────────────────────────────────────

def _classify_type(mime, url):
    mime = (mime or "").lower()
    url  = (url  or "").lower()
    if "javascript" in mime or url.endswith(".js"):
        return "javascript"
    if "css" in mime or url.endswith(".css"):
        return "css"
    if "html" in mime:
        return "html"
    if "image" in mime or re.search(r'\.(png|jpg|jpeg|gif|svg|webp|ico|jxl)$', url):
        return "image"
    if "font" in mime or re.search(r'\.(woff2?|ttf|otf|eot)$', url):
        return "font"
    if "video" in mime or re.search(r'\.(mp4|webm|ogv|mov|avi)$', url):
        return "video"
    if "pdf" in mime or url.endswith(".pdf"):
        return "pdf"
    if "json" in mime or url.endswith(".json"):
        return "json"
    return "other"


def parse_har(har_path):
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)
    return har


def har_traffic_analysis(har_data):
    """Analyse du trafic : domaines, codes HTTP, top ressources, doublons."""
    entries = har_data.get("log", {}).get("entries", [])

    domains = defaultdict(int)
    http_codes = defaultdict(int)
    resources = []
    url_counts = defaultdict(int)
    # Stocker les headers de réponse par URL pour analyser le cache
    url_resp_headers = {}

    _FONT_DOMAINS  = {"fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net", "use.fontawesome.com"}

    def _dup_category(url, host, hdrs_resp):
        from urllib.parse import urlparse as _up
        path = _up(url).path.lower()
        # Tracker / analytics
        if _is_tracker(host, url):
            return "tracker", "Requête analytics/tracker — comportement normal, envoi répété intentionnel"
        # Police externe
        if host in _FONT_DOMAINS or "font" in host:
            return "font", "Police externe — absence de cache navigateur entre les pages"
        # Ressource statique : vérifier cache-control
        cc = hdrs_resp.get("cache-control", "")
        has_long_cache = "max-age" in cc and any(
            int(v) >= 3600 for v in re.findall(r"max-age=(\d+)", cc)
        ) if "max-age" in cc else False
        rtype = _classify_type("", url)
        if rtype in ("javascript", "css", "image", "font"):
            if has_long_cache:
                return "static_cached", "Ressource statique avec cache long — rechargement dû au parcours multi-pages (normal)"
            else:
                return "static_no_cache", "Ressource statique SANS cache long — retéléchargée à chaque page, ajouter Cache-Control: max-age"
        return "other", "URL appelée plusieurs fois — vérifier si intentionnel"

    for e in entries:
        req  = e.get("request", {})
        resp = e.get("response", {})
        url  = req.get("url", "")
        status = resp.get("status", 0)
        size   = resp.get("content", {}).get("size", 0)
        mime   = resp.get("content", {}).get("mimeType", "")
        hdrs_resp = {h["name"].lower(): h["value"] for h in resp.get("headers", [])}

        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc
        except Exception:
            host = url[:40]

        domains[host] += 1
        http_codes[status] += 1
        url_counts[url] += 1
        resources.append({"url": url, "size": size, "mime": mime, "status": status, "host": host})
        if url not in url_resp_headers:
            url_resp_headers[url] = hdrs_resp

    # Dédupliquer par URL avant le classement (garder la taille max observée)
    seen_urls = {}
    for r in resources:
        url_key = r["url"].split("?")[0]
        if url_key not in seen_urls or r["size"] > seen_urls[url_key]["size"]:
            seen_urls[url_key] = r
    top10 = sorted(seen_urls.values(), key=lambda x: x["size"], reverse=True)[:10]

    # Doublons enrichis avec catégorie et cause
    duplicates = []
    for u, c in url_counts.items():
        if c <= 1:
            continue
        try:
            host = urlparse(u).netloc
        except Exception:
            host = ""
        hdrs = url_resp_headers.get(u, {})
        cat, cause = _dup_category(u, host, hdrs)
        duplicates.append({"url": u, "count": c, "category": cat, "cause": cause})

    # Trackers/scripts tiers (Lot 2) : nombre de requêtes + poids cumulé,
    # calculés sur les requêtes brutes (pas dédupliquées par URL, pour refléter
    # le trafic réseau réel généré, doublons de tracking inclus).
    tracker_entries = [r for r in resources if _is_tracker(r["host"], r["url"])]
    total_size = sum(r["size"] for r in resources) or 1
    trackers = {
        "count": len(tracker_entries),
        "size_ko": round(sum(r["size"] for r in tracker_entries) / 1024, 1),
        "pct_requests": round(len(tracker_entries) / len(resources) * 100, 1) if resources else 0,
        "pct_size": round(sum(r["size"] for r in tracker_entries) / total_size * 100, 1),
        "domains": sorted({r["host"] for r in tracker_entries}),
    }

    return {
        "total_req": len(entries),
        "total_ko": round(sum(r["size"] for r in resources) / 1024, 1),
        "domains": dict(sorted(domains.items(), key=lambda x: -x[1])),
        "http_codes": dict(http_codes),
        "top10": top10,
        "duplicates": duplicates,
        "trackers": trackers,
    }


# ── Parsing Coverage ──────────────────────────────────────────────────────────

def parse_coverage_file(cov_path):
    with open(cov_path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data if isinstance(data, list) else data.get("entries", [])
    results = []

    for item in entries:
        url    = item.get("url", "")
        text   = item.get("text", "") or ""
        ranges = item.get("ranges", [])
        total  = len(text)
        used   = sum(r["end"] - r["start"] for r in ranges if "end" in r and "start" in r)
        unused = total - used
        pct    = round(unused / total * 100, 1) if total > 0 else 0.0
        mime   = item.get("mimeType", "")
        rtype  = _classify_type(mime, url)

        results.append({
            "url":        url,
            "filename":   url.split("/")[-1].split("?")[0][:60] or url[:60],
            "type":       rtype,
            "total_kb":   round(total / 1024, 1),
            "used_kb":    round(used / 1024, 1),
            "unused_kb":  round(unused / 1024, 1),
            "unused_pct": pct,
        })

    return results


def coverage_summary(entries):
    js  = [e for e in entries if e["type"] == "javascript"]
    css = [e for e in entries if e["type"] == "css"]

    def _agg(lst):
        total  = sum(e["total_kb"]  for e in lst)
        unused = sum(e["unused_kb"] for e in lst)
        pct    = round(unused / total * 100, 1) if total > 0 else 0.0
        return {"total_kb": round(total, 1), "unused_kb": round(unused, 1), "pct": pct}

    return {"js": _agg(js), "css": _agg(css), "all": _agg(entries)}


# ── Images : compression AVIF + intégration base64 ───────────────────────────

def embed_image(source, alt="", max_dim=500):
    """
    Compresse une image (URL ou chemin local) en AVIF 500×500 max et retourne
    le bloc HTML <figure> avec le base64 inline.

    Retourne une chaîne HTML vide si vipsthumbnail n'est pas disponible ou si
    la source est inaccessible.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = Path(tmpdir) / "orig"
            avif = Path(tmpdir) / "out.avif"

            # Téléchargement ou copie
            src = str(source)
            if src.startswith("http://") or src.startswith("https://"):
                urllib.request.urlretrieve(src, orig)
            else:
                orig = Path(source)
                if not orig.exists():
                    return ""

            # Dimensions originales
            r = subprocess.run(
                ["vipsheader", "-f", "width", str(orig), "-f", "height", str(orig)],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                return ""
            dims = r.stdout.strip().split()
            orig_w, orig_h = (int(dims[0]), int(dims[1])) if len(dims) == 2 else (0, 0)

            # Compression AVIF
            size_arg = f"{max_dim}x{max_dim}>"
            r2 = subprocess.run(
                ["vipsthumbnail", str(orig), "--size", size_arg,
                 "-o", f"{avif}[Q=60,effort=9,keep=none]"],
                capture_output=True
            )
            if r2.returncode != 0 or not avif.exists():
                return ""

            # Dimensions compressées
            r3 = subprocess.run(
                ["vipsheader", "-f", "width", str(avif), "-f", "height", str(avif)],
                capture_output=True, text=True
            )
            dims2 = r3.stdout.strip().split()
            comp_w, comp_h = (int(dims2[0]), int(dims2[1])) if len(dims2) == 2 else (orig_w, orig_h)

            b64 = base64.b64encode(avif.read_bytes()).decode()

        resized = (orig_w != comp_w or orig_h != comp_h) and orig_w > 0
        caption = (
            f"(Pour ce rapport image redimensionnée : {orig_w}×{orig_h} → {comp_w}×{comp_h} px et version allègement du fichier au format AVIF)"
            if resized else
            "(Pour ce rapport : version allègement du fichier au format AVIF)"
        )
        return (
            f'<figure style="margin:0.75rem 0; text-align:center;">'
            f'<img src="data:image/avif;base64,{b64}" alt="{alt}" '
            f'style="max-width:100%; max-height:{max_dim}px; border:1px solid #e0e0e0; border-radius:4px;">'
            f'<figcaption style="font-size:0.78rem; color:#9e9e9e; margin-top:0.3rem;">{caption}</figcaption>'
            f'</figure>'
        )
    except Exception:
        return ""


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _html_head(title):
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --octo-dark:  {OCTO_DARK};
    --octo-blue:  {OCTO_BLUE};
    --octo-light: {OCTO_LIGHT};
    --octo-pale:  {OCTO_PALE};
    --octo-grey:  {OCTO_GREY};
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; font-size: 18px; color: #222; background: #f9f9f9; }}
  header {{ background: var(--octo-dark); color: white; padding: 32px 40px 24px; }}
  header h1 {{ font-size: 28px; font-weight: bold; margin-bottom: 6px; }}
  header .meta {{ font-size: 16px; opacity: .75; margin-top: 8px; }}
  nav[role="navigation"] {{ background: var(--octo-pale); border-bottom: 2px solid var(--octo-blue);
    padding: 14px 40px; }}
  nav[role="navigation"] h2 {{ font-size: 17px; font-weight: bold; color: var(--octo-dark);
    margin-bottom: 8px; border: none; padding: 0; }}
  nav[role="navigation"] ul {{ display: flex; flex-wrap: wrap; align-items: flex-start; gap: 6px 20px; padding: 0;
    margin: 0; font-size: 17px; list-style: none; }}
  nav[role="navigation"] a {{ color: var(--octo-dark); text-decoration: none; }}
  nav[role="navigation"] a:hover {{ text-decoration: underline; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px; }}
  section {{ margin-bottom: 40px; }}
  h2 {{ font-size: 22px; color: var(--octo-dark); border-left: 4px solid var(--octo-blue);
        padding-left: 12px; margin-bottom: 16px; margin-top: 4px; }}
  h3 {{ font-size: 18px; color: var(--octo-dark); margin: 16px 0 8px; font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 17px; margin-bottom: 12px; }}
  th {{ background: var(--octo-dark); color: white; padding: 7px 10px; text-align: left; font-size: 16px; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #ddd; }}
  tr:nth-child(even) td {{ background: var(--octo-pale); }}
  tr.alert td {{ background: #ffe0e0; }}
  tr.bold td {{ background: #dde8f0; font-weight: bold; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-weight: bold; font-size: 17px; color: white; min-width: 32px; text-align: center; }}
  .bar-wrap {{ display: flex; height: 16px; border-radius: 3px; overflow: hidden; width: 120px; }}
  .bar-used   {{ background: #50b450; }}
  .bar-unused {{ background: #dc5050; }}
  .kpi-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
  .kpi {{ background: var(--octo-pale); border: 1px solid var(--octo-blue); border-radius: 6px;
          padding: 14px 20px; min-width: 140px; }}
  .kpi .val {{ font-size: 26px; font-weight: bold; color: var(--octo-dark); }}
  .kpi .lbl {{ font-size: 15px; color: #555; margin-top: 2px; }}
  .prio {{ margin: 6px 0; padding: 10px 14px; border-radius: 4px; font-size: 17px; }}
  .prio-1 {{ background: #ffe0e0; border-left: 4px solid #dc3545; }}
  .prio-2 {{ background: #fff3cd; border-left: 4px solid #fd7e14; }}
  .prio-3 {{ background: #d4edda; border-left: 4px solid #28a745; }}
  .domain-tag {{ display: inline-block; background: var(--octo-grey); border-radius: 3px;
                 padding: 1px 6px; font-size: 15px; margin: 2px; }}
  footer {{ text-align: center; padding: 20px; font-size: 15px; color: #888;
            border-top: 1px solid #ddd; margin-top: 40px; }}
  @media print {{ body {{ background: white; }} header {{ -webkit-print-color-adjust: exact; }} }}
</style>
</head>
<body>
"""


def _badge(grade, color):
    return f'<span class="badge" style="background:{color}">{grade}</span>'


def _bar(used_pct):
    unused_pct = 100 - used_pct
    return (f'<div class="bar-wrap">'
            f'<div class="bar-used" style="width:{used_pct:.0f}%"></div>'
            f'<div class="bar-unused" style="width:{unused_pct:.0f}%"></div>'
            f'</div>')


def _dedup_page_metrics(page_metrics):
    """Déduplique par URL canonique : garde la ligne avec DOM non-zéro, sinon la plus lourde.
    Ajoute un champ page_num (1-indexé) dans l'ordre de première apparition."""
    seen = {}
    order = []
    for m in page_metrics:
        url = m["title"].split("?")[0].rstrip("/") or m["title"]
        prev = seen.get(url)
        if prev is None:
            seen[url] = m
            order.append(url)
        else:
            if m["dom"] > 0 and prev["dom"] == 0:
                seen[url] = m
            elif m["dom"] > 0 and prev["dom"] > 0 and m["req"] > prev["req"]:
                seen[url] = m
            elif m["dom"] == 0 and prev["dom"] == 0 and m["req"] > prev["req"]:
                seen[url] = m
    result = []
    for i, url in enumerate(order, 1):
        m = dict(seen[url])
        m["page_num"] = i
        result.append(m)
    return result


def _cwv_for_page(m, cwv):
    """Cherche les données CWV d'une page (dict groupé par stratégie).

    Retourne {"mobile": row, "desktop": row} (clés éventuellement absentes),
    d'abord par URL (normalisée) puis par page_id."""
    url = m.get("title", "").rstrip("/")
    return cwv.get(url) or cwv.get(m["page_id"], {})


def _cwv_device_marker(strat):
    """Pictogramme d'appareil pour annoter d'où provient une valeur retenue."""
    return "📱" if strat == "mobile" else "🖥"


def _cwv_worst_per_metric(by_strategy):
    """Compose un row synthétique en prenant, pour CHAQUE métrique (lcp/inp/cls),
    la valeur la PIRE parmi les stratégies disponibles (mobile / desktop).

    Pour les trois CWV, "pire" = valeur la plus élevée (LCP/INP/CLS : plus haut =
    plus mauvais). À valeur égale, le mobile est préféré (trafic dominant + conditions
    les plus contraignantes).

    Retourne (row, strat_by_metric) où :
      - row = {"lcp": .., "inp": .., "cls": ..} (clés présentes seulement si mesurées) ;
      - strat_by_metric = {"lcp": "mobile"|"desktop", ...} indiquant l'appareil retenu
        pour chaque métrique.
    Retourne (None, {}) si aucune donnée exploitable."""
    if not by_strategy:
        return None, {}
    row = {}
    strat_by_metric = {}
    for metric in ("lcp", "inp", "cls"):
        best_strat = None
        best_val = None
        for strat in ("mobile", "desktop"):  # mobile d'abord => gagne à égalité
            r = by_strategy.get(strat)
            if not r:
                continue
            v = r.get(metric)
            if not isinstance(v, (int, float)):
                continue
            if best_val is None or v > best_val:
                best_val = v
                best_strat = strat
        if best_strat is not None:
            row[metric] = best_val
            strat_by_metric[metric] = best_strat
    if not row:
        return None, {}
    return row, strat_by_metric


# Libellés lisibles des sources CWV (distingue terrain / lab API / lab local).
_CWV_SOURCE_LABELS = {
    "crux": ("terrain", STATUS_GOOD, "CrUX terrain (utilisateurs Chrome réels, via PageSpeed)"),
    "pagespeed_lab": ("lab", STATUS_WARN, "Lab PageSpeed (simulation via l'API PSI)"),
    "lighthouse": ("lab local", STATUS_WARN, "Lab Lighthouse (simulation en local)"),
}


_STATUS_BY_COLOR = {STATUS_GOOD: "good", STATUS_WARN: "warn", STATUS_NEUTRAL: "neutral"}


def _cwv_source_badge(source):
    """Petit badge indiquant la source réelle d'une mesure CWV (style "chip")."""
    label, color, _ = _CWV_SOURCE_LABELS.get(source, ("?", STATUS_NEUTRAL, "Source inconnue"))
    bg = STATUS_BG[_STATUS_BY_COLOR.get(color, "neutral")]
    return (f'<span style="display:inline-block;font-size:13px;padding:1px 7px;'
            f'border-radius:10px;background:{bg};border:1.5px solid {color};'
            f'color:{color};font-weight:bold">{label}</span>')


def _section_dashboard(page_metrics, cwv):
    deduped = _dedup_page_metrics(page_metrics)
    rows = ""
    for m in deduped:
        badge = _badge(m["grade"], m["grade_color"])
        url = m["title"]
        from urllib.parse import urlparse
        parsed = urlparse(url)
        short = parsed.path.rstrip("/") or "/"
        num = m.get("page_num", "")
        page_cell = f'<a href="{url}" target="_blank" rel="noopener" title="{url}"><span style="color:#888;font-size:15px;margin-right:4px">P{num}</span>{short}</a>'
        # Dashboard = "pire des deux" par métrique (mobile ou desktop, le plus mauvais).
        cwv_data, worst_strat = _cwv_worst_per_metric(_cwv_for_page(m, cwv))

        def _cwv_cell(val, unit, thresholds, strat=None):
            # thresholds = (good_max, needs_improvement_max)
            if not isinstance(val, (int, float)):
                return f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'
            if val <= thresholds[0]:
                color, emoji = STATUS_GOOD, STATUS_EMOJI["good"]
            elif val <= thresholds[1]:
                color, emoji = STATUS_WARN, STATUS_EMOJI["warn"]
            else:
                color, emoji = STATUS_BAD, STATUS_EMOJI["bad"]
            # Pictogramme indiquant l'appareil dont vient la valeur retenue (pire des deux)
            marker = (f'<span style="color:#999;font-size:12px;margin-right:3px" '
                      f'title="valeur la plus défavorable : {strat}">{_cwv_device_marker(strat)}</span>'
                      if strat else "")
            return (f'<td style="text-align:right;color:{color};font-weight:bold">'
                    f'{emoji} {marker}{val} {unit}</td>')

        if cwv_data:
            lcp_val = cwv_data.get("lcp")
            inp_val = cwv_data.get("inp")
            cls_num = cwv_data.get("cls")
            lcp_cell = _cwv_cell(lcp_val, "s", (1.8, 2.5), worst_strat.get("lcp"))
            inp_cell = _cwv_cell(inp_val, "ms", (200, 500), worst_strat.get("inp"))
            cls_cell = _cwv_cell(cls_num, "", (0.1, 0.25), worst_strat.get("cls"))
        else:
            lcp_cell = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">{m["on_load_ms"]} ms *</td>'
            inp_cell = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'
            cls_cell = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'

        rows += f"""<tr>
      <td>{page_cell}</td>
      <td style="text-align:center">{badge} {m['ecoindex']}/100</td>
      <td style="text-align:right">{m['req']}</td>
      <td style="text-align:right">{m['size_ko']:.0f} Ko</td>
      <td style="text-align:right">{m['dom']}</td>
      {lcp_cell}{inp_cell}{cls_cell}
    </tr>"""

    cwv_legend = f"""<div style="font-size:15px;margin-top:8px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">
    <span style="font-weight:bold;color:#555">Légende CWV :</span>
    <span style="color:{STATUS_GOOD}">{STATUS_EMOJI['good']} Bon</span>
    <span style="color:{STATUS_WARN}">{STATUS_EMOJI['warn']} A améliorer</span>
    <span style="color:{STATUS_BAD}">{STATUS_EMOJI['bad']} Mauvais</span>
    <span style="color:#999">📱/🖥 appareil de la valeur la plus défavorable (pire des deux par métrique)</span>
    <span style="color:{STATUS_NEUTRAL};font-style:italic">{STATUS_EMOJI['neutral']} Données terrain non disponibles (fournir cwv.json)</span>
  </div>"""
    cwv_note = "" if cwv else '<p style="font-size:15px;color:#888;margin-top:6px">* LCP = onLoad HAR (proxy). INP et CLS nécessitent des données terrain (API PageSpeed ou cwv.json).</p>'

    return f"""<section id="dashboard">
  <h2>Tableau de bord EcoIndex et CWV (Core Web Vitals)</h2>
  <table>
    <thead><tr>
      <th>Page</th><th>EcoIndex</th><th>Requêtes</th>
      <th>Poids</th><th>DOM</th><th>LCP</th><th>INP</th><th>CLS</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {cwv_legend}
  {cwv_note}
</section>"""


def _section_traffic(traffic):
    domains_html = "".join(
        f'<span class="domain-tag">{d} <b>({c})</b></span>'
        for d, c in list(traffic["domains"].items())[:15]
    )

    CODE_LABELS = {
        200: ("Succès", "Ressource chargée normalement"),
        201: ("Créé", "Requête API acceptée (POST)"),
        204: ("Vide OK", "Réponse sans contenu, souvent des pings analytics"),
        206: ("Partiel", "Contenu partiel (streaming, range request)"),
        301: ("Redirection permanente", "URL déplacée définitivement"),
        302: ("Redirection temporaire", "URL redirigée (ex: /recrutement → /recrutement/)"),
        304: ("Non modifié (cache)", "Ressource en cache navigateur, non retéléchargée"),
        400: ("Requête invalide", "Erreur côté client"),
        401: ("Non authentifié", "Accès refusé, authentification requise"),
        403: ("Accès refusé", "Serveur bloque la requête"),
        404: ("Introuvable", "Ressource absente sur le serveur"),
        500: ("Erreur serveur", "Problème côté serveur"),
        503: ("Service indisponible", "Serveur temporairement hors service"),
    }
    codes_rows = ""
    for k, v in sorted(traffic["http_codes"].items()):
        color = "green" if k < 300 else ("orange" if k < 400 else "red")
        label, desc = CODE_LABELS.get(k, ("", ""))
        codes_rows += (
            f'<tr>'
            f'<td><b style="color:{color}">{k}</b></td>'
            f'<td style="text-align:right"><b>{v}</b></td>'
            f'<td>{label}</td>'
            f'<td style="color:#555;font-size:16px">{desc}</td>'
            f'</tr>'
        )
    codes_html = f"""<table style="border-collapse:collapse;width:100%">
  <thead><tr>
    <th style="text-align:left;width:60px">Code</th>
    <th style="text-align:right;width:50px">Nb</th>
    <th style="text-align:left;width:160px">Statut</th>
    <th style="text-align:left">Signification</th>
  </tr></thead>
  <tbody>{codes_rows}</tbody>
</table>"""

    top_rows = ""
    for r in traffic["top10"]:
        fname = r["url"].split("/")[-1].split("?")[0][:50] or r["url"][:50]
        color = TYPE_COLORS.get(_classify_type(r["mime"], r["url"]), "#999")
        top_rows += f"""<tr>
      <td><a href="{r['url']}" target="_blank" rel="noopener" title="{r['url']}">{fname}</a></td>
      <td><span style="color:{color}">{_classify_type(r['mime'], r['url'])}</span></td>
      <td style="text-align:right">{round(r['size']/1024, 1)} Ko</td>
      <td style="color:#555;font-size:15px">{r['host']}</td>
    </tr>"""

    # Catégories de doublons : couleur + libellé court
    _CAT_META = {
        "tracker":        ("#5a3494", "#f0e9fa", "🔗 Tracker / analytics"),
        "font":           ("#a83232", "#fbe9e9", "🔤 Police externe"),
        "static_no_cache":("#a72834", "#fbe9e9", "🔴 Statique sans cache"),
        "static_cached":  (STATUS_GOOD, STATUS_BG["good"], "✅ Statique avec cache"),
        "other":          (STATUS_NEUTRAL, STATUS_BG["neutral"], "➖ Autre"),
    }

    dup_section = ""
    dups = traffic["duplicates"]
    if dups:
        # Grouper par catégorie
        from collections import OrderedDict
        groups = OrderedDict()
        for cat in _CAT_META:
            groups[cat] = [d for d in dups if d.get("category") == cat]

        # KPIs doublons
        nb_problematic = sum(1 for d in dups if d.get("category") in ("static_no_cache", "other"))
        nb_tracker     = sum(1 for d in dups if d.get("category") == "tracker")
        nb_font        = sum(1 for d in dups if d.get("category") == "font")

        dup_kpis = (
            f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px;font-size:16px">'
            f'<span style="background:#fbe9e9;border:1.5px solid #a72834;color:#a72834;font-weight:bold;padding:2px 8px;border-radius:4px">🔴 <b>{nb_problematic}</b> à corriger (sans cache)</span>'
            f'<span style="background:#f0e9fa;border:1.5px solid #5a3494;color:#5a3494;font-weight:bold;padding:2px 8px;border-radius:4px">🔗 <b>{nb_tracker}</b> trackers (normal)</span>'
            f'<span style="background:#fbe9e9;border:1.5px solid #a83232;color:#a83232;font-weight:bold;padding:2px 8px;border-radius:4px">🔤 <b>{nb_font}</b> polices externes</span>'
            f'</div>'
        )

        # Tableau par groupe
        dup_tables = ""
        for cat, items in groups.items():
            if not items:
                continue
            cat_color, cat_bg, cat_label = _CAT_META[cat]
            # Cause (identique pour tout le groupe)
            cause = items[0].get("cause", "")
            rows_html = ""
            for d in sorted(items, key=lambda x: -x["count"]):
                fname = d["url"].split("/")[-1].split("?")[0][:70] or d["url"][:70]
                rows_html += (
                    f'<tr>'
                    f'<td><a href="{d["url"]}" target="_blank" rel="noopener" title="{d["url"]}">{fname}</a></td>'
                    f'<td style="text-align:center;font-weight:bold;color:{cat_color}">{d["count"]}×</td>'
                    f'</tr>'
                )
            dup_tables += (
                f'<details style="margin-bottom:8px" {"open" if cat == "static_no_cache" else ""}>'
                f'<summary style="cursor:pointer;font-weight:bold;font-size:17px;padding:6px 0">'
                f'<span style="background:{cat_bg};border:1.5px solid {cat_color};color:{cat_color};font-weight:bold;padding:1px 7px;border-radius:4px;font-size:16px;margin-right:6px">{cat_label}</span>'
                f'{len(items)} URL(s) — <span style="font-weight:normal;color:#555;font-size:16px">{cause}</span>'
                f'</summary>'
                f'<table style="margin-top:6px">'
                f'<thead><tr><th>Fichier</th><th style="width:50px">Nb</th></tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                f'</table>'
                f'</details>'
            )

        dup_section = f'<h3 id="trafic-doublons">Requêtes dupliquées ({len(dups)} URL(s))</h3>{dup_kpis}{dup_tables}'

    tr = traffic.get("trackers") or {}
    trackers_section = ""
    if tr.get("count", 0) > 0:
        tr_domains_html = "".join(f'<span class="domain-tag">{d}</span>' for d in tr.get("domains", [])[:10])
        trackers_section = f"""<h3 id="trafic-trackers">Trackers et scripts tiers</h3>
  <div class="kpi-grid" style="margin-bottom:8px">
    <div class="kpi"><div class="val">{tr['count']}</div><div class="lbl">Requêtes trackers ({tr['pct_requests']}% du total)</div></div>
    <div class="kpi"><div class="val">{tr['size_ko']:.0f} Ko</div><div class="lbl">Poids trackers ({tr['pct_size']}% du total)</div></div>
  </div>
  <div style="margin-bottom:8px">{tr_domains_html}</div>
  <p style="font-size:15px;color:#888">Pour référence, les pisteurs tiers ajoutent typiquement 20 à 100 requêtes HTTP par page (source : études sur le pistage web) — chiffre à comparer à la mesure ci-dessus.</p>
"""

    return f"""<section id="trafic">
  <h2>Trafic réseau</h2>
  <div class="kpi-grid">
    <div class="kpi"><div class="val">{traffic['total_req']}</div><div class="lbl">Requêtes totales</div></div>
    <div class="kpi"><div class="val">{traffic['total_ko']:.0f} Ko</div><div class="lbl">Volume transféré</div></div>
    <div class="kpi"><div class="val">{len(traffic['domains'])}</div><div class="lbl">Domaines</div></div>
  </div>
  {trackers_section}
  <h3>Domaines contactés</h3>
  <div style="margin-bottom:12px">{domains_html}</div>
  <h3>Codes HTTP</h3>
  <div style="margin-bottom:16px">{codes_html}</div>
  <h3>Top 10 ressources les plus lourdes</h3>
  <table>
    <thead><tr><th>Fichier</th><th>Type</th><th>Poids</th><th>Domaine</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>
  {dup_section}
</section>"""


def _section_coverage(coverage_by_page):
    html = '<section id="coverage">\n  <h2>Code mort (Coverage JS/CSS)</h2>\n'

    for page_name, page_data in coverage_by_page.items():
        entries = page_data["entries"] if isinstance(page_data, dict) else page_data
        page_url = page_data.get("url", "") if isinstance(page_data, dict) else ""
        if not entries:
            continue
        summ = coverage_summary(entries)
        h3_label = (f'<a href="{page_url}" target="_blank" rel="noopener" title="{page_url}">{page_name}</a>'
                    if page_url else page_name)
        html += f'  <h3>{h3_label}</h3>\n'

        # Jauges
        js_used = 100 - summ["js"]["pct"] if summ["js"]["total_kb"] else 0
        css_used = 100 - summ["css"]["pct"] if summ["css"]["total_kb"] else 0
        html += f"""  <div style="display:flex;gap:24px;margin-bottom:10px;align-items:center">
    <div>JS {_bar(js_used)} <span style="font-size:16px">{summ['js']['unused_kb']} Ko non utilisés ({summ['js']['pct']}%)</span></div>
    <div>CSS {_bar(css_used)} <span style="font-size:16px">{summ['css']['unused_kb']} Ko non utilisés ({summ['css']['pct']}%)</span></div>
  </div>\n"""

        # Top fichiers
        top = sorted(entries, key=lambda e: e["unused_kb"], reverse=True)[:8]
        rows = ""
        for e in top:
            color = TYPE_COLORS.get(e["type"], "#999")
            rows += f"""<tr>
      <td><a href="{e['url']}" target="_blank" rel="noopener" title="{e['url']}">{e['filename']}</a></td>
      <td style="color:{color}">{e['type']}</td>
      <td style="text-align:right">{e['total_kb']} Ko</td>
      <td style="text-align:right;color:#dc5050">{e['unused_kb']} Ko</td>
      <td style="text-align:right">{e['unused_pct']}%</td>
      <td>{_bar(100 - e['unused_pct'])}</td>
    </tr>"""
        html += f"""  <table>
    <thead><tr><th>Fichier</th><th>Type</th><th>Total</th><th>Non utilisé</th><th>%</th><th></th></tr></thead>
    <tbody>{rows}</tbody>
  </table>\n"""

    html += "</section>\n"
    return html


def _cwv_colored(val, unit, thresholds):
    if not isinstance(val, (int, float)):
        return f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'
    if val <= thresholds[0]:
        color, emoji = STATUS_GOOD, STATUS_EMOJI["good"]
    elif val <= thresholds[1]:
        color, emoji = STATUS_WARN, STATUS_EMOJI["warn"]
    else:
        color, emoji = STATUS_BAD, STATUS_EMOJI["bad"]
    return f'<td style="text-align:right;color:{color};font-weight:bold">{emoji} {val} {unit}</td>'


def _section_cwv(page_metrics, cwv):
    if not cwv:
        return ""

    deduped = _dedup_page_metrics(page_metrics)
    from urllib.parse import urlparse
    rows = ""
    for m in deduped:
        by_strat = _cwv_for_page(m, cwv)
        url = m["title"]
        parsed = urlparse(url)
        short = parsed.path.rstrip("/") or "/"
        num = m.get("page_num", "")
        page_cell = f'<a href="{url}" target="_blank" rel="noopener" title="{url}"><span style="color:#888;font-size:15px;margin-right:4px">P{num}</span>{short}</a>'

        # Une sous-ligne par appareil disponible (mobile puis desktop)
        strats = [s for s in ("mobile", "desktop") if by_strat.get(s)]
        if not strats:
            na = f'<td style="text-align:right;color:{STATUS_NEUTRAL}">—</td>'
            rows += f"""<tr>
      <td>{page_cell}</td>
      <td style="color:{STATUS_NEUTRAL}">—</td>
      {na}{na}{na}
    </tr>"""
            continue
        for i, strat in enumerate(strats):
            c = by_strat[strat]
            device_label = "📱 Mobile" if strat == "mobile" else "🖥 Desktop"
            device_cell = f'{device_label} {_cwv_source_badge(c.get("source"))}'
            lcp_cell = _cwv_colored(c.get("lcp"), "s", (1.8, 2.5))
            inp_cell = _cwv_colored(c.get("inp"), "ms", (200, 500))
            cls_cell = _cwv_colored(c.get("cls"), "", (0.1, 0.25))
            # La cellule "Page" n'est affichée que sur la 1re sous-ligne (rowspan)
            first_cell = f'<td rowspan="{len(strats)}">{page_cell}</td>' if i == 0 else ""
            rows += f"""<tr>
      {first_cell}
      <td>{device_cell}</td>
      {lcp_cell}{inp_cell}{cls_cell}
    </tr>"""

    legend = f"""<div style="font-size:15px;margin-top:8px;display:flex;gap:16px;align-items:center">
    <span style="font-weight:bold;color:#555">Légende :</span>
    <span style="color:{STATUS_GOOD}">{STATUS_EMOJI['good']} Bon</span>
    <span style="color:{STATUS_WARN}">{STATUS_EMOJI['warn']} A améliorer</span>
    <span style="color:{STATUS_BAD}">{STATUS_EMOJI['bad']} Mauvais</span>
  </div>
  <table style="margin-top:10px;font-size:15px;border:none;width:auto">
    <thead><tr style="background:none">
      <th style="border:none;text-align:left">Métrique</th>
      <th style="border:none;color:{STATUS_GOOD}">Bon</th>
      <th style="border:none;color:{STATUS_WARN}">A améliorer</th>
      <th style="border:none;color:{STATUS_BAD}">Mauvais</th>
      <th style="border:none;text-align:left;color:#555">Description</th>
    </tr></thead>
    <tbody>
      <tr><td style="border:none"><b>LCP</b></td><td style="border:none">&lt; 1,8 s</td><td style="border:none">1,8 - 2,5 s</td><td style="border:none">&gt; 2,5 s</td><td style="border:none">Largest Contentful Paint - temps d'affichage du plus grand élément visible</td></tr>
      <tr><td style="border:none"><b>INP</b></td><td style="border:none">&lt; 200 ms</td><td style="border:none">200 - 500 ms</td><td style="border:none">&gt; 500 ms</td><td style="border:none">Interaction to Next Paint - réactivité aux interactions utilisateur</td></tr>
      <tr><td style="border:none"><b>CLS</b></td><td style="border:none">&lt; 0,1</td><td style="border:none">0,1 - 0,25</td><td style="border:none">&gt; 0,25</td><td style="border:none">Cumulative Layout Shift - stabilité visuelle (décalages inattendus)</td></tr>
    </tbody>
  </table>"""

    methodo_note = _cwv_methodo_note(cwv)

    return f"""<section id="cwv">
  <h2>Core Web Vitals</h2>
  {methodo_note}
  <table>
    <thead><tr><th>Page</th><th>Appareil</th><th>LCP</th><th>INP</th><th>CLS</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {legend}
</section>"""


def _cwv_methodo_note(cwv):
    """Note méthodologique CWV, adaptée aux sources RÉELLEMENT présentes.

    Distingue les 3 sources (crux terrain / pagespeed_lab / lighthouse local) au
    lieu de confondre crux et pagespeed_lab sous 'terrain manuel'."""
    sources = {row.get("source")
               for by_strat in cwv.values() if isinstance(by_strat, dict)
               for row in by_strat.values() if row}
    present = [s for s in ("crux", "pagespeed_lab", "lighthouse") if s in sources]
    src_lines = "".join(
        f'<li><strong>{_CWV_SOURCE_LABELS[s][0]}</strong> : {_CWV_SOURCE_LABELS[s][2]}</li>'
        for s in present
    ) or '<li>Source non renseignée</li>'

    has_lab = bool(sources & {"pagespeed_lab", "lighthouse"})
    has_field = "crux" in sources
    color = STATUS_GOOD if has_field and not has_lab else STATUS_WARN
    bg = "#e8f5e9" if has_field and not has_lab else "#fff8e1"

    lab_caveat = ""
    if has_lab:
        lab_caveat = ('<span style="color:#888;margin-top:6px;display:block">'
                      'Les mesures lab sont des simulations (réseau/CPU bridés). Les valeurs terrain '
                      'réelles sont souvent meilleures, surtout sur desktop et connexion rapide. '
                      'Les pages nécessitant une authentification sont analysées sans session : les '
                      'métriques reflètent alors la page de login, pas la page cible.</span>')
    field_caveat = ""
    if has_field:
        field_caveat = ('<span style="color:#888;margin-top:6px;display:block">'
                        'Le terrain CrUX ne couvre que les utilisateurs Chrome : iOS/Safari ne sont '
                        'pas mesurés (voir annexe méthodologique).</span>')

    return (f'<div style="background:{bg};border-left:3px solid {color};padding:10px 14px;'
            f'margin-bottom:14px;font-size:16px;color:#555;border-radius:0 4px 4px 0">'
            f'<strong>Note méthodologique - sources des mesures</strong>'
            f'<ul style="margin:6px 0 0 16px;padding:0">{src_lines}</ul>'
            f'{field_caveat}{lab_caveat}</div>')


CWV_ACTIONS = {
    "lcp_warn": "L'élément principal de la page (souvent l'image ou le bloc héro) met un "
                "peu trop de temps à s'afficher. À vérifier : cette image/bloc est-il chargé "
                "en priorité, ou un script/une autre ressource le retarde-t-il ?",
    "lcp_bad":  "L'élément principal de la page (image ou bloc héro) met trop de temps à "
                "s'afficher. Causes probables : image non préchargée, formats non optimisés, "
                "lazy loading activé par erreur sur le hero, ou script bloquant le rendu.",
    "inp_warn": "Le thread principal met un peu de temps à répondre après un clic ou un tap. "
                "Cause probable : gestionnaires d'événements ou traitements JS qui retardent "
                "la réponse.",
    "inp_bad":  "Le thread principal met trop de temps à répondre après une interaction "
                "(clic, tap). Cause probable : tâches JS longues ou gestionnaires "
                "d'événements lourds qui saturent le thread principal.",
    "cls_warn": "Des éléments de la page se décalent légèrement après l'affichage initial. "
                "Cause probable : images, iframes ou polices sans dimensions réservées.",
    "cls_bad":  "Des éléments de la page se décalent nettement après l'affichage initial, "
                "perturbant la lecture. Cause probable : images/iframes sans dimensions "
                "réservées, ou contenus injectés tardivement dans la page.",
}

_CWV_THRESHOLDS = {"lcp": (1.8, 2.5), "inp": (200, 500), "cls": (0.1, 0.25)}
_CWV_UNITS = {"lcp": "s", "inp": "ms", "cls": ""}
_CIRCLED_DIGITS = "①②③④⑤⑥⑦⑧⑨⑩"


def _cwv_status(metric, val):
    """Retourne (statut, couleur) pour une valeur de métrique CWV donnée."""
    lo, hi = _CWV_THRESHOLDS[metric]
    if val > hi:
        return "bad", STATUS_BAD
    if val > lo:
        return "warn", STATUS_WARN
    return "good", STATUS_GOOD


def _cwv_fmt_value(metric, val):
    if metric == "cls":
        return f"{val:.2f}"
    if metric == "lcp":
        return f"{val:.1f} {_CWV_UNITS[metric]}"
    return f"{int(round(val))} {_CWV_UNITS[metric]}"


def _cwv_diagnostic_signal(action_key, traffic, greenit, coverage_by_page):
    """Lot 5 : croise le problème CWV détecté avec des données déjà collectées
    (trackers, polices externes, ressource la plus lourde, JS non utilisé) pour
    nommer une cause probable plutôt qu'un message générique. Retourne une
    phrase additionnelle (vocabulaire prudent : "signal indicatif", pas de
    certitude) ou une chaîne vide si aucun signal exploitable n'est disponible.
    """
    metric = action_key.split("_")[0]
    agg = (greenit or {}).get("aggregated", {}) or {}

    if metric == "cls":
        signals = []
        trackers = (traffic or {}).get("trackers") or {}
        if trackers.get("count"):
            signals.append(f"{trackers['count']} requête(s) de trackers/scripts tiers détectée(s)")
        fonts = agg.get("UseStandardTypefaces", {}).get("evidence") or []
        if fonts:
            signals.append(f"police(s) web externe(s) détectée(s) ({', '.join(fonts[:2])})")
        if signals:
            return (f"Signal indicatif : {' et '.join(signals)}, susceptibles d'injecter du "
                    f"contenu tardivement dans la page (widgets, fallback de police) — à vérifier "
                    f"comme cause possible du décalage.")
        return ""

    if metric == "lcp":
        top10 = (traffic or {}).get("top10") or []
        for r in top10:
            rtype = _classify_type(r.get("mime", ""), r.get("url", ""))
            if rtype in ("image", "font"):
                ko = round(r["size"] / 1024, 1)
                return (f"Signal indicatif : la ressource la plus lourde du parcours est "
                        f"un(e) {rtype} de {ko} Ko ({r.get('host', '')}) — à vérifier si elle "
                        f"correspond à l'élément LCP de la page concernée.")
        return ""

    if metric == "inp":
        if coverage_by_page:
            heavy_pages = [
                label for label, pd in coverage_by_page.items()
                if coverage_summary(pd["entries"] if isinstance(pd, dict) else pd)["js"]["pct"] > 60
            ]
            if heavy_pages:
                return (f"Signal indicatif : taux de JS non utilisé &gt; 60 % relevé sur "
                        f"{len(heavy_pages)} page(s) (voir Coverage en annexe) — cause possible "
                        f"de surcharge du thread principal, sans certitude sur le JS exécuté "
                        f"réellement au runtime.")
        return ""

    return ""


def _section_cwv_analyse(page_metrics, cwv, traffic=None, greenit=None, coverage_by_page=None):
    if not cwv:
        return ""

    from urllib.parse import urlparse

    deduped = _dedup_page_metrics(page_metrics)

    methodo_note = _cwv_methodo_note(cwv)

    legend = f"""<div style="font-size:15px;margin-top:16px;display:flex;gap:16px;align-items:center">
    <span style="font-weight:bold;color:#555">Légende :</span>
    <span style="color:{STATUS_GOOD}">{STATUS_EMOJI['good']} Bon</span>
    <span style="color:{STATUS_WARN}">{STATUS_EMOJI['warn']} A améliorer</span>
    <span style="color:{STATUS_BAD}">{STATUS_EMOJI['bad']} Mauvais</span>
    <span style="color:{STATUS_NEUTRAL}">{STATUS_EMOJI['neutral']} Non mesuré</span>
  </div>"""

    # Numérotation des types de problèmes (①②③...), attribuée dans l'ordre de
    # première apparition en parcourant le tableau page par page, métrique par
    # métrique — un même type de problème (ex. "lcp_warn") garde le même numéro
    # partout, même s'il touche plusieurs pages/appareils.
    problem_order = []
    problem_number = {}

    def _note_number(action_key):
        if action_key not in problem_number:
            problem_order.append(action_key)
            problem_number[action_key] = len(problem_order)
        return problem_number[action_key]

    def _render_value(metric, strat, val):
        """Rend une ligne de valeur (émoji statut + émoji appareil + valeur +
        repère numéroté si dégradée). Retourne (html, status)."""
        status, color = _cwv_status(metric, val)
        status_emoji = STATUS_EMOJI.get(status, "")
        marker = f'{status_emoji} {_cwv_device_marker(strat)}'
        txt = _cwv_fmt_value(metric, val)
        sup = ""
        if status in ("bad", "warn"):
            n = _note_number(f"{metric}_{status}")
            sup = f'<sup style="font-size:11px;color:#000">{_CIRCLED_DIGITS[n - 1]}</sup>'
        return marker, txt, sup, status, color

    def _render_cell(metric, by_strat):
        row_worst, strat_by_metric = _cwv_worst_per_metric(by_strat)
        worst_strat = strat_by_metric.get(metric) if strat_by_metric else None
        if worst_strat is None:
            return f'<span style="color:{STATUS_NEUTRAL}" title="Non mesuré">{STATUS_EMOJI["neutral"]}</span>'

        marker_w, txt_w, sup_w, status_w, color_w = _render_value(metric, worst_strat, row_worst[metric])
        line1 = f'<div><b style="color:{color_w}">{marker_w} {txt_w}</b>{sup_w}</div>'

        other_strat = "desktop" if worst_strat == "mobile" else "mobile"
        other_row = by_strat.get(other_strat)
        line2 = ""
        if other_row and isinstance(other_row.get(metric), (int, float)):
            marker_o, txt_o, sup_o, status_o, color_o = _render_value(metric, other_strat, other_row[metric])
            style_o = f"color:{color_o};font-weight:bold"
            line2 = f'<div style="font-size:14px;{style_o}">{marker_o} {txt_o}{sup_o}</div>'
        return line1 + line2

    rows = ""
    for m in deduped:
        by_strat = _cwv_for_page(m, cwv)
        url = m["title"]
        parsed = urlparse(url)
        short = parsed.path.rstrip("/") or "/"
        num = m.get("page_num", "")

        sources = {r.get("source") for r in by_strat.values() if r}
        page_badge = _cwv_source_badge(next(iter(sources))) if len(sources) == 1 else ""

        if by_strat:
            lcp_cell = _render_cell("lcp", by_strat)
            inp_cell = _render_cell("inp", by_strat)
            cls_cell = _render_cell("cls", by_strat)
        else:
            not_measured = f'<span style="color:{STATUS_NEUTRAL}" title="Non mesuré">{STATUS_EMOJI["neutral"]}</span>'
            lcp_cell = inp_cell = cls_cell = not_measured

        rows += (
            '<tr style="border-bottom:1px solid #eee">'
            f'<td style="padding:8px;white-space:nowrap">'
            f'<span style="color:#888;font-size:14px;margin-right:4px">P{num}</span>'
            f'<a href="{url}" target="_blank" rel="noopener" style="color:inherit">{short}</a>'
            f' {page_badge}</td>'
            f'<td style="padding:8px;text-align:center">{lcp_cell}</td>'
            f'<td style="padding:8px;text-align:center">{inp_cell}</td>'
            f'<td style="padding:8px;text-align:center">{cls_cell}</td>'
            '</tr>'
        )

    table = f"""<table style="width:100%;border-collapse:collapse;margin-top:10px">
    <thead><tr style="background:#E0F0F4">
      <th style="padding:8px;text-align:left">Page</th>
      <th style="padding:8px">LCP</th>
      <th style="padding:8px">INP</th>
      <th style="padding:8px">CLS</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>"""

    legend_notes = ""
    if problem_order:
        def _note_html(key):
            signal = _cwv_diagnostic_signal(key, traffic, greenit, coverage_by_page)
            extra = f' <span style="color:#888">{signal}</span>' if signal else ""
            return f"{CWV_ACTIONS[key]}{extra}"
        items = "".join(
            f'<li><sup style="color:#000">{_CIRCLED_DIGITS[i]}</sup> {_note_html(key)}</li>'
            for i, key in enumerate(problem_order)
        )
        legend_notes = (
            '<div style="font-size:15px;margin-top:10px;color:#555">'
            f'<ul style="margin:4px 0 0 16px;padding:0;line-height:1.6">{items}</ul>'
            '</div>'
        )

    return f"""<section id="cwv-analyse">
  <h2>Analyse Core Web Vitals</h2>
  {methodo_note}
  {table}
  {legend}
  {legend_notes}
</section>"""


GREENIT_RULES = {
    "AddExpiresOrCacheControlHeaders": {
        "name": "Ajouter des expires ou cache-control headers (>= 95%)",
        "description": "Configurez les headers pour que CSS, JS et images soient mis en cache le plus longtemps possible.",
    },
    "CompressHttp": {
        "name": "Compresser les ressources (>= 95%)",
        "description": "Activez gzip/Deflate. Pré-compressez les ressources statiques ; la compression à la volée convient pour le HTML dynamique.",
    },
    "DomainsNumber": {
        "name": "Limiter le nombre de domaines (< 3)",
        "description": "Moins de domaines = moins de connexions HTTP. Exception : un domaine séparé sans cookie pour les ressources statiques.",
    },
    "DontResizeImageInBrowser": {
        "name": "Ne pas retailler les images dans le navigateur",
        "description": "Redimensionner via HTML gaspille la bande passante : un PNG 350×300 px pèse 41 Ko même affiché en 70×60 px.",
    },
    "EmptySrcTag": {
        "name": "Eviter les tags SRC vides",
        "description": "Un attribut src vide déclenche des requêtes HTTP inutiles vers le répertoire de la page.",
    },
    "ExternalizeCss": {
        "name": "Externaliser les css",
        "description": "Le CSS inline est renvoyé à chaque requête de page ; les fichiers externes peuvent être mis en cache.",
    },
    "ExternalizeJs": {
        "name": "Externaliser les js",
        "description": "Même principe que le CSS : les fichiers JS séparés permettent la mise en cache navigateur.",
    },
    "HttpError": {
        "name": "Eviter les requêtes en erreur",
        "description": "Les réponses en erreur consomment des ressources inutilement.",
    },
    "HttpRequests": {
        "name": "Limiter le nombre de requêtes HTTP (< 27)",
        "description": "Moins de requêtes par page allègent la charge serveur et réduisent l'impact environnemental.",
    },
    "ImageDownloadedNotDisplayed": {
        "name": "Ne pas télécharger des images inutilement",
        "description": "Les images chargées mais affichées seulement après interaction utilisateur gaspillent des ressources.",
    },
    "JsValidate": {
        "name": "Valider le javascript",
        "description": "JSLint garantit la conformité syntaxique cross-navigateur et permet une exécution plus rapide de l'interpréteur.",
    },
    "MaxCookiesLength": {
        "name": "Taille maximum des cookies par domaine (< 512 octets)",
        "description": "Les cookies sont envoyés à chaque requête : les garder courts économise de la bande passante.",
    },
    "MinifiedCss": {
        "name": "Minifier les css (>= 95%)",
        "description": "Utilisez YUI Compressor ou mod_pagespeed pour supprimer espaces et sauts de ligne.",
    },
    "MinifiedJs": {
        "name": "Minifier les js (>= 95%)",
        "description": "Supprimez les espaces, sauts de ligne, points-virgules inutiles et raccourcissez les noms de variables locales.",
    },
    "NoCookieForStaticRessources": {
        "name": "Pas de cookie pour les ressources statiques",
        "description": "Les cookies sur les ressources statiques gaspillent de la bande passante. Utilisez un domaine séparé ou limitez la portée des cookies.",
    },
    "NoRedirect": {
        "name": "Eviter les redirections",
        "description": "Les redirections ralentissent les temps de réponse et consomment des ressources inutilement.",
    },
    "OptimizeBitmapImages": {
        "name": "Optimiser les images bitmap",
        "description": "Les bitmaps représentent généralement la majorité des octets téléchargés : leur optimisation a un fort impact.",
    },
    "OptimizeSvg": {
        "name": "Optimiser les images svg",
        "description": "Bien que plus légères que les bitmaps, les SVG peuvent être minifiés avec des outils comme svgo.",
    },
    "Plugins": {
        "name": "Ne pas utiliser de plugins",
        "description": "Flash, Java, Silverlight imposent une charge CPU/RAM importante. Préférez HTML5 et ECMAScript.",
    },
    "PrintStyleSheet": {
        "name": "Fournir une print css",
        "description": "Une feuille de style d'impression réduit le nombre de pages imprimées ; masquez menus, en-têtes et images non essentielles.",
    },
    "SocialNetworkButton": {
        "name": "N'utilisez pas les boutons standards des réseaux sociaux",
        "description": "Les plugins officiels (Facebook, Twitter…) chargent des ressources inutiles ; utilisez des liens directs.",
    },
    "StyleSheets": {
        "name": "Limiter le nombre de fichiers css (< 3)",
        "description": "Concaténez les feuilles de style en un seul fichier pour réduire les requêtes HTTP.",
    },
    "UseETags": {
        "name": "Utiliser des ETags (>= 95%)",
        "description": "Les ETags permettent la réutilisation des ressources en cache quand la signature serveur correspond.",
    },
    "UseStandardTypefaces": {
        "name": "Utiliser des polices de caractères standards",
        "description": "Les polices standard sont déjà présentes sur l'appareil de l'utilisateur : aucun téléchargement nécessaire.",
    },
    "PreferHttp2": {
        "name": "Privilégier HTTP/2 à HTTP/1",
        "description": (
            "HTTP/2 permet le multiplexage des requêtes sur une seule connexion TCP "
            "(fin du plafond de 6 connexions/domaine d'HTTP/1.1) et compresse les en-têtes "
            "(HPACK), réduisant la latence et le nombre de handshakes TCP/TLS. "
            "Activation selon le serveur : Apache -> mod_http2 (nécessite le MPM event ou "
            "worker ; incompatible avec mpm_prefork) ; Nginx -> directive 'listen 443 ssl "
            "http2;' (>= 1.25 pour HTTP/3 QUIC) ; derrière un CDN/reverse-proxy -> HTTP/2 "
            "est généralement activé par défaut côté edge, vérifier la configuration entre "
            "le CDN et l'origine."
        ),
    },
}

COMPLIANCE_STATUS = {"A": "good", "B": "warn", "C": "bad", "NA": "neutral"}
COMPLIANCE_ORDER  = {"C": 0, "B": 1, "A": 2, "NA": 3}


def _compliance_badge_html(level, count=None, min_width="28px"):
    """Badge de conformité GreenIT (A/B/C/N.A), style "chip" (fond clair + bordure
    + emoji coloré) : la couleur seule ne doit jamais porter l'information, et
    l'emoji doit rester visible même sur son propre statut (accessibilité)."""
    status = COMPLIANCE_STATUS.get(level, "neutral")
    display = "N.A" if level == "NA" else level
    label = f"<b>{count}</b> {display}" if count is not None else display
    return _status_chip(status, label, extra_style=f"min-width:{min_width}")


def load_greenit(audit_dir):
    """
    Charge le fichier greenit.json si présent.
    Formats acceptés :
      - CLI GreenIT-Analysis-cli : liste de pages {"url":..., "bestPractices":{...}}
      - EcoSonar export          : {"ecodesign": {"RuleName": {"compliance":..., "auditedMetric":..., "averageScore":..., "description":...}}}
    Retourne un dict {"pages": [...], "aggregated": {"RuleName": {...}}} ou None.
    """
    path = Path(audit_dir) / "greenit.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Format EcoSonar
    if isinstance(data, dict) and "ecodesign" in data:
        aggregated = {}
        for key, val in data["ecodesign"].items():
            aggregated[key] = {
                "complianceLevel": val.get("compliance", "NA"),
                "comment":         str(val.get("auditedMetric", "")),
                "detailComment":   val.get("description", ""),
            }
        return {"pages": [], "aggregated": aggregated}

    # Format CLI : liste de pages
    pages = data if isinstance(data, list) else [data]
    aggregated = {}
    for page in pages:
        for key, bp in page.get("bestPractices", {}).items():
            level = bp.get("complianceLevel", "NA")
            if key not in aggregated:
                aggregated[key] = {"complianceLevel": level, "comment": bp.get("comment", ""), "detailComment": bp.get("detailComment", ""), "_levels": []}
            aggregated[key]["_levels"].append(level)

    # Compliance globale = pire niveau parmi les pages
    for key, val in aggregated.items():
        levels = val.pop("_levels", [])
        worst = sorted(levels, key=lambda x: COMPLIANCE_ORDER.get(x, 3))[-1] if levels else "NA"
        val["complianceLevel"] = worst

    return {"pages": pages, "aggregated": aggregated}


def compute_greenit_from_har(har_data):
    """
    Calcule les bonnes pratiques GreenIT-Analysis depuis un HAR.
    Logique basée sur cnumr/GreenIT-Analysis (open source).
    Retourne un dict compatible avec load_greenit() : {"pages":[], "aggregated":{...}}
    """
    from urllib.parse import urlparse

    entries = har_data.get("log", {}).get("entries", [])
    if not entries:
        return None

    def _is_static(mime, url):
        return _classify_type(mime, url) in ("javascript", "css", "image", "font")

    def _is_cached(resp):
        hdrs = {h["name"].lower(): h["value"] for h in resp.get("headers", [])}
        return bool(hdrs.get("cache-control") or hdrs.get("expires") or hdrs.get("etag") or resp.get("status") == 304)

    # ── Collecte des métriques brutes ─────────────────────────────────────────
    total = len(entries)
    nb_errors = 0;         urls_errors = []
    nb_redirects = 0;      urls_redirects = []
    nb_no_cache = 0;       urls_no_cache = []
    static_cacheable_bytes = 0;  cacheable_ok_bytes = 0  # Lot 3 : gain estimé "visite de retour"
    nb_no_compress = 0;    urls_no_compress = []
    nb_no_etag = 0;        urls_no_etag = []
    nb_cookie_static = 0;  urls_cookie_static = [];  cookie_static_bytes = 0
    cookie_bytes_by_domain = defaultdict(int)
    domains = set()
    css_files = []
    inline_css = 0
    inline_js = 0
    font_external = 0;     urls_fonts = []
    nb_svg = 0;            urls_svg_heavy = []
    nb_bitmap = 0;         urls_bitmap_heavy = []
    nb_bitmap_heavy = 0
    nb_svg_heavy = 0
    urls_svg_fake = []     # Lot 4 : SVG anormalement lourd (> 30 Ko), probable bitmap encodé
    nb_video = 0;          video_bytes = 0;  urls_video = []
    nb_pdf = 0;            pdf_bytes = 0;    urls_pdf = []
    has_print_css = False
    social_domains = {"facebook.com", "twitter.com", "x.com", "linkedin.com", "instagram.com",
                      "platform.twitter.com", "connect.facebook.net", "platform.linkedin.com"}
    nb_social = 0;         urls_social = []
    http_versions = defaultdict(int)  # pour HTTP/2

    def _short(u, n=80):
        return u if len(u) <= n else u[:n] + "…"

    for e in entries:
        req  = e.get("request", {})
        resp = e.get("response", {})
        url  = req.get("url", "")
        status = resp.get("status", 0)
        mime = resp.get("content", {}).get("mimeType", "")
        rtype = _classify_type(mime, url)
        size  = resp.get("content", {}).get("size", 0) or 0
        hdrs_resp = {h["name"].lower(): h["value"] for h in resp.get("headers", [])}
        hdrs_req  = {h["name"].lower(): h["value"] for h in req.get("headers", [])}
        http_ver  = req.get("httpVersion", "") or resp.get("httpVersion", "")

        try:
            netloc = urlparse(url).netloc
        except Exception:
            netloc = ""
        if netloc:
            domains.add(netloc)

        # HTTP version
        if http_ver:
            http_versions[http_ver] += 1

        # Erreurs
        if 400 <= status < 600:
            nb_errors += 1
            if len(urls_errors) < 20:
                urls_errors.append((url, status))

        # Redirections
        if 300 <= status < 400 and status != 304:
            nb_redirects += 1
            if len(urls_redirects) < 20:
                urls_redirects.append((url, status))

        # Cache-control / expires
        if _is_static(mime, url) and status != 304:
            has_cc   = bool(hdrs_resp.get("cache-control") or hdrs_resp.get("expires"))
            has_etag = bool(hdrs_resp.get("etag"))
            static_cacheable_bytes += size
            if has_cc:
                cacheable_ok_bytes += size
            else:
                nb_no_cache += 1
                if len(urls_no_cache) < 20:
                    urls_no_cache.append(url)
            if not has_etag:
                nb_no_etag += 1
                if len(urls_no_etag) < 20:
                    urls_no_etag.append(url)

        # Compression
        if rtype in ("javascript", "css", "html") and size > 1024:
            enc = hdrs_resp.get("content-encoding", "")
            if not enc or enc.lower() == "identity":
                nb_no_compress += 1
                if len(urls_no_compress) < 20:
                    urls_no_compress.append(url)

        # Cookies sur statiques
        if _is_static(mime, url) and hdrs_req.get("cookie"):
            nb_cookie_static += 1
            cookie_static_bytes += len(hdrs_req["cookie"].encode())
            if len(urls_cookie_static) < 20:
                urls_cookie_static.append(url)
        for h in req.get("headers", []):
            if h["name"].lower() == "cookie" and netloc:
                cookie_bytes_by_domain[netloc] += len(h["value"].encode())

        # CSS
        if rtype == "css":
            if url.startswith("http"):
                css_files.append(url)
                for h in req.get("headers", []):
                    if "print" in h.get("value", "").lower():
                        has_print_css = True
            else:
                inline_css += 1

        # JS inline
        if rtype == "html":
            body = resp.get("content", {}).get("text", "") or ""
            if "<script" in body and "src=" not in body.split("<script")[1][:100] if "<script" in body else False:
                inline_js += 1

        # Polices externes
        if "googleapis.com" in netloc or "gstatic.com" in netloc or "typekit" in netloc or rtype == "font":
            if netloc:
                font_external = 1
                if netloc not in [u for u in urls_fonts]:
                    urls_fonts.append(netloc)

        # Images
        if rtype == "image":
            ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext == "svg":
                nb_svg += 1
                if size > 10 * 1024:
                    nb_svg_heavy += 1
                    if len(urls_svg_heavy) < 20:
                        urls_svg_heavy.append((url, round(size/1024, 1)))
                # Lot 4 : au-delà de 30 Ko, un SVG (vectoriel, normalement léger)
                # cache le plus souvent un bitmap encodé en base64 (signal, pas certitude)
                if size > 30 * 1024 and len(urls_svg_fake) < 20:
                    urls_svg_fake.append((url, round(size/1024, 1)))
            else:
                nb_bitmap += 1
                if size > 200 * 1024 and ext not in ("webp", "avif", "jxl"):
                    nb_bitmap_heavy += 1
                    if len(urls_bitmap_heavy) < 20:
                        urls_bitmap_heavy.append((url, round(size/1024, 1)))

        # Vidéos et PDF (Lot 4) : signalement factuel, pas de jugement A/B/C
        if rtype == "video":
            nb_video += 1
            video_bytes += size
            if len(urls_video) < 20:
                urls_video.append((url, round(size/1024, 1)))
        elif rtype == "pdf":
            nb_pdf += 1
            pdf_bytes += size
            if len(urls_pdf) < 20:
                urls_pdf.append((url, round(size/1024, 1)))

        # Réseaux sociaux
        if netloc in social_domains or any(s in netloc for s in ("facebook", "twitter", "linkedin", "instagram")):
            nb_social += 1
            if len(urls_social) < 10:
                urls_social.append(url)

    # print CSS : chercher dans les corps HTML
    for e in entries:
        body = e.get("response", {}).get("content", {}).get("text", "") or ""
        if "media" in body and "print" in body:
            has_print_css = True
            break

    # ── Évaluation des règles ─────────────────────────────────────────────────
    static_total = sum(
        1 for e in entries
        if _is_static(
            e.get("response",{}).get("content",{}).get("mimeType",""),
            e.get("request",{}).get("url","")
        ) and e.get("response",{}).get("status",0) != 304
    )

    def _pct_ok(nb_bad, total_concerned):
        if total_concerned == 0:
            return "A", "100% conformes"
        pct_bad = nb_bad / total_concerned * 100
        if pct_bad == 0:
            return "A", "100% conformes"
        elif pct_bad <= 5:
            return "B", f"{nb_bad}/{total_concerned} ressource(s) non conforme(s)"
        else:
            return "C", f"{nb_bad}/{total_concerned} ressource(s) non conforme(s)"

    def _ev(urls, label="URL"):
        """Formate la liste d'evidence pour stockage."""
        return urls

    agg = {}

    # AddExpiresOrCacheControlHeaders
    lvl, cmt = _pct_ok(nb_no_cache, static_total)
    # Gain "visite de retour" (Lot 3) : poids déjà évité par le cache en place
    # + poids additionnel qui serait évité si les ressources sans cache étaient corrigées.
    _no_cache_bytes = static_cacheable_bytes - cacheable_ok_bytes
    if static_cacheable_bytes > 0:
        cmt += (f" — gain revisite actuel : {cacheable_ok_bytes/1024:.0f} Ko évités/visite de retour"
                f"{f', {_no_cache_bytes/1024:.0f} Ko additionnels possibles si corrigé' if _no_cache_bytes > 0 else ''}")
    agg["AddExpiresOrCacheControlHeaders"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_no_cache}

    # CompressHttp
    compressible = sum(
        1 for e in entries
        if _classify_type(
            e.get("response",{}).get("content",{}).get("mimeType",""),
            e.get("request",{}).get("url","")
        ) in ("javascript","css","html")
        and (e.get("response",{}).get("content",{}).get("size",0) or 0) > 1024
    )
    lvl, cmt = _pct_ok(nb_no_compress, compressible)
    agg["CompressHttp"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_no_compress}

    # DomainsNumber
    nd = len(domains)
    if nd < 3:
        lvl = "A"
    elif nd < 6:
        lvl = "B"
    else:
        lvl = "C"
    agg["DomainsNumber"] = {"complianceLevel": lvl, "comment": f"{nd} domaine(s)", "evidence": sorted(domains)}

    # HttpError
    lvl = "A" if nb_errors == 0 else "C"
    cmt = "Aucune erreur HTTP" if nb_errors == 0 else f"{nb_errors} requête(s) en erreur"
    agg["HttpError"] = {"complianceLevel": lvl, "comment": cmt, "evidence": [f"{u} ({s})" for u, s in urls_errors]}

    # HttpRequests
    pages_har = har_data.get("log", {}).get("pages", [])
    nb_pages_har = max(len(pages_har), 1)
    avg_req = total / nb_pages_har
    if avg_req < 27:   lvl = "A"
    elif avg_req < 40: lvl = "B"
    else:              lvl = "C"
    agg["HttpRequests"] = {"complianceLevel": lvl, "comment": f"{avg_req:.0f} req/page en moyenne ({total} total, {nb_pages_har} pages)", "evidence": []}

    # NoRedirect
    if nb_redirects == 0:     lvl, cmt = "A", "Aucune redirection"
    elif nb_redirects <= 2:   lvl, cmt = "B", f"{nb_redirects} redirection(s)"
    else:                     lvl, cmt = "C", f"{nb_redirects} redirection(s)"
    agg["NoRedirect"] = {"complianceLevel": lvl, "comment": cmt, "evidence": [f"{u} ({s})" for u, s in urls_redirects]}

    # NoCookieForStaticRessources
    lvl = "A" if nb_cookie_static == 0 else "C"
    if nb_cookie_static == 0:
        cmt = "Aucun cookie sur ressource statique"
    else:
        cmt = (f"{nb_cookie_static} ressource(s) statique(s) avec cookie — "
               f"{cookie_static_bytes} octets de cookie transmis inutilement sur ce parcours "
               f"(mesuré depuis les en-têtes HAR, pas une estimation)")
    agg["NoCookieForStaticRessources"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_cookie_static}

    # UseETags
    lvl, cmt = _pct_ok(nb_no_etag, static_total)
    agg["UseETags"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_no_etag[:10]}

    # ExternalizeCss
    lvl = "A" if inline_css == 0 else "C"
    cmt = "Pas de CSS inline détecté" if inline_css == 0 else f"{inline_css} CSS inline détecté(s)"
    agg["ExternalizeCss"] = {"complianceLevel": lvl, "comment": cmt, "evidence": []}

    # ExternalizeJs
    lvl = "A" if inline_js == 0 else "C"
    cmt = "Pas de JS inline détecté" if inline_js == 0 else f"{inline_js} JS inline détecté(s)"
    agg["ExternalizeJs"] = {"complianceLevel": lvl, "comment": cmt, "evidence": []}

    # StyleSheets
    nb_css = len(set(u.split("?")[0] for u in css_files))
    if nb_css <= 2:   lvl = "A"
    elif nb_css <= 5: lvl = "B"
    else:             lvl = "C"
    agg["StyleSheets"] = {"complianceLevel": lvl, "comment": f"{nb_css} fichier(s) CSS distincts", "evidence": sorted(set(u.split("?")[0] for u in css_files))}

    # UseStandardTypefaces
    lvl = "C" if font_external else "A"
    cmt = "Polices externes détectées" if font_external else "Pas de police externe détectée"
    agg["UseStandardTypefaces"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_fonts}

    # MinifiedCss / MinifiedJs — heuristique whitespace ratio
    def _count_unminified(rtype_filter):
        nb = 0; tot = 0; urls_bad = []
        for e in entries:
            mime = e.get("response",{}).get("content",{}).get("mimeType","")
            u = e.get("request",{}).get("url","")
            if _classify_type(mime, u) != rtype_filter:
                continue
            sz = e.get("response",{}).get("content",{}).get("size",0) or 0
            if sz < 2048:
                continue
            tot += 1
            body = e.get("response",{}).get("content",{}).get("text","") or ""
            if len(body) > 500 and body.count("\n") > len(body) / 200:
                nb += 1
                if len(urls_bad) < 20:
                    urls_bad.append(u)
        return nb, tot, urls_bad

    nb_unmin_css, tot_css, urls_unmin_css = _count_unminified("css")
    lvl, cmt = _pct_ok(nb_unmin_css, tot_css)
    agg["MinifiedCss"] = {"complianceLevel": lvl, "comment": cmt if cmt else f"{tot_css} fichier(s) CSS", "evidence": urls_unmin_css}

    nb_unmin_js, tot_js, urls_unmin_js = _count_unminified("javascript")
    lvl, cmt = _pct_ok(nb_unmin_js, tot_js)
    agg["MinifiedJs"] = {"complianceLevel": lvl, "comment": cmt if cmt else f"{tot_js} fichier(s) JS", "evidence": urls_unmin_js}

    # OptimizeBitmapImages
    if nb_bitmap == 0:
        agg["OptimizeBitmapImages"] = {"complianceLevel": "NA", "comment": "Pas d'image bitmap", "evidence": [], "evidence_images": []}
    elif nb_bitmap_heavy == 0:
        # Top 10 images les plus lourdes même si conformes (pour aperçu)
        top_bitmaps = sorted(
            [(e.get("request",{}).get("url",""), e.get("response",{}).get("content",{}).get("size",0) or 0)
             for e in entries
             if _classify_type(e.get("response",{}).get("content",{}).get("mimeType",""), e.get("request",{}).get("url","")) == "image"
             and e.get("request",{}).get("url","").split("?")[0].rsplit(".",1)[-1].lower() not in ("svg",)],
            key=lambda x: -x[1]
        )[:10]
        agg["OptimizeBitmapImages"] = {
            "complianceLevel": "A",
            "comment": f"{nb_bitmap} image(s), aucune > 200 Ko non-webp/avif/jxl",
            "evidence": [],
            "evidence_images": [{"url": u, "size_kb": round(s/1024, 1)} for u, s in top_bitmaps if u],
        }
    else:
        heavy_ko = sum(s for _, s in urls_bitmap_heavy)
        # Gains forfaitaires cnumr JPEG/PNG -> WebP : -31,5% / -50,3% (moyenne ~-41% retenue,
        # pas de distinction par format source ici — fourchette à préciser en méthodologie)
        gain_low_ko  = round(heavy_ko * 0.315)
        gain_high_ko = round(heavy_ko * 0.503)
        agg["OptimizeBitmapImages"] = {
            "complianceLevel": "C",
            "comment": (f"{nb_bitmap_heavy} image(s) > 200 Ko, format non-webp/avif/jxl — "
                        f"gain estimé webp : {gain_low_ko} à {gain_high_ko} Ko (forfaitaire, non mesuré)"),
            "evidence": [f"{u} ({s} Ko)" for u, s in urls_bitmap_heavy],
            "evidence_images": [{"url": u, "size_kb": s} for u, s in urls_bitmap_heavy],
        }

    # OptimizeSvg
    if nb_svg == 0:
        agg["OptimizeSvg"] = {"complianceLevel": "NA", "comment": "Pas de SVG", "evidence": [], "evidence_images": []}
    elif nb_svg_heavy == 0:
        agg["OptimizeSvg"] = {"complianceLevel": "A", "comment": f"{nb_svg} SVG, aucun > 10 Ko", "evidence": [], "evidence_images": []}
    else:
        cmt = f"{nb_svg_heavy} SVG lourd(s) (> 10 Ko)"
        if urls_svg_fake:
            cmt += (f" — dont {len(urls_svg_fake)} probable(s) bitmap encodé(s) en base64 "
                    f"(> 30 Ko, signal non confirmé)")
        agg["OptimizeSvg"] = {
            "complianceLevel": "C",
            "comment": cmt,
            "evidence": [f"{u} ({s} Ko)" for u, s in urls_svg_heavy],
            "evidence_images": [{"url": u, "size_kb": s} for u, s in urls_svg_heavy],
        }

    # PrintStyleSheet
    lvl = "A" if has_print_css else "C"
    cmt = "Print CSS détectée" if has_print_css else "Aucune feuille de style print détectée"
    agg["PrintStyleSheet"] = {"complianceLevel": lvl, "comment": cmt, "evidence": []}

    # SocialNetworkButton
    lvl = "A" if nb_social == 0 else "C"
    cmt = "Aucun bouton réseau social standard" if nb_social == 0 else f"{nb_social} ressource(s) réseau social détectée(s)"
    agg["SocialNetworkButton"] = {"complianceLevel": lvl, "comment": cmt, "evidence": urls_social}

    # MaxCookiesLength
    max_cookie = max(cookie_bytes_by_domain.values()) if cookie_bytes_by_domain else 0
    if max_cookie == 0:
        lvl, cmt = "A", "Aucun cookie"
    elif max_cookie <= 512:
        lvl, cmt = "A", f"Max {max_cookie} octets/domaine"
    else:
        lvl, cmt = "C", f"Max {max_cookie} octets/domaine (> 512)"
    agg["MaxCookiesLength"] = {"complianceLevel": lvl, "comment": cmt,
                                "evidence": [f"{d} : {b} octets" for d, b in sorted(cookie_bytes_by_domain.items(), key=lambda x: -x[1])[:10]]}

    # PreferHttp2
    nb_h1 = sum(v for k, v in http_versions.items() if "1.1" in k or k == "HTTP/1.0")
    nb_h2 = sum(v for k, v in http_versions.items() if "2" in k or "h2" in k.lower())
    if not http_versions or (nb_h1 == 0 and nb_h2 == 0):
        # Pas d'info de version dans le HAR
        agg["PreferHttp2"] = {"complianceLevel": "NA", "comment": "Version HTTP non disponible dans le HAR", "evidence": []}
    elif nb_h1 == 0:
        agg["PreferHttp2"] = {"complianceLevel": "A", "comment": f"HTTP/2 ou supérieur ({nb_h2} requêtes)", "evidence": []}
    elif nb_h2 == 0:
        agg["PreferHttp2"] = {"complianceLevel": "C", "comment": f"HTTP/1.x uniquement ({nb_h1} requêtes)", "evidence": list(http_versions.items())}
    else:
        agg["PreferHttp2"] = {"complianceLevel": "B", "comment": f"Mix HTTP/1.x ({nb_h1}) et HTTP/2+ ({nb_h2})",
                               "evidence": [f"{k}: {v} requête(s)" for k, v in sorted(http_versions.items())]}

    # Lot 4 : médias volumineux (vidéos, PDF) — signalement factuel, pas de badge A/B/C
    # (pas de seuil universel défendable, pas de comparaison poids/usage réel possible ici)
    media = {
        "video": {"count": nb_video, "size_ko": round(video_bytes/1024), "urls": urls_video},
        "pdf":   {"count": nb_pdf,   "size_ko": round(pdf_bytes/1024),   "urls": urls_pdf},
    }

    return {"pages": [], "aggregated": agg, "_source": "har", "media": media}


def _section_greenit(greenit):
    if not greenit:
        return ""

    agg = greenit["aggregated"]
    # Trier : C en premier, puis B, puis A, puis NA
    sorted_keys = sorted(agg.keys(), key=lambda k: COMPLIANCE_ORDER.get(agg[k]["complianceLevel"], 3))

    rows = ""
    for key in sorted_keys:
        bp    = agg[key]
        rule  = GREENIT_RULES.get(key, {"name": key, "description": ""})
        level = bp["complianceLevel"]
        badge = _compliance_badge_html(level)
        detail = bp.get("comment") or bp.get("detailComment") or ""

        # Bloc <details> avec les URLs incriminées si disponibles
        evidence = bp.get("evidence", [])
        evidence_images = bp.get("evidence_images", [])  # [{url, size_kb}]

        # Dédupliquer par URL canonique (sans query string)
        _seen_ev = {}
        for img in evidence_images:
            key = img["url"].split("?")[0]
            if key not in _seen_ev or img.get("size_kb", 0) > _seen_ev[key].get("size_kb", 0):
                _seen_ev[key] = img
        evidence_images = list(_seen_ev.values())

        # Thumbnails pour les 10 images les plus lourdes
        thumbs_html = ""
        if evidence_images:
            top_imgs = sorted(evidence_images, key=lambda x: -x.get("size_kb", 0))[:10]
            thumbs = []
            for img in top_imgs:
                url = img["url"]
                size_kb = img.get("size_kb", 0)
                fname = url.split("/")[-1].split("?")[0][:40]
                thumb = embed_image(url, alt=fname, max_dim=50)
                if thumb:
                    # Remplacer la figure par une version inline compacte
                    thumb_inline = (
                        f'<div style="display:inline-block;text-align:center;margin:4px;vertical-align:top">'
                        f'<a href="{url}" target="_blank" rel="noopener">'
                        f'{thumb}'
                        f'</a>'
                        f'<div style="font-size:14px;color:#555;max-width:60px;word-break:break-all">'
                        f'{fname}<br><b>{size_kb} Ko</b></div>'
                        f'</div>'
                    )
                    thumbs.append(thumb_inline)
                else:
                    # Fallback : lien texte si vipsthumbnail absent
                    thumbs.append(
                        f'<div style="display:inline-block;margin:4px;font-size:15px;vertical-align:top">'
                        f'<a href="{url}" target="_blank" rel="noopener">{fname}</a>'
                        f'<br><b>{size_kb} Ko</b></div>'
                    )
            if thumbs:
                thumbs_html = (
                    f'<div style="margin-top:6px;padding:6px;background:#f8f8f8;border-radius:4px">'
                    f'<div style="font-size:15px;color:#555;margin-bottom:4px">Top {len(thumbs)} image(s) les plus lourdes :</div>'
                    f'{"".join(thumbs)}'
                    f'</div>'
                )

        if thumbs_html:
            # Les thumbnails remplacent la liste texte pour les règles images
            nb = len(evidence_images)
            details_html = (
                f'<details style="margin-top:4px">'
                f'<summary style="cursor:pointer;font-size:15px;color:#555">'
                f'Aperçu ({nb} image(s))</summary>'
                f'{thumbs_html}'
                f'</details>'
            )
        elif evidence:
            # Autres règles : liste texte simple
            ev_items = "".join(
                f'<li style="font-size:15px;word-break:break-all;margin:2px 0">'
                f'<a href="{item}" target="_blank" rel="noopener">{item}</a></li>'
                if str(item).startswith("http")
                else f'<li style="font-size:15px;margin:2px 0">{item}</li>'
                for item in evidence
            )
            details_html = (
                f'<details style="margin-top:4px">'
                f'<summary style="cursor:pointer;font-size:15px;color:#555">'
                f'Détail ({len(evidence)} élément(s))</summary>'
                f'<ul style="margin:4px 0 0 12px;padding:0">{ev_items}</ul>'
                f'</details>'
            )
        else:
            details_html = ""

        detail_html = f'<span style="font-size:15px;color:#666">{detail}</span>' if detail else ""
        rows += f"""<tr>
      <td style="text-align:center;width:48px;vertical-align:top;padding-top:10px">{badge}</td>
      <td><b>{rule['name']}</b><br>{detail_html}{details_html}</td>
      <td style="font-size:16px;color:#555;vertical-align:top">{rule['description']}</td>
    </tr>"""

    nb_c  = sum(1 for k in agg if agg[k]["complianceLevel"] == "C")
    nb_b  = sum(1 for k in agg if agg[k]["complianceLevel"] == "B")
    nb_a  = sum(1 for k in agg if agg[k]["complianceLevel"] == "A")
    nb_na = sum(1 for k in agg if agg[k]["complianceLevel"] == "NA")

    summary = (
        f'<span style="margin-right:6px">{_compliance_badge_html("C", nb_c, min_width="auto")}</span>'
        f'<span style="margin-right:6px">{_compliance_badge_html("B", nb_b, min_width="auto")}</span>'
        f'<span style="margin-right:6px">{_compliance_badge_html("A", nb_a, min_width="auto")}</span>'
        f'{_compliance_badge_html("NA", nb_na, min_width="auto")}'
    )

    legend = (
        '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px;font-size:16px">'
        f'<span>{_compliance_badge_html("C", min_width="auto")} &nbsp;<b>Non conforme</b> - action corrective requise</span>'
        f'<span>{_compliance_badge_html("B", min_width="auto")} &nbsp;<b>Partiellement conforme</b> - amélioration possible</span>'
        f'<span>{_compliance_badge_html("A", min_width="auto")} &nbsp;<b>Conforme</b> - bonne pratique respectée</span>'
        f'<span>{_compliance_badge_html("NA", min_width="auto")} &nbsp;<b>Non applicable</b> - critère sans objet pour ce site</span>'
        '</div>'
    )

    source_note = ' <span style="font-size:16px;font-weight:normal;color:#888">(calculé depuis HAR)</span>' if greenit.get("_source") == "har" else ""
    return f"""<section id="greenit">
  <h2>Bonnes pratiques GreenIT-Analysis{source_note}</h2>
  <div style="margin-bottom:8px">{summary}</div>
  {legend}
  <table>
    <thead><tr><th style="width:48px">Niveau</th><th>Bonne pratique</th><th>Description</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


def _section_medias(greenit):
    """Section Lot 4 : contenus médias lourds (vidéos, PDF) — signalement factuel,
    pas de badge A/B/C (pas de seuil universel défendable pour ces formats).
    Retourne "" si aucun média détecté (section absente, pas de ligne vide)."""
    media = (greenit or {}).get("media") or {}
    video = media.get("video", {})
    pdf = media.get("pdf", {})
    if not video.get("count") and not pdf.get("count"):
        return ""

    def _kpi_block(label, data, color):
        if not data.get("count"):
            return ""
        rows = "".join(
            f'<tr><td><a href="{u}" target="_blank" rel="noopener" title="{u}">'
            f'{u.split("/")[-1].split("?")[0][:60] or u[:60]}</a></td>'
            f'<td style="text-align:right">{s} Ko</td></tr>'
            for u, s in data.get("urls", [])
        )
        return f"""<div style="margin-bottom:16px">
  <div class="kpi-grid" style="margin-bottom:8px">
    <div class="kpi"><div class="val">{data['count']}</div><div class="lbl">{label} détecté(s)</div></div>
    <div class="kpi"><div class="val">{data['size_ko']:,} Ko</div><div class="lbl">Poids cumulé</div></div>
  </div>
  <details><summary style="cursor:pointer;color:{color};font-weight:bold">Détail des {data['count']} fichier(s)</summary>
    <table style="margin-top:6px"><tbody>{rows}</tbody></table>
  </details>
</div>"""

    return f"""<section id="medias">
  <h2>Médias et documents à surveiller</h2>
  <p style="font-size:15px;color:#888;margin-bottom:12px">
    Signalement factuel (poids, nombre) : aucun seuil de conformité n'est appliqué ici,
    l'usage attendu d'une vidéo ou d'un PDF variant trop selon le contexte du site pour
    fixer un repère universel.
  </p>
  {_kpi_block("Vidéo", video, TYPE_COLORS.get("video", "#e67e22"))}
  {_kpi_block("PDF", pdf, TYPE_COLORS.get("pdf", "#c0392b"))}
</section>"""


_CONFIDENCE_LEVELS = ("high", "medium", "low", "default", "default_efootprint",
                      "default_script", "unjustified")


def _confidence_badge(conf):
    """Rend un petit badge coloré pour un niveau de confiance.

    "default"/"default_efootprint" : valeur par défaut de la LIBRAIRIE e-footprint
    (ex. archétypes smartphone/laptop). "default_script" : valeur fixée en dur par
    NOTRE script (ex. stockage 50 GB), pas par e-footprint — distinction nécessaire
    car les deux étaient auparavant confondues sous un même badge trompeur.
    "unjustified" : donnée précisée manuellement par la personne qui lance l'audit,
    mais sans justification/source vérifiable fournie (ex. type d'instance choisi
    sans preuve).
    """
    mapping = {
        "high":               ("#1e7e34", "#e8f5e9", "✅", "collecté"),
        "medium":             ("#0f6674", "#e0f4f7", "🔎", "estimé"),
        "low":                ("#9a4d00", "#fff3e0", "❓", "supposé"),
        "default":            ("#5a5a5a", "#eeeeee", "📦", "défaut lib"),
        "default_efootprint": ("#5a5a5a", "#eeeeee", "📦", "défaut lib"),
        "default_script":     ("#33383d", "#e4e5e7", "🛠️", "défaut script"),
        "unjustified":        ("#5a3d34", "#f3e8e4", "✋", "précisé (non justifié)"),
    }
    color, bg, emoji, label = mapping.get(conf, ("#5a5a5a", "#eeeeee", "❔", conf or "?"))
    return (
        f'<span style="background:{bg};border:1.5px solid {color};color:{color};'
        f'font-weight:bold;padding:1px 8px;border-radius:4px;font-size:13px;'
        f'white-space:nowrap">{emoji} {label}</span>'
    )


def _audience_source_label(label, url):
    """Libellé de source du mix pays d'audience, suffixé d'un lien standard
    ("↗ source") vers l'URL de provenance (ex. page SimilarWeb) si fournie."""
    if url:
        return (f'{label} (<a href="{url}" target="_blank" rel="noopener">'
                f'&#8599;&nbsp;source</a>)')
    return label


def _instance_type_row(hyp):
    """Ligne "Type d'instance" avec 3 niveaux de confiance :
    - jamais précisé (--instance non fourni) : valeur par défaut du SCRIPT
      (pas d'e-footprint), badge "défaut script".
    - précisé (--instance fourni) mais sans justification (--instance-source
      absent) : badge "précisé (non justifié)", choix actif mais non vérifié.
    - précisé ET justifié (--instance-source fourni) : badge "estimé", avec
      le texte de justification (et lien source si fourni), sur le modèle de
      _traffic_source_label()/_audience_source_label().

    hyp : dict hypotheses d'efootprint-results.json. Retourne (label_value, conf).
    """
    value = hyp.get("instance_type", "?")
    source_text = hyp.get("instance_type_source")
    source_url = hyp.get("instance_type_source_url")

    if not hyp.get("instance_type_manual"):
        return value, "default_script"

    if not source_text:
        return value, "unjustified"

    label = source_text
    if source_url:
        label = (f'{label} (<a href="{source_url}" target="_blank" rel="noopener">'
                 f'&#8599;&nbsp;source</a>)')
    return f'{value} <span style="color:#888;font-size:0.85em">— {label}</span>', "medium"


def _traffic_source_label(traffic):
    """Libellé de provenance du trafic annuel, avec snapshot et lien source.

    traffic : bloc {source, source_url, snapshot, confidence} d'efootprint-results.json.
    Retourne un libellé lisible ("estimation SimilarWeb, juin 2026 ↗ source",
    "saisie (analytics client)", "hypothèse par défaut") destiné à la colonne source
    des tableaux d'hypothèses."""
    traffic = traffic or {}
    source = traffic.get("source") or "paramètre"
    url = traffic.get("source_url")
    snapshot = traffic.get("snapshot")

    if source == "default":
        return "hypothèse par défaut (100 000/an)"

    label = source
    if snapshot:
        label = f'{label}, {snapshot}'
    if url:
        label = (f'{label} (<a href="{url}" target="_blank" rel="noopener">'
                 f'&#8599;&nbsp;source</a>)')
    return label


def load_efootprint_results(audit_dir):
    """Cherche efootprint-results.json dans audit_dir ou son parent (source_dir)."""
    audit_dir = Path(audit_dir)
    for candidate in [audit_dir / "efootprint-results.json",
                       audit_dir.parent / "efootprint-results.json"]:
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                return json.load(f)
    return None


def load_tech_stack(audit_dir):
    """Cherche le bloc tech_stack dans env-data.json (audit_dir ou parent).

    Même schéma de recherche "audit_dir ou parent" que le HAR / efootprint.
    Retourne le dict tech_stack (technologies/categories/third_party_hosts) ou None
    (env-data.json absent, illisible, ou schéma antérieur à 1.3 sans la clé)."""
    audit_dir = Path(audit_dir)
    for candidate in [audit_dir / "env-data.json",
                      audit_dir.parent / "env-data.json"]:
        if candidate.exists():
            try:
                with open(candidate, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
            return data.get("tech_stack")
    return None


def _section_tech(tech_stack):
    """Section 'Stack technique' — technologies détectées (règles maison sur le HAR).

    Rendue en sous-section d'annexe (caractère documentaire). Groupe les
    technologies par catégorie avec un badge de confiance et l'indice ayant permis
    la détection. Non-régression : retourne "" si tech_stack absent (ancien
    env-data.json)."""
    if not tech_stack:
        return ""

    technos = tech_stack.get("technologies", [])
    third_party = tech_stack.get("third_party_hosts", [])
    req_count = tech_stack.get("request_count", 0)

    if not technos:
        return ""

    # Groupement par catégorie en préservant l'ordre d'arrivée (déjà trié amont)
    by_cat = defaultdict(list)
    for t in technos:
        by_cat[t.get("category", "Autre")].append(t)

    rows = ""
    for cat, items in by_cat.items():
        first = True
        for t in items:
            cat_cell = (
                f'<td style="padding:6px 8px;vertical-align:top;font-weight:600" '
                f'rowspan="{len(items)}">{cat}</td>' if first else ""
            )
            first = False
            rows += (
                f'<tr>'
                f'{cat_cell}'
                f'<td style="padding:6px 8px">{t.get("name", "?")}</td>'
                f'<td style="padding:6px 8px">{_confidence_badge(t.get("confidence"))}</td>'
                f'<td style="padding:6px 8px;color:#666;font-size:14px">{t.get("evidence", "")}</td>'
                f'</tr>'
            )

    tp_html = ""
    if third_party:
        tp_items = "".join(
            f'<li style="display:inline-block;background:{OCTO_PALE};border-radius:4px;'
            f'padding:2px 8px;margin:2px;font-size:14px">{h}</li>'
            for h in third_party
        )
        tp_html = (
            f'<h4 style="margin:20px 0 8px">Hôtes tiers ({len(third_party)})</h4>'
            f'<p style="font-size:14px;color:#666;margin:0 0 6px">Domaines distincts '
            f'du domaine principal sollicités lors du chargement (scripts, polices, '
            f'analytics, CDN externes).</p>'
            f'<ul style="list-style:none;padding:0;margin:0">{tp_items}</ul>'
        )

    return f"""<section id="stack-technique">
  <h2>Stack technique</h2>
  <p style="font-size:16px;color:#555;margin-bottom:8px">
    Technologies détectées par <b>règles maison</b> (pattern-matching hors-ligne sur le
    HAR : en-têtes de réponse, URLs, HTML, cookies). Aucun appel externe, aucune
    dépendance. Détection volontairement limitée aux signaux visibles côté client :
    le backend caché et le type d'instance serveur restent indétectables.
  </p>
  <p style="font-size:15px;color:#666">
    Confiance : {_confidence_badge("high")} signal distinctif
    &nbsp;·&nbsp;
    {_confidence_badge("medium")} signal partagé/indirect
    &nbsp;·&nbsp;
    {_confidence_badge("low")} indice faible (HTML)
  </p>
  <table style="width:100%;border-collapse:collapse;margin-top:8px">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Catégorie</th>
      <th style="padding:6px 8px;text-align:left">Technologie</th>
      <th style="padding:6px 8px;text-align:left">Confiance</th>
      <th style="padding:6px 8px;text-align:left">Indice</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {tp_html}
  <p style="font-size:14px;color:#888;margin-top:12px">
    {len(technos)} technologie(s) détectée(s) sur {req_count} requêtes analysées.
    Pour relancer la détection seule :
    <code>python3 detect_tech.py &lt;source_dir&gt;</code>
  </p>
</section>"""


def _section_efootprint(results):
    """Section 'Impact environnemental (estimation hypothétique)' - CO2e depuis e-footprint."""
    if not results:
        return ""

    totals = results.get("totals", {})
    hyp = results.get("hypotheses", {})
    visits = results.get("visits_per_year", 0)
    traffic = results.get("traffic", {})
    _traffic_is_sourced = traffic.get("source") not in (None, "default", "paramètre")
    _traffic_kpi_sub = (
        f'{traffic.get("source")}{", " + traffic["snapshot"] if traffic.get("snapshot") else ""}'
        if _traffic_is_sourced else "hypothèse"
    )

    total_kg = totals.get("total_kg_co2e_per_year", 0)
    per_visit_g = totals.get("per_visit_g_co2e", 0)
    fab = totals.get("fabrication_kg_co2e_per_year", {})
    ener = totals.get("energy_kg_co2e_per_year", {})

    fab_total = sum(fab.values())
    ener_total = sum(ener.values())

    # KPIs en tête
    kpi_style = (
        "flex:1;min-width:180px;background:white;border:1px solid #ddd;"
        "border-radius:6px;padding:16px;text-align:center"
    )
    kpis = (
        f'<div style="display:flex;flex-wrap:wrap;gap:12px;margin:16px 0 24px">'
        f'  <div style="{kpi_style}">'
        f'    <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px">Total annuel</div>'
        f'    <div style="font-size:28px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">~{total_kg:.1f} kg CO2e</div>'
        f'    <div style="font-size:14px;color:#888">pour {visits:,} visites/an ({_traffic_kpi_sub})</div>'
        f'  </div>'
        f'  <div style="{kpi_style}">'
        f'    <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px">Par visite</div>'
        f'    <div style="font-size:28px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">~{per_visit_g:.2f} g CO2e</div>'
        f'    <div style="font-size:14px;color:#888">ordre de grandeur (hypothèse)</div>'
        f'  </div>'
        f'  <div style="{kpi_style}">'
        f'    <div style="font-size:14px;color:#666;text-transform:uppercase;letter-spacing:1px">Fabrication / Énergie</div>'
        f'    <div style="font-size:24px;font-weight:bold;color:{OCTO_DARK};margin:6px 0">'
        f'{fab_total:.1f} / {ener_total:.1f} kg</div>'
        f'    <div style="font-size:14px;color:#888">amortie / usage annuel</div>'
        f'  </div>'
        f'</div>'
    )

    # Breakdown : barres empilées simples pour fabrication et énergie
    def _breakdown_rows(d, decimals=2):
        total = sum(d.values()) or 1e-9
        rows = ""
        for cat, kg in sorted(d.items(), key=lambda x: -x[1]):
            if kg <= 0:
                continue
            pct = kg / total * 100
            bar = (
                f'<div style="background:#eee;border-radius:3px;height:14px;position:relative;overflow:hidden">'
                f'  <div style="background:{OCTO_BLUE};height:100%;width:{pct:.1f}%"></div>'
                f'</div>'
            )
            rows += (
                f'<tr>'
                f'<td style="padding:6px 8px">{cat}</td>'
                f'<td style="padding:6px 8px;text-align:right;font-variant-numeric:tabular-nums">'
                f'{kg:.{decimals}f} kg</td>'
                f'<td style="padding:6px 8px;text-align:right;color:#666;font-variant-numeric:tabular-nums">'
                f'{pct:.1f} %</td>'
                f'<td style="padding:6px 8px;width:180px">{bar}</td>'
                f'</tr>'
            )
        return rows

    fab_table = f"""<table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Poste (fabrication)</th>
      <th style="padding:6px 8px;text-align:right">kg CO2e/an</th>
      <th style="padding:6px 8px;text-align:right">Part</th>
      <th style="padding:6px 8px">Répartition</th>
    </tr></thead>
    <tbody>{_breakdown_rows(fab, 2)}</tbody>
  </table>"""

    ener_table = f"""<table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Poste (énergie)</th>
      <th style="padding:6px 8px;text-align:right">kg CO2e/an</th>
      <th style="padding:6px 8px;text-align:right">Part</th>
      <th style="padding:6px 8px">Répartition</th>
    </tr></thead>
    <tbody>{_breakdown_rows(ener, 4)}</tbody>
  </table>"""

    # Tableau des hypothèses
    # LOT 1 : page_weight_kb = poids TRANSFÉRÉ (réseau réel) si dispo ; on affiche le
    # décompressé en repère quand les deux diffèrent (env-data >= 1.4).
    _pw_transferred = hyp.get("page_weight_transferred_kb")
    _pw_uncompressed = hyp.get("page_weight_uncompressed_kb")
    if _pw_transferred:
        _ratio = hyp.get("compression_ratio")
        _pw_label = "Poids page transféré (réseau réel)"
        _pw_repere = f' <span style="color:#888">(décompressé : {_pw_uncompressed} kB'
        _pw_repere += f', ratio {_ratio})</span>' if _ratio else ')</span>'
        _pw_value = f'{hyp.get("page_weight_kb", "?")} kB{_pw_repere}'
    else:
        _pw_label = "Poids de page (représentative)"
        _pw_value = f'{hyp.get("page_weight_kb", "?")} kB'
    hyp_rows = [
        (_pw_label, _pw_value,                                                          hyp.get("confidence_page_weight")),
        ("Durée chargement",                f'{hyp.get("request_duration_ms", "?")} ms', hyp.get("confidence_request_duration")),
        ("Pays hébergement",                hyp.get("country", "?"),                     hyp.get("confidence_country")),
        ("Intensité carbone électricité",   f'{hyp.get("carbon_intensity_g_kwh", "?")} g/kWh', hyp.get("confidence_carbon_intensity")),
        ("Provider hébergeur",              hyp.get("provider", "?"),                    hyp.get("confidence_provider")),
        ("Instance type",                   *_instance_type_row(hyp)),
        ("Mix device (mobile / desktop)",   f'{hyp.get("phone_fraction", 0):.0%} / {hyp.get("desktop_fraction", 0):.0%}',  hyp.get("confidence_device_mix")),
    ]
    audience_mix = hyp.get("audience_mix")
    if audience_mix:
        _asrc = hyp.get("audience_source", "default")
        if _asrc == "default":
            _asrc_short = "default"
        elif isinstance(_asrc, str) and "similarweb" in _asrc.lower():
            _asrc_short = "SimilarWeb (estimé)"
        elif isinstance(_asrc, str) and _asrc.startswith("saisie"):
            _asrc_short = "saisie manuelle"
        else:
            _asrc_short = "estimé"
        hyp_rows.append(
            ("Mix pays d'audience (→ iOS/macOS)",
             ", ".join(f'{cc} {w:.0%}' for cc, w in audience_mix.items()),
             _audience_source_label(_asrc_short, hyp.get("audience_source_url"))))
    hyp_rows += [
        ("Réseau (déduit du mix appareils)", "mobile → réseau mobile ; desktop → wifi", "déduit"),
        ("Trafic annuel estimé",            f'{visits:,} visites',                       _traffic_source_label(traffic)),
        ("Stockage serveur",                f'{hyp.get("storage_gb", 50)} GB',           "default_script"),
    ]
    hyp_html = "".join(
        f'<tr>'
        f'<td style="padding:6px 8px">{label}</td>'
        f'<td style="padding:6px 8px"><b>{value}</b></td>'
        f'<td style="padding:6px 8px">{_confidence_badge(conf)}</td>'
        f'</tr>'
        for label, value, conf in hyp_rows
    )

    warning = (
        f'<div style="background:#fff3cd;border-left:4px solid #ffc107;'
        f'padding:12px 16px;margin:16px 0;border-radius:4px">'
        f'<b>&#9888; Estimation hypothétique</b><br>'
        f'Ces valeurs sont des <b>ordres de grandeur</b> calculés à partir de données '
        f'collectées automatiquement (HAR, CrUX, géoloc IP) et de nombreuses hypothèses '
        f'par défaut. Elles <b>ne constituent pas une mesure réelle</b>. Elles servent '
        f'à comparer des scénarios et identifier les postes dominants.'
        f'</div>'
    )

    # Composition du poids de la page (documentaire : explique l'input, n'entre pas
    # dans le calcul CO2e qui repose sur le poids total agrégé de page_weight_kb).
    # LOT 4 : poids TRANSFÉRÉ (réseau réel, LOT 1) en valeur principale si dispo,
    # décompressé en repère — cohérence avec page_weight_kb ci-dessus.
    weight_by_type_transfer = hyp.get("weight_by_type_transfer_bytes") or {}
    weight_by_type_uncompressed = hyp.get("weight_by_type_bytes") or {}
    weight_by_type = weight_by_type_transfer or weight_by_type_uncompressed
    _using_transfer = bool(weight_by_type_transfer)
    weight_composition = ""
    if weight_by_type:
        _type_labels = {
            "html": "HTML", "css": "CSS", "js": "JavaScript",
            "image": "Images", "font": "Polices", "autre": "Autres",
        }
        _wtotal = sum(v for v in weight_by_type.values() if v > 0) or 1e-9
        comp_rows = ""
        for typ, nbytes in sorted(weight_by_type.items(), key=lambda x: -x[1]):
            if nbytes <= 0:
                continue
            pct = nbytes / _wtotal * 100
            kb = nbytes / 1024
            kb_uncompressed = weight_by_type_uncompressed.get(typ, 0) / 1024
            repere = (
                f' <span style="color:#888;font-size:13px">(décompressé : {kb_uncompressed:,.0f} Ko)</span>'
                if _using_transfer and weight_by_type_uncompressed else ""
            )
            bar = (
                f'<div style="background:#eee;border-radius:3px;height:14px;position:relative;overflow:hidden">'
                f'  <div style="background:{OCTO_BLUE};height:100%;width:{pct:.1f}%"></div>'
                f'</div>'
            )
            comp_rows += (
                f'<tr>'
                f'<td style="padding:6px 8px">{_type_labels.get(typ, typ)}</td>'
                f'<td style="padding:6px 8px;text-align:right;font-variant-numeric:tabular-nums">'
                f'{kb:,.0f} Ko{repere}</td>'
                f'<td style="padding:6px 8px;text-align:right;color:#666;font-variant-numeric:tabular-nums">'
                f'{pct:.1f} %</td>'
                f'<td style="padding:6px 8px;width:180px">{bar}</td>'
                f'</tr>'
            )
        req_count = hyp.get("page_request_count")
        tp_share = hyp.get("third_party_transfer_share") if _using_transfer else hyp.get("third_party_share")
        tp_requests = hyp.get("third_party_requests")
        tp_bytes = hyp.get("third_party_transfer_bytes") if _using_transfer else hyp.get("third_party_bytes")
        meta_bits = []
        if req_count is not None:
            meta_bits.append(f'{req_count} requêtes')
        if tp_share is not None:
            _tp_extra = ""
            if tp_requests is not None and tp_bytes is not None:
                _tp_extra = f' ({tp_requests} requêtes, {tp_bytes / 1024:,.0f} Ko)'
            meta_bits.append(
                f'ressources tierces : <b>{tp_share * 100:.1f} %</b> du poids{_tp_extra}')
        meta_line = (
            f'<p style="font-size:14px;color:#666;margin:8px 0 0">{" &nbsp;·&nbsp; ".join(meta_bits)}</p>'
            if meta_bits else ""
        )
        _poids_label = "poids transféré (réseau réel)" if _using_transfer else "poids décompressé"
        weight_composition = f"""
  <h3 style="margin-top:24px">Composition du poids de la page représentative</h3>
  <p style="font-size:14px;color:#888;margin:0 0 8px">
    Répartition par type de ressource de la page la plus lourde du parcours (celle qui
    sert de poids de référence au calcul), en {_poids_label}. Documentaire : cette
    décomposition <b>explique</b> le poids retenu, elle <b>n'entre pas séparément dans le
    calcul CO2e</b>.
  </p>
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Type de ressource</th>
      <th style="padding:6px 8px;text-align:right">Poids</th>
      <th style="padding:6px 8px;text-align:right">Part</th>
      <th style="padding:6px 8px">Répartition</th>
    </tr></thead>
    <tbody>{comp_rows}</tbody>
  </table>
  {meta_line}"""

    dominant_fab = max(fab, key=fab.get) if fab else "?"
    dominant_ener = max(ener, key=ener.get) if ener else "?"

    return f"""<section id="efootprint">
  <h2>Impact environnemental (estimation CO2e)</h2>
  <p style="font-size:16px;color:#555;margin-bottom:8px">
    Estimation via la librairie <a href="https://github.com/Boavizta/e-footprint" target="_blank" rel="noopener">e-footprint</a> (Boavizta).
    Poste dominant en fabrication : <b>{dominant_fab}</b> ({fab.get(dominant_fab, 0):.1f} kg CO2e/an).
    Poste dominant en énergie : <b>{dominant_ener}</b> ({ener.get(dominant_ener, 0):.3f} kg CO2e/an).
  </p>
  {warning}
  {kpis}

  <h3 style="margin-top:24px">Décomposition par poste</h3>
  <div style="display:grid;grid-template-columns:1fr;gap:20px">
    <div>
      <h4 style="margin:0 0 8px">Fabrication (amortie sur la durée de vie)</h4>
      {fab_table}
    </div>
    <div>
      <h4 style="margin:0 0 8px">Énergie (usage annuel)</h4>
      {ener_table}
    </div>
  </div>
  {weight_composition}

  <h3 style="margin-top:24px">Hypothèses d'entrée</h3>
  <p style="font-size:15px;color:#666">
    Niveau de confiance : {_confidence_badge("high")} API/HAR
    &nbsp;·&nbsp;
    {_confidence_badge("medium")} inféré ou déclaré avec justification
    &nbsp;·&nbsp;
    {_confidence_badge("low")} valeur type
    &nbsp;·&nbsp;
    {_confidence_badge("unjustified")} choix manuel sans preuve
    &nbsp;·&nbsp;
    {_confidence_badge("default_efootprint")} valeur par défaut de la librairie e-footprint
    &nbsp;·&nbsp;
    {_confidence_badge("default_script")} valeur fixée par notre script (pas e-footprint)
  </p>
  <table style="width:100%;border-collapse:collapse;margin-top:8px">
    <thead><tr style="background:{OCTO_PALE}">
      <th style="padding:6px 8px;text-align:left">Paramètre</th>
      <th style="padding:6px 8px;text-align:left">Valeur retenue</th>
      <th style="padding:6px 8px;text-align:left">Source</th>
    </tr></thead>
    <tbody>{hyp_html}</tbody>
  </table>

  <p style="font-size:14px;color:#888;margin-top:12px">
    Pour recalculer avec d'autres hypothèses :
    <code>python3 run_efootprint.py &lt;source_dir&gt; --visits N --instance TYPE</code>
    puis régénérer le rapport.
  </p>
</section>"""


def _methodo_table(rows):
    """Rend un tableau Paramètre / Valeur / Source-confiance pour l'annexe méthodo.

    rows : liste de (label, valeur, confiance|libellé). Si la confiance correspond
    à un niveau connu (cf. _CONFIDENCE_LEVELS), affiche le badge ; sinon texte brut.
    """
    body = ""
    for label, value, conf in rows:
        if conf in _CONFIDENCE_LEVELS:
            src = _confidence_badge(conf)
        else:
            src = f'<span style="font-size:14px;color:#666">{conf}</span>'
        body += (f'<tr>'
                 f'<td style="padding:5px 8px">{label}</td>'
                 f'<td style="padding:5px 8px"><b>{value}</b></td>'
                 f'<td style="padding:5px 8px">{src}</td>'
                 f'</tr>')
    return (f'<table style="width:100%;border-collapse:collapse;margin-top:6px">'
            f'<thead><tr style="background:{OCTO_PALE}">'
            f'<th style="padding:6px 8px;text-align:left">Paramètre</th>'
            f'<th style="padding:6px 8px;text-align:left">Valeur retenue</th>'
            f'<th style="padding:6px 8px;text-align:left">Source</th>'
            f'</tr></thead><tbody>{body}</tbody></table>')


def _methodo_efootprint(efootprint_results):
    """Sous-section A : hypothèses ET méthodes du calcul CO2e."""
    if not efootprint_results:
        return ""
    hyp = efootprint_results.get("hypotheses", {})
    visits = efootprint_results.get("visits_per_year", 0)
    traffic = efootprint_results.get("traffic", {})

    def pct(v):
        return f'{v:.0%}' if isinstance(v, (int, float)) else "?"

    # Trafic : valeur mensuelle en note si dispo (ex. 36 700/mois × 12)
    _monthly = traffic.get("monthly_visits")
    _visits_val = (f'{visits:,} visites (≈ {_monthly:,}/mois × 12)'
                   if _monthly else f'{visits:,} visites')

    # --- Tableau des données/hypothèses ---
    # LOT 1 : poids transféré (réseau réel) en valeur ; décompressé en repère si dispo.
    _pw_transferred_m = hyp.get("page_weight_transferred_kb")
    if _pw_transferred_m:
        _ratio_m = hyp.get("compression_ratio")
        _repere_m = f' <span style="color:#888">(décompressé : {hyp.get("page_weight_uncompressed_kb")} kB'
        _repere_m += f', ratio {_ratio_m})</span>' if _ratio_m else ')</span>'
        _pw_row = ("Poids page transféré (réseau réel)",
                   f'{hyp.get("page_weight_kb", "?")} kB{_repere_m}',
                   hyp.get("confidence_page_weight", "default"))
    else:
        _pw_row = ("Poids de page (représentative)",
                   f'{hyp.get("page_weight_kb", "?")} kB',
                   hyp.get("confidence_page_weight", "default"))
    rows = [
        _pw_row,
        ("Durée de chargement", f'{hyp.get("request_duration_ms", "?")} ms', hyp.get("confidence_request_duration", "default")),
        ("Pays d'hébergement", hyp.get("country", "?"), hyp.get("confidence_country", "default")),
        ("Intensité carbone électricité", f'{hyp.get("carbon_intensity_g_kwh", "?")} g/kWh', hyp.get("confidence_carbon_intensity", "default")),
        ("Provider hébergeur", hyp.get("provider", "?"), hyp.get("confidence_provider", "default")),
        ("Type d'instance", *_instance_type_row(hyp)),
        ("Trafic annuel", _visits_val, _traffic_source_label(traffic)),
    ]
    # Mix pays d'audience (sert à pondérer iOS/macOS)
    audience_mix = hyp.get("audience_mix")
    if audience_mix:
        mix_str = ", ".join(f'{cc} {w:.0%}' for cc, w in audience_mix.items())
        rows.append(("Mix pays d'audience", mix_str,
                     _audience_source_label(hyp.get("audience_source", "default"),
                                            hyp.get("audience_source_url"))))
    # Mix appareils : brut CrUX (si dispo) + retenu corrigé
    mob_raw = hyp.get("mobile_fraction_raw")
    if mob_raw is not None:
        rows.append(("Mix brut CrUX (mobile / desktop)",
                     f'{pct(mob_raw)} / {pct(hyp.get("desktop_fraction_raw"))} '
                     f'(dont phone {pct(hyp.get("phone_fraction_raw"))}, tablette {pct(hyp.get("tablet_fraction_raw"))})',
                     hyp.get("device_mix_source", "crux")))
        rows.append(("Part iOS retenue (correction mobile)",
                     pct(hyp.get("ios_share_used")),
                     hyp.get("ios_share_source", "?")))
        rows.append(("Part macOS retenue (correction desktop)",
                     pct(hyp.get("macos_share_used")),
                     hyp.get("macos_share_source", "?")))
    rows.append(("Mix appareils retenu (mobile / desktop)",
                 f'{pct(hyp.get("phone_fraction"))} / {pct(hyp.get("desktop_fraction"))}',
                 hyp.get("confidence_device_mix", "default")))
    rows.append(("Split du trafic (mobile / desktop)",
                 f'{hyp.get("visits_mobile", "?"):,} / {hyp.get("visits_desktop", "?"):,} visites'
                 if isinstance(hyp.get("visits_mobile"), int) else "?",
                 "dérivé du mix"))
    rows.append(("Réseau (déduit du mix appareils)",
                 "mobile → réseau mobile ; desktop → wifi",
                 "déduit du mix appareils"))
    rows.append(("Stockage serveur", f'{hyp.get("storage_gb", 50)} GB', "default_script"))
    rows.append(("Appareils modélisés (e-footprint)", "smartphone + laptop (archétypes lib)", "default_efootprint"))

    table = _methodo_table(rows)

    # --- Fourchette de scénarios iOS ---
    scenarios_html = ""
    sc = hyp.get("device_scenarios")
    if sc:
        sc_rows = ""
        for key, human in (("conservateur", "Conservateur"), ("central", "Central (retenu)"), ("apple_heavy", "Audience Apple")):
            s = sc.get(key, {})
            sc_rows += (f'<tr><td style="padding:5px 8px">{human}</td>'
                        f'<td style="padding:5px 8px">part iOS {pct(s.get("ios_share"))}</td>'
                        f'<td style="padding:5px 8px"><b>{pct(s.get("mobile"))}</b> mobile / {pct(s.get("desktop"))} desktop</td></tr>')
        scenarios_html = (
            f'<h4 style="margin:14px 0 4px">Fourchette du mix selon la part iOS</h4>'
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr style="background:{OCTO_PALE}">'
            f'<th style="padding:6px 8px;text-align:left">Scénario</th>'
            f'<th style="padding:6px 8px;text-align:left">Hypothèse</th>'
            f'<th style="padding:6px 8px;text-align:left">Mix résultant</th>'
            f'</tr></thead><tbody>{sc_rows}</tbody></table>')

    # --- Détail du mix pays d'audience (pondération iOS/macOS) ---
    audience_html = ""
    per_country = hyp.get("audience_per_country")
    if per_country:
        ac_rows = ""
        for d in per_country:
            flag_note = "" if d.get("in_table") else ' <span style="color:#999;font-size:13px">(valeur monde par défaut)</span>'
            ac_rows += (f'<tr><td style="padding:5px 8px">{_country_label(d.get("country"))}{flag_note}</td>'
                        f'<td style="padding:5px 8px">{pct(d.get("weight"))}</td>'
                        f'<td style="padding:5px 8px">{pct(d.get("ios_share"))}</td>'
                        f'<td style="padding:5px 8px">{pct(d.get("macos_share"))}</td></tr>')
        ios_w = hyp.get("audience_ios_weighted")
        mac_w = hyp.get("audience_macos_weighted")
        ac_foot = (f'<tr style="background:{OCTO_PALE};font-weight:bold">'
                   f'<td style="padding:5px 8px">Pondéré (retenu)</td>'
                   f'<td style="padding:5px 8px">100 %</td>'
                   f'<td style="padding:5px 8px">{pct(ios_w)}</td>'
                   f'<td style="padding:5px 8px">{pct(mac_w)}</td></tr>')
        src = hyp.get("audience_source", "default")
        src_url = hyp.get("audience_source_url")
        _src_link = f' (<a href="{src_url}" target="_blank" rel="noopener">&#8599;&nbsp;source</a>)' if src_url else ""
        caveat = ""
        if isinstance(src, str) and "similarweb" in src.lower():
            caveat = ('<p style="font-size:14px;color:#888;margin:4px 0 0">'
                      'Mix pays estimé via SimilarWeb (page publique, source non officielle, '
                      'usage limite CGU, potentiellement indisponible) : ordre de grandeur, '
                      'à confirmer avec l\'analytics du site (GA/Matomo) via <code>--audience</code>.</p>')
        elif src == "default":
            caveat = ('<p style="font-size:14px;color:#888;margin:4px 0 0">'
                      'Aucun mix pays fourni : France (100 %) par défaut. Fournir '
                      '<code>--audience "FR:0.7,US:0.3"</code> ou laisser l\'agent estimer via SimilarWeb.</p>')
        audience_html = (
            f'<h4 style="margin:14px 0 4px">Mix pays d\'audience (pondération iOS / macOS)</h4>'
            f'<p style="font-size:15px;color:#666;margin:0 0 4px">Source : {src}{_src_link}. '
            f'Ce mix ne sert QU\'À pondérer les parts iOS/macOS de la correction CrUX '
            f'(CrUX n\'a pas de dimension pays) ; il ne modifie pas les Core Web Vitals.</p>'
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr style="background:{OCTO_PALE}">'
            f'<th style="padding:6px 8px;text-align:left">Pays</th>'
            f'<th style="padding:6px 8px;text-align:left">Poids audience</th>'
            f'<th style="padding:6px 8px;text-align:left">Part iOS (mobile)</th>'
            f'<th style="padding:6px 8px;text-align:left">Part macOS (desktop)</th>'
            f'</tr></thead><tbody>{ac_rows}{ac_foot}</tbody></table>{caveat}')

    # --- LOT 2/3 : signaux serveur/réseau factuels annexés (documentaire) ---
    har_facts_html = ""
    hf = hyp.get("har_facts")
    if hf:
        conf_hf = hyp.get("confidence_har_facts", "high")
        methods_str = ", ".join(f'{v}×{k}' for k, v in sorted(hf.get("methods", {}).items(), key=lambda kv: -kv[1]))
        statuses_str = ", ".join(f'{v}×{k}' for k, v in sorted(hf.get("statuses", {}).items(), key=lambda kv: -kv[1]))
        cache_bytes_kb = round(hf.get("cache_304_uncompressed_bytes", 0) / 1024)
        hf_rows = [
            ("Requêtes servies depuis le cache navigateur (304)",
             f'{hf.get("cache_304_count", 0)} / {hf.get("request_count", 0)} '
             f'({pct(hf.get("cache_304_share"))}, ≈ {cache_bytes_kb} kB non retéléchargés)',
             conf_hf),
            ("Temps d'attente serveur (TTFB, wait)",
             f'médiane {hf.get("wait_ms_median", "?")} ms, p95 {hf.get("wait_ms_p95", "?")} ms',
             conf_hf),
            ("Méthodes HTTP", methods_str or "?", conf_hf),
            ("Statuts HTTP", statuses_str or "?", conf_hf),
            ("Version HTTP dominante", hf.get("dominant_http_version", "?"), conf_hf),
        ]
        har_facts_html = (
            f'<h4 style="margin:14px 0 4px">Signaux réseau/serveur factuels (annexe)</h4>'
            f'<p style="font-size:14px;color:#888;margin:0 0 4px">'
            f'{hf.get("note", "Documentaire, n\'entre pas dans le calcul CO2e.")}</p>'
            f'{_methodo_table(hf_rows)}'
        )

    # --- Méthodes / formules ---
    methods = (
        '<h4 style="margin:14px 0 4px">Méthodes appliquées</h4>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        '<li><b>Correction CrUX symétrique (iOS + macOS).</b> CrUX ne mesure que Chrome : '
        'côté mobile les iPhone/iPad (Safari, et même Chrome sur iOS) sont absents ; côté '
        'desktop les Mac sous Safari le sont aussi. On regonfle les <b>deux</b> côtés par '
        '<code>mobile_corrigé = mobile_brut / (1 − part_iOS)</code> et '
        '<code>desktop_corrigé = desktop_brut / (1 − part_macOS)</code>, puis on renormalise '
        'l\'ensemble à 100 %. Corriger aussi le desktop supprime le biais "pro-mobile" de '
        'l\'ancienne correction unilatérale.</li>'
        '<li><b>Pondération par mix pays d\'audience.</b> Les parts iOS et macOS dépendent '
        'du pays. Elles sont donc pondérées par le mix pays d\'audience (voir tableau ci-dessus). '
        'Ordre de résolution du mix : <code>--audience</code> saisi (analytics client) &gt; '
        'estimation SimilarWeb écrite par l\'agent &gt; France (100 %) par défaut. CrUX n\'ayant '
        'aucune dimension géographique, ce mix ne sert QU\'À cette pondération, jamais aux CWV.</li>'
        '<li><b>Rattachement tablette.</b> La tablette est comptée avec le mobile '
        '(logique tactile/portable). Le corps du rapport n\'affiche que mobile/desktop ; '
        'le détail figure ci-dessus.</li>'
        '<li><b>Pondération du CO2e.</b> Le trafic est réparti en <b>deux profils d\'usage</b> '
        '(mobile → smartphone + réseau mobile ; desktop → laptop + wifi), avec des volumes '
        'proportionnels au mix. Ceci corrige un surcomptage antérieur où chaque visite était '
        'facturée à 100 % sur smartphone ET laptop.</li>'
        '<li><b>Nature des chiffres.</b> Ordres de grandeur hypothétiques (données HAR/CrUX/géoloc IP '
        '+ valeurs par défaut), pas une mesure réelle.</li>'
        '</ul>'
    )

    return (f'<h3 id="methodo-efootprint" style="margin-top:20px">A. Impact environnemental (CO2e)</h3>'
            f'{table}{audience_html}{scenarios_html}{har_facts_html}{methods}')


def _methodo_cwv(cwv):
    """Sous-section B : sources et limites des Core Web Vitals."""
    if not cwv:
        return ""
    sources = {row.get("source")
               for by_strat in cwv.values() if isinstance(by_strat, dict)
               for row in by_strat.values() if row}
    src_items = "".join(
        f'<li><b>{_CWV_SOURCE_LABELS[s][0]}</b> : {_CWV_SOURCE_LABELS[s][2]}</li>'
        for s in ("crux", "pagespeed_lab", "lighthouse") if s in sources
    ) or '<li>Source non renseignée</li>'
    return (
        '<h3 id="methodo-cwv" style="margin-top:20px">B. Core Web Vitals</h3>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        f'<li><b>Sources présentes :</b><ul style="margin:2px 0 6px 16px">{src_items}</ul></li>'
        '<li><b>CrUX = terrain Chrome.</b> Les données "terrain" proviennent du champ '
        '<code>loadingExperience</code> de la réponse PageSpeed Insights (percentiles P75 '
        'des utilisateurs Chrome réels) : ce n\'est PAS un appel dédié à l\'API CrUX.</li>'
        '<li><b>Limite iOS/Safari.</b> Comme le mix appareils, le terrain CrUX ne couvre '
        'que Chrome ; les utilisateurs iOS/Safari ne sont pas représentés.</li>'
        '<li><b>Mobile ET desktop, "pire des deux" par métrique.</b> Les deux stratégies '
        'PageSpeed sont collectées. Dans le tableau de bord et les recommandations, chaque '
        'métrique (LCP, INP, CLS) retient la valeur la <b>plus défavorable</b> entre mobile '
        'et desktop, indépendamment métrique par métrique (un pictogramme 📱/🖥 signale '
        'l\'appareil retenu). Un problème desktop remonte donc dans les recos. Le détail '
        'mobile + desktop côte à côte reste consultable dans la section "Analyse Core Web '
        'Vitals". Seuils : LCP &lt; 1,8 s bon / 1,8-2,5 s à améliorer / &gt; 2,5 s mauvais ; '
        'INP 200/500 ms ; CLS 0,1/0,25.</li>'
        '<li><b>Lab (simulation).</b> Les sources "lab" (PageSpeed lab ou Lighthouse local) '
        'sont des simulations à réseau/CPU bridés, généralement plus pessimistes que le terrain.</li>'
        '<li><b>Signaux indicatifs (diagnostic causal).</b> Quand un problème LCP/INP/CLS est '
        'détecté, le rapport ajoute un signal croisé avec des données déjà collectées (trackers, '
        'polices web externes, ressource la plus lourde du parcours, taux de JS non utilisé). '
        'Ce sont des corrélations, pas des causes confirmées : le HAR ne capture ni le JS exécuté '
        'réellement au runtime, ni le rendu réel de la page (pas de mesure DOM/CSS). À vérifier '
        'manuellement avant conclusion.</li>'
        '</ul>'
    )


def _methodo_ecoindex():
    """Sous-section C : formule EcoIndex."""
    return (
        '<h3 id="methodo-ecoindex" style="margin-top:20px">C. EcoIndex / GreenIT</h3>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        '<li><b>Formule (cnumr/ecoindex_reference) :</b> '
        '<code>score = 100 − 5 × (3·q_DOM + 2·q_req + q_poids) / 6</code>, '
        'où q_x est le rang (0-20) de la valeur dans les quantiles de référence '
        '(nombre d\'éléments DOM, nombre de requêtes, poids en Ko).</li>'
        '<li><b>Grades :</b> A ≥ 80, B ≥ 70, C ≥ 55, D ≥ 40, E ≥ 25, F ≥ 10, G sinon.</li>'
        '<li><b>Entrées :</b> DOM, requêtes et poids sont extraits du HAR de la capture.</li>'
        '</ul>'
    )


def _methodo_medias():
    """Sous-section E : limites des règles médias (Lot 4)."""
    return (
        '<h3 id="methodo-medias" style="margin-top:20px">E. Médias et documents à surveiller</h3>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        '<li><b>Seuils "image bitmap lourde" (200 Ko) et "SVG suspect" (30 Ko).</b> '
        'Heuristiques internes non sourcées (aucun référentiel GreenIT-Analysis/EcoIndex '
        'officiel ne fixe de seuil de poids en Ko pour ces règles) — <b>confiance faible</b>, '
        'à ajuster si un référentiel documenté est identifié.</li>'
        '<li><b>Gain estimé format WebP (-31,5 % à -50,3 %).</b> Chiffres forfaitaires cnumr '
        'appliqués au poids cumulé des images concernées, sans mesure réelle par image ni '
        'distinction JPEG/PNG source.</li>'
        '<li><b>SVG "faux" (probable bitmap encodé en base64).</b> Signal de poids anormal, pas '
        'une confirmation : un SVG légitimement complexe (carte, illustration détaillée) peut '
        'aussi dépasser le seuil sans contenir de bitmap.</li>'
        '<li><b>Surdimensionnement réel non mesurable.</b> Le pipeline n\'effectue aucune capture '
        'du DOM/CSS de rendu (pas de Puppeteer/Playwright/CDP) : impossible de comparer le poids '
        'du fichier à sa taille d\'affichage réelle. Les règles média restent au niveau "poids '
        'brut vs seuil", pas "surdimensionnement mesuré".</li>'
        '<li><b>Vidéos et PDF.</b> Signalement factuel (poids, nombre), sans badge de conformité : '
        'aucun seuil universel ne serait défendable, l\'usage attendu variant trop selon le site.</li>'
        '</ul>'
    )


def _methodo_trafic(efootprint_results=None):
    """Sous-section D : trafic et réseau. Décrit la provenance réelle du volume
    de trafic (saisie analytics, estimation SimilarWeb, ou baseline par défaut)."""
    traffic = (efootprint_results or {}).get("traffic", {})
    source = traffic.get("source")
    url = traffic.get("source_url")
    snapshot = traffic.get("snapshot")
    monthly = traffic.get("monthly_visits")
    visits = (efootprint_results or {}).get("visits_per_year")

    if source and source not in ("default", "paramètre"):
        src_txt = source
        if snapshot:
            src_txt += f', {snapshot}'
        if url:
            src_txt += (f' (<a href="{url}" target="_blank" rel="noopener">'
                        f'&#8599;&nbsp;source</a>)')
        derivation = ""
        if monthly and visits:
            derivation = (f' Dérivation : {monthly:,}/mois × 12 ≈ {visits:,}/an.')
        volume_li = (
            f'<li><b>Volume de trafic.</b> Estimation tierce : <b>{src_txt}</b>.{derivation} '
            'Ni PageSpeed ni CrUX ne fournissent de volume d\'audience (leurs API ne renvoient '
            'que des distributions, jamais de compteurs) ; les estimateurs tiers restent des '
            '<b>estimations à marge large</b>, à ne pas prendre pour une mesure. '
            'Un chiffre exact ne peut venir que des analytics du site (GA4/Matomo/logs).</li>'
            '<li><b>Sensibilité au volume.</b> Le CO2e <b>total</b> croît avec le trafic, au-dessus '
            'd\'un <b>socle fixe</b> (fabrication serveur + stockage, amorti quel que soit le trafic) : '
            'la relation est <b>affine, pas strictement proportionnelle</b>. Le CO2e <b>par visite</b> '
            '<b>diminue</b> donc quand le trafic augmente (le socle se répartit sur plus de visites). '
            'Une erreur sur le volume déplace surtout l\'ordre de grandeur du total, moins le par-visite.</li>'
        )
    else:
        volume_li = (
            '<li><b>Volume de trafic.</b> Le nombre de visites/an est une <b>hypothèse par défaut</b> '
            '(100 000/an) : ni PageSpeed ni CrUX ne fournissent de volume d\'audience (leurs API ne '
            'renvoient que des distributions, jamais de compteurs). Pour fiabiliser : saisir les '
            'analytics du site (<code>--visits</code>) ou une estimation SimilarWeb.</li>'
            '<li><b>Sensibilité au volume.</b> Le CO2e <b>total</b> croît avec le trafic au-dessus '
            'd\'un socle fixe (fabrication serveur + stockage) ; le CO2e <b>par visite</b> diminue '
            'quand le trafic augmente.</li>'
        )

    return (
        '<h3 id="methodo-trafic" style="margin-top:20px">D. Trafic &amp; réseau</h3>'
        '<ul style="margin:0 0 0 16px;padding:0;font-size:16px;color:#555;line-height:1.5">'
        f'{volume_li}'
        '<li><b>Volumétrie réseau.</b> Le poids transféré et le nombre de requêtes viennent '
        'du HAR (mesure réelle de la capture), à ne pas confondre avec un volume d\'audience.</li>'
        '</ul>'
    )


def _section_methodologie(efootprint_results, cwv):
    """Annexe méthodologique structurée par section (A: CO2e, B: CWV, C: EcoIndex, D: trafic,
    E: médias).

    Trace toutes les données et hypothèses des calculs : valeur, source, confiance,
    et les méthodes/formules appliquées."""
    parts = [
        _methodo_efootprint(efootprint_results),
        _methodo_cwv(cwv),
        _methodo_ecoindex(),
        _methodo_trafic(efootprint_results),
        _methodo_medias(),
    ]
    body = "".join(p for p in parts if p)
    return (
        '<section id="methodologie">\n'
        '<h2>Méthodologie &amp; hypothèses</h2>\n'
        '<p style="font-size:16px;color:#555;margin-bottom:8px">'
        'Cette annexe recense, par domaine, les données et hypothèses entrant dans '
        'chaque calcul (valeur, source, niveau de confiance) ainsi que les méthodes appliquées.</p>\n'
        f'{body}\n'
        '</section>'
    )


def _section_couts(page_metrics):
    # Formule EcoIndex officielle : 1 visite = (1.8 - score/100 * 1.8) gCO2e (approx cnumr)
    # Source : https://www.ecoindex.fr/comment-ca-marche
    deduped = _dedup_page_metrics(page_metrics)
    rows = ""
    total_co2 = 0.0
    total_energy = 0.0
    for m in deduped:
        score = m["ecoindex"]
        co2 = round((1.0 - score / 100) * 1.8 + 0.013, 3)   # gCO2e / visite
        energy = round((1.0 - score / 100) * 1.5 + 0.013, 3) # Wh / visite
        total_co2 += co2
        total_energy += energy
        url = m["title"]
        label = "/" + url.split("//", 1)[-1].split("/", 1)[-1] if "//" in url else url
        badge = _badge(m["grade"], m["grade_color"])
        rows += (
            f'<tr><td>{badge}</td>'
            f'<td><a href="{url}" target="_blank" title="{url}">{label}</a></td>'
            f'<td style="text-align:right">{score}/100</td>'
            f'<td style="text-align:right">{co2:.3f} gCO2e</td>'
            f'<td style="text-align:right">{energy:.3f} Wh</td></tr>\n'
        )
    return f"""<section id="couts">
  <h2>Couts de generation</h2>
  <p style="font-size:16px;color:#666;margin-bottom:12px">
    Estimation par visite, basee sur le score EcoIndex (formule cnumr/ecoindex_reference).
    1 visite = transfert reseau + rendu navigateur + serveur.
  </p>
  <table>
    <thead><tr>
      <th style="width:48px">Grade</th>
      <th>Page</th>
      <th style="text-align:right">EcoIndex</th>
      <th style="text-align:right">CO2 / visite</th>
      <th style="text-align:right">Energie / visite</th>
    </tr></thead>
    <tbody>{rows}</tbody>
    <tfoot><tr style="font-weight:bold;background:#f4f6fa">
      <td colspan="3">Total parcours ({len(deduped)} pages)</td>
      <td style="text-align:right">{total_co2:.3f} gCO2e</td>
      <td style="text-align:right">{total_energy:.3f} Wh</td>
    </tr></tfoot>
  </table>
  <p style="font-size:15px;color:#999;margin-top:8px">
    Pour reference : un email envoye = ~4 gCO2e ; une recherche Google = ~0.2 gCO2e.
  </p>
</section>"""


def _cwv_reco_signal_html(metric, traffic, greenit, coverage_by_page):
    """Lot 5 (recommandations) : version courte du signal indicatif de
    _cwv_diagnostic_signal(), avec renvoi vers le détail en section Analyse CWV.
    Retourne une chaîne vide si aucun signal exploitable (même logique de calcul
    que la section détaillée, texte raccourci uniquement)."""
    long_signal = _cwv_diagnostic_signal(f"{metric}_x", traffic, greenit, coverage_by_page)
    if not long_signal:
        return ""
    short = {
        "cls": "trackers tiers et/ou police(s) web externe(s) détectés",
        "inp": "JS non utilisé &gt; 60 % relevé",
    }.get(metric)
    if not short:
        return ""
    return (f'<br><span style="color:#888;font-size:0.85em">Signal : {short} '
            f'(détail en <a href="#cwv-analyse">section Analyse CWV</a>).</span>')


def _section_recommendations(page_metrics, traffic, coverage_by_page, cwv=None, tech_stack=None, greenit=None):
    prio1, prio2, prio3 = [], [], []
    cwv = cwv or {}
    deduped = _dedup_page_metrics(page_metrics)

    # CWV — groupé par métrique (LCP, INP, CLS), une recommandation par problème
    from urllib.parse import urlparse

    # Vérifier si du code mort JS > 60% est présent (pour enrichir la reco LCP)
    _has_heavy_js = any(
        coverage_summary(pd["entries"] if isinstance(pd, dict) else pd)["js"]["pct"] > 60
        for pd in coverage_by_page.values()
    ) if coverage_by_page else False

    lcp_bad, lcp_warn = [], []
    inp_bad, inp_warn = [], []
    cls_bad, cls_warn = [], []

    for m in deduped:
        # Recos = "pire des deux" par métrique : un problème desktop remonte aussi.
        c, worst_strat = _cwv_worst_per_metric(_cwv_for_page(m, cwv))
        if not c:
            continue
        num = m.get("page_num", "")
        url = m["title"]
        short = urlparse(url).path.rstrip("/") or "/"

        def _label(metric):
            # Annote la page avec l'appareil dont vient la valeur la plus défavorable
            mk = _cwv_device_marker(worst_strat[metric]) if worst_strat.get(metric) else ""
            mk = f'<span title="pire des deux : {worst_strat.get(metric)}">{mk}</span> ' if mk else ""
            return f'<a href="{url}" target="_blank" rel="noopener">{mk}P{num} {short}</a>'

        lcp  = c.get("lcp")
        inp  = c.get("inp")
        cls_ = c.get("cls")
        if isinstance(lcp, (int, float)):
            if lcp > 2.5:   lcp_bad.append((lcp, _label("lcp")))
            elif lcp > 1.8: lcp_warn.append((lcp, _label("lcp")))
        if isinstance(inp, (int, float)):
            if inp > 500:   inp_bad.append((inp, _label("inp")))
            elif inp > 200: inp_warn.append((inp, _label("inp")))
        if isinstance(cls_, (int, float)):
            if cls_ > 0.25: cls_bad.append((cls_, _label("cls")))
            elif cls_ > 0.1: cls_warn.append((cls_, _label("cls")))

    def _pages_str(items):
        return ", ".join(lbl for _, lbl in items)

    def _lcp_item(items, severity):
        vals = [v for v, _ in items]
        range_str = f"{min(vals):.1f} s" if len(vals) == 1 else f"entre {min(vals):.1f} s et {max(vals):.1f} s"
        n = len(items)
        js_note = " (code mort JS > 60 % identifié)" if _has_heavy_js else ""
        return (
            f"<strong>Réduire le LCP</strong> ({range_str} sur {n} page{'s' if n>1 else ''} — {severity})<br>"
            f'<span style="color:#555;font-size:0.9em">'
            f"Causes probables : image hero non préchargée, JS bloquant le rendu{js_note}, TTFB élevé.<br>"
            f"Actions : ajouter <code>&lt;link rel=\"preload\"&gt;</code> sur l'image hero &middot; "
            f"passer le JS non critique en <code>defer</code>/<code>async</code> &middot; "
            f"analyser le TTFB avec WebPageTest.<br>"
            f"Pages : {_pages_str(items)}"
            f"</span>"
        )

    def _inp_item(items, severity):
        vals = [v for v, _ in items]
        range_str = f"{int(min(vals))} ms" if len(vals) == 1 else f"entre {int(min(vals))} ms et {int(max(vals))} ms"
        n = len(items)
        signal = _cwv_reco_signal_html("inp", traffic, greenit, coverage_by_page)
        return (
            f"<strong>Réduire l'INP</strong> ({range_str} sur {n} page{'s' if n>1 else ''} — {severity})<br>"
            f'<span style="color:#555;font-size:0.9em">'
            f"Causes probables : long tasks JS, thread principal saturé lors des interactions.<br>"
            f"Actions : découper les tâches longues (&gt; 50 ms) &middot; "
            f"utiliser <code>scheduler.yield()</code> &middot; lazy-loader les composants non visibles.<br>"
            f"Pages : {_pages_str(items)}"
            f"</span>{signal}"
        )

    def _cls_item(items, severity):
        vals = [v for v, _ in items]
        range_str = f"{min(vals):.2f}" if len(vals) == 1 else f"entre {min(vals):.2f} et {max(vals):.2f}"
        n = len(items)
        signal = _cwv_reco_signal_html("cls", traffic, greenit, coverage_by_page)
        return (
            f"<strong>Corriger les décalages de mise en page (CLS)</strong> ({range_str} sur {n} page{'s' if n>1 else ''} — {severity})<br>"
            f'<span style="color:#555;font-size:0.9em">'
            f"Causes probables : images ou iframes sans dimensions explicites, polices web sans size-adjust.<br>"
            f"Actions : définir <code>width</code>/<code>height</code> sur les médias &middot; "
            f"utiliser <code>font-display: optional</code> ou <code>size-adjust</code>.<br>"
            f"Pages : {_pages_str(items)}"
            f"</span>{signal}"
        )

    if lcp_bad:
        prio1.append(_lcp_item(lcp_bad, "mauvais"))
    elif lcp_warn:
        prio2.append(_lcp_item(lcp_warn, "à améliorer"))

    if inp_bad:
        prio1.append(_inp_item(inp_bad, "mauvais"))
    elif inp_warn:
        prio2.append(_inp_item(inp_warn, "à améliorer"))

    if cls_bad:
        prio1.append(_cls_item(cls_bad, "mauvais"))
    elif cls_warn:
        prio2.append(_cls_item(cls_warn, "à améliorer"))

    # EcoIndex < 40 → priorité 1
    for m in page_metrics:
        if m["ecoindex"] < 40:
            prio1.append(f"<b>{m['title'][:40]}</b> : EcoIndex {m['ecoindex']}/100 (grade {m['grade']}) - optimisation urgente")
        elif m["ecoindex"] < 55:
            prio2.append(f"<b>{m['title'][:40]}</b> : EcoIndex {m['ecoindex']}/100 (grade {m['grade']}) - à améliorer")

    # DOM élevé
    for m in page_metrics:
        if m["dom"] > 1500:
            prio1.append(f"DOM {m['dom']} éléments sur <b>{m['title'][:30]}</b> - réduire les composants inactifs")
        elif m["dom"] > 800:
            prio2.append(f"DOM {m['dom']} éléments sur <b>{m['title'][:30]}</b> - évaluer les composants superflus")

    # Doublons
    if traffic["duplicates"]:
        prio2.append(
            f"{len(traffic['duplicates'])} ressources chargées en double - configurer le cache navigateur"
            f' <a href="#trafic-doublons" style="color:inherit;text-decoration:underline;font-size:16px">&#8594; voir le d&eacute;tail</a>'
        )

    # Code mort > 70%
    for page_name, page_data in coverage_by_page.items():
        entries = page_data["entries"] if isinstance(page_data, dict) else page_data
        summ = coverage_summary(entries)
        if summ["js"]["pct"] > 70:
            prio1.append(f"<b>{page_name}</b> : {summ['js']['pct']}% du JS non utilisé ({summ['js']['unused_kb']} Ko) - lazy loading + tree shaking")
        elif summ["js"]["pct"] > 50:
            prio2.append(f"<b>{page_name}</b> : {summ['js']['pct']}% du JS non utilisé - évaluer le découpage par route")
        if summ["css"]["pct"] > 80:
            prio2.append(f"<b>{page_name}</b> : {summ['css']['pct']}% du CSS non utilisé ({summ['css']['unused_kb']} Ko) - PurgeCSS recommandé")

    # PRIORITÉ 3 — amélioration continue, croisée avec la stack détectée (documentaire).
    # Les règles lisent les CATÉGORIES détectées, jamais des noms de sites : génériques.
    prio3 = ["Activer la compression Brotli sur tous les serveurs"]

    _technos = (tech_stack or {}).get("technologies", []) if tech_stack else []
    _cats = {t.get("category") for t in _technos}
    _by_cat = defaultdict(list)
    for _t in _technos:
        _name = _t.get("name")
        if _name:
            _by_cat[_t.get("category")].append(_name)

    # CDN : valoriser s'il est présent, sinon recommander de le mettre en place.
    if "CDN" in _cats:
        _cdn_names = ", ".join(dict.fromkeys(_by_cat.get("CDN", [])))
        prio3.append(
            f"<b>CDN déjà en place</b> ({_cdn_names}) : bon point, les assets statiques "
            "sont diffusés au plus près des visiteurs. À maintenir."
        )
    else:
        prio3.append("Mettre en place un CDN pour les assets statiques")

    # Scripts tiers : les nommer s'ils sont détectés, sinon garder la piste générique.
    _third_labels = []
    for _cat in ("Analytics", "Balise / Tag manager", "Bibliothèque JS"):
        for _name in _by_cat.get(_cat, []):
            _third_labels.append(f"{_name} ({_cat.lower()})")
    if _third_labels:
        prio3.append(
            "Scripts tiers détectés : <b>" + ", ".join(_third_labels) + "</b>. "
            "Évaluer leur poids réel et leur nécessité ; envisager des alternatives légères "
            "ou un chargement différé."
        )
    else:
        prio3.append(
            "Évaluer le remplacement des librairies tierces lourdes (analytics, chatbot) "
            "par des alternatives légères"
        )

    # Multiplication des domaines tiers : chaque hôte ajoute DNS + TLS.
    _tp_hosts = (tech_stack or {}).get("third_party_hosts", []) if tech_stack else []
    if len(_tp_hosts) >= 8:
        prio3.append(
            f"<b>{len(_tp_hosts)} domaines tiers</b> sollicités au chargement : chaque domaine "
            "ajoute une résolution DNS et une négociation TLS. Regrouper ou auto-héberger "
            "les ressources critiques réduit la latence et les connexions."
        )

    def _items(lst):
        return "".join(f"<li>{i}</li>" for i in lst) if lst else "<li>Aucun constat critique.</li>"

    def _see_also(items_list, *links):
        if not items_list:
            return ""
        parts = " &nbsp;·&nbsp; ".join(
            f'<a href="#{sid}" style="color:inherit;text-decoration:underline;font-size:16px">{label}</a>'
            for sid, label in links
        )
        return f'<div style="margin-top:8px;opacity:.8">&#8594; Voir : {parts}</div>'

    return f"""<section id="recommandations">
  <h2>Recommandations</h2>
  <div class="prio prio-1">
    <b>PRIORITÉ 1 - Impact fort</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio1)}</ul>
    {_see_also(prio1, ("dashboard", "A.1 Tableau de bord EcoIndex"), ("cwv-analyse", "Analyse CWV"), ("coverage", "A.3 Code mort (Coverage)"))}
  </div>
  <div class="prio prio-2">
    <b>PRIORITÉ 2 - Impact moyen</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio2)}</ul>
    {_see_also(prio2, ("trafic", "A.2 Trafic réseau"), ("dashboard", "A.1 Tableau de bord EcoIndex"))}
  </div>
  <div class="prio prio-3">
    <b>PRIORITÉ 3 - Amélioration continue</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio3)}</ul>
    {_see_also(prio3, ("trafic", "A.2 Trafic réseau"), ("greenit", "2. Bonnes pratiques GreenIT"))}
  </div>
</section>"""


# ── Entrée principale ─────────────────────────────────────────────────────────

def generate(audit_dir, output_path=None):
    audit_dir = Path(audit_dir)

    # Localisation des fichiers — chercher dans audit_dir, sinon dans le dossier parent (SOURCE_DIR)
    har_files = list(audit_dir.glob("*.har"))
    source_dir = audit_dir
    if not har_files and audit_dir.parent != audit_dir:
        har_files = list(audit_dir.parent.glob("*.har"))
        if har_files:
            source_dir = audit_dir.parent
    if not har_files:
        raise FileNotFoundError(f"Aucun fichier .har dans {audit_dir} ni dans {audit_dir.parent}")
    har_path = har_files[0]

    cov_files = sorted(source_dir.glob("Coverage-*.json")) or sorted(source_dir.glob("*coverage*.json"))
    cwv_path  = audit_dir / "cwv.json"
    if not cwv_path.exists():
        cwv_path = source_dir / "cwv.json"

    greenit_path = audit_dir / "greenit.json"

    print(f"HAR      : {har_path.name}")
    print(f"Coverage : {len(cov_files)} fichier(s)")
    print(f"CWV      : {'oui' if cwv_path.exists() else 'non (timings HAR utilisés)'}")
    print(f"GreenIT  : {'fichier JSON' if greenit_path.exists() else 'calculé depuis HAR'}")

    har_data     = parse_har(har_path)
    page_metrics = extract_page_metrics(har_data)
    traffic      = har_traffic_analysis(har_data)
    cwv          = load_cwv(cwv_path) if cwv_path.exists() else {}
    greenit      = load_greenit(audit_dir) or compute_greenit_from_har(har_data)
    efootprint_results = load_efootprint_results(audit_dir)
    tech_stack = load_tech_stack(audit_dir)

    coverage_by_page = {}
    _asset_exts = re.compile(r'\.(js|css|webp|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|otf|eot|json|map)(\?.*)?$', re.I)
    _generic_scripts = {"header", "footer", "orejime", "swetrix", "gtm", "analytics",
                        "style", "main", "bundle", "chunk", "home", "index"}

    for cf in cov_files:
        with open(cf, encoding="utf-8") as _f:
            _raw = json.load(_f)
        raw_entries = _raw if isinstance(_raw, list) else _raw.get("entries", [])
        entries = parse_coverage_file(cf)

        # 1. URL de page : chercher une URL sans extension d'asset dans tous les domaines,
        #    en privilégiant les URLs qui ne sont pas des fonts/cdn tiers.
        from urllib.parse import urlparse as _up0
        from collections import Counter as _Counter

        # Domaine principal = le plus représenté parmi les URLs avec assets
        _domain_counts = _Counter()
        for item in raw_entries:
            u = item.get("url", "")
            if u.startswith("http"):
                _domain_counts[_up0(u).netloc] += 1
        _main_domain = _domain_counts.most_common(1)[0][0] if _domain_counts else ""

        page_url = ""
        first_party = None
        for item in raw_entries:
            u = item.get("url", "")
            if not u.startswith("http"):
                continue
            _netloc = _up0(u).netloc
            if _netloc != _main_domain:
                continue
            if not _asset_exts.search(u.split("?")[0]):
                page_url = u
                break
            if first_party is None and u.endswith(".js"):
                fname = u.split("/")[-1].split("?")[0].replace(".js", "").lower()
                if fname not in _generic_scripts:
                    first_party = u

        # 2. Fallback : script JS spécifique à une page
        if not page_url and first_party:
            from urllib.parse import urlparse as _up
            _p = _up(first_party)
            _fname = _p.path.split("/")[-1].split("?")[0].replace(".js", "")
            page_url = f"{_p.scheme}://{_p.netloc}/{_fname}"

        ts_raw = cf.stem.replace("Coverage-", "")
        # Convertir "20260710T152838" → "15:28" (heure de capture)
        import re as _re
        _m = _re.match(r'\d{8}T(\d{2})(\d{2})', ts_raw)
        ts_human = f"{_m.group(1)}h{_m.group(2)}" if _m else ts_raw[:10]

        if page_url:
            from urllib.parse import urlparse as _up2
            path = _up2(page_url).path.rstrip("/") or "/"
            label = path
        else:
            label = f"Page — {ts_human}"
        # Éviter les collisions si deux captures de la même page
        base_label = label
        n = 2
        while label in coverage_by_page:
            label = f"{base_label} ({ts_human})"
            if label in coverage_by_page:
                label = f"{base_label} ({ts_human}-{n})"
                n += 1
            else:
                break
        coverage_by_page[label] = {"entries": entries, "url": page_url}

    # Construction HTML
    today   = date.today().strftime("%d/%m/%Y")
    domains = ", ".join(list(traffic["domains"].keys())[:4])
    title   = f"Audit de parcours web - {today}"
    deduped_metrics = _dedup_page_metrics(page_metrics)
    nb_pages = len(deduped_metrics)

    # La section techno n'est rendue que si des technologies ont été détectées
    has_tech = bool(tech_stack and tech_stack.get("technologies"))

    # Sections présentes (pour le sommaire)
    annexe_sections = [
        ("dashboard", "Tableau de bord EcoIndex"),
        ("trafic",    "Trafic réseau"),
        ("coverage",  "Code mort (Coverage)"),
    ]
    if cwv:
        annexe_sections.append(("cwv", "Core Web Vitals"))
    if has_tech:
        annexe_sections.append(("stack-technique", "Stack technique"))
    annexe_sections.append(("methodologie", "Méthodologie & hypothèses"))

    has_medias = bool((greenit or {}).get("media", {}).get("video", {}).get("count") or
                       (greenit or {}).get("media", {}).get("pdf", {}).get("count"))

    letters = "abcdefgh"
    n = 3  # 1=Recommandations, 2=GreenIT, puis suit
    medias_nav = ""
    if has_medias:
        medias_nav = f'<li><a href="#medias">{n}. Médias et documents à surveiller</a></li>'
        n += 1
    cwv_nav = ""
    if cwv:
        cwv_nav = f'<li><a href="#cwv-analyse">{n}. Analyse Core Web Vitals</a></li>'
        n += 1
    efootprint_nav = ""
    if efootprint_results:
        efootprint_nav = f'<li><a href="#efootprint">{n}. Impact environnemental (CO2e)</a></li>'
        n += 1
    annexes_num = n
    annexe_inline = " &nbsp;·&nbsp; ".join(
        f'<a href="#{sid}">{annexes_num}.{letters[i]} {slabel}</a>'
        for i, (sid, slabel) in enumerate(annexe_sections)
    )
    nav_items = (
        f'<li><a href="#recommandations">1. Recommandations</a></li>'
        f'<li><a href="#greenit">2. Bonnes pratiques GreenIT</a></li>'
        f'{medias_nav}'
        f'{cwv_nav}'
        f'{efootprint_nav}'
        f'<li style="display:flex;flex-direction:column;gap:2px">'
        f'<span style="display:flex;flex-direction:row;align-items:baseline;gap:12px">'
        f'<a href="#annexes">{annexes_num}. Annexes</a>'
        f'<a href="#couts">&#9658; Couts de generation</a>'
        f'</span>'
        f'<span style="font-size:15px;opacity:.75;padding-left:4px">{annexe_inline}</span>'
        f'</li>'
    )

    html = _html_head(title)
    html += f"""<header>
  <h1>Audit EROOM Version {AGENT_VERSION}</h1>
  <div style="font-size:18px;margin-top:6px;opacity:.9">{domains}</div>
  <div class="meta">
    Date : {today} &nbsp;|&nbsp;
    {nb_pages} page(s) analysée(s) &nbsp;|&nbsp;
    HAR : {har_path.name} &nbsp;|&nbsp;
    Coverage : {len(cov_files)} fichier(s)
  </div>
</header>
<nav role="navigation" aria-label="Sommaire du rapport">
  <h2>Sommaire</h2>
  <ul style="list-style:none;padding:0;margin:0">{nav_items}</ul>
</nav>
<main id="contenu">
"""
    html += _section_recommendations(page_metrics, traffic, coverage_by_page, cwv, tech_stack, greenit)
    html += _section_greenit(greenit)
    if has_medias:
        html += _section_medias(greenit)
    if cwv:
        html += _section_cwv_analyse(page_metrics, cwv, traffic, greenit, coverage_by_page)
    if efootprint_results:
        html += _section_efootprint(efootprint_results)
    def _prefix_h2(html_str, prefix):
        return html_str.replace('<h2>', f'<h2>{prefix} — ', 1)

    html += '<section id="annexes" style="background:#f4f6fa;border:2px solid var(--octo-blue);border-radius:6px;padding:24px 24px 8px;margin-bottom:40px">\n'
    html += '<h2 style="border-left:none;padding-left:0;font-size:17px;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:20px">Annexes</h2>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_dashboard(page_metrics, cwv), "A.1")}</div>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_traffic(traffic), "A.2")}</div>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_coverage(coverage_by_page), "A.3")}</div>\n'
    if cwv:
        html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_cwv(page_metrics, cwv), "A.4")}</div>\n'
    if has_tech:
        # Numéro dérivé de la position dans annexe_sections (robuste à la présence de cwv)
        tech_num = f"A.{[sid for sid, _ in annexe_sections].index('stack-technique') + 1}"
        html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_tech(tech_stack), tech_num)}</div>\n'
    methodo_num = f"A.{len(annexe_sections)}"  # methodologie est le dernier élément d'annexe_sections
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_methodologie(efootprint_results, cwv), methodo_num)}</div>\n'
    html += '</section>\n'

    html += "</main>\n"
    html += f"""<div id="couts" class="cost-info" style="background:#f0f4f8;border-top:1px solid #ccc;padding:1.5rem 0;">
  <div style="max-width:700px;margin:0 auto 0 40px">
    <details style="padding:0.75rem 1rem;background:white;border:1px solid #ccc;border-radius:4px;">
      <summary style="cursor:pointer;font-weight:600;">Coûts de génération (<span data-cost-field="cout">—</span> [*])</summary>
      <p style="margin:0.75rem 0 0.5rem;font-size:0.9rem;font-style:italic;opacity:0.8;">[*] Estimation calculée par fenêtre temporelle sur le fichier JSONL de session. Durée et tokens peuvent inclure des échanges hors analyse. Coût aux tarifs API Anthropic publics ; sous AWS Bedrock, consulter AWS Cost Explorer.</p>
      <p style="margin:0.3rem 0;"><strong>Modèle :</strong> <span data-cost-field="modele">—</span></p>
      <p style="margin:0.3rem 0;"><strong>Effort :</strong> <span data-cost-field="effort">—</span></p>
      <p style="margin:0.3rem 0;"><strong>Durée :</strong> <span data-cost-field="duree">—</span></p>
      <p style="margin:0.3rem 0;"><strong>Tokens :</strong> <span data-cost-field="tokens">—</span></p>
      <p style="margin:0.3rem 0;"><strong>CO2e estimé :</strong> <span data-cost-field="co2e">—</span></p>
      <p style="margin:0.3rem 0;font-size:0.9rem;color:#666;"><span data-cost-field="ratio-co2e"></span></p>
      <p style="margin:0.75rem 0 0 0;font-size:0.8rem;font-style:italic;opacity:0.75;">CO2e estimé à partir des tokens de calcul (input + output + cache creation, hors lecture de cache) : 0,3-1,0 Wh/1000 tokens (Epoch AI 2025, Google Cloud août 2025), PUE 1,1-1,3, intensité carbone électrique 450-480 gCO2/kWh (moyenne mondiale, IEA). Fourchette large car aucune donnée publique précise sur l'infrastructure de calcul réelle de la session ; ordre de grandeur, pas une mesure.</p>
      <p style="margin:0.3rem 0;font-size:0.85rem;color:#888;"><strong>Fichiers sources :</strong> {har_path.name}, {len(cov_files)} fichier(s) Coverage</p>
    </details>
  </div>
</div>
<footer>Rapport généré le {today} - Agent EROOM v{AGENT_VERSION}</footer>
"""
    html += "</body>\n</html>\n"

    if output_path is None:
        output_path = audit_dir / f"rapport-parcours-{date.today().isoformat()}.html"
    output_path = Path(output_path)
    output_path.write_text(html, encoding="utf-8")
    print(f"\nRapport HTML généré : {output_path}")

    import subprocess
    patch_script = Path.home() / ".claude/scripts/patch-audit-cost.sh"
    if patch_script.exists():
        subprocess.run(["bash", str(patch_script), str(output_path)], check=False)
    else:
        print(f"[coûts] patch-audit-cost.sh introuvable ({patch_script}) — section coûts non patchée")

    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_report_html.py <dossier-audit> [--output fichier.html]")
        sys.exit(1)

    audit_dir = sys.argv[1]
    out = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            out = sys.argv[idx + 1]

    generate(audit_dir, out)
