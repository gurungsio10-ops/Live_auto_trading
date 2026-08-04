# Test Strategy — Paper Consolidation

## Pyramid

### Unit

Indicators, strategies, risk reason codes, accounting invariants, fees/slippage, precision, redaction, config validation, security order-path scan.

### Integration

Migrations (blank→head, 0006 down/up), paper cycle, durable restart, reconciliation halt, cycle locks, concurrent duplicate cycles, authenticated admin routes, soak short-run, recovery status API.

### End-to-end (API)

Reset → deterministic cycle → fill → portfolio → recovery status → restart hydrate → idempotent replay.

## Offline / no-network

Default candle source is offline fixtures. Full `pytest` suite must not require exchange credentials or network market data.

## Coverage

Application coverage gate **≥85%** (`pyproject.toml` / CI). Omits advisory/disabled paths (`app/ai/*`, `app/execution/exchange/*`, deprecated `mvp.py` / `market_data/service.py`, `app/cli.py`, `app/news/*`).

## Commands

```bash
pytest -q
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
pytest tests/integration/test_concurrent_cycles.py -q
python -m app.cli paper-soak --max-cycles 6 --seed 42
```

See also `docs/testing/TEST_STRATEGY.md` (historical) — this file is authoritative for paper-v1 consolidation.
