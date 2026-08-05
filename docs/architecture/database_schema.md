# Database schema

PostgreSQL is the normal Docker development database (`docker-compose.yml`). SQLite is used for tests and lightweight local runs.

## Migrations

| Revision | Contents |
|----------|----------|
| `0001_phase2` | `symbols`, `candles` |
| `0002_phase9` | Journal: `signals`, `risk_decisions`, `orders`, `fills`, `system_events` |
| `0003_users` | `users` |
| `0004_paper_slice` | `strategy_runs`, `balances`, `positions`, `portfolio_snapshots`, `trade_journal`, `system_state` |
| `0005_cycle_ops` | `cycle_locks`, `scheduler_runs`, `reconciliation_reports` |
| `0006_paper_durable` | `paper_accounts`, `risk_state`, `strategy_state`, `processed_cycle_keys`, `equity_snapshots`, `kill_switch_events` |

Apply: `alembic upgrade head`

## Durable paper runtime tables (0006)

| Table | Role |
|-------|------|
| `paper_accounts` | First-class cash / peak / daily start / fees / idempotency index |
| `risk_state` | Circuit breaker, seen keys, health flags, kill switch, drawdown inputs |
| `strategy_state` | Selected strategy, running set, param overrides |
| `processed_cycle_keys` | Normalized uniqueness for `(account, strategy_version, symbol, timeframe, candle_open_time)` |
| `equity_snapshots` | Equity curve samples |
| `kill_switch_events` | Explicit kill-switch toggles (audit) |

`system_state` keys remain dual-written for backward compatibility (`paper_checkpoint`, `kill_switch`, `processed_cycle_keys`, `reconciliation_halt`, trading flags).

## Notable constraints

- Candles: unique identity on symbol/timeframe/open_time (see 0001)
- Orders: unique `idempotency_key`
- Strategy runs: unique `(strategy_name, strategy_version, symbol, timeframe, candle_open_time)`
- Processed cycle keys: unique `(account_id, strategy_version, symbol, timeframe, candle_open_time)`
- Monetary columns: `Numeric(36, 18)`
- Timestamps: timezone-aware UTC

## Application vs persistence

Paper session keeps a process-local cache for latency. On every cycle (and kill-switch / trading-flag mutation) the runtime dual-writes:

1. Checkpoint JSON + balances/positions/snapshots (`0004`)
2. First-class account / risk / strategy / equity rows (`0006`)
3. Journal orders/fills when a `JournalStore` is attached

Startup hydrate reconstructs the process-local session from these tables, then runs reconciliation. Failures halt trading (fail closed).
