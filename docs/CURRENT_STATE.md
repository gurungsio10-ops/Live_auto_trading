# Current State — Paper Trading MVP Audit

**Date:** 2026-08-04  
**Branch:** `feature/paper-trading-mvp`  
**Method:** Code inspection + `pytest` (178+ passed) + HTTP smoke against uvicorn. Roadmap labels were not trusted.

## Stack (preserved)

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Pydantic Settings, SQLAlchemy async, Alembic |
| Market data | CCXT (`binance` + `bybit` adapters) |
| Frontend | Next.js 14 + TypeScript + Tailwind |
| DB | SQLite default; Postgres via compose |
| CI | GitHub Actions (lint, typecheck, test, build, gitleaks, compose) |

## Module classification

| Module | Status | Evidence |
|--------|--------|----------|
| Configuration & safety defaults | **Complete** | `app/core/config.py`, safety guard, live hard-block |
| Market data (Binance + Bybit public) | **Partial→Complete** | Offline fixtures + CCXT providers; network optional |
| Candle validation / UTC normalize | **Complete** | `validators/candles.py`, `normalizers/timestamps.py` |
| Indicators (EMA, RSI, ATR) | **Complete** | `app/indicators/` |
| EMA+RSI strategy | **Complete** | `ema_crossover` + `ema_rsi` baseline |
| Risk engine | **Complete** | All orders via `OrderGateway` → `RiskEngine` |
| Paper broker | **Complete** | `PaperTradingEngine` / `PaperBroker` |
| Trading orchestrator / cycle | **Complete** | `paper_cycle.py`, `trading_orchestrator.py` |
| Persistence / migrations | **Partial** | Alembic 0001–0004; checkpoint + cycle keys; full fill ledger hydrate incomplete |
| Versioned API `/api/v1` | **Complete** | Paper cycle, portfolio, kill switch, reset |
| MVP API aliases `/api/*` | **Complete** | Checklist paths mounted under `/api` |
| Dashboard | **Partial→Complete** | Real backends when API up; GET demo fallback if down |
| Live / futures / leverage | **Blocked** | Hard-disabled by design |
| Makefile / Dockerfile | **Complete** (this branch) | `make setup|dev|test|paper-cycle` |
| Redis | **Stubbed** | Configured; unused by paper path |
| News / AI order path | **N/A** | AI advisory only; never submits orders |

## Verified runtime behaviours

- Paper cycle: signal → risk `APPROVED` → paper `FILLED` → position/portfolio update
- Kill switch blocks new orders; mutators require `ADMIN_API_TOKEN`
- `LiveTradingGate.allowed` always `false`
- `TRADING_MODE` defaults to `paper`; LIVE startup raises
- Tests: see CI / local `pytest -q`

## Honest completion

~**85%** for a personal **paper trading MVP** (not live-ready). Remaining non-blocking gaps: continuous scheduler, full ORM fill hydrate across restart, Redis unused, live public OHLCV optional (offline fixtures default in CI).
