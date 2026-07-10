#!/usr/bin/env bash
# Génère cwv.json depuis Lighthouse CLI pour un dossier d'audit.
# Usage : run_lighthouse.sh <dossier-audit> <url-page1> [url-page2 ...]
# Sortie : <dossier-audit>/cwv.json (format attendu par generate_report_html.py)
#
# Prérequis : Node.js installé.
# Utilise en priorité l'install locale (node_modules/.bin/lighthouse).
# Sinon bascule sur npx (version non fixée).
# Pour fixer la version : npm install --prefix <dossier-scripts>/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_BIN="${SCRIPT_DIR}/node_modules/.bin/lighthouse"

AUDIT_DIR="${1:?Usage: $0 <dossier-audit> <url-page1> [url-page2 ...]}"
shift
URLS=("$@")

if [[ ${#URLS[@]} -eq 0 ]]; then
    echo "Erreur : au moins une URL requise." >&2
    exit 1
fi

# Sélection du binaire Lighthouse
if [[ -x "$LOCAL_BIN" ]]; then
    LH_VERSION=$("$LOCAL_BIN" --version 2>/dev/null || echo "?")
    echo "[ Lighthouse ] version ${LH_VERSION} (install locale)"
    LH_CMD="$LOCAL_BIN"
elif command -v npx >/dev/null 2>&1; then
    echo "[ Lighthouse ] install locale absente - utilisation de npx (version non fixée)"
    echo "  Pour fixer la version : npm install --prefix ${SCRIPT_DIR}"
    LH_CMD="npx --yes lighthouse@latest"
else
    echo "Erreur : ni install locale ni npx disponibles." >&2
    echo "  Installe Node.js : https://nodejs.org" >&2
    exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "[ Lighthouse ] $((${#URLS[@]})) page(s) à analyser..."

JSON_ENTRIES=""
PAGE_NUM=0

for URL in "${URLS[@]}"; do
    PAGE_NUM=$((PAGE_NUM + 1))
    PAGE_ID="page_${PAGE_NUM}"
    LH_OUT="${TMP_DIR}/lh_${PAGE_NUM}.json"

    echo "  -> page_${PAGE_NUM} : ${URL}"

    $LH_CMD \
        "$URL" \
        --output json \
        --output-path "$LH_OUT" \
        --chrome-flags="--headless --no-sandbox --disable-dev-shm-usage" \
        --only-categories=performance \
        --quiet 2>/dev/null || {
        echo "     Avertissement : Lighthouse a échoué pour ${URL}, page ignorée." >&2
        continue
    }

    # Extraire LCP, INP, CLS depuis le JSON Lighthouse
    # largest-contentful-paint : numericValue en ms -> convertir en s
    # interaction-to-next-paint (Lighthouse 11+) : numericValue en ms
    # cumulative-layout-shift : numericValue (score décimal)
    LCP=$(python3 - "$LH_OUT" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
audits = d.get("audits", {})
lcp_ms = audits.get("largest-contentful-paint", {}).get("numericValue")
print(round(lcp_ms / 1000, 2) if lcp_ms is not None else "null")
PYEOF
)

    INP=$(python3 - "$LH_OUT" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
audits = d.get("audits", {})
inp_ms = audits.get("interaction-to-next-paint", {}).get("numericValue")
if inp_ms is None:
    inp_ms = audits.get("max-potential-fid", {}).get("numericValue")
print(round(inp_ms) if inp_ms is not None else "null")
PYEOF
)

    CLS=$(python3 - "$LH_OUT" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
audits = d.get("audits", {})
cls = audits.get("cumulative-layout-shift", {}).get("numericValue")
print(round(cls, 3) if cls is not None else "null")
PYEOF
)

    ENTRY="{\"page\": \"${PAGE_ID}\", \"lcp\": ${LCP}, \"inp\": ${INP}, \"cls\": ${CLS}, \"source\": \"lighthouse\", \"url\": \"${URL}\"}"

    if [[ -n "$JSON_ENTRIES" ]]; then
        JSON_ENTRIES="${JSON_ENTRIES},
  ${ENTRY}"
    else
        JSON_ENTRIES="  ${ENTRY}"
    fi
done

if [[ -z "$JSON_ENTRIES" ]]; then
    echo "Erreur : aucune page analysée avec succès." >&2
    exit 1
fi

CWV_PATH="${AUDIT_DIR}/cwv.json"
printf "[\n%s\n]\n" "$JSON_ENTRIES" > "$CWV_PATH"

echo "[ Lighthouse ] cwv.json écrit : ${CWV_PATH}"
