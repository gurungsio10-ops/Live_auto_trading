# Incident Response — Project Atlas

Paper-trading personal platform. Treat incidents seriously even without live capital: incorrect kill-switch behavior, demo/BFF confusion, or leaked secrets can still cause operational harm if modes are later expanded.

## 1. Kill-switch procedure

**When:** Unexpected order spam, strategy misbehavior, stale/bad market data driving signals, suspected compromise of admin token, or any “stop trading now” need.

**Steps:**

1. Activate kill switch (API or dashboard):

   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/system/kill-switch/activate \
     -H "X-Admin-Token: $ADMIN_API_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"reason":"<incident id / short reason>"}'
   ```

2. Confirm via `GET /health` or Overview — `kill_switch_enabled` true.
3. Pause strategy controls if needed (`pause` mutators also require admin token).
4. Do **not** rely on a BFF “success” without checking API health — mutator BFF routes **fail closed** (503) when backend is down; they will not fake activation.
5. Investigate root cause (logs, risk events, last paper cycle payload).
6. Deactivate only after cause is understood and risk accepted.
7. State persists across restart — verify after any process bounce.

**Reads remain available** while the kill switch blocks new orders.

## 2. Market-data unhealthy

**Symptoms:** Stale candles, empty feeds, Binance HTTP 451, readiness/monitoring flags for `market_data`, risk reasons tied to market-data health.

**Actions:**

1. Prefer offline paper path: `POST /api/v1/paper/cycle/run` fixture or `python -m app.cli paper-run --offline`.
2. Check `MARKET_DATA_STALE_SECONDS` and network egress.
3. If live/public feed is required for research, switch venue or network — do not “force” LIVE.
4. Risk engine / live gate treat unhealthy market data as a blocking condition for live readiness (live submit remains hard-blocked regardless).

## 3. Reconciliation mismatch

**Context:** Risk and live-gate state include `reconciliation_healthy`. Paper balance accounting is validated in tests against fills (fees included). Full exchange↔local reconciliation for live accounts is **not** a shipped product feature while LIVE is hard-blocked.

**If paper balances / positions look wrong:**

1. Activate kill switch.
2. Capture `GET /api/v1/portfolio`, orders, fills, risk decisions, and DB checkpoint tables.
3. Compare last cycle idempotency keys (`system_state`) — duplicate cycles should no-op.
4. Prefer paper reset only after backup/export of journal evidence:

   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/paper/reset \
     -H "X-Admin-Token: $ADMIN_API_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"confirm":"RESET_PAPER_ACCOUNT"}'
   ```

5. File a bug with fixture inputs; do not “correct” balances by hand against a real exchange.

**If preparing any future live work:** a reconciliation mismatch must keep `reconciliation_healthy=false` and block live gates — see do-not-go-live checklist.

## 4. Secret leak response

**Examples:** Committed `.env`, pasted `EXCHANGE_API_*`, `ADMIN_API_TOKEN`, `ATLAS_AUTH_SECRET`, or dashboard password in logs/tickets.

**Actions:**

1. Rotate all exposed secrets immediately (exchange keys, admin token, auth secret, DB passwords).
2. Revoke exchange API keys at the venue; never reuse leaked keys.
3. Confirm `.env` is gitignored; scrub history if a commit leaked secrets (Gitleaks runs in CI — treat failures as blocking).
4. Assume any leaked `ADMIN_API_TOKEN` allowed mutators — activate kill switch after rotation if the process is still running with the old token in memory (restart with new env).
5. Review access logs / recent mutator calls if available.
6. Do not put real secrets in docs, screenshots, or issue bodies.

## 5. Do-not-go-live checklist

Do **not** enable live money trading. Even with all of the following, submission remains hard-blocked in code (`LiveTradingGate.allowed` is always false; `assert_startup_safe` raises on LIVE):

- [ ] `ENABLE_LIVE_TRADING=true`
- [ ] `TRADING_MODE=live` / `ATLAS_RUNTIME_MODE=LIVE` / `EXCHANGE_ENV=live`
- [ ] Exchange credentials present
- [ ] `LIVE_APPROVAL_TOKEN` set
- [ ] `LIVE_STARTUP_ACK=I_UNDERSTAND_LIVE_TRADING_RISKS`
- [ ] Kill switch off
- [ ] Risk / market-data / DB / reconciliation healthy

**Operator rule:** Keep `ATLAS_RUNTIME_MODE=PAPER` (or TESTNET for non-money experiments where supported) and `ENABLE_LIVE_TRADING=false`. See `docs/operations/live_trading_readiness_checklist.md` — items remain unchecked for production live use.

## Severity quick reference

| Severity | Example | Immediate action |
|----------|---------|------------------|
| Sev-1 | Suspected unauthorized mutators / leaked admin token | Kill switch + rotate secrets + restart |
| Sev-2 | Bad market data driving paper cycles | Kill switch or pause; switch offline |
| Sev-3 | Demo banner / read-only demo data confusion | Restore backend connectivity; do not trust demo reads for decisions |
| Sev-4 | Cosmetic UI / docs drift | Ticket; no trading impact |

## Related

- `docs/operations/DEPLOYMENT_RUNBOOK.md`
- `docs/operations/BACKUP_RESTORE.md`
- `docs/operations/RUNBOOK.md`
- `docs/security/THREAT_MODEL.md`
- `app/execution/live_gate.py`
