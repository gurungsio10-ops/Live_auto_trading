# Paper V1 Acceptance Report

**Result:** PASSED
**Harness:** `scripts/paper_v1_acceptance.py`
**Evidence JSON:** `docs/release/PAPER_V1_ACCEPTANCE_EVIDENCE.json`
**Fixed candle start:** `2026-08-05T12:00:00+00:00`
**Starting balance:** `10000` USDT
**Symbol:** `BTC/USDT`

## Inputs

- Deterministic EMA crossover buy fixture (`force_buy_on_last=True`, fixed start)
- Deterministic EMA crossover sell fixture (bearish dump) for signal generation
- Reduce-only gateway exit at entry mark when strategy sell is risk-rejected (daily-loss on dump mark)
- In-memory SQLite with full ORM metadata (`Base.metadata.create_all`)

## Step evidence

| Step | OK | Key outputs |
|------|----|-------------|
| `1_session_creation` | yes | cash=10000; reserved_cash=0; mode=paper |
| `2_market_data_ingestion` | yes | candle_count=41; last_close=65000.00 |
| `4_risk_rejection` | yes | reason=RiskDecision.HALTED/RiskReasonCode.KILL_SWITCH_ACTIVE |
| `3_signal_generation` | yes | direction=buy |
| `5_accepted_buy` | yes | order_status=FILLED; correlation_id=3465c52a8c4d4e0c990921535a227a85; idempotent_replay=False |
| `6_fill` | yes | order_status=FILLED |
| `7_position_creation` | yes | count=1; qty=0.01538462; entry=65039.000000 |
| `8_reserved_capital` | yes | cash=8998.39909952000000; reserved_cash=0; available=8998.39909952000000 |
| `9_sell_exit` | yes | path=gateway_reduce_only; accepted=True; signal=sell; order_status=FILLED; correlation_id=c3e9726c8984477bb4426f53d26c8272; open_positions_after=0 |
| `10_closed_trade` | yes | trade_count=1; trade_ids=['ct-1b12e6e854284b678dbd1fee592521d7'] |
| `11_pnl` | yes | realized=-1.60; unrealized=0.00; net=-1.60 |
| `12_fees` | yes | total_fees=2.000600239999999808 |
| `13_equity_curve` | yes | points=1; last_equity=9997.40 |
| `14_performance_metrics` | yes | roi_pct=-0.02600; win_rate=0; profit_factor=0E+18; max_drawdown=0.00026; trade_count=1 |
| `22_csv_export` | yes | bytes=487; header_ok=True |
| `23_json_export` | yes | bytes=1212 |
| `15_restart` | yes |  |
| `16_state_hydration` | yes | cash=9997.399039579892000000; reserved_cash=0; kill_switch=True; expected_cash=9997.399039579892000000; expected_reserved=0 |
| `17_reconciliation` | yes | cash_non_negative=True; available_identity=9997.399039579892000000 |
| `18_scheduler_resume` | yes | processed_keys=2; note=scheduler resumes via restored cycle keys + run_paper_trading_cycle |
| `19_duplicate_cycle_prevention` | yes | idempotent_replay=True; accepted=True |
| `20_kill_switch` | yes | detail=RiskDecision.HALTED/RiskReasonCode.KILL_SWITCH_ACTIVE; kill_switch_enabled=True |
| `live_money_impossible` | yes | allowed=False; checklist_complete=False; reason_code=RiskReasonCode.INVALID_CREDENTIALS |
| `21_paper_reset` | yes | cash_after_reset=10000; note=API reset still requires admin token + RESET_PAPER_ACCOUNT confirm |
| `24_dashboard` | yes | routes=['/performance', '/trades', '/trades/[id]', '/reports']; bff=/api/analytics/* |

## Mid-flight open position (post-buy, pre-exit)

```json
{
  "cash": "8998.39909952000000",
  "reserved_cash": "0",
  "position_qty": "0.01538462"
}
```

## Reconciliation totals (post-restart)

```json
{
  "ok": true,
  "cash": "9997.399039579892000000",
  "reserved_cash": "0",
  "kill_switch": true,
  "expected_cash": "9997.399039579892000000",
  "expected_reserved": "0"
}
{
  "ok": true,
  "cash_non_negative": true,
  "available_identity": "9997.399039579892000000"
}
```

## Notes

- Kill-switch rejection reason: `RiskDecision.HALTED/RiskReasonCode.KILL_SWITCH_ACTIVE`.
- Live gate `allowed` remains hard-false even when checklist conditions are forced.
- Duplicate cycle after hydrate returned `idempotent_replay=true`.
- Closed-trade journal rows are written via analytics recorder (idempotent trade ids).
- Position replace persistence flush regression covered by `tests/unit/test_position_persist_replace.py`.
