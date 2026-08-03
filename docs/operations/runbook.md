# Operations runbook (paper)

## Start locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# ensure TRADING_MODE=paper and ADMIN_API_TOKEN set
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend && npm install
ADMIN_API_TOKEN=local-dev-admin-token ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Docker data plane:

```bash
docker compose up -d   # postgres + redis
```

## Run one paper cycle

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/paper/cycle/run \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTC/USDT","timeframe":"1m"}'
```

CLI offline:

```bash
python -m app.cli paper-run --offline
```

## Kill switch

```bash
curl -X POST http://127.0.0.1:8000/api/v1/system/kill-switch/activate \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"reason":"ops halt"}'
```

## Paper reset

```bash
curl -X POST http://127.0.0.1:8000/api/v1/paper/reset \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"confirm":"RESET_PAPER_ACCOUNT"}'
```

## Health

- `GET /health`, `GET /ready`
- `GET /api/v1/health`, `GET /api/v1/ready`, `GET /api/v1/system/status`

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 503 on kill-switch/reset | `ADMIN_API_TOKEN` unset |
| Binance HTTP 451 | Geo-block; use `--offline` or another public venue |
| Demo banner in UI | Backend unreachable from Next.js (`ATLAS_BACKEND_URL`) |
| Live mode startup failure | Expected — keep `TRADING_MODE=paper` |
