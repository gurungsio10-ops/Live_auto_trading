# Project Atlas

Safe, deterministic, personal cryptocurrency **paper** trading platform.

**Paper trading is supported. Live money remains disabled.**  
AI is advisory only. Every order passes through one central risk engine (`app/risk/engine.py` via `OrderGateway`).

Banner: **PAPER TRADING — NO REAL FUNDS**

## Authoritative release branch

**`release/atlas-paper-v1`** (PR **#34**) consolidates the verified paper lineage (#21–#28) plus PR **#35** performance analytics. Target tag: **`v1.0.0-paper`**.

| Doc | Purpose |
|-----|---------|
| `docs/release/PAPER_V1_PR_AUDIT.md` | Evidence-based open PR decisions (SHA / merge-base) |
| `docs/release/PAPER_V1_ACCEPTANCE_REPORT.md` | Deterministic acceptance evidence |
| `docs/PR_CONSOLIDATION_AUDIT.md` | Earlier consolidation map |
| `docs/RELEASE_READINESS_REPORT.md` | Completion % / blockers |
| `docs/MOBILE_UI_AUDIT.md` | Viewport evidence 320–1440 + mobile IA |
| `docs/operations/DEPLOYMENT_RUNBOOK.md` | Paper deploy bring-up |
| `docs/operations/BACKUP_RESTORE.md` | Backup / restore |
| `docs/operations/INCIDENT_RESPONSE.md` | Kill switch / secrets / recon incidents |

## What works today

- Deterministic paper cycles (offline fixtures by default; public Bybit MD optional)
- Strategies: **EMA crossover**, **EMA + RSI**, **RSI mean reversion**, **Donchian breakout**
- Durable paper account / risk / strategy persistence (Alembic through **`0007_perf_analytics`**)
- Persistent closed-trade journal + performance metrics / reports / CSV+JSON export
- Restart-safe hydration + fail-closed reconciliation
- Continuous scheduler with explicit start/stop; kill switch; cycle locks; idempotency
- Next-bar SL/TP evaluation on the paper path; backtests; journal / audit trail
- Admin authentication for mutating operations; fail-closed Next.js BFF proxies
- Health, readiness, metrics; webhook alert hooks; Docker Compose + Codespaces helpers
- Mobile-first ops UI: Home / Trade / Positions / Activity / More (+ `/performance`, `/trades`, `/reports`)

## Architecture

```text
Market data → candle validation → strategy → signal → OrderGateway → RiskEngine
  → paper engine → PaperSession + journal + dual-write persistence
  → analytics (closed trades / performance) → /api + dashboard
```

Historical audits under `docs/audits/` and `docs/audit/` remain reference material; prefer the release docs above for merge decisions.

## Migrations

| Revision | Contents |
|----------|----------|
| `0001_phase2` | symbols, candles |
| `0002_phase9` | journal tables |
| `0003_users` | users |
| `0004_paper_slice` | balances, positions, snapshots, system_state, … |
| `0005_cycle_ops` | cycle_locks, scheduler_runs, reconciliation_reports |
| `0006_paper_durable` | paper_accounts, risk_state, strategy_state, processed_cycle_keys, equity_snapshots, kill_switch_events |
| `0007_perf_analytics` | closed_trades, performance_reports |

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
# set DATABASE_URL=postgresql+asyncpg://atlas:atlas@127.0.0.1:5432/atlas in .env
alembic upgrade head
```

### Dashboard

```bash
cd frontend && npm ci
ADMIN_API_TOKEN=local-dev-admin-token ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000 — login `admin` / `atlas` (dev defaults).  
Mobile: bottom nav Home / Trade / Positions / Activity / More. Recovery: `/recovery`.

## Safety invariants (non-negotiable)

- Default mode remains **PAPER**; `ENABLE_LIVE_TRADING=false`
- `LiveTradingGate` fails closed — live order submission is impossible in this release
- Futures, margin, leverage, withdrawals remain disabled
- AI is advisory only and cannot bypass the risk engine
- Never expose API keys, exchange secrets, or admin tokens to the browser
- Never invent portfolio / order / trade data when the backend is unavailable
- Decimal for money; timezone-aware UTC timestamps
- Testnet and paper states must stay labelled and isolated

## Verify

```bash
pytest -q
ruff check app tests
ruff format --check app tests
mypy app
alembic upgrade head
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
docker compose config
node frontend/scripts/check-mobile-nav.mjs
```

Coverage gate remains **≥85%** (`pyproject.toml`).

## Attribution

Project Atlas — Developed by Saugat Gurung
