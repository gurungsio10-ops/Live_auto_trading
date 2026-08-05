.PHONY: setup dev test lint typecheck paper-cycle down migrate frontend-dev frontend-build help

help:
	@echo "Project Atlas — paper trading MVP"
	@echo "  make setup         Install backend + frontend deps"
	@echo "  make migrate       alembic upgrade head"
	@echo "  make dev           Start FastAPI (paper mode)"
	@echo "  make frontend-dev  Start Next.js dashboard"
	@echo "  make test          Run pytest"
	@echo "  make lint          Ruff + frontend lint"
	@echo "  make typecheck     mypy + tsc"
	@echo "  make paper-cycle   One-shot paper cycle via API"
	@echo "  make down          Stop docker compose data plane"

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -U pip
	.venv/bin/pip install -e ".[dev]"
	npm --prefix frontend ci
	@test -f .env || cp .env.example .env
	@test -f frontend/.env.local || cp frontend/.env.example frontend/.env.local
	@echo "Setup complete. Activate with: source .venv/bin/activate"
	@echo "Keep TRADING_MODE=paper and TRADING_ENABLED=false."

migrate:
	.venv/bin/alembic upgrade head

dev:
	TRADING_MODE=paper TRADING_ENABLED=false ENABLE_LIVE_TRADING=false \
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	ADMIN_API_TOKEN=local-dev-admin-token \
	ATLAS_BACKEND_URL=http://127.0.0.1:8000 \
	ATLAS_AUTH_SECRET=atlas-dev-secret-change-me \
	npm --prefix frontend run dev -- --hostname 0.0.0.0 --port 3000

# Production-ish local stack (Postgres + API image)
docker compose up -d --build

test:
	pytest -q

lint:
	ruff check app tests
	ruff format --check app tests
	npm --prefix frontend run lint

typecheck:
	mypy app
	npm --prefix frontend run typecheck

frontend-build:
	npm --prefix frontend run build

paper-cycle:
	curl -s -X POST http://127.0.0.1:8000/api/trading/cycle \
	  -H 'Content-Type: application/json' \
	  -H "X-Admin-Token: $${ADMIN_API_TOKEN:-local-dev-admin-token}" \
	  -d '{"confirm":"RUN_ONE_CYCLE","symbol":"BTC/USDT","timeframe":"5m","strategy_id":"ema_crossover"}' \
	  | python -m json.tool

down:
	docker compose down || true
