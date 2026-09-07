#!/usr/bin/env bash
#
# Compare la photocopie versionnée du référentiel EOF avec la Google Sheet vivante
# d'EROOM, onglet par onglet.
#
# Pourquoi ce script existe : le référentiel EOF que notre code lit
# (eof-referentiel.json) est fabriqué à partir d'un export de la Google Sheet
# d'EROOM. Si EROOM modifie sa Sheet, rien ne nous alerte. Ce script est la seule
# façon de le savoir, et il n'est utile QUE parce que la photocopie de référence
# est versionnée à côté : sans point de comparaison, retélécharger n'apprend rien.
#
# Usage :
#   .claude/skills/eof/scripts/verifier_source_sheet.sh            # compare
#   .claude/skills/eof/scripts/verifier_source_sheet.sh --rafraichir # remplace la photocopie
#
# Codes de sortie :
#   0  la Sheet est identique à la photocopie, ou rafraîchissement réussi
#   1  au moins un onglet a changé, ou un téléchargement a échoué
#
# Aucune dépendance : curl et diff seulement. Ne touche à aucun fichier du dépôt
# sauf avec --rafraichir, qui n'écrit que dans docs/source-sheet/.

set -euo pipefail

SHEET_ID="1zJkT_5Ck9WKyxHZ7Uf5f03PmsaLh_SUB7LzKToPlcZ0"
BASE="https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:json"

# Racine du dépôt, déduite de l'emplacement de ce script, pour pouvoir être lancé
# depuis n'importe quel répertoire.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REFERENCE_DIR="${SCRIPT_DIR}/../docs/source-sheet"

# Un onglet par ligne : "gid nom-de-fichier". Les gid viennent de l'URL de chaque
# onglet dans l'interface Google Sheets. Ne pas les deviner.
ONGLETS="
1677462955 a-lire.json
296916801  diag-rapide.json
2022239731 produit.json
615231881  architecture.json
1603246930 infrastructure.json
31675448   stockage.json
1046049603 algo-code.json
24436077   facilite.json
958616182  synthese.json
"

RAFRAICHIR=0
if [ "${1:-}" = "--rafraichir" ]; then
  RAFRAICHIR=1
elif [ -n "${1:-}" ]; then
  echo "Option inconnue : $1" >&2
  echo "Usage : $(basename "$0") [--rafraichir]" >&2
  exit 1
fi

if [ ! -d "$REFERENCE_DIR" ]; then
  echo "[ÉCHEC] la photocopie de référence est absente : $REFERENCE_DIR" >&2
  exit 1
fi

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Sheet source : https://docs.google.com/spreadsheets/d/${SHEET_ID}/edit"
echo "Photocopie   : ${REFERENCE_DIR}"
echo

nb_changes=0
nb_echecs=0
nb_identiques=0

while read -r gid fichier; do
  [ -z "${gid:-}" ] && continue

  cible="${TEMP_DIR}/${fichier}"
  if ! curl -sfL -A "Mozilla/5.0" "${BASE}&gid=${gid}" -o "$cible"; then
    echo "[ÉCHEC RÉSEAU] ${fichier} (gid ${gid}) : téléchargement impossible"
    nb_echecs=$((nb_echecs + 1))
    continue
  fi

  # Une Sheet devenue privée ou un gid supprimé renvoie du HTML avec un code 200,
  # pas une erreur réseau. Contrôler la signature du format gviz, sinon on
  # comparerait une page d'erreur au référentiel.
  if ! head -c 60 "$cible" | grep -q 'google.visualization.Query.setResponse'; then
    echo "[RÉPONSE INVALIDE] ${fichier} (gid ${gid}) : ce n'est pas un export gviz."
    echo "                   Sheet devenue privée, ou onglet supprimé ?"
    nb_echecs=$((nb_echecs + 1))
    continue
  fi

  reference="${REFERENCE_DIR}/${fichier}"
  if [ ! -f "$reference" ]; then
    echo "[NOUVEAU] ${fichier} : absent de la photocopie"
    nb_changes=$((nb_changes + 1))
  elif diff -q "$reference" "$cible" >/dev/null; then
    nb_identiques=$((nb_identiques + 1))
  else
    echo "[A CHANGÉ] ${fichier}"
    nb_changes=$((nb_changes + 1))
  fi

  if [ "$RAFRAICHIR" -eq 1 ]; then
    cp "$cible" "${REFERENCE_DIR}/${fichier}"
  fi
done <<< "$ONGLETS"

echo
echo "${nb_identiques} onglet(s) identique(s), ${nb_changes} modifié(s), ${nb_echecs} en échec."

if [ "$RAFRAICHIR" -eq 1 ]; then
  echo
  echo "Photocopie rafraîchie. À faire maintenant :"
  echo "  1. git diff .claude/skills/eof/docs/source-sheet/  pour voir ce qu'EROOM a changé"
  echo "  2. régénérer le référentiel, cf. étape 2 de .claude/skills/eof/SKILL.md"
  echo "  3. rejouer processus/valider_coherence_cles.py"
  exit 0
fi

if [ "$nb_echecs" -gt 0 ] || [ "$nb_changes" -gt 0 ]; then
  if [ "$nb_changes" -gt 0 ]; then
    echo
    echo "La Sheet d'EROOM a évolué depuis la photocopie. Pour l'adopter :"
    echo "  $(basename "$0") --rafraichir"
  fi
  exit 1
fi

echo "La Sheet d'EROOM n'a pas bougé. Le référentiel est à jour."
exit 0
