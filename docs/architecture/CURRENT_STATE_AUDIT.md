# Current State Audit — Project Atlas

**Date:** 2026-08-04  
**Branch:** `cursor/paper-trading-e2e-e3a2` (docs suite may land on a docs branch)  
**Method:** Code + tests + CI + runtime verification. Roadmap labels were not trusted.

## Baseline checks (executed before further changes)

| Check | Result |
|-------|--------|
| `pip install -e ".[dev]"` | pass |
| `ruff check` / `ruff format --check` | pass |
| `mypy app` | pass |
| `pytest -q` | **169 passed** (plus newer strategy/gate/backtest tests on hardening branch) |
| `alembic upgrade head` | pass (0001–0004) |
| `npm ci` / lint / typecheck / build | pass |
| `docker compose config` | **unavailable** in some VMs (`docker` binary absent); validated in CI job when Docker present |

## Honest completion (working functionality)

| Area | Status | % |
|------|--------|--:|
| Foundation / config / safety defaults | Working | 95 |
| Historical market data + validators | Working | 90 |
| Strategy framework (EMA + RSI MR + breakout) | Working | 88 |
| Backtesting (next-bar SL/TP) | Working | 85 |
| Risk engine | Working (strong) | 92 |
| Paper trading + restart hydrate | Working | 88 |
| Live WebSocket | Partial (generic + testnet adapter on other branch) | 55 |
| Portfolio / journal persistence | Partial (checkpoint yes; full ORM fills hydrate no) | 70 |
| Monitoring / readiness (DB probe on `/ready`) | Improved | 75 |
| Next.js dashboard (fail-closed mutator BFF) | Working; read demo fallback remains | 88 |
| AI advisory isolation | Working | 95 |
| News sentiment | Partial (unwired to risk) | 40 |
| Testnet execution | Partial on this branch (fuller on Sprint 1 PR) | 50 |
| Live trading | Correctly blocked (ack + hard-block aligned) | 100 (as safety) / 0 (as live product) |
| Futures primitives | Isolated helpers only | 40 |
| CI / security scanning (Gitleaks + compose job) | Improved | 85 |
| Ops documentation suite | Improved | 85 |

**Overall honest completion: ~78–80%** for a personal paper-first platform (not live-ready).

## Genuinely implemented

- Paper default + LIVE hard-block + `LIVE_STARTUP_ACK` checklist alignment + Decimal/UTC rules
- Risk-gated paper cycle API + dashboard PaperSession
- Durable kill switch / portfolio checkpoint / cycle idempotency keys
- EMA crossover (+ ATR stops), EMA trend, **RSI mean reversion**, **breakout**
- Auth login (PBKDF2) + Next middleware; **admin token on dashboard + `/api/v1` mutators**
- **Fail-closed BFF** for orders / kill-switch (and related mutators)
- **`/ready` DB probe** + lifespan engine dispose
- **Next-bar SL/TP** in backtester
- Alembic 0001–0004; CI lint/type/test/build/migrate + **secret scan** + compose config job

## Partial / mocked / disconnected / remaining

- Read-path demo fallbacks when backend down (labeled; mutators no longer fake success)
- Redis unused for core paper REST path but listed in compose
- Fill/order history not fully ORM-hydrated after restart (balances/positions/kill switch are)
- Continuous 24/7 paper stream still cycle-driven
- No app Dockerfile; docker CLI may be absent in some agent VMs
- Default example dashboard credentials (`admin` / `atlas`)
- Live product execution intentionally unimplemented
- Roadmap / older audits may still mention pre-hardening gaps — prefer this file

## Security / operational risks (remaining)

1. Default example credentials on shared hosts
2. Demo **read** data if operators ignore banners
3. Stack traces on unhandled 500s possible
4. Exposing API without network controls still risky even with admin token

## Prioritised fixes — status

| # | Fix | Status |
|---|-----|--------|
| 1 | Admin-auth dashboard + legacy mutators; pass token from BFF | **Done** |
| 2 | Fail-closed BFF for orders/kill-switch | **Done** |
| 3 | Real readiness DB probe + graceful shutdown | **Done** |
| 4 | RSI mean-reversion + breakout strategies | **Done** |
| 5 | Live-gate + `LIVE_STARTUP_ACK` alignment | **Done** |
| 6 | Next-bar SL/TP in backtester | **Done** |
| 7 | CI secret scan + compose config job | **Done** |
| 8 | Required ops/security/docs suite | **In progress / landing** |

## Still not done (honest backlog)

- Full journal ORM hydrate on every HTTP path
- Continuous paper runtime loop
- Higher CI coverage gate (still 70% on selected packages)
- Live trading product work (blocked by design until an explicit future phase)
