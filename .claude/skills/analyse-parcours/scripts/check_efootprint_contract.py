#!/usr/bin/env python3
"""
Filet de sécurité du refactoring e-footprint : contrôle de CONTRAT sur la sortie.

POURQUOI CE SCRIPT EXISTE
-------------------------
Le rapport HTML lit `efootprint-synthese-python.json` clé par clé avec
`.get()`. S'il manque une clé, il n'échoue pas : il affiche un trou, ou une
valeur par défaut, SANS AUCUNE ERREUR. Un refactoring peut donc casser le
rapport en silence.

Ce script compare une BASELINE figée à une sortie fraîche et signale :
  - les chemins PERDUS            -> ERREUR (le rapport perdra de l'information)
  - les chemins CHANGÉS DE TYPE   -> ERREUR (ex. un float devenu str)
  - les chemins AJOUTÉS           -> information seulement (une addition est licite)

CE QU'IL NE FAIT PAS, ET C'EST IMPORTANT
----------------------------------------
Il ne vérifie PAS que les valeurs sont JUSTES. Un total qui passerait de 174 à
300 kg avec toutes les clés en place ne serait pas détecté ici. C'est le rôle de
l'option `--total`, à utiliser en complément et non à la place.

Usage :
    # 1. Figer la baseline AVANT de toucher au code (à faire une seule fois)
    python3 check_efootprint_contract.py --freeze audits/<site>

    # 2. Après chaque modification : comparer
    python3 check_efootprint_contract.py audits/<site>

    # 3. Comparaison + vérification numérique du total
    python3 check_efootprint_contract.py audits/<site> --total 174.076 --tol 1e-3

Options utiles :
    --baseline <chemin>   baseline explicite (défaut : tmp/baselines/<site>-efootprint-synthese-python.json)
    --results <chemin>    sortie à contrôler (défaut : <source_dir>/efootprint-synthese-python.json)
    --strict-added        traite aussi les chemins AJOUTÉS comme des erreurs

Code de sortie : 0 si le contrat est tenu, 1 sinon. Prévu pour un enchaînement
`&&` ou une vérification de fin de lot.

Les baselines vivent dans `tmp/baselines/`, hors git (`tmp/` est dans .gitignore) :
ce sont des artefacts de travail, pas des livrables, et elles contiennent les
valeurs mesurées du cas de test.
"""

import argparse
import json
import sys
from pathlib import Path

# Racine du projet : ce script vit dans .claude/skills/analyse-parcours/scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[4]
BASELINE_DIR = PROJECT_ROOT / "tmp" / "baselines"

SYNTHESE_FILENAME = "efootprint-synthese-python.json"

# Chemins dont la valeur change à chaque exécution sans que rien ne soit cassé.
# Comparer leur contenu n'aurait aucun sens ; leur PRÉSENCE et leur TYPE le sont
# toujours, donc ils restent dans l'inventaire des chemins.
VOLATILE_PATHS = {
    "/generated_at",
}


# ---------------------------------------------------------------------------
# Aplatissement en chemins typés
# ---------------------------------------------------------------------------

def flatten(obj, prefix=""):
    """Aplatit un JSON en {chemin: nom_de_type}.

    Un dict vide et une liste sont des feuilles : on ne descend pas dedans. Les
    listes changent de longueur d'un site à l'autre, et leur contenu n'est pas un
    contrat stable. Le type `list` suffit à détecter une disparition.
    """
    out = {}
    if isinstance(obj, dict):
        if not obj:
            out[prefix] = "dict"
        for key, value in obj.items():
            out.update(flatten(value, f"{prefix}/{key}"))
    elif isinstance(obj, list):
        out[prefix] = "list"
    else:
        out[prefix] = type(obj).__name__
    return out


def compatible(type_before, type_after):
    """Un changement de type est-il acceptable ?

    Deux tolérances, et pas une de plus :
      - int <-> float : un arrondi ou une division peut basculer l'un dans l'autre
        sans changer le sens de la valeur.
      - NoneType -> autre chose : un champ qui valait null et qui porte enfin une
        valeur est un GAIN. L'inverse (une valeur devenue null) est une PERTE et
        reste signalée.
    """
    if type_before == type_after:
        return True
    numeric = {"int", "float"}
    if type_before in numeric and type_after in numeric:
        return True
    if type_before == "NoneType":
        return True
    return False


# ---------------------------------------------------------------------------
# Localisation des fichiers
# ---------------------------------------------------------------------------

def default_baseline_path(source_dir):
    """tmp/baselines/<nom-du-cas-d-audit>-efootprint-synthese-python.json"""
    return BASELINE_DIR / f"{source_dir.name}-{SYNTHESE_FILENAME}"


def load_json(path, label):
    if not path.exists():
        print(f"[erreur] {label} introuvable : {path}")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"[erreur] {label} n'est pas un JSON valide : {path}")
        print(f"         {exc}")
        return None


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def freeze(source_dir, results_path, baseline_path):
    """Copie la sortie actuelle comme référence."""
    data = load_json(results_path, "fichier de résultats")
    if data is None:
        return 1

    paths = flatten(data)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[freeze] Baseline figée : {baseline_path}")
    print(f"[freeze] {len(paths)} chemins sous contrat.")
    total = data.get("totals", {}).get("total_kg_co2e_per_year")
    if total is not None:
        print(f"[freeze] Total de référence : {total} kg CO2e/an")
        print(f"[freeze] Pour verrouiller aussi la valeur : --total {total}")
    return 0


def compare(baseline, results, strict_added):
    """Compare deux sorties. Retourne (nb_erreurs, nb_ajouts)."""
    before = flatten(baseline)
    after = flatten(results)

    lost = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    retyped = sorted(
        (p, before[p], after[p])
        for p in set(before) & set(after)
        if not compatible(before[p], after[p])
    )

    print(f"[contrat] {len(before)} chemins en baseline, {len(after)} dans la sortie.")
    print()

    if lost:
        print(f"[ERREUR] {len(lost)} chemin(s) PERDU(S) — le rapport perdra cette information :")
        for path in lost:
            print(f"    - {path}   (était {before[path]})")
        print()
    else:
        print("[OK] 0 clé manquante.")

    if retyped:
        print(f"[ERREUR] {len(retyped)} chemin(s) ayant CHANGÉ DE TYPE :")
        for path, type_before, type_after in retyped:
            print(f"    - {path}   {type_before} -> {type_after}")
        print()
    else:
        print("[OK] 0 changement de type incompatible.")

    if added:
        marker = "ERREUR" if strict_added else "info"
        print(f"[{marker}] {len(added)} chemin(s) AJOUTÉ(S) :")
        for path in added:
            print(f"    + {path}   ({after[path]})")
        print()
    else:
        print("[info] 0 chemin ajouté.")

    errors = len(lost) + len(retyped) + (len(added) if strict_added else 0)
    return errors, len(added)


def check_total(results, expected, tolerance):
    """Vérifie le total annuel. Complète le contrôle de contrat, ne le remplace pas."""
    actual = results.get("totals", {}).get("total_kg_co2e_per_year")
    if actual is None:
        print("[ERREUR] /totals/total_kg_co2e_per_year absent : total invérifiable.")
        return 1

    delta = abs(actual - expected)
    if delta <= tolerance:
        print(f"[OK] Total {actual} kg CO2e/an (attendu {expected}, écart {delta:.2e}).")
        return 0

    print(f"[ERREUR] Total {actual} kg CO2e/an, attendu {expected} "
          f"(écart {delta:.4f} > tolérance {tolerance}).")
    return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Contrôle de contrat sur efootprint-synthese-python.json "
                    "(clés présentes et typées, pas valeurs justes).",
    )
    parser.add_argument("source_dir", type=Path,
                        help="Cas d'audit, ex. audits/octo.com")
    parser.add_argument("--freeze", action="store_true",
                        help="Fige la sortie actuelle comme baseline, puis s'arrête.")
    parser.add_argument("--baseline", type=Path, default=None,
                        help="Baseline explicite (défaut : tmp/baselines/<site>-...json).")
    parser.add_argument("--results", type=Path, default=None,
                        help="Sortie à contrôler (défaut : <source_dir>/efootprint-synthese-python.json).")
    parser.add_argument("--strict-added", action="store_true",
                        help="Traite les chemins ajoutés comme des erreurs.")
    parser.add_argument("--total", type=float, default=None,
                        help="Total attendu en kg CO2e/an (vérification numérique).")
    parser.add_argument("--tol", type=float, default=1e-3,
                        help="Tolérance sur --total (défaut : 1e-3).")
    args = parser.parse_args()

    source_dir = args.source_dir
    if not source_dir.is_dir():
        print(f"[erreur] Cas d'audit introuvable : {source_dir}")
        return 1

    results_path = args.results or (source_dir / SYNTHESE_FILENAME)
    baseline_path = args.baseline or default_baseline_path(source_dir)

    if args.freeze:
        return freeze(source_dir, results_path, baseline_path)

    baseline = load_json(baseline_path, "baseline")
    if baseline is None:
        print()
        print("Aucune baseline. La figer d'abord, AVANT toute modification du code :")
        print(f"    python3 {Path(__file__).name} {source_dir} --freeze")
        return 1

    results = load_json(results_path, "fichier de résultats")
    if results is None:
        print()
        print("Générer la sortie d'abord :")
        print(f"    python3 run_efootprint.py {source_dir}")
        return 1

    print("=" * 68)
    print(f"  CONTRAT e-footprint — {source_dir.name}")
    print(f"  baseline : {baseline_path}")
    print(f"  sortie   : {results_path}")
    print("=" * 68)
    print()

    errors, _ = compare(baseline, results, args.strict_added)

    if args.total is not None:
        errors += check_total(results, args.total, args.tol)
        print()

    if errors:
        print(f"[ÉCHEC] {errors} problème(s). Le contrat n'est pas tenu.")
        return 1

    print("[SUCCÈS] Contrat tenu.")
    print("Rappel : les clés sont présentes et typées. Cela ne prouve PAS que les")
    print("valeurs sont justes (sauf pour le total, si --total a été fourni).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
