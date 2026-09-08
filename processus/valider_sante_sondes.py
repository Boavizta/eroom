#!/usr/bin/env python3
"""
Validateur de santé des sondes d'extraction dans un dossier d'audit.

POURQUOI CE SCRIPT EXISTE
-------------------------
Les extracteurs confondent deux choses : un service qui n'a pas la chose cherchée
(résultat d'audit légitime) et un échec de notre outil (timeout réseau, fichier
illisible, API quota dépassé). Cette confusion produit des chiffres faux au
lecteur : un timeout sur robots.txt rend `present: False`, exactement comme un
vrai 404. Un DOM à zéro balises (capture sans corps HTML) fabrique un EcoIndex
artificiellement flatteur.

La convention d'état de mesure (documentation/implementation/convention-etat-de-mesure.md)
résout cela en séparant les deux destinations :
  - Interne : bloc `mesure` avec `statut` (`ok`, `rien_trouve`, `echec_*`)
  - Client : `reponse: null` si échec, jamais de chiffre inventé

Ce script contrôle la santé d'un dossier d'audit complet : il relit tous les
JSON produits, ramasse tous les blocs `mesure`, et **sort en 1 si un seul
échec d'extracteur est présent**. Un échec de sonde signale que nous ne savons
pas, donc le livrable ne peut pas être publié en l'état.

`rien_trouve` n'est PAS un échec : la sonde a bien cherché, la chose est
réellement absente, c'est un résultat d'audit.

CE QU'IL CONTRÔLE
-----------------
1. Parcourt récursivement tous les fichiers JSON d'un dossier d'audit
2. Trouve tous les blocs `mesure` (à n'importe quelle profondeur)
3. Décompte par statut : global et par fichier
4. Liste détaillée des `echec_*` uniquement (pas des `rien_trouve`)
5. Signale (sans faire échouer) : statut invalide, bloc sans `cible`
6. JSON invalide = sortie en 1 (un audit cassé est un problème de santé)

VALEURS DE STATUT AUTORISÉES
-----------------------------
  ok            - mesuré avec succès
  rien_trouve   - la sonde a bien cherché, la chose est absente (RÉSULTAT D'AUDIT)
  echec_reseau  - timeout, DNS, connexion refusée, quota d'API
  echec_lecture - fichier absent, encodage cassé, JSON invalide
  echec_analyse - ressource lue mais inexploitable (champ attendu absent)

Usage :
    python3 valider_sante_sondes.py audits/<domaine>
    python3 valider_sante_sondes.py audits/<domaine> --liste-fichiers

Code de sortie : 0 si aucun échec, 1 si au moins un échec ou anomalie structurelle.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


# Valeurs de statut autorisées (cf. convention section 3)
VALID_STATUSES = {"ok", "rien_trouve", "echec_reseau", "echec_lecture", "echec_analyse"}

# Statuts qui constituent des échecs (la sonde n'a pas réussi)
FAILURE_STATUSES = {"echec_reseau", "echec_lecture", "echec_analyse"}


def find_mesure_blocks(data, path="", file_path=""):
    """Parcourt récursivement une structure JSON et trouve tous les blocs `mesure`.

    Retourne une liste de (fichier, chemin, statut, cible, detail).

    Cette fonction ne présume pas de l'emplacement des blocs : ils peuvent être
    à n'importe quelle profondeur, dans des dicts ou des listes.
    """
    results = []

    if isinstance(data, dict):
        # Si c'est un bloc mesure (contient la clé 'statut' directement dans 'mesure')
        if "mesure" in data and isinstance(data["mesure"], dict) and "statut" in data["mesure"]:
            mesure = data["mesure"]
            statut = mesure.get("statut")
            cible = mesure.get("cible")
            detail = mesure.get("detail")
            results.append((file_path, path + ".mesure", statut, cible, detail))

        # Continuer la recherche dans tous les champs
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            results.extend(find_mesure_blocks(value, new_path, file_path))

    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path = f"{path}[{i}]"
            results.extend(find_mesure_blocks(item, new_path, file_path))

    return results


def validate_audit_directory(audit_dir: Path, list_files: bool = False):
    """Valide la santé des sondes dans un dossier d'audit.

    Retourne un tuple (code_de_sortie, rapport_texte).
    """
    if not audit_dir.exists():
        return 1, f"[ERREUR] Dossier d'audit introuvable : {audit_dir}"

    if not audit_dir.is_dir():
        return 1, f"[ERREUR] Le chemin n'est pas un dossier : {audit_dir}"

    # Trouver tous les fichiers JSON récursivement
    json_files = sorted(audit_dir.rglob("*.json"))

    if not json_files:
        return 0, f"[info] Aucun fichier JSON trouvé dans {audit_dir}\n"

    # Option --liste-fichiers
    if list_files:
        output = []
        output.append(f"[info] {len(json_files)} fichier(s) JSON trouvé(s) dans {audit_dir}")
        output.append("")
        total_blocs = 0
        for json_file in json_files:
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                blocs = find_mesure_blocks(data, file_path=str(json_file.relative_to(audit_dir)))
                total_blocs += len(blocs)
                output.append(f"    {json_file.relative_to(audit_dir)} : {len(blocs)} bloc(s) mesure")
            except (json.JSONDecodeError, OSError) as exc:
                output.append(f"    {json_file.relative_to(audit_dir)} : ERREUR ({type(exc).__name__})")
        output.append("")
        output.append(f"[info] Total : {total_blocs} bloc(s) mesure trouvé(s)")
        return 0, "\n".join(output)

    # Collecter tous les blocs mesure
    all_mesures = []
    json_errors = []

    for json_file in json_files:
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            blocs = find_mesure_blocks(data, file_path=str(json_file.relative_to(audit_dir)))
            all_mesures.extend(blocs)
        except json.JSONDecodeError as exc:
            json_errors.append((json_file.relative_to(audit_dir), f"JSON invalide ligne {exc.lineno}"))
        except OSError as exc:
            json_errors.append((json_file.relative_to(audit_dir), f"Lecture impossible : {exc}"))

    # Si des fichiers JSON sont cassés, c'est un échec immédiat
    if json_errors:
        output = []
        output.append(f"[ÉCHEC] {len(json_errors)} fichier(s) JSON illisible(s) :")
        for file_path, error in json_errors:
            output.append(f"    - {file_path} : {error}")
        output.append("")
        output.append("Un JSON cassé dans un dossier d'audit est un problème de santé.")
        return 1, "\n".join(output)

    # Si aucun bloc mesure trouvé
    if not all_mesures:
        output = []
        output.append(f"[info] {len(json_files)} fichier(s) JSON analysé(s)")
        output.append("")
        output.append("[AVERTISSEMENT] Aucun bloc mesure trouvé.")
        output.append("")
        output.append("Soit les extracteurs n'ont pas encore été rejoués avec la convention,")
        output.append("soit ce dossier est antérieur à la convention d'état de mesure.")
        output.append("")
        output.append("Utilisez --liste-fichiers pour voir quels fichiers ont été analysés.")
        return 0, "\n".join(output)

    # Décomptes et analyses
    status_counts: Dict[str, int] = {}
    status_by_file: Dict[str, Dict[str, int]] = {}
    failures: List[Tuple[str, str, str, str, str]] = []  # (fichier, chemin, statut, cible, detail)
    invalid_statuses: List[Tuple[str, str, str]] = []  # (fichier, chemin, statut)
    missing_cibles: List[Tuple[str, str]] = []  # (fichier, chemin)

    for file_path, path, statut, cible, detail in all_mesures:
        # Décompte global
        status_counts[statut] = status_counts.get(statut, 0) + 1

        # Décompte par fichier
        if file_path not in status_by_file:
            status_by_file[file_path] = {}
        status_by_file[file_path][statut] = status_by_file[file_path].get(statut, 0) + 1

        # Vérifier statut valide
        if statut not in VALID_STATUSES:
            invalid_statuses.append((file_path, path, statut))

        # Vérifier présence de cible
        if cible is None:
            missing_cibles.append((file_path, path))

        # Collecter les échecs
        if statut in FAILURE_STATUSES:
            failures.append((file_path, path, statut, cible or "?", detail or ""))

    # Construction du rapport
    output = []
    output.append("-" * 70)
    output.append("  SANTÉ DES SONDES D'EXTRACTION")
    output.append(f"  Dossier : {audit_dir.name}")
    output.append("-" * 70)
    output.append("")

    # Décompte global
    output.append(f"[info] {len(json_files)} fichier(s) JSON, {len(all_mesures)} bloc(s) mesure")
    output.append("")
    output.append("Décompte global par statut :")
    for statut in sorted(status_counts.keys()):
        count = status_counts[statut]
        output.append(f"    {statut:20} : {count:4}")
    output.append("")

    # Décompte par fichier
    output.append("Décompte par fichier :")
    for file_path in sorted(status_by_file.keys()):
        counts = status_by_file[file_path]
        counts_str = ", ".join(f"{s}={c}" for s, c in sorted(counts.items()))
        output.append(f"    {file_path} : {counts_str}")
    output.append("")

    # Anomalies de forme (ne font pas échouer)
    has_form_anomalies = False

    if invalid_statuses:
        has_form_anomalies = True
        output.append(f"[AVERTISSEMENT] {len(invalid_statuses)} statut(s) invalide(s) détecté(s) :")
        for file_path, path, statut in invalid_statuses:
            output.append(f"    - {file_path} > {path}")
            output.append(f"      statut = '{statut}' (valeurs autorisées : {', '.join(sorted(VALID_STATUSES))})")
        output.append("")

    if missing_cibles:
        has_form_anomalies = True
        output.append(f"[AVERTISSEMENT] {len(missing_cibles)} bloc(s) mesure sans cible :")
        for file_path, path in missing_cibles:
            output.append(f"    - {file_path} > {path}")
        output.append("")

    if has_form_anomalies:
        output.append("Ces anomalies signalent un extracteur mal posé, mais ne constituent")
        output.append("pas un échec de santé (la distinction compte pour l'orchestration).")
        output.append("")

    # Échecs de sonde (font échouer)
    if failures:
        output.append(f"[ÉCHEC] {len(failures)} sonde(s) en échec :")
        output.append("")
        for file_path, path, statut, cible, detail in failures:
            output.append(f"    Fichier : {file_path}")
            output.append(f"    Chemin  : {path}")
            output.append(f"    Statut  : {statut}")
            output.append(f"    Cible   : {cible}")
            if detail:
                output.append(f"    Détail  : {detail}")
            output.append("")
        output.append("Un échec d'extracteur signale que nous ne savons pas. Le livrable ne peut")
        output.append("pas être publié en l'état : soit relancer l'extracteur, soit marquer le")
        output.append("critère comme non répondu dans le questionnaire.")
        return 1, "\n".join(output)

    # Succès
    rien_trouve_count = status_counts.get("rien_trouve", 0)
    ok_count = status_counts.get("ok", 0)

    output.append(f"[OK] Aucun échec de sonde détecté")
    if ok_count > 0:
        output.append(f"[OK] {ok_count} mesure(s) réussie(s)")
    if rien_trouve_count > 0:
        output.append(f"[OK] {rien_trouve_count} absence(s) confirmée(s) (résultats d'audit légitimes)")
    output.append("")
    output.append("[SUCCÈS] La santé des sondes est bonne. Le dossier d'audit peut être publié.")

    return 0, "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Valide la santé des sondes d'extraction dans un dossier d'audit. "
                    "Sort en 1 si un seul échec de sonde est présent.",
        epilog="Rappel : 'rien_trouve' n'est PAS un échec (c'est un résultat d'audit).",
    )
    parser.add_argument(
        "audit_dir",
        type=Path,
        nargs="?",
        help="Chemin du dossier d'audit à contrôler",
    )
    parser.add_argument(
        "--liste-fichiers",
        action="store_true",
        help="Affiche la liste des fichiers JSON trouvés et leur nombre de blocs mesure",
    )
    args = parser.parse_args()

    if not args.audit_dir:
        parser.print_help()
        print()
        print("Erreur : un dossier d'audit est requis.")
        print()
        print("Exemples :")
        print("    python3 valider_sante_sondes.py audits/octo.com")
        print("    python3 valider_sante_sondes.py audits/example.org --liste-fichiers")
        return 2

    exit_code, report = validate_audit_directory(args.audit_dir, args.liste_fichiers)
    print(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
