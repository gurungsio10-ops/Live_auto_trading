# Security Policy — Project Atlas

## Supported scope

Project Atlas is a **paper-trading** platform. This repository’s supported security
boundary for the current milestone is:

- Local / self-hosted paper and offline simulation
- Optional public market-data fetch (read-only)
- Admin-authenticated control-plane mutations

**Live money trading is out of scope and hard-blocked.** Do not treat any
environment as production live trading readiness.

## Paper / live safety boundary

- Default `TRADING_MODE=paper`
- `LiveTradingDisabledError` / live gate must never be bypassed
- No leverage, futures, withdrawals, deposits, or wallet signing
- Every order intent must pass through `app/risk/engine.py` via `OrderGateway`
- Kill switch and reconciliation halt fail closed

## Secret-management rules

- Never commit API keys, admin tokens, passwords, or private keys
- Configure secrets via environment variables or a secret manager
- Never log secrets, authorization headers, or private account data
- Admin tokens must not be exposed to browser-side JavaScript
- Frontend BFFs proxy protected mutations server-side (`ADMIN_API_TOKEN`)

## Vulnerability reporting

If you discover a vulnerability:

1. Do **not** open a public GitHub issue with exploit details
2. Contact the repository maintainers privately
3. Include reproduction steps, impact, and affected versions
4. Allow reasonable time for a fix before public disclosure

## Incident response for leaked credentials

1. Rotate the leaked credential immediately
2. Activate the kill switch (`POST /api/trading/kill-switch`)
3. Pause/stop the scheduler
4. Review `trade_journal` / audit events for unauthorized mutations
5. Run reconciliation and keep trading halted until healthy
6. Reset paper account only with admin auth + `RESET_PAPER_ACCOUNT`

## Operational security checklist

- [ ] `ADMIN_API_TOKEN` set and rotated periodically
- [ ] CORS restricted to known dashboard origins
- [ ] Destructive endpoints require confirmation phrases
- [ ] Dependency audit / secret scan enabled in CI
- [ ] Database backups available before paper resets
- [ ] Readiness fails when reconciliation is unhealthy
- [ ] Live mode remains disabled
