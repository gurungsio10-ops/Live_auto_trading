# Release Readiness Report — Atlas Paper v1

**Branch:** `release/atlas-paper-v1`  
**PR:** [#34](https://github.com/gurungsio10-ops/Live_auto_trading/pull/34)  
**Base tip:** PR #28 `cursor/codespaces-auto-start-e3a2` (`2ed644a`) + consolidation commits  
**Report date:** 2026-08-05 (UTC, release-engineer pass)  
**Companion docs:** `docs/PR_CONSOLIDATION_AUDIT.md`, `docs/MOBILE_UI_AUDIT.md`

## Honest completion percentages

| Area | % | Notes |
|------|--:|-------|
| Codebase architecture | **90%** | Canonical paper cycle → risk → paper broker → dual-write; hydrate account/legacy fallbacks covered |
| Paper trading | **92%** | Deterministic cycles, strategies, scheduler, kill switch, restart hydrate; coverage ≥85.00% with precision=2 |
| Testnet | **55%** | Bybit/public MD + offline fallback present; Binance Spot Testnet pipeline remains on PR #20 (not merged) |
| Mobile UI | **85%** | Required IA + viewports verified; polish remaining on dense action wrap |
| Deployment readiness | **82%** | Compose validates; Codespaces scripts present; CI coverage gate hardened |
| Live-money readiness | **0%** | Intentionally hard-blocked; `LiveTradingGate.allowed` always false |
| **Overall paper-v1** | **~91%** | Merge-ready pending human review + green Actions on latest tip |

## What is complete

- Deterministic paper cycles (`run_paper_trading_cycle`) with offline candle fallback
- Strategies: EMA crossover, EMA+RSI, RSI mean reversion, Donchian breakout
- PostgreSQL dual-write checkpoint / `paper_accounts` / risk / strategy state (Alembic through `0006`)
- Restart hydrate verified: cash + open position survived backend restart after paper cycle fill
- Continuous scheduler with explicit start/stop (`/api/trading/start|stop`)
- Central risk engine on OrderGateway path; kill switch blocks cycles (HTTP 423)
- Reconciliation + fail-closed persistence on cycle write failure
- Admin auth on mutating APIs; unauthorised kill-switch → 401
- Frontend fail-closed BFF (503 + `backend_error`, no invented portfolio)
- Health / ready / metrics surfaces; Docker Compose config valid
- Mobile bottom nav Home/Trade/Positions/Activity/More; desktop sidebar ≥ lg
- Attribution footer: “Project Atlas — Developed by Saugat Gurung”
- Journal fingerprint truncation fix (≤256) for scheduler journal writes

## What remains incomplete

- Manual dashboard `/orders` can reject with `DATA_STALE` if market-data timestamp is not refreshed (cycle path refreshes it)
- Concurrent scheduler + journal edge cases previously hit `StringDataRightTruncationError` on fingerprint (mitigated by truncation; soak longer under load)
- PR #20 Binance Spot Testnet not consolidated into this release
- Control-centre / premium UI from PRs #31–#33 not merged (backend CI red / API divergence)
- Live trading remains impossible by design

## Automated verification (executed — release-engineer pass)

| Check | Result |
|-------|--------|
| `pytest --cov=app --cov-fail-under=85 --cov-precision=2` | **301 passed**, coverage **85.54%** |
| `pytest tests/unit -q` (subset invariants) | **passed** (incl. hydrate / kill-switch / secrets / TRADING_MODE) |
| `ruff check app tests` | **passed** |
| `ruff format --check app tests` | **passed** |
| `mypy app` | **passed** (106 files) |
| `alembic upgrade head` (SQLite migrate DB) | **passed** → `0006_paper_durable` |
| `npm --prefix frontend ci` / lint / typecheck / build | **passed** |
| `docker compose config` | **passed** |
| `node frontend/scripts/check-mobile-nav.mjs` | **passed** (320–1440) |
| Secret scan | CI `gitleaks-action` **SUCCESS** on PR #34 |
| `pip-audit` after `ccxt>=4.5.71` | **no known vulns** |
| `npm audit` | Next 14 / nested postcss **high** advisories; fix requires Next 16 (breaking) — deferred |

## Smoke test (executed against Postgres + Redis)

1. Postgres + Redis already healthy via Compose  
2. `alembic upgrade head` applied  
3. Backend `uvicorn` on `:8000` with `DATABASE_URL=postgresql+asyncpg://atlas:atlas@127.0.0.1:5432/atlas`  
4. Frontend `next dev` on `:3000`  
5. `GET /ready` → `ready`, `database_ok: true`  
6. `POST /api/trading/start` → scheduler `running: true`  
7. Offline/public MD path via paper cycle  
8. EMA crossover produced **buy** signal  
9. Risk approved / reduced as applicable  
10. Simulated fill updated portfolio (cash `8998.40`, 1 position)  
11. Journal / checkpoint dual-write observed (`paper_checkpoint`, `paper_accounts`, `positions`)  
12. Dashboard portfolio reflected values  
13. Backend restarted  
14. **Hydrate OK** — cash + position count matched pre-restart  
15. Kill switch activated  
16. New cycles blocked (`423 Kill switch active`)  
17. Read-only `GET /portfolio` remained `200` with kill switch reflected  

## Safety invariants (verified)

- Default mode PAPER; `ENABLE_LIVE_TRADING` / `live_trading_enabled` false  
- `LiveTradingGate.evaluate().allowed is False` even with green checklist  
- Futures / leverage / withdrawals blocked via `SafetyGuard`  
- No secrets in browser (admin token server-side only)  
- Decimal money path; UTC timestamps in API payloads  

## Known risks

1. Scheduler journal persistence can fail-closed if ORM column constraints are violated — fingerprint now truncated; continue monitoring soak.  
2. Dashboard manual tickets require fresh MD timestamp or risk returns `DATA_STALE`.  
3. Merging divergent UI PRs (#31–#33) without rebase onto this tip will reintroduce backend CI failures.  

## Exact manual steps remaining

Follow `docs/PR_CONSOLIDATION_AUDIT.md` § “Exact human steps in GitHub”:

1. Mark PR #34 ready for review.  
2. Merge PR #34 → `main` with a **merge commit** only when Actions are green.  
3. Close superseded PRs (#3–#18, #21–#28, #29–#32) without merging.  
4. Keep PR #20 open (testnet).  
5. Rebase PR #33 onto post-merge `main` before any future integration.  
6. Rotate demo `ADMIN_API_TOKEN` / dashboard passwords before shared hosting.  
7. Optional: `python -m app.cli paper-soak --seed 42` on staging Postgres.

## Live-money readiness

**Not ready. Do not enable.** Live gate remains fail-closed. No “Go Live” UI.
