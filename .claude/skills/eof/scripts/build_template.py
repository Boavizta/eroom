#!/usr/bin/env python3
"""Construit le template Markdown vierge du référentiel EOF-V.1.1 (EROOM
Optimization Framework) à partir des données brutes récupérées via gviz
(un fichier JSON par onglet, cf. fetch_gviz.py).

Ce script ne fait AUCUN calcul de potentiel d'optimisation : le template produit est vierge
(toutes les listes à cocher sont décochées). Seule la méthode de calcul est
documentée en texte, pour que le fichier reste auto-suffisant et
recalculable à la main plus tard (cf. section "Comment ce référentiel se
lit" en tête du document).

Usage :
    python3 build_template.py <dossier_json> <fichier_markdown_sortie>
"""
import json
import re
import sys
import os

PILLAR_TABS = [
    ("produit", "🛖 1 — Produit"),
    ("architecture", "🗺️ 2 — Architecture"),
    ("infrastructure", "🏢 3 — Infrastructure"),
    ("stockage", "💾 4 — Stockage et données"),
    ("algo-code", "👨‍💻 5 — Algo & Code"),
    ("facilite", "🛠 6 — Facilité de changement"),
]

# Ordre de LECTURE du template vierge (sommaire + corps), distinct de
# PILLAR_TABS ci-dessus : 0 - Diagnostic rapide (avant, hors liste) → 6 -
# Facilité de changement en premier (préalable pratique : est-il seulement
# possible d'agir ?) → puis 1,2,3,4,5 dans l'ordre du référentiel. Ne
# s'applique qu'à ce fichier de sortie humain : PILLAR_TABS et
# build_referentiel_json() gardent l'ordre canonique 1..6 (consommé par
# run_eof.py côté eof-audit/analyse-parcours, hors scope de ce changement).
PILLAR_TABS_TEMPLATE_ORDER = [PILLAR_TABS[5]] + PILLAR_TABS[0:5]

# Dropdown observé sur les onglets dimensions (5 valeurs, cf. relevé empirique
# sur les 6 onglets). Correspondance numérique observée (coefficient avant
# pondération par le maximum de potentiel) :
#   ✅ Point fort confirmé              -> 0  (rien à optimiser)
#   💡 Potentiel d'amélioration identifié -> 1  (levier identifié)
#   🚫 Non applicable                    -> 0  (exclu, compte quand même dans le maximum de potentiel total)
#   🤔 À évaluer                         -> 0  (pas encore regardé)
#   ⌛️ Évaluation en cours               -> 0,5 (UNE seule occurrence observée dans
#                                              tout le classeur au moment de la
#                                              génération, à confirmer si le
#                                              cas se représente, pas encore
#                                              une règle certaine)
PILLAR_EVAL_OPTIONS = [
    ("✅ Point fort confirmé", 0),
    ("💡 Potentiel d'amélioration identifié", 1),
    ("🚫 Non applicable", 0),
    ("🤔 À évaluer", 0),
    ("⌛️ Évaluation en cours", 0.5),
]

# Onglet 6 (Facilité de changement) seul : dropdown DIFFÉRENT des 5 autres
# dimensions, confirmé par le texte de l'onglet "À LIRE" (Étape 6). Mapping
# numérique non observé dans des cellules réelles (onglet encore vide au
# moment de la génération), à confirmer le jour où des réponses existeront.
FACILITE_EVAL_OPTIONS = [
    ("🟢 Facile à modifier", 0),
    ("🟡 Effort modéré", 0.5),
    ("🔴 Difficile à changer", 1),
]

DIAG_RAPIDE_NIVEAUX = ["Modéré", "Significatif", "Déterminant"]

# 3 liens hypertexte du Sheet source (récupérés depuis les relations du
# fichier Excel fourni, car l'API gviz ne renvoie que le texte affiché, pas
# la cible du lien). Les coordonnées de cellule exactes ont bougé depuis
# (des critères ont été ajoutés) — on relie donc la PREMIÈRE occurrence du
# mot dans l'onglet concerné, ce qui atteint le même but (rendre le terme
# navigable) sans dépendre d'une référence de cellule devenue obsolète.
TAB_HYPERLINKS = {
    "diag-rapide": ("SLA", "https://fr.wikipedia.org/wiki/Service-level_agreement"),
    "algo-code": ("Core Web Vitals", "https://developers.google.com/search/docs/appearance/core-web-vitals?hl=fr"),
    "facilite": ("CI/CD", "https://fr.wikipedia.org/wiki/CI/CD"),
}


def apply_hyperlink(text, tab_name):
    if tab_name not in TAB_HYPERLINKS:
        return text
    word, url = TAB_HYPERLINKS[tab_name]
    pattern = re.compile(re.escape(word))
    return pattern.sub(f"[{word}]({url})", text, count=1)


def load_tab(json_dir, name):
    raw = open(os.path.join(json_dir, f"{name}.json"), encoding="utf-8").read()
    m = re.search(r"setResponse\((.*)\);?\s*$", raw, re.S)
    return json.loads(m.group(1))["table"]["rows"]


def cell(row, idx):
    if idx >= len(row["c"]) or row["c"][idx] is None:
        return None
    c = row["c"][idx]
    v = c.get("f", c.get("v"))
    if isinstance(v, str):
        v = v.strip()
    return v if v not in ("", None) else None


def is_id(v):
    return bool(v) and re.match(r"^\d+\.\d+$", str(v))


def checklist(options, checked=None):
    lines = []
    for opt in options:
        mark = "x" if opt == checked else " "
        lines.append(f"- [{mark}] {opt}")
    return "\n".join(lines)


def build_diag_rapide(json_dir):
    rows = load_tab(json_dir, "diag-rapide")
    out = ["## 🏦 0 — Diagnostic rapide\n"]
    out.append(
        "*Identifiez les meilleures opportunités d'optimisation. Un score plus "
        "élevé reflète un potentiel d'optimisation plus important.*\n"
    )
    for r in rows:
        crit_id = cell(r, 1)
        if not is_id(crit_id):
            continue
        critere = cell(r, 2)
        methode = cell(r, 4)  # texte des 5 crans, enumeré "1 - ... \n2 - ..."
        niveau = cell(r, 5)
        out.append(f"### {crit_id} — {critere}\n")
        out.append("**Évaluation**")
        if methode:
            crans = [c.strip() for c in methode.split("\n") if c.strip()]
            for c in crans:
                out.append(f"- [ ] {c}")
        out.append("")
        out.append("**Niveau d'impact**")
        out.append(checklist(DIAG_RAPIDE_NIVEAUX, checked=niveau))
        out.append("")
    return "\n".join(out)


def build_pillar(json_dir, tab_name, title):
    rows = load_tab(json_dir, tab_name)
    eval_options = FACILITE_EVAL_OPTIONS if tab_name == "facilite" else PILLAR_EVAL_OPTIONS
    out = [f"## {title}\n"]
    # ligne 1 (index 1 dans les rows) porte la description courte de la dimension
    if len(rows) > 1:
        desc = cell(rows[1], 2)
        if desc:
            out.append(f"*{desc}*\n")
    for r in rows:
        crit_id = cell(r, 1)
        if not is_id(crit_id):
            continue
        critere = cell(r, 2)
        explication = cell(r, 3)
        niveau = cell(r, 6)
        out.append(f"### {crit_id} — {critere}\n")
        if explication:
            out.append(f"**Explication supplémentaire** : {explication}\n")
        out.append("**Évaluation**")
        out.append(checklist([o for o, _ in eval_options]))
        out.append("")
        out.append("**Niveau d'impact**")
        out.append(checklist(DIAG_RAPIDE_NIVEAUX, checked=niveau))
        out.append("")
    return "\n".join(out)


def parse_potentiel_max(v):
    if v is None:
        return None
    return float(str(v).replace(",", "."))


def build_diag_rapide_json(json_dir):
    """Liste structurée des 16 questions de l'onglet 0-Diagnostic rapide,
    pour affichage en aperçu (topo) uniquement — échelle 1-5 différente des
    6 dimensions détaillées, jamais remplie automatiquement par `eof-audit`,
    jamais mêlée à la liste `criteres` (54) ni à son radar."""
    rows = load_tab(json_dir, "diag-rapide")
    out = []
    for r in rows:
        crit_id = cell(r, 1)
        if not is_id(crit_id):
            continue
        methode = cell(r, 4)
        crans = [c.strip() for c in methode.split("\n") if c.strip()] if methode else []
        out.append({
            "id": crit_id,
            "critere": cell(r, 2),
            "crans": crans,
            "niveau_impact": cell(r, 5),
        })
    return out


def build_referentiel_json(json_dir):
    """Construit la table structurée du référentiel :
    - `criteres` : les 54 critères détaillés (6 dimensions), ceux que lit
      `eof-audit` pour remplir automatiquement et calculer le radar.
    - `diagnostic_rapide` : les 16 questions de l'onglet 0, pour un aperçu
      seulement (échelle différente, jamais remplies automatiquement — cf.
      section "Comment ce référentiel se lit").
    C'est ce fichier, et lui seul, que le futur processus `eof-audit` doit
    lire : jamais la Google Sheet, jamais le Markdown humain.
    """
    criteres = []
    for key, title in PILLAR_TABS:
        rows = load_tab(json_dir, key)
        eval_options = FACILITE_EVAL_OPTIONS if key == "facilite" else PILLAR_EVAL_OPTIONS
        for r in rows:
            crit_id = cell(r, 1)
            if not is_id(crit_id):
                continue
            criteres.append({
                "id": crit_id,
                "pilier": title,
                "critere": cell(r, 2),
                "explication": cell(r, 3),
                "methode": cell(r, 5),
                "niveau_impact": cell(r, 6),
                "potentiel_max": parse_potentiel_max(cell(r, 9)),
                "options_evaluation": [o for o, _ in eval_options],
                "options_evaluation_coefficient": {o: s for o, s in eval_options},
            })
    return {"criteres": criteres, "diagnostic_rapide": build_diag_rapide_json(json_dir)}


def build_a_lire(json_dir):
    rows = load_tab(json_dir, "a-lire")
    out = ["## 📖 À lire\n"]
    out.append("![Logo Boavizta](logo1.png) ![Licence CC BY-SA](logo2.png)\n")
    out.append(
        "> ⚠️ Le logo Boavizta (`logo1.png`) est en blanc sur fond transparent : "
        "il ne s'affiche pas sur un rendu Markdown à fond blanc (GitHub, VS Code, "
        "la plupart des visionneuses). Visible seulement sur fond sombre, ou en "
        "ouvrant le fichier directement. Non corrigé ici (retouche graphique hors "
        "périmètre) — signalé pour ne pas laisser croire à une image manquante.\n"
    )
    for r in rows:
        txt = cell(r, 1)
        if txt:
            if txt.startswith(("🎯", "📊", "🧮", "💡")) and len(txt) < 60:
                out.append(f"### {txt}\n")
            else:
                out.append(f"{txt}\n")
    return "\n".join(out)


def build_synthese(json_dir, criteria_counts):
    categories = [
        "🛖 Produit", "🗺️ Architecture", "🏢 Infrastructure",
        "💾 Stockage & Données", "👨‍💻 Algo & Code", "🛠 Facilité de changement",
    ]
    total = sum(criteria_counts.values())
    out = ["## 🕸️ 7 — Synthèse\n"]
    out.append(
        "Ce référentiel compte **{} critères détaillés** au total, répartis sur "
        "les 6 dimensions ci-dessous (hors Diagnostic rapide, qui les recouvre en "
        "version condensée mais n'entre pas dans cette synthèse).\n".format(total)
    )
    out.append("| Catégorie | Nombre de critères | Renvoi |")
    out.append("|---|---|---|")
    keys = ["produit", "architecture", "infrastructure", "stockage", "algo-code", "facilite"]
    for cat, key in zip(categories, keys):
        anchor = cat.split(" ", 1)[1].lower().replace(" ", "-").replace("&", "")
        out.append(f"| {cat} | {criteria_counts[key]} | [Voir la section](#{anchor}) |")
    out.append("")
    out.append(
        "**Note sur le total du Sheet source.** La formule Google Sheets qui "
        "compte le nombre total de critères référence des onglets qui n'existent "
        "plus (`#REF!` + anciens noms d'onglets) — sa valeur affichée est figée et "
        "fausse. Le total ci-dessus ({}) est recompté directement depuis les "
        "données actuelles, un par un.\n".format(total)
    )
    out.append(
        "**Radar.** Le Sheet source affiche un radar à 6 axes qui, à l'examen, "
        "n'en trace que 5 : la catégorie *Facilité de changement* est absente du "
        "graphique (bug constaté, pas une exclusion volontaire). Tant que ce "
        "template est vierge, aucun radar réel n'a de sens ici, un exemple de "
        "rendu (potentiels d'optimisation fictifs, 6 axes) est disponible via "
        "`.claude/skills/eof/scripts/generate_radar_svg.py`.\n"
    )
    out.append("### Comment ce référentiel se lit\n")
    out.append(
        "- **Dimensions 1 à 5 (Produit, Architecture, Infrastructure, Stockage, "
        "Algo & Code)** : chaque critère se répond par un choix unique parmi 5 "
        "(`✅ Point fort confirmé`, `💡 Potentiel d'amélioration identifié`, "
        "`🚫 Non applicable`, `🤔 À évaluer`, `⌛️ Évaluation en cours`), en "
        "cochant la case correspondante. Coefficient observé sur le Sheet "
        "source : `✅`/`🚫`/`🤔`/vide = 0, `💡` = 1, `⌛️` = 0,5 (cette dernière "
        "valeur n'a été observée qu'une seule fois dans tout le classeur au "
        "moment de la génération, à confirmer si elle se reproduit ailleurs, "
        "ce n'est pas encore une règle certaine).\n"
        "- **Dimension 6 (Facilité de changement)** : dropdown **différent** des 5 "
        "autres dimensions (confirmé par l'onglet \"À lire\" du Sheet source) : "
        "`🟢 Facile à modifier`, `🟡 Effort modéré`, `🔴 Difficile à changer`. "
        "Aucune réponse réelle n'existait sur cet onglet au moment de la "
        "génération, le mapping numérique (0 / 0,5 / 1 retenu ici) est une "
        "supposition par analogie avec les autres dimensions, **non vérifiée** sur "
        "une donnée réelle.\n"
        "- **Potentiel d'optimisation d'une dimension** = "
        "`Σ (coefficient de la réponse × maximum de potentiel du critère)` "
        "÷ `Σ (maximum de potentiel de TOUS les critères de la dimension, répondus ou non)`. "
        "**Un critère non répondu compte 0 au numérateur mais son maximum reste "
        "au dénominateur**, il ne pénalise donc jamais le potentiel d'optimisation, et une dimension "
        "vierge affiche 0 % de potentiel d'optimisation, pas \"inconnu\". "
        "C'est un biais méthodologique du Sheet source, pas une correction "
        "faite ici.\n"
        "- **Maximum de potentiel \"Sans objet\"** : l'onglet \"À lire\" indique qu'on peut "
        "exclure complètement un critère en réglant son maximum de potentiel sur \"Sans "
        "objet\" (pas juste répondre \"Non applicable\" à l'évaluation, qui "
        "elle laisse le maximum compter au dénominateur). Aucun exemple réel de "
        "ce réglage n'a été observé dans les données récupérées, mécanisme "
        "documenté ici tel que décrit par le Sheet, non vérifié sur un cas "
        "concret.\n"
        "- **Onglet 0 (Diagnostic rapide)** : logique différente, une échelle "
        "1 à 5 par critère (`(5 − réponse) ÷ 4 × maximum de potentiel`), ne contribue pas à ce "
        "tableau de synthèse.\n"
        "- **Maximum de potentiel** : chaque critère porte son propre maximum de potentiel "
        "(visible dans le Sheet source, colonne correspondante), différent d'un critère à l'autre, "
        "ce n'est jamais 1 partout.\n"
    )
    return "\n".join(out)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 build_template.py <dossier_json> <fichier_sortie.md>")
        sys.exit(1)
    json_dir, out_path = sys.argv[1], sys.argv[2]

    criteria_counts = {}
    for key, _ in PILLAR_TABS:
        rows = load_tab(json_dir, key)
        criteria_counts[key] = sum(1 for r in rows if is_id(cell(r, 1)))

    parts = []
    parts.append("# EOF-V.1.1 (EROOM Optimization Framework) — Référentiel complet\n")
    parts.append(
        "> Généré depuis la Google Sheet source : "
        "https://docs.google.com/spreadsheets/d/1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0/edit\n"
        ">\n"
        "> **Template vierge** — aucune réponse n'est pré-remplie. Le fichier Excel "
        "fourni en complément n'a servi qu'à deux choses que l'API de données du "
        "Sheet ne fournit pas : les 2 logos de la section \"À lire\" et 3 URLs de "
        "liens hypertexte (voir aux endroits concernés).\n"
    )
    toc_items = [
        ("À lire", "à-lire"),
        ("0 — Diagnostic rapide", "0--diagnostic-rapide"),
    ]
    for key, title in PILLAR_TABS_TEMPLATE_ORDER:
        anchor = title.lower()
        anchor = re.sub(r"[^\w\s-]", "", anchor).strip().replace(" ", "-")
        toc_items.append((title, anchor))
    toc_items.append(("Synthèse", "🕸️-7--synthèse".lower()))

    parts.append("## Sommaire\n")
    for label, anchor in toc_items:
        parts.append(f"- [{label}](#{anchor})")
    parts.append("")

    parts.append(build_a_lire(json_dir))
    parts.append("\n-----\n")
    parts.append(apply_hyperlink(build_diag_rapide(json_dir), "diag-rapide"))
    parts.append("\n-----\n")
    for key, title in PILLAR_TABS_TEMPLATE_ORDER:
        parts.append(apply_hyperlink(build_pillar(json_dir, key, title), key))
        parts.append("\n-----\n")
    parts.append(build_synthese(json_dir, criteria_counts))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    referentiel = build_referentiel_json(json_dir)
    referentiel_path = os.path.join(os.path.dirname(out_path) or ".", "eof-referentiel.json")
    with open(referentiel_path, "w", encoding="utf-8") as f:
        json.dump(referentiel, f, ensure_ascii=False, indent=2)

    print(f"Template écrit : {out_path}")
    print(
        f"Référentiel structuré écrit : {referentiel_path} "
        f"({len(referentiel['criteres'])} critères détaillés + "
        f"{len(referentiel['diagnostic_rapide'])} questions Diagnostic rapide)"
    )
    print("Critères par dimension :", criteria_counts, "total =", sum(criteria_counts.values()))


if __name__ == "__main__":
    main()
