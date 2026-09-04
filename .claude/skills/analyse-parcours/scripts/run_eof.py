#!/usr/bin/env python3
"""Remplit automatiquement ce qui peut l'être du référentiel EOF pour un
site audité, à partir UNIQUEMENT de `eof-referentiel.json` (produit par le
skill `eof`) et des données déjà collectées par `analyse-parcours`
(`env-data.json`, `audit/har-analysis.json`, `audit/coverage-analysis.json`,
`cwv.json`, `security-headers-analysis.json`, `wellknown-scan.json`,
`html-css-criteria.json`). Ne lit JAMAIS la Google Sheet ni le Markdown
humain — c'est le découplage voulu entre "synchroniser le référentiel" et
"auditer un site" (cf. plan d'architecture, `tmp/handoff.md`).

Sur les 54 critères détaillés (6 dimensions), une reconnaissance manuelle
initiale (2026-09-03) avait montré que 10 étaient exploitables (4
"automatisable", 6 "partiel"). Extension Phase 1 (même jour, plan
`eof-questionnaire`) : 18 exploitables (7 "automatisable" avec case cochée :
1.12, 2.1, 3.3, 5.4, 1.5, 1.6, 1.13 ; 11 "partiel" avec indice contextuel
jamais coché) — les 36 autres restent "je ne sais pas" par construction,
cf. `eof_criteria_mapping.py`. Les 16 questions de 🏦 0-Diagnostic rapide ne
sont JAMAIS remplies automatiquement (échelle 1-5 différente, décision
explicite), SAUF 0.16 : elles apparaissent en aperçu, avec pour 0.4 et 0.10
un indice contextuel affiché à titre indicatif (jamais une réponse cochée).

Usage :
    python3 run_eof.py <source_dir>

Écrit dans <source_dir>/ :
    eof-audit-results.json  - résumé léger, consommé par generate_report_html.py
    eof-rempli.md           - référentiel complet lisible, réponses + provenance + source
    eof-radar-<domaine>.svg - radar des 6 dimensions (valeurs None = "N/A", jamais un faux 0%)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from eof_criteria_mapping import MAPPING  # noqa: E402
from csp_inventory import inventory_from_headers_analysis, tracking_summary  # noqa: E402
from deploy_freshness import analyse_har_freshness, find_har, summarise  # noqa: E402

sys.path.insert(0, str(SCRIPT_DIR.parent.parent / "eof" / "scripts"))
from generate_radar_svg import radar_svg  # noqa: E402

REFERENTIEL_PATH = (
    SCRIPT_DIR.parent.parent / "eof" / "docs"
    / "EOF-V.1.1 (EROOM Optimization Framework) - Template - Français"
    / "eof-referentiel.json"
)

CWV_GOOD = {"lcp": 2.5, "inp": 200, "cls": 0.1}
CWV_POOR = {"lcp": 4.0, "inp": 500, "cls": 0.25}


def load_json(path):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return None


def find_first(*candidates):
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    return None


def load_audit_data(source_dir):
    """Charge les données d'audit. COÛT : parse le .har entier (fichier lourd)
    pour deploy_freshness, alors qu'aujourd'hui seuls les résumés JSON étaient lus.
    """
    audit_dir = source_dir / "audit"
    env = load_json(find_first(source_dir / "env-data.json", audit_dir / "env-data.json"))
    har = load_json(find_first(audit_dir / "har-analysis.json", source_dir / "har-analysis.json"))
    coverage = load_json(find_first(audit_dir / "coverage-analysis.json", source_dir / "coverage-analysis.json"))
    cwv = load_json(find_first(source_dir / "cwv.json", audit_dir / "cwv.json"))
    headers = load_json(find_first(source_dir / "security-headers-analysis.json", audit_dir / "security-headers-analysis.json"))
    wellknown = load_json(find_first(source_dir / "wellknown-scan.json", audit_dir / "wellknown-scan.json"))
    htmlcss = load_json(find_first(source_dir / "html-css-criteria.json", audit_dir / "html-css-criteria.json"))
    return {
        "env": env, "har": har, "coverage": coverage, "cwv": cwv,
        "headers": headers, "wellknown": wellknown, "htmlcss": htmlcss,
        "source_dir": source_dir,  # exposé pour deploy_freshness (nécessite le chemin du .har, pas le JSON)
    }


# ---------------------------------------------------------------------------
# Règles "automatisable" : retournent (reponse, provenance, source) ou (None, None, motif)
# ---------------------------------------------------------------------------

def rule_1_12(data):
    """Distingue pistage (marketing, pixels publicitaires, analytics comportemental)
    de l'analytics sobre (sans cookie, sans profilage).

    Provenance : estime (classification taxonomique des domaines en familles pistage/sobre).
    """
    headers = data["headers"]
    har = data["har"]
    inv = inventory_from_headers_analysis(headers)

    # Si aucun CSP disponible, repli sur l'ancienne heuristique tech_stack
    if inv is None:
        env = data["env"]
        categories = ((env or {}).get("tech_stack") or {}).get("categories") or {}
        analytics = categories.get("Analytics")
        if not analytics:
            return "✅ Point fort confirmé", "estime", "env-data.json: tech_stack.categories — aucune techno 'Analytics' détectée"
        tp_share = ((env or {}).get("har_summary") or {}).get("efootprint", {}).get("third_party_share")
        extra = f", third_party_share={tp_share:.1%}" if tp_share is not None else ""
        return ("💡 Potentiel d'amélioration identifié", "estime",
                f"env-data.json: tech_stack.categories['Analytics'] = {', '.join(analytics)}{extra} (CSP absent : heuristique ancienne)")

    summary = tracking_summary(inv, har)
    if summary is None or not summary["loaded_connu"]:
        return (None, None,
                "security-headers-analysis.json: CSP présent mais har-analysis.json absent — "
                "impossible de distinguer déclaré/chargé")

    pistage = summary["pistage_charge"]
    pistage_declare_only = summary["pistage_declare_non_charge"]
    sobre = summary["analytics_sobre_charge"]

    # Pistage effectivement chargé -> problème identifié
    if pistage:
        return ("💡 Potentiel d'amélioration identifié", "estime",
                f"security-headers-analysis.json + har-analysis.json: pistage effectivement chargé : {', '.join(pistage)}")

    # Pistage déclaré mais absent du HAR -> écart (probablement capture sans consentement)
    if pistage_declare_only:
        return ("🤔 À évaluer", "estime",
                f"security-headers-analysis.json + har-analysis.json: pistage déclaré au CSP mais absent du HAR "
                f"({', '.join(pistage_declare_only)}) — probable capture sans accepter le consentement")

    # Seulement analytics sobre -> point fort
    if sobre:
        return ("✅ Point fort confirmé", "estime",
                f"security-headers-analysis.json + har-analysis.json: seulement analytics sobre chargé ({', '.join(sobre)}), "
                "aucun pistage marketing/publicitaire/comportemental")

    # Ni pistage ni analytics sobre
    return ("✅ Point fort confirmé", "estime",
            "security-headers-analysis.json + har-analysis.json: aucun pistage ni analytics détecté")


def rule_2_1(data):
    """Détection de technologies IA et blockchain.

    Provenance : estime. La détection de technologies est une empreinte, pas une
    mesure : l'absence d'empreinte IA ne prouve pas l'absence d'IA, et le
    rattachement d'une techno à la catégorie "IA" vient du catalogue de l'outil de
    détection, pas du service audité.
    """
    env = data["env"]
    ai = (env or {}).get("ai_external_apis") or {}
    techs = ((env or {}).get("tech_stack") or {}).get("technologies") or []
    flagged = [t["name"] for t in techs if t.get("category", "").lower() in ("ia", "intelligence artificielle", "blockchain")]
    if not ai and not flagged:
        return "✅ Point fort confirmé", "estime", "env-data.json: ai_external_apis vide, aucune techno IA/blockchain détectée"
    detail = list(ai.keys()) + flagged
    return "💡 Potentiel d'amélioration identifié", "estime", f"env-data.json: ai_external_apis/tech_stack = {detail}"


def rule_3_3(data):
    """Intensité carbone de l'hébergement.

    Provenance : collecte (API ipinfo + table de référence intensité carbone par pays).
    """
    env = data["env"]
    servers = (env or {}).get("servers")
    if not servers and (env or {}).get("server"):
        servers = [env["server"]]
    if not servers:
        return None, None, "env-data.json: servers[] absent"
    seuil = 250
    detail = "; ".join(
        f"{s.get('host', '?')} ({s.get('country_code', '?')}, {s.get('carbon_intensity_g_kwh', '?')} gCO2/kWh)"
        for s in servers
    )
    over = [s for s in servers if (s.get("carbon_intensity_g_kwh") or 0) > seuil]
    if over:
        return "💡 Potentiel d'amélioration identifié", "collecte", f"env-data.json: servers[] = {detail} (seuil {seuil} gCO2/kWh dépassé)"
    return "✅ Point fort confirmé", "collecte", f"env-data.json: servers[] = {detail} (sous le seuil {seuil} gCO2/kWh)"


def rule_5_4(data):
    """Core Web Vitals (LCP, INP, CLS).

    Provenance : collecte (données terrain Chrome UX Report via API CrUX).
    """
    cwv = data["cwv"]
    if not cwv:
        return None, None, "cwv.json absent"
    poor_pages, all_good = [], True
    for entry in cwv:
        lcp, inp, cls = entry.get("lcp"), entry.get("inp"), entry.get("cls")
        label = entry.get("url") or entry.get("page") or "?"
        if (lcp is not None and lcp > CWV_POOR["lcp"]) or \
           (inp is not None and inp > CWV_POOR["inp"]) or \
           (cls is not None and cls > CWV_POOR["cls"]):
            poor_pages.append(label)
        if not ((lcp is None or lcp <= CWV_GOOD["lcp"]) and
                (inp is None or inp <= CWV_GOOD["inp"]) and
                (cls is None or cls <= CWV_GOOD["cls"])):
            all_good = False
    if poor_pages:
        return "💡 Potentiel d'amélioration identifié", "collecte", f"cwv.json: page(s) en zone 'poor' : {', '.join(sorted(set(poor_pages)))}"
    if all_good:
        return "✅ Point fort confirmé", "collecte", "cwv.json: toutes les pages sous les seuils CWV 'good'"
    return "🤔 À évaluer", "collecte", "cwv.json: zone intermédiaire ('needs improvement'), aucune page 'poor'"


# --- Extension Phase 1 (2026-09-03) ---------------------------------------

def rule_1_5(data):
    """Détection de médias à lecture automatique (autoplay).

    Provenance : collecte (parsing HTML, recherche attribut autoplay sur <video>/<audio>).
    """
    htmlcss = data["htmlcss"]
    pages = (htmlcss or {}).get("pages")
    if not pages:
        return None, None, "html-css-criteria.json absent"
    offenders = [p["url"] for p in pages if p.get("has_autoplay_media")]
    if offenders:
        return "💡 Potentiel d'amélioration identifié", "collecte", f"html-css-criteria.json: autoplay détecté sur {offenders}"
    return "✅ Point fort confirmé", "collecte", "html-css-criteria.json: aucune balise <video|audio autoplay> détectée sur les pages auditées"


def rule_1_6(data):
    """Adaptation des ressources (images responsive, media queries CSS).

    Provenance : estime. Les comptages sont mesurés, mais le verdict repose sur des
    seuils de notre invention (ratio d'images adaptatives >= 0,5 et au moins
    3 @media queries) que ni le référentiel EOF ni aucune source publique ne fixe.
    Le chiffre est collecté, la conclusion est déduite.
    """
    htmlcss = data["htmlcss"]
    pages = (htmlcss or {}).get("pages")
    css = (htmlcss or {}).get("css")
    if not pages or css is None:
        return None, None, "html-css-criteria.json absent"
    ratios = [p["adaptive_img_ratio"] for p in pages if p.get("adaptive_img_ratio") is not None]
    has_any_adaptive_img = any(r > 0 for r in ratios)
    all_pages_adaptive = bool(ratios) and all(r >= 0.5 for r in ratios)
    has_media_queries = (css.get("media_query_count") or 0) >= 3
    source = f"html-css-criteria.json: adaptive_img_ratio par page = {ratios} ; media_query_count = {css.get('media_query_count')}"
    if all_pages_adaptive and has_media_queries:
        return "✅ Point fort confirmé", "estime", source
    if not has_any_adaptive_img and not has_media_queries:
        return "💡 Potentiel d'amélioration identifié", "estime", source
    return "🤔 À évaluer", "estime", source + " (signaux discordants entre pages/CSS, contrainte déterministe : ne pas trancher)"


def rule_1_13(data):
    """Optimisation des parcours (proxy : score d'accessibilité Lighthouse).

    Provenance : collecte (API PageSpeed Insights, catégorie accessibility).
    """
    cwv = data["cwv"]
    if not cwv:
        return None, None, "cwv.json absent"
    accessibility_scores = [e["accessibility_score_pct"] for e in cwv if e.get("accessibility_score_pct") is not None]
    if not accessibility_scores:
        return None, None, "cwv.json: aucun accessibility_score_pct disponible"
    worst = min(accessibility_scores)
    source = f"cwv.json: accessibility_score_pct (PageSpeed Insights) — pire page/stratégie = {worst}, valeurs = {accessibility_scores}"
    if worst < 60:
        return "💡 Potentiel d'amélioration identifié", "collecte", source
    if worst >= 90:
        return "✅ Point fort confirmé", "collecte", source
    return "🤔 À évaluer", "collecte", source + " (zone 60-90, ambigu)"


RULES = {
    "1.12": rule_1_12, "2.1": rule_2_1, "3.3": rule_3_3, "5.4": rule_5_4,
    "1.5": rule_1_5, "1.6": rule_1_6, "1.13": rule_1_13,
}


# ---------------------------------------------------------------------------
# Diagnostic rapide : JAMAIS automatisé, sauf 0.16 — doublon quasi exact de
# 3.3 (même donnée : servers[].carbon_intensity_g_kwh), avec une échelle
# numérique plus précise. Décision explicite du 2026-09-03 (analyse
# eof-analyse-minimisation-questions.md, section 1) : seule exception au
# principe "Diagnostic rapide = aperçu, jamais rempli automatiquement".
# ---------------------------------------------------------------------------

# (seuil_haut_exclusif, rang_cran) des crans 2 à 5 ("< X gCO2e/kWh"), du
# meilleur au pire. Le cran 1 ("> 750") est le repli si aucun seuil n'est
# satisfait. Zone [500, 750] non couverte par l'échelle du Sheet source
# (biais connu, cf. eof-analyse-minimisation-questions.md) : repli sur le
# cran 1 avec provenance dégradée à "estime" au lieu de "collecte", pour ne pas
# prétendre à une précision que l'échelle source n'a pas à cet endroit.
_CARBON_BUCKETS = [(100, 5), (200, 4), (300, 3), (500, 2)]


def rule_diag_0_16(data, crans):
    """Diagnostic rapide 0.16 : intensité carbone hébergement (doublon de 3.3).

    Provenance : collecte (même source que 3.3, API ipinfo + table carbone),
    dégradée à estime pour la zone [500, 750] gCO2/kWh non couverte par l'échelle.
    """
    env = data["env"]
    servers = (env or {}).get("servers")
    if not servers and (env or {}).get("server"):
        servers = [env["server"]]
    if not servers:
        return None, None, "env-data.json: servers[] absent"
    # Cran le plus défavorable parmi tous les serveurs 1st-party détectés.
    worst_rank, worst_value = 1, None
    for s in servers:
        v = s.get("carbon_intensity_g_kwh")
        if v is None:
            continue
        rank = next((r for upper, r in _CARBON_BUCKETS if v < upper), 1)
        if worst_value is None or rank < worst_rank:
            worst_rank, worst_value = rank, v
    if worst_value is None:
        return None, None, "env-data.json: servers[].carbon_intensity_g_kwh absent"
    # Dégradation de provenance pour la zone [500, 750] non couverte par l'échelle EOF
    provenance = "estime" if (worst_rank == 1 and worst_value <= 750) else "collecte"
    reponse = next((c for c in crans if c.strip().startswith(f"{worst_rank}")), crans[worst_rank - 1] if len(crans) >= worst_rank else None)
    source_suffix = " (repli échelle, zone non couverte [500, 750])" if provenance == "estime" else ""
    source = f"env-data.json: servers[].carbon_intensity_g_kwh = {worst_value} gCO2e/kWh (doublon de 3.3, même donnée){source_suffix}"
    return reponse, provenance, source


# ---------------------------------------------------------------------------
# Contextes "partiel" : indice affiché en annexe, jamais une réponse cochée
# ---------------------------------------------------------------------------

def context_1_9(data):
    env = data["env"]
    v = ((env or {}).get("har_summary") or {}).get("efootprint", {}).get("data_transferred_bytes_real")
    return f"Poids réel transféré (page repère) : {v / 1024:.0f} Ko" if v else None


def context_1_14(data):
    env = data["env"]
    pages = [(p.get("url", "?"), p.get("size_kb")) for p in ((env or {}).get("pages") or []) if p.get("size_kb") is not None]
    if not pages:
        return None
    pages.sort(key=lambda x: -x[1])
    return f"Page la plus lourde : {pages[0][0]} ({pages[0][1]:.0f} Ko) ; la plus légère : {pages[-1][0]} ({pages[-1][1]:.0f} Ko)"


def context_1_15(data):
    env = data["env"]
    t = (env or {}).get("traffic") or {}
    v = t.get("visits_per_year")
    return f"Trafic estimé : {v:,} visites/an ({t.get('source', '?')})" if v else None


def context_5_5(data):
    coverage = data["coverage"]
    pages = (coverage or {}).get("pages") or []
    worst = sorted(pages, key=lambda p: -(p.get("js_unused_pct") or 0))[:2]
    if not worst:
        return None
    return "; ".join(f"{p.get('url', '?')} : JS inutilisé {p.get('js_unused_pct', '?')}%" for p in worst)


def context_2_3(data):
    """Indice de composants backend séparés (PaaS distincts déclarés au CSP)."""
    headers = data["headers"]
    inv = inventory_from_headers_analysis(headers)
    if not inv:
        return None
    families = inv["familles"]
    paas = families.get("paas_backend") or []
    if not paas:
        return None
    return f"Composant(s) backend externalisé(s) détecté(s) ({', '.join(paas)}) : ces domaines PaaS distincts suggèrent une architecture à composants séparés, mais ne prouvent ni l'efficacité de leur couplage ni l'optimisation de leur communication"


def context_2_5(data):
    har = data["har"]
    dups = sorted((har or {}).get("duplicate_urls") or [], key=lambda d: -d.get("count", 0))[:3]
    if not dups:
        return None
    return "; ".join(f"{d['url']} ×{d['count']}" for d in dups)


# --- Extension Phase 1 (2026-09-03) ---------------------------------------

def context_1_4(data):
    htmlcss = data["htmlcss"]
    pages = (htmlcss or {}).get("pages") or []
    native = sum(p.get("native_buttons") or 0 for p in pages)
    custom = sum(p.get("custom_role_buttons") or 0 for p in pages)
    if native + custom == 0:
        return None
    return f"Boutons natifs <button> : {native} ; boutons personnalisés (role=\"button\") : {custom} (toutes pages confondues)"


def context_1_11(data):
    htmlcss = data["htmlcss"]
    css = (htmlcss or {}).get("css")
    if css is None:
        return None
    return ("@media (prefers-reduced-motion|prefers-color-scheme) détecté dans le CSS chargé"
            if css.get("has_prefers_reduced_or_scheme")
            else "Aucune règle @media (prefers-reduced-motion|prefers-color-scheme) détectée dans le CSS chargé")


def context_6_1(data):
    headers = data["headers"]
    worst = (headers or {}).get("worst_page")
    if not worst:
        return None
    return f"Score en-têtes sécurité (proxy indirect de maturité prod) : {worst['score_pct']}% (grade {worst['grade']}) sur {worst['url']}"


def context_3_5(data):
    """Indice d'infrastructure mutualisée (PaaS/CDN/cloud déclarés au CSP)."""
    headers = data["headers"]
    inv = inventory_from_headers_analysis(headers)
    if not inv:
        return None
    families = inv["familles"]
    paas = families.get("paas_backend") or []
    cdn = families.get("cdn_bibliotheques") or []
    cloud = families.get("infra_cloud_generique") or []
    all_mut = paas + cdn + cloud
    if not all_mut:
        return None
    return f"Infrastructure mutualisée déclarée au CSP : {len(all_mut)} domaine(s) (PaaS/CDN/cloud) : {', '.join(all_mut[:5])}{'...' if len(all_mut) > 5 else ''}"


def context_3_7(data):
    """Indice de plate-forme supportant l'élasticité (PaaS déclarés au CSP)."""
    headers = data["headers"]
    inv = inventory_from_headers_analysis(headers)
    if not inv:
        return None
    families = inv["familles"]
    paas = families.get("paas_backend") or []
    if not paas:
        return None
    return f"Plate-forme(s) PaaS détectée(s) ({', '.join(paas)}) : ces services cloud supportent l'auto-scaling natif, mais rien ne prouve qu'il soit configuré ni que la charge du service varie suffisamment pour le justifier"


def context_6_3(data):
    """Indice de fraîcheur et atomicité de déploiement (Last-Modified du .har)."""
    source_dir = data.get("source_dir")
    if not source_dir:
        return None
    har_path = find_har(source_dir)
    if not har_path:
        return None
    env = data["env"]
    first_party_hosts = set()
    for page in (env or {}).get("pages") or []:
        url = page.get("url")
        if url:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower()
            if host:
                first_party_hosts.add(host)
    info = analyse_har_freshness(har_path, first_party_hosts or None)
    return summarise(info)


def context_6_6(data):
    cwv = data["cwv"]
    headers = data["headers"]
    wellknown = data["wellknown"]
    parts = []
    if cwv:
        bp_scores = [e["best_practices_score_pct"] for e in cwv if e.get("best_practices_score_pct") is not None]
        if bp_scores:
            parts.append(f"Best Practices Lighthouse (pire page) : {min(bp_scores)}%")
    if headers and headers.get("worst_page"):
        parts.append(f"en-têtes sécurité (pire page) : grade {headers['worst_page']['grade']}")
    if wellknown is not None:
        txt = (wellknown.get("security_txt") or {})
        parts.append(f"security.txt : {'présent, bien formé' if txt.get('well_formed') else ('présent, mal formé' if txt.get('present') else 'absent')}")
    return "; ".join(parts) if parts else None


def context_6_8(data):
    """Indice de duplication de bundles JS (audit Lighthouse duplicated-javascript).
    Tolérant aux deux formats : logical_name ("duplicated-javascript") ou clé brute
    ("duplicated-javascript-insight" ou "duplicated-javascript").
    """
    cwv = data["cwv"]
    if not cwv:
        return None
    # Chercher l'audit dans toutes les entrées (pages/stratégies)
    for entry in cwv:
        insights = entry.get("lighthouse_insights")
        if not insights:
            continue
        # Chercher par logical_name (nouveau format) ou par clés brutes (ancien format)
        dup = (insights.get("duplicated-javascript") or
               insights.get("duplicated-javascript-insight"))
        if dup is None:
            continue
        score = dup.get("score")
        item_count = dup.get("itemCount", 0)
        found_as = dup.get("found_as")
        if found_as is None:
            # Ancien format : deviner la clé depuis insights
            found_as = "duplicated-javascript-insight" if "duplicated-javascript-insight" in insights else "duplicated-javascript"
        if score == 1 and item_count == 0:
            return f"Audit Lighthouse '{found_as}' : aucune duplication de bundle détectée (score parfait, 0 item) - ne prouve pas que la gestion des dépendances soit bonne, seulement l'absence de duplication évidente"
        elif score is not None:
            return f"Audit Lighthouse '{found_as}' : score {score:.2f}, {item_count} item(s) détecté(s) - indice de duplication potentielle de bundles JS"
        else:
            return f"Audit Lighthouse '{found_as}' : présent mais sans score (contenu non analysable)"
    return None


CONTEXTS = {
    "1.9": context_1_9, "1.14": context_1_14,
    "1.15": context_1_15, "1.16": context_1_15,  # même champ trafic
    "5.5": context_5_5, "2.3": context_2_3, "2.5": context_2_5,
    "3.5": context_3_5, "3.7": context_3_7,
    "1.4": context_1_4, "1.11": context_1_11,
    "6.1": context_6_1, "6.3": context_6_3, "6.6": context_6_6, "6.8": context_6_8,
}

# Indices contextuels pour 🏦 0-Diagnostic rapide — jamais une réponse cochée
# (seul 0.16 a droit à une réponse automatique, cf. plus haut), simplement une
# donnée affichée en regard de la question dans l'aperçu.

def diag_context_0_4(data):
    har = data["har"]
    third_party = (har or {}).get("domains", {}).get("third_party")
    if third_party is None:
        return None
    return f"{len(third_party)} domaine(s) tiers détecté(s) dans le HAR (≠ dépendances techniques du SI, simple proxy) : {', '.join(third_party)}"


def diag_context_0_10(data):
    wellknown = data["wellknown"]
    sitemap = (wellknown or {}).get("sitemap") or {}
    if not sitemap.get("present") or not sitemap.get("url_count"):
        return None
    import math
    n = sitemap["url_count"]
    return f"{n} URL(s) dans le sitemap (échelle grossière log2 ≈ {math.log2(n):.1f})"


DIAG_CONTEXTS = {"0.4": diag_context_0_4, "0.10": diag_context_0_10}


# ---------------------------------------------------------------------------
# Évaluation d'un critère
# ---------------------------------------------------------------------------

def evaluate_criterion(crit, data):
    entry = MAPPING.get(crit["id"])
    result = {
        "id": crit["id"], "dimension": crit["pilier"], "critere": crit["critere"],
        "potentiel_max": crit["potentiel_max"], "categorie": "aucune_donnee",
        "reponse": None, "coefficient": None, "provenance": None, "source": None, "contexte": None,
    }
    if not entry:
        return result

    result["categorie"] = entry["categorie"]
    if entry["categorie"] == "automatisable":
        rule = RULES.get(crit["id"])
        reponse, provenance, source = rule(data) if rule else (None, None, "règle non implémentée")
        result["source"] = source
        if reponse is not None:
            result["reponse"] = reponse
            result["coefficient"] = crit["options_evaluation_coefficient"].get(reponse)
            result["provenance"] = provenance
    elif entry["categorie"] == "partiel":
        ctx_fn = CONTEXTS.get(crit["id"])
        contexte = ctx_fn(data) if ctx_fn else None
        if contexte:
            result["contexte"] = contexte
            result["provenance"] = entry["provenance_max"]
            result["source"] = entry["champ_donnee"]
    return result


def build_diag_rapide_apercu(referentiel, data):
    questions = []
    for q in referentiel["diagnostic_rapide"]:
        entry = {"id": q["id"], "critere": q["critere"], "niveau_impact": q["niveau_impact"],
                 "reponse": None, "provenance": None, "source": None, "indice_contextuel": None}
        if q["id"] == "0.16":
            reponse, provenance, source = rule_diag_0_16(data, q["crans"])
            if reponse is not None:
                entry.update(reponse=reponse, provenance=provenance, source=source)
        ctx_fn = DIAG_CONTEXTS.get(q["id"])
        if ctx_fn:
            entry["indice_contextuel"] = ctx_fn(data)
        questions.append(entry)
    return questions


def compute_dimension_scores(criteres_results):
    by_dim = {}
    for c in criteres_results:
        by_dim.setdefault(c["dimension"], []).append(c)
    dimensions = []
    for dim, items in by_dim.items():
        answered = [c for c in items if c["reponse"] is not None]
        # Formule canonique : somme des potentiels retenus ÷ somme des potentiel_max de TOUS les critères de la dimension
        total_potentiel_max = sum(c["potentiel_max"] for c in items) or 1e-9
        if answered:
            potentiel_optimisation_pct = sum(c["coefficient"] * c["potentiel_max"] for c in answered) / total_potentiel_max * 100
        else:
            potentiel_optimisation_pct = None
        completude_pct = len(answered) / len(items) * 100 if items else 0
        # Comptage par provenance
        repondus_par_provenance = {"collecte": 0, "estime": 0, "declare": 0, "precise": 0}
        for c in answered:
            prov = c.get("provenance")
            if prov in repondus_par_provenance:
                repondus_par_provenance[prov] += 1
        dimensions.append({
            "nom": dim, "potentiel_optimisation_pct": potentiel_optimisation_pct,
            "repondus": len(answered), "total": len(items),
            "completude_pct": completude_pct,
            "repondus_par_provenance": repondus_par_provenance,
        })
    return dimensions


def build_eof_rempli_md(referentiel, results_by_id, dimensions, diag_rapide_apercu):
    lines = ["# EOF — Référentiel rempli automatiquement (partiel)\n"]
    lines.append(
        "> Généré par `run_eof.py`, depuis les données d'audit disponibles. "
        "**La grande majorité des critères ne peut pas être déduite automatiquement** "
        "(questions organisationnelles/produit) : ils restent \"je ne sais pas\", à "
        "compléter humainement dans le template vierge du skill `eof`.\n"
    )
    lines.append(
        "## 🏦 0 — Diagnostic rapide (aperçu, jamais rempli automatiquement — "
        "SAUF 0.16, doublon exact de 3.3, cf. `eof-analyse-minimisation-questions.md`)\n"
    )
    for q in diag_rapide_apercu:
        if q["reponse"]:
            lines.append(
                f"- **{q['id']}** — {q['critere']} → **{q['reponse']}** "
                f"_(automatique, provenance {q['provenance']} — {q['source']})_"
            )
        elif q.get("indice_contextuel"):
            lines.append(
                f"- **{q['id']}** — {q['critere']} _(niveau d'impact : {q['niveau_impact']})_ "
                f"— donnée indicative : {q['indice_contextuel']}"
            )
        else:
            lines.append(f"- **{q['id']}** — {q['critere']} _(niveau d'impact : {q['niveau_impact']})_")
    lines.append("")
    current_dim = None
    for crit in referentiel["criteres"]:
        r = results_by_id[crit["id"]]
        if crit["pilier"] != current_dim:
            current_dim = crit["pilier"]
            dim_info = next(d for d in dimensions if d["nom"] == current_dim)
            potentiel_txt = f"{dim_info['potentiel_optimisation_pct']:.0f}%" if dim_info["potentiel_optimisation_pct"] is not None else "sans donnée"
            lines.append(f"\n## {current_dim} — potentiel d'optimisation : {potentiel_txt} ({dim_info['repondus']}/{dim_info['total']} répondus)\n")
        lines.append(f"### {crit['id']} — {crit['critere']}\n")
        if r["reponse"]:
            lines.append(f"**Réponse (automatique)** : {r['reponse']}")
            lines.append(f"**Provenance** : {r['provenance']} — **Source** : {r['source']}")
        elif r["contexte"]:
            lines.append("**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)")
            lines.append(f"**Donnée indicative** ({r['provenance']}) : {r['contexte']} — _champ : {r['source']}_")
        else:
            lines.append("**Réponse** : je ne sais pas (aucune donnée d'audit disponible — critère organisationnel/produit)")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir")
    parser.add_argument("--domaine", default=None, help="Nom court utilisé pour eof-radar-<domaine>.svg (déduit du dossier sinon)")
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    domaine = args.domaine or source_dir.name

    if not REFERENTIEL_PATH.exists():
        print(f"ERREUR : référentiel introuvable ({REFERENTIEL_PATH}). Lancer le skill eof d'abord.")
        sys.exit(1)
    referentiel = json.loads(REFERENTIEL_PATH.read_text(encoding="utf-8"))

    data = load_audit_data(source_dir)
    # Clés de données réelles (exclut source_dir, qui est toujours non-None)
    data_keys = ("env", "har", "coverage", "cwv", "headers", "wellknown", "htmlcss")
    if not any(data[k] for k in data_keys):
        print("⚠ Aucune donnée d'audit trouvée (env-data.json / har-analysis.json / coverage-analysis.json / "
              "cwv.json / security-headers-analysis.json / wellknown-scan.json / html-css-criteria.json) "
              "— tous les critères resteront 'je ne sais pas'.")

    results = [evaluate_criterion(c, data) for c in referentiel["criteres"]]
    results_by_id = {r["id"]: r for r in results}
    dimensions = compute_dimension_scores(results)
    diag_rapide_apercu = build_diag_rapide_apercu(referentiel, data)

    auto_answered = [r for r in results if r["categorie"] == "automatisable" and r["reponse"] is not None]
    all_answered = [r for r in results if r["reponse"] is not None]
    partiel_with_context = [r for r in results if r["categorie"] == "partiel" and r["contexte"] is not None]
    # Calcul global : même formule que par dimension, appliquée à tous les critères
    total_potentiel_max_global = sum(r["potentiel_max"] for r in results) or None
    potentiel_optimisation_global_pct = (
        sum(r["coefficient"] * r["potentiel_max"] for r in all_answered) / total_potentiel_max_global * 100
        if total_potentiel_max_global else None
    )
    completude_globale_pct = len(all_answered) / len(results) * 100 if results else 0
    # Comptage par provenance global
    repondus_par_provenance = {"collecte": 0, "estime": 0, "declare": 0, "precise": 0}
    for r in all_answered:
        prov = r.get("provenance")
        if prov in repondus_par_provenance:
            repondus_par_provenance[prov] += 1

    # Radar : une valeur par dimension, None si aucune réponse (jamais un faux 0%)
    axes = [(d["nom"], d["potentiel_optimisation_pct"]) for d in dimensions]
    radar_note = (
        f"{len(auto_answered)}/{len(referentiel['criteres'])} critères répondus automatiquement — "
        "les axes 'N/A' n'ont aucune réponse (jamais un faux 0%)"
    )
    svg_text = radar_svg(axes, title=f"EOF — potentiel d'optimisation ({domaine})", note=radar_note)
    radar_path = source_dir / f"eof-radar-{domaine}.svg"
    radar_path.write_text(svg_text, encoding="utf-8")

    audit_results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domaine": domaine,
        "criteres_total": len(referentiel["criteres"]),
        "criteres_repondus": len(all_answered),
        "criteres_avec_indice_partiel": len(partiel_with_context),
        "completude_globale_pct": completude_globale_pct,
        "potentiel_optimisation_global_pct": potentiel_optimisation_global_pct,
        "repondus_par_provenance": repondus_par_provenance,
        "dimensions": dimensions,
        "diagnostic_rapide_apercu": {
            "total_questions": len(referentiel["diagnostic_rapide"]),
            "note": (
                "Échelle 1 à 5, jamais remplie automatiquement — à évaluer humainement. "
                "Exception : 0.16 (doublon exact de 3.3), cf. eof-analyse-minimisation-questions.md."
            ),
            "questions": diag_rapide_apercu,
        },
        "criteres": results,
    }

    results_path = source_dir / "eof-audit-results.json"
    results_path.write_text(json.dumps(audit_results, ensure_ascii=False, indent=2), encoding="utf-8")

    md_text = build_eof_rempli_md(referentiel, results_by_id, dimensions, diag_rapide_apercu)
    md_path = source_dir / "eof-rempli.md"
    md_path.write_text(md_text, encoding="utf-8")

    print(f"eof-audit-results.json écrit : {results_path}")
    print(f"eof-rempli.md écrit : {md_path}")
    print(f"eof-radar-{domaine}.svg écrit : {radar_path}")
    # Le potentiel est rapporté à TOUS les critères, pas aux seuls répondus : sans la
    # complétude affichée juste à côté, un chiffre bas se lit comme un service mature
    # alors qu'il ne dit que "nous n'avons presque rien regardé".
    print(f"Critères répondus automatiquement : {len(auto_answered)}/{len(referentiel['criteres'])}"
          f" (complétude {completude_globale_pct:.1f} %)"
          + (f" — potentiel d'optimisation global, rapporté aux {len(referentiel['criteres'])} critères :"
             f" {potentiel_optimisation_global_pct:.2f} %" if potentiel_optimisation_global_pct is not None else ""))


if __name__ == "__main__":
    main()
