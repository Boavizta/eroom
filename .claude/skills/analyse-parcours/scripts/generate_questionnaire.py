#!/usr/bin/env python3
"""
Génération de questionnaires EOF depuis un audit existant.

Lit eof-audit-results.json, eof-referentiel.json et questionnaire-blocs.json
pour produire un fichier Markdown unique contenant les questions encore à
répondre, triées par rendement décroissant.

Le résidu : un critère fait partie du résidu s'il n'a pas de verdict utile.
ATTENTION : "🤔 À évaluer" et "⌛️ Évaluation en cours" comptent comme des
réponses dans le reste du code (coefficient 0) mais NE TRANCHENT RIEN. Ces
réponses doivent être reposées. Raison : éviter qu'un critère ne soit jamais
posé et reste un faux zéro.

Usage :
    python3 generate_questionnaire.py <repertoire-audit> --output-dir <autre-dir>
    python3 generate_questionnaire.py --autotest

Écrit questionnaire-eof.md dans le répertoire spécifié par --output-dir.

Par défaut, REFUSE d'écrire dans un chemin contenant "audits" (un questionnaire
vierge ne doit jamais se trouver dans audits/ pour éviter l'envoi accidentel
d'un fichier non rempli). Passer --dans-le-dossier-audit pour forcer.

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
    elif bloc["type"] == "filtre":
        # Bloc filtre : liste de critères écartés
        return bloc.get("criteres", [])
    else:
        # Bloc composé : extraire tous les critères des options. Ordre trié pour
        # que la sortie soit déterministe (list(set(...)) dépend du hash-seed du
        # process Python, donc changeait d'un rejeu à l'autre sans raison).
        criteres = set()
        for option in bloc.get("options", []):
            for cid in option.get("reponses", {}).keys():
                criteres.add(cid)
        return sorted(criteres)


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


def bloc_filtre_doit_etre_supprime(bloc, audit_results):
    """
    Vérifie si un bloc filtre doit être supprimé selon la règle 4.2.

    Un filtre n'est imprimé que si AUCUN de ses critères ne porte déjà une
    réponse tranchante (c'est-à-dire une réponse absente de REPONSES_NON_TRANCHANTES).

    Retourne True si le filtre doit être supprimé, False sinon.
    """
    if bloc.get("type") != "filtre":
        return False

    criteres_filtre = bloc.get("criteres", [])

    # Construire un index {id_critere: reponse} depuis audit_results
    reponses = {}

    # Critères détaillés
    for c in audit_results.get("criteres", []):
        reponses[c["id"]] = c.get("reponse")

    # Questions diagnostic rapide
    diag_apercu = audit_results.get("diagnostic_rapide_apercu", {})
    for q in diag_apercu.get("questions", []):
        reponses[q["id"]] = q.get("reponse")

    # Vérifier si au moins un critère du filtre a une réponse tranchante
    for cid in criteres_filtre:
        reponse = reponses.get(cid)
        if reponse is not None and reponse not in REPONSES_NON_TRANCHANTES:
            # Une réponse tranchante existe : supprimer le filtre
            return True

    return False


def select_and_sort_blocs(blocs_data, residu, criteres_ref, diag_rapide_ref, audit_results=None):
    """
    Sélectionne et trie les blocs à afficher dans le questionnaire unique.

    Un bloc est retenu si au moins un de ses critères est dans le résidu.
    Un bloc filtre est supprimé si l'un de ses critères a déjà une réponse tranchante.

    Tri : rendement décroissant (nombre de critères), puis phase "porte" avant
    "detail", puis ordre du référentiel (0.x, puis 1.x à 6.x).
    """
    blocs_retenus = []

    for bloc in blocs_data["blocs"]:
        # Règle 4.2 : supprimer un filtre si l'un de ses critères est déjà tranché
        if audit_results and bloc_filtre_doit_etre_supprime(bloc, audit_results):
            continue

        criteres = get_criteres_from_bloc(bloc, criteres_ref, diag_rapide_ref)

        # Retenir si au moins un critère est dans le résidu
        criteres_residu = [c for c in criteres if c in residu]
        if criteres_residu:
            potentiel = compute_potentiel_bloc(bloc, residu, criteres_ref, diag_rapide_ref)
            rendement = len(criteres_residu)
            blocs_retenus.append((bloc, potentiel, criteres, rendement))

    # Tri spécial : les filtres en tête de la partie detail, triés entre eux par rendement,
    # puis tous les autres blocs (porte puis detail) triés par rendement/ordre référentiel
    def parse_critere_id(critere_id):
        """
        Extrait les composants numériques d'un id de critère pour tri numérique.
        Ex: "0.10" -> (0, 10), "1.5" -> (1, 5)
        """
        import re
        match = re.search(r'(\d+)\.(\d+)', critere_id)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (999, 999)

    def sort_key(item):
        bloc, potentiel, criteres, rendement = item

        # Tri : porte d'abord, puis filtres detail, puis autres detail
        # Ordre de tri : (1) phase_order, (2) rendement décroissant, (3) ordre ref
        is_filtre = bloc.get("type") == "filtre"

        if bloc["phase"] == "porte":
            # Blocs porte : (0, rendement décroissant, ordre ref)
            phase_order = 0
        elif is_filtre:
            # Filtres detail : (1, rendement décroissant, ordre ref)
            phase_order = 1
        else:
            # Autres blocs detail : (2, rendement décroissant, ordre ref)
            phase_order = 2

        min_critere = min(criteres, key=parse_critere_id) if criteres else "999.999"
        ordre_ref = parse_critere_id(min_critere)

        return (phase_order, -rendement, ordre_ref)

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


def build_filtres_index(blocs_tries):
    """
    Construit un index {critere_id: [(filtre_id, num_question, titre, libelle_ecarte), ...]}
    pour tous les critères gouvernés par des filtres.

    blocs_tries est la liste triée des blocs retenus (avec leurs métadonnées).
    """
    index = {}
    num = 1

    for bloc, potentiel, criteres, rendement in blocs_tries:
        if bloc.get("type") == "filtre":
            filtre_id = bloc["id"]
            titre = bloc["titre"]
            libelle_ecarte = bloc["libelle_ecarte"]

            for critere_id in bloc.get("criteres", []):
                if critere_id not in index:
                    index[critere_id] = []
                index[critere_id].append((filtre_id, num, titre, libelle_ecarte))

        num += 1

    return index


def format_bloc_markdown(bloc, criteres, num, total, criteres_ref, diag_rapide_ref,
                         audit_results, residu, contextes, filtres_index):
    """
    Formate un bloc en Markdown.

    Respecte les consignes de style : séparateurs en "-----", guillemets droits,
    pas de tiret long.

    Paramètre contextes : dict {id_critere: texte_contexte} pour l'emprunt 1.
    Paramètre filtres_index : dict {critere_id: [(filtre_id, num_question, titre, libelle_ecarte), ...]}
    """
    lines = []

    # Titre du bloc : le sujet de la question, plus la personne a qui la passer.
    # "Bloc 3 sur 41" seul ne disait rien du sujet, donc le lecteur devait lire la
    # question entiere pour savoir si elle etait pour lui, et un questionnaire qui
    # circule mal revient sans reponse.
    titre_ligne = f"## {num} sur {total} - {bloc['titre']}"
    if bloc.get("interlocuteur"):
        titre_ligne += f" (à voir avec {bloc['interlocuteur']})"
    lines.append(titre_ligne)
    lines.append("")

    # Mention "À IGNORER" si tous les critères du bloc sont gouvernés par des filtres
    # Section 4.2ter de la convention
    if bloc.get("type") != "filtre":
        criteres_residu = [c for c in criteres if c in residu]

        # Vérifier si tous les critères sont gouvernés
        filtres_gouvernants = {}  # {filtre_id: (num, titre, libelle_ecarte)}
        tous_gouvernes = True

        for cid in criteres_residu:
            if cid not in filtres_index or not filtres_index[cid]:
                tous_gouvernes = False
                break
            # Collecter tous les filtres qui gouvernent ce critère
            for filtre_id, num_q, titre_f, libelle_e in filtres_index[cid]:
                if filtre_id not in filtres_gouvernants:
                    filtres_gouvernants[filtre_id] = (num_q, titre_f, libelle_e)

        if tous_gouvernes and filtres_gouvernants:
            # Construire la mention avec conjonction si plusieurs filtres
            # Trier par numéro de question pour avoir l'ordre d'apparition dans le questionnaire
            filtres_tries = sorted(filtres_gouvernants.items(), key=lambda item: item[1][0])

            if len(filtres_tries) == 1:
                # Un seul filtre : extraire son libellé et construire la mention
                filtre_id, (num_q, titre_f, libelle_e) = filtres_tries[0]
                debut_libelle = libelle_e.split('(')[0].strip()
                condition = f"si vous avez repondu \"{debut_libelle}\" a la question {num_q} ({titre_f})"
            else:
                # Plusieurs filtres : chaque terme porte son propre libellé
                termes = []
                for filtre_id, (num_q, titre_f, libelle_e) in filtres_tries:
                    debut_libelle = libelle_e.split('(')[0].strip()
                    termes.append(f"\"{debut_libelle}\" a la question {num_q} ({titre_f})")
                condition = f"si vous avez repondu {' ET '.join(termes)}"

            lines.append(f"**A IGNORER** {condition}.")
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

    # Critères couverts et potentiel : plomberie interne, en commentaires HTML.
    # Ces deux informations servent à nous, jamais au service audité : un identifiant
    # de critère et un nombre de points ne l'aident pas à répondre et lui donnent à
    # lire le fonctionnement de notre outil. Elles restent dans le fichier, invisibles
    # à la lecture, pour rester traçables.
    criteres_residu = [c for c in criteres if c in residu]
    potentiel = compute_potentiel_bloc(bloc, residu, criteres_ref, diag_rapide_ref)

    lines.append(f"<!-- criteres:{','.join(criteres_residu)} -->")
    if potentiel > 0:
        lines.append(f"<!-- potentiel:{potentiel:.1f} -->")
    lines.append("")

    # Options
    if bloc["type"] == "direct":
        options = get_options_for_direct_bloc(bloc, criteres_ref, diag_rapide_ref)
        # Pour les blocs directs sur diagnostic rapide, nettoyer les mentions "je ne sais pas"
        cid = bloc["critere"]
        if cid.startswith("0."):
            options = [nettoyer_mention_jnsp(opt) for opt in options]

        for i, opt_libelle in enumerate(options):
            lines.append(f"- [ ] {opt_libelle}  <!-- opt:{i} -->")

    elif bloc["type"] == "filtre":
        # Bloc filtre : deux options (ecarte et applicable)
        lines.append(f"- [ ] {bloc['libelle_ecarte']}  <!-- opt:ecarte -->")
        lines.append(f"- [ ] {bloc['libelle_applicable']}  <!-- opt:applicable -->")

    else:
        # Bloc composé
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


def generate_questionnaire_unique(blocs_data, audit_results, criteres_ref,
                                   diag_rapide_ref, output_dir, contextes):
    """Génère le questionnaire unique trié par rendement décroissant."""
    residu = compute_residu(audit_results, criteres_ref, diag_rapide_ref)
    blocs_tries = select_and_sort_blocs(blocs_data, residu, criteres_ref,
                                        diag_rapide_ref, audit_results)

    if not blocs_tries:
        # Aucun bloc à afficher : ne pas créer le fichier
        return None

    lines = []

    # En-tête du fichier
    lines.append(SEPARATOR)
    lines.append("Questionnaire EOF")
    lines.append(SEPARATOR)
    lines.append("")

    # Instructions
    lines.append("**Comment remplir ce questionnaire :**")
    lines.append("")
    lines.append("- Cochez UNE SEULE case par bloc en utilisant la syntaxe `- [x]`.")
    lines.append("- Une case laissée vide reste vide et ne sera jamais devinée.")
    lines.append("- Chaque question indique dans son titre à qui la poser.")
    lines.append("- Les questions sont classées pour que les premières rapportent le plus de critères.")
    lines.append("- Vous pouvez vous arrêter en cours de route : l'effort fourni aura couvert le maximum de critères.")
    lines.append("- Si vous ne savez pas, cochez la case \"Je ne sais pas\".")
    lines.append("")

    # Marqueurs machine
    lines.append(f"<!-- questionnaire: eof -->")
    lines.append(f"<!-- version-blocs: {blocs_data['version']} -->")
    lines.append("")

    # Construire l'index des filtres pour la mention "À IGNORER"
    filtres_index = build_filtres_index(blocs_tries)

    # Séparer porte et détail
    blocs_porte = [(b, p, c, r) for b, p, c, r in blocs_tries if b["phase"] == "porte"]
    blocs_detail = [(b, p, c, r) for b, p, c, r in blocs_tries if b["phase"] == "detail"]

    total_blocs = len(blocs_tries)
    num = 1

    if blocs_porte:
        lines.append(SEPARATOR)
        # "Porte" est notre étiquette interne pour cette phase, elle ne dit rien à
        # un lecteur client : le titre imprimé emploie des mots ordinaires.
        lines.append("Partie 1 : Premier tri")
        lines.append(SEPARATOR)
        lines.append("")
        lines.append("Ce premier tri permet de décider rapidement si un diagnostic approfondi est pertinent.")
        lines.append("")

        for bloc, potentiel, criteres, rendement in blocs_porte:
            lines.append(format_bloc_markdown(bloc, criteres, num, total_blocs,
                                             criteres_ref, diag_rapide_ref,
                                             audit_results, residu, contextes, filtres_index))
            num += 1

    if blocs_detail:
        lines.append(SEPARATOR)
        lines.append("Partie 2 : Questions détaillées")
        lines.append(SEPARATOR)
        lines.append("")

        for bloc, potentiel, criteres, rendement in blocs_detail:
            lines.append(format_bloc_markdown(bloc, criteres, num, total_blocs,
                                             criteres_ref, diag_rapide_ref,
                                             audit_results, residu, contextes, filtres_index))
            num += 1

    # Écrire le fichier
    output_path = output_dir / "questionnaire-eof.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def autotest():
    """Rejoue les cas de test embarqués."""
    import tempfile
    import subprocess

    echecs = []
    total = 0

    # Les cas 24 à 26 sont groupés ici parce qu'ils sont les seuls à relancer le
    # script par subprocess : ils exercent main() et son garde-fou, pas une
    # fonction interne. Ils travaillent donc avec le VRAI référentiel et la VRAIE
    # bibliothèque de blocs, que le script retrouve depuis son propre répertoire
    # (find_referentiel) et non depuis le dossier d'audit qu'on lui passe.

    # Cas 24 : Refus d'écrire dans audits/ sans drapeau
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Créer une arborescence avec audits/
            audit_dir = tmpdir / "audits" / "test.com"
            audit_dir.mkdir(parents=True)

            audit_data = {"criteres": [{"id": "1.1", "reponse": None}], "diagnostic_rapide_apercu": {"questions": []}}
            audit_path = audit_dir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            # Appeler le script sans drapeau
            result = subprocess.run(
                [sys.executable, __file__, str(audit_dir)],
                capture_output=True,
                text=True
            )

            if result.returncode != 2:
                echecs.append(("Refus ecriture dans audits sans drapeau", f"Code sortie attendu 2, obtenu {result.returncode}"))
            elif "audits" not in result.stderr:
                echecs.append(("Refus ecriture dans audits sans drapeau", "Message d'erreur ne mentionne pas 'audits'"))
    except Exception as exc:
        echecs.append(("Refus ecriture dans audits sans drapeau", f"Exception : {exc}"))

    # Cas 25 : Acceptation avec --dans-le-dossier-audit
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            audit_dir = tmpdir / "audits" / "test.com"
            audit_dir.mkdir(parents=True)

            audit_data = {"criteres": [{"id": "1.1", "reponse": None}], "diagnostic_rapide_apercu": {"questions": []}}
            audit_path = audit_dir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            # Appeler le script avec drapeau
            result = subprocess.run(
                [sys.executable, __file__, str(audit_dir), "--dans-le-dossier-audit"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                echecs.append(("Acceptation avec drapeau explicite", f"Code sortie attendu 0, obtenu {result.returncode}. stderr: {result.stderr}"))
            elif not (audit_dir / "questionnaire-eof.md").exists():
                echecs.append(("Acceptation avec drapeau explicite", "Fichier questionnaire-eof.md non cree"))
    except Exception as exc:
        echecs.append(("Acceptation avec drapeau explicite", f"Exception : {exc}"))

    # Cas 26 : Acceptation sans drapeau hors de audits/
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            audit_dir = tmpdir / "test.com"
            audit_dir.mkdir(parents=True)
            output_dir = tmpdir / "output"
            output_dir.mkdir()

            audit_data = {"criteres": [{"id": "1.1", "reponse": None}], "diagnostic_rapide_apercu": {"questions": []}}
            audit_path = audit_dir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            # Appeler le script sans drapeau mais avec output-dir hors audits/
            result = subprocess.run(
                [sys.executable, __file__, str(audit_dir), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                echecs.append(("Acceptation sans drapeau hors audits", f"Code sortie attendu 0, obtenu {result.returncode}. stderr: {result.stderr}"))
            elif not (output_dir / "questionnaire-eof.md").exists():
                echecs.append(("Acceptation sans drapeau hors audits", "Fichier questionnaire-eof.md non cree"))
    except Exception as exc:
        echecs.append(("Acceptation sans drapeau hors audits", f"Exception : {exc}"))

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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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
                    {"id": "bloc-detail", "fichier": "produit-usage", "phase": "detail", "titre": "Test", "interlocuteur": "le responsable produit", "type": "direct", "critere": "1.1", "question": "Detail ?"},
                    {"id": "bloc-porte", "fichier": "produit-usage", "phase": "porte", "titre": "Test", "interlocuteur": "le responsable produit", "type": "direct", "critere": "0.1", "question": "Porte ?"}
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

            result = generate_questionnaire_unique(blocs, audit,
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

    # Cas 15 : Emprunt 3 - le titre du bloc porte le sujet et l'interlocuteur
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "1.1", "pilier": "🛖 1 — Produit", "critere": "C", "potentiel_max": 2.0,
                     "options_evaluation": ["✅ Point fort confirmé", "💡 Potentiel d'amélioration identifié"],
                     "options_evaluation_coefficient": {"✅ Point fort confirmé": 0,
                                                        "💡 Potentiel d'amélioration identifié": 1}}
                ],
                "diagnostic_rapide": []
            }
            (tmpdir / "eof-referentiel.json").write_text(
                json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {"version": 1, "blocs": [
                {"id": "b-titre", "fichier": "produit-usage", "phase": "detail",
                 "titre": "Appareils anciens",
                 "interlocuteur": "le responsable produit",
                 "type": "direct", "critere": "1.1", "question": "Q ?"}
            ]}
            (tmpdir / "questionnaire-blocs.json").write_text(
                json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            (tmpdir / "eof-audit-results.json").write_text(
                json.dumps({"criteres": [{"id": "1.1", "reponse": None, "contexte": None}],
                            "diagnostic_rapide_apercu": {"questions": []}},
                           ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(tmpdir / "eof-referentiel.json")
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)
            if result is None:
                echecs.append(("Emprunt 3 - titre de bloc", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                attendu = "## 1 sur 1 - Appareils anciens (à voir avec le responsable produit)"
                if attendu not in content:
                    echecs.append(("Emprunt 3 - titre de bloc",
                                   f"Ligne de titre absente : {attendu}"))
                # La plomberie interne ne doit pas revenir sous les yeux du lecteur
                if "**Critères EOF couverts" in content or "**Potentiel débloqué" in content:
                    echecs.append(("Emprunt 3 - titre de bloc",
                                   "Plomberie interne affichée au lecteur"))
    except Exception as exc:
        echecs.append(("Emprunt 3 - titre de bloc", f"Exception : {exc}"))

    # Cas 16 : Bloc filtre imprimé (aucun critère tranché)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "4.1", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}},
                    {"id": "4.2", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}}
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "filtre-test",
                        "fichier": "technique",
                        "phase": "porte",
                        "titre": "Test filtre",
                        "interlocuteur": "la personne qui gère les données",
                        "type": "filtre",
                        "criteres": ["4.1", "4.2"],
                        "question": "Question filtre ?",
                        "libelle_ecarte": "Non applicable",
                        "libelle_applicable": "Cela s'applique"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # Aucun critère tranché : le filtre doit être imprimé
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

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc filtre imprimé", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                if "<!-- bloc:filtre-test -->" not in content:
                    echecs.append(("Bloc filtre imprimé", "Marqueur bloc filtre absent"))
                if "<!-- opt:ecarte -->" not in content:
                    echecs.append(("Bloc filtre imprimé", "Marqueur opt:ecarte absent"))
                if "<!-- opt:applicable -->" not in content:
                    echecs.append(("Bloc filtre imprimé", "Marqueur opt:applicable absent"))
                if "Non applicable" not in content:
                    echecs.append(("Bloc filtre imprimé", "Libellé écarte absent"))
    except Exception as exc:
        echecs.append(("Bloc filtre imprimé", f"Exception : {exc}"))

    # Cas 17 : Bloc filtre supprimé par la règle 4.2 (un critère déjà tranché)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "1.5", "potentiel_max": 1.0, "options_evaluation": ["✅ Point fort confirmé"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}},
                    {"id": "1.13", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}},
                    {"id": "2.1", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}}
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "filtre-interface",
                        "fichier": "produit-usage",
                        "phase": "porte",
                        "titre": "Interface utilisateur",
                        "interlocuteur": "le responsable produit",
                        "type": "filtre",
                        "criteres": ["1.5", "1.13"],
                        "question": "Le service a-t-il une interface ?",
                        "libelle_ecarte": "Non, pas d'interface",
                        "libelle_applicable": "Oui, il y a une interface"
                    },
                    {
                        "id": "bloc-autre",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Autre bloc",
                        "interlocuteur": "l'équipe de développement",
                        "type": "direct",
                        "critere": "2.1",
                        "question": "Question autre ?"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # 1.5 est tranché : le filtre doit être supprimé, mais le bloc autre reste
            audit_data = {
                "criteres": [
                    {"id": "1.5", "reponse": "✅ Point fort confirmé", "coefficient": 0},
                    {"id": "1.13", "reponse": None},
                    {"id": "2.1", "reponse": None}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc filtre supprimé règle 4.2", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                if "<!-- bloc:filtre-interface -->" in content:
                    echecs.append(("Bloc filtre supprimé règle 4.2", "Filtre présent alors qu'il devrait être supprimé"))
                if "<!-- bloc:bloc-autre -->" not in content:
                    echecs.append(("Bloc filtre supprimé règle 4.2", "Bloc autre absent"))
    except Exception as exc:
        echecs.append(("Bloc filtre supprimé règle 4.2", f"Exception : {exc}"))

    # Cas 18 : Bloc filtre avec réponse "🤔 À évaluer" (ne supprime pas le filtre)
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "3.8", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}},
                    {"id": "3.9", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}}
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "filtre-env-test",
                        "fichier": "technique",
                        "phase": "porte",
                        "titre": "Environnement de test",
                        "interlocuteur": "la personne qui exploite l'infrastructure",
                        "type": "filtre",
                        "criteres": ["3.8", "3.9"],
                        "question": "Avez-vous des environnements de test ?",
                        "libelle_ecarte": "Non",
                        "libelle_applicable": "Oui"
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            # 3.8 a une réponse non tranchante : le filtre doit être imprimé
            audit_data = {
                "criteres": [
                    {"id": "3.8", "reponse": "🤔 À évaluer", "coefficient": 0},
                    {"id": "3.9", "reponse": None}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc filtre avec À évaluer", "Aucun fichier généré"))
            else:
                content = result.read_text(encoding="utf-8")
                if "<!-- bloc:filtre-env-test -->" not in content:
                    echecs.append(("Bloc filtre avec À évaluer", "Filtre absent alors qu'il devrait être imprimé (réponse non tranchante)"))
    except Exception as exc:
        echecs.append(("Bloc filtre avec À évaluer", f"Exception : {exc}"))

    # Cas 19 : Bloc totalement gouverné qui reçoit la mention "À IGNORER"
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "4.1", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}},
                    {"id": "4.2", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}}
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "filtre-donnees",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Stockage de donnees du service",
                        "interlocuteur": "la personne qui gère les données",
                        "type": "filtre",
                        "criteres": ["4.1", "4.2"],
                        "question": "Avez-vous des donnees ?",
                        "libelle_ecarte": "Non, le service ne conserve aucune donnee",
                        "libelle_applicable": "Oui"
                    },
                    {
                        "id": "bloc-4.1",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Critere 4.1",
                        "interlocuteur": "la personne qui gère les données",
                        "type": "direct",
                        "critere": "4.1",
                        "question": "Question 4.1 ?"
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

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc totalement gouverne avec mention", "Aucun fichier genere"))
            else:
                content = result.read_text(encoding="utf-8")
                if "**A IGNORER**" not in content:
                    echecs.append(("Bloc totalement gouverne avec mention", "Mention 'A IGNORER' absente"))
                elif "la question 1 (Stockage de donnees du service)" not in content:
                    echecs.append(("Bloc totalement gouverne avec mention", "Reference au filtre absente ou incorrecte"))
    except Exception as exc:
        echecs.append(("Bloc totalement gouverne avec mention", f"Exception : {exc}"))

    # Cas 20 : Bloc partiellement gouverné qui ne reçoit pas la mention
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "4.1", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}},
                    {"id": "5.1", "potentiel_max": 1.0, "options_evaluation": ["✅ Point fort confirmé"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0}}
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "filtre-donnees",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Stockage",
                        "interlocuteur": "la personne qui gère les données",
                        "type": "filtre",
                        "criteres": ["4.1"],
                        "question": "Avez-vous des donnees ?",
                        "libelle_ecarte": "Non",
                        "libelle_applicable": "Oui"
                    },
                    {
                        "id": "bloc-compose",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Bloc compose",
                        "interlocuteur": "l'équipe de développement",
                        "type": "compose",
                        "question": "Question ?",
                        "options": [
                            {"libelle": "Option A", "reponses": {"4.1": "✅ Point fort confirmé", "5.1": "✅ Point fort confirmé"}}
                        ]
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteres": [
                    {"id": "4.1", "reponse": None},
                    {"id": "5.1", "reponse": None}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc partiellement gouverne sans mention", "Aucun fichier genere"))
            else:
                content = result.read_text(encoding="utf-8")
                # Trouver le bloc compose dans le contenu
                if "bloc-compose" in content:
                    # Extraire la section du bloc compose
                    bloc_debut = content.find("<!-- bloc:bloc-compose -->")
                    bloc_fin = content.find("##", bloc_debut + 1) if bloc_debut >= 0 else -1
                    bloc_section = content[bloc_debut:bloc_fin] if bloc_fin > bloc_debut else content[bloc_debut:]

                    if "**A IGNORER**" in bloc_section:
                        echecs.append(("Bloc partiellement gouverne sans mention", "Mention presente alors qu'elle ne devrait pas (bloc partiellement gouverne)"))
    except Exception as exc:
        echecs.append(("Bloc partiellement gouverne sans mention", f"Exception : {exc}"))

    # Cas 21 : Bloc gouverné par deux filtres avec conjonction ET
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "3.8", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}},
                    {"id": "3.9", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}},
                    {"id": "4.4", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}}
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "filtre-env",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Environnements de test",
                        "interlocuteur": "la personne qui exploite l'infrastructure",
                        "type": "filtre",
                        "criteres": ["3.8", "3.9"],
                        "question": "Question env ?",
                        "libelle_ecarte": "Non",
                        "libelle_applicable": "Oui"
                    },
                    {
                        "id": "filtre-donnees",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Donnees persistantes",
                        "interlocuteur": "la personne qui gère les données",
                        "type": "filtre",
                        "criteres": ["4.4"],
                        "question": "Question donnees ?",
                        "libelle_ecarte": "Non",
                        "libelle_applicable": "Oui"
                    },
                    {
                        "id": "bloc-compose",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Environnements de test",
                        "interlocuteur": "la personne qui exploite l'infrastructure",
                        "type": "compose",
                        "question": "Question compose ?",
                        "options": [
                            {"libelle": "Option A", "reponses": {"3.9": "✅ Point fort confirmé", "4.4": "✅ Point fort confirmé"}}
                        ]
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteres": [
                    {"id": "3.8", "reponse": None},
                    {"id": "3.9", "reponse": None},
                    {"id": "4.4", "reponse": None}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Bloc gouverne par deux filtres avec ET", "Aucun fichier genere"))
            else:
                content = result.read_text(encoding="utf-8")
                if " ET " not in content:
                    echecs.append(("Bloc gouverne par deux filtres avec ET", "Conjonction 'ET' absente de la mention"))
    except Exception as exc:
        echecs.append(("Bloc gouverne par deux filtres avec ET", f"Exception : {exc}"))

    # Cas 22 : Filtre toujours placé avant les blocs qu'il gouverne
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "4.1", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}},
                    {"id": "4.2", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}}
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "filtre-donnees",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Stockage",
                        "interlocuteur": "la personne qui gère les données",
                        "type": "filtre",
                        "criteres": ["4.1", "4.2"],
                        "question": "Avez-vous des donnees ?",
                        "libelle_ecarte": "Non",
                        "libelle_applicable": "Oui"
                    },
                    {
                        "id": "bloc-4.1",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Critere 4.1",
                        "interlocuteur": "la personne qui gère les données",
                        "type": "direct",
                        "critere": "4.1",
                        "question": "Question 4.1 ?"
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

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Filtre avant les blocs gouvernes", "Aucun fichier genere"))
            else:
                content = result.read_text(encoding="utf-8")
                pos_filtre = content.find("<!-- bloc:filtre-donnees -->")
                pos_bloc = content.find("<!-- bloc:bloc-4.1 -->")
                if pos_filtre == -1 or pos_bloc == -1:
                    echecs.append(("Filtre avant les blocs gouvernes", "Blocs absents"))
                elif pos_filtre > pos_bloc:
                    echecs.append(("Filtre avant les blocs gouvernes", f"Filtre apres le bloc gouverne (positions : {pos_filtre} > {pos_bloc})"))
    except Exception as exc:
        echecs.append(("Filtre avant les blocs gouvernes", f"Exception : {exc}"))

    # Cas 23 : Mention "À IGNORER" avec deux filtres porte les deux libellés distincts
    total += 1
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            ref_data = {
                "criteres": [
                    {"id": "3.9", "potentiel_max": 1.5, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}},
                    {"id": "4.4", "potentiel_max": 2.0, "options_evaluation": ["✅ Point fort confirmé", "🚫 Non applicable"], "options_evaluation_coefficient": {"✅ Point fort confirmé": 0, "🚫 Non applicable": 0}}
                ],
                "diagnostic_rapide": []
            }
            ref_path = tmpdir / "eof-referentiel.json"
            ref_path.write_text(json.dumps(ref_data, ensure_ascii=False), encoding="utf-8")

            blocs_data = {
                "version": 1,
                "blocs": [
                    {
                        "id": "filtre-donnees",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Stockage de donnees du service",
                        "interlocuteur": "la personne qui gère les données",
                        "type": "filtre",
                        "criteres": ["4.4"],
                        "question": "Question donnees ?",
                        "libelle_ecarte": "Non, le service ne conserve aucune donnee (ni base de donnees, ni stockage objet)",
                        "libelle_applicable": "Oui"
                    },
                    {
                        "id": "filtre-env",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Environnements de test",
                        "interlocuteur": "la personne qui exploite l'infrastructure",
                        "type": "filtre",
                        "criteres": ["3.9"],
                        "question": "Question env ?",
                        "libelle_ecarte": "Non, pas d'environnement de pre-production distinct (tous les tests en local ou en production)",
                        "libelle_applicable": "Oui"
                    },
                    {
                        "id": "bloc-compose",
                        "fichier": "technique",
                        "phase": "detail",
                        "titre": "Gestion des environnements de test",
                        "interlocuteur": "la personne qui exploite l'infrastructure",
                        "type": "compose",
                        "question": "Question compose ?",
                        "options": [
                            {"libelle": "Option A", "reponses": {"3.9": "✅ Point fort confirmé", "4.4": "✅ Point fort confirmé"}}
                        ]
                    }
                ]
            }
            blocs_path = tmpdir / "questionnaire-blocs.json"
            blocs_path.write_text(json.dumps(blocs_data, ensure_ascii=False), encoding="utf-8")

            audit_data = {
                "criteres": [
                    {"id": "3.9", "reponse": None},
                    {"id": "4.4", "reponse": None}
                ],
                "diagnostic_rapide_apercu": {"questions": []}
            }
            audit_path = tmpdir / "eof-audit-results.json"
            audit_path.write_text(json.dumps(audit_data, ensure_ascii=False), encoding="utf-8")

            criteres_ref, diag_ref = load_referentiel(ref_path)
            audit, contextes = load_audit_results(tmpdir)
            blocs = load_blocs(tmpdir)

            result = generate_questionnaire_unique(blocs, audit,
                                                criteres_ref, diag_ref, tmpdir, contextes)

            if result is None:
                echecs.append(("Mention deux filtres avec deux libelles", "Aucun fichier genere"))
            else:
                content = result.read_text(encoding="utf-8")
                # Vérifier que les deux libellés apparaissent dans la mention
                libelle_donnees = "Non, le service ne conserve aucune donnee"
                libelle_env = "Non, pas d'environnement de pre-production distinct"

                if libelle_donnees not in content:
                    echecs.append(("Mention deux filtres avec deux libelles", f"Libelle du filtre donnees absent : {libelle_donnees}"))
                if libelle_env not in content:
                    echecs.append(("Mention deux filtres avec deux libelles", f"Libelle du filtre env absent : {libelle_env}"))
                # Vérifier que la conjonction ET est présente
                if " ET " not in content:
                    echecs.append(("Mention deux filtres avec deux libelles", "Conjonction 'ET' absente"))
    except Exception as exc:
        echecs.append(("Mention deux filtres avec deux libelles", f"Exception : {exc}"))

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
        description="Génère un questionnaire EOF depuis un audit existant")
    parser.add_argument("repertoire_audit", nargs="?",
                        help="dossier d'audit contenant eof-audit-results.json")
    parser.add_argument("--output-dir",
                        help="répertoire de sortie (par défaut : repertoire_audit)")
    parser.add_argument("--dans-le-dossier-audit", action="store_true",
                        help="autorise l'écriture dans un chemin contenant 'audits'")
    parser.add_argument("--autotest", action="store_true",
                        help="rejoue les cas de test embarqués et sort 1 si un cas échoue")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())

    if not args.repertoire_audit:
        parser.error("repertoire_audit est requis (ou utiliser --autotest)")

    audit_dir = Path(args.repertoire_audit).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else audit_dir

    # Garde-fou : refuser d'écrire dans audits/ sans drapeau explicite
    if "audits" in output_dir.parts and not args.dans_le_dossier_audit:
        print(
            "ERREUR : Ce script refuse d'écrire dans un chemin contenant 'audits'.\n"
            "\n"
            "RAISON : Un questionnaire généré est VIERGE, toutes ses cases restent à cocher.\n"
            "Seul un questionnaire revenu REMPLI du client a le droit d'exister dans\n"
            "audits/<domaine>/. Un questionnaire vierge dans ce dossier peut être envoyé\n"
            "au client comme s'il était à jour, alors qu'il ne contient aucune réponse.\n"
            "\n"
            "SOLUTION :\n"
            "  - Pour générer sans risque : --output-dir /tmp/questionnaire-<domaine>\n"
            "  - Pour forcer (si vous savez ce que vous faites) : --dans-le-dossier-audit\n",
            file=sys.stderr
        )
        sys.exit(2)

    # Charger les données
    ref_path = find_referentiel()
    criteres_ref, diag_rapide_ref = load_referentiel(ref_path)
    audit_results, contextes = load_audit_results(audit_dir)

    # Trouver la bibliothèque de blocs
    scripts_dir = Path(__file__).resolve().parent
    blocs_data = load_blocs(scripts_dir)

    # Générer le questionnaire unique
    result = generate_questionnaire_unique(blocs_data, audit_results,
                                          criteres_ref, diag_rapide_ref, output_dir, contextes)
    if result:
        print(f"Généré : {result}")
    else:
        print("Aucun bloc à afficher (résidu vide)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
