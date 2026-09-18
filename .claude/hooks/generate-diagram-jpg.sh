#!/bin/bash
# Hook PostToolUse (matcher Bash). Apres une commande `plantuml -tsvg` qui
# regenere un ou plusieurs diagrammes dans documentation/diagrammes/, genere
# aussi la version JPG legere (800px de large, qualite 85, meme nom) a cote.
# Cf. skill diagrammes-analyse-parcours, section "JPG leger".
#
# Ne fait rien pour toute autre commande Bash (sort immediatement).

PROJECT_DIR="/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"

# Filtre d'abord sur le JSON brut (pas de spawn `jq`) : la commande n'apparait
# de toute facon que sous forme de sous-chaine du JSON, donc ce filtre grossier
# suffit a ecarter les >99% d'appels Bash qui ne concernent pas plantuml.
input=$(cat)
case "$input" in
  *plantuml*-tsvg*documentation/diagrammes*) ;;
  *) exit 0 ;;
esac

cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)

echo "$cmd" | grep -oE '[A-Za-z0-9._/-]*documentation/diagrammes/[A-Za-z0-9_.-]+\.puml' | while read -r f; do
  case "$f" in
    /*) puml="$f" ;;
    *) puml="$PROJECT_DIR/$f" ;;
  esac
  base="${puml%.puml}"
  svg="${base}.svg"
  [ -f "$svg" ] || continue
  tmp_png="/tmp/$(basename "$base").diagram-jpg-hook.png"
  if rsvg-convert -b white -w 800 "$svg" -o "$tmp_png" 2>/dev/null; then
    magick "$tmp_png" -quality 85 "${base}.jpg" 2>/dev/null
  fi
  rm -f "$tmp_png"
done

exit 0
