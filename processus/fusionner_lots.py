#!/usr/bin/env python3
"""
Fusionneur de lots d'audit EOF multi-agents.

POURQUOI CE SCRIPT EXISTE
-------------------------
Le processus d'audit EOF est découpé en lots indépendants. Chaque lot (agent LLM,
script, ou humain) écrit UN fichier de résultats conforme à schema-sortie-lot.json.
Ce script consolide tous ces fichiers en UN SEUL résultat d'audit, selon des règles
de précédence déterministes et sans aucun LLM dans la boucle.

Motif : une agrégation déterministe garantit que l'ordre d'exécution des lots N'A
AUCUN EFFET sur le résultat. Deux exécutions consécutives sur les mêmes lots
produisent le même fichier, au champ d'horodatage près (idempotence).

RÈGLES DE FUSION (impératives, non négociables)
-----------------------------------------------
1. Précédence par provenance (lue depuis le manifeste) :
   collecte > estime > declare > precise
   Une provenance haute ne peut JAMAIS être écrasée par une provenance plus basse.

2. Divergence (deux provenances DIFFÉRENTES avec réponses DIFFÉRENTES) :
   - Conserver la réponse de la provenance la plus haute en précédence (avec son coefficient)
   - Marquer la divergence explicitement
   - Consigner l'écart dans le contexte (quelles provenances, quelles réponses, laquelle retenue)

3. Conflit (même provenance, réponses différentes) : REFUSER la fusion, exit 1.
   Le manifeste garantit que chaque critère appartient à un seul lot. Si deux lots
   portent le même critère avec la même provenance, c'est un défaut de conception.

4. Absence de donnée : reponse=null, categorie=aucune_donnee, RIEN d'inventé.

5. Validation bloquante : chaque fichier de lot passe par valider_sortie_lot.py.
   Un fichier non conforme est REFUSÉ, jamais fusionné.

6. Enrichissement depuis le référentiel : potentiel_max, dimension, libellé du critère sont
   ajoutés par CE SCRIPT depuis le référentiel, jamais lus depuis un fichier de lot.

7. Idempotence : deux exécutions sur les mêmes lots = même fichier (hors horodatage).

Usage :
    python3 fusionner_lots.py audits/<domaine>

Le répertoire d'audit contient :
  - lots/*.json        : fichiers de sortie de lots, validés avant fusion
  - eof-audit-results.json : sortie consolidée (ÉCRASÉE par ce script)

Code de sortie : 0 si fusion réussie, 1 sinon.

Alignement de style avec check_efootprint_contract.py et valider_sortie_lot.py :
  - Bandeau visuel avec séparateurs
  - Préfixes [OK] / [ÉCHEC] / [info]
  - Message final pédagogique
  - Sortie structurée : liste des violations, puis verdict
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Racine du projet : ce script vit dans processus/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENTIEL_PATH = (
    PROJECT_ROOT
    / ".claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - Français"
    / "eof-referentiel.json"
)
MANIFESTE_PATH = PROJECT_ROOT / "processus" / "manifeste-lots.json"
VALIDATEUR_PATH = PROJECT_ROOT / "processus" / "valider_sortie_lot.py"

# Importer les fonctions de résolution de propriété depuis le module partagé
from propriete_criteres import compute_ownership


# ---------------------------------------------------------------------------
# Chargement des données de référence
# ---------------------------------------------------------------------------

def load_json_file(path):
    """Charge un fichier JSON, retourne (data, errors)."""
    if not path.exists():
        return None, [f"Fichier introuvable : {path}"]
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), []
    except (json.JSONDecodeError, OSError) as exc:
        return None, [f"Erreur de lecture {path} : {exc}"]


def load_referentiel():
    """Charge le référentiel EOF. Retourne (criteres_dict, diagnostic_dict, erreurs)."""
    data, errors = load_json_file(REFERENTIEL_PATH)
    if errors:
        return None, None, errors

    criteres = {c["id"]: c for c in data.get("criteres", []) if "id" in c}
    diagnostic = {q["id"]: q for q in data.get("diagnostic_rapide", []) if "id" in q}

    if not criteres and not diagnostic:
        return None, None, ["Référentiel vide ou mal formé"]

    return criteres, diagnostic, []


def load_manifeste():
    """Charge le manifeste des lots. Retourne (manifeste_data, precedence_list, erreurs)."""
    data, errors = load_json_file(MANIFESTE_PATH)
    if errors:
        return None, None, errors

    precedence = data.get("conventions", {}).get("precedence_provenance")
    if not isinstance(precedence, list) or not precedence:
        return None, None, ["Manifeste : clé conventions.precedence_provenance manquante ou invalide"]

    return data, precedence, []


# ---------------------------------------------------------------------------
# Validation des fichiers de lots
# ---------------------------------------------------------------------------

def validate_lot_file(lot_path):
    """Valide un fichier de lot avec valider_sortie_lot.py. Retourne (ok, erreur_texte)."""
    if not VALIDATEUR_PATH.exists():
        return False, f"Validateur introuvable : {VALIDATEUR_PATH}"

    try:
        result = subprocess.run(
            [sys.executable, str(VALIDATEUR_PATH), str(lot_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return True, None
        else:
            return False, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Validation timeout (> 30s)"
    except OSError as exc:
        return False, f"Erreur d'exécution du validateur : {exc}"


# ---------------------------------------------------------------------------
# Logique de fusion
# ---------------------------------------------------------------------------


def merge_entries(entries_by_id, precedence_list, ref_criteres, ref_diagnostic, ownership_map, residuel_lots, known_lot_ids):
    """
    Fusionne les entrées de lots selon les règles de précédence.

    Args:
        entries_by_id: dict {id: [entry1, entry2, ...]}
        precedence_list: liste ordonnée des provenances (plus haute d'abord)
        ref_criteres: dict {id: critere_complet} depuis le référentiel
        ref_diagnostic: dict {id: question} depuis le diagnostic rapide
        ownership_map: dict {crit_id: [lot_id, ...]} pour le contrôle de propriété
        residuel_lots: dict {lot_id: provenance} des lots résiduels
        known_lot_ids: set des lot_id valides depuis le manifeste

    Returns:
        (merged_entries, errors) où merged_entries est une liste de critères fusionnés
    """
    merged = []
    errors = []

    # Créer un mapping provenance -> priorité (plus bas = plus haute priorité)
    provenance_priority = {provenance: idx for idx, provenance in enumerate(precedence_list)}

    for cid, entries in sorted(entries_by_id.items()):
        # Référence du critère
        ref = ref_criteres.get(cid) or ref_diagnostic.get(cid)
        if not ref:
            errors.append(f"Critère {cid} absent du référentiel")
            continue

        # Valider les lot_id
        for entry in entries:
            lot_id = entry.get("_lot_id")
            if lot_id and lot_id not in known_lot_ids:
                errors.append(f"Critère {cid} : lot_id inconnu '{lot_id}' (lots connus : {sorted(known_lot_ids)})")
                continue

        # Contrôle de propriété : vérifier que seuls les propriétaires et les lots résiduels posent des réponses
        owners = ownership_map.get(cid, [])
        for entry in entries:
            lot_id = entry.get("_lot_id")
            reponse = entry.get("reponse")
            if reponse is not None and lot_id not in owners and lot_id not in residuel_lots:
                expected_owner = owners[0] if owners else "aucun"
                errors.append(
                    f"Critère {cid} : le lot '{lot_id}' a posé une réponse mais ne possède pas ce critère "
                    f"(propriétaire attendu : {expected_owner})"
                )

        # Filtrer les entrées avec réponse non null
        with_reponse = [e for e in entries if e.get("reponse") is not None]

        # Collecter tous les contextes (y compris ceux des lots non propriétaires)
        all_contextes = [e.get("contexte") for e in entries if e.get("contexte")]

        if not with_reponse:
            # Aucune réponse : prendre la première entrée ou créer une entrée vide
            if entries:
                base = entries[0].copy()
                # Concaténer les contextes si plusieurs
                if len(all_contextes) > 1:
                    base["contexte"] = " ; ".join(all_contextes)
            else:
                base = {
                    "id": cid,
                    "categorie": "aucune_donnee",
                    "reponse": None,
                    "coefficient": None,
                    "provenance": None,
                    "source": None,
                    "contexte": None,
                    "sans_objet": None,
                }
            merged.append(base)
            continue

        # Grouper par provenance
        by_provenance = defaultdict(list)
        for e in with_reponse:
            provenance = e.get("provenance")
            by_provenance[provenance].append(e)

        # Trouver la provenance la plus haute présente
        highest_provenance = None
        for provenance in precedence_list:
            if provenance in by_provenance:
                highest_provenance = provenance
                break

        if highest_provenance is None:
            errors.append(f"Critère {cid} : aucune provenance reconnue")
            continue

        entries_highest = by_provenance[highest_provenance]

        # Vérifier les conflits à provenance égale
        unique_reponses = set(e.get("reponse") for e in entries_highest)
        if len(unique_reponses) > 1:
            lot_ids = [e.get("_lot_id", "?") for e in entries_highest]
            errors.append(
                f"Critère {cid} : conflit à provenance égale ({highest_provenance}) - "
                f"réponses divergentes : {unique_reponses} - lots : {lot_ids}"
            )
            continue

        # Prendre la première entrée de la provenance la plus haute
        base = entries_highest[0].copy()

        # Vérifier que la réponse existe dans options_evaluation du référentiel
        options_evaluation = ref.get("options_evaluation", [])
        if base["reponse"] not in options_evaluation:
            errors.append(
                f"Critère {cid} : réponse '{base['reponse']}' absente de options_evaluation "
                f"du référentiel (options valides : {options_evaluation})"
            )
            continue

        # Vérifier les divergences entre provenances différentes
        other_provenances = [p for p in by_provenance if p != highest_provenance]
        if other_provenances:
            # Collecter toutes les réponses des autres provenances
            other_reponses = set()
            for provenance in other_provenances:
                for e in by_provenance[provenance]:
                    other_reponses.add(e.get("reponse"))

            # Y a-t-il une divergence (réponse différente) ?
            if base["reponse"] not in other_reponses:
                # Divergence détectée : conserver la réponse de la provenance la plus haute
                # et consigner l'écart
                base["divergence"] = True

                # Construire le contexte explicatif
                divergence_details = []
                for provenance in [highest_provenance] + other_provenances:
                    for e in by_provenance[provenance]:
                        divergence_details.append(f"{provenance}: '{e.get('reponse')}'")

                base["contexte"] = (
                    f"Divergence entre provenances - {'; '.join(divergence_details)} - "
                    f"réponse retenue (provenance la plus haute) : {highest_provenance}"
                )

        # Concaténer les contextes additionnels des lots non propriétaires
        if len(all_contextes) > 1 or (len(all_contextes) == 1 and not base.get("contexte")):
            if base.get("contexte"):
                base["contexte"] = base["contexte"] + " ; " + " ; ".join([c for c in all_contextes if c != base.get("contexte")])
            else:
                base["contexte"] = " ; ".join(all_contextes)

        merged.append(base)

    return merged, errors


def enrich_from_referentiel(entries, ref_criteres, ref_diagnostic):
    """
    Enrichit les entrées avec les données du référentiel (potentiel_max, dimension, libellé).
    Produit UNE entrée pour CHAQUE critère du référentiel, même ceux sans lot.

    Args:
        entries: liste d'entrées fusionnées
        ref_criteres: dict {id: critere_complet}
        ref_diagnostic: dict {id: question}

    Returns:
        liste d'entrées enrichies pour le format de sortie final (54 critères)
    """
    # Créer un mapping des entrées fusionnées par ID
    entries_by_id = {e.get("id"): e for e in entries if e.get("id")}

    enriched = []

    # Itérer sur TOUS les critères du référentiel dans l'ordre
    for cid in sorted(ref_criteres.keys(), key=lambda x: (int(x.split('.')[0]), int(x.split('.')[1]))):
        ref = ref_criteres[cid]
        entry = entries_by_id.get(cid)

        if entry:
            # Entrée fusionnée existe
            enriched_entry = {
                "id": cid,
                "dimension": ref.get("pilier", ""),
                "critere": ref.get("critere", ""),
                "potentiel_max": ref.get("potentiel_max", 0),
                "categorie": entry.get("categorie", "aucune_donnee"),
                "reponse": entry.get("reponse"),
                "coefficient": entry.get("coefficient"),
                "provenance": entry.get("provenance"),
                "source": entry.get("source"),
                "contexte": entry.get("contexte"),
                "sans_objet": entry.get("sans_objet"),
            }
            # Ajouter divergence si présente
            if entry.get("divergence"):
                enriched_entry["divergence"] = True
        else:
            # Aucune entrée : créer une entrée vide
            enriched_entry = {
                "id": cid,
                "dimension": ref.get("pilier", ""),
                "critere": ref.get("critere", ""),
                "potentiel_max": ref.get("potentiel_max", 0),
                "categorie": "aucune_donnee",
                "reponse": None,
                "coefficient": None,
                "provenance": None,
                "source": None,
                "contexte": None,
                "sans_objet": None,
            }

        enriched.append(enriched_entry)

    return enriched


def compute_metrics(criteres, ref_criteres):
    """
    Calcule les métriques agrégées depuis les critères fusionnés.

    Returns:
        dict avec :
          - criteres_repondus : nombre de critères avec réponse (toutes provenances)
          - criteres_avec_indice_partiel : nombre avec indice partiel
          - potentiel_optimisation_global_pct : pourcentage global
          - completude_globale_pct : part des critères examinés sur le total
          - dimensions : liste des 6 dimensions avec potentiels
          - repondus_par_provenance : répartition des critères répondus par provenance
    """
    # Définir les 6 dimensions
    dimension_names = [
        "🛖 1 — Produit",
        "🗺️ 2 — Architecture",
        "🏢 3 — Infrastructure",
        "💾 4 — Stockage et données",
        "👨‍💻 5 — Algo & Code",
        "🛠 6 — Facilité de changement",
    ]

    # Calculer les totaux depuis le référentiel (TOUS les critères)
    dimension_totals_potentiel = {name: 0.0 for name in dimension_names}
    dimension_counts = {name: 0 for name in dimension_names}

    for cid, ref in ref_criteres.items():
        pilier = ref.get("pilier", "")
        if pilier in dimension_names:
            dimension_counts[pilier] += 1
            dimension_totals_potentiel[pilier] += ref.get("potentiel_max", 0)

    # Agréger les potentiels et complétudes par dimension
    dimension_metrics = {name: {
        "potentiel_retenu": 0.0,
        "potentiel_total": dimension_totals_potentiel[name],
        "repondus": 0,
        "sans_objet_count": 0,
        "repondus_par_provenance": {"collecte": 0, "estime": 0, "declare": 0, "precise": 0}
    } for name in dimension_names}

    criteres_repondus = 0
    criteres_avec_indice_partiel = 0
    repondus_par_provenance_global = {"collecte": 0, "estime": 0, "declare": 0, "precise": 0}

    for c in criteres:
        pilier = c.get("dimension", "")
        if pilier not in dimension_names:
            continue

        categorie = c.get("categorie")
        reponse = c.get("reponse")
        coefficient = c.get("coefficient")
        potentiel_max = c.get("potentiel_max", 0)
        provenance = c.get("provenance")
        sans_objet = c.get("sans_objet")

        # Mécanisme sans_objet : retire du numérateur ET du dénominateur
        if sans_objet:
            dimension_metrics[pilier]["sans_objet_count"] += 1
            dimension_metrics[pilier]["potentiel_total"] -= potentiel_max
            continue

        # TOUTE réponse compte, quelle que soit sa provenance ou catégorie
        if reponse is not None:
            criteres_repondus += 1
            dimension_metrics[pilier]["repondus"] += 1

            # Compter par provenance
            if provenance in repondus_par_provenance_global:
                repondus_par_provenance_global[provenance] += 1
                dimension_metrics[pilier]["repondus_par_provenance"][provenance] += 1

            # Calcul du potentiel retenu
            if coefficient is not None:
                potentiel_retenu = coefficient * potentiel_max
                dimension_metrics[pilier]["potentiel_retenu"] += potentiel_retenu

        if categorie == "partiel" and c.get("contexte"):
            criteres_avec_indice_partiel += 1

    # Calculer les pourcentages par dimension
    dimensions = []
    potentiel_total_global = 0.0
    potentiel_retenu_global = 0.0
    criteres_examines_global = 0
    criteres_totaux_global = len(ref_criteres)

    for name in dimension_names:
        stats = dimension_metrics[name]
        potentiel_total = stats["potentiel_total"]
        potentiel_retenu = stats["potentiel_retenu"]
        repondus = stats["repondus"]
        total_criteres = dimension_counts[name] - stats["sans_objet_count"]

        # Potentiel d'optimisation : dénominateur = TOUS les critères de la dimension, hors sans_objet
        if potentiel_total > 0:
            potentiel_optimisation_pct = (potentiel_retenu / potentiel_total) * 100
        else:
            potentiel_optimisation_pct = None

        # Complétude : part des critères examinés
        if total_criteres > 0:
            completude_pct = (repondus / total_criteres) * 100
        else:
            completude_pct = None

        dimensions.append({
            "nom": name,
            "potentiel_optimisation_pct": potentiel_optimisation_pct,
            "completude_pct": completude_pct,
            "repondus": repondus,
            "total": total_criteres,
            "repondus_par_provenance": stats["repondus_par_provenance"],
        })

        potentiel_total_global += potentiel_total
        potentiel_retenu_global += potentiel_retenu
        criteres_examines_global += repondus

    # Calcul global
    if potentiel_total_global > 0:
        potentiel_optimisation_global_pct = (potentiel_retenu_global / potentiel_total_global) * 100
    else:
        potentiel_optimisation_global_pct = None

    if criteres_totaux_global > 0:
        completude_globale_pct = (criteres_examines_global / criteres_totaux_global) * 100
    else:
        completude_globale_pct = None

    return {
        "criteres_repondus": criteres_repondus,
        "criteres_avec_indice_partiel": criteres_avec_indice_partiel,
        "potentiel_optimisation_global_pct": potentiel_optimisation_global_pct,
        "completude_globale_pct": completude_globale_pct,
        "repondus_par_provenance": repondus_par_provenance_global,
        "dimensions": dimensions,
    }


def build_diagnostic_rapide_apercu(entries_by_id, ref_diagnostic):
    """Construit la section diagnostic_rapide_apercu depuis les entrées fusionnées."""
    questions = []

    for qid in sorted(ref_diagnostic.keys(), key=lambda x: float(x.split(".")[-1])):
        ref = ref_diagnostic[qid]
        entries = entries_by_id.get(qid, [])

        # Prendre la première entrée ou créer une vide
        if entries:
            entry = entries[0]
            question = {
                "id": qid,
                "critere": ref.get("critere", ""),
                "niveau_impact": ref.get("niveau_impact", ""),
                "reponse": entry.get("reponse"),
                "provenance": entry.get("provenance"),
                "source": entry.get("source"),
                "indice_contextuel": entry.get("contexte"),
            }
        else:
            question = {
                "id": qid,
                "critere": ref.get("critere", ""),
                "niveau_impact": ref.get("niveau_impact", ""),
                "reponse": None,
                "provenance": None,
                "source": None,
                "indice_contextuel": None,
            }

        questions.append(question)

    return {
        "total_questions": len(ref_diagnostic),
        "note": (
            "Échelle 1 à 5, jamais remplie automatiquement — à évaluer humainement. "
            "Exception : 0.16 (doublon exact de 3.3), cf. eof-analyse-minimisation-questions.md."
        ),
        "questions": questions,
    }


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fusionne les fichiers de lots d'audit EOF en un seul résultat consolidé. "
                    "Validation bloquante, règles de précédence déterministes, aucun LLM."
    )
    parser.add_argument("audit_dir", type=Path,
                        help="Répertoire d'audit contenant lots/ et où écrire eof-audit-results.json")
    args = parser.parse_args()

    audit_dir = args.audit_dir
    if not audit_dir.exists():
        print(f"[erreur] Répertoire introuvable : {audit_dir}")
        return 1

    lots_dir = audit_dir / "lots"
    if not lots_dir.exists():
        print(f"[erreur] Sous-répertoire lots/ introuvable : {lots_dir}")
        return 1

    output_path = audit_dir / "eof-audit-results.json"
    domaine = audit_dir.name

    print("=" * 68)
    print(f"  FUSION DES LOTS EOF — {domaine}")
    print(f"  répertoire  : {audit_dir}")
    print(f"  lots        : {lots_dir}")
    print(f"  sortie      : {output_path}")
    print("=" * 68)
    print()

    # Charger le référentiel
    ref_criteres, ref_diagnostic, ref_errors = load_referentiel()
    if ref_errors:
        print("[ÉCHEC] Impossible de charger le référentiel :")
        for err in ref_errors:
            print(f"    {err}")
        return 1

    print(f"[info] Référentiel chargé : {len(ref_criteres)} critères, {len(ref_diagnostic)} questions")

    # Charger le manifeste
    manifeste_data, precedence, manifeste_errors = load_manifeste()
    if manifeste_errors:
        print("[ÉCHEC] Impossible de charger le manifeste :")
        for err in manifeste_errors:
            print(f"    {err}")
        return 1

    print(f"[info] Précédence des provenances : {' > '.join(precedence)}")

    # Calculer l'ownership depuis le manifeste
    lots = manifeste_data.get("lots", [])
    all_criteria = list(ref_criteres.keys())
    ownership_map, _, residuel_lots, _, ownership_errors = compute_ownership(lots, all_criteria)

    if ownership_errors:
        print("[ÉCHEC] Impossible de calculer l'ownership des critères :")
        for err in ownership_errors:
            print(f"    {err}")
        return 1

    known_lot_ids = {lot["id"] for lot in lots}
    print(f"[info] Ownership calculé : {len(lots)} lots, {len(known_lot_ids)} lot_id connus")
    if residuel_lots:
        print(f"[info] Lots résiduels : {', '.join(residuel_lots.keys())}")
    print()

    # Lister et valider les fichiers de lots
    lot_files = sorted(lots_dir.glob("*.json"))
    if not lot_files:
        print(f"[avertissement] Aucun fichier de lot trouvé dans {lots_dir}")
        print("[info] Fusion annulée : impossible de produire un résultat sans lots")
        return 1

    print(f"[info] {len(lot_files)} fichier(s) de lot détecté(s)")
    print()

    all_entries_by_id = defaultdict(list)
    validation_failures = []

    for lot_path in lot_files:
        print(f"[validation] {lot_path.name} ... ", end="")
        ok, error_msg = validate_lot_file(lot_path)

        if not ok:
            print("ÉCHEC")
            validation_failures.append((lot_path.name, error_msg))
            continue

        print("OK")

        # Charger le fichier de lot
        lot_data, load_errors = load_json_file(lot_path)
        if load_errors:
            validation_failures.append((lot_path.name, f"Erreur de chargement : {load_errors[0]}"))
            continue

        # Collecter les entrées par ID
        for entry in lot_data.get("criteres", []):
            cid = entry.get("id")
            if cid:
                # Ajouter le nom du lot pour traçabilité en cas de conflit
                entry["_lot_id"] = lot_data.get("lot_id", lot_path.stem)
                all_entries_by_id[cid].append(entry)

    print()

    if validation_failures:
        print(f"[ÉCHEC] {len(validation_failures)} fichier(s) non conforme(s) :")
        for filename, msg in validation_failures:
            print(f"    {filename} :")
            for line in (msg or "").splitlines()[:10]:  # Limiter l'affichage
                print(f"        {line}")
        print()
        print("Corriger les fichiers de lots ci-dessus et relancer la fusion.")
        return 1

    # Fusion des entrées
    print("[fusion] Application des règles de précédence...")
    merged_entries, merge_errors = merge_entries(
        all_entries_by_id, precedence, ref_criteres, ref_diagnostic, ownership_map, residuel_lots, known_lot_ids
    )

    if merge_errors:
        print(f"[ÉCHEC] {len(merge_errors)} erreur(s) de fusion :")
        for err in merge_errors:
            print(f"    {err}")
        print()
        print("Vérifier le manifeste et les fichiers de lots. La fusion est refusée.")
        return 1

    print(f"[OK] {len(merged_entries)} entrée(s) fusionnée(s)")

    # Enrichissement depuis le référentiel
    print("[enrichissement] Ajout des données du référentiel...")
    enriched = enrich_from_referentiel(merged_entries, ref_criteres, ref_diagnostic)
    print(f"[OK] {len(enriched)} critère(s) enrichi(s)")

    # Calcul des métriques
    print("[métriques] Calcul des agrégats...")
    metrics = compute_metrics(enriched, ref_criteres)
    print(f"[OK] Critères répondus : {metrics['criteres_repondus']}/{len(ref_criteres)}")
    if metrics["completude_globale_pct"] is not None:
        print(f"[OK] Complétude globale : {metrics['completude_globale_pct']:.1f}%")
    if metrics["potentiel_optimisation_global_pct"] is not None:
        print(f"[OK] Potentiel d'optimisation global : {metrics['potentiel_optimisation_global_pct']:.1f}%")

    # Construction du diagnostic rapide
    diagnostic_apercu = build_diagnostic_rapide_apercu(all_entries_by_id, ref_diagnostic)

    # Assemblage du résultat final
    audit_results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domaine": domaine,
        "criteres_total": len(ref_criteres),
        "criteres_repondus": metrics["criteres_repondus"],
        "criteres_avec_indice_partiel": metrics["criteres_avec_indice_partiel"],
        "completude_globale_pct": metrics["completude_globale_pct"],
        "potentiel_optimisation_global_pct": metrics["potentiel_optimisation_global_pct"],
        "repondus_par_provenance": metrics["repondus_par_provenance"],
        "dimensions": metrics["dimensions"],
        "diagnostic_rapide_apercu": diagnostic_apercu,
        "criteres": enriched,
    }

    # Écriture du fichier de sortie
    print()
    print(f"[écriture] {output_path} ... ", end="")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(audit_results, f, ensure_ascii=False, indent=2)
        print("OK")
    except OSError as exc:
        print("ÉCHEC")
        print(f"[erreur] Impossible d'écrire le fichier : {exc}")
        return 1

    print()
    print("=" * 68)
    print("[SUCCÈS] Fusion terminée")
    print(f"  Fichier produit   : {output_path}")
    print(f"  Critères répondus : {metrics['criteres_repondus']}/{len(ref_criteres)}")
    if metrics["completude_globale_pct"] is not None:
        print(f"  Complétude globale : {metrics['completude_globale_pct']:.1f}%")
    if metrics["potentiel_optimisation_global_pct"] is not None:
        print(f"  Potentiel global  : {metrics['potentiel_optimisation_global_pct']:.1f}%")
    print("=" * 68)

    return 0


if __name__ == "__main__":
    sys.exit(main())
