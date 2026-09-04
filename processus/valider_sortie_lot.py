#!/usr/bin/env python3
"""
Validateur de contrat pour les sorties de lots d'audit EOF multi-agents.

POURQUOI CE SCRIPT EXISTE
-------------------------
Le processus d'audit EOF devient multi-agents : chaque lot (agent, script, humain)
écrit UN fichier de résultats, qu'un script de fusion consolide ensuite. Pour que
ça tienne, il faut un contrat de sortie strict, validé AVANT la fusion. Une sortie
mal formée fausse un chiffre de livrable sans rien casser visiblement : le radar
EOF agrège des verdicts, et une valeur hors vocabulaire ou un score incohérent se
propage silencieusement jusqu'au PDF client.

Ce script refuse le non conforme au lieu de le fusionner. Zéro tolérance : un lot
qui ne respecte pas le contrat ne passe pas. Motif : mieux vaut un rapport
incomplet qu'un rapport faux.

CE QU'IL VALIDE, EXHAUSTIVEMENT
-------------------------------
  - Structure JSON : métadonnées racine (lot_id, genere_le, entrees, criteres)
  - Champs requis et champs interdits (poids, potentiel_max, dimension, critere)
  - `id` existe au référentiel EOF (54 critères) ou au diagnostic rapide (16 questions)
  - `reponse` appartient au vocabulaire du référentiel POUR CE CRITÈRE
  - `coefficient` cohérent avec options_evaluation_coefficient du référentiel
  - Cohérence `reponse`/`coefficient` : null ensemble ou non-null ensemble
  - Cohérence `provenance`/`source` : requis si reponse ou contexte non null
  - Pas d'`id` en doublon dans un même fichier
  - Pas de champs inconnus (validation stricte)

Contrainte technique : bibliothèque standard seulement, pas de jsonschema ni pyyaml.
Motif : portabilité. Un autre harnais doit pouvoir lire le schéma et appliquer ce
validateur sans dépendances externes.

Usage :
    python3 valider_sortie_lot.py <fichier-de-lot.json>

Code de sortie : 0 si conforme, 1 sinon.

Alignement de style avec check_efootprint_contract.py et check_genericite.py :
  - Bandeau visuel avec séparateur
  - Préfixes [OK] / [ÉCHEC] / [info]
  - Message final pédagogique
  - Sortie structurée : liste des violations, puis verdict
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Racine du projet : ce script vit dans processus/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENTIEL_PATH = (
    PROJECT_ROOT
    / ".claude/skills/eof/docs/EOF-V.1.1 (EROOM Optimization Framework) - Template - Français"
    / "eof-referentiel.json"
)
SCHEMA_PATH = PROJECT_ROOT / "processus" / "schema-sortie-lot.json"

# Champs interdits dans une entrée de critère (viennent du référentiel, pas du lot)
FORBIDDEN_FIELDS = {"poids", "potentiel_max", "dimension", "critere", "pilier"}

# Vocabulaire fermé, hérité du projet
PROVENANCE_VALUES = {"collecte", "estime", "declare", "precise", None}
CATEGORIE_VALUES = {"automatisable", "partiel", "aucune_donnee"}


# ---------------------------------------------------------------------------
# Chargement du référentiel
# ---------------------------------------------------------------------------

def load_referentiel():
    """Charge le référentiel EOF et retourne un dict {id: critere_complet}.

    Retourne (dict_criteres, dict_diagnostic, erreurs).
    """
    if not REFERENTIEL_PATH.exists():
        return None, None, [f"Référentiel introuvable : {REFERENTIEL_PATH}"]

    try:
        with open(REFERENTIEL_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return None, None, [f"Référentiel illisible : {exc}"]

    criteres = {}
    for c in data.get("criteres", []):
        cid = c.get("id")
        if cid:
            criteres[cid] = c

    diagnostic = {}
    for q in data.get("diagnostic_rapide", []):
        qid = q.get("id")
        if qid:
            diagnostic[qid] = q

    if not criteres and not diagnostic:
        return None, None, ["Référentiel vide ou mal formé"]

    return criteres, diagnostic, []


# ---------------------------------------------------------------------------
# Validation de structure
# ---------------------------------------------------------------------------

def validate_root_structure(data):
    """Valide les métadonnées racine. Retourne (violations, champs_a_valider)."""
    violations = []

    if not isinstance(data, dict):
        return [("racine", "le fichier n'est pas un objet JSON")], None

    required = {"lot_id", "genere_le", "entrees", "criteres"}
    missing = required - set(data.keys())
    if missing:
        violations.append(("racine", f"champs requis manquants : {', '.join(sorted(missing))}"))

    extra = set(data.keys()) - required
    if extra:
        violations.append(("racine", f"champs inconnus (rejet strict) : {', '.join(sorted(extra))}"))

    if "lot_id" in data and not isinstance(data["lot_id"], str):
        violations.append(("lot_id", f"doit être une chaîne, trouvé {type(data['lot_id']).__name__}"))
    elif "lot_id" in data and not data["lot_id"].strip():
        violations.append(("lot_id", "chaîne vide"))

    if "genere_le" in data and not isinstance(data["genere_le"], str):
        violations.append(("genere_le", f"doit être une chaîne ISO 8601, trouvé {type(data['genere_le']).__name__}"))
    elif "genere_le" in data:
        try:
            datetime.fromisoformat(data["genere_le"].replace("Z", "+00:00"))
        except ValueError:
            violations.append(("genere_le", f"format ISO 8601 invalide : {data['genere_le']}"))

    if "entrees" in data and not isinstance(data["entrees"], list):
        violations.append(("entrees", f"doit être une liste, trouvé {type(data['entrees']).__name__}"))

    if "criteres" in data and not isinstance(data["criteres"], list):
        violations.append(("criteres", f"doit être une liste, trouvé {type(data['criteres']).__name__}"))

    if violations:
        return violations, None

    return [], data.get("criteres", [])


def validate_entry_fields(entry, index):
    """Valide les champs d'une entrée. Retourne violations."""
    violations = []
    prefix = f"criteres[{index}]"

    if not isinstance(entry, dict):
        return [(prefix, f"doit être un objet, trouvé {type(entry).__name__}")]

    required = {"id", "categorie"}
    allowed = {
        "id", "reponse", "coefficient", "provenance", "source",
        "contexte", "categorie", "sans_objet"
    }

    missing = required - set(entry.keys())
    if missing:
        violations.append((prefix, f"champs requis manquants : {', '.join(sorted(missing))}"))

    # Champs interdits
    forbidden_present = FORBIDDEN_FIELDS & set(entry.keys())
    if forbidden_present:
        violations.append((
            prefix,
            f"champs interdits détectés (viennent du référentiel, pas du lot) : {', '.join(sorted(forbidden_present))}"
        ))

    # Champs inconnus
    extra = set(entry.keys()) - allowed
    if extra:
        violations.append((prefix, f"champs inconnus (rejet strict) : {', '.join(sorted(extra))}"))

    # Type de base pour id
    if "id" in entry and not isinstance(entry["id"], str):
        violations.append((f"{prefix}.id", f"doit être une chaîne, trouvé {type(entry['id']).__name__}"))

    # Vocabulaires fermés
    if "categorie" in entry and entry["categorie"] not in CATEGORIE_VALUES:
        violations.append((
            f"{prefix}.categorie",
            f"valeur hors vocabulaire : '{entry['categorie']}' (attendu : {', '.join(sorted(str(v) for v in CATEGORIE_VALUES))})"
        ))

    if "provenance" in entry and entry["provenance"] not in PROVENANCE_VALUES:
        violations.append((
            f"{prefix}.provenance",
            f"valeur hors vocabulaire : '{entry['provenance']}' (attendu : collecte, estime, declare, precise ou null)"
        ))

    return violations


def validate_coherence(entry, index, ref_criteres, ref_diagnostic):
    """Valide la cohérence sémantique d'une entrée. Retourne violations."""
    violations = []
    prefix = f"criteres[{index}]"

    cid = entry.get("id")
    if not cid:
        return violations  # déjà signalé par validate_entry_fields

    # L'id existe-t-il au référentiel ?
    ref = ref_criteres.get(cid) or ref_diagnostic.get(cid)
    if not ref:
        violations.append((
            f"{prefix}.id",
            f"identifiant '{cid}' absent du référentiel EOF (54 critères 1.1-6.10 + 16 questions 0.1-0.16)"
        ))
        return violations  # impossible de valider reponse/score sans référentiel

    reponse = entry.get("reponse")
    coefficient = entry.get("coefficient")
    contexte = entry.get("contexte")
    provenance = entry.get("provenance")
    source = entry.get("source")

    # Cohérence reponse / coefficient (dépend du type de critère)
    is_diagnostic = cid in ref_diagnostic

    if reponse is None and coefficient is not None:
        violations.append((f"{prefix}.coefficient", "doit être null si reponse est null"))

    if reponse is not None:
        # Pour le diagnostic rapide, coefficient doit être null (pas de coefficient au référentiel)
        # Pour les critères du référentiel, coefficient doit être non-null
        if is_diagnostic and coefficient is not None:
            violations.append((
                f"{prefix}.coefficient",
                "doit être null pour une question du diagnostic rapide (pas de coefficient défini au référentiel)"
            ))
        elif not is_diagnostic and coefficient is None:
            violations.append((f"{prefix}.coefficient", "doit être non-null si reponse est non-null"))

    # Cohérence reponse / provenance / source
    if reponse is not None or contexte:
        if provenance is None:
            violations.append((f"{prefix}.provenance", "requis si reponse ou contexte non null"))
        if not source:
            violations.append((f"{prefix}.source", "requis et non vide si reponse ou contexte non null"))

    # Validation du vocabulaire de reponse (si non null)
    if reponse is not None:
        # Critères du référentiel (1.1-6.10) : options_evaluation
        if cid in ref_criteres:
            options = ref_criteres[cid].get("options_evaluation", [])
            if reponse not in options:
                violations.append((
                    f"{prefix}.reponse",
                    f"'{reponse}' hors vocabulaire pour ce critère (attendu : {', '.join(options)})"
                ))

            # Validation du coefficient
            coefficient_map = ref_criteres[cid].get("options_evaluation_coefficient", {})
            expected_coefficient = coefficient_map.get(reponse)
            if expected_coefficient is not None and coefficient != expected_coefficient:
                violations.append((
                    f"{prefix}.coefficient",
                    f"incohérent avec options_evaluation_coefficient : attendu {expected_coefficient}, trouvé {coefficient}"
                ))

        # Questions du diagnostic rapide (0.1-0.16) : crans
        elif cid in ref_diagnostic:
            crans = ref_diagnostic[cid].get("crans", [])
            if reponse not in crans:
                violations.append((
                    f"{prefix}.reponse",
                    f"'{reponse}' hors vocabulaire pour cette question (attendu : {', '.join(crans)})"
                ))

    return violations


def validate_no_duplicates(entries):
    """Vérifie l'absence de doublons d'id. Retourne violations."""
    violations = []
    seen = {}
    for i, entry in enumerate(entries):
        cid = entry.get("id")
        if not cid:
            continue
        if cid in seen:
            violations.append((
                f"criteres[{i}].id",
                f"doublon détecté : '{cid}' déjà présent à l'index {seen[cid]}"
            ))
        else:
            seen[cid] = i
    return violations


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Valide le contrat de sortie d'un lot d'audit EOF. "
                    "Refuse tout fichier non conforme au lieu de le fusionner."
    )
    parser.add_argument("fichier", type=Path,
                        help="Fichier de sortie de lot à valider (JSON).")
    args = parser.parse_args()

    fichier = args.fichier
    if not fichier.exists():
        print(f"[erreur] Fichier introuvable : {fichier}")
        return 1

    try:
        with open(fichier, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"[erreur] JSON invalide : {fichier}")
        print(f"         {exc}")
        return 1
    except OSError as exc:
        print(f"[erreur] Fichier illisible : {exc}")
        return 1

    # Charger le référentiel
    ref_criteres, ref_diagnostic, ref_errors = load_referentiel()
    if ref_errors:
        print("[erreur] Impossible de charger le référentiel EOF :")
        for err in ref_errors:
            print(f"         {err}")
        return 1

    print("=" * 68)
    print(f"  VALIDATION SORTIE LOT EOF — {fichier.name}")
    print(f"  fichier     : {fichier}")
    print(f"  référentiel : {REFERENTIEL_PATH.relative_to(PROJECT_ROOT)}")
    print("=" * 68)
    print()

    violations = []

    # 1. Structure racine
    root_violations, entries = validate_root_structure(data)
    violations.extend(root_violations)

    if entries is None:
        print(f"[ÉCHEC] Structure racine invalide ({len(root_violations)} erreur(s)) :")
        for loc, msg in violations:
            print(f"    {loc} : {msg}")
        print()
        print("Impossible de continuer sans structure valide.")
        return 1

    # 2. Validation de chaque entrée
    for i, entry in enumerate(entries):
        violations.extend(validate_entry_fields(entry, i))
        violations.extend(validate_coherence(entry, i, ref_criteres, ref_diagnostic))

    # 3. Doublons d'id
    violations.extend(validate_no_duplicates(entries))

    # Rapport
    if violations:
        print(f"[ÉCHEC] {len(violations)} violation(s) détectée(s) :")
        for loc, msg in violations:
            print(f"    {loc} : {msg}")
        print()
        print("Le contrat n'est pas respecté. Ce fichier ne peut pas être fusionné.")
        print("Corriger les violations ci-dessus avant de relancer la fusion.")
        return 1

    print(f"[OK] {len(entries)} entrée(s) validée(s), 0 violation.")
    print()
    print("[SUCCÈS] Contrat respecté. Ce fichier peut être fusionné.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
