#!/usr/bin/env python3
"""Remplit automatiquement ce qui peut l'être du référentiel EOF pour un
site audité, à partir UNIQUEMENT de `eof-referentiel.json` (produit par le
skill `eof`) et des données déjà collectées par `analyse-parcours`
(`env-data.json`, `audit/har-analysis.json`, `audit/coverage-analysis.json`,
`cwv.json`). Ne lit JAMAIS la Google Sheet ni le Markdown humain — c'est le
découplage voulu entre "synchroniser le référentiel" et "auditer un site"
(cf. plan d'architecture, `tmp/handoff.md`).

Sur les 54 critères détaillés (6 dimensions), une reconnaissance manuelle a
montré que seuls 10 sont exploitables depuis les données d'audit existantes
(4 "automatisable" avec case cochée, 6 "partiel" avec indice contextuel
jamais coché) — les 44 autres restent "je ne sais pas" par construction,
cf. `eof_criteria_mapping.py`. Les 16 questions de 🏦 0-Diagnostic rapide ne
sont JAMAIS remplies automatiquement (échelle 1-5 différente, décision
explicite) : elles apparaissent seulement en aperçu.

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
    return env, har, coverage, cwv


# ---------------------------------------------------------------------------
# Règles "automatisable" : retournent (reponse, confidence, source) ou (None, None, motif)
# ---------------------------------------------------------------------------

def rule_1_12(env, har, coverage, cwv):
    categories = ((env or {}).get("tech_stack") or {}).get("categories") or {}
    analytics = categories.get("Analytics")
    tp_share = ((env or {}).get("har_summary") or {}).get("efootprint", {}).get("third_party_share")
    if not analytics:
        return "✅ Point fort confirmé", "medium", "env-data.json: tech_stack.categories — aucune techno 'Analytics' détectée"
    extra = f", third_party_share={tp_share:.1%}" if tp_share is not None else ""
    return ("💡 Potentiel d'amélioration identifié", "medium",
            f"env-data.json: tech_stack.categories['Analytics'] = {', '.join(analytics)}{extra}")


def rule_2_1(env, har, coverage, cwv):
    ai = (env or {}).get("ai_external_apis") or {}
    techs = ((env or {}).get("tech_stack") or {}).get("technologies") or []
    flagged = [t["name"] for t in techs if t.get("category", "").lower() in ("ia", "intelligence artificielle", "blockchain")]
    if not ai and not flagged:
        return "✅ Point fort confirmé", "medium", "env-data.json: ai_external_apis vide, aucune techno IA/blockchain détectée"
    detail = list(ai.keys()) + flagged
    return "💡 Potentiel d'amélioration identifié", "medium", f"env-data.json: ai_external_apis/tech_stack = {detail}"


def rule_3_3(env, har, coverage, cwv):
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


def rule_5_4(env, har, coverage, cwv):
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


RULES = {"1.12": rule_1_12, "2.1": rule_2_1, "3.3": rule_3_3, "5.4": rule_5_4}


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


def rule_diag_0_16(env, crans):
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

def context_1_9(env, har, coverage, cwv):
    v = ((env or {}).get("har_summary") or {}).get("efootprint", {}).get("data_transferred_bytes_real")
    return f"Poids réel transféré (page repère) : {v / 1024:.0f} Ko" if v else None


def context_1_14(env, har, coverage, cwv):
    pages = [(p.get("url", "?"), p.get("size_kb")) for p in ((env or {}).get("pages") or []) if p.get("size_kb") is not None]
    if not pages:
        return None
    pages.sort(key=lambda x: -x[1])
    return f"Page la plus lourde : {pages[0][0]} ({pages[0][1]:.0f} Ko) ; la plus légère : {pages[-1][0]} ({pages[-1][1]:.0f} Ko)"


def context_1_15(env, har, coverage, cwv):
    t = (env or {}).get("traffic") or {}
    v = t.get("visits_per_year")
    return f"Trafic estimé : {v:,} visites/an ({t.get('source', '?')})" if v else None


def context_5_5(env, har, coverage, cwv):
    pages = (coverage or {}).get("pages") or []
    worst = sorted(pages, key=lambda p: -(p.get("js_unused_pct") or 0))[:2]
    if not worst:
        return None
    return "; ".join(f"{p.get('url', '?')} : JS inutilisé {p.get('js_unused_pct', '?')}%" for p in worst)


def context_2_5(env, har, coverage, cwv):
    dups = sorted((har or {}).get("duplicate_urls") or [], key=lambda d: -d.get("count", 0))[:3]
    if not dups:
        return None
    return "; ".join(f"{d['url']} ×{d['count']}" for d in dups)


CONTEXTS = {
    "1.9": context_1_9, "1.14": context_1_14,
    "1.15": context_1_15, "1.16": context_1_15,  # même champ trafic
    "5.5": context_5_5, "2.5": context_2_5,
}


# ---------------------------------------------------------------------------
# Évaluation d'un critère
# ---------------------------------------------------------------------------

def evaluate_criterion(crit, env, har, coverage, cwv):
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
        reponse, confidence, source = rule(env, har, coverage, cwv) if rule else (None, None, "règle non implémentée")
        result["source"] = source
        if reponse is not None:
            result["reponse"] = reponse
            result["score"] = crit["options_evaluation_score"].get(reponse)
            result["confidence"] = confidence
    elif entry["categorie"] == "partiel":
        ctx_fn = CONTEXTS.get(crit["id"])
        contexte = ctx_fn(env, har, coverage, cwv) if ctx_fn else None
        if contexte:
            result["contexte"] = contexte
            result["confidence"] = entry["confidence_max"]
            result["source"] = entry["champ_donnee"]
    return result


def build_diag_rapide_apercu(referentiel, env):
    questions = []
    for q in referentiel["diagnostic_rapide"]:
        entry = {"id": q["id"], "critere": q["critere"], "niveau_impact": q["niveau_impact"],
                 "reponse": None, "confidence": None, "source": None}
        if q["id"] == "0.16":
            reponse, confidence, source = rule_diag_0_16(env, q["crans"])
            if reponse is not None:
                entry.update(reponse=reponse, confidence=confidence, source=source)
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

    env, har, coverage, cwv = load_audit_data(source_dir)
    if not any((env, har, coverage, cwv)):
        print("⚠ Aucune donnée d'audit trouvée (env-data.json / har-analysis.json / coverage-analysis.json / cwv.json) "
              "— tous les critères resteront 'je ne sais pas'.")

    results = [evaluate_criterion(c, env, har, coverage, cwv) for c in referentiel["criteres"]]
    results_by_id = {r["id"]: r for r in results}
    dimensions = compute_dimension_scores(results)
    diag_rapide_apercu = build_diag_rapide_apercu(referentiel, env)

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
