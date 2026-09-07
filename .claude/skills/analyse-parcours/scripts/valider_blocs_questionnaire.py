#!/usr/bin/env python3
"""
Validateur de la bibliotheque de blocs de questionnaire EOF.

Ce script valide questionnaire-blocs.json contre eof-referentiel.json.

Il verifie :
- La structure JSON et les cles obligatoires/interdites
- Les valeurs des champs enumeres (fichier, phase, type)
- La coherence entre le type de bloc et ses cles (direct vs compose)
- L'existence des criteres cites dans le referentiel
- La correspondance exacte des libelles de reponse avec le referentiel
- L'absence de doublons (id de bloc, options identiques dans un meme bloc)
- La coherence des criteres dans un bloc compose (memes criteres dans toutes les options)
- Les champs non vides (titre, question)

Ce qu'il ne verifie PAS :
- La fidelite de la question a la methode du critere (jugement humain requis)
- La pertinence du regroupement des criteres dans un bloc compose
- La repartition equilibree entre fichiers ou phases

Usage :
    python3 valider_blocs_questionnaire.py [--blocs PATH] [--referentiel PATH] [--autotest]

Codes de sortie :
    0 : validation reussie
    1 : erreurs de validation detectees
    2 : erreur de lecture des fichiers ou autre erreur systeme
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


# Chemins par defaut, resolus depuis l'emplacement de CE fichier et non depuis le
# repertoire courant : sinon le script ne fonctionne que lance depuis la racine du
# depot, et rend une erreur "fichier introuvable" trompeuse partout ailleurs.
_SCRIPTS_DIR = Path(__file__).resolve().parent
_RACINE_DEPOT = _SCRIPTS_DIR.parents[3]

DEFAULT_BLOCS = str(_SCRIPTS_DIR / "questionnaire-blocs.json")
DEFAULT_REFERENTIEL = str(
    _RACINE_DEPOT
    / ".claude/skills/eof/docs"
    / "EOF-V.1.1 (EROOM Optimization Framework) - Template - Français"
    / "eof-referentiel.json"
)


class Validateur:
    """Valide la bibliotheque de blocs contre le referentiel EOF."""

    def __init__(self, blocs_data: Dict[str, Any], referentiel_data: Dict[str, Any]):
        self.blocs_data = blocs_data
        self.referentiel_data = referentiel_data
        self.erreurs: List[str] = []

        # Construire l'index des criteres du referentiel
        self.criteres_detailles = {c["id"]: c for c in referentiel_data.get("criteres", [])}
        self.criteres_diag_rapide = {c["id"]: c for c in referentiel_data.get("diagnostic_rapide", [])}
        self.tous_criteres = {**self.criteres_detailles, **self.criteres_diag_rapide}

    def valider(self) -> bool:
        """Lance toutes les validations. Retourne True si tout est valide."""
        self._valider_structure_racine()

        if "blocs" not in self.blocs_data:
            return len(self.erreurs) == 0

        blocs = self.blocs_data["blocs"]
        if not isinstance(blocs, list):
            self.erreurs.append("La cle 'blocs' doit etre une liste")
            return False

        ids_vus = set()

        for i, bloc in enumerate(blocs):
            id_bloc = bloc.get("id", f"<bloc {i}>")

            # 1. Verifier les doublons d'id
            if "id" in bloc:
                if bloc["id"] in ids_vus:
                    self.erreurs.append(f"{id_bloc}: id de bloc en doublon")
                ids_vus.add(bloc["id"])

            # 2. Verifier les cles
            self._valider_cles_bloc(bloc, id_bloc)

            # 3. Verifier les enums
            self._valider_enums(bloc, id_bloc)

            # 4. Verifier la coherence type/cles
            self._valider_coherence_type(bloc, id_bloc)

            # 5. Verifier l'existence des criteres
            self._valider_existence_criteres(bloc, id_bloc)

            # 6. Verifier les libelles de reponse
            self._valider_libelles_reponses(bloc, id_bloc)

            # 7 & 8. Pour les blocs composes : options identiques et coherence des criteres
            if bloc.get("type") == "compose":
                self._valider_bloc_compose(bloc, id_bloc)

            # 9. Verifier les champs non vides
            self._valider_champs_non_vides(bloc, id_bloc)

        return len(self.erreurs) == 0

    def _valider_structure_racine(self):
        """Valide la structure de premier niveau."""
        cles_obligatoires = {"version", "blocs"}
        cles_autorisees = cles_obligatoires

        for cle in cles_obligatoires:
            if cle not in self.blocs_data:
                self.erreurs.append(f"Cle obligatoire manquante a la racine : {cle}")

        for cle in self.blocs_data:
            if cle not in cles_autorisees:
                self.erreurs.append(f"Cle inconnue a la racine : {cle}")

    def _valider_cles_bloc(self, bloc: Dict[str, Any], id_bloc: str):
        """Valide les cles d'un bloc."""
        cles_obligatoires = {"id", "fichier", "phase", "titre", "type", "question"}
        cles_optionnelles = {"critere", "options", "aide", "note"}
        cles_autorisees = cles_obligatoires | cles_optionnelles

        for cle in cles_obligatoires:
            if cle not in bloc:
                self.erreurs.append(f"{id_bloc}: cle obligatoire manquante : {cle}")

        for cle in bloc:
            if cle not in cles_autorisees:
                self.erreurs.append(f"{id_bloc}: cle inconnue : {cle}")

    def _valider_enums(self, bloc: Dict[str, Any], id_bloc: str):
        """Valide les champs enumeres."""
        if "fichier" in bloc and bloc["fichier"] not in {"produit-usage", "technique"}:
            self.erreurs.append(f"{id_bloc}: fichier invalide : {bloc['fichier']}")

        if "phase" in bloc and bloc["phase"] not in {"porte", "detail"}:
            self.erreurs.append(f"{id_bloc}: phase invalide : {bloc['phase']}")

        if "type" in bloc and bloc["type"] not in {"direct", "compose"}:
            self.erreurs.append(f"{id_bloc}: type invalide : {bloc['type']}")

    def _valider_coherence_type(self, bloc: Dict[str, Any], id_bloc: str):
        """Valide la coherence entre le type et les cles presentes."""
        if bloc.get("type") == "direct":
            if "critere" not in bloc:
                self.erreurs.append(f"{id_bloc}: bloc direct sans cle 'critere'")
            if "options" in bloc:
                self.erreurs.append(f"{id_bloc}: bloc direct ne doit pas avoir de cle 'options'")

        elif bloc.get("type") == "compose":
            if "critere" in bloc:
                self.erreurs.append(f"{id_bloc}: bloc compose ne doit pas avoir de cle 'critere'")
            if "options" not in bloc:
                self.erreurs.append(f"{id_bloc}: bloc compose sans cle 'options'")

    def _valider_existence_criteres(self, bloc: Dict[str, Any], id_bloc: str):
        """Valide que les criteres cites existent dans le referentiel."""
        if bloc.get("type") == "direct" and "critere" in bloc:
            critere_id = bloc["critere"]
            if critere_id not in self.tous_criteres:
                self.erreurs.append(f"{id_bloc}: critere inexistant : {critere_id}")

        elif bloc.get("type") == "compose" and "options" in bloc:
            for i, option in enumerate(bloc["options"]):
                if not isinstance(option, dict):
                    continue
                reponses = option.get("reponses", {})
                for critere_id in reponses:
                    if critere_id not in self.tous_criteres:
                        self.erreurs.append(f"{id_bloc}, option {i}: critere inexistant : {critere_id}")

    def _valider_libelles_reponses(self, bloc: Dict[str, Any], id_bloc: str):
        """Valide que les libelles de reponse correspondent au referentiel."""
        if bloc.get("type") != "compose" or "options" not in bloc:
            return

        for i, option in enumerate(bloc["options"]):
            if not isinstance(option, dict):
                continue

            reponses = option.get("reponses", {})
            for critere_id, libelle_reponse in reponses.items():
                if critere_id not in self.tous_criteres:
                    continue  # Deja signale par _valider_existence_criteres

                critere = self.tous_criteres[critere_id]

                # Determiner les options valides selon le type de critere
                if critere_id in self.criteres_diag_rapide:
                    # Diagnostic rapide : utilise "crans"
                    options_valides = set(critere.get("crans", []))
                else:
                    # Critere detaille : utilise "options_evaluation_coefficient"
                    options_valides = set(critere.get("options_evaluation_coefficient", {}).keys())

                if libelle_reponse not in options_valides:
                    self.erreurs.append(
                        f"{id_bloc}, option {i}: libelle de reponse invalide pour {critere_id} : '{libelle_reponse}'"
                    )

    def _valider_bloc_compose(self, bloc: Dict[str, Any], id_bloc: str):
        """Valide les contraintes specifiques aux blocs composes."""
        if "options" not in bloc:
            return

        options = bloc["options"]
        if not isinstance(options, list):
            return

        # 7. Verifier qu'il n'y a pas deux options identiques
        reponses_vues = []
        for i, option in enumerate(options):
            if not isinstance(option, dict):
                continue

            reponses = option.get("reponses", {})
            # Convertir en tuple trie pour pouvoir comparer
            reponses_tuple = tuple(sorted(reponses.items()))

            if reponses_tuple in reponses_vues:
                self.erreurs.append(f"{id_bloc}, option {i}: option identique a une autre (memes reponses)")
            reponses_vues.append(reponses_tuple)

        # 8. Verifier que toutes les options renseignent exactement les memes criteres
        ensemble_criteres_par_option = []
        for i, option in enumerate(options):
            if not isinstance(option, dict):
                continue

            reponses = option.get("reponses", {})
            ensemble_criteres = set(reponses.keys())
            ensemble_criteres_par_option.append((i, ensemble_criteres))

        if ensemble_criteres_par_option:
            premier_ensemble = ensemble_criteres_par_option[0][1]
            for i, ensemble in ensemble_criteres_par_option[1:]:
                if ensemble != premier_ensemble:
                    manquants = premier_ensemble - ensemble
                    en_trop = ensemble - premier_ensemble
                    msg_parts = [f"{id_bloc}: les options ne renseignent pas les memes criteres"]
                    if manquants:
                        msg_parts.append(f"option {i} manque : {manquants}")
                    if en_trop:
                        msg_parts.append(f"option {i} en trop : {en_trop}")
                    self.erreurs.append(" - ".join(msg_parts))

    def _valider_champs_non_vides(self, bloc: Dict[str, Any], id_bloc: str):
        """Valide que les champs texte ne sont pas vides."""
        for champ in ["titre", "question"]:
            if champ in bloc:
                valeur = bloc[champ]
                if not isinstance(valeur, str) or not valeur.strip():
                    self.erreurs.append(f"{id_bloc}: {champ} vide")

    def imprimer_etat_des_lieux(self):
        """Imprime un recapitulatif de la bibliotheque."""
        if "blocs" not in self.blocs_data:
            return

        blocs = self.blocs_data["blocs"]

        # Compter par fichier et phase
        compteurs_fichier = {}
        compteurs_phase = {}

        for bloc in blocs:
            fichier = bloc.get("fichier", "inconnu")
            phase = bloc.get("phase", "inconnu")

            compteurs_fichier[fichier] = compteurs_fichier.get(fichier, 0) + 1
            compteurs_phase[phase] = compteurs_phase.get(phase, 0) + 1

        # Compter les criteres couverts et le potentiel
        criteres_couverts = set()
        potentiel_total = 0.0

        for bloc in blocs:
            if bloc.get("type") == "direct" and "critere" in bloc:
                critere_id = bloc["critere"]
                criteres_couverts.add(critere_id)

                # Ajouter le potentiel si c'est un critere detaille
                if critere_id in self.criteres_detailles:
                    potentiel_total += self.criteres_detailles[critere_id].get("potentiel_max", 0)

            elif bloc.get("type") == "compose" and "options" in bloc:
                for option in bloc["options"]:
                    if isinstance(option, dict) and "reponses" in option:
                        for critere_id in option["reponses"]:
                            criteres_couverts.add(critere_id)

                            # Ajouter le potentiel si c'est un critere detaille (une seule fois)
                            if critere_id in self.criteres_detailles:
                                potentiel_total += self.criteres_detailles[critere_id].get("potentiel_max", 0)

        # Retirer les doublons de potentiel (si un critere apparait dans plusieurs blocs composes)
        # Recalculer correctement
        criteres_detailles_couverts = criteres_couverts & set(self.criteres_detailles.keys())
        potentiel_total = sum(
            self.criteres_detailles[c].get("potentiel_max", 0)
            for c in criteres_detailles_couverts
        )

        print("\n----- ETAT DES LIEUX DE LA BIBLIOTHEQUE -----")
        print(f"Version : {self.blocs_data.get('version', 'non specifiee')}")
        print(f"Nombre total de blocs : {len(blocs)}")
        print(f"\nRepartition par fichier :")
        for fichier, count in sorted(compteurs_fichier.items()):
            print(f"  {fichier}: {count} blocs")
        print(f"\nRepartition par phase :")
        for phase, count in sorted(compteurs_phase.items()):
            print(f"  {phase}: {count} blocs")
        print(f"\nCriteres couverts : {len(criteres_couverts)} / {len(self.tous_criteres)}")
        print(f"  - Diagnostic rapide : {len(criteres_couverts & set(self.criteres_diag_rapide.keys()))} / {len(self.criteres_diag_rapide)}")
        print(f"  - Criteres detailles : {len(criteres_detailles_couverts)} / {len(self.criteres_detailles)}")
        print(f"\nPotentiel couvert (criteres detailles uniquement) : {potentiel_total:.1f}")
        print(f"  Note : Les questions du diagnostic rapide n'ont pas de potentiel_max.")
        print("---------------------------------------------\n")


def charger_json(chemin: Path) -> Dict[str, Any]:
    """Charge un fichier JSON."""
    with open(chemin, "r", encoding="utf-8") as f:
        return json.load(f)


def autotest() -> bool:
    """Execute les autotests. Retourne True si tous les tests passent."""
    print("----- AUTOTESTS -----")

    # Referentiel de test minimaliste
    referentiel_test = {
        "criteres": [
            {
                "id": "1.1",
                "potentiel_max": 2.0,
                "options_evaluation_coefficient": {
                    "✅ Point fort confirmé": 0,
                    "💡 Potentiel d'amélioration identifié": 1
                }
            },
            {
                "id": "1.2",
                "potentiel_max": 1.5,
                "options_evaluation_coefficient": {
                    "✅ Point fort confirmé": 0,
                    "💡 Potentiel d'amélioration identifié": 1
                }
            },
            {
                "id": "6.1",
                "potentiel_max": 2.0,
                "options_evaluation_coefficient": {
                    "🟢 Facile à modifier": 0,
                    "🟡 Effort modéré": 0.5,
                    "🔴 Difficile à changer": 1
                }
            }
        ],
        "diagnostic_rapide": [
            {
                "id": "0.1",
                "crans": [
                    "1 - Impact nul",
                    "5 - Impact critique"
                ]
            }
        ]
    }

    tests_reussis = 0
    tests_total = 0

    # Test 1 : Bloc valide direct
    tests_total += 1
    blocs_valide = {
        "version": 1,
        "blocs": [
            {
                "id": "test-1",
                "fichier": "produit-usage",
                "phase": "porte",
                "titre": "Test",
                "type": "direct",
                "critere": "0.1",
                "question": "Question test ?"
            }
        ]
    }
    v = Validateur(blocs_valide, referentiel_test)
    if v.valider():
        tests_reussis += 1
        print("✓ Test 1 : Bloc direct valide")
    else:
        print(f"✗ Test 1 : Bloc direct valide - ECHEC : {v.erreurs}")

    # Test 2 : ID en doublon (doit echouer)
    tests_total += 1
    blocs_doublon = {
        "version": 1,
        "blocs": [
            {"id": "test-1", "fichier": "technique", "phase": "porte", "titre": "A", "type": "direct", "critere": "0.1", "question": "Q1"},
            {"id": "test-1", "fichier": "technique", "phase": "porte", "titre": "B", "type": "direct", "critere": "0.1", "question": "Q2"}
        ]
    }
    v = Validateur(blocs_doublon, referentiel_test)
    if not v.valider() and any("doublon" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 2 : Detection doublon d'id")
    else:
        print(f"✗ Test 2 : Detection doublon d'id - ECHEC")

    # Test 3 : Cle obligatoire manquante (doit echouer)
    tests_total += 1
    blocs_incomplet = {
        "version": 1,
        "blocs": [
            {"id": "test-3", "fichier": "technique", "phase": "porte", "type": "direct", "critere": "0.1", "question": "Q"}
            # Manque "titre"
        ]
    }
    v = Validateur(blocs_incomplet, referentiel_test)
    if not v.valider() and any("titre" in e and "manquante" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 3 : Detection cle obligatoire manquante")
    else:
        print(f"✗ Test 3 : Detection cle obligatoire manquante - ECHEC")

    # Test 4 : Fichier invalide (doit echouer)
    tests_total += 1
    blocs_fichier_invalide = {
        "version": 1,
        "blocs": [
            {"id": "test-4", "fichier": "INVALIDE", "phase": "porte", "titre": "T", "type": "direct", "critere": "0.1", "question": "Q"}
        ]
    }
    v = Validateur(blocs_fichier_invalide, referentiel_test)
    if not v.valider() and any("fichier invalide" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 4 : Detection fichier invalide")
    else:
        print(f"✗ Test 4 : Detection fichier invalide - ECHEC")

    # Test 5 : Bloc direct avec options (doit echouer)
    tests_total += 1
    blocs_direct_options = {
        "version": 1,
        "blocs": [
            {
                "id": "test-5",
                "fichier": "technique",
                "phase": "porte",
                "titre": "T",
                "type": "direct",
                "critere": "0.1",
                "question": "Q",
                "options": []
            }
        ]
    }
    v = Validateur(blocs_direct_options, referentiel_test)
    if not v.valider() and any("direct" in e and "options" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 5 : Detection bloc direct avec options")
    else:
        print(f"✗ Test 5 : Detection bloc direct avec options - ECHEC")

    # Test 6 : Bloc compose sans options (doit echouer)
    tests_total += 1
    blocs_compose_sans_options = {
        "version": 1,
        "blocs": [
            {
                "id": "test-6",
                "fichier": "technique",
                "phase": "detail",
                "titre": "T",
                "type": "compose",
                "question": "Q"
            }
        ]
    }
    v = Validateur(blocs_compose_sans_options, referentiel_test)
    if not v.valider() and any("compose" in e and "options" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 6 : Detection bloc compose sans options")
    else:
        print(f"✗ Test 6 : Detection bloc compose sans options - ECHEC")

    # Test 7 : Critere inexistant (doit echouer)
    tests_total += 1
    blocs_critere_inexistant = {
        "version": 1,
        "blocs": [
            {
                "id": "test-7",
                "fichier": "technique",
                "phase": "porte",
                "titre": "T",
                "type": "direct",
                "critere": "99.99",
                "question": "Q"
            }
        ]
    }
    v = Validateur(blocs_critere_inexistant, referentiel_test)
    if not v.valider() and any("inexistant" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 7 : Detection critere inexistant")
    else:
        print(f"✗ Test 7 : Detection critere inexistant - ECHEC")

    # Test 8 : Libelle de reponse invalide (doit echouer)
    tests_total += 1
    blocs_libelle_invalide = {
        "version": 1,
        "blocs": [
            {
                "id": "test-8",
                "fichier": "technique",
                "phase": "detail",
                "titre": "T",
                "type": "compose",
                "question": "Q",
                "options": [
                    {
                        "libelle": "Option 1",
                        "reponses": {
                            "1.1": "REPONSE INVALIDE"
                        }
                    }
                ]
            }
        ]
    }
    v = Validateur(blocs_libelle_invalide, referentiel_test)
    if not v.valider() and any("libelle de reponse invalide" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 8 : Detection libelle de reponse invalide")
    else:
        print(f"✗ Test 8 : Detection libelle de reponse invalide - ECHEC")

    # Test 9 : Options identiques dans un bloc compose (doit echouer)
    tests_total += 1
    blocs_options_identiques = {
        "version": 1,
        "blocs": [
            {
                "id": "test-9",
                "fichier": "technique",
                "phase": "detail",
                "titre": "T",
                "type": "compose",
                "question": "Q",
                "options": [
                    {
                        "libelle": "Option 1",
                        "reponses": {"1.1": "✅ Point fort confirmé"}
                    },
                    {
                        "libelle": "Option 2",
                        "reponses": {"1.1": "✅ Point fort confirmé"}
                    }
                ]
            }
        ]
    }
    v = Validateur(blocs_options_identiques, referentiel_test)
    if not v.valider() and any("option identique" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 9 : Detection options identiques")
    else:
        print(f"✗ Test 9 : Detection options identiques - ECHEC")

    # Test 10 : Criteres incoherents entre options d'un bloc compose (doit echouer)
    tests_total += 1
    blocs_criteres_incoherents = {
        "version": 1,
        "blocs": [
            {
                "id": "test-10",
                "fichier": "technique",
                "phase": "detail",
                "titre": "T",
                "type": "compose",
                "question": "Q",
                "options": [
                    {
                        "libelle": "Option 1",
                        "reponses": {
                            "1.1": "✅ Point fort confirmé",
                            "1.2": "✅ Point fort confirmé"
                        }
                    },
                    {
                        "libelle": "Option 2",
                        "reponses": {
                            "1.1": "💡 Potentiel d'amélioration identifié"
                            # Manque 1.2
                        }
                    }
                ]
            }
        ]
    }
    v = Validateur(blocs_criteres_incoherents, referentiel_test)
    if not v.valider() and any("memes criteres" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 10 : Detection criteres incoherents entre options")
    else:
        print(f"✗ Test 10 : Detection criteres incoherents entre options - ECHEC")

    # Test 11 : Champ vide (doit echouer)
    tests_total += 1
    blocs_champ_vide = {
        "version": 1,
        "blocs": [
            {
                "id": "test-11",
                "fichier": "technique",
                "phase": "porte",
                "titre": "",
                "type": "direct",
                "critere": "0.1",
                "question": "Q"
            }
        ]
    }
    v = Validateur(blocs_champ_vide, referentiel_test)
    if not v.valider() and any("titre vide" in e for e in v.erreurs):
        tests_reussis += 1
        print("✓ Test 11 : Detection champ vide")
    else:
        print(f"✗ Test 11 : Detection champ vide - ECHEC")

    # Test 12 : Bloc compose valide
    tests_total += 1
    blocs_compose_valide = {
        "version": 1,
        "blocs": [
            {
                "id": "test-12",
                "fichier": "technique",
                "phase": "detail",
                "titre": "Test compose",
                "type": "compose",
                "question": "Question ?",
                "options": [
                    {
                        "libelle": "Option A",
                        "reponses": {
                            "1.1": "✅ Point fort confirmé",
                            "1.2": "✅ Point fort confirmé"
                        }
                    },
                    {
                        "libelle": "Option B",
                        "reponses": {
                            "1.1": "💡 Potentiel d'amélioration identifié",
                            "1.2": "💡 Potentiel d'amélioration identifié"
                        }
                    }
                ]
            }
        ]
    }
    v = Validateur(blocs_compose_valide, referentiel_test)
    if v.valider():
        tests_reussis += 1
        print("✓ Test 12 : Bloc compose valide")
    else:
        print(f"✗ Test 12 : Bloc compose valide - ECHEC : {v.erreurs}")

    print(f"\n{tests_reussis}/{tests_total} tests reussis")
    print("---------------------\n")

    return tests_reussis == tests_total


def main():
    """Point d'entree principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Valide la bibliotheque de blocs de questionnaire EOF")
    parser.add_argument("--blocs", type=str, default=DEFAULT_BLOCS, help="Chemin vers questionnaire-blocs.json")
    parser.add_argument("--referentiel", type=str, default=DEFAULT_REFERENTIEL, help="Chemin vers eof-referentiel.json")
    parser.add_argument("--autotest", action="store_true", help="Execute les autotests")

    args = parser.parse_args()

    if args.autotest:
        if not autotest():
            return 2
        return 0

    # Validation normale
    try:
        blocs_path = Path(args.blocs)
        referentiel_path = Path(args.referentiel)

        if not blocs_path.exists():
            print(f"ERREUR : Fichier introuvable : {blocs_path}", file=sys.stderr)
            return 2

        if not referentiel_path.exists():
            print(f"ERREUR : Fichier introuvable : {referentiel_path}", file=sys.stderr)
            return 2

        print(f"Chargement de {blocs_path}...")
        blocs_data = charger_json(blocs_path)

        print(f"Chargement de {referentiel_path}...")
        referentiel_data = charger_json(referentiel_path)

        print("Validation en cours...\n")

        validateur = Validateur(blocs_data, referentiel_data)
        valide = validateur.valider()

        if not valide:
            print("----- ERREURS DE VALIDATION -----")
            for erreur in validateur.erreurs:
                print(f"  ✗ {erreur}")
            print("---------------------------------\n")

            validateur.imprimer_etat_des_lieux()

            return 1

        print("✓ Validation reussie : aucune erreur detectee.\n")

        validateur.imprimer_etat_des_lieux()

        return 0

    except json.JSONDecodeError as e:
        print(f"ERREUR : JSON invalide : {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
