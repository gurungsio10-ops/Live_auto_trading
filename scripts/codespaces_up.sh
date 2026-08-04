#!/usr/bin/env bash
# Start Atlas paper stack for GitHub Codespaces / local dual-service dev.
# Paper mode only — never enables live trading.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export TRADING_MODE="${TRADING_MODE:-paper}"
export ATLAS_RUNTIME_MODE="${ATLAS_RUNTIME_MODE:-PAPER}"
export ENABLE_LIVE_TRADING="${ENABLE_LIVE_TRADING:-false}"
export LIVE_TRADING_ENABLED="${LIVE_TRADING_ENABLED:-false}"
export TRADING_ENABLED="${TRADING_ENABLED:-false}"
export KILL_SWITCH_ENABLED="${KILL_SWITCH_ENABLED:-false}"
export ATLAS_AUTH_SECRET="${ATLAS_AUTH_SECRET:-atlas-dev-secret-change-me}"
export ATLAS_DASHBOARD_USER="${ATLAS_DASHBOARD_USER:-admin}"
export ATLAS_DASHBOARD_PASSWORD="${ATLAS_DASHBOARD_PASSWORD:-atlas}"
export ADMIN_API_TOKEN="${ADMIN_API_TOKEN:-local-dev-admin-token}"
export ATLAS_BACKEND_URL="${ATLAS_BACKEND_URL:-http://127.0.0.1:8000}"
export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000}"

# Prefer Postgres when available (Codespaces often has it); else SQLite file.
if [[ -z "${DATABASE_URL:-}" ]]; then
  if PGPASSWORD="${POSTGRES_PASSWORD:-atlas}" psql -h 127.0.0.1 -U "${POSTGRES_USER:-atlas}" -d postgres -c 'SELECT 1' >/dev/null 2>&1; then
    PGPASSWORD="${POSTGRES_PASSWORD:-atlas}" psql -h 127.0.0.1 -U "${POSTGRES_USER:-atlas}" -d postgres -tc \
      "SELECT 1 FROM pg_database WHERE datname='atlas'" | grep -q 1 || \
      PGPASSWORD="${POSTGRES_PASSWORD:-atlas}" psql -h 127.0.0.1 -U "${POSTGRES_USER:-atlas}" -d postgres -c 'CREATE DATABASE atlas'
    export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER:-atlas}:${POSTGRES_PASSWORD:-atlas}@127.0.0.1:5432/atlas"
  else
    export DATABASE_URL="sqlite+aiosqlite:///./atlas.db"
  fi
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -U pip
pip install -q -e ".[dev]"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "==> DATABASE_URL=${DATABASE_URL}"
# Fail fast if .env cannot be parsed (e.g. historical ALLOWED_SYMBOLS JSON issues).
python - <<'PY'
from app.core.config import Settings
s = Settings()
print("settings_ok", s.trading_mode, s.supported_symbols)
PY
alembic upgrade head

mkdir -p frontend
if [[ ! -f frontend/.env.local ]]; then
  cat > frontend/.env.local <<EOF
ATLAS_BACKEND_URL=http://127.0.0.1:8000
ATLAS_AUTH_SECRET=${ATLAS_AUTH_SECRET}
ATLAS_DASHBOARD_USER=${ATLAS_DASHBOARD_USER}
ATLAS_DASHBOARD_PASSWORD=${ATLAS_DASHBOARD_PASSWORD}
ADMIN_API_TOKEN=${ADMIN_API_TOKEN}
APP_ENV=development
EOF
  echo "==> wrote frontend/.env.local"
fi

npm --prefix frontend ci >/dev/null

echo "==> starting FastAPI on 0.0.0.0:8000 via .venv"
pkill -f 'uvicorn app.main:app' >/dev/null 2>&1 || true
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/atlas-api.log 2>&1 &
sleep 2
curl -sf "http://127.0.0.1:8000/health" >/dev/null
curl -sf "http://127.0.0.1:8000/ready" >/dev/null
curl -sf -X POST "http://127.0.0.1:8000/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${ATLAS_DASHBOARD_USER}\",\"password\":\"${ATLAS_DASHBOARD_PASSWORD}\"}" >/dev/null
echo "==> backend health/ready/login OK"

echo "==> starting Next.js on 0.0.0.0:3000"
pkill -f 'next dev' >/dev/null 2>&1 || true
(
  cd frontend
  nohup npm run dev -- --hostname 0.0.0.0 --port 3000 > /tmp/atlas-frontend.log 2>&1 &
)
sleep 3
curl -sf -X POST "http://127.0.0.1:3000/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${ATLAS_DASHBOARD_USER}\",\"password\":\"${ATLAS_DASHBOARD_PASSWORD}\"}" >/dev/null
echo "==> frontend BFF login OK"

echo
echo "Open the forwarded Codespaces URL for port 3000 (HTTPS)."
echo "Dev credentials: ${ATLAS_DASHBOARD_USER} / ${ATLAS_DASHBOARD_PASSWORD}"
echo "Logs: /tmp/atlas-api.log  /tmp/atlas-frontend.log"
echo "Paper mode only — live trading remains hard-blocked."
