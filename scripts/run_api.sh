#!/usr/bin/env bash
# Start FastAPI on 0.0.0.0:8000 using the project venv (Codespaces-safe).
# Paper mode only — never enables live trading.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -U pip
pip install -q -e ".[dev]"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "==> created .env from .env.example"
fi

export TRADING_MODE="${TRADING_MODE:-paper}"
export ATLAS_RUNTIME_MODE="${ATLAS_RUNTIME_MODE:-PAPER}"
export ENABLE_LIVE_TRADING="${ENABLE_LIVE_TRADING:-false}"
export LIVE_TRADING_ENABLED="${LIVE_TRADING_ENABLED:-false}"
export TRADING_ENABLED="${TRADING_ENABLED:-false}"
export ATLAS_AUTH_SECRET="${ATLAS_AUTH_SECRET:-atlas-dev-secret-change-me}"
export ATLAS_DASHBOARD_USER="${ATLAS_DASHBOARD_USER:-admin}"
export ATLAS_DASHBOARD_PASSWORD="${ATLAS_DASHBOARD_PASSWORD:-atlas}"
export ADMIN_API_TOKEN="${ADMIN_API_TOKEN:-local-dev-admin-token}"

# Smoke-parse settings before binding the port (fail fast on bad .env).
python - <<'PY'
from app.core.config import Settings
s = Settings()
print(f"settings_ok trading_mode={s.trading_mode} symbols={s.supported_symbols}")
assert s.trading_mode == "paper"
assert not s.live_trading_enabled
PY

alembic upgrade head

echo "==> starting uvicorn on 0.0.0.0:8000 (venv: $(which uvicorn))"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
