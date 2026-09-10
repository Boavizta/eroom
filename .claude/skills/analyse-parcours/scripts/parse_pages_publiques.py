#!/usr/bin/env python3
"""
Extraction de déclarations publiques de suivi d'impact environnemental depuis
les pages HTML archivées dans audits/<domaine>/pages-publiques/.

Produit pages-publiques-criteria.json, consommé par run_eof.py pour construire
un indice contextuel au critère 3.2 (jamais une réponse cochée automatiquement).

Contrainte critique : distinguer "je n'ai rien trouvé car absent" de "je n'ai
rien trouvé car échec d'extraction" - les deux doivent produire des sorties
DIFFÉRENTES et reconnaissables. Un échec silencieux fabrique un chiffre faux.

Usage :
    python3 parse_pages_publiques.py <source_dir>
    python3 parse_pages_publiques.py --autotest

Écrit <source_dir>/pages-publiques-criteria.json.
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Motifs de noms de fichiers à chercher (sans extension), par ordre de
# priorité. Générique : aucun nom propre à un site particulier.
PAGE_NAME_PATTERNS = [
    "eco-conception",
    "ecoconception",
    "numérique-responsable",
    "numerique-responsable",
    "rse-numerique",
    "declaration-environnementale",
    "empreinte-environnementale",
]

# Mots-clés de recherche pour les déclarations de suivi/mesure d'impact
# environnemental. Recherche insensible à la casse.
KEYWORDS_SUIVI = [
    "système de suivi",
    "systeme de suivi",
    "mesure de l'impact environnemental",
    "mesure de l impact environnemental",
    "suivi de l'impact",
    "suivi de l impact",
    "surveillance des émissions",
    "surveillance des emissions",
    "consommation d'énergie",
    "consommation d energie",
    "empreinte carbone",
    "empreinte environnementale",
    "mesure de la consommation",
]

# Mots-clés de recherche pour les déclarations de rétention/suppression/
# archivage/droit à l'effacement des données. Recherche insensible à la
# casse. Aucun recoupement avec KEYWORDS_SUIVI (vérifié à la main).
KEYWORDS_RETENTION = [
    "durée de conservation",
    "duree de conservation",
    "droit à l'effacement",
    "droit a l effacement",
    "politique de suppression",
    "politique d'archivage",
    "politique d archivage",
    "suppression des données",
    "suppression des donnees",
    "conservation des données",
    "conservation des donnees",
    "droit à l'oubli",
    "droit a l oubli",
    "durée de rétention",
    "duree de retention",
    "période de rétention",
    "periode de retention",
    "purge des données",
    "purge des donnees",
    "archivage des données",
    "archivage des donnees",
]


class _PagePubliqueParser(HTMLParser):
    """Extrait le texte visible depuis une page HTML.

    Ne juge rien, ne déduit rien : extrait uniquement le contenu textuel
    visible, en préservant la casse d'origine.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_fragments = []
        self.in_script_or_style = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.in_script_or_style = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.in_script_or_style = False

    def handle_data(self, data):
        if not self.in_script_or_style:
            self.text_fragments.append(data)

    def get_text(self):
        """Retourne le texte visible de la page, casse d'origine préservée."""
        return " ".join(self.text_fragments)


def split_into_sentences(text):
    """Découpe un texte en phrases, en préservant la casse d'origine.

    Retourne une liste de phrases complètes (avec leur ponctuation finale).
    """
    # Normaliser les espaces multiples
    text = re.sub(r'\s+', ' ', text).strip()

    # Split sur . ! ? suivi d'un espace et d'une majuscule, ou en fin de texte
    # Utiliser un lookahead pour ne pas consommer le début de la phrase suivante
    sentences = re.split(r'([.!?])\s+(?=[A-Z])', text)

    result = []
    i = 0
    while i < len(sentences):
        sentence = sentences[i].strip()
        if not sentence:
            i += 1
            continue

        # Ajouter le séparateur s'il existe
        if i + 1 < len(sentences) and sentences[i + 1] in '.!?':
            sentence += sentences[i + 1]
            i += 2
        else:
            # Dernier fragment, peut ne pas avoir de ponctuation
            if not sentence[-1] in '.!?':
                sentence += '.'
            i += 1

        result.append(sentence)

    return result


def extract_declarations(html_text):
    """Extrait les déclarations publiques depuis un HTML : suivi d'impact
    environnemental, et rétention/suppression/archivage des données.

    Retourne un dict avec :
    - declarations_suivi : list[dict] avec phrase complète, casse d'origine
    - declarations_retention : list[dict] avec phrase complète, casse d'origine
    - parse_success : bool (True si le parsing HTML a réussi)
    - parse_error : str|None (message d'erreur si échec)
    """
    result = {
        "declarations_suivi": [],
        "declarations_retention": [],
        "parse_success": False,
        "parse_error": None,
    }

    parser = _PagePubliqueParser()
    try:
        parser.feed(html_text)
        parser.close()
        result["parse_success"] = True
    except Exception as exc:
        result["parse_error"] = str(exc)
        return result

    text = parser.get_text()
    sentences = split_into_sentences(text)

    # Recherche de déclarations de suivi/mesure et de rétention - un seul
    # passage sur les phrases déjà découpées, extraction de la phrase entière
    seen_phrases_suivi = set()
    seen_phrases_retention = set()
    for sentence in sentences:
        sentence_lower = sentence.lower()

        for keyword in KEYWORDS_SUIVI:
            if keyword in sentence_lower:
                # Phrase entière, casse d'origine, jamais coupée au milieu d'un mot
                if sentence not in seen_phrases_suivi:
                    result["declarations_suivi"].append({
                        "phrase": sentence,
                        "mot_cle_trouve": keyword,
                    })
                    seen_phrases_suivi.add(sentence)
                break  # Une seule correspondance par phrase

        for keyword in KEYWORDS_RETENTION:
            if keyword in sentence_lower:
                if sentence not in seen_phrases_retention:
                    result["declarations_retention"].append({
                        "phrase": sentence,
                        "mot_cle_trouve": keyword,
                    })
                    seen_phrases_retention.add(sentence)
                break

    return result


def find_page_files(pages_publiques_dir):
    """Cherche les fichiers HTML de pages publiques.

    Retourne un dict :
    - found : list[Path] des fichiers trouvés
    - searched_patterns : list[str] des motifs cherchés
    """
    if not pages_publiques_dir.exists():
        return {"found": [], "searched_patterns": PAGE_NAME_PATTERNS}

    found = []
    for pattern in PAGE_NAME_PATTERNS:
        path = pages_publiques_dir / f"{pattern}.html"
        if path.exists():
            found.append(path)

    return {"found": found, "searched_patterns": PAGE_NAME_PATTERNS}


def analyze_pages_publiques(source_dir):
    """Analyse le dossier pages-publiques/ d'un audit.

    Retourne un dict avec :
    - status : "success" | "no_directory" | "no_files" | "partial_success" | "all_failed"
    - pages_publiques_dir_exists : bool
    - files_searched : list[str] motifs cherchés
    - files_found : list[str] chemins trouvés
    - files_analyzed : list[dict] résultats par fichier, chacun avec son propre
      bloc "mesure" (statut/cible/detail, convention d'état de mesure)
    - mesure : bloc top-level UNIQUEMENT dans les cas "no_directory"/"no_files"
      (rien_trouve : la sonde a bien cherché à l'emplacement attendu et n'y a
      réellement rien trouvé — ce n'est pas un échec de notre outil).
    """
    pages_publiques_dir = source_dir / "pages-publiques"
    result = {
        "pages_publiques_dir_exists": pages_publiques_dir.exists(),
        "files_searched": PAGE_NAME_PATTERNS,
        "files_found": [],
        "files_analyzed": [],
    }

    cible_dir = str(pages_publiques_dir.relative_to(source_dir))

    if not pages_publiques_dir.exists():
        result["status"] = "no_directory"
        result["mesure"] = {
            "statut": "rien_trouve",
            "cible": cible_dir,
            "detail": "dossier pages-publiques/ absent de cet audit",
        }
        return result

    search_result = find_page_files(pages_publiques_dir)
    result["files_found"] = [str(p.name) for p in search_result["found"]]

    if not search_result["found"]:
        result["status"] = "no_files"
        result["mesure"] = {
            "statut": "rien_trouve",
            "cible": cible_dir,
            "detail": f"aucun fichier parmi les motifs cherchés : {', '.join(PAGE_NAME_PATTERNS)}",
        }
        return result

    # Analyser chaque fichier trouvé
    any_success = False
    any_failure = False
    for path in search_result["found"]:
        cible_fichier = str(path.relative_to(source_dir))
        file_result = {
            "filename": path.name,
            "read_success": False,
            "read_error": None,
            "declarations": None,
        }

        try:
            html_content = path.read_text(encoding="utf-8")
            file_result["read_success"] = True
            decl = extract_declarations(html_content)
            file_result["declarations"] = decl
            if decl["parse_success"]:
                any_success = True
                file_result["mesure"] = {"statut": "ok", "cible": cible_fichier, "detail": None}
            else:
                any_failure = True
                file_result["mesure"] = {
                    "statut": "echec_analyse",
                    "cible": cible_fichier,
                    "detail": decl.get("parse_error") or "échec de parsing HTML sans message",
                }
        except Exception as exc:
            file_result["read_error"] = str(exc)
            any_failure = True
            file_result["mesure"] = {
                "statut": "echec_lecture",
                "cible": cible_fichier,
                "detail": str(exc),
            }

        result["files_analyzed"].append(file_result)

    if any_success and not any_failure:
        result["status"] = "success"
    elif any_success and any_failure:
        result["status"] = "partial_success"
    else:
        result["status"] = "all_failed"

    return result


# ---------------------------------------------------------------------------
# Autotest : chaque cas couvre une écriture HTML différente ou un scénario
# d'échec. Un cas marqué "regression" est une situation que l'outil doit
# distinguer pour ne pas fabriquer un faux positif.
# ---------------------------------------------------------------------------

_AUTOTEST_CASES = [
    # --- Déclarations de suivi ---
    ("déclaration de suivi explicite",
     "<p>Nous avons mis en place un système de suivi de l'impact environnemental.</p>",
     lambda r: len(r["declarations"]["declarations_suivi"]) == 1 and
              r["declarations"]["declarations_suivi"][0]["phrase"].startswith("Nous avons"),
     False),

    ("mesure de consommation",
     "<div>Le système permet de connaître la mesure de la consommation de chaque page.</div>",
     lambda r: len(r["declarations"]["declarations_suivi"]) >= 1,
     False),

    ("phrase entière jamais coupée au milieu d'un mot",
     "<p>Réduire l'empreinte environnementale de notre site internet en diminuant la consommation d'énergie nécessaire à son fonctionnement.</p>",
     lambda r: (len(r["declarations"]["declarations_suivi"]) == 1 and
               r["declarations"]["declarations_suivi"][0]["phrase"].startswith("Réduire") and
               "empreinte environnementale" in r["declarations"]["declarations_suivi"][0]["phrase"] and
               not r["declarations"]["declarations_suivi"][0]["phrase"].startswith("ntale")),
     True),

    ("casse d'origine préservée",
     "<p>Nous avons fixé plusieurs Objectifs pour Réduire l'Empreinte Carbone.</p>",
     lambda r: (len(r["declarations"]["declarations_suivi"]) >= 1 and
               "Objectifs" in r["declarations"]["declarations_suivi"][0]["phrase"] and
               "Empreinte Carbone" in r["declarations"]["declarations_suivi"][0]["phrase"]),
     False),

    ("mot-clé dans un attribut ne compte pas",
     '<img alt="système de suivi" src="x.png"><p>Aucune déclaration réelle.</p>',
     lambda r: len(r["declarations"]["declarations_suivi"]) == 0,
     True),

    ("mot-clé dans un commentaire ne compte pas",
     '<!-- système de suivi --><p>Aucune déclaration réelle.</p>',
     lambda r: len(r["declarations"]["declarations_suivi"]) == 0,
     True),

    ("texte vide",
     "<html><body></body></html>",
     lambda r: len(r["declarations"]["declarations_suivi"]) == 0 and
              r["declarations"]["parse_success"],
     False),

    # --- Robustesse HTML ---
    ("HTML avec entités",
     "<p>Système de suivi de l&amp;apos;impact environnemental.</p>",
     lambda r: len(r["declarations"]["declarations_suivi"]) >= 1,
     False),

    ("HTML mal formé (balise non fermée)",
     "<p>système de suivi<div>suite",
     lambda r: r["declarations"]["parse_success"] or r["declarations"]["parse_error"] is not None,
     False),

    ("texte en majuscules",
     "<P>SYSTÈME DE SUIVI DE L'IMPACT ENVIRONNEMENTAL</P>",
     lambda r: len(r["declarations"]["declarations_suivi"]) >= 1,
     False),

    ("espaces multiples",
     "<p>système   de    suivi    de  l'impact</p>",
     lambda r: len(r["declarations"]["declarations_suivi"]) >= 1,
     False),

    # --- Déclarations de rétention/suppression/archivage (chantier 37) ---
    ("déclaration de rétention explicite",
     "<p>Nous avons fixé une durée de conservation des données limitée à 24 mois.</p>",
     lambda r: len(r["declarations"]["declarations_retention"]) == 1 and
              r["declarations"]["declarations_retention"][0]["phrase"].startswith("Nous avons"),
     False),

    ("droit à l'effacement",
     "<p>Vous disposez d'un droit à l'effacement de vos données à tout moment.</p>",
     lambda r: len(r["declarations"]["declarations_retention"]) >= 1,
     False),

    ("suivi et rétention distingués dans la même page",
     "<p>Nous avons mis en place un système de suivi de l'impact environnemental.</p>"
     "<p>Notre politique de suppression des données est appliquée chaque année.</p>",
     lambda r: len(r["declarations"]["declarations_suivi"]) == 1 and
              len(r["declarations"]["declarations_retention"]) == 1,
     False),

    ("aucune déclaration de rétention",
     "<p>Nous mesurons notre empreinte carbone chaque trimestre.</p>",
     lambda r: len(r["declarations"]["declarations_retention"]) == 0,
     False),

    ("mot-clé de rétention dans un attribut ne compte pas",
     '<img alt="durée de conservation" src="x.png"><p>Aucune déclaration réelle.</p>',
     lambda r: len(r["declarations"]["declarations_retention"]) == 0,
     True),
]


def autotest():
    """Rejoue les cas de test embarqués."""
    echecs = []
    corriges = 0

    for libelle, html, check, regression in _AUTOTEST_CASES:
        try:
            result = {
                "filename": "test.html",
                "read_success": True,
                "read_error": None,
                "declarations": extract_declarations(html),
            }

            if not check(result):
                echecs.append((libelle, "Assertion échouée", result))
            elif regression:
                corriges += 1
        except Exception as exc:
            echecs.append((libelle, f"Exception : {exc}", None))

    total = len(_AUTOTEST_CASES)
    if echecs:
        print(f"AUTOTEST EN ÉCHEC : {len(echecs)} cas sur {total}")
        for libelle, erreur, result in echecs:
            print(f"  - {libelle}")
            print(f"      {erreur}")
            if result:
                print(f"      Résultat obtenu : {json.dumps(result['declarations'], ensure_ascii=False, indent=2)}")
        return 1

    print(f"Autotest : {total} cas passés, dont {corriges} situations que "
          f"l'outil doit distinguer (faux positifs évités).")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Extrait les déclarations publiques de suivi d'impact environnemental depuis pages-publiques/")
    parser.add_argument("source_dir", nargs="?",
                        help="dossier d'audit contenant pages-publiques/")
    parser.add_argument("--autotest", action="store_true",
                        help="rejoue les cas de test embarqués et sort 1 si un cas échoue")
    args = parser.parse_args()

    if args.autotest:
        sys.exit(autotest())
    if not args.source_dir:
        parser.error("source_dir est requis (ou utiliser --autotest)")

    source_dir = Path(args.source_dir).resolve()
    result = analyze_pages_publiques(source_dir)

    out_path = source_dir / "pages-publiques-criteria.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"pages-publiques-criteria.json écrit : {out_path}")
    print(f"Statut : {result['status']}")
    if result["status"] == "no_directory":
        print(f"  Le dossier pages-publiques/ n'existe pas dans {source_dir}")
    elif result["status"] == "no_files":
        print(f"  Aucun fichier trouvé parmi les motifs : {', '.join(result['files_searched'])}")
    elif result["files_analyzed"]:
        for fa in result["files_analyzed"]:
            if fa["read_success"] and fa["declarations"]["parse_success"]:
                n_suivi = len(fa["declarations"]["declarations_suivi"])
                print(f"  {fa['filename']} : {n_suivi} déclaration(s) de suivi d'impact détectée(s)")
            elif not fa["read_success"]:
                print(f"  {fa['filename']} : échec lecture ({fa['read_error']})")
            else:
                print(f"  {fa['filename']} : échec parsing ({fa['declarations']['parse_error']})")


if __name__ == "__main__":
    main()
