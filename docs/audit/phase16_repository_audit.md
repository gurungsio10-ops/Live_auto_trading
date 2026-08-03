# Phase 16 — Repository Audit

Status: **Stage 1 audit (read-only inspection).** No production code was changed to produce this report.

Scope: full inspection of the `Live_auto_trading` repository as it exists on branch
`cursor/dev-environment-setup-e3a2`, to determine whether Project Atlas can run a
complete deterministic paper-trading lifecycle on real public market data without
submitting any live order.

Method: direct reads of every `app/` package, the tests, migrations, Alembic env,
frontend proxy contract, and config; plus repository-wide searches for `TODO`,
`FIXME`, `NotImplementedError`, `float(` (money), naive timestamps, secrets, and
direct-exchange bypasses.

---

## 1. Architecture discovered from the actual code

Two services in one repo.

**Backend (FastAPI, `app/`)** — routers registered in `app/main.py`:
- Root: `GET /health`, `GET /config/safe`.
- `app/api/auth.py` (root paths): `POST /auth/login`, `POST /auth/verify` — DB-backed user store, PBKDF2 hashes, HMAC session tokens.
- `app/api/dashboard.py` (root paths): the **live** dashboard surface (portfolio, positions, orders, signals, risk-events, equity-curve, strategies + control, kill-switch, pause, settings, journal export, backtests), backed by `app/services/paper_session.py`.
- `app/api/routes.py` (prefix `/api`): an **older/parallel** surface with placeholder data (`/api/portfolio/summary` hard-coded, `/api/equity-curve` synthetic), advisory AI endpoints, live-gate status, and a **separate** in-memory kill-switch/pause. The frontend does **not** use these.

**Domain core** (`app/models/domain/*`): Pydantic models (`Candle`, `TradeSignal`, `OrderRequest`, `Order`, `Fill`, `Position`, `PortfolioState`, `RiskEvaluation`) — all `Decimal` money, all UTC timestamps via `app/core/time.py`. Enums in `app/models/domain/enums.py`.

**Pipeline building blocks:**
- `app/market_data/` — `BinanceProvider` (real public REST via `ccxt.async_support`), a **generic** websocket client (no Binance adapter/URL wired), candle validators, UTC normalizers, and `MarketDataService` (idempotent DB upsert of candles/symbols).
- `app/indicators/` — SMA/EMA/RSI/MACD/ATR/Bollinger/VWAP; pure, deterministic, `Decimal`-out, causal (no look-ahead, unit-verified).
- `app/strategies/` — `Strategy` ABC + `EMATrendStrategy` (`ema_trend`) + a registry (only `ema_trend` is registered/bootstrapped).
- `app/backtesting/` — event-driven `BacktestEngine` + `PerformanceMetrics` + JSON/Markdown reports.
- `app/risk/engine.py` — deterministic `RiskEngine.evaluate(request, context) -> RiskEvaluation`; every reason code exercised in tests.
- `app/execution/` — `PaperTradingEngine` (real simulated fills, fees, slippage, partial fills, idempotency, P&L), `OrderGateway` (risk-first single entrypoint), `LiveTradingGate` (status only), `ExchangeTestnetClient` (complete but **unwired**), `futures.py` (pure math, **unwired**).
- `app/journal/store.py` — ORM tables (`signals`, `risk_decisions`, `orders`, `fills`, `system_events`) + `JournalStore` (write-only; **no read API**).
- `app/portfolio/service.py` — `PortfolioService.snapshot()` (used in tests; **not** used by the live dashboard, which inlines the math).
- `app/monitoring/health.py` — flag-based readiness aggregator + console/webhook alert channels (webhook is a deliberate no-op).
- `app/ai/`, `app/news/` — advisory only; **verified** not to import execution/risk.
- `app/services/paper_session.py` — the current orchestration-ish layer: an **in-memory** singleton that wires risk → paper engine → strategy → backtest for the dashboard; synthesises candles for strategy ticks; **does not persist to the journal DB**.

**Frontend (`frontend/`)** — Next.js 14 dashboard; server-side proxy routes call the backend root paths; middleware gates routes; login delegates to the backend. All proxy paths map to registered backend endpoints; a demo/mock fallback remains for backend-down resilience.

**Data flow that actually exists today:** the dashboard path is `PaperSession.run_strategy_tick` → *synthetic* candles → indicators → `EMATrendStrategy` → `OrderGateway`/`RiskEngine` → `PaperTradingEngine` → in-memory portfolio → in-memory risk/signal logs → API. **There is no real-public-data ingestion path feeding the strategy, and no persistence of the lifecycle to the journal DB.**

---

## 2. Implemented features (real, tested)

| Area | Evidence |
|---|---|
| Deterministic indicators | `app/indicators/*`, `tests/unit/test_indicators.py`, no-look-ahead tests |
| EMA-trend strategy | `app/strategies/ema_trend.py`, `tests/unit/test_ema_trend_strategy.py` |
| Risk engine (all reason codes) | `app/risk/engine.py`, `tests/unit/test_risk_engine.py` (537 lines) |
| Paper execution (fills/fees/slippage/partial/idempotency/P&L) | `app/execution/paper/engine.py`, `tests/unit/test_paper_engine.py` |
| Order gateway (risk-first) | `app/execution/gateway.py`, `test_paper_engine.py` |
| Backtest engine + metrics + reports | `app/backtesting/*`, `tests/unit/test_backtest_engine.py` |
| Market-data provider (real public REST) | `app/market_data/providers/binance.py` (ccxt), `tests/unit/test_binance_provider.py` (mocked) |
| Candle validation / UTC normalization | `app/market_data/validators`, `normalizers`, tests |
| Journal persistence (write) | `app/journal/store.py`, `tests/unit/test_journal_portfolio.py` |
| Backend auth (hashed passwords, tokens) | `app/auth/*`, `tests/unit/test_auth.py` |
| Live paper dashboard endpoints | `app/api/dashboard.py`, `app/services/paper_session.py`, `tests/unit/test_paper_session.py` |
| Live-gate status evaluator | `app/execution/live_gate.py`, `tests/unit/test_testnet_and_live_gate.py` |
| Advisory AI / news (no execution coupling) | `app/ai`, `app/news`; static import test in `test_ai_analyst.py` |

---

## 3. Partially implemented features

| Item | File / symbol | Gap | Severity |
|---|---|---|---|
| Live market-data feed | `app/market_data/websocket/client.py` | Generic protocol only; **no Binance stream URL/adapter**, no default transport; `is_stale` is passive (does not trigger reconnect) | High (for live-feed goals) |
| Journal read/query | `app/journal/store.py` | Write-only; no methods to read back orders/fills/decisions for the API | Medium |
| Monitoring readiness | `app/monitoring/health.py` | Flag aggregator; no live DB/Redis/market-data probes; `WebhookAlertChannel` is an intentional no-op | Medium |
| Candle staleness | `app/market_data/validators/candles.py` | Structural checks (dup/gap/continuity) but **no age-vs-now** stale rejection | Medium |
| News → risk integration | `app/news/sentiment.py` | Complete logic but **not wired** into `RiskEngine` | Low (out of Phase-16 scope to wire) |
| Testnet adapter | `app/execution/exchange/testnet.py` | Complete adapter but **unwired** (no factory, tests only) — good for safety, incomplete as a feature | Low |
| Portfolio service reuse | `app/portfolio/service.py` | Not used by the live dashboard (`PaperSession` inlines equivalent math) → duplicate logic | Low |

---

## 4. Placeholder or disconnected features

| Item | File / symbol | Note | Severity |
|---|---|---|---|
| Legacy `/api/*` surface | `app/api/routes.py` | `/api/portfolio/summary` returns hard-coded `"10000"`; `/api/equity-curve` returns a synthetic series; `/api/controls/*` keep **separate** in-memory kill-switch/pause state. Registered but **unused by the frontend** → two divergent API surfaces | Medium |
| Futures/leverage | `app/execution/futures.py` | Pure math, **unwired** to execution (correct for Phase 16, but disconnected) | Low |
| Frontend demo/mock data | `frontend/lib/mock-data.ts` | Fallback used only when backend is unreachable; still ships in the bundle | Low |
| No orchestrator | *(absent)* `app/services/trading_orchestrator.py` | Orchestration currently lives inside `PaperSession` + dashboard, tied to synthetic data; there is no explicit event-driven orchestrator consuming normalized closed candles | High (Stage 4 target) |
| No CLI | *(absent)* `app/cli.py` / `__main__` | No `python -m app.cli paper-run` entrypoint | High (Stage 7 target) |

---

## 5. Safety defects

| Finding | File / symbol | Assessment | Severity |
|---|---|---|---|
| AI/news → execution coupling | `app/ai/*`, `app/news/*` | **None** — verified no imports of gateway/paper/risk. Advisory only. | OK (no defect) |
| Live execution reachability | `app/execution/*`, `PaperSession` | **Unreachable** with default flags: no live backend is ever instantiated; paper backend is always used; kill switch halts globally; live-mode branch rejects unless all 9 gates pass. | OK (no defect) |
| Kill-switch default | `app/core/config.py` `kill_switch_enabled=False` | Not a code defect, but Phase 16 requires `KILL_SWITCH_ENABLED=true` while running this phase → must be set in `.env`. | Note |
| WS future-timestamp check mixes naive/aware | `app/market_data/websocket/client.py` (`is_stale`/future check uses `utc_now().replace()`) | Minor UTC-policy inconsistency; can misjudge future-dated ticks. | Low |
| Reduce-only exit sizing bypass | `app/services/paper_session.py` `_close_symbol` | Passes a tight protective stop so the risk engine sizes the **full** exit. This **reduces** risk (closing), still routes through the risk engine, and does not touch safety gates — but it circumvents `max_risk_per_trade` sizing for exits and should be documented explicitly. | Low |

No secrets were found committed. No `float` is used for money in the money path (ccxt floats are converted via `Decimal(str(...))`). No naive `datetime.now()`/`utcnow()` in `app/`.

---

## 6. Functional defects

| Finding | File / symbol | Impact | Severity |
|---|---|---|---|
| Live lifecycle is not persisted | `app/services/paper_session.py` | Orders/fills/risk decisions/positions live only in memory; **not restart-safe** and not written to the journal DB. Fails Phase-16 "restart-safe persistence" and "journal every decision". | High |
| No real-data → strategy path | `PaperSession.run_strategy_tick` uses `_live_series` (synthetic) | The strategy never evaluates **real** public candles in the running app; only the backtest and (to-be-built) CLI would. | High |
| Dual API state | `app/api/routes.py` vs `app/api/dashboard.py` | Divergent kill-switch/pause/portfolio state can confuse operators/tests. | Medium |
| Backtest test assertions weak | `tests/unit/test_backtest_engine.py` | `test_no_lookahead_context_window` asserts only `isinstance(trade_count, int)`; `>= 0` is always true. | Low |
| WS `test_rest_fallback_on_failure` | `tests/unit/test_websocket_client.py` | Calls `fallback()` manually and bumps the metric instead of exercising the client loop. | Low |

---

## 7. Missing tests

| Missing | Why it matters |
|---|---|
| Deterministic **offline replay** integration (candles→…→journal→metrics) | Core Phase-16 proof (Stage 8); does not exist |
| **Failure-mode** tests (Stage 9 list: disconnect, malformed msg, dup/out-of-order/stale candle, warm-up, strategy exception, insufficient balance, DB tx failure, dup order/fill, restart, shutdown, kill-switch, live-gate single-failure, AI-influence attempt, news outage, frontend failure, invalid config) | Robustness proof; mostly absent |
| **HTTP-level** API tests (dashboard/auth `/api/*`) | Route regression coverage; none exist |
| **Log-redaction** test (Stage 11) | Prove secrets never appear in structured logs |
| Orchestrator tests | Orchestrator does not exist yet |
| Risk **boundary/table** tests | Some coverage exists in `test_risk_engine.py`; Phase 16 asks for explicit table-driven per-rule boundaries |

---

## 8. Frontend/backend integration gaps

- **No missing endpoints:** every `frontend/lib/backend.ts` path maps to a registered backend route (post the dashboard work). Verified in Stage-1 router audit.
- **Divergent legacy surface:** `/api/*` in `routes.py` is unused by the UI and returns placeholder data — should be reconciled or clearly deprecated.
- **Production mock data present:** `frontend/lib/mock-data.ts` fallback still ships; Phase 16 Stage 10 asks to remove production-facing mock data (decision needed — it is the app's documented "never blank-screen" resilience).
- Auth `session`/`logout` are Next-only; `POST /auth/verify` on the backend is unused (frontend verifies locally with the shared secret).

---

## 9. Database and migration gaps

| Finding | File | Severity |
|---|---|---|
| `alembic/env.py` does not import `app.auth.store` | `alembic/env.py` (imports only `market` + `journal`) | `users` table is absent from `target_metadata` during Alembic autogenerate; migration `0003_users.py` exists but future `UserORM` changes won't be detected | Medium |
| Journal ORM nullability drift | `app/journal/store.py` vs `alembic/versions/0002_phase9_journal.py` | ORM omits `nullable=False` on many columns the migration marks `NOT NULL`; runtime always populates them, but metadata diverges | Low |
| Live lifecycle not written to journal tables | `paper_session.py` | Tables exist and are tested in isolation, but the running app never inserts into them | High (functional, see §6) |

Migrations `0001`, `0002`, `0003` apply cleanly to a fresh SQLite DB (verified during earlier setup). Model/migration table shapes otherwise match.

---

## 10. Dependency and configuration problems

| Finding | Impact | Severity |
|---|---|---|
| No `mypy` in `[project.optional-dependencies].dev` | Stage-2 `mypy app` cannot run without adding it; no `[tool.mypy]` config | Medium |
| No `[tool.ruff]` config; `ruff format` not configured | `ruff check .` yields ~291 findings (pre-existing repo style); `ruff format --check` would flag many files | Medium |
| No `docker-compose.yml` / `Dockerfile` | Stage-2 `docker compose config` fails; Docker instructions cannot validate | Medium |
| No CLI entrypoint / `[project.scripts]` | Stage-7 `python -m app.cli paper-run` must be created | High |
| `redis` dependency present but unused at runtime | `REDIS_URL` configured; nothing connects | Low |

---

## 11. Severity roll-up

**Critical:** none found (no live-order path, no secret leakage, no float-money, no AI/news→execution coupling).

**High:**
- Live paper lifecycle is in-memory only — not restart-safe, not journalled (§6, §9).
- No explicit orchestrator consuming real normalized candle events (§4, Stage 4).
- No public-data CLI paper-run (§4, §10, Stage 7).
- No deterministic offline replay integration test (§7, Stage 8).
- Live websocket feed not wired to a real source (§3).

**Medium:**
- Dual/legacy `/api/*` placeholder surface (§4, §6, §8).
- `alembic/env.py` missing `users` import (§9).
- No mypy/ruff-format/docker config (§10).
- Monitoring readiness is flag-only; webhook is a no-op (§3).

**Low:**
- WS naive/aware timestamp check; reduce-only exit sizing note; weak backtest/WS tests; journal nullability drift; frontend mock fallback; unused testnet/futures/portfolio helpers.

---

## 12. Recommended remediation (Phase 16 order)

1. **Fix `alembic/env.py`** to import `app.auth.store` (metadata completeness). *(Medium, quick)*
2. **Build `app/services/trading_orchestrator.py`** (Stage 4): consume normalized closed candles, reject stale/dup/out-of-order, run indicators+strategy, journal **every** decision incl. HOLD, route actionable signals through `RiskEngine`/`OrderGateway` to the paper engine, process fills, update portfolio, and **persist orders/fills/risk decisions to the journal DB** with deterministic client-order-ids + idempotency for restart safety.
3. **Add `app/cli.py` `paper-run`** (Stage 7): public Binance REST (ccxt) closed-candle polling, PAPER banner, kill-switch-honouring, graceful shutdown, session summary; no live path reachable.
4. **Add deterministic offline replay integration test** (Stage 8) covering BUY/HOLD/SELL/reject + a completed paper trade + idempotency, using an embedded candle fixture (no network).
5. **Add failure-mode tests** (Stage 9) and a **log-redaction** test (Stage 11).
6. **Add risk table-driven boundary tests** (Stage 6).
7. **Reconcile the legacy `/api/*` surface** or clearly mark it deprecated (avoid divergent state).
8. **Add tooling/config** decisions for mypy/ruff-format/docker (Stage 2 truthfully documented).
9. **Docs + truthful roadmap** (Stage 12), including data-flow doc (Stage 3).

---

## Final verdict

**Partially runnable.**

The backend and frontend start, 122 tests pass, and the dashboard shows **live paper data** driven by the real risk and paper-execution engines. However, the repository is **not yet "paper-trading ready" in the Phase-16 sense**: there is no real-public-data ingestion feeding the strategy in the running app, no explicit event-driven orchestrator, the live lifecycle is in-memory (not restart-safe, not journalled), there is no public-data CLI paper-run, and there is no deterministic offline replay proof. Live trading is **not** reachable (correct), and this phase must never be classified as testnet- or live-ready.

Target after Stages 4–9: **Paper-trading ready** (offline replay + public-data paper-run, journalled, restart-safe), still **not** testnet/live ready.
