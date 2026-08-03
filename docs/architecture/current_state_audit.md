# Project Atlas — Current State Audit

**Date:** 2026-08-03  
**Branch context:** `cursor/dev-environment-setup-e3a2` (includes Phase 16 paper orchestrator + merged `main` PR #2 foundation)  
**Scope:** End-to-end deterministic paper-trading vertical slice for BTC/USDT

This audit describes the repository **before** the vertical-slice completion work in this milestone. Implementation continues immediately after this document.

---

## Existing modules and responsibilities

| Module | Path | Responsibility |
|--------|------|----------------|
| Config / safety | `app/core/config.py`, `security.py`, `logging.py`, `time.py` | pydantic-settings, paper defaults, redaction, UTC helpers |
| Domain models | `app/models/domain/{enums,market,trading}.py` | Candle, TradeSignal, OrderRequest, RiskEvaluation, Fill, Position, PortfolioState |
| DB / migrations | `app/db/`, `alembic/versions/0001–0003` | Symbols, candles, journal tables, users |
| Market data | `app/market_data/` | Provider interface, Binance REST, validators, retry, service, WS stub |
| Indicators | `app/indicators/` | EMA, RSI, ATR, volume MA (Decimal) |
| Strategies | `app/strategies/` | Strategy ABC, registry, EMA Trend (12/26 + filters) |
| Risk | `app/risk/engine.py` | Mandatory risk gate (APPROVED/REJECTED/REDUCED/HALTED) |
| Execution | `app/execution/{gateway,paper,live_gate,exchange}` | OrderGateway → paper engine; live gate blocks live |
| Portfolio | `app/portfolio/service.py` | Thin portfolio helpers |
| Journal | `app/journal/store.py` | Persist signals, risk decisions, orders, fills, system events |
| Orchestrator | `app/services/trading_orchestrator.py` | Candle → strategy → risk → paper → journal |
| Paper session | `app/services/paper_session.py` | In-memory dashboard backend (synthetic candles) |
| Sample market | `app/services/sample_market.py` | Deterministic offline candle series |
| CLI | `app/cli.py` | `paper-run` offline/public feed |
| Backtesting | `app/backtesting/` | Strategy replay with fees/slippage (bypasses RiskEngine) |
| AI / news | `app/ai/`, `app/news/` | Advisory only |
| Auth | `app/auth/`, `app/api/auth.py` | PBKDF2 users, HMAC session tokens |
| API | `app/api/{dashboard,routes}.py`, `app/main.py` | Root dashboard + legacy `/api` |
| Frontend | `frontend/` | Next.js Atlas Terminal with BFF proxies |
| Compose | `docker-compose.yml` | Postgres + Redis (no app image) |

---

## Fully implemented

- Candle domain validation (OHLC consistency, UTC)
- Risk engine with broad rejection matrix + unit tests (~40)
- Paper trading engine (fees, slippage, spread, WAC, idempotency)
- OrderGateway risk-first submission
- Live trading gate / NotImplemented live path
- EMA Trend strategy framework (deterministic, no credentials)
- TradingOrchestrator + offline replay integration tests
- CLI paper-run with kill-switch / graceful shutdown
- Journal ORM write path
- Auth login + users migration
- Dashboard root API wired to PaperSession
- Frontend shell (overview, positions, orders, signals, risk, strategies, backtests, settings, login)
- Tooling in `pyproject.toml` (ruff, black, mypy, pytest)

---

## Partially implemented

| Area | Gap |
|------|-----|
| Config | Missing env knobs for paper balance/fee/slippage bps, API host/port, percent aliases |
| EMA strategy | Exists as 12/26 + RSI/ATR/volume filters; not minimal 9/21 BUY/SELL/HOLD crossover |
| Orchestration | `process_candle` exists; no `run_paper_trading_cycle(symbol, timeframe, correlation_id)` façade |
| Dual pipelines | CLI/replay → orchestrator+journal; dashboard → PaperSession synthetic/in-memory |
| Market data | Stale-age not in candle validators; Binance WS not wired; VM may get HTTP 451 from Binance |
| Portfolio persistence | Accounting in memory; no balances/positions/portfolio_snapshots tables |
| Backtesting | Same strategy math-ish, but bypasses RiskEngine / OrderGateway |
| Legacy `/api` | Placeholder/divergent kill-switch and portfolio vs live dashboard |
| Health | Flag-based SystemHealth dataclass; limited live probes |
| Docs | README still partially stale vs compose/tooling |

---

## Placeholder-only

- Live exchange order execution (correctly gated / not implemented)
- WebSocket Binance stream adapter (generic client only)
- Redis usage (URL present, unused at runtime)
- AI as execution authority (correctly absent; advisory only)

---

## Current test coverage

- **~143 pytest tests** passing after merge
- Strong: risk, paper engine, orchestrator, live gate, candle validators, auth, CLI, offline replay
- Weak/missing: FastAPI HTTP route tests for `/api/v1`, portfolio snapshot persistence, frontend tests, CI gate, coverage target ≥85% on risk/execution/portfolio/strategy as a formal CI gate

---

## Security concerns

1. Mutating dashboard endpoints (kill switch, pause, orders) lack a dedicated admin API token (login protects UI, not raw API).
2. Legacy `/api` routes may diverge from live dashboard controls.
3. Default auth credentials (`admin`/`atlas`) are for local paper only — must never ship as live defaults.
4. Exchange secrets correctly use `SecretStr` + redaction; keep that invariant.
5. No CI yet to enforce lint/type/test on every PR.

---

## Financial correctness concerns

1. Paper fee/slippage/cash are hardcoded in `PaperConfig`, not settings-driven.
2. Risk percent settings use fractions (0.01 = 1%); env aliases for `*_PERCENT` needed for clarity.
3. Backtest path can diverge from risk-gated paper fills.
4. Dashboard synthetic candles are fine for demo ticks but must not be confused with live market data.
5. Symbol allowlist enforced in provider, not yet in risk engine.

---

## Database and migration concerns

- Migrations 0001–0003 exist (candles/symbols, journal, users).
- Missing tables for: `strategy_runs`, `balances`, `positions`, `portfolio_snapshots`, `trade_journal` (unified append-only), `system_state`.
- Journal tables exist but read APIs for UI reconstruction are thin.
- SQLite used in tests; Postgres via docker-compose for normal local DB.

---

## Frontend / backend integration gaps

- Frontend proxies to **root** FastAPI paths, not `/api/v1`.
- Demo mock fallback still active when backend is down (acceptable with banner).
- No “Run one paper cycle”, paper reset with confirmation, or journal/history views bound to orchestrator persistence.
- No frontend typecheck/test script beyond `next lint` / `tsc` via build.

---

## Top ten implementation priorities

1. Persist audit + extend Settings (paper balance/fee/slippage, API host/port, admin token, percent aliases).
2. Add domain aliases / missing models (`Signal`, `OrderIntent`, `MarketSnapshot`, `Balance`, `StrategyRun`, `TradeJournalEntry`, `SystemHealth`).
3. Add deterministic EMA crossover strategy (fast 9 / slow 21, BUY/SELL/HOLD).
4. Enforce allowed symbols + short-sale/leverage rejects in risk.
5. Implement `run_paper_trading_cycle` over TradingOrchestrator.
6. Add Alembic migration for portfolio/strategy_run/system_state tables.
7. Expose `/api/v1/*` (health, market, strategy, signals, risk, orders, fills, portfolio, journal, cycle, kill-switch, reset) with admin token on mutators.
8. Wire PaperSession + frontend controls to the cycle path; keep root dashboard for BFF compatibility.
9. Align backtest docs/tests; add API + cycle + strategy unit tests; raise coverage on core modules.
10. Add GitHub Actions CI + architecture/ops documentation (live checklist unchecked).

---

## Design decisions for this milestone

- **Reuse over rewrite:** Keep RiskEngine, PaperTradingEngine, OrderGateway, TradingOrchestrator.
- **Aliases:** Expose prompt-named types as aliases where existing names differ (`Signal = TradeSignal`, `OrderIntent = OrderRequest`).
- **Single cycle entry:** New service façade; dashboard and `/api/v1` both call it.
- **Live trading:** Remains disabled; readiness checklist stays unchecked.
