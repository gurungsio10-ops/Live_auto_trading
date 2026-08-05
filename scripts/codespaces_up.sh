#!/usr/bin/env bash
# Back-compat wrapper — prefer scripts/codespaces_start.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${ROOT}/scripts/codespaces_start.sh" "$@"
