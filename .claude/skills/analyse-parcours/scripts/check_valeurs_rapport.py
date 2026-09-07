#!/usr/bin/env python3
"""
Garde-fou sur les VALEURS AFFICHÉES d'un rapport, pas sur les noms de clés.

POURQUOI CE SCRIPT EXISTE
-------------------------
Le projet contrôlait déjà les NOMS de ses données (`valider_coherence_cles.py`,
`valider_manifeste.py`, `valider_sortie_lot.py`). Aucun contrôle ne regardait ce
que le lecteur voit à l'écran. Conséquence vécue : deux dimensions du radar EOF
n'avaient reçu aucune réponse, Python a rendu son mot pour dire "pas de valeur",
et le rapport a affiché littéralement

    <text ... font-weight="bold">None%</text>

en bleu, en gras, au centre de l'image, dans un livrable destiné à un client. La
faute a traversé toute la chaîne de contrôle du projet : les clés étaient bonnes,
les badges étaient présents, seul le rendu était faux.

Ce script échoue si le texte VISIBLE du rapport contient :
  - une valeur interne de Python ou de JavaScript recopiée telle quelle
    (`None`, `NaN`, `null`, `undefined`, `True`, ...) ;
  - un emplacement de gabarit jamais substitué (`{today}`, `{{`, `%s`) ;
  - une trace de représentation interne ou de plantage
    (`<class '`, `object at 0x`, `Traceback`, `KeyError`, ...).

CE QU'IL NE FAIT PAS, ET IL FAUT LE DIRE
----------------------------------------
Il attrape la valeur ABSENTE ou NON SUBSTITUÉE, pas la valeur FAUSSE. Un
pourcentage calculé avec le mauvais dénominateur, une provenance promue à tort,
un chiffre pris sur le mauvais critère : tout cela passe ici sans broncher, parce
qu'un nombre plausible ressemble à un nombre juste. Le seul contrôle qui attrape
ça est le recalcul de l'arithmétique depuis les données, et la lecture de l'image
produite.

Il ne remplace pas non plus le fait de REGARDER le rapport. Il prouve l'absence
de quelques accidents connus, pas la lisibilité d'une page.

POURQUOI IL N'EST PAS BLOQUANT DANS LE GÉNÉRATEUR
-------------------------------------------------
Lancé seul, il rend le code de sortie 1 quand il trouve quelque chose, comme les
autres contrôles du projet, pour pouvoir entrer dans une batterie. Appelé depuis
`generate_report_html.py`, il ne fait qu'AVERTIR : le rapport reste produit et la
génération se termine normalement. Décision de l'utilisatrice, et elle se
défend : un axe sans réponse est un état légitime du référentiel aujourd'hui, il
se raréfiera à mesure que la couverture progresse.

Usage :
    python3 check_valeurs_rapport.py <rapport.html>        # un fichier
    python3 check_valeurs_rapport.py <dossier-audit>       # le rapport le plus récent
    python3 check_valeurs_rapport.py <radar.svg>           # un SVG seul
    python3 check_valeurs_rapport.py --list-motifs         # affiche les motifs surveillés
    python3 check_valeurs_rapport.py <cible> --audit-exemptions

Code de sortie : 0 si aucune fuite, 1 sinon.

EXEMPTION
---------
Une occurrence légitime s'exempte par un commentaire sur la MÊME ligne, avec sa
raison obligatoire :

    <!-- valeurs: ok - <raison> -->

Une exemption sans raison écrite est refusée et signalée. Le compte des lignes
exemptées s'affiche à chaque exécution, pour qu'une exemption reste un choix
visible et non un silence installé.
"""

import argparse
import html
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Les motifs surveillés
#
# Chaque entrée : (littéral, raison lisible).
# Tout est SENSIBLE À LA CASSE : `None` est une valeur Python, `none` est une
# valeur CSS parfaitement légitime (`border:none`, `fill="none"`). C'est cette
# distinction, plus le fait de ne regarder que le texte visible, qui évite le
# bruit.
# ---------------------------------------------------------------------------

VALEURS_INTERNES = [
    ("None", "valeur absente de Python affichée telle quelle"),
    ("NaN", "résultat d'un calcul impossible (JavaScript)"),
    ("nan", "résultat d'un calcul impossible (Python, flottant)"),
    ("Infinity", "division par zéro (JavaScript)"),
    ("inf", "division par zéro (Python, flottant)"),
    ("null", "valeur absente de JSON ou de JavaScript"),
    ("undefined", "variable JavaScript jamais affectée"),
    ("True", "booléen Python non traduit pour le lecteur"),
    ("False", "booléen Python non traduit pour le lecteur"),
]

# Ces traces commencent par `<`, donc le navigateur les prend pour une balise
# inconnue et ne les affiche PAS. Le lecteur ne voit rien du tout, ce qui est
# encore plus traître qu'un `None%` visible : il manque un morceau de la page et
# personne ne peut le deviner. Comme mon extracteur de texte visible retire les
# balises, il les mangerait exactement comme le navigateur. Elles sont donc
# cherchées dans le fichier BRUT, et elles seules.
TRACES_MASQUEES = [
    ("<class '", "type Python non échappé : avalé comme une balise, contenu manquant"),
    ("<built-in ", "fonction Python non échappée : avalée comme une balise"),
    ("<generator object", "générateur Python non échappé : avalé comme une balise"),
    ("<function ", "fonction Python non échappée : avalée comme une balise"),
]

TRACES_INTERNES = [
    ("dict_keys(", "vue de dictionnaire Python affichée telle quelle"),
    ("dict_values(", "vue de dictionnaire Python affichée telle quelle"),
    ("Traceback (most recent call last)", "trace de plantage Python"),
    ("KeyError", "clé manquante, plantage recopié dans le livrable"),
    ("TypeError", "erreur de type, plantage recopié dans le livrable"),
    ("ValueError", "erreur de valeur, plantage recopié dans le livrable"),
    ("AttributeError", "attribut manquant, plantage recopié dans le livrable"),
    ("IndexError", "indice hors bornes, plantage recopié dans le livrable"),
    ("ZeroDivisionError", "division par zéro, plantage recopié dans le livrable"),
]

# Ces traces ne s'écrivent pas comme des littéraux : leur fin est variable, et
# une frontière de mot posée après un préfixe hexadécimal ne trouverait jamais
# rien (`object at 0x` suivi de `10f3a2b80` : pas de frontière entre `x` et `1`).
# Le test négatif embarqué a attrapé exactement cette faute.
TRACES_REGEX = [
    (r"object at 0x[0-9a-fA-F]+", "adresse mémoire d'un objet Python"),
]

GABARITS = [
    (r"\{\{", "accolade Python échappée, gabarit jamais rendu"),
    (r"\}\}", "accolade Python échappée, gabarit jamais rendu"),
    (
        r"\{[A-Za-z_][A-Za-z0-9_.\[\]'\"]*\}",
        "emplacement de gabarit jamais substitué",
    ),
    (r"%[sdr]\b", "emplacement printf jamais substitué"),
]


def _compiler_litteral(litteral):
    """Échappe un littéral et l'encadre de frontières de mot là où c'est utile.

    Sans la frontière, `inf` attraperait `information` et le contrôle deviendrait
    inutilisable. Mais `<class '` ne commence pas par un caractère de mot, et lui
    coller un `\\b` ne trouverait plus jamais rien.
    """
    gabarit = re.escape(litteral)
    if litteral[:1].isalnum() or litteral[:1] == "_":
        gabarit = r"\b" + gabarit
    if litteral[-1:].isalnum() or litteral[-1:] == "_":
        gabarit = gabarit + r"\b"
    return re.compile(gabarit)


def motifs_texte_visible():
    """Les motifs cherchés dans le texte que le lecteur voit."""
    motifs = []
    for litteral, raison in VALEURS_INTERNES + TRACES_INTERNES + TRACES_MASQUEES:
        motifs.append((litteral, _compiler_litteral(litteral), raison))
    for gabarit, raison in TRACES_REGEX + GABARITS:
        motifs.append((gabarit, re.compile(gabarit), raison))
    return motifs


def motifs_fichier_brut():
    """Les motifs cherchés dans le fichier brut, parce qu'ils y sont invisibles.

    Une trace Python échappée (`&lt;class 'dict'&gt;`) est bien attrapée par le
    contrôle du texte visible. La même trace NON échappée passe pour une balise :
    le navigateur la cache, mon extracteur la retire, et le contrôle ne verrait
    rien. Elle ne se trouve donc que dans le brut.
    """
    return [
        (litteral, _compiler_litteral(litteral), raison)
        for litteral, raison in TRACES_MASQUEES
    ]


# ---------------------------------------------------------------------------
# Extraction du texte visible
#
# Le principe : ne JAMAIS chercher dans le fichier brut. Un rapport contient du
# CSS (`display:none`), du JavaScript et des attributs SVG (`fill="none"`) qui
# emploient légitimement des mots surveillés. Chercher dans le brut noierait la
# vraie fuite sous des dizaines de fausses.
#
# Les zones retirées sont remplacées par le MÊME nombre de retours à la ligne
# qu'elles contenaient, pour que les numéros de ligne restent ceux du fichier
# d'origine. Sans ça, tout numéro signalé serait faux.
# ---------------------------------------------------------------------------

_COMMENTAIRE_HTML = re.compile(r"<!--.*?-->", re.DOTALL)
_SCRIPT = re.compile(r"<script\b.*?</script\s*>", re.DOTALL | re.IGNORECASE)
_STYLE = re.compile(r"<style\b.*?</style\s*>", re.DOTALL | re.IGNORECASE)
_BALISE = re.compile(r"<[^>]*>", re.DOTALL)


def _remplacer_par_sauts(trouve):
    """Garde les retours à la ligne, jette le reste."""
    return "\n" * trouve.group(0).count("\n")


def _remplacer_balise(trouve):
    """Une balise devient une espace, pour ne pas coller deux mots voisins."""
    contenu = trouve.group(0)
    return "\n" * contenu.count("\n") + " "


def texte_visible(source):
    """Rend le texte que le lecteur voit, avec les numéros de ligne d'origine."""
    texte = _SCRIPT.sub(_remplacer_par_sauts, source)
    texte = _STYLE.sub(_remplacer_par_sauts, texte)
    texte = _COMMENTAIRE_HTML.sub(_remplacer_par_sauts, texte)
    texte = _BALISE.sub(_remplacer_balise, texte)
    return html.unescape(texte)


# ---------------------------------------------------------------------------
# Exemptions
# ---------------------------------------------------------------------------

_EXEMPTION = re.compile(r"<!--\s*valeurs:\s*ok\b\s*-?\s*(?P<raison>.*?)\s*-->")


def lire_exemptions(source):
    """Rend ({numéro de ligne: raison}, [(numéro de ligne, problème)]).

    L'exemption est cherchée dans le source ORIGINAL, commentaires compris,
    puisque l'extraction du texte visible les supprime justement.
    """
    exemptees = {}
    malformees = []
    for numero, ligne in enumerate(source.splitlines(), start=1):
        trouve = _EXEMPTION.search(ligne)
        if not trouve:
            continue
        raison = trouve.group("raison").strip()
        if not raison:
            malformees.append((numero, "exemption sans raison écrite"))
            continue
        exemptees[numero] = raison
    return exemptees, malformees


# ---------------------------------------------------------------------------
# Contrôle d'un fichier
# ---------------------------------------------------------------------------

LARGEUR_EXTRAIT = 90


def _extrait(ligne, debut, fin):
    """Un morceau de ligne centré sur la trouvaille, sur une seule ligne."""
    marge = max(0, (LARGEUR_EXTRAIT - (fin - debut)) // 2)
    gauche = max(0, debut - marge)
    droite = min(len(ligne), fin + marge)
    morceau = re.sub(r"\s+", " ", ligne[gauche:droite]).strip()
    if gauche > 0:
        morceau = "..." + morceau
    if droite < len(ligne):
        morceau = morceau + "..."
    return morceau


def _balayer(lignes, motifs, exemptees, deja_vu, fuites):
    """Cherche chaque motif dans chaque ligne, une seule fois par couple.

    Une seule fuite par motif et par ligne : le but est d'alerter, pas de
    compter. Une ligne qui en porte trois se corrige d'un seul geste.
    """
    for numero, ligne in enumerate(lignes, start=1):
        if numero in exemptees:
            continue
        for nom, expression, raison in motifs:
            if (numero, nom) in deja_vu:
                continue
            trouve = expression.search(ligne)
            if trouve:
                deja_vu.add((numero, nom))
                fuites.append(
                    (numero, nom, raison, _extrait(ligne, trouve.start(), trouve.end()))
                )


def controler(source):
    """Rend ([(numéro, motif, raison, extrait)], exemptées, malformées)."""
    exemptees, malformees = lire_exemptions(source)
    fuites = []
    deja_vu = set()
    _balayer(
        texte_visible(source).splitlines(),
        motifs_texte_visible(),
        exemptees,
        deja_vu,
        fuites,
    )
    _balayer(source.splitlines(), motifs_fichier_brut(), exemptees, deja_vu, fuites)
    fuites.sort(key=lambda fuite: (fuite[0], fuite[1]))
    return fuites, exemptees, malformees


# ---------------------------------------------------------------------------
# Résolution de la cible
# ---------------------------------------------------------------------------

MOTIFS_RAPPORT = ("rapport-*.html", "*.html")
EXTENSIONS = {".html", ".htm", ".xhtml", ".svg"}


def resoudre_cibles(chemin):
    """Rend la liste des fichiers à contrôler, ou lève ValueError.

    Un dossier donne le rapport le plus récent par ordre alphabétique, parce que
    les noms de rapport portent leur date en ISO et se trient donc
    chronologiquement.
    """
    chemin = Path(chemin)
    if chemin.is_file():
        return [chemin]
    if not chemin.is_dir():
        raise ValueError(f"cible introuvable : {chemin}")
    for motif in MOTIFS_RAPPORT:
        candidats = sorted(chemin.glob(motif))
        if candidats:
            return [candidats[-1]]
    raise ValueError(f"aucun rapport HTML dans {chemin}")


# ---------------------------------------------------------------------------
# Test négatif, embarqué dans le script
#
# Un garde-fou dont le test négatif ne casse pas ne vaut rien. Les cas vivent
# ici, et pas dans un fichier jetable de /tmp, pour qu'ils soient rejouables des
# mois plus tard par quelqu'un qui n'a pas assisté à leur écriture.
#
# Deux familles, aussi importantes l'une que l'autre :
#   - DOIT_ALERTER : les accidents connus. S'ils passent, le filet est troué.
#   - NE_DOIT_PAS_ALERTER : les usages légitimes. S'ils alertent, le contrôle
#     devient bruyant, on l'ignorera, et il ne servira plus à rien.
# ---------------------------------------------------------------------------

DOIT_ALERTER = [
    ("le None% du radar EOF", '<text font-weight="bold">None%</text>'),
    ("un None dans un tableau", "<td>Type d'instance</td><td>None</td>"),
    ("un nan de flottant Python", "<p>Émissions : nan gCO2e</p>"),
    ("un NaN de JavaScript", "<p>Total : NaN kg</p>"),
    ("un null de JSON", "<td>Pays du serveur</td><td>null</td>"),
    ("un undefined de JavaScript", "<span>undefined</span>"),
    ("un Infinity de JavaScript", "<td>Infinity</td>"),
    ("un inf de flottant Python", "<td>inf</td>"),
    ("un booléen Python non traduit", "<td>Consentement</td><td>True</td>"),
    ("un emplacement de gabarit resté nu", "<footer>Rapport généré le {today}</footer>"),
    ("une accolade Python échappée", "<p>Total {{ valeur }}</p>"),
    ("un emplacement printf resté nu", "<p>Domaine analysé : %s</p>"),
    ("une trace Python échappée", "<td>&lt;class 'dict'&gt;</td>"),
    ("une trace Python NON échappée", "<td><class 'dict'></td>"),
    ("un plantage recopié", "<pre>Traceback (most recent call last)</pre>"),
    ("une clé manquante recopiée", "<p>KeyError: 'provenance'</p>"),
    ("une adresse mémoire", "<td>&lt;Server object at 0x10f3a2b80&gt;</td>"),
]

NE_DOIT_PAS_ALERTER = [
    ("le none de CSS", "<style>.tuile{border:none;display:none}</style>"),
    ("le none des attributs SVG", '<path fill="none" stroke="none" d="M0 0"/>'),
    ("le null et le undefined de JavaScript", "<script>var x=null;if(y===undefined){}</script>"),
    ("un None dans un commentaire HTML", "<!-- ancien libellé : None -->"),
    ("du français qui contient les lettres", "<p>Informations infimes, aucune inférence</p>"),
    ("un pourcentage suivi d'un mot", "<p>12,5 % des critères, 90 % du total</p>"),
    ("le libellé de remplacement du radar", '<text fill="#999">N/A</text>'),
    ("une accolade seule dans du texte", "<p>La dimension {5} n'existe pas</p>"),
    (
        "un None exempté avec sa raison",
        "<td>None</td> <!-- valeurs: ok - valeur brute rendue par le fournisseur -->",
    ),
]


def autotest():
    """Rejoue les cas d'école. Rend 0 si le filet fait exactement son travail."""
    echecs = []

    for description, fragment in DOIT_ALERTER:
        fuites, _exemptees, _malformees = controler(fragment)
        if not fuites:
            echecs.append(f"NON DÉTECTÉ - {description} : {fragment}")

    for description, fragment in NE_DOIT_PAS_ALERTER:
        fuites, _exemptees, _malformees = controler(fragment)
        if fuites:
            motifs = ", ".join(sorted({fuite[1] for fuite in fuites}))
            echecs.append(f"FAUSSE ALERTE - {description} : motif(s) {motifs}")

    # Une exemption sans raison doit être refusée, sinon l'exemption devient un
    # interrupteur silencieux qu'on posera partout.
    _fuites, _exemptees, malformees = controler("<td>None</td> <!-- valeurs: ok -->")
    if not malformees:
        echecs.append("NON DÉTECTÉ - une exemption sans raison écrite est acceptée")

    # Le numéro de ligne signalé doit être celui du FICHIER, pas celui du texte
    # extrait. C'est ce qui casse en premier si l'extraction change.
    source = "<style>\n.a{color:red}\n</style>\n<p>x</p>\n<td>None</td>\n"
    fuites, _exemptees, _malformees = controler(source)
    if not fuites or fuites[0][0] != 5:
        obtenu = fuites[0][0] if fuites else "aucune fuite"
        echecs.append(f"NUMÉRO DE LIGNE FAUX - attendu 5, obtenu {obtenu}")

    total = len(DOIT_ALERTER) + len(NE_DOIT_PAS_ALERTER) + 2
    if echecs:
        print(f"[ÉCHEC] {len(echecs)} cas sur {total} :")
        for echec in echecs:
            print(f"    {echec}")
        print()
        print("Le garde-fou ne fait pas ce qu'il annonce. Ne pas le commiter en l'état.")
        return 1

    print(f"[SUCCÈS] {total} cas passés :")
    print(f"    {len(DOIT_ALERTER)} accident(s) connu(s) bien détecté(s)")
    print(f"    {len(NE_DOIT_PAS_ALERTER)} usage(s) légitime(s) bien ignoré(s)")
    print("    l'exemption sans raison est refusée")
    print("    le numéro de ligne signalé est celui du fichier")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    analyseur = argparse.ArgumentParser(
        description="Contrôle les valeurs affichées d'un rapport déjà produit.",
    )
    analyseur.add_argument(
        "cible",
        nargs="?",
        help="un rapport HTML, un SVG, ou un dossier d'audit (rapport le plus récent)",
    )
    analyseur.add_argument(
        "--list-motifs",
        action="store_true",
        help="affiche les motifs surveillés et sort",
    )
    analyseur.add_argument(
        "--audit-exemptions",
        action="store_true",
        help="liste les exemptions en vigueur au lieu de contrôler",
    )
    analyseur.add_argument(
        "--autotest",
        action="store_true",
        help="rejoue les cas d'école du garde-fou et sort",
    )
    args = analyseur.parse_args(argv)

    if args.autotest:
        return autotest()

    if args.list_motifs:
        visibles = motifs_texte_visible()
        bruts = motifs_fichier_brut()
        print(f"{len(visibles)} motif(s) dans le TEXTE VISIBLE, sensibles à la casse :")
        for nom, _expression, raison in visibles:
            print(f"    {nom:38s} {raison}")
        print()
        print("Les blocs <script> et <style>, les commentaires et les attributs de")
        print("balise sont retirés avant la recherche. C'est ce qui permet de garder")
        print("`None` sans être noyé par les `fill=\"none\"` du SVG et les")
        print("`border:none` du CSS.")
        print()
        print(f"{len(bruts)} motif(s) dans le FICHIER BRUT, parce qu'une trace non")
        print("échappée passe pour une balise et disparait de l'écran :")
        for nom, _expression, raison in bruts:
            print(f"    {nom:38s} {raison}")
        return 0

    if not args.cible:
        analyseur.print_usage()
        print("[erreur] indiquer un rapport, un SVG ou un dossier d'audit.")
        return 1

    try:
        cibles = resoudre_cibles(args.cible)
    except ValueError as erreur:
        print(f"[erreur] {erreur}")
        return 1

    total_fuites = 0
    total_exempt = 0
    total_malformees = 0

    for cible in cibles:
        if cible.suffix.lower() not in EXTENSIONS:
            print(f"[info] {cible.name} ignoré : extension non prise en charge.")
            continue
        source = cible.read_text(encoding="utf-8", errors="replace")
        fuites, exemptees, malformees = controler(source)
        total_exempt += len(exemptees)
        total_malformees += len(malformees)

        if args.audit_exemptions:
            if exemptees:
                print(f"{cible.name} - {len(exemptees)} ligne(s) exemptée(s) :")
                for numero, raison in sorted(exemptees.items()):
                    print(f"    {cible.name}:{numero}  {raison}")
            continue

        for numero, probleme in malformees:
            print(f"[ÉCHEC] {cible.name}:{numero}  {probleme}")

        suffixe = f"  ({len(exemptees)} ligne(s) exemptée(s))" if exemptees else ""
        if not fuites:
            print(f"[OK] {cible.name}{suffixe}")
            continue
        total_fuites += len(fuites)
        print(f"[ÉCHEC] {cible.name} - {len(fuites)} fuite(s){suffixe} :")
        for numero, nom, raison, extrait in fuites:
            print(f"    {cible.name}:{numero}  {nom} - {raison}")
            print(f"        {extrait}")
        print()

    if args.audit_exemptions:
        print()
        print(f"{total_exempt} ligne(s) exemptée(s) au total.")
        print("Chacune est un endroit où le contrôle ne voit rien. Vérifier que la")
        print("raison tient toujours.")
        return 0

    print()
    if total_fuites or total_malformees:
        if total_fuites:
            print(f"[ÉCHEC] {total_fuites} fuite(s) de valeur dans le texte visible.")
            print("Le lecteur du rapport voit ces caractères à l'écran. Trois issues,")
            print("dans cet ordre de préférence :")
            print("  1. traiter le cas d'absence à la source, avec un libellé lisible")
            print("     (le radar affiche \"N/A\" au lieu d'interpoler un faux 0 %) ;")
            print("  2. corriger le gabarit si l'emplacement n'a jamais été substitué ;")
            print("  3. si l'occurrence est légitime, l'exempter avec sa raison :")
            print("     <!-- valeurs: ok - <raison> -->")
        if total_malformees:
            print(f"[ÉCHEC] {total_malformees} exemption(s) sans raison écrite.")
            print("Une exemption sans raison redevient un silence dans six mois.")
        return 1

    print("[SUCCÈS] Aucune valeur interne dans le texte visible du rapport.")
    if total_exempt:
        print(f"({total_exempt} ligne(s) exemptée(s) - les relire avec --audit-exemptions.)")
    print("Rappel : ce contrôle attrape la valeur ABSENTE ou NON SUBSTITUÉE, PAS la")
    print("valeur FAUSSE. Un chiffre plausible mais calculé de travers passe ici sans")
    print("broncher. Regarder l'image produite reste obligatoire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
