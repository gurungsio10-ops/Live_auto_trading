# User Guide — Project Atlas (Paper Trading)

**Financial risk warning:** Project Atlas is a **personal paper-trading** research tool. Simulated fills, backtests, and strategy signals do **not** guarantee future profits. Live money trading is **disabled**. Never risk capital you cannot afford to lose based on results shown here.

## What you get

- Paper account (default starting balance from `PAPER_STARTING_BALANCE`, typically 10 000 quote units)
- Risk-gated simulated orders (fees + slippage)
- Strategies evaluated on closed candles
- Dashboard for portfolio, orders, fills, signals, risk events, strategies, backtests, and journal-oriented views
- Optional advisory AI explanations (analysis only — not execution)

## Modes

| Mode | Meaning in Atlas |
|------|------------------|
| **PAPER** (default) | Simulated broker; safe development path |
| **BACKTEST** | Historical research; next-bar SL/TP in the engine |
| **TESTNET** | Non-live venue experiments where wired — still not production money |
| **LIVE** | Hard-blocked — app will refuse to run as a live executor in this phase |

UI shows a trading-mode indicator. Keep configuration at paper unless you are deliberately testing testnet plumbing on a dedicated branch/environment.

## Banners and demo data

If the Next.js server cannot reach the FastAPI backend (`ATLAS_BACKEND_URL`), some **read** pages may show a **demo** banner and placeholder data (`meta.demo=true`).

- Demo data is **not** your paper account.
- Mutating actions (place order, kill switch, etc.) **fail closed** when the backend is down — they will not pretend to succeed.
- Fix: start uvicorn and ensure `ATLAS_BACKEND_URL` points at it.

## Kill switch and pause

- **Kill switch:** Blocks new orders. Existing read views stay available. State persists across API restarts.
- **Pause:** Stops/pauses trading controls from the dashboard (admin-protected).
- Use kill switch if something looks wrong with signals, data, or accidental click-spam.

Operators need `ADMIN_API_TOKEN` configured on both API and frontend server for these controls.

## Strategies

Available strategy IDs (long-oriented paper research):

| ID | Description |
|----|-------------|
| `ema_crossover` | EMA cross with optional ATR stops / RSI filter (common paper-cycle default) |
| `ema_trend` | EMA trend variant |
| `rsi_mean_reversion` | RSI mean-reversion entries/exits |
| `breakout` | Donchian-style breakout |

Use the Strategies pages to select/start/stop and adjust params (mutations require admin token via BFF). Strategies only produce signals; the risk engine can still reject or reduce size.

## Running paper activity

1. Log in to the dashboard (defaults from `.env.example` — change them).
2. Confirm mode is paper and demo banner is absent.
3. Overview → **Run one paper cycle** (or call `/api/v1/paper/cycle/run`).
4. Inspect **Positions**, **Orders**, **Fills**, **Signals**, **Risk events**.
5. Repeat cycles as needed; identical candle keys are idempotent (no double fill).

Offline CLI alternative:

```bash
python -m app.cli paper-run --offline
```

## Backtests

Use the Backtests UI or API to run historical simulations. Results share strategy logic but are research artifacts. The backtester uses **next-bar** stop-loss / take-profit evaluation to avoid same-bar look-ahead optimism. Past simulated performance ≠ future results.

## Journal and audit trail

- Trade journal / risk decision endpoints under `/api/v1` support review of why orders were approved or rejected.
- Durable checkpoint data (balances, positions, kill switch, cycle keys) survives restart; some in-memory fill lists may look empty after bounce until new activity occurs.

## Reset paper account

Overview → Reset (typed confirmation) or API `POST /api/v1/paper/reset` with `{"confirm":"RESET_PAPER_ACCOUNT"}` and admin token. This wipes the paper session — irreversible for that simulated account.

## What Atlas will not do for you

- Place live exchange orders (hard-blocked)
- Let AI bypass risk or submit tickets
- Promise profitability
- Replace your own risk management if you later trade elsewhere

## Getting help / ops

- Start/stop and curl recipes: `docs/operations/RUNBOOK.md`
- Incidents: `docs/operations/INCIDENT_RESPONSE.md`
- Architecture: `docs/architecture/SYSTEM_DESIGN.md`
