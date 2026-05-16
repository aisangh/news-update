#!/usr/bin/env bash
# AI News Agent — pass number of days as first argument (default: 7)
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
DAYS="${1:-7}"
NODE="${NODE:-node}"
if ! command -v node >/dev/null 2>&1; then
  NODE="/Applications/Cursor.app/Contents/Resources/app/resources/helpers/node"
fi
exec "$NODE" "$DIR/agent.mjs" --days "$DAYS" "${@:2}"
# Auto-saves to reports/latest-Ndays.txt unless --no-save is passed
