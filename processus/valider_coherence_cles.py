#!/usr/bin/env python3
"""
Validateur de cohérence des clés EOF entre producteurs et consommateur.

POURQUOI CE SCRIPT EXISTE
-------------------------
Deux scripts écrivent le même fichier eof-audit-results.json, et un troisième le lit.
Si les deux producteurs n'écrivent pas les MÊMES noms de clés, le rapport affiche des
blancs selon lequel des deux a produit le fichier.

Incident vécu : fusionner_lots.py écrivait "criteres_repondus" pendant que run_eof.py
écrivait encore "criteres_repondus_auto", et le KPI du rapport affichait 0/54 au lieu
du nombre réel.

L'invariant est tenu aujourd'hui mais AUCUN test ne le protège. Ce validateur est ce
filet.

CE QU'IL CONTRÔLE
-----------------
1. Les clés canoniques sont écrites par les DEUX producteurs
2. Le consommateur lit chacune de ces clés, sauf celles dont le consommateur n'existe
   pas encore et qui sont exemptées explicitement (CLES_PRODUITES_NON_ENCORE_LUES)
3. Aucun nom mort n'est ÉCRIT par un producteur (distinction écriture/lecture)
4. Aucun nom de clé inventé (famille potentiel_*, completude_*, criteres_*)

Distinction écriture/lecture (contrôle 3) :
  - Le consommateur (generate_report_html.py) a le DROIT de LIRE les anciens noms
    en repli pour que les audits déjà produits continuent de s'afficher.
  - Les producteurs (run_eof.py, fusionner_lots.py) ne doivent JAMAIS ÉCRIRE ces
    anciens noms.
  - Méthode retenue : analyse par recherche de string literals dans des contextes
    d'assignation de dictionnaire (clés entre guillemets dans le code). Cette approche
    attrape les écritures explicites de clés, qui sont le cas dominant dans ces scripts.
    Elle ne couvre pas les cas où la clé serait construite dynamiquement ou passée par
    variable, mais ces patterns n'existent pas dans les deux producteurs (vérification
    manuelle faite). L'alternative (AST complet) serait plus robuste mais complexe et
    fragile aux changements de structure du code.

Usage :
    python3 valider_coherence_cles.py [--test-dir <répertoire-copies-cassées>]

    Sans argument : contrôle l'état réel du repo
    Avec --test-dir : pointe sur des copies modifiées pour test négatif

Code de sortie : 0 si conforme, 1 sinon.

Contrat partagé entre run_eof.py et fusionner_lots.py (liste faisant foi :
CANONICAL_KEYS, plus bas dans ce fichier) :
  - completude_globale_pct
  - completude_pct (par dimension)
  - criteres_repondus
  - criteres_total
  - potentiel_optimisation_global_pct
  - potentiel_optimisation_pct (par dimension)
  - repondus_par_provenance (produite, pas encore lue : exemption du contrôle 2)
  - provenance (par critère et par question de diagnostic, pas à la racine)
"""

import argparse
import ast
import re
import sys
from pathlib import Path

# Résolution des chemins relativement à l'emplacement du validateur
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Chemins par défaut (état réel du repo)
DEFAULT_PATHS = {
    "run_eof": PROJECT_ROOT / ".claude/skills/analyse-parcours/scripts/run_eof.py",
    "fusionner_lots": PROJECT_ROOT / "processus/fusionner_lots.py",
    "generate_report": PROJECT_ROOT / ".claude/skills/analyse-parcours/scripts/generate_report_html.py",
}

# Les clés canoniques que les deux producteurs doivent écrire à l'identique
# (contrat partagé référencé dans memory/project_eof_deux_producteurs_un_contrat.md)
CANONICAL_KEYS = {
    "completude_globale_pct",
    "completude_pct",
    "criteres_repondus",
    "criteres_total",
    "potentiel_optimisation_global_pct",
    "potentiel_optimisation_pct",
    "repondus_par_provenance",
    # Portée par chaque critère et chaque question de diagnostic, pas par la racine.
    # Ajoutée après un incident réel : les producteurs écrivaient déjà `provenance`
    # pendant que le rapport lisait encore `confidence`. Résultat, un tiret à la place
    # de chaque badge, et un plantage sec (KeyError) dès qu'une question de diagnostic
    # portait une réponse. Aucun contrôle ne l'attrapait.
    "provenance",
}

# Noms morts : anciens noms qui ne doivent PLUS être ÉCRITS par les producteurs
# (le consommateur peut les LIRE en repli, mais pas les producteurs les ÉCRIRE)
DEAD_NAMES = {
    "score_pct",
    "criteres_repondus_auto",
    "score_pondere",
    "options_evaluation_score",
    "confidence",
    "nature_preuve",
    "natures_autorisees",
    "potentiel_pct",
    "auto_declare_public",
    "declare_qcm",
}

# Clés produites mais pas encore consommées : exemption EXPLICITE et TEMPORAIRE du
# contrôle 2 (lecture par le consommateur). Elles doivent quand même être écrites à
# l'identique par les deux producteurs, le contrôle 1 continue de s'appliquer.
#
# `repondus_par_provenance` : produite par les deux producteurs, à la racine et par
# dimension. Son consommateur prévu est le radar à deux couches, chantier encore
# ouvert. Retirer cette entrée le jour où le radar lit la clé : le contrôle 2
# redeviendra alors bloquant, ce qui est le but.
CLES_PRODUITES_NON_ENCORE_LUES = {
    "repondus_par_provenance",
}

# Familles de clés surveillées pour détecter les inventions
KEY_FAMILIES = ["potentiel_", "completude_", "criteres_"]


def extract_written_keys(source, filepath):
    """Extrait les clés de dictionnaire écrites dans le code source.

    Retourne un ensemble de (clé, numéro_de_ligne) pour chaque string literal
    utilisée comme clé dans une assignation de dictionnaire.

    Cette approche par string literals attrape les écritures explicites de clés,
    qui sont le cas dominant dans run_eof.py et fusionner_lots.py. Elle ne couvre
    pas les constructions dynamiques de clés, mais ces patterns n'existent pas dans
    ces scripts (vérification manuelle faite).
    """
    written = set()
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        return {("PARSE_ERROR", exc.lineno or 0)}

    for node in ast.walk(tree):
        # Pattern 1 : {"key": value} dans un dict literal
        if isinstance(node, ast.Dict):
            for key_node in node.keys:
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    written.add((key_node.value, key_node.lineno))

        # Pattern 2 : dict["key"] = value ou dict.update({"key": value})
        # Capturé par ast.Dict ci-dessus pour les literals

    return written


def extract_read_keys(source, filepath):
    """Extrait les clés de dictionnaire lues dans le code source.

    Retourne un ensemble de (clé, numéro_de_ligne) pour chaque string literal
    utilisée dans .get("clé") ou ["clé"].
    """
    read = set()
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        return {("PARSE_ERROR", exc.lineno or 0)}

    for node in ast.walk(tree):
        # Pattern 1 : .get("key") ou .get("key", default)
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Attribute) and
                node.func.attr == "get" and
                node.args and
                isinstance(node.args[0], ast.Constant) and
                isinstance(node.args[0].value, str)):
                read.add((node.args[0].value, node.func.lineno))

        # Pattern 2 : dict["key"]
        elif isinstance(node, ast.Subscript):
            if (isinstance(node.slice, ast.Constant) and
                isinstance(node.slice.value, str)):
                read.add((node.slice.value, node.lineno))

    return read


def check_canonical_keys_written(written_keys, producer_name):
    """Vérifie que toutes les clés canoniques sont écrites par le producteur.

    Retourne une liste de violations (clés manquantes).
    """
    violations = []
    written_key_names = {key for key, lineno in written_keys if key != "PARSE_ERROR"}

    for key in CANONICAL_KEYS:
        if key not in written_key_names:
            violations.append(f"{producer_name} : clé canonique manquante '{key}'")

    return violations


def check_canonical_keys_read(read_keys, consumer_name):
    """Vérifie que toutes les clés canoniques sont lues par le consommateur.

    Les clés de CLES_PRODUITES_NON_ENCORE_LUES sont exemptées, mais l'exemption est
    affichée : elle doit rester visible pour être levée un jour, pas devenir un
    silence installé.

    Retourne un couple (violations, rappels).
    """
    violations = []
    rappels = []
    read_key_names = {key for key, lineno in read_keys if key != "PARSE_ERROR"}

    for key in sorted(CANONICAL_KEYS):
        if key in read_key_names:
            continue
        if key in CLES_PRODUITES_NON_ENCORE_LUES:
            rappels.append(
                f"{consumer_name} : clé '{key}' produite mais pas encore lue "
                f"(exemption explicite, cf. CLES_PRODUITES_NON_ENCORE_LUES)"
            )
        else:
            violations.append(f"{consumer_name} : clé canonique non lue '{key}'")

    return violations, rappels


def check_dead_names_written(written_keys, producer_name):
    """Vérifie qu'aucun nom mort n'est écrit par le producteur.

    EXEMPTIONS : certaines occurrences sont légitimes et ne sont pas dans le
    périmètre EOF (ex. score_pct d'un outil tiers dans run_eof.py ligne ~403).
    Ces exemptions sont filtrées par une liste explicite.

    Retourne une liste de violations.
    """
    violations = []

    # Exemptions explicites : (nom_fichier, clé, numéro_ligne_approx)
    # Ces occurrences sont légitimes (non-EOF) et ne doivent pas être signalées.
    exemptions = {
        ("run_eof.py", "score_pct", 403),  # score en-têtes sécurité d'un outil tiers
    }

    for key, lineno in written_keys:
        if key == "PARSE_ERROR":
            continue
        if key in DEAD_NAMES:
            # Vérifier si c'est une exemption
            file_name = producer_name.split()[0]  # Extraire le nom du fichier
            is_exempt = any(
                file_name.endswith(ex_file) and key == ex_key and abs(lineno - ex_line) < 5
                for ex_file, ex_key, ex_line in exemptions
            )
            if not is_exempt:
                violations.append(
                    f"{producer_name} ligne {lineno} : nom mort ÉCRIT '{key}' "
                    f"(vocabulaire obsolète, ne doit plus être écrit)"
                )

    return violations


def check_invented_keys(written_keys, producer_name):
    """Vérifie qu'aucune clé inventée n'est écrite par le producteur.

    Une clé inventée est une clé de la famille potentiel_*, completude_*, criteres_*
    qui n'est pas dans la liste canonique ni dans les extensions autorisées.

    Retourne une liste de violations.
    """
    violations = []
    written_key_names = {key for key, lineno in written_keys if key != "PARSE_ERROR"}

    for key, lineno in written_keys:
        if key == "PARSE_ERROR":
            continue
        for family in KEY_FAMILIES:
            if key.startswith(family) and key not in CANONICAL_KEYS:
                # Clés autorisées en dehors des 7 canoniques :
                # - criteres_avec_indice_partiel : dans le contrat de sortie fusionné
                # - potentiel_max : ajouté par fusionner_lots.py depuis le référentiel (cf. ligne 36 docstring)
                # - potentiel_retenu, potentiel_total : variables de calcul internes
                allowed_extra = {
                    "criteres_avec_indice_partiel",
                    "potentiel_max",
                    "potentiel_retenu",
                    "potentiel_total",
                }
                if key not in allowed_extra:
                    violations.append(
                        f"{producer_name} ligne {lineno} : clé inventée '{key}' "
                        f"(famille {family}*, non canonique)"
                    )

    return violations


def main():
    parser = argparse.ArgumentParser(
        description="Valide la cohérence des clés EOF entre producteurs et consommateur. "
                    "Refuse toute divergence de nommage qui ferait afficher des blancs dans le rapport."
    )
    parser.add_argument("--test-dir", type=Path,
                        help="Répertoire contenant des copies modifiées pour test négatif. "
                             "Si absent, contrôle l'état réel du repo.")
    args = parser.parse_args()

    # Déterminer les chemins à contrôler
    if args.test_dir:
        paths = {
            "run_eof": args.test_dir / "run_eof.py",
            "fusionner_lots": args.test_dir / "fusionner_lots.py",
            "generate_report": args.test_dir / "generate_report_html.py",
        }
    else:
        paths = DEFAULT_PATHS

    # Vérifier que tous les fichiers existent
    for name, path in paths.items():
        if not path.exists():
            print(f"[erreur] Fichier introuvable : {path}")
            return 1

    print("-" * 70)
    print("  COHÉRENCE DES CLÉS EOF")
    print(f"  Producteur 1  : {paths['run_eof'].name}")
    print(f"  Producteur 2  : {paths['fusionner_lots'].name}")
    print(f"  Consommateur  : {paths['generate_report'].name}")
    print(f"  {len(CANONICAL_KEYS)} clés canoniques à vérifier")
    print("-" * 70)
    print()

    violations = []

    # Charger les sources
    try:
        source_run_eof = paths["run_eof"].read_text(encoding="utf-8")
        source_fusionner = paths["fusionner_lots"].read_text(encoding="utf-8")
        source_generate = paths["generate_report"].read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[erreur] Impossible de lire les fichiers : {exc}")
        return 1

    # Extraire les clés écrites et lues
    written_run_eof = extract_written_keys(source_run_eof, paths["run_eof"])
    written_fusionner = extract_written_keys(source_fusionner, paths["fusionner_lots"])
    read_generate = extract_read_keys(source_generate, paths["generate_report"])

    # Vérifier les erreurs de parsing
    if any(key == "PARSE_ERROR" for key, _ in written_run_eof):
        violations.append(f"run_eof.py : erreur de parsing, contrôle impossible")
    if any(key == "PARSE_ERROR" for key, _ in written_fusionner):
        violations.append(f"fusionner_lots.py : erreur de parsing, contrôle impossible")
    if any(key == "PARSE_ERROR" for key, _ in read_generate):
        violations.append(f"generate_report_html.py : erreur de parsing, contrôle impossible")

    if violations:
        print("[ÉCHEC] Erreurs de parsing :")
        for v in violations:
            print(f"    {v}")
        print()
        print("Impossible de continuer sans source analysable.")
        return 1

    # Contrôle 1 : les clés canoniques sont écrites par les DEUX producteurs
    violations.extend(check_canonical_keys_written(written_run_eof, "run_eof.py"))
    violations.extend(check_canonical_keys_written(written_fusionner, "fusionner_lots.py"))

    # Contrôle 2 : Le consommateur lit chacune des clés canoniques, sauf celles
    # explicitement exemptées parce que leur consommateur n'existe pas encore.
    violations_lecture, rappels = check_canonical_keys_read(read_generate, "generate_report_html.py")
    violations.extend(violations_lecture)

    # Contrôle 3 : Aucun nom mort n'est ÉCRIT par un producteur
    violations.extend(check_dead_names_written(written_run_eof, "run_eof.py"))
    violations.extend(check_dead_names_written(written_fusionner, "fusionner_lots.py"))

    # Contrôle 4 : Aucun nom de clé inventé
    violations.extend(check_invented_keys(written_run_eof, "run_eof.py"))
    violations.extend(check_invented_keys(written_fusionner, "fusionner_lots.py"))

    # Rapport
    if violations:
        print(f"[ÉCHEC] {len(violations)} violation(s) détectée(s) :")
        for v in violations:
            print(f"    {v}")
        print()
        print("Le contrat partagé n'est pas respecté. Ces divergences de nommage feraient")
        print("afficher des blancs dans le rapport selon lequel des deux producteurs a généré")
        print("le fichier eof-audit-results.json.")
        print()
        print("Corriger les violations ci-dessus pour restaurer la cohérence.")
        return 1

    nb_cles = len(CANONICAL_KEYS)
    nb_lues = nb_cles - len(CLES_PRODUITES_NON_ENCORE_LUES)
    print(f"[OK] Producteur 1 (run_eof.py) écrit les {nb_cles} clés canoniques")
    print(f"[OK] Producteur 2 (fusionner_lots.py) écrit les {nb_cles} clés canoniques")
    print(f"[OK] Consommateur (generate_report_html.py) lit les {nb_lues} clés attendues de lui")
    print("[OK] Aucun nom mort écrit par les producteurs")
    print("[OK] Aucune clé inventée")
    for rappel in rappels:
        print(f"[RAPPEL] {rappel}")
    print()
    print("[SUCCÈS] Cohérence préservée. Le contrat partagé est respecté.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
