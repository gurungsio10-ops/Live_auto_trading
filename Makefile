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
	python -m pip install -e ".[dev]"
	npm --prefix frontend ci
	@test -f .env || cp .env.example .env
	@echo "Setup complete. Keep TRADING_MODE=paper and TRADING_ENABLED=false."

migrate:
	alembic upgrade head

dev:
	TRADING_MODE=paper TRADING_ENABLED=false ENABLE_LIVE_TRADING=false \
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	ADMIN_API_TOKEN=$${ADMIN_API_TOKEN:-local-dev-admin-token} \
	ATLAS_BACKEND_URL=http://127.0.0.1:8000 \
	npm --prefix frontend run dev

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
