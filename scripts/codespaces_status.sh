#!/usr/bin/env bash
# Display Atlas Codespaces/dev stack status (no secrets).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="${ROOT}/.run"
BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_PORT=8000
FRONTEND_PORT=3000

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

port_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :${port} )" 2>/dev/null | grep -q ":${port}"
  elif command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
  else
    (echo >/dev/tcp/127.0.0.1/"${port}") >/dev/null 2>&1
  fi
}

compose_service_status() {
  local service="$1"
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo "docker unavailable"
    return
  fi
  local line health state
  line="$(docker compose ps --format '{{.Service}} {{.State}} {{.Health}}' 2>/dev/null | awk -v s="$service" '$1==s {print; exit}')"
  if [[ -z "$line" ]]; then
    echo "not running"
    return
  fi
  state="$(awk '{print $2}' <<<"$line")"
  health="$(awk '{print $3}' <<<"$line")"
  if [[ -n "$health" && "$health" != "-" ]]; then
    echo "${state} (${health})"
  else
    echo "${state}"
  fi
}

proc_status() {
  local label="$1"
  local pid_file="$2"
  local port="$3"
  local pid
  pid="$(read_pid "$pid_file" || true)"
  if pid_alive "$pid"; then
    echo "running (pid ${pid}, port ${port})"
  elif [[ -n "${pid:-}" ]]; then
    echo "stale pid ${pid} (port $(port_listening "$port" && echo up || echo down))"
  elif port_listening "$port"; then
    echo "port ${port} listening (no PID file)"
  else
    echo "stopped"
  fi
}

backend_health() {
  if curl -sf --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
    local body
    body="$(curl -sf --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || true)"
    # Print only non-secret health summary fields when jq is available.
    if command -v jq >/dev/null 2>&1 && [[ -n "$body" ]]; then
      printf 'ok (%s)\n' "$(jq -c '{status,trading_mode,live_trading_enabled,database:(.database.ok // null)}' <<<"$body" 2>/dev/null || echo ok)"
    else
      echo "ok"
    fi
  else
    echo "unreachable"
  fi
}

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

echo "Atlas Codespaces status"
echo "-----------------------"
echo "Git branch:     ${BRANCH}"
echo "PostgreSQL:     $(compose_service_status postgres)"
echo "Redis:          $(compose_service_status redis)"
echo "Backend:        $(proc_status backend "$BACKEND_PID_FILE" "$BACKEND_PORT")"
echo "Frontend:       $(proc_status frontend "$FRONTEND_PID_FILE" "$FRONTEND_PORT")"
echo "Backend health: $(backend_health)"
echo "Port ${BACKEND_PORT}:       $(port_listening "$BACKEND_PORT" && echo listening || echo closed)"
echo "Port ${FRONTEND_PORT}:       $(port_listening "$FRONTEND_PORT" && echo listening || echo closed)"
echo "Logs:           .run/logs/backend.log  .run/logs/frontend.log"
