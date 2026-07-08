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

import json
import re
import sys
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

    for e in entries:
        req  = e.get("request", {})
        resp = e.get("response", {})
        url  = req.get("url", "")
        status = resp.get("status", 0)
        size   = resp.get("content", {}).get("size", 0)
        mime   = resp.get("content", {}).get("mimeType", "")

        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc
        except Exception:
            host = url[:40]

        domains[host] += 1
        http_codes[status] += 1
        url_counts[url] += 1
        resources.append({"url": url, "size": size, "mime": mime, "status": status, "host": host})

    top10 = sorted(resources, key=lambda x: x["size"], reverse=True)[:10]
    duplicates = [{"url": u, "count": c} for u, c in url_counts.items() if c > 1]

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


def _section_dashboard(page_metrics, cwv):
    rows = ""
    for m in page_metrics:
        badge = _badge(m["grade"], m["grade_color"])
        title = m["title"][:50]
        cwv_data = cwv.get(m["page_id"], {})
        lcp = f"{cwv_data.get('lcp','—')} s" if cwv_data else f"{m['on_load_ms']} ms *"
        inp = f"{cwv_data.get('inp','—')} ms" if cwv_data else "—"
        cls_val = str(cwv_data.get("cls", "—")) if cwv_data else "—"

        cls_class = ""
        if cwv_data:
            cls_num = cwv_data.get("cls", 0)
            if isinstance(cls_num, (int, float)) and cls_num > 0.1:
                cls_class = ' class="alert"' if cls_num > 0.25 else ""

        rows += f"""<tr{cls_class}>
      <td>{title}</td>
      <td style="text-align:center">{badge} {m['ecoindex']}/100</td>
      <td style="text-align:right">{m['req']}</td>
      <td style="text-align:right">{m['size_ko']:.0f} Ko</td>
      <td style="text-align:right">{m['dom']}</td>
      <td style="text-align:right">{lcp}</td>
      <td style="text-align:right">{inp}</td>
      <td style="text-align:right">{cls_val}</td>
    </tr>"""

    cwv_note = "" if cwv else '<p style="font-size:11px;color:#888;margin-top:6px">* LCP affiché = onLoad HAR (proxy). Fournir <code>cwv.json</code> pour les vraies métriques terrain.</p>'

    return f"""<section id="dashboard">
  <h2>Tableau de bord EcoIndex</h2>
  <table>
    <thead><tr>
      <th>Page</th><th>EcoIndex</th><th>Requêtes</th>
      <th>Poids</th><th>DOM</th><th>LCP</th><th>INP</th><th>CLS</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {cwv_note}
</section>"""


def _section_traffic(traffic):
    domains_html = "".join(
        f'<span class="domain-tag">{d} <b>({c})</b></span>'
        for d, c in list(traffic["domains"].items())[:15]
    )

    codes_html = "  ".join(
        f'<b style="color:{"green" if k < 300 else ("orange" if k < 400 else "red")}">'
        f'{k}</b> × {v}'
        for k, v in sorted(traffic["http_codes"].items())
    )

    top_rows = ""
    for r in traffic["top10"]:
        fname = r["url"].split("/")[-1][:50] or r["url"][:50]
        color = TYPE_COLORS.get(_classify_type(r["mime"], r["url"]), "#999")
        top_rows += f"""<tr>
      <td>{fname}</td>
      <td><span style="color:{color}">{_classify_type(r['mime'], r['url'])}</span></td>
      <td style="text-align:right">{round(r['size']/1024, 1)} Ko</td>
      <td style="color:#555;font-size:11px">{r['host']}</td>
    </tr>"""

    dup_rows = ""
    for d in traffic["duplicates"][:10]:
        fname = d["url"].split("/")[-1][:60] or d["url"][:60]
        dup_rows += f'<tr><td>{fname}</td><td style="text-align:center;color:red">{d["count"]}×</td></tr>'

    dup_section = ""
    if dup_rows:
        dup_section = f"""<h3>Requêtes dupliquées</h3>
  <table>
    <thead><tr><th>Fichier</th><th>Nb</th></tr></thead>
    <tbody>{dup_rows}</tbody>
  </table>"""

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
  <p style="margin-bottom:12px">{codes_html}</p>
  <h3>Top 10 ressources les plus lourdes</h3>
  <table>
    <thead><tr><th>Fichier</th><th>Type</th><th>Poids</th><th>Domaine</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>
  {dup_section}
</section>"""


def _section_coverage(coverage_by_page):
    html = '<section id="coverage">\n  <h2>Code mort (Coverage JS/CSS)</h2>\n'

    for page_name, entries in coverage_by_page.items():
        if not entries:
            continue
        summ = coverage_summary(entries)
        html += f'  <h3>{page_name}</h3>\n'

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
      <td>{e['filename']}</td>
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


def _section_cwv(page_metrics, cwv):
    if not cwv:
        return ""

    rows = ""
    for m in page_metrics:
        c = cwv.get(m["page_id"], {})
        if not c:
            continue
        lcp = c.get("lcp", "—")
        inp = c.get("inp", "—")
        cls_val = c.get("cls", "—")

        lcp_class = ""
        cls_class = ""
        if isinstance(lcp, (int, float)):
            lcp_class = 'style="color:red"' if lcp > 2.5 else ('style="color:orange"' if lcp > 1.8 else 'style="color:green"')
        if isinstance(cls_val, (int, float)):
            cls_class = 'style="color:red"' if cls_val > 0.25 else ('style="color:orange"' if cls_val > 0.1 else 'style="color:green"')

        rows += f"""<tr>
      <td>{m['title'][:40]}</td>
      <td {lcp_class}>{lcp} s</td>
      <td>{inp} ms</td>
      <td {cls_class}>{cls_val}</td>
    </tr>"""

    return f"""<section id="cwv">
  <h2>Core Web Vitals</h2>
  <p style="font-size:12px;color:#666;margin-bottom:10px">
    Seuils Google — LCP : &lt; 1,8 s (bon), &lt; 2,5 s (à améliorer), &gt; 2,5 s (mauvais).
    CLS : &lt; 0,1 (bon), &lt; 0,25 (à améliorer), &gt; 0,25 (mauvais).
  </p>
  <table>
    <thead><tr><th>Page</th><th>LCP</th><th>INP</th><th>CLS</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
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
    for page_name, entries in coverage_by_page.items():
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

    return f"""<section id="recommandations">
  <h2>Recommandations</h2>
  <div class="prio prio-1"><b>PRIORITÉ 1 - Impact fort (&lt; 1 semaine)</b><ul style="margin-top:6px;padding-left:20px">{_items(prio1)}</ul></div>
  <div class="prio prio-2"><b>PRIORITÉ 2 - Impact moyen (sprint)</b><ul style="margin-top:6px;padding-left:20px">{_items(prio2)}</ul></div>
  <div class="prio prio-3"><b>PRIORITÉ 3 - Amélioration continue</b><ul style="margin-top:6px;padding-left:20px">{_items(prio3)}</ul></div>
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

    print(f"HAR      : {har_path.name}")
    print(f"Coverage : {len(cov_files)} fichier(s)")
    print(f"CWV      : {'oui' if cwv_path.exists() else 'non (timings HAR utilisés)'}")

    har_data     = parse_har(har_path)
    page_metrics = extract_page_metrics(har_data)
    traffic      = har_traffic_analysis(har_data)
    cwv          = load_cwv(cwv_path) if cwv_path.exists() else {}

    coverage_by_page = {}
    for cf in cov_files:
        entries = parse_coverage_file(cf)
        name = cf.stem.replace("Coverage-", "").replace("_", " ")
        # Extraire "page N" du nom si présent
        m = re.search(r'page\s*(\d+)', name, re.I)
        label = f"Page {m.group(1)}" if m else name[:40]
        coverage_by_page[label] = entries

    # Construction HTML
    today   = date.today().strftime("%d/%m/%Y")
    domains = ", ".join(list(traffic["domains"].keys())[:4])
    title   = f"Audit de parcours web - {today}"

    html = _html_head(title)
    html += f"""<header>
  <h1>Audit d'écoresponsabilité web</h1>
  <div style="font-size:14px;margin-top:6px;opacity:.9">{domains}</div>
  <div class="meta">
    Date : {today} &nbsp;|&nbsp;
    {len(page_metrics)} page(s) analysée(s) &nbsp;|&nbsp;
    HAR : {har_path.name} &nbsp;|&nbsp;
    Coverage : {len(cov_files)} fichier(s)
  </div>
</header>
<main>
"""
    html += _section_dashboard(page_metrics, cwv)
    html += _section_traffic(traffic)
    html += _section_coverage(coverage_by_page)
    html += _section_cwv(page_metrics, cwv)
    html += _section_recommendations(page_metrics, traffic, coverage_by_page)

    html += "</main>\n"
    html += f'<footer>Rapport généré le {today} - Outil analyse-parcours (OCTO Technology)</footer>\n'
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
