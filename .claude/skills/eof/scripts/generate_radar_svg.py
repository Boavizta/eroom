#!/usr/bin/env python3
"""Génère un radar SVG (grille circulaire) pour la synthèse du référentiel EOF.

Usage :
    python3 generate_radar_svg.py sortie.svg
        -> génère un radar de démonstration à deux couches avec des valeurs
           fictives (les 6 axes du référentiel EOF, un axe sans réponse,
           une couche déclarée non vide) pour voir le rendu complet

    from generate_radar_svg import build_radar_from_results
    svg_text = build_radar_from_results(audit_results, "octo.com")

DEUX COUCHES, ET POURQUOI ELLES EXISTENT
----------------------------------------
Un axe à 0 % parce que tout a été regardé et que tout va bien, et un axe à 0 %
parce qu'un critère sur six a été regardé, ne doivent pas se ressembler. Mesuré
sur un audit réel : la dimension 4 est passée de "vide" à 0 % le jour où UN
critère sur six a reçu une réponse, et une bonne. Le radar affichait alors un axe
exemplaire là où personne n'avait presque rien regardé.

Trois éléments répondent à ça, et aucun n'invente de chiffre :

  - la couche PLEINE : la part du potentiel affiché que nous avons établie
    nous-mêmes (provenances de PROVENANCES_ETABLI) ;
  - la couche HACHURÉE : ce que les réponses du service audité y ont ajouté
    (provenances de PROVENANCES_DECLARE). La couche hachurée contient toujours la
    pleine, puisqu'elle ajoute des termes positifs ;
  - sous chaque axe, le nombre de critères renseignés sur son total ; et sous le
    radar, une jauge de ce qui est renseigné à l'échelle du référentiel.

Un critère sans réponse ne reçoit AUCUNE valeur par défaut, ni la meilleure ni la
pire : la jauge dit ce qui manque au lieu de le combler.

Toutes les coordonnées sont calculées par trigonométrie (math.cos/sin), jamais
estimées à l'œil. Tout le texte est échappé XML (xml.sax.saxutils.escape) :
un "&" non échappé dans un libellé (ex. "Stockage & Données") casse le
parsing XML et peut faire disparaître silencieusement tout ce qui suit dans
certains navigateurs.
"""
import math
import sys
from xml.sax.saxutils import escape

NAVY = "#2D4675"  # contraste ~9,35:1 sur fond blanc (RGAA/WCAG AAA)
GREY = "#5F5F5F"  # contraste ~6,7:1 sur fond blanc : couleur de l'absence de réponse,
                  # visiblement éteinte par rapport au NAVY sans descendre sous le seuil AA
SCALE = 100  # axe en pourcentage (0-100%), comme le radar du Google Sheet source

# Identifiant du motif de hachures. Distinctif à dessein : le SVG est INLINÉ dans
# le rapport HTML, au milieu d'autres SVG. Un id générique ("hachure") serait
# capturé par le premier motif du document portant le même nom, et la couche
# déclarée se remplirait avec les hachures d'un diagramme voisin.
HACHURE_ID = "eof-radar-couche-declaree"

AXES_EOF = [
    "🛖 Produit",
    "🗺️ Architecture",
    "🏢 Infrastructure",
    "💾 Stockage & Données",
    "👨‍💻 Algo & Code",
    "🛠 Facilité de changement",
]

# Répartition des provenances entre les deux couches.
#
# La couche hachurée est celle du manifeste (`declare`, `precise`) : ce que le
# service audité a répondu lui-même. Les trois autres provenances vont dans la
# couche pleine parce qu'elles viennent toutes de NOUS : `collecte` est une
# mesure, `estime` une déduction depuis un ordre de grandeur, `suppose` une
# déduction depuis un indice faible. Les mêler au déclaratif ferait lire
# "le client l'a dit" là où c'est nous qui l'avons avancé.
#
# `suppose` n'existait pas quand le manifeste a été écrit : sans cette liste
# explicite, une réponse posée en `suppose` disparaîtrait des deux couches et le
# polygone rétrécirait sans que rien ne le dise.
PROVENANCES_ETABLI = ("collecte", "estime", "suppose")
PROVENANCES_DECLARE = ("declare", "precise")

# Libellés lisibles des provenances, pour la ligne de décompte sous le radar.
# Le manifeste impose que les provenances restent distinguables sur le radar :
# les deux couches en distinguent l'origine, cette ligne en donne le détail.
LIBELLES_PROVENANCE = {
    "collecte": "collecte",
    "estime": "estimation",
    "declare": "déclaré",
    "precise": "précisé",
    "suppose": "supposé",
}


def _pct(valeur, decimales=1):
    """Formate un pourcentage à la française : virgule décimale, espace avant %.

    Ne reçoit jamais None : l'appelant traite l'absence de réponse à part, par le
    libellé "aucune réponse". Un None arrivant ici afficherait "None %" dans un
    livrable client, accident déjà vécu et surveillé par check_valeurs_rapport.py.
    """
    return f"{valeur:.{decimales}f}".replace(".", ",") + " %"


def _decompte_criteres(repondus, total):
    """Formate "4 critères renseignés sur 16", accord compris, y compris à zéro.

    Écrit pour être lu à voix haute : "0 critères sur 10 renseignés" se prononce mal
    et laisse penser qu'il existe un critère nul.
    """
    if repondus == 0:
        return f"aucun critère renseigné sur {total}"
    if repondus == 1:
        return f"1 critère renseigné sur {total}"
    return f"{repondus} critères renseignés sur {total}"


def radar_svg(axes, title="Radar EROOM", note=None, width=1100, height=None,
              axes_etabli=None, axes_renseignes=None, couverture=None,
              provenances=None):
    """axes : liste de tuples (nom, valeur 0-100 OU None). Retourne le texte SVG complet.

    Une valeur `None` (dimension sans aucune donnée réelle) est rendue à
    r=0 (le polygone se pince sur cet axe), avec un anneau gris et le libellé
    "aucune réponse" au lieu d'un pourcentage : jamais assimilée à un vrai 0 %
    (qui signifierait "point fort confirmé partout"), une absence de réponse
    n'est pas une réponse.

    Paramètres facultatifs, tous omissibles : sans eux, la fonction rend le radar
    à une seule couche d'avant le chantier 13, ce qui garde les appelants anciens
    valides.

      axes_etabli      liste de valeurs (0-100 ou None), MÊME ORDRE que `axes`,
                       pour la couche pleine. `axes` porte alors le total, qui est
                       dessiné hachuré autour d'elle.
      axes_renseignes  liste de tuples (répondus, total), même ordre : affichée
                       sous chaque libellé d'axe.
      couverture       tuple (pourcentage, répondus, total) pour la jauge.
      provenances      dict {provenance: nombre} pour la ligne de décompte.

    width généreux par défaut : le libellé le plus long ("Facilité de
    changement") dépasse largement le rayon du radar. Une valeur trop petite
    le coupe sur le bord de l'image (constaté et corrigé après vérification
    par rendu réel, pas par relecture du code).

    height serré à l'inverse, et calculé selon ce qui est demandé : sans pied de
    figure, le contenu le plus bas est le libellé de l'axe du bas, dont la ligne
    de base tombe à cy + R + 55 + 34 = 669. Une valeur trop grande ne coupe rien mais
    laisse une bande blanche vide sous le radar, bien visible dans le rapport HTML
    où le SVG est encadré (constaté à 900, ramené à 720).

    Piège de vérification : contrôler ce rendu avec `qlmanage -t` (QuickLook)
    donne une image fausse. Il produit une vignette carrée, décale le contenu
    et coupe les libellés de droite, ce qui fait croire à un débordement
    inexistant. Utiliser `rsvg-convert -o sortie.png fichier.svg`, qui respecte
    le viewBox (il rend en revanche les emojis en noir, faute de police
    couleur : c'est sa limite, pas celle du SVG).
    """
    n = len(axes)
    if axes_etabli is not None and len(axes_etabli) != n:
        raise ValueError(
            f"axes_etabli a {len(axes_etabli)} valeurs pour {n} axes : les deux couches "
            "sont indexées par position, un décalage attribuerait la mesure d'une "
            "dimension à sa voisine sans que le rendu paraisse faux"
        )
    if axes_renseignes is not None and len(axes_renseignes) != n:
        raise ValueError(
            f"axes_renseignes a {len(axes_renseignes)} valeurs pour {n} axes"
        )

    pied = couverture is not None or provenances is not None
    if height is None:
        height = 792 if pied else 720

    cx, cy = width / 2, 360
    R = 220

    def point(i, value):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        r = R * ((value or 0) / SCALE)
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    def axis_end(i):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        return cx + R * math.cos(angle), cy + R * math.sin(angle)

    def label_point(i, offset=55):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        return cx + (R + offset) * math.cos(angle), cy + (R + offset) * math.sin(angle)

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '  # genericite: ok - espace de noms XML du format SVG, pas un domaine audité
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">'
    )
    # Motif de hachures : pas de fond opaque, sinon la couche déclarée masquerait
    # la grille et les axes qu'elle recouvre.
    svg.append(
        f'<defs><pattern id="{HACHURE_ID}" width="9" height="9" '
        f'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        f'<line x1="0" y1="0" x2="0" y2="9" stroke="{NAVY}" stroke-width="2.5"/>'
        f'</pattern></defs>'
    )
    svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')
    svg.append(
        f'<text x="{width/2:.1f}" y="30" text-anchor="middle" font-size="18" '
        f'font-weight="bold">{escape(title)}</text>'
    )

    # grille = vrais cercles (pas des hexagones)
    #
    # Les graduations sont mises de côté et rendues APRÈS les polygones, avec un halo
    # blanc. Elles sont posées sur l'axe vertical, à l'endroit exact où passe le
    # polygone : dessinées avant, la couche pleine les recouvre. Vu sur le rendu de
    # démonstration, où le "2" de "25 %" avait disparu et où la graduation se lisait
    # "5 %".
    graduations = []
    for ring in (25, 50, 75, 100):
        color = "#333" if ring == 100 else "#ccc"
        svg.append(
            f'<circle cx="{cx}" cy="{cy}" r="{R*ring/SCALE:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        lx, ly = cx, cy - R * ring / SCALE
        graduations.append(
            f'<text x="{lx+6:.1f}" y="{ly-4:.1f}" font-size="12" fill="#666" '
            f'paint-order="stroke" stroke="white" stroke-width="3">{ring} %</text>'
        )

    # axes = lignes droites du centre au bord
    for i in range(n):
        ex, ey = axis_end(i)
        svg.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#999" stroke-width="1"/>')

    # Bloc de libellé de chaque axe : le nom, la valeur, puis le nombre de critères
    # renseignés.
    #
    # ⚠️ La valeur est écrite ICI et pas près de son point sur le polygone, contre
    # l'usage des radars, et c'est délibéré. Sur un audit réel, quatre dimensions
    # sur six valaient presque zéro : leurs quatre nombres se sont empilés au
    # centre, par-dessus les marqueurs des dimensions sans réponse, illisibles.
    # Les repousser à un rayon minimal aurait été pire : un "0,0 %" posé au-delà du
    # cercle des 25 % se lit comme 28 %. Le bloc de libellé, lui, est toujours hors
    # de la grille et son axe est nommé juste au-dessus : aucune ambiguïté possible.
    #
    # La troisième ligne est ce qui empêche de lire un axe à 0 % comme un axe
    # exemplaire : elle dit combien de critères ont réellement répondu.
    for i, (name, val) in enumerate(axes):
        lx, ly = label_point(i)
        anchor = "middle"
        if lx < cx - 10:
            anchor = "end"
        elif lx > cx + 10:
            anchor = "start"
        svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="14" '
            f'font-weight="bold" fill="#222">{escape(name)}</text>'
        )
        if val is None:
            # "aucune réponse", pas "N/A" : le rapport est lu à voix haute par une
            # synthèse vocale, qui épelle les sigles. Et une absence de réponse
            # n'est jamais assimilée à un 0 %, qui voudrait dire "point fort
            # confirmé partout".
            svg.append(
                f'<text x="{lx:.1f}" y="{ly + 18:.1f}" text-anchor="{anchor}" font-size="13" '
                f'font-weight="bold" fill="{GREY}">aucune réponse</text>'
            )
        else:
            svg.append(
                f'<text x="{lx:.1f}" y="{ly + 18:.1f}" text-anchor="{anchor}" font-size="13" '
                f'font-weight="bold" fill="{NAVY}">{escape(_pct(val))} de potentiel</text>'
            )
        if axes_renseignes is not None:
            repondus, total = axes_renseignes[i]
            # "renseignés" placé juste après "critères", pas après le total : la
            # première tournure essayée, "1 critère sur 5 renseigné", laissait
            # entendre que c'était le 5 qui était renseigné.
            svg.append(
                f'<text x="{lx:.1f}" y="{ly + 34:.1f}" text-anchor="{anchor}" font-size="12" '
                f'fill="{GREY}">{_decompte_criteres(repondus, total)}</text>'
            )

    # Polygones de données (lignes droites entre points, comme le Sheet source).
    # La couche hachurée d'abord, la pleine par-dessus : dans l'autre ordre les
    # hachures recouvriraient la couche pleine et les deux se confondraient.
    def polygone(valeurs, fill, fill_opacity=None, stroke_dash=None):
        pts = [point(i, v) for i, v in enumerate(valeurs)]
        pts_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
        opacity = f' fill-opacity="{fill_opacity}"' if fill_opacity else ""
        dash = f' stroke-dasharray="{stroke_dash}"' if stroke_dash else ""
        return (
            f'<polygon points="{pts_str}" fill="{fill}"{opacity} '
            f'stroke="{NAVY}" stroke-width="2.5"{dash}/>'
        )

    valeurs_totales = [val for _, val in axes]
    if axes_etabli is None:
        svg.append(polygone(valeurs_totales, NAVY, fill_opacity="0.40"))
    else:
        svg.append(polygone(valeurs_totales, f"url(#{HACHURE_ID})", stroke_dash="7 4"))
        svg.append(polygone(axes_etabli, NAVY, fill_opacity="0.40"))

    svg.extend(graduations)

    # Marqueurs sur les axes. Aucun texte ici : tous les nombres sont dans les blocs
    # de libellé, hors de la grille.
    for i, (name, val) in enumerate(axes):
        p = point(i, val)
        if val is None:
            # Absence de réponse : anneau gris au centre. La dimension est bien
            # dessinée, mais éteinte, et son bloc de libellé dit "aucune réponse".
            svg.append(
                f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="5" fill="white" '
                f'stroke="{GREY}" stroke-width="2"><title>'
                f'{escape(name)} : aucune réponse, ce n\'est pas un 0 %</title></circle>'
            )
            continue
        svg.append(
            f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="6" fill="{NAVY}" stroke="white" '
            f'stroke-width="1.5"><title>{escape(name)} : {escape(_pct(val))} '
            f'de potentiel d\'optimisation</title></circle>'
        )
        # Couche pleine : un anneau creux là où elle s'arrête sur cet axe. Sa
        # valeur n'est PAS écrite sur l'image, elle est portée par un <title>,
        # que le navigateur montre au survol et qu'un lecteur d'écran énonce.
        #
        # Deux placements du nombre ont été essayés et jetés après avoir regardé
        # l'image : près de l'anneau, les axes dont rien n'est établi se pincent
        # tous sur le centre et leurs nombres s'y empilent par-dessus le marqueur
        # "N/A" ; sous la valeur du total, le nombre retombe sur le bord du
        # polygone des axes obliques. La valeur chiffrée de chaque couche est de
        # toute façon dans eof-rempli.md et dans le rapport : sur le radar, ce qui
        # doit se voir est l'écart entre les deux couches, et il se voit.
        if axes_etabli is not None and axes_etabli[i] is not None and axes_etabli[i] < val:
            pe = point(i, axes_etabli[i])
            infobulle = (
                f"{name} : {_pct(val)} de potentiel d'optimisation, "
                f"dont {_pct(axes_etabli[i])} établi par nos mesures, "
                f"le reste venant des réponses du service audité"
            )
            svg.append(
                f'<circle cx="{pe[0]:.1f}" cy="{pe[1]:.1f}" r="4.5" fill="white" '
                f'stroke="{NAVY}" stroke-width="2"><title>{escape(infobulle)}</title></circle>'
            )

    # Légende en haut à gauche : le coin est libre, et le pied de figure est déjà
    # chargé. Deux lignes plutôt qu'une : les libellés dépassent 40 caractères et
    # côte à côte ils atteindraient le libellé de l'axe du haut.
    if axes_etabli is not None:
        # Tant que le service audité n'a rien répondu, les deux couches se
        # superposent exactement et la couche hachurée est invisible. Le dire, plutôt
        # que d'afficher une légende pour une couche absente : sans cette mention, le
        # lecteur cherche des hachures qui n'existent pas et doute de la figure.
        rien_de_declare = all(
            e == t for e, (_, t) in zip(axes_etabli, axes)
        )
        libelle_declare = "en hachuré : ce que le service audité a déclaré"
        if rien_de_declare:
            libelle_declare += " (aucune réponse à ce jour)"
        for k, (fill, opacity, libelle) in enumerate([
            (NAVY, ' fill-opacity="0.40"', "en plein : ce que nous avons établi nous-mêmes"),
            (f"url(#{HACHURE_ID})", "", libelle_declare),
        ]):
            y = 46 + k * 22
            svg.append(
                f'<rect x="24" y="{y}" width="16" height="14" fill="{fill}"{opacity} '
                f'stroke="{NAVY}" stroke-width="1.5"/>'
            )
            svg.append(
                f'<text x="48" y="{y + 12}" font-size="12" fill="#222">{escape(libelle)}</text>'
            )

    # Pied de figure : jauge de ce qui est renseigné, puis décompte par provenance,
    # puis la note. La jauge est là pour qu'un potentiel bas ne se lise pas comme
    # un service mûr alors qu'il ne dit que "nous n'avons presque rien regardé".
    if couverture is not None:
        pct, repondus, total = couverture
        bar_w, bar_h, bar_y = 560, 14, 708
        bar_x = (width - bar_w) / 2
        svg.append(
            f'<text x="{width/2:.1f}" y="700" text-anchor="middle" font-size="12" fill="#222">'
            f'Renseigné à ce jour : {escape(_pct(pct, 0))} du potentiel maximum du référentiel '
            f'({repondus} critères sur {total})</text>'
        )
        svg.append(
            f'<rect x="{bar_x:.1f}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
            f'fill="#EEE" stroke="{GREY}" stroke-width="1"/>'
        )
        remplie = bar_w * max(0.0, min(100.0, pct)) / 100
        if remplie > 0:
            svg.append(
                f'<rect x="{bar_x:.1f}" y="{bar_y}" width="{remplie:.1f}" height="{bar_h}" '
                f'fill="{NAVY}"/>'
            )

    if provenances is not None:
        detail = ", ".join(
            f"{LIBELLES_PROVENANCE.get(p, p)} {provenances.get(p, 0)}"
            for p in ("collecte", "estime", "declare", "precise", "suppose")
        )
        svg.append(
            f'<text x="{width/2:.1f}" y="748" text-anchor="middle" font-size="12" '
            f'fill="{GREY}">Provenance des réponses : {escape(detail)}</text>'
        )

    if note:
        svg.append(
            f'<text x="{width/2:.1f}" y="{height - 22}" text-anchor="middle" font-size="12" '
            f'fill="#666">{escape(note)}</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


def build_radar_from_results(audit_results, domaine=None, title=None, note=None):
    """Construit le radar à deux couches depuis un `eof-audit-results.json` chargé.

    Point d'entrée UNIQUE des deux producteurs du fichier de résultats
    (`run_eof.py` et `processus/fusionner_lots.py`). Ils ont déjà deux
    arithmétiques jumelles à tenir alignées ; leur laisser en plus deux façons de
    dessiner le radar garantissait qu'un jour l'une des deux montrerait autre
    chose que l'autre sur les mêmes données.

    La couche pleine n'est PAS recalculée depuis un dénominateur maison : elle est
    prise comme la part du potentiel déjà affiché qui vient de nos propres
    provenances. Le producteur reste seul maître de son dénominateur (les deux
    ne traitent pas les critères sans objet de la même façon), et la couche
    pleine ne peut pas sortir de la couche hachurée.
    """
    dimensions = audit_results.get("dimensions") or []
    criteres = audit_results.get("criteres") or []
    noms_dimensions = [d.get("nom") for d in dimensions]

    # Potentiel retenu par dimension, séparé selon l'origine de la réponse.
    retenu = {nom: {"etabli": 0.0, "total": 0.0} for nom in noms_dimensions}
    pmax_par_dimension = {nom: {"repondu": 0.0, "total": 0.0} for nom in noms_dimensions}
    for c in criteres:
        nom = c.get("dimension")
        if nom not in retenu:
            # Les questions du diagnostic rapide n'appartiennent à aucune des 6
            # dimensions détaillées et n'ont pas de potentiel : elles ne comptent
            # ni dans le radar ni dans la jauge.
            continue
        pmax = c.get("potentiel_max") or 0.0
        pmax_par_dimension[nom]["total"] += pmax
        if c.get("reponse") is None:
            continue
        pmax_par_dimension[nom]["repondu"] += pmax
        coefficient = c.get("coefficient") or 0.0
        retenu[nom]["total"] += coefficient * pmax
        if c.get("provenance") in PROVENANCES_ETABLI:
            retenu[nom]["etabli"] += coefficient * pmax

    axes = []
    axes_etabli = []
    axes_renseignes = []
    for d in dimensions:
        nom = d.get("nom")
        total_pct = d.get("potentiel_optimisation_pct")
        axes.append((nom, total_pct))
        if total_pct is None:
            axes_etabli.append(None)
        elif retenu[nom]["total"] > 0:
            axes_etabli.append(total_pct * retenu[nom]["etabli"] / retenu[nom]["total"])
        else:
            # Tout ce qui a répondu porte un coefficient nul : le potentiel affiché
            # est 0, les deux couches se confondent au centre.
            axes_etabli.append(total_pct)
        axes_renseignes.append((d.get("repondus") or 0, d.get("total") or 0))

    # Jauge : part du potentiel maximum du référentiel déjà renseignée. Pondérée
    # par `potentiel_max`, comme le demande le manifeste : un critère à 2,0 qui
    # manque ne laisse pas le même trou qu'un critère à 0,5. Un critère répondu
    # "non applicable" compte comme renseigné, parce qu'il l'a bien été.
    pmax_total = sum(v["total"] for v in pmax_par_dimension.values())
    pmax_repondu = sum(v["repondu"] for v in pmax_par_dimension.values())
    couverture = None
    if pmax_total > 0:
        criteres_des_dimensions = [c for c in criteres if c.get("dimension") in retenu]
        couverture = (
            pmax_repondu / pmax_total * 100,
            sum(1 for c in criteres_des_dimensions if c.get("reponse") is not None),
            len(criteres_des_dimensions),
        )

    if title is None:
        domaine_txt = domaine or audit_results.get("domaine") or "service audité"
        title = f"EOF : potentiel d'optimisation ({domaine_txt})"
    if note is None:
        note = (
            "Une dimension dont aucun critère n'a répondu est marquée \"aucune réponse\", "
            "jamais 0 % : un 0 % voudrait dire point fort confirmé sur toute la dimension."
        )

    return radar_svg(
        axes,
        title=title,
        note=note,
        axes_etabli=axes_etabli,
        axes_renseignes=axes_renseignes,
        couverture=couverture,
        provenances=audit_results.get("repondus_par_provenance"),
    )


def _demo(output_path):
    """Radar de démonstration : le rendu complet, y compris les cas rares.

    Les valeurs sont fictives et choisies pour montrer d'un coup les quatre
    situations qu'on ne voit jamais toutes sur un même audit réel : un axe sans
    aucune réponse, un axe où tout vient de nos mesures, un axe où tout vient du
    déclaratif du service audité, et un axe partagé entre les deux.
    """
    totaux = [35, 70, 15, 85, 50, None]
    etablis = [35, 20, 15, 0, 32, None]
    renseignes = [(16, 16), (3, 5), (8, 8), (2, 6), (5, 9), (0, 10)]
    svg_text = radar_svg(
        list(zip(AXES_EOF, totaux)),
        title="Radar EROOM : test complet (6 axes, valeurs fictives)",
        note="Valeurs fictives de potentiel d'optimisation, uniquement pour valider le rendu visuel",
        axes_etabli=etablis,
        axes_renseignes=renseignes,
        couverture=(48.0, 34, 54),
        provenances={"collecte": 18, "estime": 6, "declare": 8, "precise": 2, "suppose": 0},
    )
    with open(output_path, "w") as f:
        f.write(svg_text)
    print(f"SVG de démonstration écrit : {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 generate_radar_svg.py <fichier_sortie.svg>")
        sys.exit(1)
    _demo(sys.argv[1])
