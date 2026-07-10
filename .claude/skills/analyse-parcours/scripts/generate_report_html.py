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
    "other":      "#95a5a6",
}


# ── Imports EcoIndex ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from ecoindex_utils import extract_page_metrics, load_cwv


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
    if "image" in mime or re.search(r'\.(png|jpg|jpeg|gif|svg|webp|ico)$', url):
        return "image"
    if "font" in mime or re.search(r'\.(woff2?|ttf|otf|eot)$', url):
        return "font"
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

    _TRACKER_DOMAINS = {
        "swetrix.org", "cdn.jsdelivr.net", "google-analytics.com", "googletagmanager.com",
        "analytics.google.com", "hotjar.com", "segment.io", "mixpanel.com",
        "amplitude.com", "heap.io", "clarity.ms",
    }
    _TRACKER_PATHS = {"/log/", "/log/hb", "/hb", "/ping", "/beacon", "/collect", "/track", "/event"}
    _FONT_DOMAINS  = {"fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net", "use.fontawesome.com"}

    def _dup_category(url, host, hdrs_resp):
        from urllib.parse import urlparse as _up
        path = _up(url).path.lower()
        # Tracker / analytics
        if host in _TRACKER_DOMAINS or any(t in host for t in ("analytics", "swetrix", "gtm", "hotjar", "segment", "mixpanel")):
            return "tracker", "Requête analytics/tracker — comportement normal, envoi répété intentionnel"
        if any(path.startswith(p) or path == p for p in _TRACKER_PATHS):
            return "tracker", "Endpoint de tracking (ping/beacon) — envoi répété intentionnel"
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

    return {
        "total_req": len(entries),
        "total_ko": round(sum(r["size"] for r in resources) / 1024, 1),
        "domains": dict(sorted(domains.items(), key=lambda x: -x[1])),
        "http_codes": dict(http_codes),
        "top10": top10,
        "duplicates": duplicates,
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
  body {{ font-family: Arial, sans-serif; font-size: 14px; color: #222; background: #f9f9f9; }}
  header {{ background: var(--octo-dark); color: white; padding: 32px 40px 24px; }}
  header h1 {{ font-size: 24px; font-weight: bold; margin-bottom: 6px; }}
  header .meta {{ font-size: 12px; opacity: .75; margin-top: 8px; }}
  nav[role="navigation"] {{ background: var(--octo-pale); border-bottom: 2px solid var(--octo-blue);
    padding: 14px 40px; }}
  nav[role="navigation"] h2 {{ font-size: 13px; font-weight: bold; color: var(--octo-dark);
    margin-bottom: 8px; border: none; padding: 0; }}
  nav[role="navigation"] ul {{ display: flex; flex-wrap: wrap; align-items: flex-start; gap: 6px 20px; padding: 0;
    margin: 0; font-size: 13px; list-style: none; }}
  nav[role="navigation"] a {{ color: var(--octo-dark); text-decoration: none; }}
  nav[role="navigation"] a:hover {{ text-decoration: underline; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px; }}
  section {{ margin-bottom: 40px; }}
  h2 {{ font-size: 18px; color: var(--octo-dark); border-left: 4px solid var(--octo-blue);
        padding-left: 12px; margin-bottom: 16px; margin-top: 4px; }}
  h3 {{ font-size: 14px; color: var(--octo-dark); margin: 16px 0 8px; font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 12px; }}
  th {{ background: var(--octo-dark); color: white; padding: 7px 10px; text-align: left; font-size: 12px; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #ddd; }}
  tr:nth-child(even) td {{ background: var(--octo-pale); }}
  tr.alert td {{ background: #ffe0e0; }}
  tr.bold td {{ background: #dde8f0; font-weight: bold; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-weight: bold; font-size: 13px; color: white; min-width: 32px; text-align: center; }}
  .bar-wrap {{ display: flex; height: 16px; border-radius: 3px; overflow: hidden; width: 120px; }}
  .bar-used   {{ background: #50b450; }}
  .bar-unused {{ background: #dc5050; }}
  .kpi-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
  .kpi {{ background: var(--octo-pale); border: 1px solid var(--octo-blue); border-radius: 6px;
          padding: 14px 20px; min-width: 140px; }}
  .kpi .val {{ font-size: 22px; font-weight: bold; color: var(--octo-dark); }}
  .kpi .lbl {{ font-size: 11px; color: #555; margin-top: 2px; }}
  .prio {{ margin: 6px 0; padding: 10px 14px; border-radius: 4px; font-size: 13px; }}
  .prio-1 {{ background: #ffe0e0; border-left: 4px solid #dc3545; }}
  .prio-2 {{ background: #fff3cd; border-left: 4px solid #fd7e14; }}
  .prio-3 {{ background: #d4edda; border-left: 4px solid #28a745; }}
  .domain-tag {{ display: inline-block; background: var(--octo-grey); border-radius: 3px;
                 padding: 1px 6px; font-size: 11px; margin: 2px; }}
  footer {{ text-align: center; padding: 20px; font-size: 11px; color: #888;
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
    """Déduplique par URL canonique : garde la ligne avec DOM non-zéro, sinon la plus lourde."""
    seen = {}
    for m in page_metrics:
        url = m["title"].split("?")[0].rstrip("/") or m["title"]
        prev = seen.get(url)
        if prev is None:
            seen[url] = m
        else:
            # Préférer : DOM non-zéro > plus de requêtes
            if m["dom"] > 0 and prev["dom"] == 0:
                seen[url] = m
            elif m["dom"] > 0 and prev["dom"] > 0 and m["req"] > prev["req"]:
                seen[url] = m
            elif m["dom"] == 0 and prev["dom"] == 0 and m["req"] > prev["req"]:
                seen[url] = m
    return list(seen.values())


def _section_dashboard(page_metrics, cwv):
    deduped = _dedup_page_metrics(page_metrics)
    rows = ""
    for m in deduped:
        badge = _badge(m["grade"], m["grade_color"])
        url = m["title"]
        # Affichage : chemin seul comme label, URL complète en title + href
        from urllib.parse import urlparse
        parsed = urlparse(url)
        short = parsed.path.rstrip("/") or "/"
        page_cell = f'<a href="{url}" target="_blank" rel="noopener" title="{url}">{short}</a>'
        cwv_data = cwv.get(m["page_id"], {})

        def _cwv_cell(val, unit, thresholds):
            # thresholds = (good_max, needs_improvement_max)
            # couleurs officielles Google CWV
            if not isinstance(val, (int, float)):
                return f'<td style="text-align:right;color:#aaa">—</td>'
            if val <= thresholds[0]:
                color = "#0cce6b"
            elif val <= thresholds[1]:
                color = "#ffa400"
            else:
                color = "#ff4e42"
            return f'<td style="text-align:right;color:{color};font-weight:bold">{val} {unit}</td>'

        if cwv_data:
            lcp_val = cwv_data.get("lcp")
            inp_val = cwv_data.get("inp")
            cls_num = cwv_data.get("cls")
            lcp_cell = _cwv_cell(lcp_val, "s", (1.8, 2.5))
            inp_cell = _cwv_cell(inp_val, "ms", (200, 500))
            cls_cell = _cwv_cell(cls_num, "", (0.1, 0.25))
        else:
            lcp_cell = f'<td style="text-align:right;color:#aaa">{m["on_load_ms"]} ms *</td>'
            inp_cell = '<td style="text-align:right;color:#aaa">—</td>'
            cls_cell = '<td style="text-align:right;color:#aaa">—</td>'

        rows += f"""<tr>
      <td>{page_cell}</td>
      <td style="text-align:center">{badge} {m['ecoindex']}/100</td>
      <td style="text-align:right">{m['req']}</td>
      <td style="text-align:right">{m['size_ko']:.0f} Ko</td>
      <td style="text-align:right">{m['dom']}</td>
      {lcp_cell}{inp_cell}{cls_cell}
    </tr>"""

    cwv_legend = """<div style="font-size:11px;margin-top:8px;display:flex;gap:16px;align-items:center">
    <span style="font-weight:bold;color:#555">Légende CWV :</span>
    <span style="color:#0cce6b">● Bon</span>
    <span style="color:#ffa400">● A améliorer</span>
    <span style="color:#ff4e42">● Mauvais</span>
    <span style="color:#aaa;font-style:italic">— Données terrain non disponibles (fournir cwv.json)</span>
  </div>"""
    cwv_note = "" if cwv else '<p style="font-size:11px;color:#888;margin-top:6px">* LCP = onLoad HAR (proxy). INP et CLS nécessitent des données terrain (API PageSpeed ou cwv.json).</p>'

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
            f'<td style="color:#555;font-size:12px">{desc}</td>'
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
      <td style="color:#555;font-size:11px">{r['host']}</td>
    </tr>"""

    # Catégories de doublons : couleur + libellé court
    _CAT_META = {
        "tracker":        ("#6f42c1", "Tracker / analytics"),
        "font":           ("#d9534f", "Police externe"),
        "static_no_cache":("#dc3545", "Statique sans cache"),
        "static_cached":  ("#28a745", "Statique avec cache"),
        "other":          ("#888",    "Autre"),
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
            f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px;font-size:12px">'
            f'<span style="background:#dc3545;color:white;padding:2px 8px;border-radius:4px"><b>{nb_problematic}</b> à corriger (sans cache)</span>'
            f'<span style="background:#6f42c1;color:white;padding:2px 8px;border-radius:4px"><b>{nb_tracker}</b> trackers (normal)</span>'
            f'<span style="background:#d9534f;color:white;padding:2px 8px;border-radius:4px"><b>{nb_font}</b> polices externes</span>'
            f'</div>'
        )

        # Tableau par groupe
        dup_tables = ""
        for cat, items in groups.items():
            if not items:
                continue
            cat_color, cat_label = _CAT_META[cat]
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
                f'<summary style="cursor:pointer;font-weight:bold;font-size:13px;padding:6px 0">'
                f'<span style="background:{cat_color};color:white;padding:1px 7px;border-radius:4px;font-size:12px;margin-right:6px">{cat_label}</span>'
                f'{len(items)} URL(s) — <span style="font-weight:normal;color:#555;font-size:12px">{cause}</span>'
                f'</summary>'
                f'<table style="margin-top:6px">'
                f'<thead><tr><th>Fichier</th><th style="width:50px">Nb</th></tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                f'</table>'
                f'</details>'
            )

        dup_section = f'<h3>Requêtes dupliquées ({len(dups)} URL(s))</h3>{dup_kpis}{dup_tables}'

    return f"""<section id="trafic">
  <h2>Trafic réseau</h2>
  <div class="kpi-grid">
    <div class="kpi"><div class="val">{traffic['total_req']}</div><div class="lbl">Requêtes totales</div></div>
    <div class="kpi"><div class="val">{traffic['total_ko']:.0f} Ko</div><div class="lbl">Volume transféré</div></div>
    <div class="kpi"><div class="val">{len(traffic['domains'])}</div><div class="lbl">Domaines</div></div>
  </div>
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
    <div>JS {_bar(js_used)} <span style="font-size:12px">{summ['js']['unused_kb']} Ko non utilisés ({summ['js']['pct']}%)</span></div>
    <div>CSS {_bar(css_used)} <span style="font-size:12px">{summ['css']['unused_kb']} Ko non utilisés ({summ['css']['pct']}%)</span></div>
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
        return f'<td style="text-align:right;color:#aaa">—</td>'
    if val <= thresholds[0]:
        color = "#0cce6b"
    elif val <= thresholds[1]:
        color = "#ffa400"
    else:
        color = "#ff4e42"
    return f'<td style="text-align:right;color:{color};font-weight:bold">{val} {unit}</td>'


def _section_cwv(page_metrics, cwv):
    if not cwv:
        return ""

    rows = ""
    for m in page_metrics:
        c = cwv.get(m["page_id"], {})
        if not c:
            continue
        from urllib.parse import urlparse
        url = m["title"]
        parsed = urlparse(url)
        short = parsed.path.rstrip("/") or "/"
        page_cell = f'<a href="{url}" target="_blank" rel="noopener" title="{url}">{short}</a>'
        rows += f"""<tr>
      <td>{page_cell}</td>
      {_cwv_colored(c.get("lcp"), "s", (1.8, 2.5))}
      {_cwv_colored(c.get("inp"), "ms", (200, 500))}
      {_cwv_colored(c.get("cls"), "", (0.1, 0.25))}
    </tr>"""

    legend = """<div style="font-size:11px;margin-top:8px;display:flex;gap:16px;align-items:center">
    <span style="font-weight:bold;color:#555">Légende :</span>
    <span style="color:#0cce6b">● Bon</span>
    <span style="color:#ffa400">● A améliorer</span>
    <span style="color:#ff4e42">● Mauvais</span>
  </div>
  <table style="margin-top:10px;font-size:11px;border:none;width:auto">
    <thead><tr style="background:none">
      <th style="border:none;text-align:left">Métrique</th>
      <th style="border:none;color:#0cce6b">Bon</th>
      <th style="border:none;color:#ffa400">A améliorer</th>
      <th style="border:none;color:#ff4e42">Mauvais</th>
      <th style="border:none;text-align:left;color:#555">Description</th>
    </tr></thead>
    <tbody>
      <tr><td style="border:none"><b>LCP</b></td><td style="border:none">&lt; 1,8 s</td><td style="border:none">1,8 - 2,5 s</td><td style="border:none">&gt; 2,5 s</td><td style="border:none">Largest Contentful Paint - temps d'affichage du plus grand élément visible</td></tr>
      <tr><td style="border:none"><b>INP</b></td><td style="border:none">&lt; 200 ms</td><td style="border:none">200 - 500 ms</td><td style="border:none">&gt; 500 ms</td><td style="border:none">Interaction to Next Paint - réactivité aux interactions utilisateur</td></tr>
      <tr><td style="border:none"><b>CLS</b></td><td style="border:none">&lt; 0,1</td><td style="border:none">0,1 - 0,25</td><td style="border:none">&gt; 0,25</td><td style="border:none">Cumulative Layout Shift - stabilité visuelle (décalages inattendus)</td></tr>
    </tbody>
  </table>"""

    return f"""<section id="cwv">
  <h2>Core Web Vitals</h2>
  <p style="font-size:12px;color:#666;margin-bottom:10px">
    Données terrain (source : cwv.json). INP et CLS ne peuvent pas être estimés depuis un HAR : ils nécessitent de vraies interactions utilisateur et un rendu navigateur complet.
  </p>
  <table>
    <thead><tr><th>Page</th><th>LCP</th><th>INP</th><th>CLS</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {legend}
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
        "description": "HTTP/2 permet le multiplexage des requêtes sur une seule connexion TCP, réduisant la latence et le nombre de connexions.",
    },
}

COMPLIANCE_COLORS = {"A": "#28a745", "B": "#fd7e14", "C": "#dc3545", "NA": "#aaa"}
COMPLIANCE_ORDER  = {"C": 0, "B": 1, "A": 2, "NA": 3}


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
    nb_no_compress = 0;    urls_no_compress = []
    nb_no_etag = 0;        urls_no_etag = []
    nb_cookie_static = 0;  urls_cookie_static = []
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
            if not has_cc:
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
            else:
                nb_bitmap += 1
                if size > 100 * 1024 and ext not in ("webp", "avif"):
                    nb_bitmap_heavy += 1
                    if len(urls_bitmap_heavy) < 20:
                        urls_bitmap_heavy.append((url, round(size/1024, 1)))

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
    cmt = "Aucun cookie sur ressource statique" if nb_cookie_static == 0 else f"{nb_cookie_static} ressource(s) statique(s) avec cookie"
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
            "comment": f"{nb_bitmap} image(s), aucune > 100 Ko non-webp",
            "evidence": [],
            "evidence_images": [{"url": u, "size_kb": round(s/1024, 1)} for u, s in top_bitmaps if u],
        }
    else:
        agg["OptimizeBitmapImages"] = {
            "complianceLevel": "C",
            "comment": f"{nb_bitmap_heavy} image(s) > 100 Ko, format non-webp/avif",
            "evidence": [f"{u} ({s} Ko)" for u, s in urls_bitmap_heavy],
            "evidence_images": [{"url": u, "size_kb": s} for u, s in urls_bitmap_heavy],
        }

    # OptimizeSvg
    if nb_svg == 0:
        agg["OptimizeSvg"] = {"complianceLevel": "NA", "comment": "Pas de SVG", "evidence": [], "evidence_images": []}
    elif nb_svg_heavy == 0:
        agg["OptimizeSvg"] = {"complianceLevel": "A", "comment": f"{nb_svg} SVG, aucun > 10 Ko", "evidence": [], "evidence_images": []}
    else:
        agg["OptimizeSvg"] = {
            "complianceLevel": "C",
            "comment": f"{nb_svg_heavy} SVG lourd(s) (> 10 Ko)",
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

    return {"pages": [], "aggregated": agg, "_source": "har"}


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
        color = COMPLIANCE_COLORS.get(level, "#aaa")
        badge = f'<span class="badge" style="background:{color};min-width:28px">{level}</span>'
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
                        f'<div style="font-size:10px;color:#555;max-width:60px;word-break:break-all">'
                        f'{fname}<br><b>{size_kb} Ko</b></div>'
                        f'</div>'
                    )
                    thumbs.append(thumb_inline)
                else:
                    # Fallback : lien texte si vipsthumbnail absent
                    thumbs.append(
                        f'<div style="display:inline-block;margin:4px;font-size:11px;vertical-align:top">'
                        f'<a href="{url}" target="_blank" rel="noopener">{fname}</a>'
                        f'<br><b>{size_kb} Ko</b></div>'
                    )
            if thumbs:
                thumbs_html = (
                    f'<div style="margin-top:6px;padding:6px;background:#f8f8f8;border-radius:4px">'
                    f'<div style="font-size:11px;color:#555;margin-bottom:4px">Top {len(thumbs)} image(s) les plus lourdes :</div>'
                    f'{"".join(thumbs)}'
                    f'</div>'
                )

        if thumbs_html:
            # Les thumbnails remplacent la liste texte pour les règles images
            nb = len(evidence_images)
            details_html = (
                f'<details style="margin-top:4px">'
                f'<summary style="cursor:pointer;font-size:11px;color:#555">'
                f'Aperçu ({nb} image(s))</summary>'
                f'{thumbs_html}'
                f'</details>'
            )
        elif evidence:
            # Autres règles : liste texte simple
            ev_items = "".join(
                f'<li style="font-size:11px;word-break:break-all;margin:2px 0">'
                f'<a href="{item}" target="_blank" rel="noopener">{item}</a></li>'
                if str(item).startswith("http")
                else f'<li style="font-size:11px;margin:2px 0">{item}</li>'
                for item in evidence
            )
            details_html = (
                f'<details style="margin-top:4px">'
                f'<summary style="cursor:pointer;font-size:11px;color:#555">'
                f'Détail ({len(evidence)} élément(s))</summary>'
                f'<ul style="margin:4px 0 0 12px;padding:0">{ev_items}</ul>'
                f'</details>'
            )
        else:
            details_html = ""

        detail_html = f'<span style="font-size:11px;color:#666">{detail}</span>' if detail else ""
        rows += f"""<tr>
      <td style="text-align:center;width:48px;vertical-align:top;padding-top:10px">{badge}</td>
      <td><b>{rule['name']}</b><br>{detail_html}{details_html}</td>
      <td style="font-size:12px;color:#555;vertical-align:top">{rule['description']}</td>
    </tr>"""

    nb_c  = sum(1 for k in agg if agg[k]["complianceLevel"] == "C")
    nb_b  = sum(1 for k in agg if agg[k]["complianceLevel"] == "B")
    nb_a  = sum(1 for k in agg if agg[k]["complianceLevel"] == "A")
    nb_na = sum(1 for k in agg if agg[k]["complianceLevel"] == "NA")

    summary = (
        f'<span style="background:#dc3545;color:white;padding:2px 8px;border-radius:4px;margin-right:6px"><b>{nb_c}</b> C</span>'
        f'<span style="background:#fd7e14;color:white;padding:2px 8px;border-radius:4px;margin-right:6px"><b>{nb_b}</b> B</span>'
        f'<span style="background:#28a745;color:white;padding:2px 8px;border-radius:4px;margin-right:6px"><b>{nb_a}</b> A</span>'
        f'<span style="background:#aaa;color:white;padding:2px 8px;border-radius:4px"><b>{nb_na}</b> N.A</span>'
    )

    legend = (
        '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px;font-size:12px">'
        '<span><span class="badge" style="background:#dc3545">C</span> &nbsp;<b>Non conforme</b> - action corrective requise</span>'
        '<span><span class="badge" style="background:#fd7e14">B</span> &nbsp;<b>Partiellement conforme</b> - amélioration possible</span>'
        '<span><span class="badge" style="background:#28a745">A</span> &nbsp;<b>Conforme</b> - bonne pratique respectée</span>'
        '<span><span class="badge" style="background:#aaa">N.A</span> &nbsp;<b>Non applicable</b> - critère sans objet pour ce site</span>'
        '</div>'
    )

    source_note = ' <span style="font-size:12px;font-weight:normal;color:#888">(calculé depuis HAR)</span>' if greenit.get("_source") == "har" else ""
    return f"""<section id="greenit">
  <h2>Bonnes pratiques GreenIT-Analysis{source_note}</h2>
  <div style="margin-bottom:8px">{summary}</div>
  {legend}
  <table>
    <thead><tr><th style="width:48px">Niveau</th><th>Bonne pratique</th><th>Description</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""


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
  <p style="font-size:12px;color:#666;margin-bottom:12px">
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
  <p style="font-size:11px;color:#999;margin-top:8px">
    Pour reference : un email envoye = ~4 gCO2e ; une recherche Google = ~0.2 gCO2e.
  </p>
</section>"""


def _section_recommendations(page_metrics, traffic, coverage_by_page):
    prio1, prio2, prio3 = [], [], []

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
        prio2.append(f"{len(traffic['duplicates'])} ressources chargées en double - configurer le cache navigateur")

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

    prio3 = [
        "Activer la compression Brotli sur tous les serveurs",
        "Mettre en place un CDN pour les assets statiques",
        "Évaluer le remplacement des librairies tierces lourdes (analytics, chatbot) par des alternatives légères",
    ]

    def _items(lst):
        return "".join(f"<li>{i}</li>" for i in lst) if lst else "<li>Aucun constat critique.</li>"

    def _see_also(*links):
        parts = " &nbsp;·&nbsp; ".join(
            f'<a href="#{sid}" style="color:inherit;text-decoration:underline;font-size:12px">{label}</a>'
            for sid, label in links
        )
        return f'<div style="margin-top:8px;opacity:.8">&#8594; Voir : {parts}</div>'

    return f"""<section id="recommandations">
  <h2>Recommandations</h2>
  <div class="prio prio-1">
    <b>PRIORITÉ 1 - Impact fort (&lt; 1 semaine)</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio1)}</ul>
    {_see_also(("dashboard", "A.1 Tableau de bord EcoIndex"), ("coverage", "A.3 Code mort (Coverage)"))}
  </div>
  <div class="prio prio-2">
    <b>PRIORITÉ 2 - Impact moyen (sprint)</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio2)}</ul>
    {_see_also(("trafic", "A.2 Trafic réseau"), ("dashboard", "A.1 Tableau de bord EcoIndex"))}
  </div>
  <div class="prio prio-3">
    <b>PRIORITÉ 3 - Amélioration continue</b>
    <ul style="margin-top:6px;padding-left:20px">{_items(prio3)}</ul>
    {_see_also(("trafic", "A.2 Trafic réseau"), ("greenit", "2. Bonnes pratiques GreenIT"))}
  </div>
</section>"""


# ── Entrée principale ─────────────────────────────────────────────────────────

def generate(audit_dir, output_path=None):
    audit_dir = Path(audit_dir)

    # Localisation des fichiers
    har_files = list(audit_dir.glob("*.har"))
    if not har_files:
        raise FileNotFoundError(f"Aucun fichier .har dans {audit_dir}")
    har_path = har_files[0]

    cov_files = sorted(audit_dir.glob("Coverage-*.json")) or sorted(audit_dir.glob("*coverage*.json"))
    cwv_path  = audit_dir / "cwv.json"

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

    # Sections présentes (pour le sommaire)
    annexe_sections = [
        ("dashboard", "Tableau de bord EcoIndex"),
        ("trafic",    "Trafic réseau"),
        ("coverage",  "Code mort (Coverage)"),
    ]
    if cwv:
        annexe_sections.append(("cwv", "Core Web Vitals"))

    annexe_sections = [
        ("dashboard", "Tableau de bord EcoIndex"),
        ("trafic",    "Trafic réseau"),
        ("coverage",  "Code mort (Coverage)"),
    ]
    if cwv:
        annexe_sections.append(("cwv", "Core Web Vitals"))

    letters = "abcdefgh"
    annexe_inline = " &nbsp;·&nbsp; ".join(
        f'<a href="#{sid}">3.{letters[i]} {slabel}</a>'
        for i, (sid, slabel) in enumerate(annexe_sections)
    )
    nav_items = (
        f'<li><a href="#recommandations">1. Recommandations</a></li>'
        f'<li><a href="#greenit">2. Bonnes pratiques GreenIT</a></li>'
        f'<li style="display:flex;flex-direction:column;gap:2px">'
        f'<a href="#annexes">3. Annexes</a>'
        f'<span style="font-size:11px;opacity:.75;padding-left:4px">{annexe_inline}</span>'
        f'</li>'
        f'<li><a href="#couts">&#9658; Couts de generation</a></li>'
    )

    html = _html_head(title)
    html += f"""<header>
  <h1>Audit d'écoresponsabilité web</h1>
  <div style="font-size:14px;margin-top:6px;opacity:.9">{domains}</div>
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
    html += _section_recommendations(page_metrics, traffic, coverage_by_page)
    html += _section_greenit(greenit)
    def _prefix_h2(html_str, prefix):
        return html_str.replace('<h2>', f'<h2>{prefix} — ', 1)

    html += '<section id="annexes" style="background:#f4f6fa;border:2px solid var(--octo-blue);border-radius:6px;padding:24px 24px 8px;margin-bottom:40px">\n'
    html += '<h2 style="border-left:none;padding-left:0;font-size:13px;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:20px">Annexes</h2>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_dashboard(page_metrics, cwv), "A.1")}</div>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_traffic(traffic), "A.2")}</div>\n'
    html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_coverage(coverage_by_page), "A.3")}</div>\n'
    if cwv:
        html += f'<div style="background:white;border-radius:4px;padding:20px;margin-bottom:16px">{_prefix_h2(_section_cwv(page_metrics, cwv), "A.4")}</div>\n'
    html += '</section>\n'

    html += "</main>\n"
    html += f"""<div id="couts" style="background:#f0f4f8;border-top:1px solid #ccc;padding:16px 40px">
  <details style="padding:10px 14px;background:white;border:1px solid #ccc;border-radius:4px;max-width:700px">
    <summary style="cursor:pointer;font-weight:bold;font-size:13px">Coûts de génération</summary>
    <p style="margin:10px 0 6px;font-size:12px;font-style:italic;color:#555">Estimation calculée par fenêtre temporelle sur le fichier JSONL de session. Durée et tokens peuvent inclure des échanges hors analyse. Coût aux tarifs API Anthropic publics ; sous AWS Bedrock, consulter AWS Cost Explorer.</p>
    <p style="margin:3px 0;font-size:13px"><strong>Modèle :</strong> Claude Sonnet (Agent EROOM)</p>
    <p style="margin:3px 0;font-size:13px"><strong>Tokens :</strong> voir session Claude Code</p>
    <p style="margin:3px 0;font-size:13px"><strong>Fichiers sources :</strong> {har_path.name}, {len(cov_files)} fichier(s) Coverage</p>
  </details>
</div>
<footer>Rapport généré le {today} - Outil analyse-parcours (OCTO Technology)</footer>
"""
    html += "</body>\n</html>\n"

    if output_path is None:
        output_path = audit_dir / f"rapport-parcours-{date.today().isoformat()}.html"
    output_path = Path(output_path)
    output_path.write_text(html, encoding="utf-8")
    print(f"\nRapport HTML généré : {output_path}")
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
