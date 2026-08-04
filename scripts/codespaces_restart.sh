#!/usr/bin/env bash
# Restart Atlas Codespaces/dev stack (stop then start).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

"${ROOT}/scripts/codespaces_stop.sh"
"${ROOT}/scripts/codespaces_start.sh"
