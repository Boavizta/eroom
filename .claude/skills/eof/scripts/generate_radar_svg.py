#!/usr/bin/env python3
"""Génère un radar SVG (grille circulaire) pour la synthèse du référentiel EOF.

Usage :
    python3 generate_radar_svg.py sortie.svg
        -> génère un radar de démonstration avec des valeurs fictives
           (les 6 axes du référentiel EOF, valeurs différentes pour voir le rendu)

    from generate_radar_svg import radar_svg
    svg_text = radar_svg([("Produit", 35), ("Architecture", 70), ...])

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
SCALE = 100  # axe en pourcentage (0-100%), comme le radar du Google Sheet source

AXES_EOF = [
    "🛖 Produit",
    "🗺️ Architecture",
    "🏢 Infrastructure",
    "💾 Stockage & Données",
    "👨‍💻 Algo & Code",
    "🛠 Facilité de changement",
]


def radar_svg(axes, title="Radar EROOM", note=None, width=1100, height=900):
    """axes : liste de tuples (nom, valeur 0-100 OU None). Retourne le texte SVG complet.

    Une valeur `None` (dimension sans aucune donnée réelle) est rendue à
    r=0 (le polygone se pince sur cet axe) avec un marqueur gris "N/A" au
    lieu d'un point coloré + pourcentage : jamais assimilée à un vrai 0%
    (qui signifierait "point fort confirmé partout"), une absence de
    réponse n'est pas une réponse.

    width/height généreux par défaut : le libellé le plus long ("Facilité de
    changement") dépasse largement le rayon du radar. Une valeur trop petite
    le coupe sur le bord de l'image (constaté et corrigé après vérification
    par rendu réel, pas par relecture du code).
    """
    cx, cy = width / 2, 360
    R = 220
    n = len(axes)

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
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">'
    )
    svg.append(f'<rect width="{width}" height="{height}" fill="white"/>')
    svg.append(
        f'<text x="{width/2:.1f}" y="30" text-anchor="middle" font-size="18" '
        f'font-weight="bold">{escape(title)}</text>'
    )

    # grille = vrais cercles (pas des hexagones)
    for ring in (25, 50, 75, 100):
        color = "#333" if ring == 100 else "#ccc"
        svg.append(
            f'<circle cx="{cx}" cy="{cy}" r="{R*ring/SCALE:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        lx, ly = cx, cy - R * ring / SCALE
        svg.append(f'<text x="{lx+6:.1f}" y="{ly-4:.1f}" font-size="12" fill="#666">{ring}%</text>')

    # axes = lignes droites du centre au bord
    for i in range(n):
        ex, ey = axis_end(i)
        svg.append(f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#999" stroke-width="1"/>')

    # labels de categorie
    for i, (name, _) in enumerate(axes):
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

    # polygone de donnees (lignes droites entre points, comme le Sheet source)
    pts = [point(i, val) for i, (_, val) in enumerate(axes)]
    pts_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
    svg.append(
        f'<polygon points="{pts_str}" fill="{NAVY}" fill-opacity="0.40" '
        f'stroke="{NAVY}" stroke-width="3"/>'
    )

    for i, (name, val) in enumerate(axes):
        p = point(i, val)
        svg.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="6" fill="{NAVY}" stroke="white" stroke-width="1.5"/>')
        angle = -math.pi / 2 + i * 2 * math.pi / n
        lx = p[0] + 22 * math.cos(angle)
        ly = p[1] + 22 * math.sin(angle)
        svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="13" '
            f'fill="{NAVY}" font-weight="bold">{val}%</text>'
        )

    if note:
        svg.append(
            f'<text x="{width/2:.1f}" y="{height-30}" text-anchor="middle" font-size="12" '
            f'fill="#666">{escape(note)}</text>'
        )

    svg.append("</svg>")
    return "\n".join(svg)


def _demo(output_path):
    """Radar de démonstration : valeurs fictives, une par axe, pour vérifier le rendu."""
    valeurs_demo = [35, 70, 15, 85, 50, 40]
    axes = list(zip(AXES_EOF, valeurs_demo))
    svg_text = radar_svg(
        axes,
        title="Radar EROOM — test complet (6 axes, valeurs fictives)",
        note="Exemple avec des scores fictifs, uniquement pour valider le rendu visuel",
    )
    with open(output_path, "w") as f:
        f.write(svg_text)
    print(f"SVG de démonstration écrit : {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 generate_radar_svg.py <fichier_sortie.svg>")
        sys.exit(1)
    _demo(sys.argv[1])
