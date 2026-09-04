#!/usr/bin/env python3
"""
Module de résolution de la propriété des critères EOF.

Extraction des fonctions partagées entre valider_manifeste.py et fusionner_lots.py
pour garantir que la propriété des critères est déterminée par la même logique
dans la validation ET dans la fusion. Toute divergence entre ces deux scripts
casse silencieusement la garantie d'indépendance à l'ordre d'exécution des lots.

Trois formes de possession définies dans le manifeste :
  - {"prefixe_id": "3."} -> tous les critères dont l'id commence par ce préfixe
  - {"source": "<chemin>", "regle": "..."} -> critères que la table de correspondance
    (eof_criteria_mapping.py) déclare automatisables
  - {"regle": "..."} sans source ni prefixe_id -> ensemble COMPLÉMENT : tous les
    critères que personne d'autre ne possède (au plus un lot de complément)

Propriété vs contexte :
  - Posséder un critère = droit d'y poser une `reponse` (verdict tranché)
  - Contribuer un contexte = droit d'y écrire un `contexte` sans verdict
  - Un lot peut contribuer un contexte sur un critère qu'il ne possède pas

Convention de résolution en trois passes (pour gérer `sauf_lots`) :
  1. Résoudre les possessions sans `sauf_lots`
  2. Résoudre les possessions avec `sauf_lots` (nécessite ownership partiel)
  3. Résoudre les contextes autorisés pour tous les lots
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_mapping():
    """Charge le MAPPING de eof_criteria_mapping.py et retourne (automatisables, partiels).

    Automatisables : critères tranchés par script, le lot possède ces critères.
    Partiels : critères où le script fournit un contexte, le verdict reste au lot de dimension.
    """
    mapping_path = (
        PROJECT_ROOT / ".claude" / "skills" / "analyse-parcours" / "scripts"
        / "eof_criteria_mapping.py"
    )
    if not mapping_path.exists():
        return None, None

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("eof_criteria_mapping", mapping_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        mapping = getattr(module, "MAPPING", {})
        automatisables = {
            crit_id
            for crit_id, meta in mapping.items()
            if meta.get("categorie") == "automatisable"
        }
        partiels = {
            crit_id
            for crit_id, meta in mapping.items()
            if meta.get("categorie") == "partiel"
        }
        return automatisables, partiels
    except Exception:
        return None, None


def resolve_criteres_possedes(lot, all_criteria, automatisables, ownership_so_far):
    """Retourne l'ensemble des critères possédés par un lot.

    Retourne None si la règle est dynamique (complément), ou un set vide si
    le lot ne possède aucun critère (lots de collecte, porte, fusion, ou résiduel).

    Gère maintenant sauf_lots : {"prefixe_id": "1.", "sauf_lots": ["jugement-automatique"]}
    signifie "tous les critères 1.X moins ceux possédés par jugement-automatique".

    Gère maintenant residuel: {"residuel": true, ...} signifie que le lot ne possède
    aucun critère en exclusivité mais peut répondre sur n'importe quel critère.

    Args:
        lot: dict du lot depuis le manifeste
        all_criteria: liste de tous les IDs de critères du référentiel
        automatisables: set des IDs automatisables depuis eof_criteria_mapping.py
        ownership_so_far: dict {crit_id: [lot_id, ...]} rempli par les lots déjà résolus

    Returns:
        set des critères possédés, ou None si règle de complément
    """
    criteres = lot.get("criteres_possedes")
    if criteres is None:
        return set()

    # Lot résiduel : ne possède aucun critère en exclusivité
    if criteres.get("residuel"):
        return set()

    owned = set()

    if "prefixe_id" in criteres:
        prefix = criteres["prefixe_id"]
        owned = {c for c in all_criteria if c.startswith(prefix)}

        # Soustraire les critères possédés par les lots cités dans sauf_lots
        sauf_lots = criteres.get("sauf_lots", [])
        for except_lot_id in sauf_lots:
            for crit_id in list(owned):
                if crit_id in ownership_so_far and except_lot_id in ownership_so_far[crit_id]:
                    owned.discard(crit_id)

        return owned

    if "source" in criteres:
        if automatisables is None:
            return set()
        # Le lot possède les critères automatisables (tranchés par script)
        return automatisables.copy()

    if "regle" in criteres and "source" not in criteres and "prefixe_id" not in criteres:
        return None

    return set()


def resolve_contextes_autorises(lot, all_criteria, partiels):
    """Retourne l'ensemble des critères où le lot peut écrire un contexte.

    Un lot peut écrire un contexte sur un critère qu'il ne possède pas.
    Pour le lot automatique : les critères de catégorie partiel.
    Gère aussi prefixe_id pour les tests (cas pathologique).

    Args:
        lot: dict du lot depuis le manifeste
        all_criteria: liste de tous les IDs de critères du référentiel
        partiels: set des IDs partiels depuis eof_criteria_mapping.py

    Returns:
        set des critères sur lesquels le lot peut contribuer un contexte
    """
    contextes = lot.get("contextes_autorises")
    if contextes is None:
        return set()

    if "source" in contextes:
        if partiels is None:
            return set()
        return partiels.copy()

    if "prefixe_id" in contextes:
        prefix = contextes["prefixe_id"]
        return {c for c in all_criteria if c.startswith(prefix)}

    return set()


def compute_ownership(lots, all_criteria):
    """Calcule l'ownership complet de tous les critères depuis la liste des lots.

    Retourne (ownership_map, complement_lots, residuel_lots, contextes_by_lot, errors) où :
      - ownership_map: dict {crit_id: [lot_id, ...]}
      - complement_lots: liste des lots déclarant une règle de complément
      - residuel_lots: dict {lot_id: nature_preuve} des lots résiduels (pas de critères en propre)
      - contextes_by_lot: dict {lot_id: set(crit_ids)}
      - errors: liste de messages d'erreur (vide si tout est OK)

    Résolution en trois passes pour gérer sauf_lots et compléments.
    """
    automatisables, partiels = load_mapping()
    if automatisables is None:
        # Ne pas échouer, juste signaler
        automatisables = set()
        partiels = set()

    ownership = {}
    complement_lots = []
    residuel_lots = {}
    contextes_by_lot = {}
    errors = []

    # Première passe : résoudre les critères sans sauf_lots et identifier les lots résiduels
    for lot in lots:
        criteres = lot.get("criteres_possedes")
        if criteres:
            # Détecter les lots résiduels
            if criteres.get("residuel"):
                natures = lot.get("natures_autorisees", [])
                if natures:
                    residuel_lots[lot["id"]] = natures[0]  # Première nature de preuve
            elif "sauf_lots" not in criteres:
                owned = resolve_criteres_possedes(lot, all_criteria, automatisables, ownership)
                if owned is None:
                    complement_lots.append(lot["id"])
                elif owned:
                    for crit_id in owned:
                        if crit_id not in ownership:
                            ownership[crit_id] = []
                        ownership[crit_id].append(lot["id"])

    # Deuxième passe : résoudre les critères avec sauf_lots
    for lot in lots:
        criteres = lot.get("criteres_possedes")
        if criteres and "sauf_lots" in criteres and not criteres.get("residuel"):
            owned = resolve_criteres_possedes(lot, all_criteria, automatisables, ownership)
            if owned is None:
                complement_lots.append(lot["id"])
            elif owned:
                for crit_id in owned:
                    if crit_id not in ownership:
                        ownership[crit_id] = []
                    ownership[crit_id].append(lot["id"])

    # Troisième passe : résoudre les contextes autorisés
    for lot in lots:
        contextes = resolve_contextes_autorises(lot, all_criteria, partiels)
        if contextes:
            contextes_by_lot[lot["id"]] = contextes

    # Résoudre le lot de complément si un seul
    if len(complement_lots) > 1:
        errors.append(f"{len(complement_lots)} lots de complément (ambiguïté)")
    elif len(complement_lots) == 1:
        complement_id = complement_lots[0]
        uncovered = set(all_criteria) - set(ownership.keys())
        for crit_id in uncovered:
            ownership[crit_id] = [complement_id]

    return ownership, complement_lots, residuel_lots, contextes_by_lot, errors
