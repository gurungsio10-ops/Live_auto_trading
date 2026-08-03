# Database schema

PostgreSQL is the normal Docker development database (`docker-compose.yml`). SQLite is used for tests and lightweight local runs.

## Migrations

| Revision | Contents |
|----------|----------|
| `0001_phase2` | `symbols`, `candles` |
| `0002_phase9` | Journal: `signals`, `risk_decisions`, `orders`, `fills`, `system_events` |
| `0003_users` | `users` |
| `0004_paper_slice` | `strategy_runs`, `balances`, `positions`, `portfolio_snapshots`, `trade_journal`, `system_state` |

Apply: `alembic upgrade head`

## Notable constraints

- Candles: unique identity on symbol/timeframe/open_time (see 0001)
- Orders: unique `idempotency_key`
- Strategy runs: unique `(strategy_name, strategy_version, symbol, timeframe, candle_open_time)`
- Monetary columns: `Numeric(36, 18)`
- Timestamps: timezone-aware UTC

## Application vs persistence

Paper session / cycle state for the dashboard is process-local for responsiveness. Orchestrator + journal ORM provide the reconstructable audit trail when a DB session is attached. Portfolio snapshot tables support durable history for the paper slice.
