#!/usr/bin/env bash
# Start Atlas paper development stack for GitHub Codespaces / local dual-service dev.
# Paper mode only — never enables live trading. Never prints secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUN_DIR="${ROOT}/.run"
LOG_DIR="${RUN_DIR}/logs"
BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_LOG="${LOG_DIR}/backend.log"
FRONTEND_LOG="${LOG_DIR}/frontend.log"
BACKEND_DEPS_STAMP="${RUN_DIR}/backend-deps.sha"
FRONTEND_DEPS_STAMP="${RUN_DIR}/frontend-deps.sha"

BACKEND_HOST="0.0.0.0"
BACKEND_PORT="8000"
FRONTEND_HOST="0.0.0.0"
FRONTEND_PORT="3000"
HEALTH_URL="http://127.0.0.1:${BACKEND_PORT}/health"
READY_URL="http://127.0.0.1:${BACKEND_PORT}/ready"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"

# Paper-only hard defaults (do not enable live trading).
export TRADING_MODE="${TRADING_MODE:-paper}"
export ATLAS_RUNTIME_MODE="${ATLAS_RUNTIME_MODE:-PAPER}"
export ENABLE_LIVE_TRADING="${ENABLE_LIVE_TRADING:-false}"
export LIVE_TRADING_ENABLED="${LIVE_TRADING_ENABLED:-false}"
export TRADING_ENABLED="${TRADING_ENABLED:-false}"
export KILL_SWITCH_ENABLED="${KILL_SWITCH_ENABLED:-false}"
export ENABLE_TRADING_SCHEDULER="${ENABLE_TRADING_SCHEDULER:-false}"
export USE_LIVE_MARKET_DATA="${USE_LIVE_MARKET_DATA:-false}"
export ATLAS_BACKEND_URL="${ATLAS_BACKEND_URL:-http://127.0.0.1:8000}"
export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}"

# Codespaces start always uses Compose Postgres/Redis on localhost.
# Do not inherit a stale shell DATABASE_URL (e.g. sqlite) from prior sessions.
# Override with ATLAS_CODESPACES_DATABASE_URL / ATLAS_CODESPACES_REDIS_URL if needed.
export DATABASE_URL="${ATLAS_CODESPACES_DATABASE_URL:-postgresql+asyncpg://atlas:atlas@127.0.0.1:5432/atlas}"
export REDIS_URL="${ATLAS_CODESPACES_REDIS_URL:-redis://127.0.0.1:6379/0}"

mkdir -p "$LOG_DIR"

log() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

sha_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

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
    # Fallback: try connecting.
    (echo >/dev/tcp/127.0.0.1/"${port}") >/dev/null 2>&1
  fi
}

wait_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-60}"
  local i
  for i in $(seq 1 "$attempts"); do
    if curl -sf --max-time 2 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "${label} did not become ready (${url}). See logs under .run/logs/"
}

wait_compose_healthy() {
  local service="$1"
  local attempts="${2:-60}"
  local i status
  for i in $(seq 1 "$attempts"); do
    status="$(docker compose ps --status running --format '{{.Service}} {{.Health}}' 2>/dev/null | awk -v s="$service" '$1==s {print $2; exit}')"
    if [[ "$status" == "healthy" ]]; then
      return 0
    fi
    # Some compose versions omit Health when healthy immediately after start.
    if docker compose exec -T "$service" true >/dev/null 2>&1; then
      case "$service" in
        postgres)
          if docker compose exec -T postgres pg_isready -U atlas -d atlas >/dev/null 2>&1; then
            return 0
          fi
          ;;
        redis)
          if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -qi pong; then
            return 0
          fi
          ;;
      esac
    fi
    sleep 1
  done
  die "Docker Compose service '${service}' did not become healthy"
}

ensure_backend_deps() {
  local need_install=0
  local current
  current="$(sha_file pyproject.toml)"
  if [[ ! -x .venv/bin/python ]]; then
    log "creating Python virtualenv (.venv)"
    python3 -m venv .venv
    need_install=1
  fi
  if [[ ! -f "$BACKEND_DEPS_STAMP" ]] || [[ "$(cat "$BACKEND_DEPS_STAMP")" != "$current" ]]; then
    need_install=1
  fi
  if [[ "$need_install" -eq 1 ]]; then
    log "installing backend dependencies (editable .[dev])"
    .venv/bin/python -m pip install -q -U pip
    .venv/bin/pip install -q -e ".[dev]"
    printf '%s\n' "$current" >"$BACKEND_DEPS_STAMP"
  else
    log "backend dependencies up to date"
  fi
}

ensure_frontend_deps() {
  local need_install=0
  local lock_src current
  if [[ -f frontend/package-lock.json ]]; then
    lock_src=frontend/package-lock.json
  else
    lock_src=frontend/package.json
  fi
  current="$(sha_file "$lock_src")"
  if [[ ! -d frontend/node_modules ]]; then
    need_install=1
  fi
  if [[ ! -f "$FRONTEND_DEPS_STAMP" ]] || [[ "$(cat "$FRONTEND_DEPS_STAMP")" != "$current" ]]; then
    need_install=1
  fi
  if [[ "$need_install" -eq 1 ]]; then
    log "installing frontend dependencies (npm ci)"
    npm --prefix frontend ci --no-fund --no-audit
    printf '%s\n' "$current" >"$FRONTEND_DEPS_STAMP"
  else
    log "frontend dependencies up to date"
  fi
}

start_backend() {
  local existing
  existing="$(read_pid "$BACKEND_PID_FILE")"
  if pid_alive "$existing"; then
    log "backend already running (pid ${existing}) — skipping"
    return 0
  fi
  if port_listening "$BACKEND_PORT"; then
    die "port ${BACKEND_PORT} is already in use by another process; stop it or run scripts/codespaces_stop.sh"
  fi
  rm -f "$BACKEND_PID_FILE"
  log "starting FastAPI on ${BACKEND_HOST}:${BACKEND_PORT} (paper mode)"
  (
    cd "$ROOT"
    # Force paper-safe env + Compose data-plane for the child process.
    export TRADING_MODE=paper
    export ATLAS_RUNTIME_MODE=PAPER
    export ENABLE_LIVE_TRADING=false
    export LIVE_TRADING_ENABLED=false
    export TRADING_ENABLED=false
    export DATABASE_URL
    export REDIS_URL
    # New session so stop can signal the process group safely.
    setsid nohup .venv/bin/python -m uvicorn app.main:app \
      --host "$BACKEND_HOST" \
      --port "$BACKEND_PORT" \
      --reload \
      >>"$BACKEND_LOG" 2>&1 &
    echo $! >"$BACKEND_PID_FILE"
  )
}

start_frontend() {
  local existing
  existing="$(read_pid "$FRONTEND_PID_FILE")"
  if pid_alive "$existing"; then
    log "frontend already running (pid ${existing}) — skipping"
    return 0
  fi
  if port_listening "$FRONTEND_PORT"; then
    die "port ${FRONTEND_PORT} is already in use by another process; stop it or run scripts/codespaces_stop.sh"
  fi
  rm -f "$FRONTEND_PID_FILE"
  log "starting Next.js on ${FRONTEND_HOST}:${FRONTEND_PORT}"
  (
    cd "$ROOT/frontend"
    setsid nohup npm run dev -- --hostname "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
      >>"$FRONTEND_LOG" 2>&1 &
    echo $! >"$FRONTEND_PID_FILE"
  )
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

require_cmd docker
require_cmd curl
require_cmd python3
require_cmd npm
docker info >/dev/null 2>&1 || die "Docker daemon is not running"

log "starting PostgreSQL and Redis (Docker Compose; volumes preserved)"
docker compose up -d postgres redis
wait_compose_healthy postgres 90
wait_compose_healthy redis 90
log "PostgreSQL healthy; Redis healthy"

if [[ ! -f .env ]]; then
  cp .env.example .env
  # Point a fresh .env at Compose data-plane (no secrets printed).
  if grep -q '^DATABASE_URL=' .env; then
    sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://atlas:atlas@127.0.0.1:5432/atlas|' .env
  else
    printf '\nDATABASE_URL=postgresql+asyncpg://atlas:atlas@127.0.0.1:5432/atlas\n' >>.env
  fi
  if grep -q '^REDIS_URL=' .env; then
    sed -i 's|^REDIS_URL=.*|REDIS_URL=redis://127.0.0.1:6379/0|' .env
  else
    printf 'REDIS_URL=redis://127.0.0.1:6379/0\n' >>.env
  fi
  log "created .env from .env.example (Compose Postgres/Redis)"
else
  log ".env already present — leaving file unchanged (runtime uses Compose URLs)"
fi

if [[ ! -f frontend/.env.local ]]; then
  if [[ -f frontend/.env.example ]]; then
    cp frontend/.env.example frontend/.env.local
  else
    cat >frontend/.env.local <<'EOF'
ATLAS_BACKEND_URL=http://127.0.0.1:8000
ATLAS_DASHBOARD_USER=admin
ATLAS_DASHBOARD_PASSWORD=atlas
ATLAS_AUTH_SECRET=atlas-dev-secret-change-me
ADMIN_API_TOKEN=local-dev-admin-token
APP_ENV=development
EOF
  fi
  log "created frontend/.env.local from example"
else
  log "frontend/.env.local already present — leaving unchanged"
fi

ensure_backend_deps
ensure_frontend_deps

log "running database migrations (alembic upgrade head)"
.venv/bin/alembic upgrade head

# Fail fast if settings are misconfigured (paper-only assertion).
.venv/bin/python - <<'PY'
from app.core.config import get_settings
s = get_settings()
assert str(s.trading_mode).lower() == "paper", "trading_mode must remain paper"
assert not bool(s.live_trading_enabled), "live trading must stay disabled"
print("settings_ok paper_mode=true live_trading=false")
PY

start_backend
wait_http "$HEALTH_URL" "backend /health" 90
wait_http "$READY_URL" "backend /ready" 30
log "backend health OK"

start_frontend
wait_http "$FRONTEND_URL" "frontend" 120
log "frontend reachable"

BACKEND_PID="$(read_pid "$BACKEND_PID_FILE" || true)"
FRONTEND_PID="$(read_pid "$FRONTEND_PID_FILE" || true)"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

cat <<EOF

Atlas paper stack is up.

  Mode:       paper (live trading hard-blocked)
  Branch:     ${BRANCH}
  PostgreSQL: localhost:5432 (compose service: postgres)
  Redis:      localhost:6379 (compose service: redis)
  Backend:    http://127.0.0.1:${BACKEND_PORT}  (pid ${BACKEND_PID:-n/a})
  Frontend:   http://127.0.0.1:${FRONTEND_PORT}  (pid ${FRONTEND_PID:-n/a})
  Health:     ${HEALTH_URL}

  Codespaces: open the forwarded URL for port ${FRONTEND_PORT}.
  Logs:       .run/logs/backend.log  .run/logs/frontend.log
  Status:     ./scripts/codespaces_status.sh
  Stop:       ./scripts/codespaces_stop.sh

  Dev login credentials are documented in docs/operations/codespaces.md
  (not printed here).

EOF
