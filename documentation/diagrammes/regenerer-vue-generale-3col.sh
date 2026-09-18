#!/bin/bash
# Régénère toutes les versions (.pdf, .jpg) de
# analyse-parcours-vue-generale-horizontal-light-3col.svg à partir du SVG,
# qui reste la seule source de vérité (construit à la main, jamais via
# `plantuml -tsvg`, cf. commentaire de tête du .svg).
#
# Usage : bash regenerer-vue-generale-3col.sh [largeur_jpg] [qualite_jpg]
#   largeur_jpg  : largeur cible du JPG en px (défaut 1600)
#   qualite_jpg  : qualité JPEG (défaut 85)
#
# Historique de réglage (2026-09-18) : un premier essai est passé par
# vipsthumbnail/MozJPEG (libvips, projet "traitement des images", skill
# image-compression) à 1000px puis 1400px -- Q=75 avec trellis_quant/
# overshoot_deringing (pensés pour la photo) rendait le texte fin (13-14px)
# illisible ; Q=92 sans ces options était correct mais plus lourd (217 Ko à
# 1400px) que la méthode plus simple ci-dessous (180 Ko à 1600px). Décision :
# revenir à `magick -quality` (pas de MozJPEG), plus léger pour ce diagramme
# précis (texte + traits nets, pas une photo -- MozJPEG n'a pas d'avantage
# ici). Si le besoin change (photo, illustration), rouvrir le skill
# image-compression plutôt que réintroduire vipsthumbnail à la main ici.
#
# Étapes :
#   1. SVG -> PDF (rsvg-convert, taille native)
#   2. SVG -> PNG (largeur cible, fond blanc) -> JPG (magick -quality)

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$DIR/analyse-parcours-vue-generale-horizontal-light-3col"
SVG="$BASE.svg"
PDF="$BASE.pdf"
JPG="$BASE.jpg"

LARGEUR_JPG="${1:-1600}"
QUALITE_JPG="${2:-85}"

[ -f "$SVG" ] || { echo "SVG introuvable : $SVG" >&2; exit 1; }
command -v rsvg-convert >/dev/null 2>&1 || { echo "rsvg-convert requis" >&2; exit 1; }
command -v magick >/dev/null 2>&1 || { echo "magick (ImageMagick) requis" >&2; exit 1; }

echo "-> PDF ($PDF)"
rsvg-convert -f pdf -o "$PDF" "$SVG"

TMP_PNG="$(mktemp -t vue-generale-3col-src).png"
echo "-> PNG (${LARGEUR_JPG}px)"
rsvg-convert -b white -w "$LARGEUR_JPG" "$SVG" -o "$TMP_PNG"

echo "-> JPG (${LARGEUR_JPG}px, quality ${QUALITE_JPG})"
magick "$TMP_PNG" -quality "$QUALITE_JPG" "$JPG"

rm -f "$TMP_PNG"

echo "OK :"
ls -lh "$PDF" "$JPG"
identify "$JPG" 2>/dev/null || true
