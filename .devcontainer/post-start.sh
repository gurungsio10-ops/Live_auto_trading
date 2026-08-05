#!/usr/bin/env bash
# Codespaces postStart hook — launch Atlas stack without blocking the IDE.
# Long-running services are backgrounded by scripts/codespaces_start.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p .run/logs

# Do not block Codespace startup indefinitely. Launch start in the background
# so the editor becomes usable while deps/services come up.
nohup ./scripts/codespaces_start.sh >>.run/logs/poststart.log 2>&1 &
echo $! >.run/poststart.pid

printf 'Atlas auto-start launched in background (pid %s).\n' "$(tr -d '[:space:]' <.run/poststart.pid)"
printf 'Track progress: tail -f .run/logs/poststart.log\n'
printf 'Status:         ./scripts/codespaces_status.sh\n'
