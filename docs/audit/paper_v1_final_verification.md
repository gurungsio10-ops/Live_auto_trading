# Paper V1 Final Verification

**Branch:** `cursor/release-paper-v1-consolidated-e3a2`  
**Migration head:** `0006_paper_durable`  
**Scope:** Production-quality **PAPER** trading platform consolidation

## Gate results (local verification)

| Gate | Status |
|------|--------|
| `pytest -q` | PASS (265 tests) |
| `pytest --cov=app --cov-fail-under=85` | PASS (**85.08%**) |
| `ruff check app tests` | PASS |
| `ruff format --check app tests` | PASS |
| `mypy app` | PASS |
| `alembic upgrade head` (blank → head) | PASS |
| `alembic downgrade base` → `upgrade head` | PASS |
| `0006` downgrade to `0005_cycle_ops` → upgrade head | PASS |
| `npm --prefix frontend run lint` | PASS |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend run build` | PASS (`/recovery` route present) |
| `docker compose config` | PASS (compose v2 binary) |
| Short soak (`paper-soak --max-cycles 6`) | PASS (`ok: true`, 0 invariant failures) |
| Security order-path scan | PASS (`tests/unit/test_security_order_paths.py`) |
| Invariant unit tests | PASS |

Coverage omits (documented, non-hot-path): `app/ai/*`, `app/execution/exchange/*`, `app/cli.py`, `app/api/mvp.py`, `app/market_data/service.py`, `app/news/*`.

## Authoritative hot path

```text
Candles → strategy → OrderGateway → RiskEngine → PaperTradingEngine
  → PaperSession + JournalStore + paper_persistence (atomic dual-write)
```

Cycle entry: `run_paper_trading_cycle` (`app/services/paper_cycle.py`).

## Recovery / durability checks covered

- Restart with open / partial position
- Kill-switch survival
- Reconciliation halt + admin clear-halt
- Duplicate cycle / fill idempotency
- Alembic chain including main `0004` → head
- Fail-closed bootstrap when durable state untrusted
- Accounting identity: `cash + marked_position_value = equity`

## Soak harness

```bash
python -m app.cli paper-soak \
  --duration-hours 24 \
  --symbols BTC/USDT,ETH/USDT \
  --restart-interval-minutes 30 \
  --seed 42
```

CI shortcut: `--max-cycles N`. Artifacts: `artifacts/soak/{summary,events,equity,reconciliation,invariants}.*`

## Honest completion estimates

| Platform | Completion | Notes |
|----------|------------|-------|
| Paper trading platform | **~92%** | Durable recovery, recon, scheduler, dashboard recovery panel, soak harness, CI gates |
| Live money platform | **0% enabled** | Hard-blocked; checklist unchecked |

Remaining paper gaps (non-blocking for merge): longer supervised 24h Postgres soak in a shared env, alert-channel polish, further dashboard UX.

## Security affirmations

- Live placement impossible via `LiveTradingGate` / `SafetyGuard`
- No `.create_order(` outside disabled `app/execution/exchange/*`
- Mutating endpoints require `ADMIN_API_TOKEN`
- Admin token never shipped to browser JS (BFF `adminHeaders()`)
- CORS allowlist-based
- Startup fail-closed for unsafe config / untrusted durable state
- AI advisory only; leverage fixed at 1x; withdrawals unavailable

## Merge recommendation

**MERGE** this release branch to `main` (squash). Close #21–#26 as superseded/absorbed. See `docs/audit/release_merge_plan.md`.
