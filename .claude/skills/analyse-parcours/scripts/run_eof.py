#!/usr/bin/env python3
"""Remplit automatiquement ce qui peut l'être du référentiel EOF pour un
site audité, à partir UNIQUEMENT de `eof-referentiel.json` (produit par le
skill `eof`) et des données déjà collectées par `analyse-parcours`
(`env-data.json`, `audit/har-analysis.json`, `audit/coverage-analysis.json`,
`cwv.json`, `security-headers-analysis.json`, `wellknown-scan.json`,
`html-css-criteria.json`, `pages-publiques-criteria.json`). Ne lit JAMAIS la Google Sheet ni le Markdown
humain — c'est le découplage voulu entre "synchroniser le référentiel" et
"auditer un site" (cf. plan d'architecture, `tmp/handoff.md`).

Sur les 54 critères détaillés (6 dimensions), une reconnaissance manuelle
initiale (2026-09-03) avait montré que 10 étaient exploitables (4
"automatisable", 6 "partiel"). Extension Phase 1 (même jour, plan
`eof-questionnaire`) : 18 exploitables (7 "automatisable" avec case cochée :
1.12, 2.1, 3.3, 5.4, 1.5, 1.6, 1.13 ; 11 "partiel" avec indice contextuel
jamais coché). Extension Phase 2 (2026-09-07, pages publiques) : 23
exploitables (7 "automatisable" inchangé ; 16 "partiel", dont 3.2 ajouté par
cette phase et 4 déjà présents depuis la Phase 1 sans que ce commentaire ait
été mis à jour). Les 31 autres restent "je ne sais pas" par construction,
cf. `eof_criteria_mapping.py`.
⚠️ Ces chiffres portent sur les 54 critères détaillés et RESTENT justes après
l'ajout de 0.16 au MAPPING le 2026-09-07 : 0.16 est une question du diagnostic
rapide, pas l'un des 54. Le MAPPING compte donc 8 automatisables quand ce
commentaire en annonce 7, et les deux sont exacts dans leur périmètre. Ne pas
"corriger" l'un d'après l'autre.
Les 16 questions de 🏦
0-Diagnostic rapide ne sont JAMAIS remplies automatiquement (échelle 1-5
différente, décision explicite), SAUF 0.16 : elles apparaissent en aperçu,
avec pour 0.4, 0.7, 0.10, 0.11, 0.12 et 0.15 un indice contextuel affiché à
titre indicatif (jamais une réponse cochée).

Usage :
    python3 run_eof.py <source_dir>

Écrit dans <source_dir>/ :
    eof-audit-results.json  - résumé léger, consommé par generate_report_html.py
    eof-rempli.md           - référentiel complet lisible, réponses + provenance + source
    eof-radar-<domaine>.svg - radar des 6 dimensions à deux couches (ce que nous avons
        établi en plein, ce que le service audité a déclaré en hachuré), avec le nombre de
        critères renseignés sous chaque axe et une jauge de ce qui est renseigné en tout.
        Une dimension sans aucune réponse est marquée "aucune réponse", jamais 0 %.
    lots/jugement-automatique.json - la sortie de lot que processus/manifeste-lots.json
        déclare, consommée par processus/fusionner_lots.py et contrôlée par
        processus/valider_sortie_lot.py. N'y figurent que les critères sur lesquels ce lot
        s'est prononcé, jamais les critères sans donnée.
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
from generate_radar_svg import build_radar_from_results  # noqa: E402

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

    Retient au passage le chemin des fichiers RÉELLEMENT trouvés, sous la clé
    `fichiers_charges`. C'est ce qui alimente le champ `entrees` du fichier de lot :
    il doit dire ce qui a été lu, pas ce qui aurait pu l'être. Chemins relatifs à
    source_dir, pour rester justes quand l'audit est rejoué depuis un autre dossier.
    L'ordre des candidats par clé est celui d'avant, il porte la priorité de recherche.
    """
    audit_dir = source_dir / "audit"
    candidats = {
        "env": (source_dir / "env-data.json", audit_dir / "env-data.json"),
        "har": (audit_dir / "har-analysis.json", source_dir / "har-analysis.json"),
        "coverage": (audit_dir / "coverage-analysis.json", source_dir / "coverage-analysis.json"),
        "cwv": (source_dir / "cwv.json", audit_dir / "cwv.json"),
        "headers": (source_dir / "security-headers-analysis.json", audit_dir / "security-headers-analysis.json"),
        "wellknown": (source_dir / "wellknown-scan.json", audit_dir / "wellknown-scan.json"),
        "htmlcss": (source_dir / "html-css-criteria.json", audit_dir / "html-css-criteria.json"),
        "pages_publiques": (source_dir / "pages-publiques-criteria.json", audit_dir / "pages-publiques-criteria.json"),
    }
    trouves = {cle: find_first(*chemins) for cle, chemins in candidats.items()}
    data = {cle: load_json(chemin) for cle, chemin in trouves.items()}
    data["fichiers_charges"] = [
        str(chemin.relative_to(source_dir)) for chemin in trouves.values() if chemin is not None
    ]
    data["source_dir"] = source_dir  # exposé pour deploy_freshness (nécessite le chemin du .har, pas le JSON)
    return data


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
    # La mesure porte sur la page LA PLUS LOURDE de la capture, pas sur la page d'accueil :
    # cf. collect_env_data.py, qui alimente ce champ depuis la variable heaviest.
    return f"Données réellement transférées (page la plus lourde) : {v / 1024:.0f} Ko" if v else None


def context_1_14(data):
    env = data["env"]
    pages = [(p.get("url", "?"), p.get("size_kb")) for p in ((env or {}).get("pages") or []) if p.get("size_kb") is not None]
    if not pages:
        return None
    pages.sort(key=lambda x: -x[1])
    # Omettre la page la plus légère si son poids s'arrondit à 0 (échec de mesure, pas un résultat)
    heaviest = f"{pages[0][0]} ({pages[0][1]:.0f} Ko)"
    if pages[-1][1] >= 0.5:
        lightest = f"{pages[-1][0]} ({pages[-1][1]:.0f} Ko)"
        return f"Page la plus lourde : {heaviest} ; la plus légère : {lightest}"
    else:
        return f"Page la plus lourde : {heaviest}"


def context_1_15(data):
    env = data["env"]
    t = (env or {}).get("traffic") or {}
    v = t.get("visits_per_year")
    if v:
        # Séparateur de milliers français (espace insécable), pas anglais (virgule)
        formatted = f"{v:,}".replace(",", " ")
        return f"Trafic estimé : {formatted} visites/an ({t.get('source', '?')})"
    return None


def context_5_5(data):
    coverage = data["coverage"]
    pages = (coverage or {}).get("pages") or []
    worst = sorted(pages, key=lambda p: -(p.get("js_unused_pct") or 0))[:2]
    if not worst:
        return None
    return " ; ".join(f"{p.get('url', '?')} : JavaScript inutilisé {p.get('js_unused_pct', '?')}%" for p in worst)


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
    return f"Plusieurs composants d'hébergement distincts détectés ({', '.join(paas)}), ce qui suggère une architecture séparant les responsabilités. Nous ne pouvons pas évaluer de l'extérieur l'efficacité de leur couplage ni l'optimisation de leur communication."


def context_2_5(data):
    har = data["har"]
    dups = sorted((har or {}).get("duplicate_urls") or [], key=lambda d: -d.get("count", 0))[:3]
    if not dups:
        return None
    return " ; ".join(f"{d['url']} chargé {d['count']} fois" for d in dups)


# --- Extension Phase 1 (2026-09-03) ---------------------------------------

def context_1_4(data):
    htmlcss = data["htmlcss"]
    pages = (htmlcss or {}).get("pages") or []
    native = sum(p.get("native_buttons") or 0 for p in pages)
    custom = sum(p.get("custom_role_buttons") or 0 for p in pages)
    if native + custom == 0:
        return None
    return f"Boutons HTML natifs détectés : {native} ; boutons avec attribut role='button' : {custom} (sur l'ensemble des pages)"


def context_1_11(data):
    htmlcss = data["htmlcss"]
    css = (htmlcss or {}).get("css")
    if css is None:
        return None
    return ("Règles @media (prefers-reduced-motion ou prefers-color-scheme) détectées dans les feuilles de style"
            if css.get("has_prefers_reduced_or_scheme")
            else "Aucune règle @media (prefers-reduced-motion ou prefers-color-scheme) détectée dans les feuilles de style")


def context_6_1(data):
    headers = data["headers"]
    worst = (headers or {}).get("worst_page")
    if not worst:
        return None
    return f"Score en-têtes de sécurité HTTP : {worst['score_pct']}% (grade {worst['grade']}) sur {worst['url']} - indicateur parmi d'autres de la maturité en production"


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
    return f"Votre service fait appel à {len(all_mut)} service(s) d'infrastructure externe(s) (hébergement, diffusion de contenu, cloud) : {', '.join(all_mut[:5])}{'...' if len(all_mut) > 5 else ''}"


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
    return f"Votre service s'appuie sur une plate-forme d'hébergement ({', '.join(paas)}) capable d'ajuster automatiquement ses ressources. Nous ne pouvons pas voir de l'extérieur si cet ajustement est activé chez vous, ni si votre charge varie assez pour le justifier."


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
    # summarise() rédige déjà son texte pour le service audité : ne pas le retoucher ici
    # par substitution de mots, cela fabrique des phrases incorrectes ("paramètre d'évite
    # la mise en cache"). Toute reformulation se fait dans deploy_freshness.summarise().
    return summarise(info)


def context_6_6(data):
    cwv = data["cwv"]
    headers = data["headers"]
    wellknown = data["wellknown"]
    parts = []
    if cwv:
        bp_scores = [e["best_practices_score_pct"] for e in cwv if e.get("best_practices_score_pct") is not None]
        if bp_scores:
            parts.append(f"Audit Lighthouse - Bonnes Pratiques (pire page) : {min(bp_scores)}%")
    if headers and headers.get("worst_page"):
        parts.append(f"en-têtes de sécurité (pire page) : grade {headers['worst_page']['grade']}")
    if wellknown is not None:
        txt = (wellknown.get("security_txt") or {})
        parts.append(f"fichier security.txt : {'présent et bien formé' if txt.get('well_formed') else ('présent mais mal formé' if txt.get('present') else 'absent')}")
    return " ; ".join(parts) if parts else None


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
        if score == 1 and item_count == 0:
            return "Aucune duplication de code JavaScript détectée par l'audit Lighthouse (score parfait). Cela ne prouve pas que votre gestion des dépendances soit optimale, seulement qu'aucune duplication évidente n'a été repérée."
        elif score is not None:
            return f"Audit Lighthouse de duplication JavaScript : score {score:.2f}, {item_count} élément(s) détecté(s) - indice de duplication potentielle"
        else:
            return "Audit Lighthouse de duplication JavaScript : présent mais sans score (contenu non analysable)"
    return None


def context_3_2(data):
    """Indice de déclaration publique de suivi d'impact environnemental."""
    pages_publiques = data["pages_publiques"]
    if not pages_publiques:
        return None

    status = pages_publiques.get("status")
    if status == "no_directory":
        return None

    if status == "no_files":
        motifs = ", ".join(pages_publiques.get("files_searched", []))
        return f"Aucune page publique d'éco-conception trouvée (motifs cherchés : {motifs})"

    # Compiler toutes les déclarations trouvées
    all_declarations = []

    for file_analysis in pages_publiques.get("files_analyzed", []):
        if not file_analysis.get("read_success"):
            continue
        decl = file_analysis.get("declarations")
        if not decl or not decl.get("parse_success"):
            continue

        all_declarations.extend(decl.get("declarations_suivi", []))

    if not all_declarations:
        return "Page publique d'éco-conception trouvée, mais aucune déclaration de suivi d'impact détectée"

    # Prendre la première déclaration (phrase complète, casse d'origine)
    premiere = all_declarations[0]["phrase"]

    # Si la phrase est très longue (> 200 caractères), couper à une frontière de mot
    if len(premiere) > 200:
        coupe = premiere[:197].rfind(' ')
        if coupe > 100:  # Ne couper que si on garde au moins 100 caractères
            premiere = premiere[:coupe] + "..."

    filename = pages_publiques.get("files_found", ["page publique"])[0]
    return f"Déclaration sur {filename} : \"{premiere}\""


CONTEXTS = {
    "1.9": context_1_9, "1.14": context_1_14,
    "1.15": context_1_15, "1.16": context_1_15,  # même champ trafic
    "5.5": context_5_5, "2.3": context_2_3, "2.5": context_2_5,
    "3.2": context_3_2,
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
    return f"{len(third_party)} domaine(s) tiers détecté(s) lors de la capture (liste observée depuis l'extérieur, ne dit rien de l'architecture technique complète) : {', '.join(third_party)}"


def diag_context_0_10(data):
    wellknown = data["wellknown"]
    sitemap = (wellknown or {}).get("sitemap") or {}
    if not sitemap.get("present") or not sitemap.get("url_count"):
        return None
    import math
    n = sitemap["url_count"]
    return f"{n} URL(s) dans le sitemap (ordre de grandeur logarithmique : environ {math.log2(n):.1f})"


def diag_context_0_7(data):
    """Indice de complexité architecturale (composants d'hébergement/diffusion distincts déclarés au CSP)."""
    headers = data["headers"]
    inv = inventory_from_headers_analysis(headers)
    if not inv:
        return None
    families = inv["familles"]
    paas = families.get("paas_backend") or []
    cdn = families.get("cdn_bibliotheques") or []
    composants = paas + cdn
    if not composants:
        return None
    return (
        f"{len(composants)} composant(s) d'hébergement/diffusion distinct(s) déclaré(s) au CSP "
        f"({', '.join(composants)}), ce qui suggère plusieurs briques séparées plutôt qu'un bloc unique. "
        "Ce n'est qu'un indice indirect et partiel : il ne voit ni le nombre de microservices internes, "
        "ni le couplage réel entre ces briques, ni la complexité fonctionnelle du site."
    )


_CRUX_CATEGORY_RANK = {"SLOW": 2, "AVERAGE": 1, "FAST": 0}


def _cwv_status_rank(entry):
    """0 = 'good', 1 = zone intermédiaire, 2 = 'poor' (mêmes seuils que rule_5_4)."""
    lcp, inp, cls = entry.get("lcp"), entry.get("inp"), entry.get("cls")
    if (lcp is not None and lcp > CWV_POOR["lcp"]) or \
       (inp is not None and inp > CWV_POOR["inp"]) or \
       (cls is not None and cls > CWV_POOR["cls"]):
        return 2
    if not ((lcp is None or lcp <= CWV_GOOD["lcp"]) and
            (inp is None or inp <= CWV_GOOD["inp"]) and
            (cls is None or cls <= CWV_GOOD["cls"])):
        return 1
    return 0


def _cwv_worst_entry(entries):
    if not entries:
        return None
    def sort_key(e):
        return (_cwv_status_rank(e), _CRUX_CATEGORY_RANK.get(e.get("crux_category"), -1))
    return max(entries, key=sort_key)


def _describe_cwv_entry(entry):
    label = entry.get("url") or entry.get("page") or "?"
    strategy = entry.get("strategy") or "?"
    lcp, inp, cls = entry.get("lcp"), entry.get("inp"), entry.get("cls")
    category = entry.get("crux_category")
    bits = []
    if lcp is not None:
        bits.append(f"LCP {lcp}s")
    if inp is not None:
        bits.append(f"INP {inp}ms")
    if cls is not None:
        bits.append(f"CLS {cls}")
    metrics = ", ".join(bits) if bits else "métriques indisponibles"
    cat_txt = f", catégorie CrUX '{category}'" if category else ""
    return f"{label} ({strategy}) : {metrics}{cat_txt}"


def diag_context_0_11(data):
    cwv = data["cwv"]
    if not cwv:
        return None
    worst = _cwv_worst_entry(cwv)
    if worst is None:
        return None
    return (f"Pire page toutes stratégies confondues (Core Web Vitals terrain/lab) : {_describe_cwv_entry(worst)}. "
            "Ce sont des scores techniques de chargement, réactivité et stabilité visuelle, pas une mesure directe du ressenti utilisateur.")


def diag_context_0_12(data):
    cwv = data["cwv"]
    if not cwv:
        return None
    mobile_entries = [e for e in cwv if e.get("strategy") == "mobile"]
    if not mobile_entries:
        return None
    worst = _cwv_worst_entry(mobile_entries)
    if worst is None:
        return None
    return (f"Pire page en stratégie mobile (proxy matériel bas de gamme/ancien) : {_describe_cwv_entry(worst)}. "
            "Le CrUX mobile terrain mélange tous types d'appareils, ce n'est pas une mesure isolée sur du matériel ancien spécifiquement.")


def diag_context_0_15(data):
    """Indice de déclaration publique de rétention/suppression/archivage des données."""
    pages_publiques = data["pages_publiques"]
    if not pages_publiques:
        return None
    if pages_publiques.get("status") in ("no_directory", "no_files"):
        return None

    for file_analysis in pages_publiques.get("files_analyzed", []):
        if not file_analysis.get("read_success"):
            continue
        decl = file_analysis.get("declarations")
        if not decl or not decl.get("parse_success"):
            continue
        retention = decl.get("declarations_retention") or []
        if not retention:
            continue
        phrase = retention[0]["phrase"]
        filename = file_analysis.get("filename", "page publique")
        if len(phrase) > 200:
            coupe = phrase[:197].rfind(" ")
            if coupe > 100:
                phrase = phrase[:coupe] + "..."
        return (
            f"Déclaration sur {filename} : \"{phrase}\". "
            "Une déclaration publique de conservation des données ne prouve pas qu'une politique "
            "formalisée et appliquée existe réellement en interne, ni qu'elle couvre tous les "
            "traitements du service : c'est seulement un indice qu'une politique de suppression et "
            "d'archivage existe potentiellement."
        )
    return None


DIAG_CONTEXTS = {
    "0.4": diag_context_0_4, "0.7": diag_context_0_7, "0.10": diag_context_0_10,
    "0.11": diag_context_0_11, "0.12": diag_context_0_12, "0.15": diag_context_0_15,
}


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


# ---------------------------------------------------------------------------
# Sortie de lot, consommée par processus/fusionner_lots.py
# ---------------------------------------------------------------------------

LOT_ID = "jugement-automatique"

# Les champs que la couche processus refuse dans un fichier de lot : ils viennent du
# référentiel et c'est la fusion qui les rajoute. Cf. FORBIDDEN_FIELDS dans
# processus/valider_sortie_lot.py. Le lot ne dit QUE ce qu'il a jugé.
CHAMPS_DU_LOT = ("reponse", "coefficient", "provenance", "source", "contexte")


def _entree_de_lot(critere_id, categorie, valeurs):
    """Une entrée de lot : `id` et `categorie` toujours, le reste seulement s'il vaut
    quelque chose. Omettre plutôt que poser `null` évite d'écrire un `coefficient: null`
    à côté d'une réponse là où le contrat en exige un non nul, et se relit mieux.
    """
    entree = {"id": critere_id, "categorie": categorie}
    for cle in CHAMPS_DU_LOT:
        if valeurs.get(cle) is not None:
            entree[cle] = valeurs[cle]
    return entree


def build_sortie_lot(results, diag_questions, fichiers_charges, genere_le):
    """Construit ce que ce lot a à dire, au format que processus/valider_sortie_lot.py
    fait respecter : racine à exactement 4 clés, rejet strict de toute autre.

    Ne verse QUE les critères sur lesquels le lot s'est prononcé, c'est-à-dire ceux qui
    portent une réponse ou un contexte. Un critère sans donnée n'est pas une information :
    le taire évite de faire passer 31 silences pour un travail.

    Les questions du diagnostic rapide (préfixe `0.`) ne sont versées que si elles sont au
    MAPPING, donc aujourd'hui la seule 0.16. C'est une question de propriété : l'indice
    contextuel de 0.4 appartient au lot `jugement-diagnostic-rapide`, et il n'a de toute
    façon ni provenance ni source, que le contrat exigerait dès qu'un contexte est posé.
    """
    criteres = []
    for r in results:
        if r["reponse"] is None and not r["contexte"]:
            continue
        criteres.append(_entree_de_lot(r["id"], r["categorie"], r))
    for q in diag_questions:
        entry = MAPPING.get(q["id"])
        if not entry:
            continue
        if q["reponse"] is None and not q["indice_contextuel"]:
            continue
        criteres.append(_entree_de_lot(q["id"], entry["categorie"], {
            "reponse": q["reponse"],
            # Jamais de coefficient sur le diagnostic rapide : le référentiel n'en définit
            # pas pour ses crans, et le validateur le refuse. Ce n'est pas un oubli.
            "coefficient": None,
            "provenance": q["provenance"],
            "source": q["source"],
            "contexte": q["indice_contextuel"],
        }))
    return {
        "lot_id": LOT_ID,
        "genere_le": genere_le,
        "entrees": fichiers_charges,
        "criteres": criteres,
    }


def compute_dimension_scores(criteres_results):
    by_dim = {}
    for c in criteres_results:
        by_dim.setdefault(c["dimension"], []).append(c)
    dimensions = []
    for dim, items in by_dim.items():
        # Identifier les critères écartés (convention critère écarté, section 2)
        ecartes = [c for c in items if c["reponse"] == "🚫 Non applicable"]
        nb_ecartes = len(ecartes)

        # Les critères écartés sortent de tous les dénominateurs (convention 2.1)
        items_retenus = [c for c in items if c["reponse"] != "🚫 Non applicable"]
        answered = [c for c in items_retenus if c["reponse"] is not None]

        # Garde-fou : une dimension entièrement écartée ne doit JAMAIS sortir 0 %
        hors_perimetre = (nb_ecartes == len(items))

        # Formule canonique : somme des potentiels retenus ÷ somme des potentiel_max des critères RETENUS
        # (les critères écartés sont retirés du dénominateur, convention 2.1)
        total_potentiel_max = sum(c["potentiel_max"] for c in items_retenus) or 1e-9
        if hors_perimetre:
            potentiel_optimisation_pct = None
            completude_pct = None
            total = 0
        elif answered:
            potentiel_optimisation_pct = sum(c["coefficient"] * c["potentiel_max"] for c in answered) / total_potentiel_max * 100
            completude_pct = len(answered) / len(items_retenus) * 100 if items_retenus else 0
            total = len(items_retenus)
        else:
            potentiel_optimisation_pct = None
            completude_pct = len(answered) / len(items_retenus) * 100 if items_retenus else 0
            total = len(items_retenus)

        # Comptage par provenance
        # Les 5 provenances de conventions.precedence_provenance, dans l'ordre. `suppose` y
        # figure depuis le 2026-09-07 : sans elle, le test `if prov in ...` juste en dessous
        # jetterait sans un mot une réponse posée en `suppose`. Un compteur à zéro est un
        # renseignement, une réponse perdue n'en est pas un.
        repondus_par_provenance = {"collecte": 0, "estime": 0, "declare": 0, "precise": 0, "suppose": 0}
        for c in answered:
            prov = c.get("provenance")
            if prov in repondus_par_provenance:
                repondus_par_provenance[prov] += 1
        dimensions.append({
            "nom": dim, "potentiel_optimisation_pct": potentiel_optimisation_pct,
            "repondus": len(answered), "total": total,
            "completude_pct": completude_pct,
            "repondus_par_provenance": repondus_par_provenance,
            "ecartes": nb_ecartes,
            "hors_perimetre": hors_perimetre,
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


def autotest():
    """Rejoue les cas de test embarqués sur l'arithmétique du critère écarté."""
    import tempfile

    echecs = []
    total = 0

    # Cas 1 : Dimension entièrement écartée ne doit JAMAIS sortir 0 %
    # POURQUOI 0 serait faux : "🚫 Non applicable" et "✅ Point fort confirmé" partagent le
    # coefficient 0, donc une dimension entièrement écartée affichée à 0 % passerait pour
    # la MIEUX notée du rapport.
    total += 1
    try:
        criteres = [
            {"id": "1.1", "dimension": "🛖 1 — Produit", "potentiel_max": 3.0, "reponse": "🚫 Non applicable", "coefficient": 0},
            {"id": "1.2", "dimension": "🛖 1 — Produit", "potentiel_max": 2.5, "reponse": "🚫 Non applicable", "coefficient": 0},
        ]
        dimensions = compute_dimension_scores(criteres)
        dim = next((d for d in dimensions if d["nom"] == "🛖 1 — Produit"), None)

        if not dim:
            echecs.append(("Dimension entièrement écartée", "dimension non trouvée"))
        elif not dim["hors_perimetre"]:
            echecs.append(("Dimension entièrement écartée", f"hors_perimetre devrait être True, obtenu {dim['hors_perimetre']}"))
        elif dim["potentiel_optimisation_pct"] is not None:
            echecs.append(("Dimension entièrement écartée", f"potentiel_optimisation_pct devrait être None, obtenu {dim['potentiel_optimisation_pct']}"))
        elif dim["potentiel_optimisation_pct"] == 0:
            echecs.append(("Dimension entièrement écartée", "potentiel_optimisation_pct vaut 0 (devrait être None) — POURQUOI 0 EST FAUX : coefficient 0 = aussi bien qu'un ✅ Point fort confirmé"))
        elif dim["completude_pct"] is not None:
            echecs.append(("Dimension entièrement écartée", f"completude_pct devrait être None, obtenu {dim['completude_pct']}"))
        elif dim["total"] != 0:
            echecs.append(("Dimension entièrement écartée", f"total devrait être 0, obtenu {dim['total']}"))
        elif dim["ecartes"] != 2:
            echecs.append(("Dimension entièrement écartée", f"ecartes devrait être 2, obtenu {dim['ecartes']}"))
    except Exception as exc:
        echecs.append(("Dimension entièrement écartée", f"Exception : {exc}"))

    # Cas 2 : Dimension partiellement écartée (chiffres discriminants)
    # Choisir des nombres où l'erreur se verrait : si on COMPTAIT les écartés,
    # le calcul serait DIFFÉRENT.
    # Critères : 2 écartés (potentiel_max 10 chacun), 2 retenus (potentiel_max 5 chacun).
    # Un critère retenu a coefficient 0.5, l'autre 0.2.
    # Potentiel retenu CORRECT : (0.5 * 5 + 0.2 * 5) / 10 = 3.5 / 10 = 35 %
    # Potentiel retenu FAUX (si on comptait les écartés) : 3.5 / 30 = 11.67 %
    total += 1
    try:
        criteres = [
            {"id": "2.1", "dimension": "🗺️ 2 — Architecture", "potentiel_max": 10.0, "reponse": "🚫 Non applicable", "coefficient": 0},
            {"id": "2.2", "dimension": "🗺️ 2 — Architecture", "potentiel_max": 10.0, "reponse": "🚫 Non applicable", "coefficient": 0},
            {"id": "2.3", "dimension": "🗺️ 2 — Architecture", "potentiel_max": 5.0, "reponse": "💡 Potentiel d'amélioration identifié", "coefficient": 0.5, "provenance": "collecte"},
            {"id": "2.4", "dimension": "🗺️ 2 — Architecture", "potentiel_max": 5.0, "reponse": "🤔 À évaluer", "coefficient": 0.2, "provenance": "estime"},
        ]
        dimensions = compute_dimension_scores(criteres)
        dim = next((d for d in dimensions if d["nom"] == "🗺️ 2 — Architecture"), None)

        attendu = 35.0
        faux_calcul = 11.67
        if not dim:
            echecs.append(("Dimension partiellement écartée", "dimension non trouvée"))
        elif dim["potentiel_optimisation_pct"] is None:
            echecs.append(("Dimension partiellement écartée", "potentiel_optimisation_pct est None (devrait être 35.0)"))
        elif abs(dim["potentiel_optimisation_pct"] - attendu) > 0.1:
            echecs.append(("Dimension partiellement écartée", f"potentiel_optimisation_pct attendu {attendu}%, obtenu {dim['potentiel_optimisation_pct']:.2f}% — calcul FAUX donnerait {faux_calcul}%"))
        elif dim["total"] != 2:
            echecs.append(("Dimension partiellement écartée", f"total devrait être 2 (retenus), obtenu {dim['total']}"))
        elif dim["ecartes"] != 2:
            echecs.append(("Dimension partiellement écartée", f"ecartes devrait être 2, obtenu {dim['ecartes']}"))
        elif dim["completude_pct"] is None:
            echecs.append(("Dimension partiellement écartée", "completude_pct est None (devrait être 100.0)"))
        elif abs(dim["completude_pct"] - 100.0) > 0.1:
            echecs.append(("Dimension partiellement écartée", f"completude_pct devrait être 100%, obtenu {dim['completude_pct']:.2f}%"))
    except Exception as exc:
        echecs.append(("Dimension partiellement écartée", f"Exception : {exc}"))

    # Cas 3 : criteres_total = retenus, criteres_total + criteres_ecartes = total référentiel
    total += 1
    try:
        criteres = [
            {"id": "3.1", "dimension": "🏢 3 — Infrastructure", "potentiel_max": 2.0, "reponse": "✅ Point fort confirmé", "coefficient": 0, "provenance": "collecte"},
            {"id": "3.2", "dimension": "🏢 3 — Infrastructure", "potentiel_max": 2.0, "reponse": "🚫 Non applicable", "coefficient": 0},
            {"id": "3.3", "dimension": "🏢 3 — Infrastructure", "potentiel_max": 2.0, "reponse": None, "coefficient": None},
        ]
        dimensions = compute_dimension_scores(criteres)
        dim = next((d for d in dimensions if d["nom"] == "🏢 3 — Infrastructure"), None)

        if not dim:
            echecs.append(("criteres_total comptabilité", "dimension non trouvée"))
        elif dim["total"] != 2:
            echecs.append(("criteres_total comptabilité", f"total (retenus) devrait être 2, obtenu {dim['total']}"))
        elif dim["ecartes"] != 1:
            echecs.append(("criteres_total comptabilité", f"ecartes devrait être 1, obtenu {dim['ecartes']}"))
        elif dim["total"] + dim["ecartes"] != 3:
            echecs.append(("criteres_total comptabilité", f"total + ecartes devrait être 3 (total référentiel), obtenu {dim['total'] + dim['ecartes']}"))
    except Exception as exc:
        echecs.append(("criteres_total comptabilité", f"Exception : {exc}"))

    # Cas 4 : Aucun critère écarté = chiffres identiques à avant session 26, criteres_ecartes == 0
    total += 1
    try:
        criteres = [
            {"id": "4.1", "dimension": "💾 4 — Stockage et données", "potentiel_max": 4.0, "reponse": "💡 Potentiel d'amélioration identifié", "coefficient": 0.5, "provenance": "collecte"},
            {"id": "4.2", "dimension": "💾 4 — Stockage et données", "potentiel_max": 4.0, "reponse": "✅ Point fort confirmé", "coefficient": 0, "provenance": "collecte"},
        ]
        dimensions = compute_dimension_scores(criteres)
        dim = next((d for d in dimensions if d["nom"] == "💾 4 — Stockage et données"), None)

        attendu = 25.0  # (0.5 * 4) / 8 = 25%
        if not dim:
            echecs.append(("Aucun critère écarté", "dimension non trouvée"))
        elif dim["ecartes"] != 0:
            echecs.append(("Aucun critère écarté", f"ecartes devrait être 0, obtenu {dim['ecartes']}"))
        elif dim["potentiel_optimisation_pct"] is None:
            echecs.append(("Aucun critère écarté", "potentiel_optimisation_pct est None (devrait être 25.0)"))
        elif abs(dim["potentiel_optimisation_pct"] - attendu) > 0.1:
            echecs.append(("Aucun critère écarté", f"potentiel_optimisation_pct attendu {attendu}%, obtenu {dim['potentiel_optimisation_pct']:.2f}%"))
        elif dim["total"] != 2:
            echecs.append(("Aucun critère écarté", f"total devrait être 2, obtenu {dim['total']}"))
        elif dim["hors_perimetre"]:
            echecs.append(("Aucun critère écarté", f"hors_perimetre devrait être False, obtenu {dim['hors_perimetre']}"))
    except Exception as exc:
        echecs.append(("Aucun critère écarté", f"Exception : {exc}"))

    if echecs:
        print(f"AUTOTEST EN ÉCHEC : {len(echecs)} cas sur {total}")
        for libelle, erreur in echecs:
            print(f"  - {libelle}")
            print(f"      {erreur}")
        return 1

    print(f"Autotest : {total} cas passés.")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", nargs="?")
    parser.add_argument("--domaine", default=None, help="Nom court utilisé pour eof-radar-<domaine>.svg (déduit du dossier sinon)")
    parser.add_argument("--autotest", action="store_true", help="rejoue les cas de test embarqués et sort 1 si un cas échoue")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())

    if not args.source_dir:
        parser.error("source_dir est requis (ou utiliser --autotest)")

    source_dir = Path(args.source_dir).resolve()

    source_dir = Path(args.source_dir).resolve()
    domaine = args.domaine or source_dir.name

    if not REFERENTIEL_PATH.exists():
        print(f"ERREUR : référentiel introuvable ({REFERENTIEL_PATH}). Lancer le skill eof d'abord.")
        sys.exit(1)
    referentiel = json.loads(REFERENTIEL_PATH.read_text(encoding="utf-8"))

    data = load_audit_data(source_dir)
    # Clés de données réelles (exclut source_dir, qui est toujours non-None)
    data_keys = ("env", "har", "coverage", "cwv", "headers", "wellknown", "htmlcss", "pages_publiques")
    if not any(data[k] for k in data_keys):
        print("⚠ Aucune donnée d'audit trouvée (env-data.json / har-analysis.json / coverage-analysis.json / "
              "cwv.json / security-headers-analysis.json / wellknown-scan.json / html-css-criteria.json / "
              "pages-publiques-criteria.json) — tous les critères resteront 'je ne sais pas'.")

    results = [evaluate_criterion(c, data) for c in referentiel["criteres"]]
    results_by_id = {r["id"]: r for r in results}
    dimensions = compute_dimension_scores(results)
    diag_rapide_apercu = build_diag_rapide_apercu(referentiel, data)

    # Identifier les critères écartés (convention critère écarté, section 2)
    ecartes_global = [r for r in results if r["reponse"] == "🚫 Non applicable"]
    criteres_ecartes = len(ecartes_global)

    # Les critères écartés sortent de tous les dénominateurs (convention 2.1)
    results_retenus = [r for r in results if r["reponse"] != "🚫 Non applicable"]

    auto_answered = [r for r in results_retenus if r["categorie"] == "automatisable" and r["reponse"] is not None]
    all_answered = [r for r in results_retenus if r["reponse"] is not None]
    partiel_with_context = [r for r in results_retenus if r["categorie"] == "partiel" and r["contexte"] is not None]

    # Calcul global : même formule que par dimension, appliquée aux critères RETENUS
    # (les critères écartés sont retirés du dénominateur, convention 2.1)
    total_potentiel_max_global = sum(r["potentiel_max"] for r in results_retenus) or None
    potentiel_optimisation_global_pct = (
        sum(r["coefficient"] * r["potentiel_max"] for r in all_answered) / total_potentiel_max_global * 100
        if total_potentiel_max_global else None
    )
    completude_globale_pct = len(all_answered) / len(results_retenus) * 100 if results_retenus else 0
    # Comptage par provenance global — mêmes 5 provenances qu'en compute_dimension_scores(),
    # `suppose` comprise, sinon une réponse posée en `suppose` disparaîtrait du décompte.
    repondus_par_provenance = {"collecte": 0, "estime": 0, "declare": 0, "precise": 0, "suppose": 0}
    for r in all_answered:
        prov = r.get("provenance")
        if prov in repondus_par_provenance:
            repondus_par_provenance[prov] += 1

    # Un seul horodatage pour les deux artefacts : le fichier de lot et le résumé d'audit
    # sortent du même passage, deux instants différents laisseraient croire le contraire.
    genere_le = datetime.now(timezone.utc).isoformat()

    audit_results = {
        "generated_at": genere_le,
        "domaine": domaine,
        "criteres_total": len(results_retenus),
        "criteres_repondus": len(all_answered),
        "criteres_ecartes": criteres_ecartes,
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

    # Radar à deux couches, construit depuis le résultat d'audit lui-même et non
    # depuis les variables locales de ce script : c'est le même point d'entrée que
    # celui de `processus/fusionner_lots.py`, l'autre producteur du même fichier.
    # Les deux tenaient déjà deux arithmétiques jumelles ; leur laisser deux façons
    # de dessiner garantissait qu'un jour l'une montrerait autre chose que l'autre.
    radar_path = source_dir / f"eof-radar-{domaine}.svg"
    radar_path.write_text(build_radar_from_results(audit_results, domaine), encoding="utf-8")

    md_text = build_eof_rempli_md(referentiel, results_by_id, dimensions, diag_rapide_apercu)
    md_path = source_dir / "eof-rempli.md"
    md_path.write_text(md_text, encoding="utf-8")

    sortie_lot = build_sortie_lot(results, diag_rapide_apercu, data["fichiers_charges"], genere_le)
    lot_dir = source_dir / "lots"
    lot_dir.mkdir(parents=True, exist_ok=True)
    lot_path = lot_dir / f"{LOT_ID}.json"
    lot_path.write_text(json.dumps(sortie_lot, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"eof-audit-results.json écrit : {results_path}")
    print(f"eof-rempli.md écrit : {md_path}")
    print(f"eof-radar-{domaine}.svg écrit : {radar_path}")
    print(f"lots/{LOT_ID}.json écrit : {lot_path} ({len(sortie_lot['criteres'])} critères)")
    # Le potentiel est rapporté à TOUS les critères, pas aux seuls répondus : sans la
    # complétude affichée juste à côté, un chiffre bas se lit comme un service mature
    # alors qu'il ne dit que "nous n'avons presque rien regardé".
    print(f"Critères répondus automatiquement : {len(auto_answered)}/{len(referentiel['criteres'])}"
          f" (complétude {completude_globale_pct:.1f} %)"
          + (f" — potentiel d'optimisation global, rapporté aux {len(referentiel['criteres'])} critères :"
             f" {potentiel_optimisation_global_pct:.2f} %" if potentiel_optimisation_global_pct is not None else ""))


if __name__ == "__main__":
    main()
