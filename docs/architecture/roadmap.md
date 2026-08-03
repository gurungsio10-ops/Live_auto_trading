# Project Atlas — Architecture Roadmap

Phases must be completed in order. Do not start a phase whose prerequisites
are not marked **done**.

## Live trading gating checklist (Phase 14)

All nine conditions must be true simultaneously for a live order to submit:

1. `TRADING_MODE == "live"`
2. `LIVE_TRADING_ENABLED == true`
3. `KILL_SWITCH_ENABLED == false`
4. Valid exchange credentials present
5. Risk engine healthy
6. Market data healthy
7. Database healthy
8. Reconciliation healthy
9. Valid manual live-approval token

## Phase status

| Phase | Name | Status | Prerequisites |
|------:|------|--------|---------------|
| 1 | Foundation (config, security, domain models, API skeleton) | **done** | — |
| 2 | Historical Market Data | **done** | Phase 1 |
| 3 | Indicators | **done** | Phase 2 |
| 4 | Strategy Framework | **done** | Phase 3 |
| 5 | Backtesting Engine | **done** | Phase 4 |
| 6 | Risk Engine | **done** | Phase 5 |
| 7 | Paper Trading Engine | **done** | Phase 6 |
| 8 | Live Market Data (WebSocket) | **partial** | Phase 7 |
| 9 | Portfolio and Journal | **done** | Phase 8 |
| 10 | Monitoring | **partial** | Phase 9 |
| 11 | Dashboard (Next.js) | **done** | Phase 10 |
| 12 | AI Analysis Layer (advisory only) | **done** | Phase 11 |
| 13 | News Sentiment | **partial** | Phase 12 |
| 13.5 | Testnet Execution | **partial** | Phase 13 |
| 14 | Live Trading Preparation | **done** (gates prepared; no live backend wired) | Phase 13.5 |
| 15 | Futures and Leverage | **done** (primitives; enable only after live-spot soak) | Phase 14 |
| 16 | Full audit and end-to-end paper-trading validation | **in progress** | Phase 15 |

## Truthful status corrections (Phase 16 audit)

Statuses were revised to match the actual implementation (see
`docs/audit/phase16_repository_audit.md`):

- **Phase 8 → partial:** `app/market_data/websocket/client.py` is a fully-tested
  *generic* WS consumer, but there is **no Binance stream adapter/URL wired**; the
  running app's live feed uses REST polling (via the CLI), not a live WS to a real
  exchange. Stale detection is passive (does not trigger reconnect).
- **Phase 10 → partial:** `app/monitoring/health.py` readiness is a flag aggregator
  (no live DB/Redis/market-data probes) and `WebhookAlertChannel` is an intentional
  no-op.
- **Phase 13 → partial:** `app/news/sentiment.py` is implemented and tested but is
  **not wired** into `RiskEngine`.
- **Phase 13.5 → partial:** `app/execution/exchange/testnet.py` is a complete adapter
  but **unwired** (referenced only from tests); no factory instantiates it in app code.

## Phase 16 acceptance criteria — current state

Met: backend installs; `pytest` green (143); migrations apply to a clean DB;
offline replay test passes; public-data paper-run starts/shuts down cleanly (and,
against a reachable public exchange, completes a paper trade); ≥1 deterministic
replayed trade completes; every actionable order has a persisted risk approval;
duplicate events do not duplicate trades; kill switch blocks all order creation;
live execution unreachable; no secrets in logs/commits; frontend build passes.

Open (why Phase 16 is **in progress**, not done): repo-wide `ruff` / `ruff format`
/ `mypy` clean-up on legacy modules; Docker packaging (`docker compose config`);
frontend ESLint config + tests; reconciling the legacy `/api/*` placeholder surface.

## Notes

- `TRADING_MODE` defaults to `paper` and must never be changed in code defaults.
- AI (`app/ai/`) is advisory only and must never call order submission.
- Every order path must pass through `app/risk/engine.py`.
- Phase 15 code is present as isolated-margin helpers with default max leverage 1x;
  it is not wired into live order submission until Phase 14 has been stable.
- **Passing tests do not make the platform live-trading ready.** Phase 16 validates
  paper trading only; testnet soak and live readiness are later, separate phases.
