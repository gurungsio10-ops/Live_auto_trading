# Live trading readiness checklist

**Status: NOT READY — all items remain unchecked.**

Do not enable live money trading until every item below is explicitly completed, reviewed, and approved. This milestone implements **paper trading only**.

## Gates (all required)

- [ ] `TRADING_MODE=live` deliberately selected in a hardened environment
- [ ] `LIVE_TRADING_ENABLED=true` with dual-control approval
- [ ] Kill switch default posture reviewed; operational runbooks signed off
- [ ] Exchange credentials stored in a secrets manager (never in git)
- [ ] Valid live approval token rotation process
- [ ] Risk engine limits re-validated against account size
- [ ] Market data redundancy + stale-data alerting
- [ ] Database backups + restore drill
- [ ] Reconciliation job against exchange balances/positions
- [ ] Testnet soak period completed with no critical incidents
- [ ] Incident response + kill-switch drills documented
- [ ] Legal / tax / compliance review for the operator's jurisdiction
- [ ] Live order adapter implemented and audited (currently raises `LiveTradingDisabledError`)
- [ ] Independent code review of execution path
- [ ] Cap on max notional per order and per day enforced in production config

## Explicit non-goals of the current milestone

- Live order placement
- Futures / margin / leverage
- Short selling
- AI-authorized execution

Until this checklist is fully checked by a human operator, keep `TRADING_MODE=paper`.
