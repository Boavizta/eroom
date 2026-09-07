#!/usr/bin/env python3
"""
Génération de questionnaires EOF depuis un audit existant.

Lit eof-audit-results.json, eof-referentiel.json et questionnaire-blocs.json
pour produire deux fichiers Markdown (produit-usage et technique) contenant
les questions encore à répondre.

Le résidu : un critère fait partie du résidu s'il n'a pas de verdict utile.
ATTENTION : "🤔 À évaluer" et "⌛️ Évaluation en cours" comptent comme des
réponses dans le reste du code (coefficient 0) mais NE TRANCHENT RIEN. Ces
réponses doivent être reposées. Raison : éviter qu'un critère ne soit jamais
posé et reste un faux zéro.

Usage :
    python3 generate_questionnaire.py <repertoire-audit>
    python3 generate_questionnaire.py <repertoire-audit> --output-dir <autre-dir>
    python3 generate_questionnaire.py --autotest

Écrit questionnaire-produit-usage.md et questionnaire-technique.md dans le
répertoire d'audit (ou dans --output-dir si spécifié).

NE modifie JAMAIS questionnaire-blocs.json ni son validateur.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Séparateur de section, jamais "-----" (lu lettre par lettre par TTS macOS)
SEPARATOR = "-----"

# Réponses qui ne tranchent rien et doivent être reposées
REPONSES_NON_TRANCHANTES = {
    "🤔 À évaluer",
    "⌛️ Évaluation en cours",
}


def nettoyer_mention_jnsp(libelle):
    """
    Nettoie la mention "je ne sais pas" d'un libellé de cran du diagnostic rapide.

    Raison de fond : certains crans du référentiel contiennent "je ne sais pas"
    collé au pire cas (ex: "1 - Très complexe / Je ne sais pas"). Ce nettoyage
    évite qu'un répondant qui ne sait pas se voie attribuer le pire cas en cochant
    cette option - nous ajoutons une case "Je ne sais pas" séparée qui ne pose
    aucune réponse.

    Ce nettoyage est PUREMENT cosmétique et ne change RIEN à la réponse versée :
    le parseur retrouve le cran d'origine par l'indice <!-- opt:N --> et va le
    relire dans le référentiel.

    Exemples de mentions à retirer (variantes de casse et séparateurs) :
    - "/ Je ne sais pas"
    - "/ je ne sais pas"
    - "ou je ne sais pas"
    - "Je ne sais pas" (en fin de libellé)

    Retourne le libellé nettoyé, ou le libellé d'origine si le nettoyage le
    viderait complètement.
    """
    if not isinstance(libelle, str):
        return libelle

    import re

    # Motif pour détecter "je ne sais pas" avec variantes
    # Capture les séparateurs courants avant la mention
    pattern = r'\s*[/]?\s*(ou\s+)?je\s+ne\s+sais\s+pas\.?'

    # Nettoyer (insensible à la casse)
    nettoye = re.sub(pattern, '', libelle, flags=re.IGNORECASE).strip()

    # Si le nettoyage vide le libellé ou ne laisse que le numéro de cran,
    # retourner l'original intact
    if not nettoye or re.match(r'^\d+\s*-?\s*$', nettoye):
        return libelle

    return nettoye


def find_referentiel():
    """Trouve le référentiel EOF dans l'arborescence."""
    # Chercher depuis le répertoire du script vers le haut
    current = Path(__file__).resolve().parent
    for _ in range(5):  # Remonter jusqu'à 5 niveaux
        matches = list(current.glob("**/eof-referentiel.json"))
        matches = [m for m in matches if ".venv" not in str(m)]
        if matches:
            return matches[0]
        current = current.parent
    raise FileNotFoundError("eof-referentiel.json introuvable")


def load_referentiel(path):
    """Charge le référentiel et retourne un dict {id: critère} et {id: question}."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    criteres = {c["id"]: c for c in data["criteres"]}
    diag_rapide = {q["id"]: q for q in data["diagnostic_rapide"]}

    return criteres, diag_rapide


def load_audit_results(audit_dir):
    """Charge les résultats d'audit existants et extrait les contextes."""
    path = audit_dir / "eof-audit-results.json"
    if not path.exists():
        raise FileNotFoundError(f"eof-audit-results.json introuvable dans {audit_dir}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Extraire les contextes pour l'emprunt 1
    # Clé = id du critère ou de la question, valeur = texte du contexte
    contextes = {}

    # Critères détaillés (1.x à 6.x)
    for c in data.get("criteres", []):
        cid = c["id"]
        ctx = c.get("contexte")
        # Piège 1 : une clé peut exister et valoir null
        if ctx is not None and isinstance(ctx, str) and ctx.strip():
            contextes[cid] = ctx.strip()

    # Questions diagnostic rapide (0.x)
    diag_apercu = data.get("diagnostic_rapide_apercu", {})
    for q in diag_apercu.get("questions", []):
        qid = q["id"]
        indice = q.get("indice_contextuel")
        # Piège 1 : une clé peut exister et valoir null
        if indice is not None and isinstance(indice, str) and indice.strip():
            contextes[qid] = indice.strip()

    return data, contextes


def load_blocs(scripts_dir):
    """Charge la bibliothèque de blocs."""
    path = scripts_dir / "questionnaire-blocs.json"
    if not path.exists():
        raise FileNotFoundError(f"questionnaire-blocs.json introuvable dans {scripts_dir}")

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_residu(audit_results, criteres_ref, diag_rapide_ref):
    """
    Calcule l'ensemble des critères encore dans le résidu.

    Un critère est dans le résidu si :
    - il n'a pas de réponse
    - ou sa réponse est "🤔 À évaluer" ou "⌛️ Évaluation en cours"

    Une question diagnostic rapide est dans le résidu si elle n'a pas de réponse.
    """
    residu = set()

    # Critères détaillés (1.x à 6.x)
    for c in audit_results.get("criteres", []):
        cid = c["id"]
        reponse = c.get("reponse")

        if reponse is None or reponse in REPONSES_NON_TRANCHANTES:
            residu.add(cid)

    # Questions diagnostic rapide (0.x)
    diag_apercu = audit_results.get("diagnostic_rapide_apercu", {})
    for q in diag_apercu.get("questions", []):
        qid = q["id"]
        reponse = q.get("reponse")

        if reponse is None or reponse in REPONSES_NON_TRANCHANTES:
            residu.add(qid)

    return residu


def get_criteres_from_bloc(bloc, criteres_ref, diag_rapide_ref):
    """Retourne la liste des critères couverts par un bloc."""
    if bloc["type"] == "direct":
        # Bloc direct : un seul critère
        return [bloc["critere"]]
    else:
        # Bloc composé : extraire tous les critères des options
        criteres = set()
        for option in bloc.get("options", []):
            for cid in option.get("reponses", {}).keys():
                criteres.add(cid)
        return list(criteres)


def compute_potentiel_bloc(bloc, residu, criteres_ref, diag_rapide_ref):
    """
    Calcule le potentiel total d'un bloc (somme des potentiel_max des critères
    encore dans le résidu).

    Les questions diagnostic rapide n'ont pas de potentiel_max : comptent comme 0.
    """
    criteres = get_criteres_from_bloc(bloc, criteres_ref, diag_rapide_ref)
    potentiel = 0.0

    for cid in criteres:
        if cid not in residu:
            continue

        # Questions diagnostic rapide : pas de potentiel_max
        if cid.startswith("0."):
            continue

        # Critère détaillé
        if cid in criteres_ref:
            potentiel += criteres_ref[cid]["potentiel_max"]

    return potentiel


def select_and_sort_blocs(blocs_data, residu, criteres_ref, diag_rapide_ref, fichier):
    """
    Sélectionne et trie les blocs à afficher dans un fichier donné.

    Un bloc est retenu si au moins un de ses critères est dans le résidu.

    Tri : phase "porte" avant "detail", puis potentiel décroissant, puis id de bloc
    (avec tri numérique des identifiants de critères pour que 0.2 < 0.10).
    """
    blocs_retenus = []

    for bloc in blocs_data["blocs"]:
        if bloc["fichier"] != fichier:
            continue

        criteres = get_criteres_from_bloc(bloc, criteres_ref, diag_rapide_ref)

        # Retenir si au moins un critère est dans le résidu
        if any(c in residu for c in criteres):
            potentiel = compute_potentiel_bloc(bloc, residu, criteres_ref, diag_rapide_ref)
            blocs_retenus.append((bloc, potentiel, criteres))

    # Tri : phase (porte=0, detail=1), puis -potentiel, puis diagnostic rapide avant détaillé, puis id numérique
    def parse_bloc_id_numerique(bloc_id):
        """
        Extrait les composants numériques d'un id de bloc pour permettre un tri numérique.
        Ex: "porte-diag-0.10" -> (0, 10), "porte-dim6-6.1" -> (6, 1)
        Retourne un tuple de nombres pour comparaison totale et déterministe.
        """
        import re
        # Chercher la partie "X.Y" dans l'id du bloc
        match = re.search(r'(\d+)\.(\d+)', bloc_id)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        # Fallback : retour d'une valeur haute pour que ça se trie en dernier
        return (999, 999)

    def sort_key(item):
        bloc, potentiel, criteres = item
        phase_order = 0 if bloc["phase"] == "porte" else 1

        # Dans la phase porte : diagnostic rapide (0.x) avant dimension 6 (6.x)
        # En utilisant le premier critère couvert (le plus petit numériquement)
        min_critere = min(criteres) if criteres else "999.999"
        is_diag_rapide = min_critere.startswith("0.")
        diag_order = 0 if is_diag_rapide else 1

        # Tri numérique sur l'id du bloc
        bloc_id_num = parse_bloc_id_numerique(bloc["id"])

        return (phase_order, diag_order, -potentiel, bloc_id_num)

    blocs_retenus.sort(key=sort_key)

    return blocs_retenus


def get_deja_tranches(bloc, criteres, audit_results, residu):
    """
    Pour un bloc composé, retourne la liste des critères déjà tranchés.

    Un critère est déjà tranché s'il n'est PAS dans le résidu.
    """
    return [c for c in criteres if c not in residu]


def get_options_for_direct_bloc(bloc, criteres_ref, diag_rapide_ref):
    """
    Pour un bloc direct, retourne les options depuis le référentiel.

    - Critère détaillé : options_evaluation
    - Question diagnostic rapide : crans
    """
    cid = bloc["critere"]

    if cid.startswith("0."):
        # Question diagnostic rapide
        if cid in diag_rapide_ref:
            return diag_rapide_ref[cid]["crans"]
        else:
            raise ValueError(f"Question diagnostic rapide {cid} introuvable dans le référentiel")
    else:
        # Critère détaillé
        if cid in criteres_ref:
            return criteres_ref[cid]["options_evaluation"]
        else:
            raise ValueError(f"Critère {cid} introuvable dans le référentiel")


def format_bloc_markdown(bloc, criteres, num, total, criteres_ref, diag_rapide_ref,
                         audit_results, residu, contextes):
    """
    Formate un bloc en Markdown.

    Respecte les consignes de style : séparateurs en "-----", guillemets droits,
    pas de tiret long.

    Paramètre contextes : dict {id_critere: texte_contexte} pour l'emprunt 1.
    """
    lines = []

    # Titre du bloc
    lines.append(f"## Bloc {num} sur {total}")
    lines.append("")

    # Marqueur machine
    lines.append(f"<!-- bloc:{bloc['id']} -->")
    lines.append("")

    # Question en gras
    lines.append(f"**{bloc['question']}**")
    lines.append("")

    # Aide en italique si présente
    if bloc.get("aide"):
        lines.append(f"*{bloc['aide']}*")
        lines.append("")

    # Emprunt 1 : Rappel des faits mesurés
    # Inséré après la question et l'aide, avant la note et les cases à cocher
    # Piège 3 (bloc composé) : afficher TOUS les faits mesurés non vides,
    # en fusionnant les doublons strictement identiques
    faits_mesures = []
    for cid in criteres:
        if cid in contextes:
            fait = contextes[cid]
            # Fusionner les doublons : n'ajouter que si pas déjà présent
            if fait not in faits_mesures:
                faits_mesures.append(fait)

    if faits_mesures:
        # Piège 5 : l'absence doit être silencieuse, mais ici on a au moins un fait
        lines.append("> **Ce que nous avons mesuré :**")
        if len(faits_mesures) == 1:
            # Un seul fait : pas de puce
            lines.append(f"> {faits_mesures[0]}")
        else:
            # Plusieurs faits : en puces
            for fait in faits_mesures:
                lines.append(f"> - {fait}")
        lines.append(">")
        lines.append("> Confirmez, ou corrigez si notre mesure est incomplète.")
        lines.append("")

    # Note en blockquote gras si présente
    if bloc.get("note"):
        lines.append(f"> **Note :** {bloc['note']}")
        lines.append("")

    # Critères couverts et potentiel
    criteres_residu = [c for c in criteres if c in residu]
    potentiel = compute_potentiel_bloc(bloc, residu, criteres_ref, diag_rapide_ref)

    lines.append(f"**Critères EOF couverts :** {', '.join(criteres_residu)}")
    if potentiel > 0:
        lines.append(f"**Potentiel débloqué :** {potentiel:.1f} points")
    lines.append("")

    # Options
    if bloc["type"] == "direct":
        options = get_options_for_direct_bloc(bloc, criteres_ref, diag_rapide_ref)
        # Pour les blocs directs sur diagnostic rapide, nettoyer les mentions "je ne sais pas"
        cid = bloc["critere"]
        if cid.startswith("0."):
            options = [nettoyer_mention_jnsp(opt) for opt in options]
    else:
        options = [opt["libelle"] for opt in bloc["options"]]

    for i, opt_libelle in enumerate(options):
        lines.append(f"- [ ] {opt_libelle}  <!-- opt:{i} -->")

    # Case "Je ne sais pas"
    lines.append(f"- [ ] Je ne sais pas  <!-- opt:jnsp -->")
    lines.append("")

    # Critères déjà tranchés (pour blocs composés)
    if bloc["type"] == "compose":
        deja_tranches = get_deja_tranches(bloc, criteres, audit_results, residu)
        if deja_tranches:
            lines.append(f"<!-- deja-tranche:{','.join(deja_tranches)} -->")
            lines.append("")

    return "\n".join(lines)


def generate_questionnaire_file(fichier, blocs_data, audit_results, criteres_ref,
                                 diag_rapide_ref, output_dir, contextes):
    """Génère un fichier de questionnaire (produit-usage ou technique)."""
    residu = compute_residu(audit_results, criteres_ref, diag_rapide_ref)
    blocs_tries = select_and_sort_blocs(blocs_data, residu, criteres_ref,
                                        diag_rapide_ref, fichier)

    if not blocs_tries:
        # Aucun bloc à afficher : ne pas créer le fichier
        return None

    lines = []

    # En-tête du fichier
    lines.append(SEPARATOR)
    titre = "Questionnaire EOF - Produit et usage" if fichier == "produit-usage" else "Questionnaire EOF - Technique"
    lines.append(titre)
    lines.append(SEPARATOR)
    lines.append("")

    # Instructions
    lines.append("**Comment remplir ce questionnaire :**")
    lines.append("")
    lines.append("- Cochez UNE SEULE case par bloc en utilisant la syntaxe `- [x]`.")
    lines.append("- Une case laissée vide reste vide et ne sera jamais devinée.")
    lines.append("- Vous pouvez vous arrêter après la partie porte en sachant ce que vous laissez.")
    lines.append("- Si vous ne savez pas, cochez la case \"Je ne sais pas\".")
    lines.append("")

    # Marqueurs machine
    lines.append(f"<!-- questionnaire: {fichier} -->")
    lines.append(f"<!-- version-blocs: {blocs_data['version']} -->")
    lines.append("")

    # Séparer porte et détail
    blocs_porte = [(b, p, c) for b, p, c in blocs_tries if b["phase"] == "porte"]
    blocs_detail = [(b, p, c) for b, p, c in blocs_tries if b["phase"] == "detail"]

    total_blocs = len(blocs_tries)
    num = 1

    if blocs_porte:
        lines.append(SEPARATOR)
        lines.append("Partie 1 : Questions de porte")
        lines.append(SEPARATOR)
        lines.append("")
        lines.append("La porte permet de décider rapidement si un diagnostic approfondi est pertinent.")
        lines.append("")

        for bloc, potentiel, criteres in blocs_porte:
            lines.append(format_bloc_markdown(bloc, criteres, num, total_blocs,
                                             criteres_ref, diag_rapide_ref,
                                             audit_results, residu, contextes))
            num += 1

    if blocs_detail:
        lines.append(SEPARATOR)
        lines.append("Partie 2 : Questions détaillées")
        lines.append(SEPARATOR)
        lines.append("")

        for bloc, potentiel, criteres in blocs_detail:
            lines.append(format_bloc_markdown(bloc, criteres, num, total_blocs,
                                             criteres_ref, diag_rapide_ref,
                                             audit_results, residu, contextes))
            num += 1

    # Écrire le fichier
    output_path = output_dir / f"questionnaire-{fichier}.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def autotest():
    """Rejoue les cas de test embarqués."""
    import tempfile

    echecs = []
    total = 0

    # Cas 1 : Bloc direct sur critère détaillé
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Créer un référentiel minimal
            ref_data = {
                "criteres": [
                    {
                        "id": "1.1",
                        "pilier": "🛖 1 — Produit",
                        "critere": "Test critère",
                        "potentiel_max": 2.0,
                        "options_evaluation": ["✅ Point fort confirmé", "💡 Potentiel d'amélioration identifié"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "💡 Potentiel d'amélioration identifié": 1}
                    }
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            # Créer une bibliothèque de blocs
            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-direct-11",
                        "fichier": "produit-usage",
                        "phase": "detail",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "1.1",
                        "question": "Question test ?",
                        "aide": "Aide test"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # Créer un audit results avec 1.1 dans le résidu
            audit_data = {
                "criteres": [{"id": "1.1", "reponse": None}],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            # Générer
            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("produit-usage", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc direct critère détaillé", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                if "Question test ?" not in content:
                    echecs.append(("Bloc direct critère détaillé", "Question absente"))
                if "<!-- bloc:test-direct-11 -->" not in content:
                    echecs.append(("Bloc direct critère détaillé", "Marqueur bloc absent"))
                if "<!-- opt:0 -->" not in content:
                    echecs.append(("Bloc direct critère détaillé", "Marqueur option absent"))
                if "<!-- opt:jnsp -->" not in content:
                    echecs.append(("Bloc direct critère détaillé", "Case 'Je ne sais pas' absente"))
    except Exception as exc:
        echecs.append(("Bloc direct critère détaillé", f"Exception : {exc}"))

    # Cas 2 : Bloc direct sur question diagnostic rapide (vérifier absence de coefficient)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [],
                "diagnostic_rapide": [
                    {
                        "id": "0.1",
                        "critere": "Question diagnostic",
                        "crans": ["Cran 1", "Cran 2"],
                        "niveau_impact": "Déterminant"
                    }
                ]
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-direct-01",
                        "fichier": "produit-usage",
                        "phase": "porte",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "0.1",
                        "question": "Question 0.1 ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteres": [],
                "diagnostic_rapide_apercu": {"questions": [{"id": "0.1", "reponse": None}]}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("produit-usage", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc direct diagnostic rapide", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                if "Cran 1" not in content:
                    echecs.append(("Bloc direct diagnostic rapide", "Options du référentiel absentes"))
    except Exception as exc:
        echecs.append(("Bloc direct diagnostic rapide", f"Exception : {exc}"))

    # Cas 3 : Critère avec "🤔 À évaluer" doit être dans le résidu
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {
                        "id": "2.1",
                        "pilier": "🗺️ 2 — Architecture",
                        "critere": "Test",
                        "potentiel_max": 1.5,
                        "options_evaluation": ["✅ Point fort confirmé", "💡 Potentiel d'amélioration identifié"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "💡 Potentiel d'amélioration identifié": 1}
                    }
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-a-evaluer",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "2.1",
                        "question": "Question 2.1 ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # Critère avec réponse "🤔 À évaluer" : doit être reposé
            audit_data = {
                "criteres": [{"id": "2.1", "reponse": "🤔 À évaluer", "coefficient": 0}],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("technique", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            # Le critère doit être dans le résidu et le bloc doit être généré
            if result is None:
                echecs.append(("Critère 'À évaluer' dans résidu", "Aucun fichier généré (bloc devait être retenu)"))
    except Exception as exc:
        echecs.append(("Critère 'À évaluer' dans résidu", f"Exception : {exc}"))

    # Cas 4 : Bloc composé avec critères déjà tranchés
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {
                        "id": "3.1",
                        "pilier": "🏢 3 — Infrastructure",
                        "critere": "Test 3.1",
                        "potentiel_max": 1.0,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    },
                    {
                        "id": "3.2",
                        "pilier": "🏢 3 — Infrastructure",
                        "critere": "Test 3.2",
                        "potentiel_max": 1.5,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    }
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-compose",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Test composé",
                        "type": "compose",
                        "question": "Question composée ?",
                        "options": [
                            {"libelle": "Option A", "reponses": {"3.1": "✅ Point fort confirmé", "3.2": "✅ Point fort confirmé"}},
                            {"libelle": "Option B", "reponses": {"3.1": "💡 Potentiel d'amélioration identifié"}}
                        ]
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # 3.1 déjà tranché, 3.2 dans le résidu
            audit_data = {
                "criteres": [
                    {"id": "3.1", "reponse": "✅ Point fort confirmé", "coefficient": 0},
                    {"id": "3.2", "reponse": None}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("technique", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc composé avec déjà tranché", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                if "<!-- deja-tranche:3.1 -->" not in content:
                    echecs.append(("Bloc composé avec déjà tranché", "Marqueur deja-tranche absent ou incorrect"))
    except Exception as exc:
        echecs.append(("Bloc composé avec déjà tranché", f"Exception : {exc}"))

    # Cas 5 : Nettoyage "je ne sais pas" dans les crans du diagnostic rapide
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [],
                "diagnostic_rapide": [
                    {
                        "id": "0.10",
                        "critere": "Complexité fonctionnelle",
                        "crans": [
                            "5 - Très simple",
                            "1 - Très complexe / Je ne sais pas"
                        ],
                        "niveau_impact": "Déterminant"
                    }
                ]
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-jnsp-nettoyage",
                        "fichier": "produit-usage",
                        "phase": "porte",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "0.10",
                        "question": "Question test ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteres": [],
                "diagnostic_rapide_apercu": {"questions": [{"id": "0.10", "reponse": None}]}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("produit-usage", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Nettoyage je ne sais pas", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                # Vérifier que "Je ne sais pas" a été retiré du cran 1
                if "1 - Très complexe / Je ne sais pas" in content:
                    echecs.append(("Nettoyage je ne sais pas", "Mention 'Je ne sais pas' non nettoyée dans le cran"))
                # Vérifier que le cran nettoyé apparaît
                if "1 - Très complexe" not in content:
                    echecs.append(("Nettoyage je ne sais pas", "Cran nettoyé absent du questionnaire"))
                # Vérifier que l'indice opt:1 est présent pour le parseur
                if "<!-- opt:1 -->" not in content:
                    echecs.append(("Nettoyage je ne sais pas", "Marqueur opt:1 absent"))
    except Exception as exc:
        echecs.append(("Nettoyage je ne sais pas", f"Exception : {exc}"))

    # Cas 6 : Ordonnancement porte avant detail
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "1.1", "potentiel_max": 2.0, "options_evaluation": [], "options_evaluation_coefficient": {}},
                    {"id": "0.1"}
                ],
                "diagnostic_rapide": [
                    {"id": "0.1", "critere": "Test", "crans": ["Cran 1"], "niveau_impact": "Déterminant"}
                ]
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {"id": "bloc-detail", "fichier": "produit-usage", "phase": "detail", "type": "direct", "critere": "1.1", "question": "Detail ?"},
                    {"id": "bloc-porte", "fichier": "produit-usage", "phase": "porte", "type": "direct", "critere": "0.1", "question": "Porte ?"}
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteres": [{"id": "1.1", "reponse": None}],
                "diagnostic_rapide_apercu": {"questions": [{"id": "0.1", "reponse": None}]}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("produit-usage", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result:
                content = result.read_text(encoding="utf-8")
                # La porte doit apparaître avant le detail
                pos_porte = content.find("bloc-porte")
                pos_detail = content.find("bloc-detail")
                if pos_porte == -1 or pos_detail == -1:
                    echecs.append(("Ordonnancement porte avant detail", "Blocs absents"))
                elif pos_porte > pos_detail:
                    echecs.append(("Ordonnancement porte avant detail", "Porte après detail (attendu : porte avant)"))
    except Exception as exc:
        echecs.append(("Ordonnancement porte avant detail", f"Exception : {exc}"))

    # Cas 7 : Tri numérique des identifiants de critères (0.2 avant 0.10)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [],
                "diagnostic_rapide": [
                    {"id": "0.2", "critere": "Test 0.2", "crans": ["Cran"], "niveau_impact": "Déterminant"},
                    {"id": "0.10", "critere": "Test 0.10", "crans": ["Cran"], "niveau_impact": "Déterminant"}
                ]
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {"id": "porte-diag-0.10", "fichier": "produit-usage", "phase": "porte", "titre": "Test", "type": "direct", "critere": "0.10", "question": "Question 0.10 ?"},
                    {"id": "porte-diag-0.2", "fichier": "produit-usage", "phase": "porte", "titre": "Test", "type": "direct", "critere": "0.2", "question": "Question 0.2 ?"}
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteres": [],
                "diagnostic_rapide_apercu": {"questions": [{"id": "0.2", "reponse": None}, {"id": "0.10", "reponse": None}]}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("produit-usage", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result:
                content = result.read_text(encoding="utf-8")
                # 0.2 doit apparaître avant 0.10
                pos_02 = content.find("porte-diag-0.2")
                pos_010 = content.find("porte-diag-0.10")
                if pos_02 == -1 or pos_010 == -1:
                    echecs.append(("Tri numérique 0.2 avant 0.10", "Blocs absents"))
                elif pos_02 > pos_010:
                    echecs.append(("Tri numérique 0.2 avant 0.10", f"0.2 après 0.10 (positions : {pos_02} > {pos_010})"))
    except Exception as exc:
        echecs.append(("Tri numérique 0.2 avant 0.10", f"Exception : {exc}"))

    # Cas 8 : Rendu de la clé `note`
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {
                        "id": "4.1",
                        "pilier": "🔍 4 — Observabilité",
                        "critere": "Test 4.1",
                        "potentiel_max": 1.0,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    },
                    {
                        "id": "4.2",
                        "pilier": "🔍 4 — Observabilité",
                        "critere": "Test 4.2",
                        "potentiel_max": 1.0,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    }
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-avec-note",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Test avec note",
                        "type": "direct",
                        "critere": "4.1",
                        "question": "Question avec note ?",
                        "aide": "Aide test",
                        "note": "À valider avec le responsable produit"
                    },
                    {
                        "id": "test-sans-note",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Test sans note",
                        "type": "direct",
                        "critere": "4.2",
                        "question": "Question sans note ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteres": [
                    {"id": "4.1", "reponse": None},
                    {"id": "4.2", "reponse": None}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("technique", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Rendu clé note", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                # Vérifier que la note apparaît pour le bloc test-avec-note
                if "> **Note :** À valider avec le responsable produit" not in content:
                    echecs.append(("Rendu clé note", "Note absente pour bloc avec note"))
                # Vérifier qu'aucune note n'apparaît pour le bloc test-sans-note
                # On cherche entre le marqueur du bloc et la ligne des critères
                pos_sans_note = content.find("<!-- bloc:test-sans-note -->")
                if pos_sans_note != -1:
                    section_sans_note = content[pos_sans_note:pos_sans_note + 500]
                    if "> **Note :**" in section_sans_note:
                        echecs.append(("Rendu clé note", "Note présente pour bloc sans note (ne devrait pas)"))
    except Exception as exc:
        echecs.append(("Rendu clé note", f"Exception : {exc}"))

    # Cas 9 : Emprunt 1 - Critère avec contexte null
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {
                        "id": "5.1",
                        "pilier": "👨‍💻 5 — Algo & Code",
                        "critere": "Test 5.1",
                        "potentiel_max": 1.0,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    }
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-contexte-null",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "5.1",
                        "question": "Question 5.1 ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # Critère avec contexte = null
            audit_data = {
                "criteres": [{"id": "5.1", "reponse": None, "contexte": None}],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("technique", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Emprunt 1 - contexte null", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                # Aucun rappel ne doit être affiché
                if "> **Ce que nous avons mesuré :**" in content:
                    echecs.append(("Emprunt 1 - contexte null", "Rappel affiché alors que contexte est null"))
    except Exception as exc:
        echecs.append(("Emprunt 1 - contexte null", f"Exception : {exc}"))

    # Cas 10 : Emprunt 1 - Critère avec contexte vide
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {
                        "id": "5.2",
                        "pilier": "👨‍💻 5 — Algo & Code",
                        "critere": "Test 5.2",
                        "potentiel_max": 1.0,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    }
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-contexte-vide",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "5.2",
                        "question": "Question 5.2 ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # Critère avec contexte = "   " (espaces uniquement)
            audit_data = {
                "criteres": [{"id": "5.2", "reponse": None, "contexte": "   "}],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("technique", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Emprunt 1 - contexte vide", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                # Aucun rappel ne doit être affiché
                if "> **Ce que nous avons mesuré :**" in content:
                    echecs.append(("Emprunt 1 - contexte vide", "Rappel affiché alors que contexte est vide"))
    except Exception as exc:
        echecs.append(("Emprunt 1 - contexte vide", f"Exception : {exc}"))

    # Cas 11 : Emprunt 1 - Bloc composé avec un seul contexte
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {
                        "id": "2.1",
                        "pilier": "🗺️ 2 — Architecture",
                        "critere": "Test 2.1",
                        "potentiel_max": 1.0,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    },
                    {
                        "id": "2.2",
                        "pilier": "🗺️ 2 — Architecture",
                        "critere": "Test 2.2",
                        "potentiel_max": 1.5,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    }
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-compose-un-contexte",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Test composé",
                        "type": "compose",
                        "question": "Question composée ?",
                        "options": [
                            {"libelle": "Option A", "reponses": {"2.1": "✅ Point fort confirmé", "2.2": "✅ Point fort confirmé"}},
                            {"libelle": "Option B", "reponses": {"2.1": "💡 Potentiel d'amélioration identifié"}}
                        ]
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # 2.1 avec contexte, 2.2 sans contexte
            audit_data = {
                "criteres": [
                    {"id": "2.1", "reponse": None, "contexte": "Fait mesuré pour 2.1"},
                    {"id": "2.2", "reponse": None, "contexte": None}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("technique", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Emprunt 1 - bloc composé un contexte", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                # Un rappel avec le seul fait doit être affiché (sans puce car un seul)
                if "> **Ce que nous avons mesuré :**" not in content:
                    echecs.append(("Emprunt 1 - bloc composé un contexte", "Aucun rappel affiché"))
                elif "> Fait mesuré pour 2.1" not in content:
                    echecs.append(("Emprunt 1 - bloc composé un contexte", "Fait 2.1 absent du rappel"))
                # Vérifier qu'il n'y a pas de puce (un seul fait)
                elif "> - Fait mesuré pour 2.1" in content:
                    echecs.append(("Emprunt 1 - bloc composé un contexte", "Puce présente alors qu'un seul fait (attendu : sans puce)"))
    except Exception as exc:
        echecs.append(("Emprunt 1 - bloc composé un contexte", f"Exception : {exc}"))

    # Cas 12 : Emprunt 1 - Bloc composé avec deux contextes identiques (fusion)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {
                        "id": "3.1",
                        "pilier": "🏢 3 — Infrastructure",
                        "critere": "Test 3.1",
                        "potentiel_max": 1.0,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    },
                    {
                        "id": "3.2",
                        "pilier": "🏢 3 — Infrastructure",
                        "critere": "Test 3.2",
                        "potentiel_max": 1.5,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    }
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-compose-fusion",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Test composé fusion",
                        "type": "compose",
                        "question": "Question composée ?",
                        "options": [
                            {"libelle": "Option A", "reponses": {"3.1": "✅ Point fort confirmé", "3.2": "✅ Point fort confirmé"}},
                            {"libelle": "Option B", "reponses": {"3.1": "💡 Potentiel d'amélioration identifié"}}
                        ]
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # 3.1 et 3.2 avec le MÊME contexte
            audit_data = {
                "criteres": [
                    {"id": "3.1", "reponse": None, "contexte": "Fait identique pour les deux"},
                    {"id": "3.2", "reponse": None, "contexte": "Fait identique pour les deux"}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("technique", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Emprunt 1 - bloc composé fusion", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                # Le fait doit apparaître une seule fois (fusion des doublons)
                if "> **Ce que nous avons mesuré :**" not in content:
                    echecs.append(("Emprunt 1 - bloc composé fusion", "Aucun rappel affiché"))
                elif content.count("Fait identique pour les deux") > 1:
                    echecs.append(("Emprunt 1 - bloc composé fusion", f"Doublon non fusionné (apparaît {content.count('Fait identique pour les deux')} fois)"))
                # Vérifier qu'il n'y a pas de puce (un seul fait après fusion)
                elif "> - Fait identique pour les deux" in content:
                    echecs.append(("Emprunt 1 - bloc composé fusion", "Puce présente alors qu'un seul fait après fusion (attendu : sans puce)"))
    except Exception as exc:
        echecs.append(("Emprunt 1 - bloc composé fusion", f"Exception : {exc}"))

    # Cas 13 : Emprunt 1 - Question 0.x avec indice_contextuel
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [],
                "diagnostic_rapide": [
                    {
                        "id": "0.5",
                        "critere": "Test diagnostic",
                        "crans": ["Cran 1", "Cran 2"],
                        "niveau_impact": "Déterminant"
                    }
                ]
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-diag-indice",
                        "fichier": "produit-usage",
                        "phase": "porte",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "0.5",
                        "question": "Question 0.5 ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # Question 0.5 avec indice_contextuel
            audit_data = {
                "criteres": [],
                "diagnostic_rapide_apercu": {
                    "questions": [
                        {"id": "0.5", "reponse": None, "indice_contextuel": "Indice de contexte pour 0.5"}
                    ]
                }
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("produit-usage", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Emprunt 1 - question 0.x avec indice", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                # Le rappel doit être affiché
                if "> **Ce que nous avons mesuré :**" not in content:
                    echecs.append(("Emprunt 1 - question 0.x avec indice", "Aucun rappel affiché"))
                elif "Indice de contexte pour 0.5" not in content:
                    echecs.append(("Emprunt 1 - question 0.x avec indice", "Indice contextuel absent du rappel"))
    except Exception as exc:
        echecs.append(("Emprunt 1 - question 0.x avec indice", f"Exception : {exc}"))

    # Cas 14 : Emprunt 1 - Audit avec tous les contextes vides
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {
                        "id": "1.1",
                        "pilier": "🛖 1 — Produit",
                        "critere": "Test 1.1",
                        "potentiel_max": 2.0,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    },
                    {
                        "id": "1.2",
                        "pilier": "🛖 1 — Produit",
                        "critere": "Test 1.2",
                        "potentiel_max": 1.5,
                        "options_evaluation": ["✅ Point fort confirmé"],
                        "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}
                    }
                ],
                "diagnostic_rapide": [
                    {
                        "id": "0.1",
                        "critere": "Test 0.1",
                        "crans": ["Cran 1"],
                        "niveau_impact": "Déterminant"
                    }
                ]
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "test-vide-1",
                        "fichier": "produit-usage",
                        "phase": "detail",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "1.1",
                        "question": "Question 1.1 ?"
                    },
                    {
                        "id": "test-vide-2",
                        "fichier": "produit-usage",
                        "phase": "detail",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "1.2",
                        "question": "Question 1.2 ?"
                    },
                    {
                        "id": "test-vide-3",
                        "fichier": "produit-usage",
                        "phase": "porte",
                        "titre": "Test",
                        "type": "direct",
                        "critere": "0.1",
                        "question": "Question 0.1 ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # Tous les contextes sont null ou vides
            audit_data = {
                "criteres": [
                    {"id": "1.1", "reponse": None, "contexte": None},
                    {"id": "1.2", "reponse": None, "contexte": ""}
                ],
                "diagnostic_rapide_apercu": {
                    "questions": [
                        {"id": "0.1", "reponse": None, "indice_contextuel": None}
                    ]
                }
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_file("produit-usage", blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Emprunt 1 - audit vide", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                # Aucun rappel ne doit être affiché nulle part
                if "> **Ce que nous avons mesuré :**" in content:
                    echecs.append(("Emprunt 1 - audit vide", "Rappel affiché alors que tous les contextes sont vides"))
    except Exception as exc:
        echecs.append(("Emprunt 1 - audit vide", f"Exception : {exc}"))

    if echecs:
        print(f"AUTOTEST EN ÉCHEC : {len(echecs)} cas sur {total}")
        for libelle, erreur in echecs:
            print(f"  - {libelle}")
            print(f"      {erreur}")
        return 1

    print(f"Autotest : {total} cas passés.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Génère des questionnaires EOF depuis un audit existant")
    parser.add_argument("repertoire_audit", nargs="?",
                        help="dossier d'audit contenant eof-audit-results.json")
    parser.add_argument("--output-dir",
                        help="répertoire de sortie (par défaut : repertoire_audit)")
    parser.add_argument("--autotest", action="store_true",
                        help="rejoue les cas de test embarqués et sort 1 si un cas échoue")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())

    if not args.repertoire_audit:
        parser.error("repertoire_audit est requis (ou utiliser --autotest)")

    audit_dir = Path(args.repertoire_audit).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else audit_dir

    # Charger les données
    ref_path = find_referentiel()
    criteres_ref, diag_rapide_ref = load_referentiel(ref_path)
    audit_results, contextes = load_audit_results(audit_dir)

    # Trouver la bibliothèque de blocs
    scripts_dir = Path(__file__).resolve().parent
    blocs_data = load_blocs(scripts_dir)

    # Générer les deux fichiers
    for fichier in ["produit-usage", "technique"]:
        result = generate_questionnaire_file(fichier, blocs_data, audit_results,
                                            criteres_ref, diag_rapide_ref, output_dir, contextes)
        if result:
            print(f"Généré : {result}")
        else:
            print(f"Aucun bloc à afficher pour {fichier} (résidu vide)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
