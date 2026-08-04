# Project Atlas

Safe, deterministic, personal cryptocurrency **paper** trading platform.

**Paper trading is supported. Live money remains disabled.**  
AI is advisory only. Every order passes through one central risk engine (`app/risk/engine.py` via `OrderGateway`).

Banner: **PAPER TRADING — NO REAL FUNDS**

## What works today

- Deterministic paper cycles (offline fixtures by default)
- Durable paper account / risk / strategy persistence (Alembic **`0006_paper_durable`**)
- Restart-safe hydration + fail-closed reconciliation
- Kill switch, cycle locks, processed-cycle idempotency
- Equity snapshots, journal dual-write, maker/taker fee + stop/TP paper realism
- Ops dashboard + **Recovery** panel (`/recovery`)
- PostgreSQL soak harness (`python -m app.cli paper-soak`)
- 265 automated tests; application coverage gate **≥85%**

## Architecture

```text
Market data → candle validation → strategy → signal → OrderGateway → RiskEngine
  → paper engine → PaperSession + journal + dual-write persistence
  → /api/v1 + dashboard (+ /recovery)
```

Authoritative consolidation audit: `docs/audits/consolidation_audit.md`  
Security audit: `docs/audits/security_audit.md`  
Merge plan: `docs/audit/release_merge_plan.md`  
Verification: `docs/audit/paper_v1_final_verification.md`  
Release notes: `docs/releases/consolidation_release.md`

## Migrations

| Revision | Contents |
|----------|----------|
| `0001_phase2` | symbols, candles |
| `0002_phase9` | journal tables |
| `0003_users` | users |
| `0004_paper_slice` | balances, positions, snapshots, system_state, … |
| `0005_cycle_ops` | cycle_locks, scheduler_runs, reconciliation_reports |
| `0006_paper_durable` | paper_accounts, risk_state, strategy_state, processed_cycle_keys, equity_snapshots, kill_switch_events |

```bash
alembic upgrade head
```

## Persistence model

`PaperSession` is process-local for latency but **hydrated from DB on startup** and dual-written after cycles / control-plane mutations. Startup reconciliation is fail-closed: untrusted durable state pauses trading. See `docs/operations/recovery_runbook.md`.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Keep TRADING_MODE=paper, ENABLE_LIVE_TRADING=false
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### PostgreSQL (recommended durable path)

```bash
docker compose up -d          # Postgres + Redis
# set DATABASE_URL=postgresql+asyncpg://... in .env
alembic upgrade head
```

### Dashboard

```bash
cd frontend && npm ci
ADMIN_API_TOKEN=local-dev-admin-token ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000 — login `admin` / `atlas` (dev defaults). Recovery panel: `/recovery`.

`ADMIN_API_TOKEN` is used only in Next.js **server** BFF routes — never expose it to browser JS.

## GitHub Codespaces

Codespaces **auto-starts** the paper stack on container start via `.devcontainer/postStartCommand` (PostgreSQL + Redis + FastAPI `:8000` + Next.js `:3000`). Startup runs in the background so the editor is not blocked; track it with `tail -f .run/logs/poststart.log`.

Codespaces **stop when idle** and are **not** 24/7 hosting — restart the Codespace (or run the start script) after it sleeps.

| Action | Command |
|--------|---------|
| Manual start | `./scripts/codespaces_start.sh` |
| Status | `./scripts/codespaces_status.sh` |
| Stop | `./scripts/codespaces_stop.sh` |
| Restart | `./scripts/codespaces_restart.sh` |

Open the forwarded **port 3000** URL (`Ports` panel → 3000 → Open in Browser). Login defaults are in `docs/operations/codespaces.md`.

Troubleshoot with logs under `.run/logs/` (`backend.log`, `frontend.log`, `poststart.log`). Full runbook: `docs/operations/codespaces.md`.

## Run one paper cycle

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/paper/cycle/run \
  -H 'Content-Type: application/json' \
  -H "X-Admin-Token: ${ADMIN_API_TOKEN}" \
  -d '{"confirm":"RUN_ONE_CYCLE","symbol":"BTC/USDT","timeframe":"1m"}'
```

Or: `make paper-cycle` / dashboard “Run one paper cycle”.

## Soak test (no exchange credentials)

```bash
python -m app.cli paper-soak \
  --duration-hours 24 \
  --symbols BTC/USDT,ETH/USDT \
  --restart-interval-minutes 30 \
  --seed 42
# CI shortcut:
python -m app.cli paper-soak --duration-hours 0.01 --seed 42 --max-cycles 6
```

Artifacts: `artifacts/soak/summary.json`, `events.jsonl`, `equity.csv`, `reconciliation.json`, `invariants.json`.

## Recover from a reconciliation halt

1. Inspect `GET /api/v1/recovery/status` or dashboard `/recovery`
2. Fix root cause (do not invent balances)
3. `POST /api/v1/reconciliation/run` (admin) until healthy
4. `POST /api/v1/reconciliation/clear-halt` with admin token + confirmation  
   Dashboard clear-halt requires confirm `CLEAR_RECONCILIATION_HALT`

Details: `docs/operations/recovery_runbook.md`.

## Quality gates

```bash
pytest -q
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
ruff check app tests && ruff format --check app tests
mypy app
alembic upgrade head
npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run build
docker compose config
```

## Safety

| Control | Default |
|---------|---------|
| `TRADING_MODE` | `paper` |
| `TRADING_ENABLED` | `false` |
| `ENABLE_LIVE_TRADING` | `false` |
| Futures / leverage / withdrawals | blocked by `SafetyGuard` |
| Live order submission | hard-blocked |
| AI order execution | not available (advisory only) |

## Current limitations

- Live money trading is **not** implemented and must stay disabled
- Futures, leverage >1x, withdrawals unavailable
- Scheduler off by default (`ENABLE_TRADING_SCHEDULER=false`)
- Redis optional (not required at startup)
- Public market data optional; offline fixtures are the default paper path
- Live readiness checklist: `docs/operations/live_trading_readiness_checklist.md` (all items unchecked)

## Verified test counts

Local verification on the release branch: **265 passed**, coverage **≥85%**. Re-run CI on the PR for the authoritative green check.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `401` on cycle/kill-switch | Set `ADMIN_API_TOKEN` and send `X-Admin-Token` |
| Yellow “Demo data” banner | Backend unreachable — start uvicorn |
| `409 TRADING_ENABLED is false` | Pass `confirm=RUN_ONE_CYCLE` or start paper trading |
| LIVE startup error | Keep `TRADING_MODE=paper` |
| Trading blocked after restart | Check `/recovery` for recon halt / kill switch / DB unhealthy |
