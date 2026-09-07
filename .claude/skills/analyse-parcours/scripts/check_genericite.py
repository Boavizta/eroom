#!/usr/bin/env python3
"""
Filet de sécurité du refactoring e-footprint : contrôle de GÉNÉRICITÉ.

POURQUOI CE SCRIPT EXISTE
-------------------------
La bibliothèque de modélisation doit fonctionner sur N'IMPORTE QUEL site, pas
seulement sur le cas de test. Le risque n'est pas théorique : en déplaçant du
code, il est facile de figer dans la bibliothèque une valeur qui avait été
MESURÉE sur un site précis. Ce type de faute est invisible à la relecture, parce
qu'un nombre nu ressemble à une constante physique.

Ce script échoue si la bibliothèque contient :
  - un nom de domaine ou une adresse IP littérale
  - une valeur numérique mesurée sur un cas d'audit (la faute la plus sournoise :
    elle passe tous les greps de nom)
  - un chemin de fichier propre à un cas d'audit

CE QU'IL NE FAIT PAS, ET IL FAUT LE DIRE
----------------------------------------
Il attrape le COPIER-COLLER, pas le BIAIS DE CONCEPTION. Une fonction qui
suppose implicitement un site à deux serveurs, ou qui suppose du HTML servi
complet, passera ce contrôle sans broncher. Le seul contrôle qui prouve la
généricité est l'exécution sur un second site réel.

Il est volontairement lancé TÔT, dès le lot 0, pour échouer au premier
copier-coller et non trois lots plus tard.

Usage :
    python3 check_genericite.py                      # cible par défaut
    python3 check_genericite.py <répertoire>         # cible explicite
    python3 check_genericite.py --list-values        # affiche les valeurs interdites

Code de sortie : 0 si la cible est générique, 1 sinon.

CE QUI EST EXCLU DE L'ANALYSE, et pourquoi :
  - les docstrings et les commentaires : un exemple documenté est légitime et
    même utile ("ex. audits/octo.com"). Seul le CODE EXÉCUTABLE est contrôlé.
  - `check_efootprint_contract.py` et `tmp/` : les valeurs du cas de test y sont
    à leur place, c'est leur raison d'être.

EXEMPTIONS EXPLICITES
---------------------
Certaines occurrences sont légitimes : une table de trackers connus, la
déclaration d'une constante de chemin, un bloc de démonstration. Elles
s'exemptent par un marqueur qui DOIT porter sa raison :

    RAW_DATA_DIR = "..."          # genericite: ok - declaration de la constante

    TRACKER_DOMAINS = {           # genericite: ok-debut - table explicite de tiers
        "google-analytics.com",
    }                             # genericite: ok-fin

Une exemption sans raison est refusée : désactiver le filet doit coûter une
phrase, sinon il se vide de sens ligne par ligne. `--audit-exemptions` les liste
toutes, pour qu'elles restent relisables.
"""

import argparse
import ast
import io
import re
import sys
import tokenize
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = Path(__file__).resolve().parent

# Cible par défaut : la bibliothèque de modélisation, quand elle existera (lot 1).
DEFAULT_TARGET = SCRIPTS_DIR / "efootprint_model"

# ---------------------------------------------------------------------------
# Valeurs mesurées sur les cas d'audit : INTERDITES dans la bibliothèque
# ---------------------------------------------------------------------------
# Chaque valeur porte son origine. Sans cette trace, personne ne saurait dans six
# mois pourquoi tel nombre est proscrit, et la liste deviendrait du folklore.
#
# Toute nouvelle mesure publiée dans un rapport doit être AJOUTÉE ici.

FORBIDDEN_VALUES = {
    # Comptages de mots des pages du cas de test (mesurés dans le HAR)
    317.0: "comptage de mots, cas de test",
    356.0: "comptage de mots, cas de test",
    153.0: "comptage de mots, cas de test",
    1096.0: "comptage de mots, cas de test",
    591.0: "comptage de mots, cas de test",
    # Données d'audience SimilarWeb du cas de test
    2.116: "audience SimilarWeb, cas de test",
    33.979: "audience SimilarWeb, cas de test",
    0.460: "audience SimilarWeb, cas de test",
    36654.0: "audience SimilarWeb, cas de test",
    16.1: "durée de visite SimilarWeb, cas de test",
    # Totaux CO2e et facteurs dérivés du cas de test
    174.139: "total CO2e (lecture propre), cas de test",
    174.076: "total CO2e (publié, lu par regex), cas de test",
    146.16: "total CO2e en serverless, cas de test",
    235.47: "total CO2e, variante mesurée sur le cas de test",
    203.45: "total CO2e à 2 serveurs, cas de test",
    203.454: "total CO2e à 2 serveurs, cas de test",
    176.805: "total CO2e, 2e serveur sans stockage, cas de test",
    0.41: "facteur de recalage Nielsen, calculé sur UN SEUL site",
    38.9: "valeur mesurée sur le cas de test, origine précise non tracée",
    82.0: "valeur mesurée sur le cas de test, origine précise non tracée",
    440.0: "visites annuelles (milliers), cas de test",
    # Bornes des fourchettes publiées (mesurées sur le cas de test)
    145.1: "borne basse fourchette infrastructure, cas de test",
    271.4: "borne haute du cumul rejeté, cas de test",
    45.9: "borne basse du cumul rejeté, cas de test",
    242.1: "borne haute fourchette usage, cas de test",
    74.9: "borne basse fourchette usage, cas de test",
    26.6: "CO2e de fabrication d'un Storage de 1 To, cas de test",
    # Empreinte CO2e par requête testée pour les hôtes tiers (aucune source publique)
    306.139: "total CO2e avec hôtes tiers à 0,2 g/requête, cas de test",
    187.339: "total CO2e avec hôtes tiers à 0,02 g/requête, cas de test",
    # Rejeu complet du 06/08/2026 : recollecte CrUX/SimilarWeb, mix appareils
    # déplacé. Ces totaux remplacent 174.076 dans les rapports livrés.
    170.856: "total CO2e après rejeu, cas de test",
    # Lot 2 (07/08/2026) : build_system() + extraction propre (sans regex) sur
    # l'env-data.json rejoué. Remplace 174.139 comme repère de non-régression.
    170.904: "total CO2e (lecture propre, Lot 2), cas de test",
    # Lot 3 (07/08/2026) : from_har.py, parcours multi-étapes + infras multiples.
    # Validation confirmée : le HAR = parcours d'une personne, donc chaque page
    # capturée devient une étape (au lieu de la seule page la plus lourde).
    853.336: "total CO2e (multi-étapes, Lot 3), cas de test octo.com",
    14480.895: "total CO2e (3 serveurs + 3 étapes, Lot 3), cas de test ANTS",
    4801.2: "total CO2e du second cas de test (site public)",
    # Code mort après correction du typage des URL versionnées
    975.5: "CSS non utilisé (Ko), cas de test",
    161.9: "CSS non utilisé d'une page (Ko), cas de test",
    926.6: "CSS non utilisé (Ko), second cas de test",
    4270.6: "CSS non utilisé (Ko), second cas de test",
    10146.6: "JS non utilisé (Ko), second cas de test",
    # Agrégats Coverage recalculés par coverage_metrics.py, qui classe l'extension
    # sur le CHEMIN de l'URL. La page dont toutes les URLs sont versionnées était
    # publiée à zéro : ces totaux remplacent 17657.4 / 9736.3 / 3491.5 / 3024.2.
    18226.6: "JS total (Ko), second cas de test",
    10146.4: "JS non utilisé (Ko), second cas de test, calcul déterministe",
    4840.4: "CSS total (Ko), second cas de test",
    4270.7: "CSS non utilisé (Ko), second cas de test, calcul déterministe",
    1349.1: "CSS total de la page servie en DSFR (Ko), second cas de test",
    1246.4: "CSS non utilisé de la page servie en DSFR (Ko), second cas de test",
    # Agrégats HAR des deux cas de test
    6987.9: "poids total HAR (Ko), cas de test",
    17674.3: "poids total HAR (Ko), second cas de test",
    # Lot 4 (07/08/2026) : temps_utilisateur.py, Nielsen recalé sur Engagments
    # SimilarWeb (moyenne des Nielsen bruts du parcours, cf. sa docstring).
    16.058: "temps moyen par page SimilarWeb (TimeOnSite/PagePerVisit), cas de test",
    0.250109: "facteur de recalage Nielsen (méthode parcours multi-étapes), cas de test",
    560.9885: "total CO2e (Nielsen recalé, Lot 4), cas de test octo.com",
    14372.7561: "total CO2e (Nielsen brut, pas de recalage SimilarWeb, Lot 4), cas de test ANTS",
    # Lot 4bis (07/08/2026) : ranges.py, fourchettes infra/usage mesurées sur
    # les deux cas d'audit (cf. tmp/lot2/_verif_lot4bis_fourchettes.py).
    533.0142: "borne basse fourchette infra (serverless), Lot 4bis, cas de test octo.com",
    881.3057: "borne haute fourchette usage (Nielsen brut), Lot 4bis, cas de test octo.com",
    14036.2206: "borne basse fourchette infra (serverless), Lot 4bis, cas de test ANTS",
    # Lot 10 (11/08/2026) : correction du bug de pairing mots<->page (from_har.py) :
    # le comptage de mots existait déjà dans le HAR sur une AUTRE répétition de
    # la même URL que celle retenue pour le poids réseau, jamais lu jusque-là.
    # Remplace 560.9885 comme repère de non-régression pour octo.com.
    268.6406: "total CO2e après correction du pairing mots/page (Lot 10), cas de test octo.com",
}

# Un entier court (82, 440, 317) est un nombre COURANT : il peut légitimement
# désigner un comptage, une taille, un code de statut. Mesuré sur le code
# existant, `82` est ainsi apparu dans un bloc de validation EcoIndex parfaitement
# légitime de `har_metrics.py`. Signaler ces valeurs reste utile, mais les
# annoncer avec la même assurance qu'un `174.139` serait mentir sur la précision
# du contrôle. Elles sont donc marquées "à vérifier" dans le rapport.
#
# Un flottant à plusieurs décimales, lui, ne se retrouve pas par hasard.
COLLISION_PRONE_MAX = 1000.0


def collision_prone(value):
    """La valeur est-elle un nombre courant, susceptible d'apparaître à bon droit ?"""
    return value.is_integer() and abs(value) < COLLISION_PRONE_MAX

# Valeurs autorisées malgré leur présence possible dans les listes ci-dessus :
# ce sont des constantes de conversion ou des grandeurs universelles.
ALLOWED_VALUES = {
    0.0, 1.0, 2.0, 3.0, 100.0, 1000.0,
    8760.0,     # heures dans une année
    24.0, 60.0, 365.0,
    1024.0,
}

# Tolérance de comparaison : un 174.0761 recopié à la main doit être attrapé.
VALUE_TOLERANCE = 1e-4

# ---------------------------------------------------------------------------
# Motifs textuels interdits dans le code exécutable
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    (
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "adresse IP littérale",
    ),
    (
        # Nom de domaine. Les extensions listées sont celles susceptibles
        # d'apparaître dans un cas d'audit ; la liste est volontairement courte
        # pour éviter d'attraper des noms de modules Python (`os.path`).
        re.compile(
            r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*"
            r"\.(?:com|fr|org|net|io|gouv\.fr|tools|ai|dev|co)\b"
        ),
        "nom de domaine littéral",
    ),
    (
        re.compile(r"\baudits?/[A-Za-z0-9._-]+"),
        "chemin vers un cas d'audit",
    ),
    (
        re.compile(r"donnees-brutes-potentiellement-sensibles"),
        "chemin de captures brutes en dur (utiliser la constante RAW_DATA_DIR)",
    ),
]


# ---------------------------------------------------------------------------
# Exemptions explicites
# ---------------------------------------------------------------------------
# Le marqueur est cherché dans le source ORIGINAL (commentaires inclus), alors que
# les violations sont cherchées dans le code seul. Les deux passes partagent la
# numérotation des lignes, ce qui rend la correspondance directe.

EXEMPT_LINE = re.compile(r"#\s*genericite:\s*ok\b\s*-?\s*(?P<raison>.*)$")
EXEMPT_START = re.compile(r"#\s*genericite:\s*ok-debut\b\s*-?\s*(?P<raison>.*)$")
EXEMPT_END = re.compile(r"#\s*genericite:\s*ok-fin\b")


def parse_exemptions(source):
    """Rend ({ligne_exemptée: raison}, [(ligne, problème)]).

    Le second élément liste les exemptions MAL FORMÉES : marqueur sans raison, ou
    bloc ouvert jamais refermé. Ce sont des erreurs, pas des avertissements : une
    exemption silencieuse est exactement ce que ce script cherche à empêcher.
    """
    exempt = {}
    malformed = []
    block_start = None
    block_reason = None

    for lineno, line in enumerate(source.splitlines(), start=1):
        if EXEMPT_END.search(line):
            if block_start is None:
                malformed.append((lineno, "marqueur ok-fin sans ok-debut"))
            else:
                for row in range(block_start, lineno + 1):
                    exempt[row] = block_reason
                block_start = None
                block_reason = None
            continue

        match_start = EXEMPT_START.search(line)
        if match_start:
            reason = match_start.group("raison").strip()
            if not reason:
                malformed.append((lineno, "exemption de bloc sans raison écrite"))
                continue
            if block_start is not None:
                malformed.append((lineno, "ok-debut imbriqué dans un bloc déjà ouvert"))
                continue
            block_start = lineno
            block_reason = reason
            continue

        # ok-debut correspond aussi à EXEMPT_LINE ; l'ordre des tests l'exclut déjà.
        match_line = EXEMPT_LINE.search(line)
        if match_line:
            reason = match_line.group("raison").strip()
            if not reason:
                malformed.append((lineno, "exemption de ligne sans raison écrite"))
            else:
                exempt[lineno] = reason

    if block_start is not None:
        malformed.append((block_start, "bloc ok-debut jamais refermé par ok-fin"))

    return exempt, malformed


# ---------------------------------------------------------------------------
# Extraction du code exécutable seul
# ---------------------------------------------------------------------------

def strip_comments_and_docstrings(source):
    """Retourne le source privé de ses commentaires et de ses docstrings.

    Deux passes, parce qu'aucune ne suffit seule :
      - `tokenize` retire les commentaires (`ast` ne les voit pas du tout).
      - `ast` identifie les docstrings (`tokenize` ne distingue pas une docstring
        d'une chaîne de caractères ordinaire).

    Les lignes retirées sont remplacées par des lignes vides plutôt que
    supprimées, pour que les numéros de ligne signalés restent EXACTS et
    cliquables.

    SUBTILITÉ QUI A COÛTÉ UN TROU DANS LE FILET (corrigée au lot 1) : une classe
    ou une fonction dont le corps est UNIQUEMENT une docstring se retrouve avec
    un corps vide après nettoyage, ce qui rend le résultat syntaxiquement
    invalide. `numeric_literals()` renvoyait alors une liste vide et TOUT le
    contrôle des valeurs mesurées du fichier était désactivé, sans le moindre
    message. La docstring est donc remplacée par un `pass` correctement indenté,
    et `numeric_literals()` signale désormais son échec au lieu de se taire.
    """
    lines = source.splitlines()

    # Passe 1 : neutraliser les commentaires.
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.COMMENT:
                row, col = token.start
                lines[row - 1] = lines[row - 1][:col]
    except (tokenize.TokenError, IndentationError):
        # Source non tokenisable : on continue sans cette passe plutôt que
        # d'abandonner le fichier. Le contrôle reste utile, juste moins précis.
        pass

    # Passe 2 : neutraliser les docstrings.
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "\n".join(lines)

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if not (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        for row in range(first.lineno, (first.end_lineno or first.lineno) + 1):
            lines[row - 1] = ""
        # Si la docstring était tout le corps, il faut le remplacer par un
        # `pass` à la bonne indentation, sinon le fichier nettoyé ne se parse
        # plus et le contrôle des valeurs se désactive en silence.
        if len(body) == 1 and not isinstance(node, ast.Module):
            indent = " " * first.col_offset
            lines[first.lineno - 1] = f"{indent}pass"

    return "\n".join(lines)


def numeric_literals(source):
    """Rend les littéraux numériques du code, en (ligne, valeur).

    Passe par l'arbre syntaxique : un nombre écrit dans une chaîne de caractères
    n'est pas un littéral numérique et ne doit pas déclencher d'alerte.

    Lève SyntaxError si le source nettoyé ne se parse pas. C'était auparavant
    un `return []` silencieux, donc un contrôle qui s'annulait tout seul en
    restant vert. Un filet qui se désactive sans le dire est pire qu'un filet
    absent : on croit être protégé.
    """
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if isinstance(node.value, bool):
                continue
            found.append((node.lineno, float(node.value)))
    return found


# ---------------------------------------------------------------------------
# Contrôles
# ---------------------------------------------------------------------------

def check_file(path):
    """Analyse un fichier. Retourne (violations, exemptions_utilisées).

    violations : liste de (ligne, motif)
    exemptions_utilisées : liste de (ligne, raison)
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return [(0, f"fichier illisible ({exc})")], []

    exempt, malformed = parse_exemptions(source)
    code = strip_comments_and_docstrings(source)

    violations = [(lineno, f"exemption invalide : {problem}")
                  for lineno, problem in malformed]

    # Un source non analysable est signalé comme une VIOLATION, pas ignoré :
    # sans analyse syntaxique, le contrôle des valeurs mesurées ne tourne pas du
    # tout, et le fichier serait déclaré conforme sans avoir été examiné.
    try:
        literals = numeric_literals(code)
    except SyntaxError as exc:
        return sorted(violations + [(
            exc.lineno or 0,
            "code non analysable après retrait des commentaires et docstrings "
            f"({exc.msg}). Le contrôle des valeurs mesurées n'a PAS pu tourner "
            "sur ce fichier : le déclarer conforme serait faux."
        )]), sorted((lineno, reason) for lineno, reason in exempt.items())

    for lineno, value in literals:
        if value in ALLOWED_VALUES or lineno in exempt:
            continue
        for forbidden, origin in FORBIDDEN_VALUES.items():
            if abs(value - forbidden) <= VALUE_TOLERANCE:
                prefix = ("valeur À VÉRIFIER (nombre courant, peut être un faux positif)"
                          if collision_prone(value) else "valeur mesurée en dur")
                violations.append((lineno, f"{prefix} : {value} ({origin})"))
                break

    for lineno, line in enumerate(code.splitlines(), start=1):
        if lineno in exempt:
            continue
        for pattern, label in FORBIDDEN_PATTERNS:
            match = pattern.search(line)
            if match:
                violations.append((lineno, f"{label} : {match.group(0)}"))

    used = sorted((lineno, reason) for lineno, reason in exempt.items())
    return sorted(violations), used


def main():
    parser = argparse.ArgumentParser(
        description="Contrôle de généricité : la bibliothèque ne doit contenir "
                    "aucune trace d'un cas d'audit particulier.",
    )
    parser.add_argument("target", type=Path, nargs="?", default=DEFAULT_TARGET,
                        help=f"Répertoire ou fichier à contrôler "
                             f"(défaut : {DEFAULT_TARGET.name}/).")
    parser.add_argument("--list-values", action="store_true",
                        help="Affiche les valeurs interdites et leur origine, puis s'arrête.")
    parser.add_argument("--audit-exemptions", action="store_true",
                        help="Liste les exemptions en vigueur avec leur raison. "
                             "À relire périodiquement : une exemption oubliée est "
                             "un trou dans le filet.")
    args = parser.parse_args()

    if args.list_values:
        print(f"{len(FORBIDDEN_VALUES)} valeurs interdites dans la bibliothèque :")
        for value, origin in sorted(FORBIDDEN_VALUES.items()):
            print(f"    {value:>12}  {origin}")
        print()
        print("Légitimes en revanche dans check_efootprint_contract.py et dans tmp/.")
        return 0

    target = args.target
    if not target.exists():
        # Cas normal avant le lot 1 : la bibliothèque n'existe pas encore. Ce
        # n'est pas un échec, et le dire clairement évite de croire à une panne.
        print(f"[info] Cible absente : {target}")
        print("[info] Rien à contrôler. Normal tant que la bibliothèque n'existe pas.")
        return 0

    files = sorted(target.rglob("*.py")) if target.is_dir() else [target]
    files = [f for f in files if "__pycache__" not in f.parts]

    if not files:
        print(f"[info] Aucun fichier Python sous {target}. Rien à contrôler.")
        return 0

    print("-" * 68)
    print(f"  GÉNÉRICITÉ — {target}")
    print(f"  {len(files)} fichier(s), {len(FORBIDDEN_VALUES)} valeurs interdites")
    print("-" * 68)
    print()

    total = 0
    total_exempt = 0
    for path in files:
        violations, exemptions = check_file(path)
        try:
            shown = path.relative_to(PROJECT_ROOT)
        except ValueError:
            shown = path

        total_exempt += len(exemptions)
        if args.audit_exemptions:
            if exemptions:
                print(f"{shown} — {len(exemptions)} ligne(s) exemptée(s) :")
                for lineno, reason in exemptions:
                    print(f"    {shown}:{lineno}  {reason}")
            continue

        suffix = f"  ({len(exemptions)} ligne(s) exemptée(s))" if exemptions else ""
        if not violations:
            print(f"[OK] {shown}{suffix}")
            continue
        total += len(violations)
        print(f"[ÉCHEC] {shown} — {len(violations)} violation(s){suffix} :")
        for lineno, reason in violations:
            print(f"    {shown}:{lineno}  {reason}")
        print()

    if args.audit_exemptions:
        print()
        print(f"{total_exempt} ligne(s) exemptée(s) au total.")
        print("Chacune est un endroit où le contrôle ne voit rien. Vérifier que la")
        print("raison tient toujours.")
        return 0

    print()
    if total:
        print(f"[ÉCHEC] {total} violation(s). La cible n'est pas générique.")
        print("Ces valeurs et ces noms doivent venir des DONNÉES du site analysé,")
        print("pas du code. Trois issues, dans cet ordre de préférence :")
        print("  1. faire venir la valeur des données du site (le bon réflexe) ;")
        print("  2. si elle est vraiment universelle, l'ajouter à ALLOWED_VALUES ;")
        print("  3. si l'occurrence est légitime, l'exempter avec sa raison :")
        print("     # genericite: ok - <raison>")
        return 1

    print("[SUCCÈS] Aucune trace d'un cas d'audit particulier.")
    if total_exempt:
        print(f"({total_exempt} ligne(s) exemptée(s) — les relire avec --audit-exemptions.)")
    print("Rappel : ce contrôle attrape le copier-coller, PAS le biais de")
    print("conception. Seule l'exécution sur un second site réel le prouve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
