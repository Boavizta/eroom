#!/usr/bin/env bash
# Generates cwv.json from the Lighthouse CLI for an audit folder.
# Usage: run_lighthouse.sh <audit-dir> [url-page1 url-page2 ...]
#   Without URLs: automatically extracts all unique URLs from the .har in <audit-dir>.
# Output: <audit-dir>/cwv.json (format expected by generate_report_html.py)
#
# Prerequisite: Node.js installed.
# Prefers the local install (node_modules/.bin/lighthouse).
# Otherwise falls back to npx (unpinned version).
# To pin the version: npm install --prefix <scripts-dir>/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_BIN="${SCRIPT_DIR}/node_modules/.bin/lighthouse"

AUDIT_DIR="${1:?Usage: $0 <audit-dir> [url-page1 url-page2 ...]}"
shift
URLS=("$@")

# Auto-extract URLs from the HAR if none provided
if [[ ${#URLS[@]} -eq 0 ]]; then
    HAR_FILE=$(find "$AUDIT_DIR" -maxdepth 1 -name "*.har" | head -1)
    if [[ -z "$HAR_FILE" ]]; then
        HAR_FILE=$(find "$AUDIT_DIR/.." -maxdepth 1 -name "*.har" | head -1)
    fi
    if [[ -z "$HAR_FILE" ]]; then
        echo "Error: no .har file in $AUDIT_DIR nor in $(dirname "$AUDIT_DIR") and no URL provided." >&2
        exit 1
    fi
    echo "[ Lighthouse ] Automatic URL extraction from $(basename "$HAR_FILE")..."
    mapfile -t URLS < <(python3 - "$HAR_FILE" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    har = json.load(f)
seen = {}
for p in har["log"]["pages"]:
    url = p["title"].rstrip("/")
    if url and url not in seen:
        seen[url] = True
        print(url)
PYEOF
)
    if [[ ${#URLS[@]} -eq 0 ]]; then
        echo "Error: no URL extracted from the HAR." >&2
        exit 1
    fi
    echo "[ Lighthouse ] ${#URLS[@]} URL(s) extracted from the HAR."
fi

# Select the Lighthouse binary
if [[ -x "$LOCAL_BIN" ]]; then
    LH_VERSION=$("$LOCAL_BIN" --version 2>/dev/null || echo "?")
    echo "[ Lighthouse ] version ${LH_VERSION} (local install)"
    LH_CMD="$LOCAL_BIN"
elif command -v npx >/dev/null 2>&1; then
    echo "[ Lighthouse ] local install missing - using npx (unpinned version)"
    echo "  To pin the version: npm install --prefix ${SCRIPT_DIR}"
    LH_CMD="npx --yes lighthouse@latest"
else
    echo "Error: neither local install nor npx available." >&2
    echo "  Install Node.js: https://nodejs.org" >&2
    exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "[ Lighthouse ] $((${#URLS[@]})) page(s) to analyze..."

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
        echo "     Warning: Lighthouse failed for ${URL}, page skipped." >&2
        continue
    }

    # Extract LCP, INP, CLS from the Lighthouse JSON
    # largest-contentful-paint: numericValue in ms -> convert to s
    # interaction-to-next-paint (Lighthouse 11+): numericValue in ms
    # cumulative-layout-shift: numericValue (decimal score)
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
    echo "Error: no page analyzed successfully." >&2
    exit 1
fi

CWV_PATH="${AUDIT_DIR}/cwv.json"
printf "[\n%s\n]\n" "$JSON_ENTRIES" > "$CWV_PATH"

echo "[ Lighthouse ] cwv.json written: ${CWV_PATH}"
