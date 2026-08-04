# Changelog — Project Atlas

All notable documentation- and product-facing hardening notes for recent paper-trading work. Format is human-readable, not strict Keep-a-Changelog sections for every commit.

## Unreleased / recent hardening (2026-08)

### Security and control plane

- **Admin auth on mutators** — Dashboard and system mutating routes require `AdminAuthDep` (`X-Admin-Token` / Bearer). Unset `ADMIN_API_TOKEN` fails closed with 503.
- **Fail-closed BFF** — Next.js proxies for orders, kill-switch, and related mutators return 503 on backend failure; they no longer invent APPROVED/FILLED orders or fake kill-switch success. Read paths may still serve labeled demo data.
- **CI secret scan** — Gitleaks job added in `.github/workflows/ci.yml`. Compose config validation job added for runners with Docker.

### Reliability

- **Readiness DB probe** — `GET /ready` / `/health/ready` runs a real `SELECT 1` against the configured database; LIVE runtime is always `not_ready`.
- **Graceful shutdown** — App lifespan disposes SQLAlchemy engines on exit.

### Trading safety

- **Live gate hard-block + `LIVE_STARTUP_ACK`** — Checklist includes `LIVE_STARTUP_ACK=I_UNDERSTAND_LIVE_TRADING_RISKS`; `LiveTradingGate.allowed` remains **false** even when the checklist is complete (`live_execution_hard_blocked`). Startup still raises if LIVE is requested.
- **Next-bar SL/TP** — Backtester evaluates stop-loss / take-profit on the **next** bar after entry (no same-bar optimistic exits).

### Strategies

- **RSI mean reversion** — `rsi_mean_reversion` registered.
- **Breakout** — `breakout` Donchian-style strategy registered (prior window excludes current bar).

### Docs

- Architecture system design, uppercase ops `RUNBOOK.md`, incident response, threat model, test strategy, user guide, and audit refresh.

## Earlier paper E2E hardening (summary)

- Paper default runtime modes (`ATLAS_RUNTIME_MODE`) with invalid → paper.
- Durable kill switch / portfolio checkpoint / cycle idempotency via `system_state`.
- Risk cooldown + insufficient-balance paths.
- EMA crossover ATR stops + optional RSI filter.
- Dashboard paper cycle / fills views; auth login (PBKDF2).

## Safety reminder

Paper mode remains the supported product path. Live money trading is not enabled.
