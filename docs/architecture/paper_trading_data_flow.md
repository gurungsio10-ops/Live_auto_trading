# Paper-Trading Data Flow (as implemented)

This document reflects the pipeline **as it exists after Phase 16**, centred on
`app/services/trading_orchestrator.py`. Every actionable order passes through
`app/risk/engine.py` via `OrderGateway`; AI and news never authorize execution;
live execution is unreachable in paper mode.

## Component diagram

```mermaid
flowchart TD
    subgraph ingest[Market data ingestion]
        SRC[Public data source<br/>ccxt REST or offline sample]
        NORM[normalizers/timestamps<br/>UTC normalize]
        VAL[validators/candles<br/>OHLC + continuity]
    end

    subgraph orch[TradingOrchestrator]
        VG[Validate: closed / not stale /<br/>not duplicate / in-order]
        IND[indicators/*]
        STR[strategies/ema_trend<br/>deterministic]
        JSIG[journal: every decision incl HOLD]
        GW[OrderGateway]
        RISK[risk/engine.py]
        PAPER[execution/paper engine]
        PORT[portfolio state<br/>Decimal, UTC]
        JORD[journal: order / fill / risk decision]
        MET[metrics / snapshot]
    end

    subgraph advisory[Advisory - NEVER authorize orders]
        AI[ai/analyst]
        NEWS[news/sentiment]
    end

    SRC --> NORM --> VAL --> VG --> IND --> STR --> JSIG
    STR -->|BUY/SELL/EXIT| GW --> RISK
    RISK -->|APPROVED/REDUCED| PAPER --> PORT --> JORD --> MET
    RISK -->|REJECTED/HALTED| JORD
    STR -.->|HOLD| MET
    AI -. advisory only .- MET
    NEWS -. advisory only .- MET

    MET --> API[API / dashboard]
    MET --> CLI[CLI paper-run summary]
```

## Sequence (one closed candle)

```mermaid
sequenceDiagram
    participant Feed as Data feed (ccxt/offline)
    participant Orch as TradingOrchestrator
    participant Strat as EMATrendStrategy
    participant Jrnl as JournalStore (DB)
    participant Gate as OrderGateway
    participant Risk as RiskEngine
    participant Paper as PaperTradingEngine

    Feed->>Orch: process_candle(candle)
    Orch->>Orch: validate (closed? dup? order? stale?)
    alt invalid
        Orch->>Jrnl: record_system_event(CANDLE_REJECTED)
        Orch-->>Feed: CandleOutcome(accepted=false)
    else valid
        Orch->>Orch: set mark price, extend window
        Orch->>Strat: evaluate(context)
        Strat-->>Orch: TradeSignal (BUY/SELL/EXIT/HOLD)
        opt actionable & not duplicate signal
            Orch->>Gate: submit(OrderRequest, RiskContext)
            Gate->>Risk: evaluate(request, context)
            alt REJECTED/HALTED
                Risk-->>Gate: RiskEvaluation(reject/halt)
                Gate-->>Orch: RiskBlockedError
                Orch->>Jrnl: record_risk_decision + record_order(REJECTED)
            else APPROVED/REDUCED
                Risk-->>Gate: RiskEvaluation(approved_qty)
                Gate->>Paper: submit(request, evaluation)
                Paper-->>Gate: Order (filled/partial) + Fill(s)
                Gate-->>Orch: Order
                Orch->>Jrnl: record_risk_decision + record_order + record_fill
            end
        end
        Orch->>Jrnl: record_signal (every decision incl HOLD)
        Orch-->>Feed: CandleOutcome(accepted=true, ...)
    end
```

## Per-transition contract

| Transition | Producer | Consumer | Input → Output | Persistence | Errors | Retry | Idempotency | Health | Tests |
|---|---|---|---|---|---|---|---|---|---|
| Source → candle | ccxt / `sample_market` | orchestrator | rows → `Candle` (Decimal, UTC) | none | feed error → backoff, `errors++`, clean shutdown | bounded exp. backoff (CLI + `providers/retry`) | last-open cursor skips seen | `stats.errors` | `test_cli_paper_run`, `test_binance_provider` |
| Normalize/validate | `normalizers`, `validators` | orchestrator | `Candle` → `Candle`/reject | none | reject reason code | — | dup/gap detection | — | `test_timestamp_normalizer`, `test_candle_validators` |
| Validate (orch) | orchestrator | orchestrator | `Candle` → accept/reject | `system_events` | INCOMPLETE/DUPLICATE/OUT_OF_ORDER/STALE | — | seen-candle set + last-open | `candles_rejected` | `test_orchestrator` |
| Indicators/strategy | `indicators`, `strategies` | orchestrator | window → `TradeSignal` | `signals` (every decision) | strategy exception contained | — | signal fingerprint dedup | `errors` | `test_indicators`, `test_ema_trend_strategy`, replay |
| Risk | `OrderGateway`→`RiskEngine` | paper engine | `OrderRequest`+`RiskContext` → `RiskEvaluation` | `risk_decisions` | reject/halt journalled (normal outcome) | — | idempotency key | `risk_engine_healthy` | `test_risk_engine`, replay, `test_orchestrator` |
| Execution | `PaperTradingEngine` | portfolio/journal | approved request → `Order`+`Fill` | `orders`, `fills` | insufficient balance → FAILED | — | idempotency index | — | `test_paper_engine`, replay |
| Portfolio | orchestrator | metrics/API | fills → `PortfolioState` | derived | — | — | recomputed | drawdown/exposure | replay, `test_journal_portfolio` |
| Metrics → API/CLI | orchestrator/`PaperSession` | dashboard/CLI | state → JSON | — | — | — | — | readiness | `test_paper_session`, `test_cli_paper_run` |

## Restart safety

`client_order_id = f"{session[:8]}-{symbolNoSlash}-{open_time_ms}-{direction}"` is
deterministic. Re-feeding the same candle is caught by the seen-candle set
(rejected, no new order); if it ever reached the risk engine, the idempotency key
would also block it. The replay test `test_replaying_same_candle_does_not_duplicate_trade`
asserts no duplicate orders are created or persisted.
