# Test Strategy — Project Atlas

Goal: prove **paper** trading safety and correctness without ever submitting orders to a production exchange.

## Principles

1. **Never hit production exchange.** Tests use offline fixtures, mocks, or in-memory SQLite. CI sets `TRADING_MODE=paper`, `LIVE_TRADING_ENABLED=false`.
2. **Fail closed on safety.** Cover live hard-block, admin auth, kill switch, and risk rejects.
3. **Decimal / UTC.** No float money; timestamps timezone-aware.
4. **Advisory AI stays non-executing.** Assert `advisory: true` and no order-submission paths.
5. **Determinism.** Paper cycles and strategy unit tests prefer fixed candles over live market pulls.

## What to test

| Area | Must cover | Location hints |
|------|------------|----------------|
| Config / runtime mode | Invalid → paper; LIVE startup rejected; ack required for checklist | `tests/unit/test_runtime_mode.py`, `test_config_security.py` |
| Live gate | Checklist vs `allowed=False` hard-block; `LIVE_STARTUP_ACK` | `tests/unit/test_testnet_and_live_gate.py` |
| Risk engine | Exposure, drawdown, kill switch, cooldown, reconciliation unhealthy, symbol allowlist | `tests/unit/test_risk_engine.py` |
| OrderGateway | Rejects never reach backend; reductions applied | `tests/unit/test_paper_engine.py` |
| Strategies | EMA crossover/trend, RSI mean reversion, breakout; no same-bar look-ahead on breakout window | `tests/unit/test_ema_*.py`, `test_rsi_breakout_strategies.py` |
| Backtester | Next-bar SL/TP (not same-bar optimistic exit) | `tests/unit/test_backtest_engine.py` |
| Paper cycle / session | Idempotent cycles; restart hydrate of kill switch / keys | `tests/unit/test_paper_cycle.py`, `tests/integration/test_paper_restart_recovery.py` |
| API | Health/ready, paper cycle, admin-protected mutators | `tests/integration/test_api_v1.py` |
| Monitoring | Readiness composition | `tests/unit/test_monitoring.py` |
| AI | Advisory labels; no execution | `tests/unit/test_ai_analyst.py` |
| Redaction | Secrets not logged | `tests/unit/test_log_redaction.py` |
| Market data validators | Closed candles, OHLC sanity | `tests/unit/test_candle_validators.py` |

## Pytest layout

```text
tests/
  conftest.py                 # shared fixtures; prefer in-memory DB
  unit/                       # fast, no network
  integration/                # API, CLI, replay, restart recovery
```

Commands:

```bash
pytest -q
# CI-style coverage gate on core packages:
pytest --cov=app.risk --cov=app.execution --cov=app.portfolio --cov=app.strategies \
  --cov-report=term-missing --cov-fail-under=70
```

Use `DATABASE_URL=sqlite+aiosqlite:///:memory:` for pytest (as CI does) so migration file DBs stay isolated.

## Frontend checks

```bash
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Manual / exploratory (not always automated):

- Demo banner appears when backend is stopped (read paths).
- Order / kill-switch POSTs return error when backend is down (fail closed — no fake success).
- Paper cycle button against a running API updates overview (simulated results only).

## What not to do in tests

- Do not call Binance **production** signed trading endpoints.
- Do not require real `EXCHANGE_API_KEY` / `EXCHANGE_API_SECRET` for the default suite.
- Do not weaken live hard-block assertions to “make LIVE tests pass.”
- Do not commit secrets to fixtures; use obvious placeholders.

## CI map

`.github/workflows/ci.yml`:

| Job | Role |
|-----|------|
| `backend` | ruff, mypy, pytest+coverage, alembic upgrade |
| `frontend` | lint, typecheck, build |
| `secret-scan` | Gitleaks |
| `docker-compose-validate` | `docker compose config` (needs Docker on runner) |

## Related

- `docs/operations/RUNBOOK.md` — local quality commands
- `docs/security/THREAT_MODEL.md` — safety properties under test
