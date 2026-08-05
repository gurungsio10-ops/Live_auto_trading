# Implementation Plan — Paper Trading MVP

## Goal

Deliver a reliable **paper-only** end-to-end path matching:

Market data → validation → indicators → strategy → risk → paper broker → portfolio → journal → API → dashboard

Live money, futures, leverage, and withdrawals remain disabled.

## Stages (this branch)

| Stage | Work | Status |
|-------|------|--------|
| 0 | Audit + `CURRENT_STATE` / `ARCHITECTURE` / this plan | Done |
| 1 | Config aliases (`STARTING_BALANCE`, `EXCHANGE_NAME`, `TRADING_ENABLED`, …) + safety guard | In progress |
| 2 | Bybit public OHLCV adapter + market facade | In progress |
| 3 | EMA+RSI baseline strategy (`ema_rsi`) with env periods / SL-TP % | In progress |
| 4 | `Broker` protocol + `PaperBroker` wrapper | In progress |
| 5 | MVP `/api/*` routes (health, cycle, start/stop, kill-switch, reset, …) | In progress |
| 6 | Makefile + Dockerfile + README run instructions | In progress |
| 7 | Tests for new modules + full verification suite | In progress |
| 8 | Dashboard paper banner / controls wired to `/api` aliases | In progress |

## Design decisions

1. **Preserve stack** — extend FastAPI/Next/CCXT rather than rewrite.
2. **Aliases over renames** — keep existing env names; accept MVP names via `AliasChoices`.
3. **Offline-first cycles** — default candle source is deterministic fixtures so CI/dev need no exchange keys; optional live public OHLCV when network allowed.
4. **`TRADING_ENABLED=false` default** — start/stop endpoints flip a process flag; one-shot cycle may use `confirm=RUN_ONE_CYCLE` when stopped.
5. **No live broker** — `PaperBroker` only; live gate always denies.

## Out of scope

- Real-money order submission
- Futures / leverage / withdrawals
- LLM-driven order placement
- Multi-user / copy-trading
