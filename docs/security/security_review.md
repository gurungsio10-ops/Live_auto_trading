# Security review — Project Atlas (durable paper milestone)

Date: 2026-08-05

## Scope

Application security review of FastAPI backend, Next.js BFF, auth, admin token usage, logging, and Docker/compose defaults after the durable paper-trading milestone.

## Resolved / mitigated in this milestone

| Finding | Status |
| --- | --- |
| Paper state lost on restart | Mitigated — hydrate/persist via DB |
| Scheduler could imply live trading | Mitigated — paper-only, disabled by default, admin-gated enable |
| Secrets in Prometheus metrics | Mitigated — `/metrics` exposes counters/labels only |
| ADMIN_API_TOKEN in client JS | Mitigated — FE smoke-check + server-only BFF headers |
| System health hard-coded OK | Mitigated — DB probe + scheduler status |
| Exception leakage on readiness | Mitigated — database errors truncated / typed |

## Remaining risks (accepted for paper-local ops)

| Risk | Notes |
| --- | --- |
| Dashboard root mutators lack admin token | Next.js session auth gates UI; raw API still callable on localhost |
| Demo BFF fallback on failed writes | Soft-200 demo responses remain when backend down — operators must watch Demo banner |
| Default auth secret in development | `ATLAS_AUTH_SECRET` must be changed outside local/dev |
| Dependency CVEs in npm tree | `npm audit` reports high findings in transitive deps — upgrade Next/eslint path in a follow-up |
| Dual historical schema on long-lived Postgres | Environments may contain tables from experimental branches; migrations are idempotent where possible |
| CSRF on cookie session | Same-site dashboard assumption; add CSRF if exposing cross-site |

## Secure defaults

- `TRADING_MODE=paper`
- `LIVE_TRADING_ENABLED=false`
- `SCHEDULER_ENABLED=false`
- Live execute endpoints raise `LiveTradingDisabledError`
- Admin token fail-closed when unset for `/api/v1` kill-switch/reset/scheduler mutators

## Never request / never store in frontend

- Seed phrases, private keys, exchange API secrets, admin tokens in `localStorage`
