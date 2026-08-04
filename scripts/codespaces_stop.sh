#!/usr/bin/env bash
# Stop Atlas Codespaces/dev processes started by codespaces_start.sh.
# Does not delete Docker volumes or databases.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="${ROOT}/.run"
BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"

log() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }

pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  local file="$1"
  if [[ -f "$file" ]]; then
    tr -d '[:space:]' <"$file"
  fi
}

stop_pid_tree() {
  local label="$1"
  local pid_file="$2"
  local pid
  pid="$(read_pid "$pid_file" || true)"
  if [[ -z "${pid:-}" ]]; then
    log "${label}: no PID file"
    rm -f "$pid_file"
    return 0
  fi
  if ! pid_alive "$pid"; then
    log "${label}: stale PID ${pid} — removing"
    rm -f "$pid_file"
    return 0
  fi

  log "${label}: stopping pid ${pid}"
  # Prefer process-group signal when start used setsid; fall back to PID.
  if kill -TERM -- "-${pid}" 2>/dev/null; then
    :
  else
    kill -TERM "$pid" 2>/dev/null || true
  fi

  local i
  for i in $(seq 1 20); do
    if ! pid_alive "$pid"; then
      break
    fi
    sleep 0.25
  done

  if pid_alive "$pid"; then
    warn "${label}: still running — sending KILL"
    kill -KILL -- "-${pid}" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  fi

  rm -f "$pid_file"
  log "${label}: stopped"
}

# Prefer PID-file shutdown; also clear common orphans from older scripts.
stop_pid_tree "frontend" "$FRONTEND_PID_FILE"
stop_pid_tree "backend" "$BACKEND_PID_FILE"

# Best-effort cleanup of known Atlas app listeners if PID files were lost.
if command -v pgrep >/dev/null 2>&1; then
  while read -r pid; do
    [[ -n "$pid" ]] || continue
    # Only match workspace uvicorn/next to avoid killing unrelated tools.
    if tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null | grep -Eq 'uvicorn app\.main:app|next dev .*--port 3000'; then
      log "stopping orphan pid ${pid}"
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done < <(pgrep -f 'uvicorn app\.main:app|next dev' 2>/dev/null || true)
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  log "stopping Docker Compose services (volumes preserved)"
  # Prefer stopping data-plane services used by Codespaces start.
  docker compose stop postgres redis >/dev/null 2>&1 || docker compose stop >/dev/null 2>&1 || true
else
  warn "Docker unavailable — skipped compose stop"
fi

# Remove any remaining stale PID files under .run/
rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"

log "Atlas Codespaces stack stopped (databases/volumes not deleted)"
