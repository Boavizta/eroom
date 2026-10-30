#!/usr/bin/env bash
#
# Compares the versioned snapshot of the EOF reference framework with EROOM's live
# Google Sheet, tab by tab.
#
# Why this script exists: the EOF reference framework our code reads
# (eof-reference.json) is built from an export of EROOM's
# Google Sheet. If EROOM modifies its Sheet, nothing alerts us. This script is the only
# way to know, and it is useful ONLY because the reference snapshot
# is versioned next to it: without a point of comparison, re-downloading learns nothing.
#
# Usage:
#   .claude/skills/eof/scripts/verify_source_sheet.sh            # compare
#   .claude/skills/eof/scripts/verify_source_sheet.sh --refresh # replaces the snapshot
#
# Exit codes:
#   0  the Sheet is identical to the snapshot, or refresh succeeded
#   1  at least one tab changed, or a download failed
#
# No dependency: curl and diff only. Touches no repository file
# except with --refresh, which only writes into docs/source-sheet/.

set -euo pipefail

SHEET_ID="1_fymJEyXxKjqy3jFlyO8MHhfmLZduUsLyloMeU2kSRM"
BASE="https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:json"

# Repository root, derived from this script's location, so it can be run
# from any directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REFERENCE_DIR="${SCRIPT_DIR}/../docs/source-sheet"

# One tab per line: "gid filename". The gids come from each
# tab's URL in the Google Sheets interface. Do not guess them.
ONGLETS="
1677462955 read-me.json
296916801  quick-diag.json
2022239731 product.json
615231881  architecture.json
1603246930 infrastructure.json
31675448   storage.json
1046049603 algo-code.json
24436077   ease.json
958616182  synthesis.json
"

REFRESH=0
if [ "${1:-}" = "--refresh" ]; then
  REFRESH=1
elif [ -n "${1:-}" ]; then
  echo "Unknown option: $1" >&2
  echo "Usage: $(basename "$0") [--refresh]" >&2
  exit 1
fi

if [ ! -d "$REFERENCE_DIR" ]; then
  echo "[FAILURE] the reference snapshot is missing: $REFERENCE_DIR" >&2
  exit 1
fi

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Source Sheet: https://docs.google.com/spreadsheets/d/${SHEET_ID}/edit"
echo "Snapshot    : ${REFERENCE_DIR}"
echo

nb_changed=0
nb_failures=0
nb_identical=0

while read -r gid file; do
  [ -z "${gid:-}" ] && continue

  target="${TEMP_DIR}/${file}"
  if ! curl -sfL -A "Mozilla/5.0" "${BASE}&gid=${gid}" -o "$target"; then
    echo "[NETWORK FAILURE] ${file} (gid ${gid}): download impossible"
    nb_failures=$((nb_failures + 1))
    continue
  fi

  # A Sheet that became private or a deleted gid returns HTML with a 200
  # code, not a network error. Check the gviz format signature, otherwise we
  # would compare an error page against the reference framework.
  if ! head -c 60 "$target" | grep -q 'google.visualization.Query.setResponse'; then
    echo "[INVALID RESPONSE] ${file} (gid ${gid}): this is not a gviz export."
    echo "                   Sheet became private, or tab deleted?"
    nb_failures=$((nb_failures + 1))
    continue
  fi

  reference="${REFERENCE_DIR}/${file}"
  if [ ! -f "$reference" ]; then
    echo "[NEW] ${file}: absent from the snapshot"
    nb_changed=$((nb_changed + 1))
  elif diff -q "$reference" "$target" >/dev/null; then
    nb_identical=$((nb_identical + 1))
  else
    echo "[CHANGED] ${file}"
    nb_changed=$((nb_changed + 1))
  fi

  if [ "$REFRESH" -eq 1 ]; then
    cp "$target" "${REFERENCE_DIR}/${file}"
  fi
done <<< "$ONGLETS"

echo
echo "${nb_identical} tab(s) identical, ${nb_changed} modified, ${nb_failures} failed."

if [ "$REFRESH" -eq 1 ]; then
  echo
  echo "Snapshot refreshed. To do now:"
  echo "  1. git diff .claude/skills/eof/docs/source-sheet/  to see exactly what EROOM changed"
  echo "  2. regenerate the reference framework, cf. step 2 of .claude/skills/eof/SKILL.md"
  echo "  3. re-run process/validate_key_consistency.py"
  exit 0
fi

if [ "$nb_failures" -gt 0 ] || [ "$nb_changed" -gt 0 ]; then
  if [ "$nb_changed" -gt 0 ]; then
    echo
    echo "EROOM's Sheet has evolved since the snapshot. To adopt it:"
    echo "  $(basename "$0") --refresh"
  fi
  exit 1
fi

echo "EROOM's Sheet has not moved. The reference framework is up to date."
exit 0
