# Metrics definitions — Project Atlas paper analytics

Paper trading only. Simulated results do not guarantee future performance.
AI output is advisory only.

## Data sources

| Metric input | Source |
| --- | --- |
| Starting balance | `Settings.paper_starting_balance` |
| Current equity | Paper session portfolio summary (cash + mark-to-market) |
| Fees | Latest `portfolio_snapshots.fees_paid` when present |
| Closed trades | `closed_positions` table (preferred) |
| Drawdown | Max of stored snapshot drawdowns and live drawdown |

## Formulas

Let \(E_0\) = starting balance, \(E\) = current equity.

- **Total return** = \((E - E_0) / E_0\) when \(E_0 > 0\)
- **Realised P/L** = cumulative realised from paper engine / closed positions
- **Unrealised P/L** = mark-to-market of open positions
- **Maximum drawdown** = max peak-to-trough fraction observed in equity snapshots
- **Win rate** = winning closed trades / total closed trades (undefined if total = 0)
- **Profit factor** = gross wins / abs(gross losses) (undefined if no losses)
- **Average win / average loss** = mean of positive / absolute mean of negative closed P/L
- **Expectancy** = mean closed-trade P/L
- **Average holding duration** = mean `(closed_at - opened_at)` in seconds

Division by zero returns `null` / omitted and surfaces `insufficient_data: true`.

## Labelling rules

- Fewer than 5 closed positions → `insufficient_data: true`
- Metrics are **not annualised** for short samples
- UI must not present paper metrics as expected future returns
- Offline candle cycles are labelled `market_data_mode: offline_fixture`

## Endpoint

`GET /api/v1/analytics/paper`
