#!/bin/bash
# Convertit un diagramme .svg en un .pptx a une seule diapositive (image plein cadre).
#
# Pourquoi ce detour (SVG -> PNG -> ODP fabrique a la main -> PPTX via LibreOffice) :
# LibreOffice headless n'a pas de filtre d'export direct SVG/PNG -> PPTX (le SVG et le
# PNG s'ouvrent comme des documents Draw, qui ne savent exporter qu'en formats Draw).
# En revanche il convertit tres bien un document de PRESENTATION (ODP) vers PPTX. On
# fabrique donc un .odp minimal (une page, une image plein cadre) puis on le convertit.
#
# Limite connue : le diagramme est incruste en IMAGE (comme le PDF/JPG), pas en formes
# vectorielles editables. Pour un PPTX avec des formes modifiables dans PowerPoint/Keynote,
# il faut repasser par un export manuel depuis un outil de dessin - ce script sert a
# eviter que le fichier reste bloque sur un unique export manuel non reproductible.
#
# Usage : svg_to_pptx.sh <fichier.svg> [largeur_png_px]
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage : $0 <fichier.svg> [largeur_png_px]" >&2
  exit 1
fi

SVG="$1"
PNG_WIDTH="${2:-1920}"

if [ ! -f "$SVG" ]; then
  echo "Fichier introuvable : $SVG" >&2
  exit 1
fi

OUT_DIR="$(cd "$(dirname "$SVG")" && pwd)"
BASE="$(basename "$SVG" .svg)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

PNG="$WORK_DIR/image1.png"
rsvg-convert -b white -w "$PNG_WIDTH" "$SVG" -o "$PNG"

# Largeur de diapositive fixee au standard PowerPoint 16:9 (33.867cm = 13.333in) ;
# la hauteur se deduit du ratio reel du PNG pour un remplissage plein cadre sans
# deformation ni bande vide.
read -r PX_W PX_H <<< "$(magick identify -format "%w %h" "$PNG")"
PAGE_W_CM="33.867"
PAGE_H_CM="$(LC_NUMERIC=C awk -v w="$PAGE_W_CM" -v pw="$PX_W" -v ph="$PX_H" 'BEGIN { printf "%.3f", w * ph / pw }')"

ODP_DIR="$WORK_DIR/odp"
mkdir -p "$ODP_DIR/META-INF" "$ODP_DIR/Pictures"
cp "$PNG" "$ODP_DIR/Pictures/image1.png"

printf 'application/vnd.oasis.opendocument.presentation' > "$ODP_DIR/mimetype"

cat > "$ODP_DIR/META-INF/manifest.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.presentation"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="Pictures/image1.png" manifest:media-type="image/png"/>
</manifest:manifest>
EOF

cat > "$ODP_DIR/meta.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2">
 <office:meta/>
</office:document-meta>
EOF

cat > "$ODP_DIR/styles.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.2">
 <office:styles/>
 <office:automatic-styles>
  <style:page-layout style:name="PL1">
   <style:page-layout-properties fo:page-width="${PAGE_W_CM}cm" fo:page-height="${PAGE_H_CM}cm" style:print-orientation="landscape"/>
  </style:page-layout>
 </office:automatic-styles>
 <office:master-styles>
  <style:master-page style:name="Default" style:page-layout-name="PL1"/>
 </office:master-styles>
</office:document-styles>
EOF

cat > "$ODP_DIR/content.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
  xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
  xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
  office:version="1.2">
 <office:automatic-styles>
  <style:style style:name="gr1" style:family="graphic">
   <style:graphic-properties draw:stroke="none" draw:fill="none" style:mirror="none"/>
  </style:style>
  <style:style style:name="Pg1" style:family="drawing-page"/>
 </office:automatic-styles>
 <office:body>
  <office:presentation>
   <draw:page draw:name="page1" draw:style-name="Pg1" draw:master-page-name="Default">
    <draw:frame draw:style-name="gr1" draw:layer="layout" svg:width="${PAGE_W_CM}cm" svg:height="${PAGE_H_CM}cm" svg:x="0cm" svg:y="0cm">
     <draw:image xlink:href="Pictures/image1.png" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>
    </draw:frame>
   </draw:page>
  </office:presentation>
 </office:body>
</office:document-content>
EOF

ODP_FILE="$WORK_DIR/$BASE.odp"
( cd "$ODP_DIR" && zip -X -q -0 "$ODP_FILE" mimetype && zip -X -q -rg "$ODP_FILE" META-INF content.xml styles.xml meta.xml Pictures )

soffice --headless --convert-to pptx --outdir "$WORK_DIR" "$ODP_FILE" >/dev/null

mv "$WORK_DIR/$BASE.pptx" "$OUT_DIR/$BASE.pptx"
echo "OK : $OUT_DIR/$BASE.pptx"
