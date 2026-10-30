#!/bin/bash
# PostToolUse hook (matcher Bash). After a `plantuml -tsvg` command that
# regenerates one or more diagrams in documentation/diagrammes/, also generate
# the lightweight JPG version (800px wide, quality 85, same name) alongside.
# Cf. skill diagrammes-analyse-parcours, section "Lightweight JPG".
#
# Does nothing for any other Bash command (exits immediately).

PROJECT_DIR="/Users/pierrick.crepy/Documents/missions/MyAIEnv/Agent EROOM"

# Filter first on the raw JSON (no `jq` spawn): the command only ever appears
# as a substring of the JSON anyway, so this coarse filter is enough to rule
# out >99% of Bash calls that do not involve plantuml.
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
