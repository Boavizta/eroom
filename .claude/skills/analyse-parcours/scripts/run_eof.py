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
    eof-rempli.md           - référentiel complet lisible, réponses + confidence + source
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
    }


# ---------------------------------------------------------------------------
# Règles "automatisable" : retournent (reponse, confidence, source) ou (None, None, motif)
# ---------------------------------------------------------------------------

def rule_1_12(data):
    env = data["env"]
    categories = ((env or {}).get("tech_stack") or {}).get("categories") or {}
    analytics = categories.get("Analytics")
    tp_share = ((env or {}).get("har_summary") or {}).get("efootprint", {}).get("third_party_share")
    if not analytics:
        return "✅ Point fort confirmé", "medium", "env-data.json: tech_stack.categories — aucune techno 'Analytics' détectée"
    extra = f", third_party_share={tp_share:.1%}" if tp_share is not None else ""
    return ("💡 Potentiel d'amélioration identifié", "medium",
            f"env-data.json: tech_stack.categories['Analytics'] = {', '.join(analytics)}{extra}")


def rule_2_1(data):
    env = data["env"]
    ai = (env or {}).get("ai_external_apis") or {}
    techs = ((env or {}).get("tech_stack") or {}).get("technologies") or []
    flagged = [t["name"] for t in techs if t.get("category", "").lower() in ("ia", "intelligence artificielle", "blockchain")]
    if not ai and not flagged:
        return "✅ Point fort confirmé", "medium", "env-data.json: ai_external_apis vide, aucune techno IA/blockchain détectée"
    detail = list(ai.keys()) + flagged
    return "💡 Potentiel d'amélioration identifié", "medium", f"env-data.json: ai_external_apis/tech_stack = {detail}"


def rule_3_3(data):
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
        return "💡 Potentiel d'amélioration identifié", "high", f"env-data.json: servers[] = {detail} (seuil {seuil} gCO2/kWh dépassé)"
    return "✅ Point fort confirmé", "high", f"env-data.json: servers[] = {detail} (sous le seuil {seuil} gCO2/kWh)"


def rule_5_4(data):
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
        return "💡 Potentiel d'amélioration identifié", "high", f"cwv.json: page(s) en zone 'poor' : {', '.join(sorted(set(poor_pages)))}"
    if all_good:
        return "✅ Point fort confirmé", "high", "cwv.json: toutes les pages sous les seuils CWV 'good'"
    return "🤔 À évaluer", "high", "cwv.json: zone intermédiaire ('needs improvement'), aucune page 'poor'"


# --- Extension Phase 1 (2026-09-03) ---------------------------------------

def rule_1_5(data):
    htmlcss = data["htmlcss"]
    pages = (htmlcss or {}).get("pages")
    if not pages:
        return None, None, "html-css-criteria.json absent"
    offenders = [p["url"] for p in pages if p.get("has_autoplay_media")]
    if offenders:
        return "💡 Potentiel d'amélioration identifié", "high", f"html-css-criteria.json: autoplay détecté sur {offenders}"
    return "✅ Point fort confirmé", "high", "html-css-criteria.json: aucune balise <video|audio autoplay> détectée sur les pages auditées"


def rule_1_6(data):
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
        return "✅ Point fort confirmé", "medium", source
    if not has_any_adaptive_img and not has_media_queries:
        return "💡 Potentiel d'amélioration identifié", "medium", source
    return "🤔 À évaluer", "medium", source + " (signaux discordants entre pages/CSS, contrainte déterministe : ne pas trancher)"


def rule_1_13(data):
    cwv = data["cwv"]
    if not cwv:
        return None, None, "cwv.json absent"
    scores = [e["accessibility_score_pct"] for e in cwv if e.get("accessibility_score_pct") is not None]
    if not scores:
        return None, None, "cwv.json: aucun accessibility_score_pct disponible"
    worst = min(scores)
    source = f"cwv.json: accessibility_score_pct (PageSpeed Insights) — pire page/stratégie = {worst}, valeurs = {scores}"
    if worst < 60:
        return "💡 Potentiel d'amélioration identifié", "high", source
    if worst >= 90:
        return "✅ Point fort confirmé", "high", source
    return "🤔 À évaluer", "high", source + " (zone 60-90, ambigu)"


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
# cran 1 avec confidence dégradée à "medium" au lieu de "high", pour ne pas
# prétendre à une précision que l'échelle source n'a pas à cet endroit.
_CARBON_BUCKETS = [(100, 5), (200, 4), (300, 3), (500, 2)]


def rule_diag_0_16(data, crans):
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
    confidence = "medium" if (worst_rank == 1 and worst_value <= 750) else "high"
    reponse = next((c for c in crans if c.strip().startswith(f"{worst_rank}")), crans[worst_rank - 1] if len(crans) >= worst_rank else None)
    source = f"env-data.json: servers[].carbon_intensity_g_kwh = {worst_value} gCO2e/kWh (doublon de 3.3, même donnée)"
    return reponse, confidence, source


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


def context_6_3(data):
    wellknown = data["wellknown"]
    parts = []
    sitemap = (wellknown or {}).get("sitemap") or {}
    if sitemap.get("present") and sitemap.get("days_since_lastmod") is not None:
        parts.append(f"sitemap.xml mis à jour il y a {sitemap['days_since_lastmod']} jour(s)")
    elif wellknown is not None:
        parts.append("sitemap.xml absent ou sans <lastmod>")
    return "; ".join(parts) if parts else None


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


CONTEXTS = {
    "1.9": context_1_9, "1.14": context_1_14,
    "1.15": context_1_15, "1.16": context_1_15,  # même champ trafic
    "5.5": context_5_5, "2.5": context_2_5,
    "1.4": context_1_4, "1.11": context_1_11,
    "6.1": context_6_1, "6.3": context_6_3, "6.6": context_6_6,
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
        "poids": crit["poids"], "categorie": "aucune_donnee",
        "reponse": None, "score": None, "confidence": None, "source": None, "contexte": None,
    }
    if not entry:
        return result

    result["categorie"] = entry["categorie"]
    if entry["categorie"] == "automatisable":
        rule = RULES.get(crit["id"])
        reponse, confidence, source = rule(data) if rule else (None, None, "règle non implémentée")
        result["source"] = source
        if reponse is not None:
            result["reponse"] = reponse
            result["score"] = crit["options_evaluation_score"].get(reponse)
            result["confidence"] = confidence
    elif entry["categorie"] == "partiel":
        ctx_fn = CONTEXTS.get(crit["id"])
        contexte = ctx_fn(data) if ctx_fn else None
        if contexte:
            result["contexte"] = contexte
            result["confidence"] = entry["confidence_max"]
            result["source"] = entry["champ_donnee"]
    return result


def build_diag_rapide_apercu(referentiel, data):
    questions = []
    for q in referentiel["diagnostic_rapide"]:
        entry = {"id": q["id"], "critere": q["critere"], "niveau_impact": q["niveau_impact"],
                 "reponse": None, "confidence": None, "source": None, "indice_contextuel": None}
        if q["id"] == "0.16":
            reponse, confidence, source = rule_diag_0_16(data, q["crans"])
            if reponse is not None:
                entry.update(reponse=reponse, confidence=confidence, source=source)
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
        if answered:
            total_poids = sum(c["poids"] for c in answered) or 1e-9
            score_pct = sum(c["score"] * c["poids"] for c in answered) / total_poids * 100
        else:
            score_pct = None
        dimensions.append({
            "nom": dim, "score_pct": score_pct,
            "repondus": len(answered), "total": len(items),
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
                f"_(automatique, confidence {q['confidence']} — {q['source']})_"
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
            score_txt = f"{dim_info['score_pct']:.0f}%" if dim_info["score_pct"] is not None else "sans donnée"
            lines.append(f"\n## {current_dim} — potentiel d'optimisation : {score_txt} ({dim_info['repondus']}/{dim_info['total']} répondus)\n")
        lines.append(f"### {crit['id']} — {crit['critere']}\n")
        if r["reponse"]:
            lines.append(f"**Réponse (automatique)** : {r['reponse']}")
            lines.append(f"**Confidence** : {r['confidence']} — **Source** : {r['source']}")
        elif r["contexte"]:
            lines.append("**Réponse** : je ne sais pas (aucune règle assez fiable pour trancher)")
            lines.append(f"**Donnée indicative** ({r['confidence']}) : {r['contexte']} — _champ : {r['source']}_")
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
    if not any(data.values()):
        print("⚠ Aucune donnée d'audit trouvée (env-data.json / har-analysis.json / coverage-analysis.json / "
              "cwv.json / security-headers-analysis.json / wellknown-scan.json / html-css-criteria.json) "
              "— tous les critères resteront 'je ne sais pas'.")

    results = [evaluate_criterion(c, data) for c in referentiel["criteres"]]
    results_by_id = {r["id"]: r for r in results}
    dimensions = compute_dimension_scores(results)
    diag_rapide_apercu = build_diag_rapide_apercu(referentiel, data)

    auto_answered = [r for r in results if r["categorie"] == "automatisable" and r["reponse"] is not None]
    partiel_with_context = [r for r in results if r["categorie"] == "partiel" and r["contexte"] is not None]
    total_poids_answered = sum(r["poids"] for r in auto_answered) or None
    potentiel_global_pct = (
        sum(r["score"] * r["poids"] for r in auto_answered) / total_poids_answered * 100
        if total_poids_answered else None
    )

    # Radar : une valeur par dimension, None si aucune réponse (jamais un faux 0%)
    axes = [(d["nom"], d["score_pct"]) for d in dimensions]
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
        "criteres_repondus_auto": len(auto_answered),
        "criteres_avec_indice_partiel": len(partiel_with_context),
        "potentiel_optimisation_global_pct": potentiel_global_pct,
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
    print(f"Critères répondus automatiquement : {len(auto_answered)}/{len(referentiel['criteres'])}"
          + (f" — potentiel d'optimisation global (sur ces réponses) : {potentiel_global_pct:.0f}%" if potentiel_global_pct is not None else ""))


if __name__ == "__main__":
    main()
