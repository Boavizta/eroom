#!/bin/bash
# Regenerates all versions (.pdf, .jpg) of
# analyse-parcours-vue-generale-horizontal-light-3col.svg from the SVG,
# which remains the single source of truth (built by hand, never via
# `plantuml -tsvg`, cf. header comment of the .svg).
#
# Usage: bash regenerate-overview-3col.sh [jpg_width] [jpg_quality]
#   jpg_width   : target width of the JPG in px (default 1600)
#   jpg_quality : JPEG quality (default 85)
#
# Tuning history (2026-09-18): a first attempt went through
# vipsthumbnail/MozJPEG (libvips, "image processing" project, skill
# image-compression) at 1000px then 1400px -- Q=75 with trellis_quant/
# overshoot_deringing (meant for photos) made the thin text (13-14px)
# unreadable ; Q=92 without these options was correct but heavier (217 KB at
# 1400px) than the simpler method below (180 KB at 1600px). Decision:
# back to `magick -quality` (not MozJPEG), lighter for this specific
# diagram (sharp text + lines, not a photo -- MozJPEG has no advantage
# here). If the need changes (photo, illustration), reopen the
# image-compression skill rather than reintroducing vipsthumbnail by hand here.
#
# Steps:
#   1. SVG -> PDF (rsvg-convert, native size)
#   2. SVG -> PNG (target width, white background) -> JPG (magick -quality)

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$DIR/analyse-parcours-vue-generale-horizontal-light-3col"
SVG="$BASE.svg"
PDF="$BASE.pdf"
JPG="$BASE.jpg"

JPG_WIDTH="${1:-1600}"
JPG_QUALITY="${2:-85}"

[ -f "$SVG" ] || { echo "SVG not found: $SVG" >&2; exit 1; }
command -v rsvg-convert >/dev/null 2>&1 || { echo "rsvg-convert required" >&2; exit 1; }
command -v magick >/dev/null 2>&1 || { echo "magick (ImageMagick) required" >&2; exit 1; }

echo "-> PDF ($PDF)"
rsvg-convert -f pdf -o "$PDF" "$SVG"

TMP_PNG="$(mktemp -t vue-generale-3col-src).png"
echo "-> PNG (${JPG_WIDTH}px)"
rsvg-convert -b white -w "$JPG_WIDTH" "$SVG" -o "$TMP_PNG"

echo "-> JPG (${JPG_WIDTH}px, quality ${JPG_QUALITY})"
magick "$TMP_PNG" -quality "$JPG_QUALITY" "$JPG"

rm -f "$TMP_PNG"

echo "OK:"
ls -lh "$PDF" "$JPG"
identify "$JPG" 2>/dev/null || true
