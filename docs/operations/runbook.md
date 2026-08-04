# Operations runbook (paper)

**Superseded by the expanded runbook:** [`docs/operations/RUNBOOK.md`](./RUNBOOK.md)

This file is kept as a short pointer so older links keep working.

## Quick start

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
cd frontend && npm ci
ADMIN_API_TOKEN=local-dev-admin-token ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Docker data plane (optional; `docker` may be absent in some VMs):

```bash
docker compose up -d   # postgres + redis
```

See `RUNBOOK.md` for paper cycle, kill switch, health/ready, admin token, and troubleshooting.
