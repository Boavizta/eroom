#!/usr/bin/env python3
"""
Validation du manifeste de lots : contrôle d'intégrité du processus d'audit EOF.

POURQUOI CE SCRIPT EXISTE
-------------------------
Le manifeste est le contrat d'orchestration du processus d'audit. S'il est
incohérent (critère possédé par deux lots, dépendance cyclique, fichier de
sortie en doublon), tout le processus dérive en silence. Ce script détecte les
violations AVANT d'exécuter le premier lot.

Contrôles implémentés :
  1. Unicité des identifiants de lot
  2. Graphe de dépendances valide (IDs existants, acyclique)
  3. Cohérence des vagues avec le graphe
  4. Propriété disjointe des critères (le plus important)
  5. Référentiel existant et compte de critères
  6. Natures de preuve valides
  7. Sorties de lot uniques
  8. Fichiers référencés existants
  9. Exécuteurs et états valides

CONTRÔLE #4 : PROPRIÉTÉ DISJOINTE DES CRITÈRES
----------------------------------------------
Chaque critère du référentiel doit être possédé par EXACTEMENT UN lot de
jugement. Deux lots possédant le même critère peuvent se contredire, et
l'ordre d'exécution devient déterminant sur le résultat (violation de la
propriété d'idempotence). Un critère possédé par aucun lot est orphelin et
ne sera jamais jugé.

Trois formes de possession :
  - {"prefixe_id": "3."} -> tous les critères du référentiel dont l'id
    commence par ce préfixe
  - {"source": "<chemin>", "regle": "..."} -> critères que la table de
    correspondance (eof_criteria_mapping.py) déclare automatisables ou partiels
  - {"regle": "..."} sans source ni prefixe_id -> ensemble COMPLÉMENT : tous
    les critères que personne d'autre ne possède

Usage :
    python3 valider_manifeste.py                        # défaut
    python3 valider_manifeste.py processus/manifeste-lots.json

Code de sortie : 0 si le manifeste est valide, 1 sinon.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "processus" / "manifeste-lots.json"

# Importer les fonctions de résolution de propriété depuis le module partagé
from propriete_criteres import (
    load_mapping,
    resolve_criteres_possedes,
    resolve_contextes_autorises,
    compute_ownership,
)


# ---------------------------------------------------------------------------
# Détection de cycles dans le graphe de dépendances
# ---------------------------------------------------------------------------

def detect_cycle(lots):
    """Retourne (est_acyclique, cycle_si_trouvé).

    Utilise une coloration tricolore pour détecter les cycles dans un graphe
    orienté : blanc (non visité), gris (en cours de visite), noir (visité).
    Un nœud gris rencontré depuis un nœud gris signale un cycle.
    """
    deps_by_id = {lot["id"]: lot.get("depends_on", []) for lot in lots}

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {lot_id: WHITE for lot_id in deps_by_id}
    parent = {}

    def visit(node, path):
        if color[node] == BLACK:
            return True, []
        if color[node] == GRAY:
            cycle_start = path.index(node)
            return False, path[cycle_start:] + [node]

        color[node] = GRAY
        path.append(node)

        for dep in deps_by_id[node]:
            if dep not in deps_by_id:
                continue
            acyclic, cycle = visit(dep, path)
            if not acyclic:
                return False, cycle

        path.pop()
        color[node] = BLACK
        return True, []

    for lot_id in deps_by_id:
        if color[lot_id] == WHITE:
            acyclic, cycle = visit(lot_id, [])
            if not acyclic:
                return False, cycle

    return True, []


# ---------------------------------------------------------------------------
# Résolution de la propriété des critères
# ---------------------------------------------------------------------------

def load_referentiel(path):
    """Charge le référentiel et retourne la liste des IDs de critères."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [c["id"] for c in data.get("criteres", [])]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


# ---------------------------------------------------------------------------
# Contrôles principaux
# ---------------------------------------------------------------------------

def check_manifest(manifest_path):
    """Valide le manifeste. Retourne le nombre d'erreurs."""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ERREUR] Manifeste illisible : {exc}")
        return 1

    lots = manifest.get("lots", [])
    vagues = manifest.get("vagues", [])
    conventions = manifest.get("conventions", {})
    referentiel_path = PROJECT_ROOT / manifest.get("referentiel", "")

    errors = 0

    print()
    print(f"[info] {len(lots)} lots déclarés, {len(vagues)} vagues.")
    print()

    # -----------------------------------------------------------------------
    # Contrôle 1 : Unicité des identifiants de lot
    # -----------------------------------------------------------------------
    lot_ids = [lot["id"] for lot in lots]
    duplicates = [lot_id for lot_id in set(lot_ids) if lot_ids.count(lot_id) > 1]

    if duplicates:
        print(f"[ERREUR] {len(duplicates)} identifiant(s) de lot en doublon :")
        for lot_id in sorted(duplicates):
            print(f"    - {lot_id}")
        print()
        errors += len(duplicates)
    else:
        print("[OK] Tous les identifiants de lot sont uniques.")

    # -----------------------------------------------------------------------
    # Contrôle 1b : Validation stricte des clés de chaque lot
    # -----------------------------------------------------------------------
    ALLOWED_LOT_KEYS = {
        "id", "vague", "libelle", "executeur", "etat", "scripts", "scripts_a_ecrire",
        "prompt", "arguments", "arguments_verifies", "depends_on", "entrees",
        "sorties_donnees", "sortie_de_lot", "provenances_autorisees", "criteres_possedes",
        "contextes_autorises", "rejouable_seul", "prerequis_humain", "contrainte",
        "note", "retour_attendu", "type", "decision"
    }

    unknown_keys_violations = []
    for lot in lots:
        lot_id = lot.get("id", "?")
        unknown_keys = set(lot.keys()) - ALLOWED_LOT_KEYS
        if unknown_keys:
            for key in sorted(unknown_keys):
                unknown_keys_violations.append((lot_id, key))

    if unknown_keys_violations:
        print(f"[ERREUR] {len(unknown_keys_violations)} clé(s) inconnue(s) dans des lots (validation stricte) :")
        for lot_id, key in unknown_keys_violations:
            print(f"    - lot '{lot_id}' : clé inconnue '{key}'")
        print()
        errors += len(unknown_keys_violations)
    else:
        print("[OK] Toutes les clés des lots sont reconnues.")

    # -----------------------------------------------------------------------
    # Contrôle 2 : Graphe de dépendances valide
    # -----------------------------------------------------------------------
    lot_ids_set = set(lot_ids)
    missing_deps = []
    for lot in lots:
        for dep in lot.get("depends_on", []):
            if dep not in lot_ids_set:
                missing_deps.append((lot["id"], dep))

    if missing_deps:
        print(f"[ERREUR] {len(missing_deps)} dépendance(s) vers des lots inexistants :")
        for lot_id, dep in missing_deps:
            print(f"    - lot '{lot_id}' dépend de '{dep}' (introuvable)")
        print()
        errors += len(missing_deps)
    else:
        print("[OK] Toutes les dépendances pointent vers des lots existants.")

    acyclic, cycle = detect_cycle(lots)
    if not acyclic:
        print(f"[ERREUR] Cycle détecté dans le graphe de dépendances :")
        print(f"    {' -> '.join(cycle)}")
        print()
        errors += 1
    else:
        print("[OK] Le graphe de dépendances est acyclique.")

    # -----------------------------------------------------------------------
    # Contrôle 3 : Cohérence des vagues avec le graphe
    # -----------------------------------------------------------------------
    vague_order = {v["id"]: i for i, v in enumerate(vagues)}
    vague_violations = []

    for lot in lots:
        lot_vague = lot.get("vague")
        if lot_vague not in vague_order:
            vague_violations.append((lot["id"], lot_vague, "vague inconnue"))
            continue

        lot_order = vague_order[lot_vague]
        for dep in lot.get("depends_on", []):
            dep_lot = next((l for l in lots if l["id"] == dep), None)
            if dep_lot is None:
                continue
            dep_vague = dep_lot.get("vague")
            if dep_vague not in vague_order:
                continue
            dep_order = vague_order[dep_vague]
            if dep_order > lot_order:
                vague_violations.append(
                    (lot["id"], dep, f"vague {lot_vague} dépend de vague {dep_vague} postérieure")
                )

    if vague_violations:
        print(f"[ERREUR] {len(vague_violations)} incohérence(s) entre vagues et dépendances :")
        for lot_id, dep_or_reason, reason in vague_violations:
            if reason == "vague inconnue":
                print(f"    - lot '{lot_id}' : {reason} ({dep_or_reason})")
            else:
                print(f"    - lot '{lot_id}' -> '{dep_or_reason}' : {reason}")
        print()
        errors += len(vague_violations)
    else:
        print("[OK] Les vagues sont cohérentes avec le graphe de dépendances.")

    # -----------------------------------------------------------------------
    # Contrôle 4 : Propriété disjointe des critères
    # -----------------------------------------------------------------------
    all_criteria = load_referentiel(referentiel_path)
    if all_criteria is None:
        print(f"[ERREUR] Référentiel illisible ou absent : {referentiel_path}")
        print()
        errors += 1
        all_criteria = []

    # Utiliser le module partagé pour calculer l'ownership
    ownership, complement_lots, residuel_lots, contextes_by_lot, ownership_errors = compute_ownership(lots, all_criteria)

    # Vérifier les erreurs d'ownership
    if ownership_errors:
        for err in ownership_errors:
            print(f"[ERREUR] {err}")
        print()
        errors += len(ownership_errors)

    # Affichage du mapping si disponible
    automatisables, partiels = load_mapping()
    if automatisables is None:
        print("[AVERTISSEMENT] eof_criteria_mapping.py illisible, contrôle de propriété partiel.")
        print()
        automatisables = set()
        partiels = set()

    collisions = {crit_id: owners for crit_id, owners in ownership.items() if len(owners) > 1}
    orphans = [c for c in all_criteria if c not in ownership]

    if collisions:
        print(f"[ERREUR] {len(collisions)} critère(s) possédé(s) par plusieurs lots :")
        for crit_id in sorted(collisions.keys()):
            owners = collisions[crit_id]
            print(f"    - {crit_id} : {', '.join(owners)}")
        print()
        errors += len(collisions)
    else:
        print("[OK] Aucun critère possédé par plusieurs lots.")

    if orphans:
        print(f"[ERREUR] {len(orphans)} critère(s) orphelin(s) (jamais jugé) :")
        for crit_id in sorted(orphans):
            print(f"    - {crit_id}")
        print()
        errors += len(orphans)
    else:
        print("[OK] Aucun critère orphelin.")

    # Contrôle supplémentaire : critère dans contextes_autorises ne doit pas être possédé par le même lot
    contexte_conflicts = []
    for lot_id, contextes in contextes_by_lot.items():
        lot_owned = [c for c, owners in ownership.items() if lot_id in owners]
        conflicts = contextes & set(lot_owned)
        if conflicts:
            for crit_id in sorted(conflicts):
                contexte_conflicts.append((lot_id, crit_id))

    if contexte_conflicts:
        print(f"[ERREUR] {len(contexte_conflicts)} critère(s) à la fois possédé ET dans contextes_autorises du même lot :")
        for lot_id, crit_id in contexte_conflicts:
            print(f"    - lot '{lot_id}' : critère {crit_id}")
        print()
        errors += len(contexte_conflicts)
    else:
        print("[OK] Aucun conflit contexte/propriété dans un même lot.")

    # -----------------------------------------------------------------------
    # Contrôle 4b : Validation sauf_lots
    # -----------------------------------------------------------------------
    sauf_lots_violations = []
    for lot in lots:
        criteres = lot.get("criteres_possedes")
        if criteres and "sauf_lots" in criteres:
            for except_lot_id in criteres["sauf_lots"]:
                if except_lot_id not in lot_ids_set:
                    sauf_lots_violations.append((lot["id"], except_lot_id))

    if sauf_lots_violations:
        print(f"[ERREUR] {len(sauf_lots_violations)} sauf_lots pointant vers des lots inexistants :")
        for lot_id, except_id in sauf_lots_violations:
            print(f"    - lot '{lot_id}' : sauf_lots cite '{except_id}' (introuvable)")
        print()
        errors += len(sauf_lots_violations)
    else:
        print("[OK] Tous les sauf_lots citent des lots existants.")

    # -----------------------------------------------------------------------
    # Contrôle 4c : Présence de conventions.contribution_de_contexte
    # -----------------------------------------------------------------------
    if "contribution_de_contexte" not in conventions:
        print("[ERREUR] conventions.contribution_de_contexte absent du manifeste.")
        print()
        errors += 1
    else:
        print("[OK] conventions.contribution_de_contexte présent.")

    # -----------------------------------------------------------------------
    # Contrôle 5 : Référentiel
    # -----------------------------------------------------------------------
    if all_criteria:
        print(f"[OK] Référentiel chargé : {len(all_criteria)} critères.")

    # Affichage du décompte automatisables/partiels pour vérification
    if automatisables or partiels:
        print(f"[info] MAPPING : {len(automatisables)} automatisables, {len(partiels)} partiels.")

    # Affichage des lots résiduels
    if residuel_lots:
        print(f"[info] {len(residuel_lots)} lot(s) résiduel(s) : {', '.join(residuel_lots.keys())}")

    # -----------------------------------------------------------------------
    # Contrôle 4d : Unicité des lots résiduels par provenance
    # -----------------------------------------------------------------------
    residuel_by_provenance = {}
    for lot_id, provenance in residuel_lots.items():
        if provenance not in residuel_by_provenance:
            residuel_by_provenance[provenance] = []
        residuel_by_provenance[provenance].append(lot_id)

    residuel_collisions = {provenance: lots for provenance, lots in residuel_by_provenance.items() if len(lots) > 1}
    if residuel_collisions:
        print(f"[ERREUR] {len(residuel_collisions)} provenance(s) avec plusieurs lots résiduels (ambiguïté d'ordre) :")
        for provenance, lot_ids in residuel_collisions.items():
            print(f"    - provenance '{provenance}' : {', '.join(lot_ids)}")
        print()
        errors += len(residuel_collisions)
    else:
        if residuel_lots:
            print("[OK] Chaque provenance a au plus un lot résiduel.")

    # -----------------------------------------------------------------------
    # Contrôle 6 : Provenances
    # -----------------------------------------------------------------------
    precedence = conventions.get("precedence_provenance", [])
    provenance_violations = []

    for lot in lots:
        provenances = lot.get("provenances_autorisees", [])
        for provenance in provenances:
            if provenance not in precedence:
                provenance_violations.append((lot["id"], provenance))

        sortie = lot.get("sortie_de_lot")
        if sortie and not provenances:
            provenance_violations.append((lot["id"], "aucune provenance déclarée pour un lot de jugement"))

    if provenance_violations:
        print(f"[ERREUR] {len(provenance_violations)} provenance(s) invalide(s) :")
        for lot_id, provenance in provenance_violations:
            print(f"    - lot '{lot_id}' : {provenance}")
        print()
        errors += len(provenance_violations)
    else:
        print("[OK] Toutes les provenances sont valides.")

    # -----------------------------------------------------------------------
    # Contrôle 7 : Sorties de lot uniques
    # -----------------------------------------------------------------------
    sorties = [lot["sortie_de_lot"] for lot in lots if lot.get("sortie_de_lot")]
    duplicates_sorties = [s for s in set(sorties) if sorties.count(s) > 1]

    if duplicates_sorties:
        print(f"[ERREUR] {len(duplicates_sorties)} sortie(s) de lot en doublon :")
        for sortie in sorted(duplicates_sorties):
            lots_with_sortie = [lot["id"] for lot in lots if lot.get("sortie_de_lot") == sortie]
            print(f"    - {sortie} : {', '.join(lots_with_sortie)}")
        print()
        errors += len(duplicates_sorties)
    else:
        print("[OK] Toutes les sorties de lot sont uniques.")

    # -----------------------------------------------------------------------
    # Contrôle 8 : Fichiers référencés
    # -----------------------------------------------------------------------
    missing_files = []
    files_to_write = []

    for lot in lots:
        etat = lot.get("etat")

        if etat == "existant":
            for script in lot.get("scripts", []):
                script_path = PROJECT_ROOT / script
                if not script_path.exists():
                    missing_files.append((lot["id"], script))

            if lot.get("executeur") == "llm":
                prompt_path_str = lot.get("prompt")
                if prompt_path_str:
                    prompt_path = PROJECT_ROOT / prompt_path_str
                    if not prompt_path.exists():
                        missing_files.append((lot["id"], prompt_path_str))

        elif etat in ("a_ecrire", "partiellement_a_ecrire"):
            files_to_write.extend(lot.get("scripts_a_ecrire", []))
            if lot.get("executeur") == "llm" and lot.get("prompt"):
                files_to_write.append(lot.get("prompt"))

    if missing_files:
        print(f"[ERREUR] {len(missing_files)} fichier(s) manquant(s) pour des lots 'existant' :")
        for lot_id, file_path in missing_files:
            print(f"    - lot '{lot_id}' : {file_path}")
        print()
        errors += len(missing_files)
    else:
        print("[OK] Tous les fichiers déclarés 'existant' sont présents.")

    if files_to_write:
        print(f"[info] {len(files_to_write)} fichier(s) / script(s) à écrire (normal).")

    schema_sortie_path = PROJECT_ROOT / manifest.get("schema_sortie_lot", "")
    if schema_sortie_path.exists():
        print(f"[info] Schéma de sortie de lot présent : {schema_sortie_path.name}")
    else:
        print(f"[info] Schéma de sortie de lot absent (à écrire) : {schema_sortie_path.name}")

    # -----------------------------------------------------------------------
    # Contrôle 9 : Exécuteurs et états
    # -----------------------------------------------------------------------
    valid_executeurs = {"script", "llm", "humain"}
    valid_etats = {"existant", "a_ecrire", "partiellement_a_ecrire"}
    exec_violations = []

    for lot in lots:
        executeur = lot.get("executeur")
        if executeur not in valid_executeurs:
            exec_violations.append((lot["id"], f"executeur invalide : {executeur}"))

        etat = lot.get("etat")
        if etat not in valid_etats:
            exec_violations.append((lot["id"], f"etat invalide : {etat}"))

        if executeur == "llm" and not lot.get("prompt"):
            exec_violations.append((lot["id"], "executeur llm sans prompt"))

        if executeur == "script":
            scripts = lot.get("scripts", []) + lot.get("scripts_a_ecrire", [])
            if not scripts:
                exec_violations.append((lot["id"], "executeur script sans scripts"))

    if exec_violations:
        print(f"[ERREUR] {len(exec_violations)} violation(s) exécuteur/état :")
        for lot_id, violation in exec_violations:
            print(f"    - lot '{lot_id}' : {violation}")
        print()
        errors += len(exec_violations)
    else:
        print("[OK] Tous les exécuteurs et états sont valides.")

    print()
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validation du manifeste de lots du processus d'audit EOF.",
    )
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=DEFAULT_MANIFEST,
        help=f"Chemin du manifeste (défaut : {DEFAULT_MANIFEST.relative_to(PROJECT_ROOT)})",
    )
    args = parser.parse_args()

    manifest_path = args.manifest
    if not manifest_path.exists():
        print(f"[ERREUR] Manifeste introuvable : {manifest_path}")
        return 1

    print("=" * 68)
    print(f"  VALIDATION DU MANIFESTE DE LOTS")
    print(f"  {manifest_path}")
    print("=" * 68)

    errors = check_manifest(manifest_path)

    if errors:
        print(f"[ÉCHEC] {errors} problème(s) détecté(s).")
        print()
        print("Le manifeste n'est pas valide. Corriger les violations ci-dessus avant")
        print("d'exécuter le processus d'audit.")
        return 1

    print("[SUCCÈS] Le manifeste est valide.")
    print()
    print("Tous les contrôles d'intégrité sont passés. Le processus d'audit peut")
    print("être orchestré à partir de ce manifeste.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
