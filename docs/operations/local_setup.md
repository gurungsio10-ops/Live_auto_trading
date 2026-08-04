# Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp -n .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Expected:

- `GET http://127.0.0.1:8000/health` → `status: ok`, `trading_mode: paper`
- `GET http://127.0.0.1:8000/ready` → `status: ready` when DB is up and recon healthy
- Dashboard at `http://localhost:3000` (login `admin` / `atlas` by default)

Paper cycle (admin token required):

```bash
curl -X POST http://127.0.0.1:8000/api/trading/cycle \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Token: local-dev-admin-token' \
  -d '{"confirm":"RUN_ONE_CYCLE","symbol":"BTC/USDT","timeframe":"5m"}'
```
